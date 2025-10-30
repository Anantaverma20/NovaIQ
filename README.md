# RTC Backend (Research Tech Collector)

AI-powered research ingestion and insight generation platform with graceful degradation and minimal dependencies.

## Features

- **Automated Ingestion**: Periodic search and article collection with deduplication
- **Smart Summarization**: Extract key insights with bullet points and citations
- **Hypothesis Generation**: AI-powered generation of testable hypotheses
- **Semantic Search**: Optional RAG-powered Q&A with vector embeddings
- **Graceful Degradation**: Works without OpenAI API key (vectors disabled)
- **Simple Architecture**: No Celery/Redis required - use webhooks + cron

## Architecture

### Core Stack
- **Backend**: FastAPI + SQLModel (SQLite)
- **Vectors** (optional): ChromaDB + OpenAI embeddings
- **Scheduling**: Webhook + external cron (no Celery)
- **Deployment**: Docker-ready, runs anywhere

### Key Design Principles

1. **Minimal Technical Debt**: Small dependency surface, clear layering
2. **Idempotent Ingestion**: Same content never duplicated (hash-based dedup)
3. **Graceful Degradation**: Missing OPENAI_API_KEY? App still works without vectors
4. **Explicit I/O Boundaries**: Clear separation of fetch/process/persist
5. **Single Source of Truth**: Typed config in `app/config.py`

## Quick Start

### Prerequisites

- Python 3.11+
- (Optional) OpenAI API key for vectors and LLM features

### Installation

```bash
cd backend

# Install core dependencies
pip install -e .

# Optional: Install vector support
pip install -e ".[vectors]"

# Initialize database
python -c "from app.db.sqlite import init_db; init_db()"
```

### Configuration

Create `.env` file in `backend/` directory:

```bash
# === Required for full functionality ===
OPENAI_API_KEY=sk-...                    # OpenAI API key (optional but recommended)
SEARCH_API_KEY=...                        # Search API key (You.com, Brave, etc.)

# === Optional Configuration ===
DATABASE_URL=sqlite:///./data/novaiq.db   # Database path
CHROMA_PERSIST_DIR=./data/chroma          # Vector store path

# Ingestion settings
INGESTION_QUERY=AI research breakthrough
INGESTION_MAX_RESULTS=20

# Webhook security (for cron triggers)
INGESTION_WEBHOOK_SECRET=your-secret-here

# CORS (for frontend)
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### Running the Server

```bash
cd backend

# Development mode
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Testing Without OpenAI

The application works perfectly without OpenAI API key:

```bash
# No .env file or empty OPENAI_API_KEY
uvicorn app.main:app --reload

# Features available:
# ✓ Article ingestion (if search API configured)
# ✓ Manual article submission
# ✓ Database operations
# ✗ Vector search (disabled)
# ✗ Insight generation (disabled)
# ✗ Hypothesis generation (disabled)
```

Check health status to see what's enabled:

```bash
curl http://localhost:8000/health
```

## API Endpoints

### Health & Status

- `GET /health` - System health with component status

### Articles

- `GET /articles` - List articles (paginated)
- `GET /articles/{id}` - Get specific article

### Insights

- `GET /insights` - List insights (paginated)
- `GET /insights/{id}` - Get specific insight

### Hypotheses

- `GET /hypotheses` - List hypotheses (paginated, optional insight filter)
- `GET /hypotheses/{id}` - Get specific hypothesis

### Q&A (RAG)

- `POST /ask` - Ask questions over ingested content
  - Uses vectors if available
  - Falls back to keyword search if vectors disabled

### Ingestion

- `POST /ingest/run` - Trigger manual ingestion (synchronous)
- `POST /webhook/ingest` - Webhook for scheduled ingestion

### Jobs (Background Tasks)

- `POST /jobs/refresh-vectors` - Reindex un-indexed articles
- `POST /jobs/generate-insights` - Generate insights from recent articles
- `POST /jobs/generate-hypotheses` - Generate hypotheses from insights

## Scheduling with Cron

Instead of Celery, use external cron + webhooks:

### Linux/Mac Crontab

```bash
# Edit crontab
crontab -e

# Add ingestion job (every 6 hours)
0 */6 * * * curl -X POST http://localhost:8000/webhook/ingest \
  -H "X-Webhook-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{"max_results": 20}'

# Generate insights daily at 2am
0 2 * * * curl -X POST http://localhost:8000/jobs/generate-insights
```

### GitHub Actions (Cloud Cron)

```yaml
# .github/workflows/scheduled-ingestion.yml
name: Scheduled Ingestion

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Ingestion
        run: |
          curl -X POST ${{ secrets.API_URL }}/webhook/ingest \
            -H "X-Webhook-Secret: ${{ secrets.WEBHOOK_SECRET }}" \
            -H "Content-Type: application/json" \
            -d '{"max_results": 20}'
```

