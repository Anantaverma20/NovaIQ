"""
Optional in-process scheduling with APScheduler.

This is an alternative to external cron + webhooks.
Only use if you want in-process scheduling.

For production, external cron + webhooks is recommended for:
- Simpler deployment
- Better observability
- No long-running process required
"""
from typing import Optional
import asyncio

# APScheduler is optional - only import if needed
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None
    CronTrigger = None

from app.config import get_settings
from app.tasks.jobs import (
    job_run_ingestion,
    job_refresh_vectors,
    job_generate_insights,
    job_generate_hypotheses,
)


_scheduler: Optional[AsyncIOScheduler] = None


def create_scheduler() -> Optional[AsyncIOScheduler]:
    """
    Create and configure APScheduler instance.
    
    Returns:
        Scheduler instance or None if APScheduler not available
    """
    if not APSCHEDULER_AVAILABLE:
        print("⚠️  APScheduler not installed. Use external cron instead.")
        return None
    
    scheduler = AsyncIOScheduler()
    settings = get_settings()
    
    # Schedule ingestion (every 6 hours by default)
    scheduler.add_job(
        job_run_ingestion,
        CronTrigger.from_crontab("0 */6 * * *"),
        id="ingestion",
        name="Periodic article ingestion",
        replace_existing=True,
    )
    
    # Schedule insight generation (daily at 2am)
    scheduler.add_job(
        job_generate_insights,
        CronTrigger.from_crontab("0 2 * * *"),
        id="insights",
        name="Daily insight generation",
        replace_existing=True,
    )
    
    # Schedule hypothesis generation (daily at 3am)
    scheduler.add_job(
        job_generate_hypotheses,
        CronTrigger.from_crontab("0 3 * * *"),
        id="hypotheses",
        name="Daily hypothesis generation",
        replace_existing=True,
    )
    
    # Schedule vector refresh (weekly on Sunday at 4am)
    if settings.vectors_enabled:
        scheduler.add_job(
            job_refresh_vectors,
            CronTrigger.from_crontab("0 4 * * 0"),
            id="vector_refresh",
            name="Weekly vector refresh",
            replace_existing=True,
        )
    
    return scheduler


def start_scheduler() -> Optional[AsyncIOScheduler]:
    """
    Start the background scheduler.
    
    Usage in main.py lifespan:
        from app.tasks.schedule import start_scheduler, stop_scheduler
        
        @asynccontextmanager
        async def lifespan(app):
            scheduler = start_scheduler()
            yield
            stop_scheduler(scheduler)
    
    Returns:
        Running scheduler instance
    """
    global _scheduler
    
    if _scheduler is not None:
        print("⚠️  Scheduler already running")
        return _scheduler
    
    _scheduler = create_scheduler()
    
    if _scheduler:
        _scheduler.start()
        print("✓ Background scheduler started")
        
        # Print scheduled jobs
        for job in _scheduler.get_jobs():
            print(f"  - {job.name}: {job.trigger}")
    
    return _scheduler


def stop_scheduler(scheduler: Optional[AsyncIOScheduler] = None):
    """
    Stop the background scheduler.
    
    Args:
        scheduler: Scheduler to stop (uses global if None)
    """
    global _scheduler
    
    target = scheduler or _scheduler
    
    if target:
        target.shutdown(wait=False)
        print("✓ Background scheduler stopped")
        _scheduler = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the current scheduler instance."""
    return _scheduler


# Example usage in main.py:
"""
from app.tasks.schedule import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    scheduler = start_scheduler()  # Optional: only if you want in-process scheduling
    
    yield
    
    # Shutdown
    stop_scheduler(scheduler)

app = FastAPI(lifespan=lifespan)
"""
