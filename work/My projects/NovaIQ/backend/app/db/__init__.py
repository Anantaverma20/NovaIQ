"""
Database module - models and persistence.

Uses SQLModel for async-ready ORM with SQLite (or PostgreSQL).
"""

from app.db import models, sqlite

__all__ = ["models", "sqlite"]

