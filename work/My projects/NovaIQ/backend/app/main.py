"""
FastAPI main application with comprehensive error handling and pagination.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import select, func, desc

from app.config import get_settings, Settings
from app.deps import (
    get_db_session,
    DBSession,
    verify_webhook_secret,
    get_openai_client,
)
from app.db.models import Article, InsightDB, HypothesisDB
from app.db.sqlite import init_db, check_db_health
from app.schemas import (
    ArticleOut,
    ArticleListOut,
    InsightOut,
    InsightListOut,
    HypothesisOut,
    HypothesisListOut,
    AskRequest,
    AskResponse,
    SourceOut,
    IngestionTriggerRequest,
    IngestionStatusOut,
    IngestionTriggerResponse,
    HealthStatus,
    ErrorResponse,
    PaginationParams,
)
from app.services.vectorstore import query_documents, is_enabled as vectors_enabled
from app.tasks.jobs import (
    job_run_ingestion,
    job_refresh_vectors,
    job_generate_insights,
    job_generate_hypotheses,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    print("🚀 Starting RTC Backend...")
    
    # Initialize database
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"⚠️  Database init warning: {e}")
    
    # Check vector availability
    if vectors_enabled():
        print("✓ Vector operations enabled")
    else:
        print("⚠️  Vector operations disabled (OPENAI_API_KEY not set)")
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")


app = FastAPI(
    title="RTC Backend",
    version="0.1.0",
    description="Research Tech Collector with graceful degradation",
    lifespan=lifespan,
)


# === Middleware ===

@app.on_event("startup")
async def add_cors_middleware():
    """Configure CORS middleware."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred",
        }
    )


# === Health Check ===

@app.get("/health", response_model=HealthStatus)
async def health_check(settings: Settings = Depends(get_settings)):
    """
    Comprehensive health check.
    
    Checks:
    - Database connectivity
    - Vector store availability
    - Search API configuration
    """
    # Check database
    db_health = check_db_health()
    
    # Check vectors
    vectors_status = {
        "enabled": vectors_enabled(),
        "configured": settings.OPENAI_API_KEY is not None,
    }
    
    # Check search API
    search_status = {
        "configured": settings.search_api_available,
    }
    
    # Determine overall status
    overall_status = "ok"
    if db_health.get("status") != "healthy":
        overall_status = "unhealthy"
    elif not vectors_enabled():
        overall_status = "degraded"
    
    return HealthStatus(
        status=overall_status,
        service="rtc-backend",
        timestamp=datetime.now(timezone.utc),
        database=db_health,
        vectors=vectors_status,
        search_api=search_status,
    )


# === Article Endpoints ===

@app.get("/articles", response_model=ArticleListOut)
async def list_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBSession,
):
    """
    List articles with pagination.
    
    Articles are returned in reverse chronological order (newest first).
    """
    # Get total count
    count_statement = select(func.count(Article.id))
    total = db.exec(count_statement).one()
    
    # Get paginated results
    statement = (
        select(Article)
        .order_by(desc(Article.created_at))
        .offset(offset)
        .limit(limit)
    )
    articles = db.exec(statement).all()
    
    return ArticleListOut(
        items=[ArticleOut.model_validate(a) for a in articles],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/articles/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    db: DBSession,
):
    """Get a specific article by ID."""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return ArticleOut.model_validate(article)


# === Insight Endpoints ===

@app.get("/insights", response_model=InsightListOut)
async def list_insights(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBSession,
):
    """
    List insights with pagination.
    
    Insights are returned in reverse chronological order.
    """
    # Get total count
    count_statement = select(func.count(InsightDB.id))
    total = db.exec(count_statement).one()
    
    # Get paginated results
    statement = (
        select(InsightDB)
        .order_by(desc(InsightDB.created_at))
        .offset(offset)
        .limit(limit)
    )
    insights = db.exec(statement).all()
    
    # Parse JSON fields
    items = []
    for insight in insights:
        item = InsightOut(
            id=insight.id,
            title=insight.title,
            summary=insight.summary,
            bullets=json.loads(insight.bullets) if insight.bullets else [],
            citations=json.loads(insight.citations) if insight.citations else [],
            confidence=insight.confidence,
            created_at=insight.created_at,
        )
        items.append(item)
    
    return InsightListOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/insights/{insight_id}", response_model=InsightOut)
