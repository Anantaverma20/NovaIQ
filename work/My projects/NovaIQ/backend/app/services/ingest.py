"""
Ingestion service with deterministic, idempotent ingestion.

Key design principles:
- Idempotent: same content won't be duplicated
- Explicit I/O: clear separation of fetch/process/persist
- Graceful degradation: works without vectors or search API
"""
import hashlib
from typing import Optional
from datetime import datetime, timezone

import httpx
from slugify import slugify
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import Article, IngestionRun
from app.deps import get_session_context
from app.services.vectorstore import add_documents, is_enabled as vectors_enabled


# === Hashing Utilities ===

def hash_url(url: str) -> str:
    """Generate deterministic hash from URL."""
    # Normalize URL before hashing
    normalized = url.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def hash_content(content: str) -> str:
    """Generate deterministic hash from content."""
    # Simple hash of content for duplicate detection
    normalized = " ".join(content.strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# === Article Normalization ===

class NormalizedArticle:
    """Normalized article data with computed fields."""
    
    def __init__(
        self,
        url: str,
        title: str,
        content: str,
        source: str = "web",
        published_at: Optional[datetime] = None,
    ):
        self.url = url
        self.title = title
        self.content = content
        self.source = source
        self.published_at = published_at
        
        # Compute hashes
        self.url_hash = hash_url(url)
        self.content_hash = hash_content(content)
    
    def to_db_model(self) -> Article:
        """Convert to SQLModel Article."""
        return Article(
            url=self.url,
            url_hash=self.url_hash,
            content_hash=self.content_hash,
            title=self.title,
            content=self.content,
            source=self.source,
            published_at=self.published_at,
            vector_indexed=False,
        )


# === External API Fetching ===

async def fetch_from_search_api(
    query: str,
    max_results: int = 20
) -> list[NormalizedArticle]:
    """
    Fetch articles from external search API.
    
    This is the I/O boundary - all external API calls happen here.
    
    Args:
        query: Search query
        max_results: Maximum results to fetch
    
    Returns:
        List of normalized articles
    """
    settings = get_settings()
    
    if not settings.search_api_available:
        print("⚠️  Search API not configured, returning empty results")
        return []
    
    try:
        async with httpx.AsyncClient(
            base_url=settings.SEARCH_API_BASE_URL,
            timeout=30.0,
        ) as client:
            response = await client.get(
                "/api/search",
                params={
                    "q": query,
                    "limit": max_results,
                },
                headers={
                    "Authorization": f"Bearer {settings.SEARCH_API_KEY}",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Normalize results to common format
            articles = []
            for item in data.get("results", [])[:max_results]:
                article = NormalizedArticle(
                    url=item.get("url", ""),
                    title=item.get("title", "Untitled"),
                    content=item.get("snippet", ""),
                    source=item.get("source", "search"),
                    published_at=_parse_datetime(item.get("published_date")),
                )
                
                # Skip articles with insufficient content
                if len(article.content) < 50:
                    continue
                
                articles.append(article)
            
            return articles
            
    except httpx.HTTPError as e:
        print(f"Search API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error fetching from search API: {e}")
        return []


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string, return None if invalid."""
    if not value:
        return None
    try:
        from dateutil import parser
        return parser.parse(value)
    except Exception:
        return None


# === Deduplication ===

def deduplicate_articles(
    articles: list[NormalizedArticle],
    session: Session
) -> list[NormalizedArticle]:
    """
    Filter out articles that already exist in database.
    
    Deduplication by:
    1. URL hash (exact URL match)
    2. Content hash (same content, different URL)
    
    Args:
        articles: List of normalized articles
        session: Database session
    
    Returns:
        List of new articles only
    """
    if not articles:
        return []
    
    # Collect all hashes
    url_hashes = {a.url_hash for a in articles}
    content_hashes = {a.content_hash for a in articles}
    
    # Query existing articles
    statement = select(Article).where(
        (Article.url_hash.in_(url_hashes)) |
        (Article.content_hash.in_(content_hashes))
    )
    existing = session.exec(statement).all()
    
    # Build sets of existing hashes
    existing_url_hashes = {a.url_hash for a in existing}
    existing_content_hashes = {a.content_hash for a in existing}
    
    # Filter to new articles only
    new_articles = [
        a for a in articles
        if a.url_hash not in existing_url_hashes
        and a.content_hash not in existing_content_hashes
    ]
    
    return new_articles


# === Persistence ===

def persist_articles(
    articles: list[NormalizedArticle],
    session: Session
) -> list[Article]:
    """
    Persist articles to database.
    
    Args:
        articles: List of normalized articles
        session: Database session
    
    Returns:
        List of persisted Article models
    """
    db_articles = []
    
    for article in articles:
        db_article = article.to_db_model()
        session.add(db_article)
        db_articles.append(db_article)
    
    session.commit()
    
    # Refresh to get IDs
    for db_article in db_articles:
        session.refresh(db_article)
    
    return db_articles


# === Vector Indexing ===

async def index_articles_to_vectors(
    articles: list[Article],
    session: Session
) -> dict[str, int]:
    """
    Add articles to vector store and update indexing status.
    
    Args:
        articles: List of Article models
        session: Database session
    
    Returns:
        Stats dict with added/skipped counts
    """
    if not articles:
        return {"added": 0, "skipped": 0}
    
    if not vectors_enabled():
        # Mark as skipped but don't fail
        return {"added": 0, "skipped": len(articles)}
    
    # Prepare documents for vector store
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
    
    # Add to vector store
    result = await add_documents(texts, metadatas)
    
    # Update indexing status in database
    if result.get("status") == "success":
        for article in articles:
            article.vector_indexed = True
            article.vector_indexed_at = datetime.now(timezone.utc)
            session.add(article)
        session.commit()
    
    return {
        "added": result.get("added", 0),
        "skipped": result.get("skipped", 0),
    }


# === Main Ingestion Pipeline ===

async def run_ingestion(
    query: Optional[str] = None,
    max_results: int = 20
) -> IngestionRun:
    """
    Execute full ingestion pipeline.
    
    Steps:
    1. Create ingestion run record
    2. Fetch articles from search API
    3. Deduplicate against existing articles
    4. Persist new articles
    5. Index to vector store (if enabled)
    6. Update run status
    
    This operation is idempotent - running multiple times with same query
    won't create duplicates.
    
    Args:
        query: Search query (uses default if None)
        max_results: Maximum articles to fetch
    
    Returns:
        IngestionRun record with stats
    """
    settings = get_settings()
    query = query or settings.INGESTION_QUERY
    
    with get_session_context() as session:
        # Create run record
        run = IngestionRun(
            query=query,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        
        try:
            # Step 1: Fetch from external API
            articles = await fetch_from_search_api(query, max_results)
            run.articles_found = len(articles)
            session.commit()
            
            # Step 2: Deduplicate
            new_articles = deduplicate_articles(articles, session)
            run.articles_new = len(new_articles)
            run.articles_skipped = len(articles) - len(new_articles)
            session.commit()
            
            # Step 3: Persist
            if new_articles:
                db_articles = persist_articles(new_articles, session)
                
                # Step 4: Vector indexing
                vector_stats = await index_articles_to_vectors(db_articles, session)
                run.vectors_added = vector_stats["added"]
                run.vectors_skipped = vector_stats["skipped"]
            
            # Step 5: Mark complete
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(run)
            
            return run
            
        except Exception as e:
            # Mark run as failed
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(run)
            
            raise
