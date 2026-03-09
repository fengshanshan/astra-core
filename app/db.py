import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
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