# Changelog

All notable changes to the RTC Backend refactor.

## [0.1.0] - 2025-10-28

### Major Refactor - Graceful Degradation & Minimal Dependencies

#### Architecture Changes

- **Removed Celery dependency**: Replaced with webhook + external cron pattern
- **Optional vector support**: App works without OpenAI API key
- **Typed configuration**: Single source of truth in `app/config.py`
- **Idempotent ingestion**: Hash-based deduplication prevents duplicates
- **Explicit I/O boundaries**: Clear separation of fetch/process/persist

#### Dependencies

- **Updated** `pyproject.toml` to Python 3.11+
- **Made optional**: `chromadb` and `openai` in `[vectors]` extras
- **Added**: `python-slugify`, `python-dateutil`, `tenacity`, `orjson`
- **Removed**: Celery, Redis dependencies (optional now)

#### New Files

- `app/config.py` - Typed settings with validation
- `app/services/summarize.py` - LLM-powered summarization
- `app/services/hypothesize.py` - Hypothesis generation
- `backend/Makefile` - Development workflow commands
- `backend/SETUP.md` - Comprehensive setup guide
- `backend/ENV_EXAMPLE.txt` - Environment configuration template

#### Updated Files

##### `app/main.py`
- ✨ Comprehensive health check with component status
- ✨ Proper pagination for all list endpoints
- ✨ Global exception handler
- ✨ Lifespan context manager for startup/shutdown
- ✨ Graceful degradation in `/ask` endpoint
- ✨ New job trigger endpoints
- 🔧 Better error responses
- 🔧 CORS middleware configuration

##### `app/deps.py`
- ✨ Database session context manager
- ✨ Optional OpenAI client with graceful degradation
- ✨ Optional ChromaDB collection getter
- ✨ Webhook authentication
- ✨ HTTP client with retry logic
- ✨ Type aliases for FastAPI dependencies

##### `app/schemas.py`
- ✨ Separate input/output schemas
- ✨ Pagination helper class
- ✨ Health status schema
- ✨ Ingestion status schemas
- ✨ Better field validation
- 🔧 Slim, focused schemas

##### `app/db/models.py`
- ✨ `url_hash` and `content_hash` for deterministic dedup
- ✨ `IngestionRun` model for observability
- ✨ Proper indexes on common query patterns
- ✨ `vector_indexed` flag and timestamp
- ✨ `summarized` flag for processing tracking
- 🔧 UTC timezone handling
- 🔧 Better field types and constraints

##### `app/db/sqlite.py`
- ✨ Automatic directory creation
- ✨ Health check function
- ✨ Migration placeholders
- 🔧 Better connection configuration

##### `app/services/ingest.py`
- ✨ `NormalizedArticle` class for type safety
- ✨ Deterministic hashing functions
- ✨ Idempotent ingestion pipeline
- ✨ Explicit I/O boundary functions
- ✨ Comprehensive error handling
- ✨ Vector indexing integration
- 🔧 Clear step-by-step pipeline

##### `app/services/vectorstore.py`
- ✨ `is_enabled()` function for feature detection
- ✨ Deterministic document ID generation
- ✨ Batch processing support
- ✨ Idempotent document addition
- ✨ Full CRUD operations (add, query, get, delete, count)
- 🔧 Returns status dicts instead of raising errors
- 🔧 Graceful degradation throughout

##### `app/tasks/jobs.py`
- ✨ All jobs return result dicts (no Celery)
- ✨ `job_run_ingestion` - Full ingestion pipeline
- ✨ `job_refresh_vectors` - Backfill vector indexing
- ✨ `job_generate_insights` - LLM-powered insights
- ✨ `job_generate_hypotheses` - Hypothesis generation
- ✨ `job_cleanup_old_runs` - Maintenance job
- 🔧 Async/await throughout
- 🔧 Graceful handling of missing dependencies

##### `app/tasks/schedule.py`
- ✨ Optional APScheduler integration
- ✨ Cron-like scheduling configuration
- 🔧 Clear instructions for external cron alternative

