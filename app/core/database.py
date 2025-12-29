"""
Database Management and Connection Handling

Comprehensive database utilities with connection pooling,
session management, migration support, and health monitoring.
"""

import asyncio
import contextlib
from typing import Any, Dict, List, Optional, AsyncGenerator, Callable
from datetime import datetime
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    text,
    event
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

from .config import settings
from .exceptions import DatabaseError
from .logging import get_logger
from .monitoring import monitor_function

logger = get_logger(__name__)

# Database metadata and base model
metadata = MetaData()
Base = declarative_base(metadata=metadata)


class DatabaseManager:
    """Main database connection and session manager"""
    
    def __init__(self):
        self.async_engine: Optional[AsyncEngine] = None
        self.sync_engine: Optional[Any] = None
        self.async_session_factory: Optional[async_sessionmaker] = None
        self.sync_session_factory: Optional[sessionmaker] = None
        self._initialized = False
        self._connection_pool_stats = {
            'created_connections': 0,
            'closed_connections': 0,
            'active_connections': 0,
            'pool_size': 0
        }
    
    async def initialize(self):
        """Initialize database connections and session factories"""
        if self._initialized:
            return
        
        try:
            await self._create_async_engine()
            self._create_sync_engine()
            await self._setup_session_factories()
            await self._setup_connection_events()
            await self._verify_connection()
            
            self._initialized = True
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {str(e)}")
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    async def _create_async_engine(self):
        """Create async database engine with connection pooling"""
        engine_kwargs = {
            'echo': settings.database.DB_ECHO,
            'echo_pool': settings.database.DB_ECHO_POOL,
            'pool_size': settings.database.DB_POOL_SIZE,
            'max_overflow': settings.database.DB_MAX_OVERFLOW,
            'pool_timeout': settings.database.DB_POOL_TIMEOUT,
            'pool_recycle': settings.database.DB_POOL_RECYCLE,
            'pool_pre_ping': True,  # Verify connections before use
        }
        
        # Use StaticPool for SQLite, QueuePool for others
        if 'sqlite' in settings.database.DB_DRIVER:
            engine_kwargs.update({
                'poolclass': StaticPool,
                'connect_args': {"check_same_thread": False}
            })
        else:
            engine_kwargs['poolclass'] = QueuePool
        
        self.async_engine = create_async_engine(
            settings.database.database_url,
            **engine_kwargs
        )
        
        logger.info(f"Created async database engine: {settings.database.DB_DRIVER}")
    
    def _create_sync_engine(self):
        """Create synchronous database engine for migrations and admin tasks"""
        engine_kwargs = {
            'echo': settings.database.DB_ECHO,
            'echo_pool': settings.database.DB_ECHO_POOL,
            'pool_size': settings.database.DB_POOL_SIZE,
            'max_overflow': settings.database.DB_MAX_OVERFLOW,
            'pool_timeout': settings.database.DB_POOL_TIMEOUT,
            'pool_recycle': settings.database.DB_POOL_RECYCLE,
            'pool_pre_ping': True,
        }
        
        if 'sqlite' in settings.database.DB_DRIVER:
            engine_kwargs.update({
                'poolclass': StaticPool,
                'connect_args': {"check_same_thread": False}
            })
        else:
            engine_kwargs['poolclass'] = QueuePool
        
        self.sync_engine = create_engine(
            settings.database.sync_database_url,
            **engine_kwargs
        )
        
        logger.info(f"Created sync database engine: {settings.database.DB_DRIVER}")
    
    async def _setup_session_factories(self):
        """Setup async and sync session factories"""
        self.async_session_factory = async_sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        
        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        
        logger.info("Database session factories created")
    
    async def _setup_connection_events(self):
        """Setup connection pool event listeners for monitoring"""
        if self.async_engine:
            @event.listens_for(self.async_engine.sync_engine, "connect")
            def on_connect(dbapi_conn, connection_record):
                self._connection_pool_stats['created_connections'] += 1
                self._connection_pool_stats['active_connections'] += 1
                logger.debug("Database connection created")
            
            @event.listens_for(self.async_engine.sync_engine, "close")
            def on_close(dbapi_conn, connection_record):
                self._connection_pool_stats['closed_connections'] += 1
                self._connection_pool_stats['active_connections'] = max(
                    0, self._connection_pool_stats['active_connections'] - 1
                )
                logger.debug("Database connection closed")
            
            @event.listens_for(self.async_engine.sync_engine, "invalidate")
            def on_invalidate(dbapi_conn, connection_record, exception):
                logger.warning(f"Database connection invalidated: {exception}")
    
    async def _verify_connection(self):
        """Verify database connection is working"""
        try:
            async with self.get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
            
            logger.info("Database connection verified successfully")
            
        except Exception as e:
            logger.error(f"Database connection verification failed: {str(e)}")
            raise DatabaseError(f"Connection verification failed: {str(e)}")
    
    @contextlib.asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with automatic cleanup"""
        if not self._initialized:
            await self.initialize()
        
        session = self.async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()
    
    @contextlib.contextmanager
    def get_sync_session(self):
        """Get sync database session with automatic cleanup"""
        if not self._initialized:
            raise DatabaseError("Database manager not initialized")
        
        session = self.sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()
    
    async def execute_raw_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        fetch_results: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute raw SQL query with optional parameters"""
        try:
            async with self.get_async_session() as session:
                result = await session.execute(text(query), parameters or {})
                
                if fetch_results:
                    rows = result.fetchall()
                    # Convert to list of dictionaries
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in rows]
                
                await session.commit()
                return None
                
        except Exception as e:
            logger.error(f"Raw query execution failed: {str(e)}")
            raise DatabaseError(f"Query execution failed: {str(e)}")
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database health and return status"""
        try:
            start_time = datetime.utcnow()
            
            # Test connection
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Get pool statistics
            pool_stats = await self.get_pool_stats()
            
            return {
                "status": "healthy",
                "response_time": response_time,
                "pool_stats": pool_stats,
                "driver": settings.database.DB_DRIVER,
                "host": settings.database.DB_HOST,
                "database": settings.database.DB_NAME,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        if not self.async_engine:
            return {}
        
        pool = self.async_engine.pool
        
        stats = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            **self._connection_pool_stats
        }
        
        self._connection_pool_stats['pool_size'] = pool.size()
        
        return stats
    
    async def close(self):
        """Close all database connections"""
        try:
            if self.async_engine:
                await self.async_engine.dispose()
                logger.info("Async database engine disposed")
            
            if self.sync_engine:
                self.sync_engine.dispose()
                logger.info("Sync database engine disposed")
            
            self._initialized = False
            
        except Exception as e:
            logger.error(f"Error closing database connections: {str(e)}")


class TransactionManager:
    """Database transaction management utilities"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._savepoints = []
    
    async def begin_nested(self, name: Optional[str] = None) -> str:
        """Begin a nested transaction (savepoint)"""
        savepoint_name = name or f"sp_{len(self._savepoints) + 1}"
        
        try:
            savepoint = await self.session.begin_nested()
            self._savepoints.append({
                'name': savepoint_name,
                'savepoint': savepoint,
                'created_at': datetime.utcnow()
            })
            
            logger.debug(f"Created savepoint: {savepoint_name}")
            return savepoint_name
            
        except Exception as e:
            logger.error(f"Failed to create savepoint {savepoint_name}: {str(e)}")
            raise DatabaseError(f"Savepoint creation failed: {str(e)}")
    
    async def rollback_to_savepoint(self, name: str):
        """Rollback to a specific savepoint"""
        try:
            savepoint_info = None
            for sp in reversed(self._savepoints):
                if sp['name'] == name:
                    savepoint_info = sp
                    break
            
            if not savepoint_info:
                raise DatabaseError(f"Savepoint '{name}' not found")
            
            await savepoint_info['savepoint'].rollback()
            
            # Remove this and all subsequent savepoints
            self._savepoints = [
                sp for sp in self._savepoints 
                if sp['created_at'] <= savepoint_info['created_at']
            ]
            
            logger.debug(f"Rolled back to savepoint: {name}")
            
        except Exception as e:
            logger.error(f"Failed to rollback to savepoint {name}: {str(e)}")
            raise DatabaseError(f"Savepoint rollback failed: {str(e)}")
    
    async def commit_savepoint(self, name: str):
        """Commit a specific savepoint"""
        try:
            for i, sp in enumerate(self._savepoints):
                if sp['name'] == name:
                    await sp['savepoint'].commit()
                    self._savepoints.pop(i)
                    logger.debug(f"Committed savepoint: {name}")
                    return
            
            raise DatabaseError(f"Savepoint '{name}' not found")
            
        except Exception as e:
            logger.error(f"Failed to commit savepoint {name}: {str(e)}")
            raise DatabaseError(f"Savepoint commit failed: {str(e)}")


