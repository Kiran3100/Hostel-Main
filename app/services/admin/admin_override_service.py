"""
Admin Override Service

Business logic for managing admin overrides of supervisor decisions
including approval workflows, impact tracking, and compliance.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.admin.admin_override import (
    AdminOverride,
    OverrideReason,
    OverrideApproval,
    OverrideImpact
)
from app.repositories.admin.admin_override_repository import AdminOverrideRepository
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    AuthorizationError,
    BusinessRuleViolationError
)


class AdminOverrideService:
    """
    Override management service with:
    - Override creation and validation
    - Multi-level approval workflows
    - Impact assessment and tracking
    - Pattern analysis for policy improvement
    - Compliance and audit reporting
    """

    def __init__(self, db: Session):
        self.db = db
        self.override_repo = AdminOverrideRepository(db)
        self.admin_repo = AdminUserRepository(db)

        # Configuration
        self.approval_thresholds = {
            'low': {'requires_approval': False, 'approver_level': 0},
            'medium': {'requires_approval': False, 'approver_level': 0},
            'high': {'requires_approval': True, 'approver_level': 7},
            'critical': {'requires_approval': True, 'approver_level': 9}
        }

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
        reason_category: Optional[str] = None,
        original_action: Optional[Dict] = None,
        override_action: Dict = None,
        severity: Optional[str] = None,
        impact_data: Optional[Dict] = None
    ) -> AdminOverride:
        """
        Create admin override with validation and workflow initiation.
        
        Args:
            admin_id: Admin performing override
            supervisor_id: Supervisor being overridden (if applicable)
            hostel_id: Hostel context
            override_type: Type of override
            entity_type: Entity being modified
            entity_id: Entity ID
            reason: Detailed reason
            reason_category: Categorized reason
            original_action: Original supervisor action
            override_action: Admin's override action
            severity: Override severity (auto-calculated if None)
            impact_data: Impact assessment data
            
        Returns:
            Created override with approval workflow if needed
        """
        # Validate admin has override permission
        await self._validate_override_permission(admin_id, hostel_id)

        # Auto-determine severity if not provided
        if not severity:
            severity = await self._calculate_severity(
                override_type,
                original_action,
                override_action
            )

        # Check if approval required
        approval_config = self.approval_thresholds.get(
            severity,
            self.approval_thresholds['medium']
        )
        requires_approval = approval_config['requires_approval']

        # Create override
        override = await self.override_repo.create_override(
            admin_id=admin_id,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            override_type=override_type,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            original_action=original_action,
            override_action=override_action,
            severity=severity,
            requires_approval=requires_approval
        )

        # Create impact assessment
        if impact_data or severity in ['high', 'critical']:
            await self._create_or_update_impact(
                override.id,
                impact_data or {}
            )

        # Initiate approval workflow if required
        if requires_approval:
            await self._initiate_approval_workflow(
                override.id,
                severity,
                admin_id
            )

        await self.db.commit()
        return override

    async def _validate_override_permission(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> None:
        """Validate admin has permission to perform override."""
        from app.services.admin.admin_permission_service import AdminPermissionService
        
        permission_service = AdminPermissionService(self.db)
        
        has_permission = await permission_service.check_permission(
            admin_id=admin_id,
            permission_key='can_override_supervisor_actions',
            hostel_id=hostel_id
        )

        if not has_permission:
            raise AuthorizationError(
                "Admin does not have permission to override supervisor actions"
            )

    async def _calculate_severity(
        self,
        override_type: str,
        original_action: Optional[Dict],
        override_action: Dict
    ) -> str:
        """Calculate override severity based on context."""
        # High severity override types
        high_severity_types = [
            'booking_cancellation',
            'fee_waiver',
            'complaint_dismissal',
            'disciplinary_reversal'
        ]

        if override_type in high_severity_types:
            return 'high'

        # Check financial impact
        if 'amount' in override_action:
            amount = Decimal(str(override_action['amount']))
            if amount > 5000:
                return 'critical'
            elif amount > 1000:
                return 'high'
            elif amount > 500:
                return 'medium'

        # Default to medium
        return 'medium'

    async def _initiate_approval_workflow(
        self,
        override_id: UUID,
        severity: str,
        requesting_admin_id: UUID
    ) -> None:
        """Initiate approval workflow for override."""
        # Find appropriate approver
        approver_level = self.approval_thresholds[severity]['approver_level']
        
        # Get admin's manager or higher level admin
        admin = await self.admin_repo.find_by_id(requesting_admin_id)
        if not admin:
            return

        approver = None
        
        # Try to get manager first
        if admin.reports_to_id:
            potential_approver = await self.admin_repo.find_by_id(admin.reports_to_id)
            if potential_approver and potential_approver.admin_level >= approver_level:
                approver = potential_approver

        # If no suitable manager, find any admin with required level
        if not approver:
            from sqlalchemy import select
            
            stmt = (
                select(AdminUser)
                .where(AdminUser.admin_level >= approver_level)
                .where(AdminUser.is_active == True)
                .where(AdminUser.is_deleted == False)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            approver = result.scalar_one_or_none()

        if approver:
            await self.override_repo.create_approval_request(
                override_id=override_id,
                approver_id=approver.id,
                escalation_level=1
            )

    # ==================== OVERRIDE QUERIES ====================

    async def get_override_by_id(
        self,
        override_id: UUID,
        include_impact: bool = True
    ) -> Optional[AdminOverride]:
        """Get override by ID with optional impact data."""
        override = await self.override_repo.find_by_id(override_id)
        
        if override and include_impact and not override.override_impact:
            # Load impact if not already loaded
            impact = await self.override_repo.get_impact_by_override_id(override_id)
            override.override_impact = impact

        return override

    async def get_admin_overrides(
        self,
        admin_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[AdminOverride]:
        """Get overrides by specific admin with filters."""
        overrides = await self.override_repo.find_by_admin(
            admin_id,
            start_date,
            end_date
        )

        if severity:
            overrides = [o for o in overrides if o.severity == severity]

        return overrides

    async def get_supervisor_overrides(
        self,
        supervisor_id: UUID,
        start_date: Optional[datetime] = None
    ) -> List[AdminOverride]:
        """Get overrides of specific supervisor's actions."""
        return await self.override_repo.find_by_supervisor(
            supervisor_id,
            start_date
        )

    async def get_pending_approvals(
        self,
        approver_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None
    ) -> List[AdminOverride]:
        """Get overrides pending approval."""
        pending = await self.override_repo.find_pending_approval(hostel_id)

        if approver_id:
            # Filter for specific approver
            filtered = []
            for override in pending:
                # Check if approver has pending approval for this override
                from sqlalchemy import select
                
                stmt = (
                    select(OverrideApproval)
                    .where(OverrideApproval.override_id == override.id)
                    .where(OverrideApproval.approver_id == approver_id)
                    .where(OverrideApproval.approval_status == 'pending')
                )
                result = await self.db.execute(stmt)
                if result.scalar_one_or_none():
                    filtered.append(override)
            
            return filtered

        return pending

    async def get_high_impact_overrides(
        self,
        days: int = 30,
        min_impact_score: float = 70.0
    ) -> List[AdminOverride]:
        """Get high-impact overrides within period."""
        return await self.override_repo.find_high_impact_overrides(
            days,
            min_impact_score
        )

    # ==================== APPROVAL WORKFLOW ====================

    async def approve_override(
        self,
        override_id: UUID,
        approver_id: UUID,
        decision_notes: Optional[str] = None,
        conditions: Optional[List[str]] = None
    ) -> AdminOverride:
        """Approve override request."""
        # Validate approver has authority
        await self._validate_approver_authority(override_id, approver_id)

        override = await self.override_repo.approve_override(
            override_id=override_id,
            approver_id=approver_id,
            decision_notes=decision_notes,
            conditions=conditions
        )

        await self.db.commit()
        
        # Notify requesting admin
        await self._notify_override_decision(override, 'approved')

        return override

    async def reject_override(
        self,
        override_id: UUID,
        approver_id: UUID,
        rejection_notes: str
    ) -> AdminOverride:
        """Reject override request."""
        # Validate approver has authority
        await self._validate_approver_authority(override_id, approver_id)

        override = await self.override_repo.reject_override(
            override_id=override_id,
            approver_id=approver_id,
            rejection_notes=rejection_notes
        )

        await self.db.commit()
        
        # Notify requesting admin
        await self._notify_override_decision(override, 'rejected')

        return override

    async def _validate_approver_authority(
        self,
        override_id: UUID,
        approver_id: UUID
    ) -> None:
        """Validate approver has authority for this override."""
        override = await self.override_repo.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        approver = await self.admin_repo.find_by_id(approver_id)
        if not approver:
            raise EntityNotFoundError(f"Approver {approver_id} not found")

        # Check level requirement
        required_level = self.approval_thresholds[override.severity]['approver_level']
        
        if approver.admin_level < required_level:
            raise AuthorizationError(
                f"Approver level ({approver.admin_level}) is below required "
                f"level ({required_level}) for {override.severity} severity overrides"
            )

    async def _notify_override_decision(
        self,
        override: AdminOverride,
        decision: str
    ) -> None:
        """Notify relevant parties of override decision."""
        # Implementation would send notifications
        # via email, SMS, in-app, etc.
        pass

    async def escalate_approval(
        self,
        override_id: UUID,
        current_approver_id: UUID,
        escalation_reason: str
    ) -> OverrideApproval:
        """Escalate override approval to higher level."""
        override = await self.override_repo.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        # Get current approval
        from sqlalchemy import select
        
        stmt = (
            select(OverrideApproval)
            .where(OverrideApproval.override_id == override_id)
            .where(OverrideApproval.approver_id == current_approver_id)
            .where(OverrideApproval.approval_status == 'pending')
        )
        result = await self.db.execute(stmt)
        current_approval = result.scalar_one_or_none()

        if not current_approval:
            raise ValidationError("No pending approval found for this approver")

        # Find higher level approver
        current_approver = await self.admin_repo.find_by_id(current_approver_id)
        required_level = current_approver.admin_level + 1

        stmt = (
            select(AdminUser)
            .where(AdminUser.admin_level >= required_level)
            .where(AdminUser.is_active == True)
            .where(AdminUser.is_deleted == False)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        higher_approver = result.scalar_one_or_none()

        if not higher_approver:
            raise BusinessRuleViolationError(
                "No higher level approver available for escalation"
            )

        # Mark current approval as escalated
        current_approval.approval_status = 'escalated'
        current_approval.decision_notes = escalation_reason

        # Create new approval at higher level
        new_approval = await self.override_repo.create_approval_request(
            override_id=override_id,
            approver_id=higher_approver.id,
            escalation_level=current_approval.escalation_level + 1
        )

        await self.db.commit()
        return new_approval

    # ==================== OVERRIDE REVERSAL ====================

    async def reverse_override(
        self,
        override_id: UUID,
        reversed_by_id: UUID,
        reversal_reason: str
    ) -> AdminOverride:
        """Reverse an override decision."""
        # Validate reversal authority
        reverser = await self.admin_repo.find_by_id(reversed_by_id)
        if not reverser or not reverser.can_override_supervisor_actions:
            raise AuthorizationError("Insufficient permissions to reverse override")

        override = await self.override_repo.reverse_override(
            override_id=override_id,
            reversed_by_id=reversed_by_id,
            reversal_reason=reversal_reason
        )

        await self.db.commit()
        
        # Notify relevant parties
        await self._notify_override_reversal(override)

        return override

    async def _notify_override_reversal(self, override: AdminOverride) -> None:
        """Notify parties of override reversal."""
        pass

    # ==================== IMPACT ASSESSMENT ====================

    async def update_impact_assessment(
        self,
        override_id: UUID,
        impact_data: Dict[str, Any],
        assessed_by_id: Optional[UUID] = None
    ) -> OverrideImpact:
        """Update or create impact assessment for override."""
        return await self._create_or_update_impact(
            override_id,
            impact_data,
            assessed_by_id
        )

    async def _create_or_update_impact(
        self,
        override_id: UUID,
        impact_data: Dict[str, Any],
        assessed_by_id: Optional[UUID] = None
    ) -> OverrideImpact:
        """Internal method to create or update impact."""
        impact = await self.override_repo.update_impact_assessment(
            override_id=override_id,
            impact_data=impact_data,
            assessed_by_id=assessed_by_id
        )

        await self.db.commit()
        return impact

    async def calculate_financial_impact(
        self,
        override_id: UUID
    ) -> Dict[str, Any]:
        """Calculate detailed financial impact of override."""
        override = await self.override_repo.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        # Extract financial data from actions
        original_amount = Decimal('0.00')
        override_amount = Decimal('0.00')

        if override.original_action and 'amount' in override.original_action:
            original_amount = Decimal(str(override.original_action['amount']))

        if override.override_action and 'amount' in override.override_action:
            override_amount = Decimal(str(override.override_action['amount']))

        impact_amount = override_amount - original_amount

        return {
            'override_id': str(override_id),
            'original_amount': float(original_amount),
            'override_amount': float(override_amount),
            'net_impact': float(impact_amount),
            'impact_type': 'cost' if impact_amount > 0 else 'savings',
            'percentage_change': (
                float((impact_amount / original_amount) * 100)
                if original_amount != 0 else 0
            )
        }

    # ==================== PATTERN ANALYSIS ====================

    async def analyze_override_patterns(
        self,
        pattern_type: str = 'type',
        days: int = 90,
        min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """Analyze override patterns for policy improvement."""
        return await self.override_repo.find_pattern_overrides(
            pattern_type=pattern_type,
            days=days,
            min_occurrences=min_occurrences
        )

    async def get_override_statistics(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive override statistics."""
        return await self.override_repo.get_override_statistics(
            admin_id=admin_id,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )

    async def identify_policy_gaps(
        self,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """Identify policy gaps based on override patterns."""
        patterns = await self.analyze_override_patterns(
            pattern_type='type',
            days=days,
            min_occurrences=5
        )

        policy_gaps = []

        for pattern in patterns:
            if pattern['occurrence_count'] >= 10:
                gap = {
                    'pattern': pattern['pattern'],
                    'frequency': pattern['occurrence_count'],
                    'avg_impact': pattern['avg_impact_score'],
                    'recommendation': self._generate_policy_recommendation(pattern),
                    'priority': self._calculate_gap_priority(pattern)
                }
                policy_gaps.append(gap)

        # Sort by priority
        policy_gaps.sort(key=lambda x: x['priority'], reverse=True)

        return policy_gaps

    def _generate_policy_recommendation(
        self,
        pattern: Dict[str, Any]
    ) -> str:
        """Generate policy recommendation based on pattern."""
        pattern_type = pattern['pattern']
        frequency = pattern['occurrence_count']
        
        if frequency >= 20:
            return f"Consider updating policy to eliminate need for '{pattern_type}' overrides"
        elif frequency >= 10:
            return f"Review guidelines for '{pattern_type}' situations"
        else:
            return f"Monitor '{pattern_type}' pattern for trends"

    def _calculate_gap_priority(self, pattern: Dict[str, Any]) -> int:
        """Calculate priority score for policy gap (0-100)."""
        frequency_score = min(pattern['occurrence_count'] * 2, 50)
        impact_score = min(pattern.get('avg_impact_score', 0) / 2, 50)
        
        return int(frequency_score + impact_score)

    # ==================== COMPLIANCE & REPORTING ====================

    async def generate_compliance_report(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Generate compliance report for overrides."""
        stats = await self.get_override_statistics(
            hostel_id=hostel_id,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time())
        )

        # Get approval compliance
        pending = await self.get_pending_approvals(hostel_id=hostel_id)
        
        # Calculate compliance metrics
        total_overrides = stats['total_overrides']
        approval_required = stats.get('approval_required_count', 0)
        
        if approval_required > 0:
            approval_rate = (
                (approval_required - len(pending)) / approval_required * 100
            )
        else:
            approval_rate = 100

        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'hostel_id': str(hostel_id) if hostel_id else 'all',
            'total_overrides': total_overrides,
            'approval_required': approval_required,
            'pending_approvals': len(pending),
            'approval_compliance_rate': round(approval_rate, 2),
            'reversal_rate': stats.get('reversal_rate_percentage', 0),
            'by_severity': stats.get('by_severity', {}),
            'avg_impact_score': stats.get('avg_impact_score', 0),
            'compliance_status': 'compliant' if approval_rate >= 95 else 'non_compliant'
        }

    async def get_override_audit_trail(
        self,
        override_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get complete audit trail for override."""
        override = await self.override_repo.find_by_id(override_id)
        if not override:
            raise EntityNotFoundError(f"Override {override_id} not found")

        audit_trail = []

        # Override creation
        audit_trail.append({
            'timestamp': override.override_timestamp,
            'action': 'created',
            'actor_id': str(override.admin_id),
            'details': {
                'override_type': override.override_type,
                'severity': override.severity,
                'reason': override.reason
            }
        })

        # Approval events
        if override.requires_approval:
            from sqlalchemy import select
            
            stmt = (
                select(OverrideApproval)
                .where(OverrideApproval.override_id == override_id)
                .order_by(OverrideApproval.created_at)
            )
            result = await self.db.execute(stmt)
            approvals = result.scalars().all()

            for approval in approvals:
                if approval.decision_timestamp:
                    audit_trail.append({
                        'timestamp': approval.decision_timestamp,
                        'action': approval.approval_status,
                        'actor_id': str(approval.approver_id),
                        'details': {
                            'decision_notes': approval.decision_notes,
                            'escalation_level': approval.escalation_level
                        }
                    })

        # Reversal
        if override.is_reversed:
            audit_trail.append({
                'timestamp': override.reversed_at,
                'action': 'reversed',
                'actor_id': str(override.reversed_by_id),
                'details': {
                    'reversal_reason': override.reversal_reason
                }
            })

        # Sort by timestamp
        audit_trail.sort(key=lambda x: x['timestamp'])

        return audit_trail