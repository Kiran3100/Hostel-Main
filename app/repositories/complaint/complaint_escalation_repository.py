# --- File: complaint_escalation_repository.py ---
"""
Complaint escalation repository with auto-escalation and escalation chain management.

Handles escalation tracking, auto-escalation rules, and escalation performance
analytics for complaint resolution optimization.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_escalation import (
    ComplaintEscalation,
    AutoEscalationRule,
)
from app.models.complaint.complaint import Complaint
from app.models.base.enums import ComplaintStatus, Priority
from app.repositories.base.base_repository import BaseRepository


class ComplaintEscalationRepository(BaseRepository[ComplaintEscalation]):
    """
    Complaint escalation repository with intelligent escalation management.
    
    Provides escalation tracking, auto-escalation processing, and performance
    analytics for effective complaint resolution.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint escalation repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintEscalation, session)

    # ==================== CRUD Operations ====================

    def create_escalation(
        self,
        complaint_id: str,
        escalated_to: str,
        escalated_by: str,
        escalation_reason: str,
        escalation_level: int = 1,
        is_urgent: bool = False,
        status_before: str = None,
        priority_before: str = None,
        priority_after: str = None,
        auto_escalated: bool = False,
        auto_escalation_rule_id: Optional[str] = None,
    ) -> ComplaintEscalation:
        """
        Create a new escalation record.
        
        Args:
            complaint_id: Complaint identifier
            escalated_to: User to escalate to
            escalated_by: User performing escalation
            escalation_reason: Reason for escalation
            escalation_level: Escalation level (1, 2, 3, etc.)
            is_urgent: Urgent flag
            status_before: Status before escalation
            priority_before: Priority before escalation
            priority_after: Priority after escalation
            auto_escalated: Auto-escalation flag
            auto_escalation_rule_id: Auto-escalation rule ID
            
        Returns:
            Created escalation instance
        """
        escalation = ComplaintEscalation(
            complaint_id=complaint_id,
            escalated_to=escalated_to,
            escalated_by=escalated_by,
            escalated_at=datetime.now(timezone.utc),
            escalation_level=escalation_level,
            escalation_reason=escalation_reason,
            is_urgent=is_urgent,
            status_before=status_before or ComplaintStatus.OPEN.value,
            priority_before=priority_before or Priority.MEDIUM.value,
            priority_after=priority_after or priority_before or Priority.HIGH.value,
            auto_escalated=auto_escalated,
            auto_escalation_rule_id=auto_escalation_rule_id,
        )
        
        return self.create(escalation)

    def respond_to_escalation(
        self,
        escalation_id: str,
        responded_by: str,
        response_notes: str,
    ) -> Optional[ComplaintEscalation]:
        """
        Record response to an escalation.
        
        Args:
            escalation_id: Escalation identifier
            responded_by: User responding
            response_notes: Response details
            
        Returns:
            Updated escalation or None
        """
        escalation = self.find_by_id(escalation_id)
        if not escalation:
            return None
        
        now = datetime.now(timezone.utc)
        
        # Calculate resolution time
        time_delta = now - escalation.escalated_at
        resolution_hours = int(time_delta.total_seconds() / 3600)
        
        update_data = {
            "responded_at": now,
            "responded_by": responded_by,
            "response_notes": response_notes,
            "resolution_time_hours": resolution_hours,
        }
        
        return self.update(escalation_id, update_data)

    def mark_escalation_resolved(
        self,
        escalation_id: str,
        resolved_after_escalation: bool = True,
    ) -> Optional[ComplaintEscalation]:
        """
        Mark escalation as resolved.
        
        Args:
            escalation_id: Escalation identifier
            resolved_after_escalation: Whether complaint was resolved
            
        Returns:
            Updated escalation or None
        """
        update_data = {
            "resolved_at": datetime.now(timezone.utc),
            "resolved_after_escalation": resolved_after_escalation,
        }
        
        return self.update(escalation_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint(
        self,
        complaint_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Find all escalations for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of escalations
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.complaint_id == complaint_id
        )
        
        query = query.order_by(desc(ComplaintEscalation.escalated_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_escalated_user(
        self,
        user_id: str,
        responded: Optional[bool] = None,
        resolved: Optional[bool] = None,
        is_urgent: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Find escalations assigned to a user.
        
        Args:
            user_id: User identifier
            responded: Filter by response status
            resolved: Filter by resolution status
            is_urgent: Filter by urgency
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of escalations
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.escalated_to == user_id
        )
        
        if responded is not None:
            if responded:
                query = query.where(ComplaintEscalation.responded_at.isnot(None))
            else:
                query = query.where(ComplaintEscalation.responded_at.is_(None))
        
        if resolved is not None:
            if resolved:
                query = query.where(ComplaintEscalation.resolved_at.isnot(None))
            else:
                query = query.where(ComplaintEscalation.resolved_at.is_(None))
        
        if is_urgent is not None:
            query = query.where(ComplaintEscalation.is_urgent == is_urgent)
        
        if date_from:
            query = query.where(ComplaintEscalation.escalated_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintEscalation.escalated_at <= date_to)
        
        query = query.order_by(desc(ComplaintEscalation.escalated_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_pending_escalations(
        self,
        user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        is_urgent: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Find pending (not responded) escalations.
        
        Args:
            user_id: Optional user filter
            hostel_id: Optional hostel filter
            is_urgent: Optional urgency filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of pending escalations
        """
        query = (
            select(ComplaintEscalation)
            .where(ComplaintEscalation.responded_at.is_(None))
        )
        
        if user_id:
            query = query.where(ComplaintEscalation.escalated_to == user_id)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if is_urgent is not None:
            query = query.where(ComplaintEscalation.is_urgent == is_urgent)
        
        query = query.order_by(
            desc(ComplaintEscalation.is_urgent),
            ComplaintEscalation.escalated_at.asc(),
        )
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_auto_escalations(
        self,
        hostel_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Find auto-generated escalations.
        
        Args:
            hostel_id: Optional hostel filter
            rule_id: Optional rule filter
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of auto-escalations
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.auto_escalated == True
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if rule_id:
            query = query.where(ComplaintEscalation.auto_escalation_rule_id == rule_id)
        
        if date_from:
            query = query.where(ComplaintEscalation.escalated_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintEscalation.escalated_at <= date_to)
        
        query = query.order_by(desc(ComplaintEscalation.escalated_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_level(
        self,
        escalation_level: int,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintEscalation]:
        """
        Find escalations by level.
        
        Args:
            escalation_level: Escalation level
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of escalations at specified level
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.escalation_level == escalation_level
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(desc(ComplaintEscalation.escalated_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Escalation Analytics ====================

    def get_escalation_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive escalation statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with escalation statistics
        """
        query = select(ComplaintEscalation)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintEscalation.escalated_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintEscalation.escalated_at <= date_to)
        
        result = self.session.execute(query)
        escalations = list(result.scalars().all())
        
        if not escalations:
            return {
                "total_escalations": 0,
                "auto_escalations": 0,
                "manual_escalations": 0,
                "urgent_escalations": 0,
                "average_response_time_hours": None,
                "pending_escalations": 0,
                "resolved_after_escalation": 0,
            }
        
        total = len(escalations)
        auto = len([e for e in escalations if e.auto_escalated])
        manual = total - auto
        urgent = len([e for e in escalations if e.is_urgent])
        pending = len([e for e in escalations if e.responded_at is None])
        resolved = len([e for e in escalations if e.resolved_after_escalation])
        
        # Calculate average response time
        responded = [e for e in escalations if e.resolution_time_hours is not None]
        avg_response = (
            sum(e.resolution_time_hours for e in responded) / len(responded)
            if responded else None
        )
        
        # Level breakdown
        level_breakdown = {}
        for e in escalations:
            level = e.escalation_level
            level_breakdown[level] = level_breakdown.get(level, 0) + 1
        
        return {
            "total_escalations": total,
            "auto_escalations": auto,
            "manual_escalations": manual,
            "urgent_escalations": urgent,
            "average_response_time_hours": avg_response,
            "pending_escalations": pending,
            "resolved_after_escalation": resolved,
            "resolution_rate": (resolved / total * 100) if total > 0 else 0,
            "level_breakdown": level_breakdown,
        }

    def get_user_escalation_performance(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get escalation performance metrics for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with performance metrics
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.escalated_to == user_id
        )
        
        if date_from:
            query = query.where(ComplaintEscalation.escalated_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintEscalation.escalated_at <= date_to)
        
        result = self.session.execute(query)
        escalations = list(result.scalars().all())
        
        if not escalations:
            return {
                "user_id": user_id,
                "total_escalations": 0,
                "responded_count": 0,
                "pending_count": 0,
                "average_response_time_hours": None,
                "resolution_rate": 0,
            }
        
        total = len(escalations)
        responded = len([e for e in escalations if e.responded_at is not None])
        pending = total - responded
        resolved = len([e for e in escalations if e.resolved_after_escalation])
        
        # Calculate average response time
        responded_escalations = [
            e for e in escalations
            if e.resolution_time_hours is not None
        ]
        
        avg_response = (
            sum(e.resolution_time_hours for e in responded_escalations) / len(responded_escalations)
            if responded_escalations else None
        )
        
        return {
            "user_id": user_id,
            "total_escalations": total,
            "responded_count": responded,
            "pending_count": pending,
            "average_response_time_hours": avg_response,
            "resolution_rate": (resolved / total * 100) if total > 0 else 0,
            "response_rate": (responded / total * 100) if total > 0 else 0,
        }

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
            List of daily escalation counts
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = (
            select(
                func.date(ComplaintEscalation.escalated_at).label("date"),
                func.count(ComplaintEscalation.id).label("count"),
                func.sum(
                    func.cast(ComplaintEscalation.is_urgent, func.Integer())
                ).label("urgent_count"),
            )
            .where(ComplaintEscalation.escalated_at >= start_date)
            .group_by(func.date(ComplaintEscalation.escalated_at))
            .order_by(func.date(ComplaintEscalation.escalated_at))
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        return [
            {
                "date": row.date.isoformat(),
                "total_escalations": row.count,
                "urgent_escalations": row.urgent_count or 0,
            }
            for row in result
        ]

    # ==================== Escalation Chain Management ====================

    def get_escalation_chain(
        self,
        complaint_id: str,
    ) -> List[ComplaintEscalation]:
        """
        Get complete escalation chain for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            List of escalations ordered by level
        """
        query = (
            select(ComplaintEscalation)
            .where(ComplaintEscalation.complaint_id == complaint_id)
            .order_by(ComplaintEscalation.escalation_level.asc())
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_next_escalation_level(
        self,
        complaint_id: str,
    ) -> int:
        """
        Get next escalation level for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Next escalation level number
        """
        query = (
            select(func.max(ComplaintEscalation.escalation_level))
            .where(ComplaintEscalation.complaint_id == complaint_id)
        )
        
        result = self.session.execute(query)
        max_level = result.scalar_one_or_none()
        
        return (max_level or 0) + 1

    def check_escalation_eligibility(
        self,
        complaint_id: str,
        max_level: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if complaint can be escalated further.
        
        Args:
            complaint_id: Complaint identifier
            max_level: Maximum allowed escalation level
            
        Returns:
            Tuple of (eligible, reason)
        """
        chain = self.get_escalation_chain(complaint_id)
        
        if not chain:
            return True, None
        
        current_level = max(e.escalation_level for e in chain)
        
        if current_level >= max_level:
            return False, f"Maximum escalation level ({max_level}) reached"
        
        # Check if last escalation is pending
        latest = chain[-1]
        if latest.responded_at is None:
            return False, "Previous escalation pending response"
        
        return True, None


class AutoEscalationRuleRepository(BaseRepository[AutoEscalationRule]):
    """
    Auto-escalation rule repository for managing escalation automation.
    
    Provides rule management and auto-escalation processing capabilities.
    """

    def __init__(self, session: Session):
        """
        Initialize auto-escalation rule repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(AutoEscalationRule, session)

    # ==================== CRUD Operations ====================

    def create_rule(
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
        conditions: Optional[Dict[str, Any]] = None,
    ) -> AutoEscalationRule:
        """
        Create a new auto-escalation rule.
        
        Args:
            hostel_id: Hostel identifier
            rule_name: Rule name
            first_escalation_to: First level escalation user
            escalate_after_hours: Default escalation hours
            escalate_on_sla_breach: Auto-escalate on SLA breach
            urgent_escalation_hours: Hours for urgent priority
            high_escalation_hours: Hours for high priority
            medium_escalation_hours: Hours for medium priority
            low_escalation_hours: Hours for low priority
            second_escalation_to: Second level user
            third_escalation_to: Third level user
            priority: Rule priority
            is_active: Active status
            conditions: Additional conditions
            
        Returns:
            Created rule instance
        """
        rule = AutoEscalationRule(
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
            conditions=conditions or {},
        )
        
        return self.create(rule)

    # ==================== Query Operations ====================

    def find_active_rules(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AutoEscalationRule]:
        """
        Find active auto-escalation rules.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of active rules
        """
        query = select(AutoEscalationRule).where(
            AutoEscalationRule.is_active == True
        )
        
        if hostel_id:
            query = query.where(AutoEscalationRule.hostel_id == hostel_id)
        
        query = query.order_by(AutoEscalationRule.priority.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_hostel(
        self,
        hostel_id: str,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AutoEscalationRule]:
        """
        Find rules for a specific hostel.
        
        Args:
            hostel_id: Hostel identifier
            active_only: Only active rules
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of rules
        """
        query = select(AutoEscalationRule).where(
            AutoEscalationRule.hostel_id == hostel_id
        )
        
        if active_only:
            query = query.where(AutoEscalationRule.is_active == True)
        
        query = query.order_by(AutoEscalationRule.priority.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_applicable_rule(
        self,
        hostel_id: str,
        complaint_priority: str,
        complaint_age_hours: int,
        sla_breached: bool = False,
    ) -> Optional[AutoEscalationRule]:
        """
        Find applicable auto-escalation rule for a complaint.
        
        Args:
            hostel_id: Hostel identifier
            complaint_priority: Complaint priority level
            complaint_age_hours: Complaint age in hours
            sla_breached: SLA breach status
            
        Returns:
            Applicable rule or None
        """
        rules = self.find_active_rules(hostel_id)
        
        for rule in rules:
            # Check SLA breach condition
            if sla_breached and rule.escalate_on_sla_breach:
                return rule
            
            # Check age threshold based on priority
            threshold = rule.get_threshold_for_priority(complaint_priority)
            
            if complaint_age_hours >= threshold:
                return rule
        
        return None

    def get_escalation_targets(
        self,
        rule_id: str,
        level: int = 1,
    ) -> Optional[str]:
        """
        Get escalation target user for a specific level.
        
        Args:
            rule_id: Rule identifier
            level: Escalation level
            
        Returns:
            User ID for escalation target or None
        """
        rule = self.find_by_id(rule_id)
        if not rule:
            return None
        
        if level == 1:
            return rule.first_escalation_to
        elif level == 2:
            return rule.second_escalation_to
        elif level == 3:
            return rule.third_escalation_to
        
        return None

    # ==================== Rule Management ====================

    def activate_rule(
        self,
        rule_id: str,
    ) -> Optional[AutoEscalationRule]:
        """
        Activate an auto-escalation rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Updated rule or None
        """
        return self.update(rule_id, {"is_active": True})

    def deactivate_rule(
        self,
        rule_id: str,
    ) -> Optional[AutoEscalationRule]:
        """
        Deactivate an auto-escalation rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Updated rule or None
        """
        return self.update(rule_id, {"is_active": False})

    def update_escalation_targets(
        self,
        rule_id: str,
        first_escalation_to: Optional[str] = None,
        second_escalation_to: Optional[str] = None,
        third_escalation_to: Optional[str] = None,
    ) -> Optional[AutoEscalationRule]:
        """
        Update escalation targets for a rule.
        
        Args:
            rule_id: Rule identifier
            first_escalation_to: First level target
            second_escalation_to: Second level target
            third_escalation_to: Third level target
            
        Returns:
            Updated rule or None
        """
        update_data = {}
        
        if first_escalation_to:
            update_data["first_escalation_to"] = first_escalation_to
        
        if second_escalation_to:
            update_data["second_escalation_to"] = second_escalation_to
        
        if third_escalation_to:
            update_data["third_escalation_to"] = third_escalation_to
        
        if not update_data:
            return None
        
        return self.update(rule_id, update_data)

    def update_thresholds(
        self,
        rule_id: str,
        urgent_hours: Optional[int] = None,
        high_hours: Optional[int] = None,
        medium_hours: Optional[int] = None,
        low_hours: Optional[int] = None,
    ) -> Optional[AutoEscalationRule]:
        """
        Update escalation time thresholds.
        
        Args:
            rule_id: Rule identifier
            urgent_hours: Urgent priority threshold
            high_hours: High priority threshold
            medium_hours: Medium priority threshold
            low_hours: Low priority threshold
            
        Returns:
            Updated rule or None
        """
        update_data = {}
        
        if urgent_hours is not None:
            update_data["urgent_escalation_hours"] = urgent_hours
        
        if high_hours is not None:
            update_data["high_escalation_hours"] = high_hours
        
        if medium_hours is not None:
            update_data["medium_escalation_hours"] = medium_hours
        
        if low_hours is not None:
            update_data["low_escalation_hours"] = low_hours
        
        if not update_data:
            return None
        
        return self.update(rule_id, update_data)

    # ==================== Analytics ====================

    def get_rule_effectiveness(
        self,
        rule_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Analyze effectiveness of an auto-escalation rule.
        
        Args:
            rule_id: Rule identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with effectiveness metrics
        """
        query = select(ComplaintEscalation).where(
            ComplaintEscalation.auto_escalation_rule_id == rule_id
        )
        
        if date_from:
            query = query.where(ComplaintEscalation.escalated_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintEscalation.escalated_at <= date_to)
        
        result = self.session.execute(query)
        escalations = list(result.scalars().all())
        
        if not escalations:
            return {
                "rule_id": rule_id,
                "total_auto_escalations": 0,
                "resolved_count": 0,
                "resolution_rate": 0,
                "average_resolution_time_hours": None,
            }
        
        total = len(escalations)
        resolved = len([e for e in escalations if e.resolved_after_escalation])
        
        # Calculate average resolution time
        resolved_escalations = [
            e for e in escalations
            if e.resolution_time_hours is not None
        ]
        
        avg_resolution = (
            sum(e.resolution_time_hours for e in resolved_escalations) / len(resolved_escalations)
            if resolved_escalations else None
        )
        
        return {
            "rule_id": rule_id,
            "total_auto_escalations": total,
            "resolved_count": resolved,
            "resolution_rate": (resolved / total * 100) if total > 0 else 0,
            "average_resolution_time_hours": avg_resolution,
        }


