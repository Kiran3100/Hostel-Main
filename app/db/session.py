"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

from app.config.settings import settings

# Create database engine using the get_database_url method
engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_OVERFLOW,
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """
    Dependency function that yields a database session.
    
    Usage in FastAPI endpoints:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()