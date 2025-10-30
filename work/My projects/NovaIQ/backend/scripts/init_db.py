#!/usr/bin/env python3
"""
Database initialization script.

Usage:
    python scripts/init_db.py              # Create tables
    python scripts/init_db.py --reset      # Drop and recreate all tables (DESTRUCTIVE!)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.sqlite import init_db


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables and recreate (DESTRUCTIVE!)"
    )
    
    args = parser.parse_args()
    
    if args.reset:
        print("⚠️  WARNING: This will delete all data!")
        confirm = input("Type 'yes' to confirm: ")
        
        if confirm.lower() != "yes":
            print("Aborted.")
            return
        
        print("Dropping all tables...")
        init_db(drop_all=True)
    else:
        print("Creating database tables...")
        init_db(drop_all=False)
    
    print("✓ Done!")


if __name__ == "__main__":
    main()

