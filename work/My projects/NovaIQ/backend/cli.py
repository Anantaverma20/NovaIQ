#!/usr/bin/env python3
"""
RTC Backend CLI - Command-line interface for common operations.

Usage:
    python cli.py init-db              # Initialize database
    python cli.py reset-db             # Reset database (DESTRUCTIVE!)
    python cli.py health               # Check system health
    python cli.py ingest               # Run ingestion
    python cli.py generate-insights    # Generate insights
    python cli.py stats                # Show database stats
"""
import sys
import asyncio
from datetime import datetime

# Add app to path
sys.path.insert(0, ".")

from app.config import get_settings
from app.db.sqlite import init_db, check_db_health
from app.tasks.jobs import (
    job_run_ingestion,
    job_generate_insights,
    job_generate_hypotheses,
    job_refresh_vectors,
)


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_status(key: str, value: any, indent: int = 0):
    """Print formatted status line."""
    spaces = "  " * indent
    print(f"{spaces}{key:30s}: {value}")


async def cmd_init_db(reset: bool = False):
    """Initialize or reset database."""
    print_header("Database Initialization")
    
    if reset:
        print("⚠️  WARNING: This will delete all data!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return
    
    init_db(drop_all=reset)
    print("✓ Database initialized successfully")


async def cmd_health():
    """Check system health."""
    print_header("System Health Check")
    
    settings = get_settings()
    
    # Configuration status
    print("Configuration:")
    print_status("OpenAI API Key", "✓ Set" if settings.OPENAI_API_KEY else "✗ Not set", 1)
    print_status("Search API Key", "✓ Set" if settings.SEARCH_API_KEY else "✗ Not set", 1)
    print_status("Vectors Enabled", "✓ Yes" if settings.vectors_enabled else "✗ No", 1)
    
    # Database health
    print("\nDatabase:")
    db_health = check_db_health()
    
    if db_health.get("status") == "healthy":
        print_status("Status", "✓ Healthy", 1)
        counts = db_health.get("counts", {})
        print_status("Articles", counts.get("articles", 0), 1)
        print_status("Insights", counts.get("insights", 0), 1)
        print_status("Hypotheses", counts.get("hypotheses", 0), 1)
        print_status("Ingestion Runs", counts.get("ingestion_runs", 0), 1)
    else:
        print_status("Status", f"✗ Unhealthy: {db_health.get('error')}", 1)
    
    # Vector store
    print("\nVector Store:")
    if settings.vectors_enabled:
        from app.services.vectorstore import count_documents
        count = await count_documents()
        print_status("Status", "✓ Enabled", 1)
        print_status("Documents", count, 1)
    else:
        print_status("Status", "✗ Disabled (no OpenAI key)", 1)
    
    print()


async def cmd_ingest(query: str = None, max_results: int = 20):
    """Run ingestion."""
    print_header("Running Ingestion")
    
    settings = get_settings()
    query = query or settings.INGESTION_QUERY
    
    print(f"Query: {query}")
    print(f"Max Results: {max_results}\n")
    
    result = await job_run_ingestion(query=query, max_results=max_results)
    
    if result["status"] == "success":
        print("✓ Ingestion completed successfully\n")
        print_status("Run ID", result["run_id"])
        print_status("Articles Found", result["articles_found"])
        print_status("New Articles", result["articles_new"])
        print_status("Skipped (duplicates)", result["articles_skipped"])
        print_status("Vectors Added", result["vectors_added"])
        print_status("Vectors Skipped", result["vectors_skipped"])
    else:
        print(f"✗ Ingestion failed: {result.get('error')}")
    
    print()


async def cmd_insights():
    """Generate insights."""
    print_header("Generating Insights")
    
    result = await job_generate_insights()
    
    if result["status"] == "success":
        print("✓ Insights generated successfully\n")
        print_status("Insights Generated", result["insights_generated"])
        print_status("Articles Processed", result.get("articles_processed", 0))
        if result.get("insight_id"):
            print_status("Insight ID", result["insight_id"])
    elif result["status"] == "skipped":
        print(f"⚠️  Skipped: {result['message']}")
    else:
        print(f"✗ Failed: {result.get('error')}")
    
    print()


async def cmd_hypotheses():
    """Generate hypotheses."""
    print_header("Generating Hypotheses")
    
    result = await job_generate_hypotheses()
    
    if result["status"] == "success":
        print("✓ Hypotheses generated successfully\n")
        print_status("Hypotheses Generated", result["hypotheses_generated"])
        print_status("Insights Processed", result["insights_processed"])
    elif result["status"] == "skipped":
        print(f"⚠️  Skipped: {result['message']}")
    else:
        print(f"✗ Failed: {result.get('error')}")
    
    print()


async def cmd_refresh_vectors():
    """Refresh vector embeddings."""
    print_header("Refreshing Vector Embeddings")
    
    result = await job_refresh_vectors()
    
    if result["status"] == "success":
        print("✓ Vectors refreshed successfully\n")
        print_status("Documents Indexed", result["indexed"])
        print_status("Already Indexed", result["skipped"])
    elif result["status"] == "skipped":
        print(f"⚠️  Skipped: {result['message']}")
    else:
        print(f"✗ Failed: {result.get('error')}")
    
    print()


async def cmd_stats():
    """Show database statistics."""
    print_header("Database Statistics")
    
    db_health = check_db_health()
    
    if db_health.get("status") == "healthy":
        counts = db_health.get("counts", {})
        
        print("Content:")
        print_status("Total Articles", counts.get("articles", 0), 1)
        print_status("Total Insights", counts.get("insights", 0), 1)
        print_status("Total Hypotheses", counts.get("hypotheses", 0), 1)
        
        print("\nProcessing:")
        print_status("Ingestion Runs", counts.get("ingestion_runs", 0), 1)
        
        # Calculate rates
        articles = counts.get("articles", 0)
        insights = counts.get("insights", 0)
        hypotheses = counts.get("hypotheses", 0)
        
        print("\nRatios:")
        if articles > 0:
            print_status("Insights per Article", f"{insights/articles:.2f}", 1)
        if insights > 0:
            print_status("Hypotheses per Insight", f"{hypotheses/insights:.2f}", 1)
    else:
        print(f"✗ Database error: {db_health.get('error')}")
    
    print()


def print_help():
    """Print help message."""
    print("""
RTC Backend CLI

Usage:
    python cli.py <command> [options]

Commands:
    init-db              Initialize database
    reset-db             Reset database (DESTRUCTIVE!)
    health               Check system health
    ingest [query]       Run ingestion (optional custom query)
    generate-insights    Generate insights from articles
    generate-hypotheses  Generate hypotheses from insights
    refresh-vectors      Refresh vector embeddings
    stats                Show database statistics
    help                 Show this help message

Examples:
    python cli.py init-db
    python cli.py health
    python cli.py ingest
    python cli.py ingest "machine learning papers"
    python cli.py generate-insights
    python cli.py stats
""")


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "init-db":
            await cmd_init_db(reset=False)
        elif command == "reset-db":
            await cmd_init_db(reset=True)
        elif command == "health":
            await cmd_health()
        elif command == "ingest":
            query = sys.argv[2] if len(sys.argv) > 2 else None
            await cmd_ingest(query=query)
        elif command == "generate-insights":
            await cmd_insights()
        elif command == "generate-hypotheses":
            await cmd_hypotheses()
        elif command == "refresh-vectors":
            await cmd_refresh_vectors()
        elif command == "stats":
            await cmd_stats()
        elif command == "help":
            print_help()
        else:
            print(f"Unknown command: {command}")
            print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

