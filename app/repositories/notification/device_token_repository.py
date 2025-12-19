# --- File: C:\Hostel-Main\app\repositories\notification\device_token_repository.py ---
"""
Device Token Repository for push notification device management.

Handles device registration, token lifecycle, and badge management
with optimization for push notification delivery.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.notification.device_token import DeviceToken
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.schemas.common.enums import DeviceType


class ActiveDeviceTokensSpec(Specification):
    """Specification for active device tokens."""
    
    def __init__(self, user_id: Optional[UUID] = None):
        self.user_id = user_id
    
    def is_satisfied_by(self, query):
        conditions = [DeviceToken.is_active == True, DeviceToken.token_invalid == False]
        if self.user_id:
            conditions.append(DeviceToken.user_id == self.user_id)
        return query.filter(and_(*conditions))


class RecentlyUsedDevicesSpec(Specification):
    """Specification for recently used devices."""
    
    def __init__(self, days: int = 30):
        self.cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    def is_satisfied_by(self, query):
        return query.filter(DeviceToken.last_used_at >= self.cutoff_date)


class DeviceTokenRepository(BaseRepository[DeviceToken]):
    """
    Repository for device token management with advanced querying and optimization.
    """

    def __init__(self, db_session: Session):
        super().__init__(DeviceToken, db_session)

    # Core device management operations
    def find_by_token(self, device_token: str) -> Optional[DeviceToken]:
        """Find device by token string."""
        return self.db_session.query(DeviceToken).filter(
            DeviceToken.device_token == device_token
        ).first()

    def find_by_user_and_token(self, user_id: UUID, device_token: str) -> Optional[DeviceToken]:
        """Find specific device token for user."""
        return self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.device_token == device_token
            )
        ).first()

    def find_active_tokens_for_user(self, user_id: UUID) -> List[DeviceToken]:
        """Get all active device tokens for a user."""
        spec = ActiveDeviceTokensSpec(user_id)
        return self.find_by_specification(spec)

    def find_active_tokens_by_type(
        self, 
        user_id: UUID, 
        device_type: DeviceType
    ) -> List[DeviceToken]:
        """Get active tokens for user by device type."""
        return self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.device_type == device_type.value,
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        ).all()

    def find_tokens_for_users(self, user_ids: List[UUID]) -> List[DeviceToken]:
        """Get all active tokens for multiple users."""
        return self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id.in_(user_ids),
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        ).all()

    # Token lifecycle management
    def register_or_update_token(
        self,
        user_id: UUID,
        device_token: str,
        device_type: DeviceType,
        device_info: Dict[str, Any]
    ) -> DeviceToken:
        """Register new token or update existing one."""
        existing_token = self.find_by_user_and_token(user_id, device_token)
        
        if existing_token:
            # Update existing token
            existing_token.is_active = True
            existing_token.token_invalid = False
            existing_token.last_used_at = datetime.utcnow()
            
            # Update device info if provided
            for key, value in device_info.items():
                if hasattr(existing_token, key) and value is not None:
                    setattr(existing_token, key, value)
            
            self.db_session.commit()
            return existing_token
        else:
            # Create new token
            new_token = DeviceToken(
                user_id=user_id,
                device_token=device_token,
                device_type=device_type.value,
                **device_info
            )
            return self.create(new_token)

    def deactivate_token(self, token_id: UUID, reason: str = None) -> bool:
        """Deactivate a device token."""
        token = self.find_by_id(token_id)
        if token:
            token.is_active = False
            if reason:
                token.metadata = token.metadata or {}
                token.metadata['deactivation_reason'] = reason
            self.db_session.commit()
            return True
        return False

    def mark_token_invalid(self, device_token: str, reason: str = None) -> bool:
        """Mark token as invalid (e.g., from provider feedback)."""
        token = self.find_by_token(device_token)
        if token:
            token.mark_invalid()
            if reason:
                token.metadata = token.metadata or {}
                token.metadata['invalid_reason'] = reason
            self.db_session.commit()
            return True
        return False

    def update_last_used(self, token_ids: List[UUID]) -> int:
        """Bulk update last used timestamp for tokens."""
        updated_count = self.db_session.query(DeviceToken).filter(
            DeviceToken.id.in_(token_ids)
        ).update(
            {DeviceToken.last_used_at: datetime.utcnow()},
            synchronize_session=False
        )
        self.db_session.commit()
        return updated_count

    # Badge management
    def update_badge_count(self, token_id: UUID, count: int) -> bool:
        """Update badge count for specific token."""
        token = self.find_by_id(token_id)
        if token:
            token.current_badge_count = max(0, count)
            self.db_session.commit()
            return True
        return False

    def increment_badge_for_user(self, user_id: UUID, amount: int = 1) -> int:
        """Increment badge count for all user's iOS devices."""
        updated_count = self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.device_type == DeviceType.IOS.value,
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        ).update(
            {DeviceToken.current_badge_count: DeviceToken.current_badge_count + amount},
            synchronize_session=False
        )
        self.db_session.commit()
        return updated_count

    def reset_badge_for_user(self, user_id: UUID) -> int:
        """Reset badge count for all user's iOS devices."""
        updated_count = self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.device_type == DeviceType.IOS.value,
                DeviceToken.is_active == True
            )
        ).update(
            {DeviceToken.current_badge_count: 0},
            synchronize_session=False
        )
        self.db_session.commit()
        return updated_count

    # Analytics and maintenance
    def find_stale_tokens(self, days: int = 90) -> List[DeviceToken]:
        """Find tokens that haven't been used in specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.db_session.query(DeviceToken).filter(
            or_(
                DeviceToken.last_used_at < cutoff_date,
                DeviceToken.last_used_at.is_(None)
            )
        ).all()

    def find_invalid_tokens(self, limit: int = 1000) -> List[DeviceToken]:
        """Find tokens marked as invalid for cleanup."""
        return self.db_session.query(DeviceToken).filter(
            DeviceToken.token_invalid == True
        ).limit(limit).all()

    def get_device_statistics(self) -> Dict[str, Any]:
        """Get device token statistics."""
        stats = self.db_session.query(
            DeviceToken.device_type,
            func.count().label('total_tokens'),
            func.sum(func.cast(DeviceToken.is_active, Integer)).label('active_tokens'),
            func.sum(func.cast(DeviceToken.token_invalid, Integer)).label('invalid_tokens')
        ).group_by(DeviceToken.device_type).all()
        
        return {
            'by_type': [
                {
                    'device_type': stat.device_type,
                    'total': stat.total_tokens,
                    'active': stat.active_tokens,
                    'invalid': stat.invalid_tokens
                }
                for stat in stats
            ],
            'total_devices': sum(stat.total_tokens for stat in stats),
            'total_active': sum(stat.active_tokens for stat in stats)
        }

    def cleanup_invalid_tokens(self, batch_size: int = 1000) -> int:
        """Clean up invalid tokens in batches."""
        deleted_count = 0
        while True:
            tokens_to_delete = self.db_session.query(DeviceToken.id).filter(
                DeviceToken.token_invalid == True
            ).limit(batch_size).all()
            
            if not tokens_to_delete:
                break
            
            token_ids = [token.id for token in tokens_to_delete]
            batch_deleted = self.db_session.query(DeviceToken).filter(
                DeviceToken.id.in_(token_ids)
            ).delete(synchronize_session=False)
            
            deleted_count += batch_deleted
            self.db_session.commit()
        
        return deleted_count

    # Device targeting for notifications
    def find_tokens_for_broadcast(
        self, 
        user_ids: Optional[List[UUID]] = None,
        device_types: Optional[List[DeviceType]] = None,
        exclude_tokens: Optional[List[str]] = None
    ) -> List[DeviceToken]:
        """Find tokens for broadcast notifications with filters."""
        query = self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        )
        
        if user_ids:
            query = query.filter(DeviceToken.user_id.in_(user_ids))
        
        if device_types:
            type_values = [dt.value for dt in device_types]
            query = query.filter(DeviceToken.device_type.in_(type_values))
        
        if exclude_tokens:
            query = query.filter(~DeviceToken.device_token.in_(exclude_tokens))
        
        return query.all()

    def get_user_preferred_tokens(self, user_id: UUID, limit: int = 5) -> List[DeviceToken]:
        """Get user's most recently used tokens for notification delivery."""
        return self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        ).order_by(desc(DeviceToken.last_used_at)).limit(limit).all()