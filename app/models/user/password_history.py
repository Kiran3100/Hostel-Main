"""
Password History model for password reuse prevention.
"""
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import TimestampMixin, UUIDMixin

class PasswordHistory(BaseModel, UUIDMixin, TimestampMixin):
    """
    Password change history for security compliance.
    
    Prevents password reuse and tracks password change patterns.
    """
    __tablename__ = "user_password_history"
    __table_args__ = (
        {"comment": "Historical password hashes for reuse prevention"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
        comment="Foreign key to users table"
    )
    
    # Password Information
    password_hash = Column(
        String(255), 
        nullable=False,
        comment="Historical password hash"
    )
    
    # Change Context
    changed_by = Column(
        ForeignKey("users.id"), 
        nullable=True,
        comment="User who initiated the change (for admin resets)"
    )
    change_reason = Column(
        String(100), 
        nullable=True,
        comment="Reason for password change: user_request, admin_reset, security_breach, etc."
    )
    
    # Security
    ip_address = Column(
        String(45), 
        nullable=True,
        comment="IP address where password was changed"
    )

    # Relationships
    user = relationship("User", back_populates="password_history", foreign_keys=[user_id])
    changed_by_user = relationship("User", foreign_keys=[changed_by])

    def __repr__(self):
        return f"<PasswordHistory user_id={self.user_id} changed_at={self.created_at}>"