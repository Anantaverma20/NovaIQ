"""
SQLModel database models with proper indexing for deduplication.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Column, Text, Index


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


class Article(SQLModel, table=True):
    """
    Ingested article with deterministic deduplication.
    
    Deduplication strategy:
    - Primary: url_hash (unique constraint)
    - Secondary: content_hash for detecting duplicates with different URLs
    """
    __tablename__ = "articles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Original URL and normalized hash for dedup
    url: str = Field(sa_column=Column(Text, nullable=False))
    url_hash: str = Field(index=True, unique=True, max_length=64)
    
    # Content hash for detecting duplicate content
    content_hash: str = Field(index=True, max_length=64)
    
    # Article metadata
    title: str = Field(sa_column=Column(Text, nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    source: str = Field(default="web", max_length=50)
    
    # Timestamps
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    
    # Indexing status
    vector_indexed: bool = Field(default=False)
    vector_indexed_at: Optional[datetime] = None
    
    # Processing status
    summarized: bool = Field(default=False)
    
    __table_args__ = (
        Index("idx_created_at", "created_at"),
        Index("idx_published_at", "published_at"),
        Index("idx_source", "source"),
    )


class InsightDB(SQLModel, table=True):
    """
    Insight extracted from one or more articles.
    
    Insights are generated in batches and may span multiple articles.
    """
    __tablename__ = "insights"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    title: str = Field(sa_column=Column(Text, nullable=False))
    summary: str = Field(sa_column=Column(Text, nullable=False))
    
    # Store as JSON text (simpler than separate table for MVP)
    bullets: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    citations: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    article_ids: str = Field(
        default="[]",
        sa_column=Column(Text, nullable=False),
        description="JSON array of article IDs"
    )
    
    # Confidence score
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    
    __table_args__ = (
        Index("idx_insights_created_at", "created_at"),
        Index("idx_insights_confidence", "confidence"),
    )


class HypothesisDB(SQLModel, table=True):
    """
    Testable hypothesis derived from insight.
    
    Each insight may generate multiple hypotheses.
    """
    __tablename__ = "hypotheses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign key to insight
    insight_id: int = Field(foreign_key="insights.id", index=True)
    
    hypothesis: str = Field(sa_column=Column(Text, nullable=False))
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    
    # Confidence score
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    
    __table_args__ = (
        Index("idx_hypotheses_insight_id", "insight_id"),
        Index("idx_hypotheses_created_at", "created_at"),
    )


class IngestionRun(SQLModel, table=True):
    """
    Track ingestion runs for observability and debugging.
    
    Each run records what was fetched, processed, and any errors.
    """
    __tablename__ = "ingestion_runs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Run metadata
    query: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(max_length=20)  # pending, running, completed, failed
    
    # Counts
    articles_found: int = Field(default=0)
    articles_new: int = Field(default=0)
    articles_skipped: int = Field(default=0)
    
    # Vector indexing
    vectors_added: int = Field(default=0)
    vectors_skipped: int = Field(default=0)
    
    # Error tracking
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Timestamps
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    completed_at: Optional[datetime] = None
    
    __table_args__ = (
        Index("idx_runs_started_at", "started_at"),
        Index("idx_runs_status", "status"),
    )
