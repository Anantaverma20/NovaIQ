"""
Dependency injection for FastAPI routes.
Provides database sessions, HTTP clients, and service dependencies.
"""
from typing import Annotated, Optional, Any
from contextlib import contextmanager
import httpx
from fastapi import Depends, HTTPException, Header
from sqlmodel import Session, create_engine
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings


# === Database Dependencies ===

_engine: Optional[Any] = None


def get_engine():
    """Get or create the SQLModel engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
            echo=False,
        )
    return _engine


def get_db_session() -> Session:
    """
    Database session dependency for FastAPI routes.
    
    Usage:
        @app.get("/items")
        def list_items(db: Session = Depends(get_db_session)):
            return db.query(Item).all()
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session


@contextmanager
def get_session_context():
    """
    Context manager for database sessions in service layer.
    
    Usage:
        with get_session_context() as session:
            session.add(item)
            session.commit()
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session


# === HTTP Client Dependencies ===

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def _http_get_with_retry(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """HTTP GET with automatic retry logic."""
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response


async def get_http_client() -> httpx.AsyncClient:
    """
    Async HTTP client with reasonable defaults.
    
    Usage:
        @app.get("/proxy")
        async def proxy(client: httpx.AsyncClient = Depends(get_http_client)):
            response = await client.get("https://api.example.com")
            return response.json()
    """
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        follow_redirects=True,
    ) as client:
        yield client


# === OpenAI Client (Optional) ===

_openai_client: Optional[Any] = None


def get_openai_client() -> Optional[Any]:
    """
    Get OpenAI client if API key is configured.
    
    Returns None if OPENAI_API_KEY is not set (graceful degradation).
    
    Usage:
        client = get_openai_client()
        if client:
            response = await client.embeddings.create(...)
        else:
            # Skip vector operations
            pass
    """
    global _openai_client
    
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None
    
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError:
            # openai not installed (vectors extra not included)
            return None
    
    return _openai_client


async def require_openai_client() -> Any:
    """
    Require OpenAI client or raise 503 Service Unavailable.
    
    Use this dependency when vectors are required for the endpoint.
    
    Usage:
        @app.post("/embed")
        async def embed(client = Depends(require_openai_client)):
            # Will fail if OpenAI not configured
            ...
    """
    client = get_openai_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Vector operations unavailable: OPENAI_API_KEY not configured"
        )
    return client


# === ChromaDB Client (Optional) ===

_chroma_collection: Optional[Any] = None


def get_chroma_collection() -> Optional[Any]:
    """
    Get ChromaDB collection if enabled and available.
    
    Returns None if:
    - OPENAI_API_KEY not set
    - chromadb not installed
    - ENABLE_VECTORS is False
    
    Usage:
        collection = get_chroma_collection()
        if collection:
            results = collection.query(...)
    """
    global _chroma_collection
    
    settings = get_settings()
    if not settings.vectors_enabled:
        return None
    
    if _chroma_collection is None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            client = chromadb.Client(ChromaSettings(
                persist_directory=settings.CHROMA_PERSIST_DIR,
                anonymized_telemetry=False,
            ))
            
            _chroma_collection = client.get_or_create_collection(
                name="rtc_documents",
                metadata={"description": "Research documents and articles"}
            )
        except ImportError:
            # chromadb not installed
            return None
        except Exception as e:
            # Other initialization errors
            print(f"Warning: Failed to initialize ChromaDB: {e}")
            return None
    
    return _chroma_collection


# === Search API Client ===

async def get_search_client() -> Optional[httpx.AsyncClient]:
    """
    Get HTTP client configured for external search API.
    
    Returns None if SEARCH_API_KEY not configured.
    
    Usage:
        client = await get_search_client()
        if client:
            response = await client.get("/search", params={"q": query})
    """
    settings = get_settings()
    if not settings.search_api_available:
        return None
    
    return httpx.AsyncClient(
        base_url=settings.SEARCH_API_BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.SEARCH_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# === Webhook Authentication ===

def verify_webhook_secret(
    x_webhook_secret: Annotated[Optional[str], Header()] = None
) -> bool:
    """
    Verify webhook secret token.
    
    Usage:
        @app.post("/webhook/ingest")
        def webhook_ingest(verified: bool = Depends(verify_webhook_secret)):
            if not verified:
                raise HTTPException(401, "Invalid webhook secret")
    """
    settings = get_settings()
    
    # If no secret configured, allow all requests (dev mode)
    if not settings.INGESTION_WEBHOOK_SECRET:
        return True
    
    # Otherwise, require matching secret
    return x_webhook_secret == settings.INGESTION_WEBHOOK_SECRET


# === Type Aliases ===

DBSession = Annotated[Session, Depends(get_db_session)]
HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
