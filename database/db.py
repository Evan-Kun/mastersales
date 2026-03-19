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

        # New fields for multi-source scraper
        if "source_url" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN source_url VARCHAR(500)"))

        indexes = inspector.get_indexes("contacts")
        has_linkedin_unique = any(
            idx.get("unique") and "linkedin_url" in idx.get("column_names", [])
            for idx in indexes
        )
        if has_linkedin_unique:
            with engine.begin() as conn:
                conn.execute(text("DROP INDEX IF EXISTS ix_contacts_linkedin_url"))

    if "companies" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("companies")}
        if "company_domain" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE companies ADD COLUMN company_domain VARCHAR(255)"))
