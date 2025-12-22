"""
Database connection settings for the hostel management system.
Provides SQLAlchemy session management and connection pooling.
"""

import time
from typing import Generator, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, event, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Create SQLAlchemy base class
Base = declarative_base()

# Configure database engine
engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,  # Check connection before using it
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_OVERFLOW,
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=settings.DB_ECHO,
    connect_args=settings.DB_CONNECT_ARGS,
)

# Create sessionmaker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Event listeners for performance monitoring
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time - start timer"""
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time - stop timer and log if slow query"""
    total_time = time.time() - conn.info['query_start_time'].pop()
    
    # Log slow queries (more than 0.5 seconds)
    if total_time > 0.5:
        logger.warning(
            f"Slow query detected ({total_time:.4f}s): "
            f"{statement[:100]}... with params {parameters}"
        )

def get_db_session() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup"""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database context error: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

class DatabaseStats:
    """Database statistics collection"""
    
    def __init__(self):
        self.query_count = 0
        self.slow_query_count = 0
        self.error_count = 0
        self.connection_errors = 0
        self.average_query_time = 0.0
    
    def reset_stats(self):
        """Reset all statistics"""
        self.query_count = 0
        self.slow_query_count = 0
        self.error_count = 0
        self.connection_errors = 0
        self.average_query_time = 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all statistics"""
        return {
            "query_count": self.query_count,
            "slow_query_count": self.slow_query_count,
            "error_count": self.error_count,
            "connection_errors": self.connection_errors,
            "average_query_time": self.average_query_time,
            "connection_pool": {
                "size": settings.DB_POOL_SIZE,
                "overflow": settings.DB_POOL_OVERFLOW,
                "recycle": 3600
            }
        }

# Global database stats instance
db_stats = DatabaseStats()

class DatabaseHealthCheck:
    """Database health check utilities"""
    
    @staticmethod
    async def check_database_connection() -> Dict[str, Any]:
        """Check database connection health"""
        start_time = time.time()
        session = SessionLocal()
        
        try:
            # Execute simple query
            session.execute("SELECT 1")
            is_connected = True
            error_message = None
        except exc.DBAPIError as e:
            is_connected = False
            error_message = str(e)
            db_stats.connection_errors += 1
        finally:
            session.close()
        
        response_time = (time.time() - start_time) * 1000  # in milliseconds
        
        return {
            "is_connected": is_connected,
            "response_time_ms": response_time,
            "error": error_message,
            "database": settings.DB_NAME,
            "host": settings.DB_HOST,
            "connection_stats": {
                "pool_size": settings.DB_POOL_SIZE,
                "connection_errors": db_stats.connection_errors
            }
        }