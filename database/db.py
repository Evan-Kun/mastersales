from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Add columns that don't exist yet (lightweight migration for SQLite)."""
    inspector = inspect(engine)
    if "contacts" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("contacts")}
        if "deleted_at" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN deleted_at DATETIME"))
