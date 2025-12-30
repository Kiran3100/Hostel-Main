# app/db/init_db.py
"""Database initialization utilities."""
import logging

from sqlalchemy import inspect
from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    Note: This is suitable for development/testing only.
    For production, use Alembic migrations instead.
    """
    try:
        # Import all models to ensure they're registered
        from app.db.base import import_models
        import_models()
        
        # Check if tables already exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            logger.info(f"Database already initialized with {len(existing_tables)} tables")
        else:
            # Create all tables
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def drop_db() -> None:
    """
    Drop all database tables.
    
    WARNING: This will delete all data! Use with caution.
    Only for development/testing purposes.
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Error dropping database: {e}")
        raise


def reset_db() -> None:
    """
    Reset the database by dropping and recreating all tables.
    
    WARNING: This will delete all data! Use with caution.
    Only for development/testing purposes.
    """
    logger.warning("Resetting database...")
    drop_db()
    init_db()
    logger.info("Database reset complete")