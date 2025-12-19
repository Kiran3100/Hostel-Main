"""
Admin override log repository for governance and accountability.

Tracks admin interventions and overrides with impact analysis,
approval workflows, and compliance monitoring.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.audit import AdminOverrideLog
from app.repositories.base.base_repository import BaseRepository


class AdminOverrideLogRepository(BaseRepository):
    """
    Repository for admin override tracking and governance.
    
    Provides comprehensive override logging, approval workflows,
    and impact analysis for administrative accountability.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, AdminOverrideLog)
    
    # ==================== CRUD Operations ====================
    
    def create_override_log(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        override_type: str,
        override_category: str,
        entity_type: str,
        entity_id: UUID,
        reason: str,
        override_action: Dict[str, Any],
        supervisor_id: Optional[UUID] = None,
        original_action: Optional[Dict] = None,
        **kwargs
    ) -> AdminOverrideLog:
        """
        Create a new admin override log entry.
        
        Args:
            admin_id: Admin performing override
            hostel_id: Hostel where override occurred
            override_type: Type of override
            override_category: Category of override
            entity_type: Type of entity affected
            entity_id: Entity ID
            reason: Override reason/justification
            override_action: Admin's override decision
            supervisor_id: Optional supervisor being overridden
            original_action: Optional original supervisor action
            **kwargs: Additional fields
            
        Returns:
            Created AdminOverrideLog instance
        """
        override_log = AdminOverrideLog(
            admin_id=admin_id,
            hostel_id=hostel_id,
            override_type=override_type,
            override_category=override_category,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            override_action=override_action,
            supervisor_id=supervisor_id,
            original_action=original_action or {},
            **kwargs
        )
        
        # Auto-calculate impact score if not provided
        if 'impact_score' not in kwargs:
            override_log.impact_score = self._calculate_impact_score(
                override_category,
                kwargs.get('severity', 'medium')
            )
        
        return self.create(override_log)
    
    # ==================== Query Operations ====================
    
    def find_by_admin(
        self,
        admin_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        override_category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AdminOverrideLog], int]:
        """
        Find overrides by admin with filtering.
        
        Args:
            admin_id: Admin ID
            start_date: Start date filter
            end_date: End date filter
            override_category: Optional category filter
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (override logs, total count)
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.admin_id == admin_id
        )
        
        if start_date:
            query = query.filter(AdminOverrideLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AdminOverrideLog.created_at <= end_date)
        
        if override_category:
            query = query.filter(AdminOverrideLog.override_category == override_category)
        
        total = query.count()
        
        results = query.order_by(desc(AdminOverrideLog.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return results, total
    
    def find_by_supervisor(
        self,
        supervisor_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find overrides of a supervisor's decisions.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of override logs
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.supervisor_id == supervisor_id
        )
        
        if start_date:
            query = query.filter(AdminOverrideLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AdminOverrideLog.created_at <= end_date)
        
        return query.order_by(desc(AdminOverrideLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find overrides by hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            severity: Optional severity filter
            limit: Maximum results
            
        Returns:
            List of override logs
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.hostel_id == hostel_id
        )
        
        if start_date:
            query = query.filter(AdminOverrideLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AdminOverrideLog.created_at <= end_date)
        
        if severity:
            query = query.filter(AdminOverrideLog.severity == severity)
        
        return query.order_by(desc(AdminOverrideLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find overrides for a specific entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            limit: Maximum results
            
        Returns:
            List of override logs
        """
        return self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.entity_type == entity_type,
            AdminOverrideLog.entity_id == entity_id
        ).order_by(desc(AdminOverrideLog.created_at))\
            .limit(limit)\
            .all()
    
    def find_pending_approval(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find overrides pending approval.
        
        Args:
            admin_id: Optional admin filter
            hostel_id: Optional hostel filter
            limit: Maximum results
            
        Returns:
            List of pending override logs
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.requires_approval == True,
            AdminOverrideLog.approved_at.is_(None)
        )
        
        if admin_id:
            query = query.filter(AdminOverrideLog.admin_id == admin_id)
        
        if hostel_id:
            query = query.filter(AdminOverrideLog.hostel_id == hostel_id)
        
        return query.order_by(AdminOverrideLog.created_at)\
            .limit(limit)\
            .all()
    
    def find_requiring_follow_up(
        self,
        hostel_id: Optional[UUID] = None,
        overdue_only: bool = False,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find overrides requiring follow-up.
        
        Args:
            hostel_id: Optional hostel filter
            overdue_only: Only return overdue items
            limit: Maximum results
            
        Returns:
            List of override logs requiring follow-up
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.follow_up_required == True,
            AdminOverrideLog.follow_up_completed != True
        )
        
        if hostel_id:
            query = query.filter(AdminOverrideLog.hostel_id == hostel_id)
        
        if overdue_only:
            # Add logic for overdue check if you have a follow_up_date field
            pass
        
        return query.order_by(AdminOverrideLog.created_at)\
            .limit(limit)\
            .all()
    
    def find_high_impact(
        self,
        threshold: Decimal = Decimal('75.0'),
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AdminOverrideLog]:
        """
        Find high-impact overrides.
        
        Args:
            threshold: Minimum impact score
            start_date: Start date filter
            limit: Maximum results
            
        Returns:
            List of high-impact override logs
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.impact_score >= threshold
        )
        
        if start_date:
            query = query.filter(AdminOverrideLog.created_at >= start_date)
        
        return query.order_by(desc(AdminOverrideLog.impact_score))\
            .limit(limit)\
            .all()
    
    # ==================== Approval Operations ====================
    
    def approve_override(
        self,
        override_id: UUID,
        approved_by: UUID
    ) -> AdminOverrideLog:
        """
        Approve a pending override.
        
        Args:
            override_id: Override log ID
            approved_by: User approving
            
        Returns:
            Updated override log
        """
        override = self.get_by_id(override_id)
        if not override:
            raise ValueError(f"Override {override_id} not found")
        
        if not override.requires_approval:
            raise ValueError("Override does not require approval")
        
        if override.approved_at:
            raise ValueError("Override already approved")
        
        override.approved_by = approved_by
        override.approved_at = datetime.utcnow()
        
        self.session.commit()
        
        return override
    
    def reject_override(
        self,
        override_id: UUID,
        rejected_by: UUID,
        rejection_reason: str
    ) -> AdminOverrideLog:
        """
        Reject a pending override.
        
        Args:
            override_id: Override log ID
            rejected_by: User rejecting
            rejection_reason: Reason for rejection
            
        Returns:
            Updated override log
        """
        override = self.get_by_id(override_id)
        if not override:
            raise ValueError(f"Override {override_id} not found")
        
        override.outcome_status = 'reversed'
        override.outcome = f"Rejected by {rejected_by}: {rejection_reason}"
        
        self.session.commit()
        
        return override
    
    # ==================== Analytics Operations ====================
    
    def get_override_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive override statistics.
        
        Args:
            start_date: Period start
            end_date: Period end
            hostel_id: Optional hostel filter
            
        Returns:
            Statistics dictionary
        """
        query = self.session.query(AdminOverrideLog).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        )
        
        if hostel_id:
            query = query.filter(AdminOverrideLog.hostel_id == hostel_id)
        
        all_overrides = query.all()
        total = len(all_overrides)
        
        if total == 0:
            return {
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'total_overrides': 0,
                'message': 'No overrides in period'
            }
        
        # By category
        category_counts = {}
        for override in all_overrides:
            cat = override.override_category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # By severity
        severity_counts = {}
        for override in all_overrides:
            sev = override.severity
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # By outcome
        outcome_counts = {}
        for override in all_overrides:
            outcome = override.outcome_status
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        
        # Top admins
        admin_counts = self.session.query(
            AdminOverrideLog.admin_id,
            AdminOverrideLog.admin_name,
            func.count(AdminOverrideLog.id).label('count')
        ).filter(
            AdminOverrideLog.created_at >= start_date,
            AdminOverrideLog.created_at <= end_date
        )
        
        if hostel_id:
            admin_counts = admin_counts.filter(AdminOverrideLog.hostel_id == hostel_id)
        
        admin_counts = admin_counts.group_by(
            AdminOverrideLog.admin_id,
            AdminOverrideLog.admin_name
        ).order_by(desc('count')).limit(10).all()
        
        # Average impact score
        impact_scores = [float(o.impact_score) for o in all_overrides if o.impact_score]
        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_overrides': total,
            'by_category': category_counts,
            'by_severity': severity_counts,
            'by_outcome': outcome_counts,
            'top_admins': [
                {'admin_id': str(aid), 'admin_name': name, 'count': count}
                for aid, name, count in admin_counts
            ],
            'average_impact_score': round(avg_impact, 2),
            'approval_metrics': {
                'requiring_approval': sum(1 for o in all_overrides if o.requires_approval),
                'approved': sum(1 for o in all_overrides if o.approved_at),
                'pending_approval': sum(
                    1 for o in all_overrides 
                    if o.requires_approval and not o.approved_at
                )
            }
        }
    
    def get_supervisor_override_analysis(
        self,
        supervisor_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Analyze overrides of a supervisor's decisions.
        
        Args:
            supervisor_id: Supervisor ID
            start_date: Period start
            end_date: Period end
            
        Returns:
            Analysis dictionary
        """
        overrides = self.find_by_supervisor(supervisor_id, start_date, end_date)
        
        if not overrides:
            return {
                'supervisor_id': str(supervisor_id),
                'total_overrides': 0,
                'message': 'No overrides found'
            }
        
        # By category
        category_counts = {}
        for override in overrides:
            cat = override.override_category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # By admin
        admin_counts = {}
        for override in overrides:
            admin = override.admin_name or str(override.admin_id)
            admin_counts[admin] = admin_counts.get(admin, 0) + 1
        
        # Average impact
        impact_scores = [float(o.impact_score) for o in overrides if o.impact_score]
        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
        
        return {
            'supervisor_id': str(supervisor_id),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_overrides': len(overrides),
            'by_category': category_counts,
            'by_admin': admin_counts,
            'average_impact_score': round(avg_impact, 2),
            'trend_analysis': 'increasing' if len(overrides) > 5 else 'stable'
        }
    
    # ==================== Helper Methods ====================
    
    def _calculate_impact_score(
        self,
        override_category: str,
        severity: str
    ) -> Decimal:
        """
        Calculate impact score based on category and severity.
        
        Args:
            override_category: Override category
            severity: Severity level
            
        Returns:
            Calculated impact score
        """
        # Base scores by category
        category_scores = {
            'decision_reversal': 40,
            'task_reassignment': 30,
            'priority_change': 25,
            'approval': 35,
            'rejection': 45,
            'other': 20
        }
        
        # Severity multipliers
        severity_multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 1.5,
            'critical': 2.0
        }
        
        base_score = category_scores.get(override_category, 30)
        multiplier = severity_multipliers.get(severity, 1.0)
        
        score = base_score * multiplier
        
        # Cap at 100
        return Decimal(str(min(100, score)))