class MigrationManager:
    """Database migration management"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.migrations_table = Table(
            'schema_migrations',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('version', String(255), unique=True, nullable=False),
            Column('description', String(500)),
            Column('applied_at', DateTime, default=datetime.utcnow),
            Column('success', Boolean, default=True)
        )
    
    def create_migrations_table(self):
        """Create migrations tracking table"""
        try:
            with self.db_manager.get_sync_session() as session:
                self.migrations_table.create(
                    self.db_manager.sync_engine, 
                    checkfirst=True
                )
            
            logger.info("Migrations table created")
            
        except Exception as e:
            logger.error(f"Failed to create migrations table: {str(e)}")
            raise DatabaseError(f"Migrations table creation failed: {str(e)}")
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        try:
            with self.db_manager.get_sync_session() as session:
                result = session.execute(
                    text("SELECT version FROM schema_migrations WHERE success = true ORDER BY applied_at")
                )
                return [row[0] for row in result.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get applied migrations: {str(e)}")
            return []
    
    def record_migration(self, version: str, description: str, success: bool = True):
        """Record migration in tracking table"""
        try:
            with self.db_manager.get_sync_session() as session:
                session.execute(
                    text("""
                        INSERT INTO schema_migrations (version, description, applied_at, success)
                        VALUES (:version, :description, :applied_at, :success)
                    """),
                    {
                        'version': version,
                        'description': description,
                        'applied_at': datetime.utcnow(),
                        'success': success
                    }
                )
            
            logger.info(f"Recorded migration: {version} ({'success' if success else 'failed'})")
            
        except Exception as e:
            logger.error(f"Failed to record migration {version}: {str(e)}")
            raise DatabaseError(f"Migration recording failed: {str(e)}")


# Global database manager instance
database_manager = DatabaseManager()


# Dependency function for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session"""
    async with database_manager.get_async_session() as session:
        yield session


