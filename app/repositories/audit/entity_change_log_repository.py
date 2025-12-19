"""
Entity change log repository for detailed field-level change tracking.

Provides granular change history with field-level tracking,
versioning, and comprehensive audit capabilities.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.audit import EntityChangeLog, EntityChangeHistory
from app.repositories.base.base_repository import BaseRepository


class EntityChangeLogRepository(BaseRepository):
    """
    Repository for detailed entity change tracking.
    
    Provides field-level change history, versioning,
    and comprehensive audit capabilities.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, EntityChangeLog)
    
    # ==================== CRUD Operations ====================
    
    def create_change_log(
        self,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
        old_value: Any,
        new_value: Any,
        change_type: str,
        changed_by: Optional[UUID] = None,
        change_reason: Optional[str] = None,
        **kwargs
    ) -> EntityChangeLog:
        """
        Create a new change log entry.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Field that changed
            old_value: Previous value
            new_value: New value
            change_type: Type of change (created, updated, deleted, etc.)
            changed_by: User who made the change
            change_reason: Reason for change
            **kwargs: Additional fields
            
        Returns:
            Created EntityChangeLog instance
        """
        change_log = EntityChangeLog(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            changed_by_user_id=changed_by,
            change_reason=change_reason,
            **kwargs
        )
        
        # Auto-calculate impact score
        change_log.calculate_impact_score()
        
        return self.create(change_log)
    
    def bulk_create_changes(
        self,
        changes: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> List[EntityChangeLog]:
        """
        Bulk create change log entries.
        
        Args:
            changes: List of change dictionaries
            batch_size: Batch size for processing
            
        Returns:
            List of created change logs
        """
        created_logs = []
        
        for i in range(0, len(changes), batch_size):
            batch = changes[i:i + batch_size]
            log_objects = [EntityChangeLog(**change) for change in batch]
            
            # Calculate impact scores
            for log in log_objects:
                log.calculate_impact_score()
            
            self.session.bulk_save_objects(log_objects, return_defaults=True)
            self.session.flush()
            
            created_logs.extend(log_objects)
        
        self.session.commit()
        return created_logs
    
    # ==================== Query Operations ====================
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_id: UUID,
        field_name: Optional[str] = None,
        only_valid: bool = True,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Get change history for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Optional specific field
            only_valid: Only return valid (non-invalidated) changes
            limit: Maximum results
            
        Returns:
            List of change logs
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.entity_id == entity_id
        )
        
        if field_name:
            query = query.filter(EntityChangeLog.field_name == field_name)
        
        if only_valid:
            query = query.filter(EntityChangeLog.is_valid == True)
        
        return query.order_by(desc(EntityChangeLog.created_at))\
            .limit(limit)\
            .all()
    
    def get_field_history(
        self,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
        only_valid: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get complete history of changes for a specific field.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            field_name: Field name
            only_valid: Only valid changes
            
        Returns:
            List of change timeline entries
        """
        changes = self.get_entity_history(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            only_valid=only_valid
        )
        
        return [
            {
                'timestamp': change.created_at.isoformat(),
                'old_value': change.old_value,
                'new_value': change.new_value,
                'changed_by': change.changed_by_user_name,
                'change_type': change.change_type,
                'reason': change.change_reason,
                'is_valid': change.is_valid
            }
            for change in changes
        ]
    
    def get_changes_by_user(
        self,
        user_id: UUID,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Get all changes made by a specific user.
        
        Args:
            user_id: User ID
            entity_type: Optional entity type filter
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of change logs
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.changed_by_user_id == user_id
        )
        
        if entity_type:
            query = query.filter(EntityChangeLog.entity_type == entity_type)
        
        if start_date:
            query = query.filter(EntityChangeLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(EntityChangeLog.created_at <= end_date)
        
        return query.order_by(desc(EntityChangeLog.created_at))\
            .limit(limit)\
            .all()
    
    def get_changes_requiring_review(
        self,
        entity_type: Optional[str] = None,
        reviewed: bool = False,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Get changes that require or have been reviewed.
        
        Args:
            entity_type: Optional entity type filter
            reviewed: True for reviewed, False for pending review
            limit: Maximum results
            
        Returns:
            List of change logs
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.requires_review == True
        )
        
        if entity_type:
            query = query.filter(EntityChangeLog.entity_type == entity_type)
        
        if reviewed:
            query = query.filter(EntityChangeLog.reviewed_at.isnot(None))
        else:
            query = query.filter(EntityChangeLog.reviewed_at.is_(None))
        
        return query.order_by(desc(EntityChangeLog.created_at))\
            .limit(limit)\
            .all()
    
    def get_sensitive_changes(
        self,
        entity_type: Optional[str] = None,
        include_pii: bool = True,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Get sensitive data changes for security audit.
        
        Args:
            entity_type: Optional entity type filter
            include_pii: Include PII changes
            start_date: Start date filter
            limit: Maximum results
            
        Returns:
            List of sensitive change logs
        """
        filters = []
        
        if include_pii:
            filters.append(
                or_(
                    EntityChangeLog.is_sensitive == True,
                    EntityChangeLog.is_pii == True
                )
            )
        else:
            filters.append(EntityChangeLog.is_sensitive == True)
        
        if entity_type:
            filters.append(EntityChangeLog.entity_type == entity_type)
        
        if start_date:
            filters.append(EntityChangeLog.created_at >= start_date)
        
        query = self.session.query(EntityChangeLog).filter(and_(*filters))
        
        return query.order_by(desc(EntityChangeLog.created_at))\
            .limit(limit)\
            .all()
    
    def get_invalidated_changes(
        self,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Get invalidated (rolled back) changes.
        
        Args:
            entity_type: Optional entity type filter
            start_date: Start date filter
            limit: Maximum results
            
        Returns:
            List of invalidated change logs
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.is_valid == False
        )
        
        if entity_type:
            query = query.filter(EntityChangeLog.entity_type == entity_type)
        
        if start_date:
            query = query.filter(EntityChangeLog.invalidated_at >= start_date)
        
        return query.order_by(desc(EntityChangeLog.invalidated_at))\
            .limit(limit)\
            .all()
    
    def find_by_change_source(
        self,
        source: str,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EntityChangeLog]:
        """
        Find changes by their source (web, api, import, etc.).
        
        Args:
            source: Change source
            entity_type: Optional entity type filter
            start_date: Start date filter
            limit: Maximum results
            
        Returns:
            List of change logs
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.change_source == source
        )
        
        if entity_type:
            query = query.filter(EntityChangeLog.entity_type == entity_type)
        
        if start_date:
            query = query.filter(EntityChangeLog.created_at >= start_date)
        
        return query.order_by(desc(EntityChangeLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_request_id(
        self,
        request_id: str
    ) -> List[EntityChangeLog]:
        """
        Find all changes related to a specific request.
        
        Args:
            request_id: Request ID
            
        Returns:
            List of change logs
        """
        return self.session.query(EntityChangeLog).filter(
            EntityChangeLog.request_id == request_id
        ).order_by(EntityChangeLog.created_at).all()
    
    # ==================== Invalidation Operations ====================
    
    def invalidate_change(
        self,
        change_id: UUID,
        invalidated_by: UUID,
        reason: str
    ) -> EntityChangeLog:
        """
        Invalidate a change (mark as rolled back).
        
        Args:
            change_id: Change log ID
            invalidated_by: User performing invalidation
            reason: Reason for invalidation
            
        Returns:
            Updated change log
        """
        change = self.get_by_id(change_id)
        if not change:
            raise ValueError(f"Change log {change_id} not found")
        
        change.invalidate(invalidated_by=invalidated_by, reason=reason)
        self.session.commit()
        
        return change
    
    def bulk_invalidate_changes(
        self,
        change_ids: List[UUID],
        invalidated_by: UUID,
        reason: str
    ) -> int:
        """
        Invalidate multiple changes at once.
        
        Args:
            change_ids: List of change log IDs
            invalidated_by: User performing invalidation
            reason: Reason for invalidation
            
        Returns:
            Number of invalidated changes
        """
        count = 0
        for change_id in change_ids:
            try:
                self.invalidate_change(change_id, invalidated_by, reason)
                count += 1
            except ValueError:
                continue
        
        return count
    
    # ==================== Review Operations ====================
    
    def mark_reviewed(
        self,
        change_id: UUID,
        reviewed_by: UUID
    ) -> EntityChangeLog:
        """
        Mark a change as reviewed.
        
        Args:
            change_id: Change log ID
            reviewed_by: User who reviewed
            
        Returns:
            Updated change log
        """
        change = self.get_by_id(change_id)
        if not change:
            raise ValueError(f"Change log {change_id} not found")
        
        change.mark_reviewed(reviewed_by=reviewed_by)
        self.session.commit()
        
        return change
    
    def bulk_mark_reviewed(
        self,
        change_ids: List[UUID],
        reviewed_by: UUID
    ) -> int:
        """
        Mark multiple changes as reviewed.
        
        Args:
            change_ids: List of change log IDs
            reviewed_by: User who reviewed
            
        Returns:
            Number of marked changes
        """
        count = 0
        for change_id in change_ids:
            try:
                self.mark_reviewed(change_id, reviewed_by)
                count += 1
            except ValueError:
                continue
        
        return count
    
    # ==================== Analytics Operations ====================
    
    def get_change_statistics(
        self,
        entity_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get change statistics for an entity type.
        
        Args:
            entity_type: Entity type
            start_date: Period start
            end_date: Period end
            
        Returns:
            Statistics dictionary
        """
        query = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        )
        
        total_changes = query.count()
        
        # Changes by type
        change_types = self.session.query(
            EntityChangeLog.change_type,
            func.count(EntityChangeLog.id)
        ).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        ).group_by(EntityChangeLog.change_type).all()
        
        # Most changed fields
        top_fields = self.session.query(
            EntityChangeLog.field_name,
            func.count(EntityChangeLog.id).label('count')
        ).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date
        ).group_by(EntityChangeLog.field_name)\
            .order_by(desc('count'))\
            .limit(10)\
            .all()
        
        # Top contributors
        top_users = self.session.query(
            EntityChangeLog.changed_by_user_name,
            func.count(EntityChangeLog.id).label('count')
        ).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.created_at <= end_date,
            EntityChangeLog.changed_by_user_name.isnot(None)
        ).group_by(EntityChangeLog.changed_by_user_name)\
            .order_by(desc('count'))\
            .limit(10)\
            .all()
        
        # Sensitive changes
        sensitive_count = query.filter(
            or_(
                EntityChangeLog.is_sensitive == True,
                EntityChangeLog.is_pii == True
            )
        ).count()
        
        # Invalid changes
        invalid_count = query.filter(
            EntityChangeLog.is_valid == False
        ).count()
        
        return {
            'entity_type': entity_type,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_changes': total_changes,
            'by_change_type': dict(change_types),
            'top_changed_fields': [
                {'field': field, 'count': count}
                for field, count in top_fields
            ],
            'top_contributors': [
                {'user': user, 'count': count}
                for user, count in top_users
            ],
            'sensitive_changes': {
                'count': sensitive_count,
                'percentage': sensitive_count / total_changes * 100 if total_changes else 0
            },
            'invalidated_changes': {
                'count': invalid_count,
                'percentage': invalid_count / total_changes * 100 if total_changes else 0
            }
        }
    
    def get_field_change_frequency(
        self,
        entity_type: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get frequency of changes for each field.
        
        Args:
            entity_type: Entity type
            days: Number of days to analyze
            
        Returns:
            List of field change frequencies
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.session.query(
            EntityChangeLog.field_name,
            func.count(EntityChangeLog.id).label('change_count'),
            func.count(func.distinct(EntityChangeLog.entity_id)).label('entity_count'),
            func.avg(EntityChangeLog.impact_score).label('avg_impact')
        ).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.is_valid == True
        ).group_by(EntityChangeLog.field_name)\
            .order_by(desc('change_count'))\
            .all()
        
        return [
            {
                'field_name': field,
                'total_changes': change_count,
                'affected_entities': entity_count,
                'average_impact': float(avg_impact) if avg_impact else 0.0,
                'changes_per_entity': change_count / entity_count if entity_count else 0
            }
            for field, change_count, entity_count, avg_impact in results
        ]
    
    def get_change_velocity(
        self,
        entity_type: str,
        entity_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate change velocity for an entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            days: Analysis period in days
            
        Returns:
            Change velocity metrics
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        changes = self.session.query(EntityChangeLog).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.entity_id == entity_id,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.is_valid == True
        ).all()
        
        if not changes:
            return {
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'period_days': days,
                'total_changes': 0,
                'changes_per_day': 0.0,
                'unique_fields_changed': 0,
                'average_impact': 0.0
            }
        
        unique_fields = set(change.field_name for change in changes)
        avg_impact = sum(
            change.impact_score for change in changes if change.impact_score
        ) / len(changes)
        
        return {
            'entity_type': entity_type,
            'entity_id': str(entity_id),
            'period_days': days,
            'total_changes': len(changes),
            'changes_per_day': len(changes) / days,
            'unique_fields_changed': len(unique_fields),
            'average_impact': avg_impact,
            'most_changed_field': max(
                unique_fields,
                key=lambda f: sum(1 for c in changes if c.field_name == f)
            ) if unique_fields else None
        }
    
    def detect_anomalies(
        self,
        entity_type: str,
        threshold_multiplier: float = 3.0,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous change patterns.
        
        Args:
            entity_type: Entity type to analyze
            threshold_multiplier: Standard deviations for anomaly
            days: Analysis period
            
        Returns:
            List of detected anomalies
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get change counts per entity
        entity_changes = self.session.query(
            EntityChangeLog.entity_id,
            EntityChangeLog.entity_display_name,
            func.count(EntityChangeLog.id).label('change_count')
        ).filter(
            EntityChangeLog.entity_type == entity_type,
            EntityChangeLog.created_at >= start_date,
            EntityChangeLog.is_valid == True
        ).group_by(
            EntityChangeLog.entity_id,
            EntityChangeLog.entity_display_name
        ).all()
        
        if len(entity_changes) < 2:
            return []
        
        # Calculate statistics
        change_counts = [count for _, _, count in entity_changes]
        mean = sum(change_counts) / len(change_counts)
        variance = sum((x - mean) ** 2 for x in change_counts) / len(change_counts)
        std_dev = variance ** 0.5
        
        threshold = mean + (threshold_multiplier * std_dev)
        
        # Find anomalies
        anomalies = []
        for entity_id, entity_name, count in entity_changes:
            if count > threshold:
                anomalies.append({
                    'entity_id': str(entity_id),
                    'entity_name': entity_name,
                    'change_count': count,
                    'expected_range': f"{mean:.2f} ± {std_dev:.2f}",
                    'deviation': count - mean,
                    'severity': 'high' if count > mean + (5 * std_dev) else 'medium'
                })
        
        return sorted(anomalies, key=lambda x: x['deviation'], reverse=True)


class EntityChangeHistoryRepository(BaseRepository):
    """
    Repository for entity state snapshots and version history.
    
    Provides snapshot-based history tracking for complete
    entity state at different points in time.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, EntityChangeHistory)
    
    # ==================== CRUD Operations ====================
    
    def create_snapshot(
        self,
        entity_type: str,
        entity_id: UUID,
        snapshot_data: Dict[str, Any],
        created_by: Optional[UUID] = None,
        change_summary: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> EntityChangeHistory:
        """
        Create a new entity state snapshot.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            snapshot_data: Complete entity state
            created_by: User creating snapshot
            change_summary: Summary of changes
            tags: Tags for categorization
            
        Returns:
            Created snapshot
        """
        # Get current version number
        current_version = self.session.query(
            func.max(EntityChangeHistory.version_number)
        ).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id
        ).scalar() or 0
        
        # Mark previous version as not current
        self.session.query(EntityChangeHistory).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id,
            EntityChangeHistory.is_current_version == True
        ).update({'is_current_version': False})
        
        snapshot = EntityChangeHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            snapshot_data=snapshot_data,
            snapshot_timestamp=datetime.utcnow(),
            version_number=current_version + 1,
            is_current_version=True,
            created_by=created_by,
            change_summary=change_summary,
            tags=tags or []
        )
        
        return self.create(snapshot)
    
    # ==================== Query Operations ====================
    
    def get_current_version(
        self,
        entity_type: str,
        entity_id: UUID
    ) -> Optional[EntityChangeHistory]:
        """
        Get current version snapshot.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            
        Returns:
            Current version snapshot or None
        """
        return self.session.query(EntityChangeHistory).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id,
            EntityChangeHistory.is_current_version == True
        ).first()
    
    def get_version_history(
        self,
        entity_type: str,
        entity_id: UUID,
        limit: int = 50
    ) -> List[EntityChangeHistory]:
        """
        Get version history for an entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            limit: Maximum versions to return
            
        Returns:
            List of version snapshots
        """
        return self.session.query(EntityChangeHistory).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id
        ).order_by(desc(EntityChangeHistory.version_number))\
            .limit(limit)\
            .all()
    
    def get_version_by_number(
        self,
        entity_type: str,
        entity_id: UUID,
        version_number: int
    ) -> Optional[EntityChangeHistory]:
        """
        Get specific version by number.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            version_number: Version number
            
        Returns:
            Version snapshot or None
        """
        return self.session.query(EntityChangeHistory).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id,
            EntityChangeHistory.version_number == version_number
        ).first()
    
    def get_version_at_time(
        self,
        entity_type: str,
        entity_id: UUID,
        timestamp: datetime
    ) -> Optional[EntityChangeHistory]:
        """
        Get entity version at specific point in time.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            timestamp: Point in time
            
        Returns:
            Closest version snapshot before timestamp
        """
        return self.session.query(EntityChangeHistory).filter(
            EntityChangeHistory.entity_type == entity_type,
            EntityChangeHistory.entity_id == entity_id,
            EntityChangeHistory.snapshot_timestamp <= timestamp
        ).order_by(desc(EntityChangeHistory.snapshot_timestamp))\
            .first()
    
    def compare_versions(
        self,
        entity_type: str,
        entity_id: UUID,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of an entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            version1: First version number
            version2: Second version number
            
        Returns:
            Comparison results
        """
        v1 = self.get_version_by_number(entity_type, entity_id, version1)
        v2 = self.get_version_by_number(entity_type, entity_id, version2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        # Compare snapshot data
        data1 = v1.snapshot_data
        data2 = v2.snapshot_data
        
        added = {k: v for k, v in data2.items() if k not in data1}
        removed = {k: v for k, v in data1.items() if k not in data2}
        changed = {
            k: {'old': data1[k], 'new': data2[k]}
            for k in data1.keys() & data2.keys()
            if data1[k] != data2[k]
        }
        
        return {
            'version1': version1,
            'version2': version2,
            'timestamp1': v1.snapshot_timestamp.isoformat(),
            'timestamp2': v2.snapshot_timestamp.isoformat(),
            'added_fields': added,
            'removed_fields': removed,
            'changed_fields': changed,
            'total_changes': len(added) + len(removed) + len(changed)
        }