"""
Smoke tests for basic application functionality.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings, reload_settings
from app.db.sqlite import init_db


@pytest.fixture(scope="session")
def test_app():
    """Create test app with initialized database."""
    # Initialize test database
    init_db()
    yield app


@pytest.fixture
def client(test_app):
    """Test client fixture."""
    return TestClient(test_app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert data["service"] == "rtc-backend"


def test_list_articles_empty(client):
    """Test listing articles (should be empty initially)."""
    response = client.get("/articles")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_list_insights_empty(client):
    """Test listing insights (should be empty initially)."""
    response = client.get("/insights")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_list_hypotheses_empty(client):
    """Test listing hypotheses (should be empty initially)."""
    response = client.get("/hypotheses")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_ask_question_no_content(client):
    """Test asking a question with no content in database."""
    response = client.post(
        "/ask",
        json={"question": "What is AI?"}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data


def test_ask_question_validation(client):
    """Test ask endpoint validation."""
    # Empty question
    response = client.post(
        "/ask",
        json={"question": ""}
    )
    assert response.status_code == 422  # Validation error
    
    # Whitespace only
    response = client.post(
        "/ask",
        json={"question": "   "}
    )
    assert response.status_code == 422


def test_pagination_defaults(client):
    """Test pagination defaults."""
    response = client.get("/articles")
    assert response.status_code == 200
    
    data = response.json()
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_pagination_custom(client):
    """Test custom pagination parameters."""
    response = client.get("/articles?limit=10&offset=5")
    assert response.status_code == 200
    
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 5


def test_get_nonexistent_article(client):
    """Test getting a non-existent article."""
    response = client.get("/articles/99999")
    assert response.status_code == 404


def test_get_nonexistent_insight(client):
    """Test getting a non-existent insight."""
    response = client.get("/insights/99999")
    assert response.status_code == 404


def test_get_nonexistent_hypothesis(client):
    """Test getting a non-existent hypothesis."""
    response = client.get("/hypotheses/99999")
    assert response.status_code == 404


def test_config_loads():
    """Test that configuration loads correctly."""
    settings = get_settings()
    
    assert settings is not None
    assert hasattr(settings, "DATABASE_URL")
    assert hasattr(settings, "OPENAI_API_KEY")
    assert hasattr(settings, "vectors_enabled")


def test_config_vectors_disabled_without_key():
    """Test that vectors are disabled without OpenAI key."""
    import os
    
    # Temporarily remove OpenAI key
    old_key = os.environ.get("OPENAI_API_KEY")
    if old_key:
        del os.environ["OPENAI_API_KEY"]
    
    # Reload settings
    settings = reload_settings()
    
    # Vectors should be disabled
    assert not settings.vectors_enabled
    
    # Restore key
    if old_key:
        os.environ["OPENAI_API_KEY"] = old_key
    reload_settings()


def test_health_check_structure(client):
    """Test health check response structure."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check required fields
    assert "status" in data
    assert "service" in data
    assert "timestamp" in data
    assert "database" in data
    assert "vectors" in data
    assert "search_api" in data
    
    # Check nested structures
    assert "enabled" in data["vectors"]
    assert "configured" in data["vectors"]
    assert "configured" in data["search_api"]


@pytest.mark.asyncio
async def test_vectorstore_graceful_degradation():
    """Test that vectorstore operations handle missing dependencies."""
    from app.services import vectorstore
    
    # These should not raise errors even if OpenAI not configured
    result = await vectorstore.add_documents(["test content"])
    assert "status" in result
    
    docs = await vectorstore.query_documents("test query")
    assert isinstance(docs, list)
    
    count = await vectorstore.count_documents()
    assert isinstance(count, int)
