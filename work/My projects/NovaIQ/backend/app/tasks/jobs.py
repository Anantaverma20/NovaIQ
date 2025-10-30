"""
Background job definitions without Celery.

Jobs can be triggered via:
1. Webhook endpoints (POST /webhook/ingest)
2. External cron (curl to webhook)
3. Manual API calls
4. Optional: APScheduler for in-process scheduling

No heavy dependencies like Celery/Redis by default.
"""
from typing import Optional
import json
from datetime import datetime, timezone
from sqlmodel import Session, select, desc

from app.config import get_settings
from app.db.models import Article, InsightDB, HypothesisDB
from app.deps import get_session_context, get_openai_client
from app.services.ingest import run_ingestion
from app.services.vectorstore import add_documents, is_enabled as vectors_enabled


# === Ingestion Job ===

async def job_run_ingestion(
    query: Optional[str] = None,
    max_results: int = 20
) -> dict[str, any]:
    """
    Run ingestion pipeline.
    
    This is the main job for periodic article ingestion.
    Trigger via webhook or manual API call.
    
    Args:
        query: Search query (uses config default if None)
        max_results: Max articles to fetch
    
    Returns:
        Job result dict
    """
    try:
        run = await run_ingestion(query=query, max_results=max_results)
        
        return {
            "status": "success",
            "run_id": run.id,
            "query": run.query,
            "articles_found": run.articles_found,
            "articles_new": run.articles_new,
            "articles_skipped": run.articles_skipped,
            "vectors_added": run.vectors_added,
            "vectors_skipped": run.vectors_skipped,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# === Vector Refresh Job ===

async def job_refresh_vectors() -> dict[str, any]:
    """
    Refresh vector embeddings for un-indexed articles.
    
    This job finds articles where vector_indexed=False and indexes them.
    Useful for backfilling after enabling vectors or API key changes.
    
    Returns:
        Job result dict
    """
    if not vectors_enabled():
        return {
            "status": "skipped",
            "message": "Vectors not enabled",
        }
    
    try:
        with get_session_context() as session:
            # Find un-indexed articles
            statement = (
                select(Article)
                .where(Article.vector_indexed == False)
                .limit(100)  # Process in batches
            )
            articles = session.exec(statement).all()
            
            if not articles:
                return {
                    "status": "success",
                    "indexed": 0,
                    "message": "All articles already indexed",
                }
            
            # Prepare for vector store
            texts = [a.content for a in articles]
            metadatas = [
                {
                    "article_id": a.id,
                    "url": a.url,
                    "title": a.title,
                    "source": a.source,
                }
                for a in articles
            ]
            
            # Add to vectors
            result = await add_documents(texts, metadatas)
            
            # Update database
            if result.get("status") == "success":
                for article in articles:
                    article.vector_indexed = True
                    article.vector_indexed_at = datetime.now(timezone.utc)
                    session.add(article)
                session.commit()
            
            return {
                "status": "success",
                "indexed": result.get("added", 0),
                "skipped": result.get("skipped", 0),
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# === Insight Generation Job ===

async def job_generate_insights(
    lookback_hours: int = 24
) -> dict[str, any]:
    """
    Generate insights from recent articles.
    
    This job:
    1. Fetches unsummarized articles from last N hours
    2. Groups related articles (simple: all together for MVP)
    3. Generates insight summaries via LLM
    4. Persists insights to database
    
    Args:
        lookback_hours: How far back to look for articles
    
    Returns:
        Job result dict
    """
    openai_client = get_openai_client()
    if not openai_client:
        return {
            "status": "skipped",
            "message": "OpenAI client not available",
        }
    
    try:
        with get_session_context() as session:
            # Find recent unsummarized articles
            statement = (
                select(Article)
                .where(Article.summarized == False)
                .order_by(desc(Article.created_at))
                .limit(50)  # Process batch at a time
            )
            articles = session.exec(statement).all()
            
            if not articles:
                return {
                    "status": "success",
                    "insights_generated": 0,
                    "message": "No new articles to summarize",
                }
            
            # For MVP: generate one insight from all articles
            # Production: cluster articles by topic first
            
            # Prepare context for LLM
            context = "\n\n".join([
                f"Article {i+1}: {a.title}\n{a.content[:500]}..."
                for i, a in enumerate(articles[:10])  # Use top 10
            ])
            
            # Generate insight via OpenAI
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract key insights from these articles. "
                                   "Provide: title, summary, 3-5 bullet points, confidence (0-1)."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                response_format={"type": "json_object"},
            )
            
            # Parse response
            insight_data = json.loads(response.choices[0].message.content)
            
            # Create insight record
            insight = InsightDB(
                title=insight_data.get("title", "Insight"),
                summary=insight_data.get("summary", ""),
                bullets=json.dumps(insight_data.get("bullets", [])),
                citations=json.dumps([a.url for a in articles[:10]]),
                article_ids=json.dumps([a.id for a in articles[:10]]),
                confidence=float(insight_data.get("confidence", 0.5)),
            )
            session.add(insight)
            
            # Mark articles as summarized
            for article in articles:
                article.summarized = True
                session.add(article)
            
            session.commit()
            session.refresh(insight)
            
            return {
                "status": "success",
                "insights_generated": 1,
                "insight_id": insight.id,
                "articles_processed": len(articles),
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# === Hypothesis Generation Job ===

async def job_generate_hypotheses(
    insight_id: Optional[int] = None
) -> dict[str, any]:
    """
    Generate hypotheses from insights.
    
    Args:
        insight_id: Specific insight to process (None = all recent)
    
    Returns:
        Job result dict
    """
    openai_client = get_openai_client()
    if not openai_client:
        return {
            "status": "skipped",
            "message": "OpenAI client not available",
        }
    
    try:
        with get_session_context() as session:
            # Find insights without hypotheses
            if insight_id:
                statement = select(InsightDB).where(InsightDB.id == insight_id)
            else:
                # Get recent insights (last 10)
                statement = (
                    select(InsightDB)
                    .order_by(desc(InsightDB.created_at))
                    .limit(10)
                )
            
            insights = session.exec(statement).all()
            
            if not insights:
                return {
                    "status": "success",
                    "hypotheses_generated": 0,
                    "message": "No insights to process",
                }
            
            hypotheses_created = 0
            
            for insight in insights:
                # Check if already has hypotheses
                existing = session.exec(
                    select(HypothesisDB).where(HypothesisDB.insight_id == insight.id)
                ).first()
                
                if existing:
                    continue  # Skip if already processed
                
                # Generate hypotheses via OpenAI
                response = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate 2-3 testable hypotheses from this insight. "
                                       "Each hypothesis should have: hypothesis, rationale, confidence."
                        },
                        {
                            "role": "user",
                            "content": f"Insight: {insight.title}\n\n{insight.summary}"
                        }
                    ],
                    response_format={"type": "json_object"},
                )
                
                # Parse response
                data = json.loads(response.choices[0].message.content)
                hypotheses_list = data.get("hypotheses", [])
                
                # Create hypothesis records
                for hyp_data in hypotheses_list:
                    hypothesis = HypothesisDB(
                        insight_id=insight.id,
                        hypothesis=hyp_data.get("hypothesis", ""),
                        rationale=hyp_data.get("rationale", ""),
                        confidence=float(hyp_data.get("confidence", 0.5)),
                    )
                    session.add(hypothesis)
                    hypotheses_created += 1
                
            session.commit()
            
            return {
                "status": "success",
                "hypotheses_generated": hypotheses_created,
                "insights_processed": len(insights),
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# === Cleanup Job ===

async def job_cleanup_old_runs(days: int = 30) -> dict[str, any]:
    """
    Clean up old ingestion run records.
    
    Args:
        days: Delete runs older than this
    
    Returns:
        Job result dict
    """
    try:
        from datetime import timedelta
        from app.db.models import IngestionRun
        
        with get_session_context() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            statement = select(IngestionRun).where(
                IngestionRun.started_at < cutoff
            )
            old_runs = session.exec(statement).all()
            
            for run in old_runs:
                session.delete(run)
            
            session.commit()
            
            return {
                "status": "success",
                "deleted": len(old_runs),
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
