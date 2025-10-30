"""
Slim Pydantic schemas for API request/response models.

Design principles:
- Separate input/output schemas for clear boundaries
- Minimal fields for lean APIs
- Proper validation with descriptive error messages
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


# === Article Schemas ===

class ArticleIn(BaseModel):
    """Input schema for manual article ingestion."""
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    source: str = Field(default="web", max_length=50)
    published_at: Optional[datetime] = None


class ArticleOut(BaseModel):
    """Output schema for article data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    url: str
    title: str
    content: str
    source: str
    published_at: Optional[datetime]
    created_at: datetime
    vector_indexed: bool


class ArticleListOut(BaseModel):
    """Paginated list of articles."""
    items: list[ArticleOut]
    total: int
    limit: int
    offset: int


# === Insight Schemas ===

class InsightOut(BaseModel):
    """Output schema for insights."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float
    created_at: datetime


class InsightListOut(BaseModel):
    """Paginated list of insights."""
    items: list[InsightOut]
    total: int
    limit: int
    offset: int


# === Hypothesis Schemas ===

class HypothesisOut(BaseModel):
    """Output schema for hypotheses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    insight_id: int
    hypothesis: str
    rationale: str
    confidence: float
    created_at: datetime


class HypothesisListOut(BaseModel):
    """Paginated list of hypotheses."""
    items: list[HypothesisOut]
    total: int
    limit: int
    offset: int


# === RAG / Q&A Schemas ===

class AskRequest(BaseModel):
    """Request to ask a question using RAG."""
    question: str = Field(min_length=1, max_length=1000)
    context_limit: int = Field(default=5, ge=1, le=20)
    
    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Ensure question is not just whitespace."""
        if not v.strip():
            raise ValueError("Question cannot be empty or whitespace only")
        return v.strip()


class SourceOut(BaseModel):
    """Source citation for RAG response."""
    article_id: int
    title: str
    url: str
    relevance: float = Field(ge=0.0, le=1.0)


class AskResponse(BaseModel):
    """Response to a question with sources."""
    answer: str
    sources: list[SourceOut] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    vectors_used: bool = Field(
        default=False,
        description="Whether vector search was used"
    )


# === Ingestion Schemas ===

class IngestionTriggerRequest(BaseModel):
    """Request to trigger manual ingestion."""
    query: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Search query (uses default if not provided)"
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum articles to fetch"
    )


class IngestionStatusOut(BaseModel):
    """Status of an ingestion run."""
    run_id: int
    status: str  # pending, running, completed, failed
    query: str
    articles_found: int
    articles_new: int
    articles_skipped: int
    vectors_added: int
    vectors_skipped: int
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str] = None


class IngestionTriggerResponse(BaseModel):
    """Response when triggering ingestion."""
    run_id: int
    status: str
    message: str


# === Health Check Schemas ===

class HealthStatus(BaseModel):
    """System health status."""
    status: str  # ok, degraded, unhealthy
    service: str
    timestamp: datetime
    
    # Component statuses
    database: dict[str, Any]
    vectors: dict[str, Any]
    search_api: dict[str, Any]


# === Error Schemas ===

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# === Pagination Helpers ===

class PaginationParams(BaseModel):
    """Reusable pagination parameters."""
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    
    @property
    def skip(self) -> int:
        """Alias for offset (SQLModel uses 'skip')."""
        return self.offset
