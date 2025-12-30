"""SQLAlchemy Base class for all models."""
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here to ensure they're registered with Base
# This ensures all models are known to Alembic for migrations
def import_models():
    """Import all models to register them with SQLAlchemy."""
    try:
        # Import your models here when you create them
        # Example:
        # from app.models.user import User
        # from app.models.room import Room
        # from app.models.booking import Booking
        pass
    except ImportError as e:
        print(f"Warning: Could not import some models: {e}")

# Import models on module load
import_models()