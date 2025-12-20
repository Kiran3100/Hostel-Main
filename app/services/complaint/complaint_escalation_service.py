"""
Complaint escalation service with auto-escalation and chain management.

Handles manual and automatic escalation, escalation rules,
and escalation chain workflow management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.base.enums import Priority
from app.models.complaint.complaint import Complaint
from app.models.complaint.complaint_escalation import (
    ComplaintEscalation,
    AutoEscalationRule,
)
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_escalation_repository import (
    ComplaintEscalationRepository,
    AutoEscalationRuleRepository,
)
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintEscalationService:
    """
    Complaint escalation service with intelligent escalation management.
    
    Handles escalation workflow, auto-escalation processing,
    and escalation chain management for effective resolution.
    """

    def __init__(self, session: Session):
        """
        Initialize escalation service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.escalation_repo = ComplaintEscalationRepository(session)
        self.rule_repo = AutoEscalationRuleRepository(session)

    # ==================== Manual Escalation ====================

    def create_escalation(
        self,
        complaint_id: str,
        escalated_to: str,
        escalated_by: str,
        escalation_reason: str,
        is_urgent: bool = False,
        escalation_level: Optional[int] = None,
    ) -> ComplaintEscalation:
        """
        Create a manual escalation.
        
        Args:
            complaint_id: Complaint identifier
            escalated_to: User to escalate to
            escalated_by: User escalating
            escalation_reason: Reason for escalation
            is_urgent: Urgent flag
            escalation_level: Escalation level (auto-determined if None)
            
        Returns:
            Created escalation instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If escalation data invalid
            BusinessLogicError: If escalation not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        if not escalation_reason or not escalation_reason.strip():
            raise ValidationError("Escalation reason is required")
        
        # Check escalation eligibility
        eligible, reason = self.escalation_repo.check_escalation_eligibility(complaint_id)
        if not eligible:
            raise BusinessLogicError(f"Cannot escalate: {reason}")
        
        # Determine escalation level
        if escalation_level is None:
            escalation_level = self.escalation_repo.get_next_escalation_level(complaint_id)
        
        # Get current status and priority
        status_before = complaint.status.value
        priority_before = complaint.priority.value
        
        # Increase priority if urgent
        priority_after = priority_before
        if is_urgent:
            priority_after = self._increase_priority(complaint.priority).value
        
        # Create escalation record
        escalation = self.escalation_repo.create_escalation(
            complaint_id=complaint_id,
            escalated_to=escalated_to,
            escalated_by=escalated_by,
            escalation_reason=escalation_reason,
            escalation_level=escalation_level,
            is_urgent=is_urgent,
            status_before=status_before,
            priority_before=priority_before,
            priority_after=priority_after,
            auto_escalated=False,
        )
        
        # Update complaint
        self.complaint_repo.escalate_complaint(
            complaint_id=complaint_id,
            escalated_to=escalated_to,
            escalated_by=escalated_by,
            escalation_reason=escalation_reason,
            new_priority=Priority[priority_after] if priority_after != priority_before else None,
        )
        
        self.session.commit()
        self.session.refresh(escalation)
        
        # Send escalation notification
        self._send_escalation_notification(escalation)
        
        return escalation

    def respond_to_escalation(
        self,
        escalation_id: str,
        responded_by: str,
        response_notes: str,
    ) -> ComplaintEscalation:
        """
        Record response to an escalation.
        
        Args:
            escalation_id: Escalation identifier
            responded_by: User responding
            response_notes: Response details
            
        Returns:
            Updated escalation
            
        Raises:
            NotFoundError: If escalation not found
            ValidationError: If response data invalid
        """
        escalation = self.escalation_repo.find_by_id(escalation_id)
        if not escalation:
            raise NotFoundError(f"Escalation {escalation_id} not found")
        
        if not response_notes or not response_notes.strip():
            raise ValidationError("Response notes are required")
        
        updated = self.escalation_repo.respond_to_escalation(
            escalation_id=escalation_id,
            responded_by=responded_by,
            response_notes=response_notes,
        )
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    def resolve_escalation(
        self,
        escalation_id: str,
        resolved_after_escalation: bool = True,
    ) -> ComplaintEscalation:
        """
        Mark escalation as resolved.
        
        Args:
            escalation_id: Escalation identifier
            resolved_after_escalation: Complaint resolved flag
            
        Returns:
            Updated escalation
            
        Raises:
            NotFoundError: If escalation not found
        """
        escalation = self.escalation_repo.find_by_id(escalation_id)
        if not escalation:
            raise NotFoundError(f"Escalation {escalation_id} not found")
        
        updated = self.escalation_repo.mark_escalation_resolved(
            escalation_id=escalation_id,
            resolved_after_escalation=resolved_after_escalation,
        )
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    # ==================== Auto-Escalation ====================

    def auto_escalate_on_sla_breach(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintEscalation]:
        """
        Auto-escalate complaint on SLA breach.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Created escalation or None
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Find applicable rule
        rule = self.rule_repo.find_applicable_rule(
            hostel_id=complaint.hostel_id,
            complaint_priority=complaint.priority.value,
            complaint_age_hours=complaint.age_hours,
            sla_breached=True,
        )
        
        if not rule:
            return None
        
        # Determine escalation target
        next_level = self.escalation_repo.get_next_escalation_level(complaint_id)
        escalation_target = self.rule_repo.get_escalation_targets(
            rule_id=rule.id,
            level=next_level,
        )
        
        if not escalation_target:
            return None
        
        # Create auto-escalation
        escalation = self.escalation_repo.create_escalation(
            complaint_id=complaint_id,
            escalated_to=escalation_target,
            escalated_by="SYSTEM",
            escalation_reason=f"Auto-escalated due to SLA breach (Rule: {rule.rule_name})",
            escalation_level=next_level,
            is_urgent=True,
            status_before=complaint.status.value,
            priority_before=complaint.priority.value,
            priority_after=self._increase_priority(complaint.priority).value,
            auto_escalated=True,
            auto_escalation_rule_id=rule.id,
        )
        
        # Update complaint
        self.complaint_repo.escalate_complaint(
            complaint_id=complaint_id,
            escalated_to=escalation_target,
            escalated_by="SYSTEM",
            escalation_reason="Auto-escalated on SLA breach",
            new_priority=self._increase_priority(complaint.priority),
        )
        
        self.session.commit()
        self.session.refresh(escalation)
        
        return escalation

    def process_auto_escalations(
        self,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Process auto-escalation for eligible complaints.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Processing summary
        """
        # Get active complaints
        complaints = self.complaint_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=None,
            limit=10000,
        )
        
        escalated_count = 0
        eligible_count = 0
        
        for complaint in complaints:
            # Skip if already resolved/closed
            from app.models.base.enums import ComplaintStatus
            if complaint.status in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
                continue
            
            # Skip if already escalated recently
            if complaint.escalated:
                # Could add logic to check if enough time has passed
                continue
            
            # Check if complaint age exceeds threshold
            rule = self.rule_repo.find_applicable_rule(
                hostel_id=complaint.hostel_id,
                complaint_priority=complaint.priority.value,
                complaint_age_hours=complaint.age_hours,
                sla_breached=complaint.sla_breach,
            )
            
            if rule:
                eligible_count += 1
                
                # Perform auto-escalation
                escalation = self.auto_escalate_on_sla_breach(complaint.id)
                if escalation:
                    escalated_count += 1
        
        return {
            "processed": len(complaints),
            "eligible": eligible_count,
            "escalated": escalated_count,
        }

    # ==================== Query Operations ====================

    def get_escalation(
        self,
        escalation_id: str,
    ) -> Optional[ComplaintEscalation]:
        """
        Get escalation by ID.
        
        Args:
            escalation_id: Escalation identifier
            
        Returns:
            Escalation instance or None
        """
        return self.escalation_repo.find_by_id(escalation_id)

    def get_complaint_escalations(
        self,
        complaint_id: str,
    ) -> List[ComplaintEscalation]:
        """
        Get all escalations for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            List of escalations
        """
        return self.escalation_repo.find_by_complaint(complaint_id)

    def get_escalation_chain(
        self,
        complaint_id: str,
    ) -> List[ComplaintEscalation]:
        """
        Get complete escalation chain.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Escalation chain ordered by level
        """
        return self.escalation_repo.get_escalation_chain(complaint_id)

    def get_user_escalations(
        self,
        user_id: str,
        responded: Optional[bool] = None,
        resolved: Optional[bool] = None,
        is_urgent: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Get escalations for a user.
        
        Args:
            user_id: User identifier
            responded: Filter by response status
            resolved: Filter by resolution status
            is_urgent: Filter by urgency
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of escalations
        """
        return self.escalation_repo.find_by_escalated_user(
            user_id=user_id,
            responded=responded,
            resolved=resolved,
            is_urgent=is_urgent,
            skip=skip,
            limit=limit,
        )

    def get_pending_escalations(
        self,
        user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        is_urgent: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Get pending (not responded) escalations.
        
        Args:
            user_id: Optional user filter
            hostel_id: Optional hostel filter
            is_urgent: Optional urgency filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of pending escalations
        """
        return self.escalation_repo.find_pending_escalations(
            user_id=user_id,
            hostel_id=hostel_id,
            is_urgent=is_urgent,
            skip=skip,
            limit=limit,
        )

    # ==================== Analytics ====================

    def get_escalation_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get escalation statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Escalation statistics
        """
        return self.escalation_repo.get_escalation_statistics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_user_escalation_performance(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get escalation performance for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Performance metrics
        """
        return self.escalation_repo.get_user_escalation_performance(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_escalation_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get escalation trends over time.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Daily escalation metrics
        """
        return self.escalation_repo.get_escalation_trends(
            hostel_id=hostel_id,
            days=days,
        )

    # ==================== Auto-Escalation Rules ====================

    def create_auto_escalation_rule(
        self,
        hostel_id: str,
        rule_name: str,
        first_escalation_to: str,
        escalate_after_hours: int = 24,
        escalate_on_sla_breach: bool = True,
        urgent_escalation_hours: int = 4,
        high_escalation_hours: int = 12,
        medium_escalation_hours: int = 24,
        low_escalation_hours: int = 48,
        second_escalation_to: Optional[str] = None,
        third_escalation_to: Optional[str] = None,
        priority: int = 100,
        is_active: bool = True,
    ) -> AutoEscalationRule:
        """
        Create auto-escalation rule.
        
        Args:
            hostel_id: Hostel identifier
            rule_name: Rule name
            first_escalation_to: First level target
            escalate_after_hours: Default threshold
            escalate_on_sla_breach: Auto-escalate on breach
            urgent_escalation_hours: Urgent threshold
            high_escalation_hours: High priority threshold
            medium_escalation_hours: Medium threshold
            low_escalation_hours: Low threshold
            second_escalation_to: Second level target
            third_escalation_to: Third level target
            priority: Rule priority
            is_active: Active status
            
        Returns:
            Created rule
            
        Raises:
            ValidationError: If rule data invalid
        """
        if not rule_name or not rule_name.strip():
            raise ValidationError("Rule name is required")
        
        if urgent_escalation_hours >= high_escalation_hours:
            raise ValidationError("Urgent threshold must be less than high threshold")
        
        rule = self.rule_repo.create_rule(
            hostel_id=hostel_id,
            rule_name=rule_name,
            first_escalation_to=first_escalation_to,
            escalate_after_hours=escalate_after_hours,
            escalate_on_sla_breach=escalate_on_sla_breach,
            urgent_escalation_hours=urgent_escalation_hours,
            high_escalation_hours=high_escalation_hours,
            medium_escalation_hours=medium_escalation_hours,
            low_escalation_hours=low_escalation_hours,
            second_escalation_to=second_escalation_to,
            third_escalation_to=third_escalation_to,
            priority=priority,
            is_active=is_active,
        )
        
        self.session.commit()
        self.session.refresh(rule)
        
        return rule

    def get_auto_escalation_rules(
        self,
        hostel_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[AutoEscalationRule]:
        """
        Get auto-escalation rules.
        
        Args:
            hostel_id: Optional hostel filter
            active_only: Only active rules
            
        Returns:
            List of rules
        """
        if active_only:
            return self.rule_repo.find_active_rules(hostel_id=hostel_id)
        
        return self.rule_repo.find_by_hostel(hostel_id=hostel_id, active_only=False)

    def activate_rule(
        self,
        rule_id: str,
    ) -> AutoEscalationRule:
        """
        Activate auto-escalation rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Updated rule
            
        Raises:
            NotFoundError: If rule not found
        """
        rule = self.rule_repo.activate_rule(rule_id)
        if not rule:
            raise NotFoundError(f"Rule {rule_id} not found")
        
        self.session.commit()
        self.session.refresh(rule)
        
        return rule

    def deactivate_rule(
        self,
        rule_id: str,
    ) -> AutoEscalationRule:
        """
        Deactivate auto-escalation rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Updated rule
            
        Raises:
            NotFoundError: If rule not found
        """
        rule = self.rule_repo.deactivate_rule(rule_id)
        if not rule:
            raise NotFoundError(f"Rule {rule_id} not found")
        
        self.session.commit()
        self.session.refresh(rule)
        
        return rule

    def determine_escalation_target(
        self,
        complaint_id: str,
        hostel_id: str,
    ) -> Optional[str]:
        """
        Determine escalation target based on rules.
        
        Args:
            complaint_id: Complaint identifier
            hostel_id: Hostel identifier
            
        Returns:
            Target user ID or None
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Get next escalation level
        next_level = self.escalation_repo.get_next_escalation_level(complaint_id)
        
        # Find applicable rule
        rules = self.rule_repo.find_active_rules(hostel_id=hostel_id)
        
        for rule in rules:
            target = self.rule_repo.get_escalation_targets(
                rule_id=rule.id,
                level=next_level,
            )
            if target:
                return target
        
        return None

    # ==================== Helper Methods ====================

    def _increase_priority(self, current_priority: Priority) -> Priority:
        """
        Increase priority by one level.
        
        Args:
            current_priority: Current priority
            
        Returns:
            Increased priority
        """
        priority_order = [
            Priority.LOW,
            Priority.MEDIUM,
            Priority.HIGH,
            Priority.URGENT,
            Priority.CRITICAL,
        ]
        
        try:
            current_index = priority_order.index(current_priority)
            if current_index < len(priority_order) - 1:
                return priority_order[current_index + 1]
        except ValueError:
            pass
        
        return current_priority

    def _send_escalation_notification(
        self,
        escalation: ComplaintEscalation,
    ) -> None:
        """
        Send escalation notification.
        
        Args:
            escalation: Escalation instance
        """
        # Would integrate with notification service
        print(f"Sending escalation notification for escalation {escalation.id}")