### Cloud Providers

**Render Cron Jobs**: Native cron job support
**Railway**: Use cron-job.org + webhook
**Heroku**: Use Heroku Scheduler add-on

## Development

### Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app with routes
│   ├── config.py            # Single source of truth for settings
│   ├── deps.py              # Dependency injection
│   ├── schemas.py           # Pydantic request/response models
│   ├── db/
│   │   ├── models.py        # SQLModel database models
│   │   └── sqlite.py        # DB initialization
│   ├── services/
│   │   ├── ingest.py        # Idempotent ingestion pipeline
│   │   └── vectorstore.py   # Optional ChromaDB wrapper
│   └── tasks/
│       └── jobs.py          # Background job definitions
├── tests/
│   └── test_smoke.py        # Basic tests
├── pyproject.toml           # Dependencies
└── .env                     # Configuration (not in git)
```

### Running Tests

```bash
cd backend

# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Run specific test
pytest tests/test_smoke.py -v
```

### Code Quality

```bash
# Format with ruff
pip install ruff
ruff check app/ --fix
ruff format app/

# Type checking
pip install mypy
mypy app/
```

## Docker Deployment

```bash
cd ops

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

### Environment Variables in Docker

Edit `ops/docker-compose.yml`:

```yaml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - SEARCH_API_KEY=${SEARCH_API_KEY}
  - DATABASE_URL=sqlite:///./data/novaiq.db
```

## Production Checklist

- [ ] Set `OPENAI_API_KEY` for full functionality
- [ ] Set `SEARCH_API_KEY` for automated ingestion
- [ ] Set `INGESTION_WEBHOOK_SECRET` for secure webhooks
- [ ] Configure `ALLOWED_ORIGINS` for frontend CORS
- [ ] Use PostgreSQL instead of SQLite (optional):
  ```bash
  DATABASE_URL=postgresql://user:pass@host:5432/dbname
  ```
- [ ] Set up cron for scheduled ingestion
- [ ] Configure monitoring/logging
- [ ] Enable HTTPS in production

## Common Patterns

### Idempotent Ingestion

Running ingestion multiple times with same query won't create duplicates:

```bash
# Run multiple times - only new articles added
curl -X POST http://localhost:8000/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"query": "AI research", "max_results": 20}'
```

### Graceful Vector Degradation

```python
# vectorstore.py checks if enabled
if not is_enabled():
    return {"status": "disabled", "added": 0}

# main.py falls back to keyword search
if vectors_enabled():
    docs = await query_documents(question)
else:
    # Keyword-based fallback
    ...
```

### Explicit I/O Boundaries

```python
# Ingestion pipeline (services/ingest.py)
# 1. Fetch (I/O boundary)
articles = await fetch_from_search_api(query)

# 2. Process (pure logic)
new_articles = deduplicate_articles(articles, session)

# 3. Persist (I/O boundary)
db_articles = persist_articles(new_articles, session)
```

## Troubleshooting

### "Vector operations unavailable"

**Cause**: `OPENAI_API_KEY` not set or `chromadb` not installed

**Solution**:
```bash
# Set API key
export OPENAI_API_KEY=sk-...

# Install vector dependencies
pip install -e ".[vectors]"
```

### "Search API not configured"

**Cause**: `SEARCH_API_KEY` not set

**Solution**:
```bash
export SEARCH_API_KEY=your-key
```

**Workaround**: Use manual article submission via API

### Database locked errors

**Cause**: SQLite concurrency limits

**Solution**: Use PostgreSQL in production:
```bash
pip install psycopg2-binary
export DATABASE_URL=postgresql://user:pass@host/db
```

## Migration from Celery

Old architecture (with Celery):
```
FastAPI → Celery → Redis → Worker
```

New architecture (webhook + cron):
```
Cron → Webhook → FastAPI (inline job)
```

**Benefits**:
- Fewer dependencies (no Redis, no Celery)
- Simpler deployment
- Lower cost
- Easier debugging

**Trade-offs**:
- No distributed task queue
- Jobs run synchronously (fine for MVP)
- For high-volume, consider adding task queue later

## Future Enhancements

- [ ] Add APScheduler for in-process cron (optional)
- [ ] Implement Alembic for database migrations
- [ ] Add PostgreSQL support for production
- [ ] Add authentication/authorization
- [ ] Implement rate limiting per user
- [ ] Add observability (OpenTelemetry)
- [ ] Support more vector stores (Pinecone, Weaviate)
- [ ] Add streaming responses for Q&A

## License

MIT

## Contributing

Pull requests welcome! Please ensure:
- Code follows ruff formatting
- Tests pass
- New features have graceful degradation
- Dependencies are optional when possible
