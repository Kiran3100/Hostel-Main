"""
Admin Override Repository

Manages admin overrides of supervisor decisions with impact tracking,
approval workflows, and compliance monitoring.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, case
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.admin_override import (
    AdminOverride,
    OverrideReason,
    OverrideApproval,
    OverrideImpact
)
from app.models.admin.admin_user import AdminUser
from app.models.supervisor.supervisor import Supervisor
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    EntityNotFoundError,
    ValidationError,
    AuthorizationError
)


class AdminOverrideRepository(BaseRepository[AdminOverride]):
    """
    Override decision tracking with:
    - Impact analysis and tracking
    - Multi-level approval workflows
    - Pattern analysis for policy improvement
    - Compliance and audit reporting
    """

    def __init__(self, db: Session):
        super().__init__(AdminOverride, db)

    # ==================== OVERRIDE CREATION ====================

    async def create_override(
        self,
        admin_id: UUID,
        supervisor_id: Optional[UUID],
        hostel_id: UUID,
        override_type: str,
        entity_type: str,
        entity_id: UUID,
        reason: str,
        original_action: Optional[Dict] = None,
        override_action: Dict = None,
        severity: str = 'medium',
        requires_approval: bool = False
    ) -> AdminOverride:
        """
        Create admin override record.
        
        Args:
            admin_id: Admin performing override
            supervisor_id: Supervisor whose action is overridden
            hostel_id: Hostel context
            override_type: Type of override
            entity_type: Entity being modified
            entity_id: Entity ID
            reason: Detailed reason
            original_action: Original supervisor action
            override_action: Admin's override action
            severity: Override severity
            requires_approval: Needs higher approval
            
        Returns:
            Created AdminOverride instance
        """
        # Calculate action diff if both provided
        action_diff = None
        if original_action and override_action:
            action_diff = self._calculate_action_diff(original_action, override_action)

        override = AdminOverride(
            admin_id=admin_id,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            override_type=override_type,
            entity_type=entity_type,
            entity_id=entity_id,
            override_timestamp=datetime.utcnow(),
            reason=reason,
            original_action=original_action,
            override_action=override_action,
            action_diff=action_diff,
            severity=severity,
            requires_approval=requires_approval,
            approval_status='pending' if requires_approval else 'approved'
        )

        self.db.add(override)

        try:
            await self.db.flush()

            # Create impact assessment
            if severity in ('high', 'critical'):
                await self._create_impact_assessment(override.id)

            # Notify supervisor if specified
            if supervisor_id and not override.supervisor_notified:
                await self._notify_supervisor(override)

            return override

        except IntegrityError as e:
            await self.db.rollback()
            raise ValidationError(f"Failed to create override: {str(e)}")

    def _calculate_action_diff(
        self,
        original: Dict,
        override: Dict
    ) -> Dict[str, Any]:
        """Calculate differences between actions."""
        diff = {
            'changed_fields': [],
            'original_values': {},
            'new_values': {}
        }

        all_keys = set(original.keys()) | set(override.keys())
        
        for key in all_keys:
            orig_val = original.get(key)
            new_val = override.get(key)
            
            if orig_val != new_val:
                diff['changed_fields'].append(key)
                diff['original_values'][key] = orig_val
                diff['new_values'][key] = new_val

        return diff

    # ==================== OVERRIDE QUERIES ====================

    async def find_by_entity(
        self,
        entity_type: str,
        entity_id: UUID
    ) -> List[AdminOverride]:
        """Find all overrides for specific entity."""
        stmt = (
            select(AdminOverride)
            .where(AdminOverride.entity_type == entity_type)
            .where(AdminOverride.entity_id == entity_id)
            .options(
                selectinload(AdminOverride.admin),
                selectinload(AdminOverride.supervisor)
            )
            .order_by(desc(AdminOverride.override_timestamp))
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_by_admin(
        self,
        admin_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AdminOverride]:
        """Find overrides by specific admin."""
        stmt = (
            select(AdminOverride)
            .where(AdminOverride.admin_id == admin_id)
            .options(selectinload(AdminOverride.override_impact))
        )

        if start_date:
            stmt = stmt.where(AdminOverride.override_timestamp >= start_date)
        if end_date:
            stmt = stmt.where(AdminOverride.override_timestamp <= end_date)

        stmt = stmt.order_by(desc(AdminOverride.override_timestamp))

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_by_supervisor(
        self,
        supervisor_id: UUID,
        start_date: Optional[datetime] = None
    ) -> List[AdminOverride]:
        """Find overrides of specific supervisor's actions."""
        stmt = (
            select(AdminOverride)
            .where(AdminOverride.supervisor_id == supervisor_id)
            .options(selectinload(AdminOverride.admin))
        )

        if start_date:
            stmt = stmt.where(AdminOverride.override_timestamp >= start_date)

        stmt = stmt.order_by(desc(AdminOverride.override_timestamp))

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_pending_approval(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[AdminOverride]:
        """Find overrides pending approval."""
        stmt = (
            select(AdminOverride)
            .where(AdminOverride.requires_approval == True)
            .where(AdminOverride.approval_status == 'pending')
            .options(
                selectinload(AdminOverride.admin),
                selectinload(AdminOverride.supervisor)
            )
        )

        if hostel_id:
            stmt = stmt.where(AdminOverride.hostel_id == hostel_id)

        stmt = stmt.order_by(
            desc(AdminOverride.severity),
            AdminOverride.override_timestamp
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_high_impact_overrides(
        self,
        days: int = 30,
        min_impact_score: float = 70.0
    ) -> List[AdminOverride]:
        """Find high-impact overrides in period."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(AdminOverride)
            .join(AdminOverride.override_impact)
            .where(AdminOverride.override_timestamp >= cutoff)
            .where(OverrideImpact.overall_impact_score >= min_impact_score)
            .options(
                selectinload(AdminOverride.override_impact),
                selectinload(AdminOverride.admin)
            )
            .order_by(desc(OverrideImpact.overall_impact_score))
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    # ==================== APPROVAL WORKFLOW ====================

    async def create_approval_request(
        self,
        override_id: UUID,
        approver_id: UUID,
        escalation_level: int = 1,
        expires_in_hours: int = 48
    ) -> OverrideApproval:
        """Create approval request for override."""
        override = await self.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        approval = OverrideApproval(
            override_id=override_id,
            approver_id=approver_id,
            approval_status='pending',
            escalation_level=escalation_level,
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours)
        )

        self.db.add(approval)
        await self.db.flush()
        return approval

    async def approve_override(
        self,
        override_id: UUID,
        approver_id: UUID,
        decision_notes: Optional[str] = None,
        conditions: Optional[List[str]] = None
    ) -> AdminOverride:
        """Approve override request."""
        override = await self.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        if not override.requires_approval:
            raise ValidationError("Override does not require approval")

        # Find pending approval
        approval_stmt = (
            select(OverrideApproval)
            .where(OverrideApproval.override_id == override_id)
            .where(OverrideApproval.approver_id == approver_id)
            .where(OverrideApproval.approval_status == 'pending')
        )
        result = await self.db.execute(approval_stmt)
        approval = result.scalar_one_or_none()

        if not approval:
            raise EntityNotFoundError("No pending approval found")

        # Update approval
        approval.approval_status = 'approved'
        approval.decision_timestamp = datetime.utcnow()
        approval.decision_notes = decision_notes
        approval.conditions = conditions or []
        approval.conditions_met = len(conditions or []) == 0

        # Update override
        override.approval_status = 'approved'
        override.approved_by_id = approver_id
        override.approved_at = datetime.utcnow()
        override.approval_notes = decision_notes

        await self.db.flush()
        return override

    async def reject_override(
        self,
        override_id: UUID,
        approver_id: UUID,
        rejection_notes: str
    ) -> AdminOverride:
        """Reject override request."""
        override = await self.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        # Find and update approval
        approval_stmt = (
            select(OverrideApproval)
            .where(OverrideApproval.override_id == override_id)
            .where(OverrideApproval.approver_id == approver_id)
            .where(OverrideApproval.approval_status == 'pending')
        )
        result = await self.db.execute(approval_stmt)
        approval = result.scalar_one_or_none()

        if approval:
            approval.approval_status = 'rejected'
            approval.decision_timestamp = datetime.utcnow()
            approval.decision_notes = rejection_notes

        # Update override
        override.approval_status = 'rejected'
        override.approval_notes = rejection_notes

        # Auto-reverse the override
        await self.reverse_override(override_id, approver_id, "Approval rejected")

        await self.db.flush()
        return override

    # ==================== OVERRIDE REVERSAL ====================

    async def reverse_override(
        self,
        override_id: UUID,
        reversed_by_id: UUID,
        reversal_reason: str
    ) -> AdminOverride:
        """Reverse an override decision."""
        override = await self.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        if override.is_reversed:
            raise ValidationError("Override already reversed")

        override.is_reversed = True
        override.reversed_at = datetime.utcnow()
        override.reversed_by_id = reversed_by_id
        override.reversal_reason = reversal_reason

        await self.db.flush()
        return override

    # ==================== IMPACT ASSESSMENT ====================

    async def _create_impact_assessment(
        self,
        override_id: UUID
    ) -> OverrideImpact:
        """Create initial impact assessment."""
        impact = OverrideImpact(
            override_id=override_id,
            operational_impact_score=Decimal('0.00'),
            financial_impact_score=Decimal('0.00'),
            stakeholder_impact_score=Decimal('0.00'),
            reputation_impact_score=Decimal('0.00'),
            overall_impact_score=Decimal('0.00')
        )

        self.db.add(impact)
        await self.db.flush()
        return impact

    async def update_impact_assessment(
        self,
        override_id: UUID,
        impact_data: Dict[str, Any],
        assessed_by_id: Optional[UUID] = None
    ) -> OverrideImpact:
        """Update impact assessment with detailed data."""
        # Get or create impact
        stmt = select(OverrideImpact).where(
            OverrideImpact.override_id == override_id
        )
        result = await self.db.execute(stmt)
        impact = result.scalar_one_or_none()

        if not impact:
            impact = await self._create_impact_assessment(override_id)

        # Update impact scores
        if 'operational_impact_score' in impact_data:
            impact.operational_impact_score = Decimal(str(impact_data['operational_impact_score']))
        if 'financial_impact_score' in impact_data:
            impact.financial_impact_score = Decimal(str(impact_data['financial_impact_score']))
        if 'stakeholder_impact_score' in impact_data:
            impact.stakeholder_impact_score = Decimal(str(impact_data['stakeholder_impact_score']))
        if 'reputation_impact_score' in impact_data:
            impact.reputation_impact_score = Decimal(str(impact_data['reputation_impact_score']))

        # Calculate overall impact
        impact.overall_impact_score = (
            impact.operational_impact_score +
            impact.financial_impact_score +
            impact.stakeholder_impact_score +
            impact.reputation_impact_score
        ) / 4

        # Update financial details
        if 'estimated_cost' in impact_data:
            impact.estimated_cost = Decimal(str(impact_data['estimated_cost']))
        if 'actual_cost' in impact_data:
            impact.actual_cost = Decimal(str(impact_data['actual_cost']))
        if 'cost_savings' in impact_data:
            impact.cost_savings = Decimal(str(impact_data['cost_savings']))
        if 'revenue_impact' in impact_data:
            impact.revenue_impact = Decimal(str(impact_data['revenue_impact']))

        # Update stakeholder impact
        if 'students_affected' in impact_data:
            impact.students_affected = impact_data['students_affected']
        if 'staff_affected' in impact_data:
            impact.staff_affected = impact_data['staff_affected']
        if 'affected_parties_details' in impact_data:
            impact.affected_parties_details = impact_data['affected_parties_details']

        # Update outcome
        if 'outcome_status' in impact_data:
            impact.outcome_status = impact_data['outcome_status']
        if 'outcome_description' in impact_data:
            impact.outcome_description = impact_data['outcome_description']

        impact.assessed_by_id = assessed_by_id
        impact.assessed_at = datetime.utcnow()

        await self.db.flush()
        return impact

    # ==================== PATTERN ANALYSIS ====================

    async def find_pattern_overrides(
        self,
        pattern_type: str = 'type',
        days: int = 90,
        min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Analyze override patterns for policy improvement.
        
        Args:
            pattern_type: 'type', 'reason', or 'entity'
            days: Analysis period
            min_occurrences: Minimum pattern occurrences
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        if pattern_type == 'type':
            group_field = AdminOverride.override_type
        elif pattern_type == 'entity':
            group_field = AdminOverride.entity_type
        else:
            # For reason, we'd need to analyze reason_category
            # Simplified here
            group_field = AdminOverride.override_type

        stmt = (
            select(
                group_field.label('pattern'),
                func.count(AdminOverride.id).label('occurrence_count'),
                func.avg(
                    case(
                        (OverrideImpact.overall_impact_score.isnot(None),
                         OverrideImpact.overall_impact_score),
                        else_=0
                    )
                ).label('avg_impact')
            )
            .outerjoin(AdminOverride.override_impact)
            .where(AdminOverride.override_timestamp >= cutoff)
            .group_by(group_field)
            .having(func.count(AdminOverride.id) >= min_occurrences)
            .order_by(desc('occurrence_count'))
        )

        result = await self.db.execute(stmt)
        
        patterns = []
        for row in result:
            patterns.append({
                'pattern': row.pattern,
                'occurrence_count': row.occurrence_count,
                'avg_impact_score': float(row.avg_impact or 0),
                'recommendation': self._generate_pattern_recommendation(
                    row.pattern,
                    row.occurrence_count,
                    row.avg_impact
                )
            })

        return patterns

    def _generate_pattern_recommendation(
        self,
        pattern: str,
        count: int,
        avg_impact: Optional[Decimal]
    ) -> str:
        """Generate recommendation based on pattern analysis."""
        if count >= 10:
            return f"High frequency pattern '{pattern}' ({count} occurrences). Consider policy review."
        elif avg_impact and float(avg_impact) > 70:
            return f"High impact pattern '{pattern}'. Review approval requirements."
        else:
            return f"Monitor pattern '{pattern}' for trends."

    # ==================== ANALYTICS & REPORTING ====================

    async def get_override_statistics(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive override statistics."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Base filter
        filters = [
            AdminOverride.override_timestamp >= start_date,
            AdminOverride.override_timestamp <= end_date
        ]
        if admin_id:
            filters.append(AdminOverride.admin_id == admin_id)
        if hostel_id:
            filters.append(AdminOverride.hostel_id == hostel_id)

        # Total overrides
        total_stmt = select(func.count(AdminOverride.id)).where(and_(*filters))
        total_overrides = await self.db.scalar(total_stmt) or 0

        # By severity
        severity_stmt = (
            select(
                AdminOverride.severity,
                func.count(AdminOverride.id).label('count')
            )
            .where(and_(*filters))
            .group_by(AdminOverride.severity)
        )
        severity_result = await self.db.execute(severity_stmt)
        by_severity = {row.severity: row.count for row in severity_result}

        # Approval stats
        approval_stmt = (
            select(
                AdminOverride.approval_status,
                func.count(AdminOverride.id).label('count')
            )
            .where(and_(*filters))
            .where(AdminOverride.requires_approval == True)
            .group_by(AdminOverride.approval_status)
        )
        approval_result = await self.db.execute(approval_stmt)
        by_approval_status = {row.approval_status: row.count for row in approval_result}

        # Average impact
        avg_impact_stmt = (
            select(func.avg(OverrideImpact.overall_impact_score))
            .join(AdminOverride.override_impact)
            .where(and_(*filters))
        )
        avg_impact = await self.db.scalar(avg_impact_stmt) or 0

        # Reversal rate
        reversed_stmt = select(func.count(AdminOverride.id)).where(
            and_(
                *filters,
                AdminOverride.is_reversed == True
            )
        )
        reversed_count = await self.db.scalar(reversed_stmt) or 0
        reversal_rate = (reversed_count / total_overrides * 100) if total_overrides > 0 else 0

        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'total_overrides': total_overrides,
            'by_severity': by_severity,
            'by_approval_status': by_approval_status,
            'avg_impact_score': float(avg_impact),
            'reversed_count': reversed_count,
            'reversal_rate_percentage': round(reversal_rate, 2),
            'approval_required_count': sum(by_approval_status.values())
        }

    # ==================== HELPER METHODS ====================

    async def _notify_supervisor(self, override: AdminOverride) -> None:
        """Notify supervisor of override (placeholder)."""
        # Implementation would send actual notification
        override.supervisor_notified = True
        override.supervisor_notified_at = datetime.utcnow()
        override.notification_method = 'email'
        # Actual notification sending would go here