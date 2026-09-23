from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# Only use check_same_thread for SQLite databases
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine_kwargs = {
    "echo": False,
    "connect_args": connect_args
}
if "sqlite" not in settings.DATABASE_URL:
    # Every page load runs several DB queries (positions, trades, leaderboard, agents, ...).
    # NullPool opened a brand-new TCP+TLS connection to Postgres/Neon per query, which on a
    # remote DB adds 100-300ms+ of pure handshake latency to EVERY request. A small persistent
    # pool reuses connections instead. pre_ping avoids surfacing errors from connections the
    # server dropped while idle; recycle keeps us under typical managed-Postgres idle timeouts.
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 280

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


# Columns added to existing tables after their initial release. `Base.metadata.create_all`
# only creates missing TABLES, not missing COLUMNS on tables that already exist (e.g. on Neon),
# so any new nullable column needs a matching entry here to reach already-deployed databases.
_NEW_COLUMNS = {
    "agents": [
        ("mode", "VARCHAR(20) DEFAULT 'FLEET'"),
        ("starting_capital", "FLOAT"),
        ("death_threshold", "FLOAT"),
        ("is_dead", "BOOLEAN DEFAULT FALSE"),
        ("died_at", "TIMESTAMP"),
        ("trading_paused", "BOOLEAN DEFAULT FALSE"),
    ],
    "arena_debate_logs": [
        ("indicators_snapshot", "TEXT"),
    ],
}


def run_lightweight_migrations():
    """Adds any missing columns listed in _NEW_COLUMNS to already-existing tables."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, columns in _NEW_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, col_def in columns:
                if col_name in existing_columns:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
