"""
Combined base models to resolve MRO conflicts.
"""

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin


class AnnouncementBaseModel(UUIDMixin, TimestampModel, AuditMixin, SoftDeleteMixin, BaseModel):
    """Combined base model for announcement entities with full functionality."""
    __abstract__ = True


class SimpleBaseModel(UUIDMixin, TimestampModel, BaseModel):
    """Simple base model for basic entities."""
    __abstract__ = True