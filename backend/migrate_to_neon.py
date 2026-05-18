import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set python path to current directory so it can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.models import Base, Agent, Trade, Position, DailyPerformance, MarketSnapshot, NewsCache, AIResponse

# SQLite Local Database
sqlite_url = "sqlite:///tradeos.db"

# Neon PostgreSQL Database (Loaded dynamically from your secure .env)
neon_url = os.getenv("DATABASE_URL")
if not neon_url or "sqlite" in neon_url:
    neon_url = "postgresql://neondb_owner:npg_WpuLcm83MwQS@ep-steep-forest-apd1dovt.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"

print("Initializing database engines...")
sqlite_engine = create_engine(sqlite_url)
neon_engine = create_engine(neon_url)

print("Creating tables on Neon PostgreSQL (if they do not exist)...")
Base.metadata.create_all(bind=neon_engine)
print("Tables successfully initialized on Neon!")

# Sessions
SQLiteSession = sessionmaker(bind=sqlite_engine)
NeonSession = sessionmaker(bind=neon_engine)

sqlite_db = SQLiteSession()
neon_db = NeonSession()

def clone_record(session_from, session_to, model_class, id_field="id"):
    """
    Dynamically clones all records of model_class from session_from to session_to.
    Optimized for low-latency network performance using bulk ID lookup.
    """
    records = session_from.query(model_class).all()
    print(f"\n--- Migrating {model_class.__tablename__} ---")
    print(f"Found {len(records)} local records in SQLite.")
    if not records:
        return
        
    # Query all existing IDs on Neon DB in a single network roundtrip!
    existing_ids = set(r[0] for r in session_to.query(getattr(model_class, id_field)).all())
    print(f"Found {len(existing_ids)} existing records already on Neon.")
    
    cloned_count = 0
    for record in records:
        record_id = getattr(record, id_field)
        
        # Check against local set (0ms cost!) instead of remote database query (200ms cost!)
        if record_id not in existing_ids:
            # Build a dictionary of column attributes, excluding SQLAlchemy's session state
            attrs = {k: v for k, v in record.__dict__.items() if k != '_sa_instance_state'}
            
            # Instantiate a clean, new instrumented object
            new_record = model_class(**attrs)
            
            # Add to destination session
            session_to.add(new_record)
            cloned_count += 1
            
            # Commit in batches of 100 to optimize write performance
            if cloned_count % 100 == 0:
                session_to.commit()
                print(f"Pushed batch of {cloned_count} records...")
            
    if cloned_count % 100 != 0:
        session_to.commit()
        
    print(f"Successfully migrated {cloned_count} new records to {model_class.__tablename__}!")

try:
    # Migrate each table dynamically
    print("\nStarting high-speed cloning sequence...")
    
    clone_record(sqlite_db, neon_db, Agent)
    clone_record(sqlite_db, neon_db, Trade)
    clone_record(sqlite_db, neon_db, Position)
    clone_record(sqlite_db, neon_db, DailyPerformance)
    clone_record(sqlite_db, neon_db, MarketSnapshot)
    clone_record(sqlite_db, neon_db, NewsCache)
    clone_record(sqlite_db, neon_db, AIResponse)

    # Sync sequences so PostgreSQL starts auto-generating IDs correctly
    print("\nSyncing PostgreSQL sequences to prevent ID conflicts...")
    tables = [
        ("agents", "id"),
        ("trades", "id"),
        ("positions", "id"),
        ("daily_performance", "id"),
        ("market_snapshots", "id"),
        ("news_cache", "id"),
        ("ai_responses", "id")
    ]
    for table_name, pk_name in tables:
        try:
            # PostgreSQL sequence reset query
            seq_reset_query = f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{pk_name}'), 
                    coalesce((SELECT max({pk_name}) FROM {table_name}), 1)
                ) FROM {table_name};
            """
            neon_db.execute(text(seq_reset_query))
            print(f"Successfully synced sequence for table: {table_name}")
        except Exception as seq_err:
            pass
            
    neon_db.commit()
    print("\n🎉 DATA MIGRATION TO NEON COMPLETE!")

except Exception as e:
    neon_db.rollback()
    print(f"\nMigration Failed: {str(e)}")
finally:
    sqlite_db.close()
    neon_db.close()