##### `backend/tests/test_smoke.py`
- ✨ Health check tests
- ✨ Pagination tests
- ✨ Validation tests
- ✨ Graceful degradation tests
- ✨ Config loading tests

##### `README.md`
- ✨ Complete rewrite for new architecture
- ✨ Graceful degradation patterns
- ✨ Cron scheduling examples
- ✨ Production deployment checklist
- ✨ Troubleshooting guide
- ✨ Migration guide from Celery

#### Breaking Changes

⚠️ **Configuration Changes**
- Redis settings removed (no longer needed)
- `LLM_PROVIDER` and `LLM_API_KEY` consolidated to `OPENAI_API_KEY`
- `YOU_API_KEY` renamed to `SEARCH_API_KEY`
- `YOU_BASE_URL` renamed to `SEARCH_API_BASE_URL`

⚠️ **Database Schema Changes**
- `Article` table: Added `url_hash`, `content_hash`, `vector_indexed`, `vector_indexed_at`, `summarized`
- New table: `IngestionRun` for tracking ingestion jobs
- Field type changes: `created_at` now uses UTC timestamps

⚠️ **API Changes**
- Health check response structure changed
- Pagination uses `offset` instead of `page`
- Error responses now follow standard format
- Job endpoints moved from Celery tasks to HTTP endpoints

⚠️ **Import Changes**
- `from app.deps import get_settings` (was: `Settings` class direct import)
- `from app.config import Settings` for type hints
- Service functions now in `app.services.*` modules

#### Migration Guide

##### 1. Update Environment Variables

Old `.env`:
```env
LLM_API_KEY=sk-...
YOU_API_KEY=...
REDIS_URL=redis://localhost:6379
```

New `.env`:
```env
OPENAI_API_KEY=sk-...
SEARCH_API_KEY=...
# REDIS_URL removed (not needed)
```

##### 2. Database Migration

```bash
# Backup existing database
cp novaiq.db novaiq.db.backup

# Option A: Reset database (loses data)
python -c "from app.db.sqlite import init_db; init_db(drop_all=True)"

# Option B: Manually migrate (keeps data)
# Add new columns to existing tables
# See app/db/sqlite.py for migration examples
```

##### 3. Update Dependencies

```bash
# Uninstall old deps
pip uninstall celery redis

# Install new deps
pip install -e ".[vectors]"
```

##### 4. Replace Celery Tasks

Old (Celery):
```python
from app.tasks import run_ingestion_task
result = run_ingestion_task.delay()
```

New (HTTP):
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8000/webhook/ingest")
```

Or use cron:
```bash
0 */6 * * * curl -X POST http://localhost:8000/webhook/ingest
```

##### 5. Update Imports

Old:
```python
from app.deps import Settings, get_settings
settings = Settings()
```

New:
```python
from app.config import get_settings
settings = get_settings()
```

#### What's Better Now

1. **Simpler Deployment**: No Redis, no Celery workers
2. **Graceful Degradation**: Works without API keys
3. **Better Observability**: Health checks show what's enabled
4. **Idempotent Operations**: Safe to run multiple times
5. **Type Safety**: Full typing with Pydantic v2
6. **Clear Architecture**: Explicit I/O boundaries
7. **Lower Costs**: Smaller dependency footprint
8. **Easier Testing**: No external services required
9. **Better Docs**: Comprehensive setup and troubleshooting guides

#### Known Issues / Limitations

- SQLite concurrency limits (use PostgreSQL for production)
- Synchronous job execution (add queue layer if needed)
- No built-in retry for failed jobs (use cron for now)
- No distributed tracing (add OpenTelemetry if needed)

#### Future Enhancements

- [ ] APScheduler integration for in-process cron
- [ ] Alembic for database migrations
- [ ] Rate limiting per user
- [ ] Authentication/authorization
- [ ] WebSocket support for live updates
- [ ] Streaming responses for Q&A
- [ ] More vector store options (Pinecone, Weaviate)
- [ ] Observability (OpenTelemetry, Prometheus)

---

## Previous Versions

### [0.0.x] - Pre-Refactor

Original architecture with Celery, Redis, and tight coupling to external services.

