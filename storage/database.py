"""
Database connectivity and session lifecycle management for IoT Data Engineering Pipeline.
Supports SQLite (development) and PostgreSQL (production).
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config.settings import settings
from monitoring.logging_config import logger

# Base class for declarative ORM models
Base = declarative_base()

# Engine creation with connection pooling or SQLite multithread options
connect_args = {}
database_url = settings.get_database_uri()

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    database_url,
    connect_args=connect_args,
    echo=settings.db.echo,
    future=True,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """Initialize database schema by creating all tables if they do not exist."""
    import storage.models  # Ensure models are imported so Base.metadata knows about them
    logger.info("Initializing database tables on %s", database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")


def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session context."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database transaction rolled back due to error: %s", e)
        raise
    finally:
        session.close()
