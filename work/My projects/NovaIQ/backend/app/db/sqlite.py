"""
Database initialization and migration utilities.
"""
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

from app.config import get_settings
from app.db.models import Article, InsightDB, HypothesisDB, IngestionRun


def get_engine():
    """Get SQLModel engine with proper configuration."""
    settings = get_settings()
    
    # Ensure data directory exists
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create engine with SQLite optimizations
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            # SQLite optimizations
            "timeout": 30.0,
        },
        echo=False,
        pool_pre_ping=True,
    )
    
    return engine


def init_db(drop_all: bool = False) -> None:
    """
    Initialize database schema.
    
    Args:
        drop_all: If True, drop all tables before creating (DESTRUCTIVE!)
    
    Usage:
        # First time setup
        from app.db.sqlite import init_db
        init_db()
        
        # Reset database (lose all data!)
        init_db(drop_all=True)
    """
    engine = get_engine()
    
    if drop_all:
        print("⚠️  Dropping all tables...")
        SQLModel.metadata.drop_all(engine)
    
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("✓ Database initialized")


def get_session() -> Session:
    """
    Get a database session (for use outside of FastAPI context).
    
    Remember to close the session when done:
        session = get_session()
        try:
            # do work
            session.commit()
        finally:
            session.close()
    
    Or use as context manager:
        with Session(get_engine()) as session:
            # do work
            session.commit()
    """
    engine = get_engine()
    return Session(engine)


def check_db_health() -> dict[str, any]:
    """
    Check database connectivity and get basic stats.
    
    Returns:
        Dict with status and table counts
    """
    try:
        engine = get_engine()
        with Session(engine) as session:
            # Test connectivity with simple query
            article_count = session.query(Article).count()
            insight_count = session.query(InsightDB).count()
            hypothesis_count = session.query(HypothesisDB).count()
            run_count = session.query(IngestionRun).count()
            
            return {
                "status": "healthy",
                "counts": {
                    "articles": article_count,
                    "insights": insight_count,
                    "hypotheses": hypothesis_count,
                    "ingestion_runs": run_count,
                }
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Migrations (simple approach for MVP)
# For production, consider Alembic

def migrate_v1_to_v2():
    """
    Example migration function.
    
    In production, use Alembic or similar for proper migrations.
    For MVP, we can add columns with ALTER TABLE if needed.
    """
    # Example:
    # engine = get_engine()
    # with engine.connect() as conn:
    #     conn.execute("ALTER TABLE articles ADD COLUMN new_field TEXT")
    pass
