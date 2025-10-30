# Setup Guide

Complete setup instructions for RTC Backend.

## Quick Start (3 Steps)

```bash
# 1. Install dependencies
cd backend
pip install -e .

# 2. Initialize database
python -c "from app.db.sqlite import init_db; init_db()"

# 3. Run server
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs for API documentation.

## Configuration

### Minimal Setup (Works Without OpenAI)

Create `backend/.env`:

```env
# Basic configuration - no API keys needed
DATABASE_URL=sqlite:///./data/novaiq.db
ALLOWED_ORIGINS=["http://localhost:3000"]
```

This will run with:
- ✅ Database operations
- ✅ Basic health checks
- ✅ Article listing/viewing
- ⚠️ No vector search (disabled)
- ⚠️ No LLM features (disabled)

### Full Setup (With OpenAI)

Add to your `.env`:

```env
# OpenAI API key enables all features
OPENAI_API_KEY=sk-...

# Optional: Search API for automated ingestion
SEARCH_API_KEY=your-key-here
```

This enables:
- ✅ Everything from minimal setup
- ✅ Vector search and embeddings
- ✅ Insight generation
- ✅ Hypothesis generation
- ✅ Q&A with RAG

## Installation Options

### Option 1: Core Only (Smallest)

```bash
pip install -e .
```

Installs:
- FastAPI, Uvicorn
- SQLModel, Pydantic
- HTTP clients
- Core utilities

**Use when**: You don't need vector operations.

### Option 2: With Vectors

```bash
pip install -e ".[vectors]"
```

Adds:
- ChromaDB (vector store)
- OpenAI Python SDK

**Use when**: You have OPENAI_API_KEY and want full features.

### Option 3: Development

```bash
pip install -e ".[vectors]"
pip install pytest pytest-asyncio ruff mypy
```

Adds testing and linting tools.

**Use when**: You're developing or contributing.

## Database Setup

### SQLite (Default)

```bash
# Initialize
python -c "from app.db.sqlite import init_db; init_db()"

# Check health
curl http://localhost:8000/health
```

Database file location: `./data/novaiq.db`

### PostgreSQL (Production)

```bash
# Install driver
pip install psycopg2-binary

# Set DATABASE_URL
export DATABASE_URL="postgresql://user:pass@localhost:5432/rtc"

# Initialize
python -c "from app.db.sqlite import init_db; init_db()"
```

## Running the Server

### Development Mode

```bash
# Auto-reload on code changes
uvicorn app.main:app --reload --port 8000
```

Or using Makefile:

```bash
make dev
```

### Production Mode

```bash
# Multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or using Makefile:

```bash
make run
```

### Docker

```bash
cd ops
docker-compose up -d
```

## Scheduling Jobs

### Option 1: External Cron (Recommended)

```bash
# Edit crontab
crontab -e

# Add jobs
0 */6 * * * curl -X POST http://localhost:8000/webhook/ingest -H "X-Webhook-Secret: your-secret"
0 2 * * * curl -X POST http://localhost:8000/jobs/generate-insights
```

### Option 2: In-Process Scheduler (Optional)

Install APScheduler:

```bash
pip install apscheduler
```

Update `app/main.py`:

```python
from app.tasks.schedule import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    scheduler = start_scheduler()  # Add this line
    
    yield
    
    # Shutdown
    stop_scheduler(scheduler)  # Add this line
```

Jobs will run in-process automatically.

### Option 3: GitHub Actions

Create `.github/workflows/scheduled-jobs.yml`:

```yaml
name: Scheduled Jobs

on:
  schedule:
    - cron: '0 */6 * * *'

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Ingestion
        run: |
          curl -X POST ${{ secrets.API_URL }}/webhook/ingest \
            -H "X-Webhook-Secret: ${{ secrets.WEBHOOK_SECRET }}"
```

## Testing

### Run All Tests

```bash
pytest
```

Or:

```bash
make test
```

### Run Specific Tests

```bash
pytest tests/test_smoke.py -v
```

### With Coverage

```bash
pytest --cov=app --cov-report=html
```

Or:

```bash
make test-cov
```

View coverage: Open `htmlcov/index.html`

## Development Workflow

### 1. Install Dependencies

```bash
make install-dev
```

### 2. Initialize Database

```bash
make init-db
```

### 3. Run Server

```bash
make dev
```

### 4. Make Changes

Edit files in `app/`

### 5. Test Changes

```bash
make check  # Runs lint, typecheck, and tests
```

### 6. Format Code

```bash
make format
```

## Troubleshooting

### "Vector operations unavailable"

**Problem**: API returns this message

**Solution**:
```bash
# Install vectors extra
pip install -e ".[vectors]"

# Set OpenAI API key
export OPENAI_API_KEY=sk-...
```

### "Search API not configured"

**Problem**: Ingestion fails

**Solution**:
```bash
# Set search API key
export SEARCH_API_KEY=your-key

# Or skip automated ingestion, use manual article submission
```

### "Database locked" errors

**Problem**: SQLite concurrency issues

**Solution**: Use PostgreSQL for production:
```bash
export DATABASE_URL="postgresql://user:pass@host/db"
```

### Import errors

**Problem**: `ModuleNotFoundError: No module named 'app'`

**Solution**: Install in editable mode:
```bash
pip install -e .
```

### Port already in use

**Problem**: `Address already in use`

**Solution**: Change port:
```bash
uvicorn app.main:app --port 8001
```

Or find and kill process:
```bash
lsof -ti:8000 | xargs kill -9
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | None | OpenAI API key for vectors/LLM |
| `SEARCH_API_KEY` | No | None | External search API key |
| `DATABASE_URL` | No | `sqlite:///./data/novaiq.db` | Database connection string |
| `CHROMA_PERSIST_DIR` | No | `./data/chroma` | Vector store directory |
| `ENABLE_VECTORS` | No | `true` | Enable vector operations |
| `ALLOWED_ORIGINS` | No | `["http://localhost:3000"]` | CORS allowed origins |
| `INGESTION_QUERY` | No | `AI research breakthrough` | Default search query |
| `INGESTION_MAX_RESULTS` | No | `20` | Max articles per run |
| `INGESTION_WEBHOOK_SECRET` | No | None | Webhook authentication |

## Next Steps

1. **Configure API Keys**: Add `OPENAI_API_KEY` to `.env`
2. **Schedule Jobs**: Set up cron for periodic ingestion
3. **Deploy**: See main README for deployment options
4. **Monitor**: Check `/health` endpoint regularly

## Support

- **Documentation**: See main README.md
- **API Docs**: http://localhost:8000/docs (when running)
- **Issues**: Check application logs for errors