async def get_insight(
    insight_id: int,
    db: DBSession,
):
    """Get a specific insight by ID."""
    insight = db.get(InsightDB, insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    
    return InsightOut(
        id=insight.id,
        title=insight.title,
        summary=insight.summary,
        bullets=json.loads(insight.bullets) if insight.bullets else [],
        citations=json.loads(insight.citations) if insight.citations else [],
        confidence=insight.confidence,
        created_at=insight.created_at,
    )


# === Hypothesis Endpoints ===

@app.get("/hypotheses", response_model=HypothesisListOut)
async def list_hypotheses(
    insight_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBSession,
):
    """
    List hypotheses with optional filtering by insight.
    """
    # Build query
    count_statement = select(func.count(HypothesisDB.id))
    statement = select(HypothesisDB).order_by(desc(HypothesisDB.created_at))
    
    if insight_id is not None:
        count_statement = count_statement.where(HypothesisDB.insight_id == insight_id)
        statement = statement.where(HypothesisDB.insight_id == insight_id)
    
    # Get total count
    total = db.exec(count_statement).one()
    
    # Get paginated results
    statement = statement.offset(offset).limit(limit)
    hypotheses = db.exec(statement).all()
    
    return HypothesisListOut(
        items=[HypothesisOut.model_validate(h) for h in hypotheses],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/hypotheses/{hypothesis_id}", response_model=HypothesisOut)
async def get_hypothesis(
    hypothesis_id: int,
    db: DBSession,
):
    """Get a specific hypothesis by ID."""
    hypothesis = db.get(HypothesisDB, hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    
    return HypothesisOut.model_validate(hypothesis)


# === RAG / Q&A Endpoint ===

@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    db: DBSession,
):
    """
    Answer questions using RAG over ingested articles.
    
    If vectors disabled, falls back to simple keyword search.
    """
    question = request.question
    
    # Try vector search first
    sources = []
    used_vectors = False
    
    if vectors_enabled():
        # Vector-based retrieval
        docs = await query_documents(question, n_results=request.context_limit)
        used_vectors = True
        
        for doc in docs:
            article_id = doc["metadata"].get("article_id")
            if article_id:
                article = db.get(Article, article_id)
                if article:
                    sources.append(
                        SourceOut(
                            article_id=article.id,
                            title=article.title,
                            url=article.url,
                            relevance=1.0 - (doc.get("distance", 0) / 2),  # Normalize
                        )
                    )
    else:
        # Fallback: simple keyword match in title/content
        keywords = question.lower().split()[:5]  # Top 5 keywords
        
        statement = select(Article).limit(request.context_limit)
        articles = db.exec(statement).all()
        
        for article in articles:
            # Simple relevance score
            content_lower = (article.title + " " + article.content).lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            
            if matches > 0:
                sources.append(
                    SourceOut(
                        article_id=article.id,
                        title=article.title,
                        url=article.url,
                        relevance=matches / len(keywords),
                    )
                )
    
    # Generate answer
    if not sources:
        return AskResponse(
            answer="I don't have enough information to answer this question.",
            sources=[],
            confidence=0.0,
            vectors_used=used_vectors,
        )
    
    # Use OpenAI to generate answer (if available)
    openai_client = get_openai_client()
    if openai_client:
        # Build context from sources
        context = "\n\n".join([
            f"Source {i+1} ({s.title}):\n{db.get(Article, s.article_id).content[:500]}"
            for i, s in enumerate(sources[:3])
        ])
        
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Answer the question using only the provided sources. "
                                   "Cite sources explicitly."
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nSources:\n{context}"
                    }
                ],
            )
            
            answer = response.choices[0].message.content
            confidence = 0.8
        except Exception as e:
            print(f"OpenAI error: {e}")
            answer = "Error generating answer. Please try again."
            confidence = 0.0
    else:
        # No LLM available - return simple response
        answer = (
            f"Found {len(sources)} relevant articles. "
            "Enable OpenAI integration for detailed answers."
        )
        confidence = 0.5
    
    return AskResponse(
        answer=answer,
        sources=sources,
        confidence=confidence,
        vectors_used=used_vectors,
    )


# === Ingestion Endpoints ===

@app.post("/ingest/run", response_model=IngestionTriggerResponse)
async def trigger_ingestion(
    request: IngestionTriggerRequest = IngestionTriggerRequest(),
    settings: Settings = Depends(get_settings),
):
    """
    Trigger manual ingestion run.
    
    This endpoint runs the ingestion job synchronously.
    For background processing, use the webhook endpoint with a queue.
    """
    try:
        result = await job_run_ingestion(
            query=request.query,
            max_results=request.max_results,
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return IngestionTriggerResponse(
            run_id=result["run_id"],
            status="completed",
            message=f"Ingested {result['articles_new']} new articles",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/ingest")
async def webhook_ingest(
    request: IngestionTriggerRequest = IngestionTriggerRequest(),
    verified: bool = Depends(verify_webhook_secret),
):
    """
    Webhook endpoint for scheduled ingestion.
    
    Call this from cron or external scheduler:
    ```bash
    curl -X POST https://your-api.com/webhook/ingest \
      -H "X-Webhook-Secret: your-secret" \
      -H "Content-Type: application/json" \
      -d '{"max_results": 20}'
    ```
    """
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    
    # Run ingestion in background (for production, use task queue)
    # For MVP, run synchronously
    result = await job_run_ingestion(
        query=request.query,
        max_results=request.max_results,
    )
    
    return result


@app.post("/jobs/refresh-vectors")
async def trigger_vector_refresh():
    """Refresh vector embeddings for un-indexed articles."""
    if not vectors_enabled():
        raise HTTPException(
            status_code=503,
            detail="Vector operations not available"
        )
    
    result = await job_refresh_vectors()
    return result


@app.post("/jobs/generate-insights")
async def trigger_insight_generation():
    """Generate insights from recent articles."""
    result = await job_generate_insights()
    return result


@app.post("/jobs/generate-hypotheses")
async def trigger_hypothesis_generation(insight_id: int | None = None):
    """Generate hypotheses from insights."""
    result = await job_generate_hypotheses(insight_id=insight_id)
    return result