# Alias for compatibility with your dependencies.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_db_session for compatibility"""
    async with database_manager.get_async_session() as session:
        yield session


@monitor_function("database_operation")
async def safe_execute(
    session: AsyncSession,
    operation: Callable,
    *args,
    **kwargs
) -> Any:
    """Safely execute database operation with error handling"""
    try:
        return await operation(session, *args, **kwargs)
    except DisconnectionError as e:
        logger.error(f"Database disconnection error: {str(e)}")
        # Attempt to reconnect and retry once
        try:
            await session.rollback()
            return await operation(session, *args, **kwargs)
        except Exception as retry_error:
            logger.error(f"Retry failed: {str(retry_error)}")
            raise DatabaseError(f"Database operation failed after retry: {str(retry_error)}")
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error: {str(e)}")
        await session.rollback()
        raise DatabaseError(f"Database operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected database error: {str(e)}")
        await session.rollback()
        raise DatabaseError(f"Unexpected database error: {str(e)}")


async def execute_in_transaction(
    operation: Callable,
    *args,
    **kwargs
) -> Any:
    """Execute operation within a transaction"""
    async with database_manager.get_async_session() as session:
        transaction_manager = TransactionManager(session)
        
        try:
            result = await safe_execute(session, operation, *args, **kwargs)
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error(f"Transaction failed: {str(e)}")
            raise


async def execute_with_retry(
    operation: Callable,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    *args,
    **kwargs
) -> Any:
    """Execute database operation with retry logic"""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            async with database_manager.get_async_session() as session:
                return await safe_execute(session, operation, *args, **kwargs)
        except DatabaseError as e:
            last_exception = e
            
            if attempt < max_retries:
                logger.warning(f"Database operation failed (attempt {attempt + 1}), retrying in {retry_delay}s: {str(e)}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Database operation failed after {max_retries} retries: {str(e)}")
                break
    
    raise last_exception or DatabaseError("Operation failed after retries")


# Export main functions and classes
__all__ = [
    'Base',
    'metadata',
    'DatabaseManager',
    'TransactionManager',
    'MigrationManager',
    'database_manager',
    'get_db_session',
    'get_db',
    'safe_execute',
    'execute_in_transaction',
    'execute_with_retry'
]