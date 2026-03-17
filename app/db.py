import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

from app.models import Base

# Ensure all models are loaded so create_all creates their tables
from app.models import User, Conversation, Message, SystemPrompt  # noqa: F401

def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL must be set (in .env or environment)")
    # Render/Heroku use postgres:// but psycopg2 requires postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = _get_database_url()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_conversations_timestamps()


def _migrate_conversations_timestamps() -> None:
    """
    Lightweight migration for older DBs:
    - Add conversations.created_at / conversations.updated_at if missing.
    This keeps existing deployments working without requiring alembic.
    """
    inspector = inspect(engine)
    try:
        cols = {c["name"] for c in inspector.get_columns("conversations")}
    except Exception:
        # conversations table may not exist yet, or DB not reachable
        return

    dialect = engine.dialect.name

    stmts: list[str] = []
    if "created_at" not in cols:
        if dialect == "postgresql":
            stmts.append("ALTER TABLE conversations ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        else:
            stmts.append("ALTER TABLE conversations ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    if "updated_at" not in cols:
        if dialect == "postgresql":
            stmts.append("ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        else:
            stmts.append("ALTER TABLE conversations ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")

    if not stmts:
        return

    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))