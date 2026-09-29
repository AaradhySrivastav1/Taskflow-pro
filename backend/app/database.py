"""
Database engine/session setup.

Uses SQLite by default (zero-config, file-based, satisfies the Persistence
requirement without any external service). Swapping to PostgreSQL only
requires changing DATABASE_URL, since all queries go through SQLAlchemy's
ORM and are not SQLite-specific.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
