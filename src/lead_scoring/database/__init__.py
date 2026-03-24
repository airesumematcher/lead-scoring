"""
Database module for lead scoring system.
Provides SQLAlchemy models and database operations.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

__all__ = ["Base"]
