from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from config import settings

# Only use check_same_thread for SQLite databases
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine_kwargs = {
    "echo": False,
    "connect_args": connect_args
}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    """Dependency injection for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
