"""
SLA (Service Level Agreement) management service for complaints.

Handles SLA calculation, monitoring, breach detection, and automated
escalation based on SLA thresholds.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.base.enums import ComplaintStatus, Priority
from app.models.complaint.complaint import Complaint
from app.repositories.complaint.complaint_repository import ComplaintRepository


class ComplaintSLAService:
    """
    SLA management service for complaint resolution tracking.
    
    Monitors SLA compliance, detects breaches, and triggers
    automated escalation when thresholds are exceeded.
    """

    # SLA hours configuration by priority
    SLA_HOURS = {
        Priority.CRITICAL: 4,
        Priority.URGENT: 8,
        Priority.HIGH: 24,
        Priority.MEDIUM: 48,
        Priority.LOW: 72,
    }
    
    # Warning threshold (percentage of SLA time remaining)
    WARNING_THRESHOLD = 0.2  # 20% time remaining

    def __init__(self, session: Session):
        """
        Initialize SLA service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)

    # ==================== SLA Calculation ====================

    def calculate_sla_due_date(
        self,
        priority: Priority,
        start_time: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate SLA due date based on priority.
        
        Args:
            priority: Complaint priority
            start_time: Start timestamp (defaults to now)
            
        Returns:
            SLA due datetime
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        
        sla_hours = self.SLA_HOURS.get(priority, 48)
        return start_time + timedelta(hours=sla_hours)

    def recalculate_sla(
        self,
        complaint_id: str,
        new_priority: Priority,
    ) -> Optional[Complaint]:
        """
        Recalculate SLA due date when priority changes.
        
        Args:
            complaint_id: Complaint identifier
            new_priority: New priority level
            
        Returns:
            Updated complaint or None
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Only recalculate if not already breached and still active
        if complaint.sla_breach or complaint.status in [
            ComplaintStatus.RESOLVED,
            ComplaintStatus.CLOSED,
        ]:
            return complaint
        
        # Calculate new SLA due date from current time
        new_sla_due = self.calculate_sla_due_date(new_priority)
        
        update_data = {
            "sla_due_at": new_sla_due,
            "priority": new_priority,
        }
        
        updated_complaint = self.complaint_repo.update(complaint_id, update_data)
        self.session.commit()
        
        return updated_complaint

    def get_remaining_sla_time(
        self,
        complaint: Complaint,
    ) -> Optional[timedelta]:
        """
        Calculate remaining SLA time.
        
        Args:
            complaint: Complaint instance
            
        Returns:
            Remaining time or None if no SLA
        """
        if not complaint.sla_due_at:
            return None
        
        now = datetime.now(timezone.utc)
        remaining = complaint.sla_due_at - now
        
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def get_sla_status(
        self,
        complaint: Complaint,
    ) -> Dict[str, Any]:
        """
        Get comprehensive SLA status.
        
        Args:
            complaint: Complaint instance
            
        Returns:
            SLA status dictionary
        """
        if not complaint.sla_due_at:
            return {
                "has_sla": False,
                "status": "NO_SLA",
            }
        
        now = datetime.now(timezone.utc)
        remaining = self.get_remaining_sla_time(complaint)
        
        if complaint.sla_breach:
            breach_hours = (now - complaint.sla_due_at).total_seconds() / 3600
            return {
                "has_sla": True,
                "status": "BREACHED",
                "sla_due_at": complaint.sla_due_at,
                "breach_hours": round(breach_hours, 2),
                "breach_reason": complaint.sla_breach_reason,
            }
        
        if remaining and remaining.total_seconds() <= 0:
            return {
                "has_sla": True,
                "status": "OVERDUE",
                "sla_due_at": complaint.sla_due_at,
                "overdue_hours": round(abs(remaining.total_seconds() / 3600), 2),
            }
        
        # Calculate percentage remaining
        total_sla_hours = self.SLA_HOURS.get(complaint.priority, 48)
        total_seconds = total_sla_hours * 3600
        remaining_seconds = remaining.total_seconds() if remaining else 0
        percentage_remaining = (remaining_seconds / total_seconds) * 100
        
        # Determine status based on remaining time
        if percentage_remaining <= (self.WARNING_THRESHOLD * 100):
            status = "AT_RISK"
        elif percentage_remaining <= 50:
            status = "ATTENTION_NEEDED"
        else:
            status = "ON_TRACK"
        
        return {
            "has_sla": True,
            "status": status,
            "sla_due_at": complaint.sla_due_at,
            "remaining_hours": round(remaining_seconds / 3600, 2),
            "percentage_remaining": round(percentage_remaining, 2),
        }

    # ==================== SLA Monitoring ====================

    def check_sla_breach(
        self,
        complaint_id: str,
        breach_reason: Optional[str] = None,
    ) -> Optional[Complaint]:
        """
        Check and mark SLA breach if applicable.
        
        Args:
            complaint_id: Complaint identifier
            breach_reason: Optional breach reason
            
        Returns:
            Updated complaint or None
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Skip if already breached or resolved
        if complaint.sla_breach or complaint.status in [
            ComplaintStatus.RESOLVED,
            ComplaintStatus.CLOSED,
        ]:
            return complaint
        
        # Check if SLA is breached
        if not complaint.sla_due_at:
            return complaint
        
        now = datetime.now(timezone.utc)
        if now <= complaint.sla_due_at:
            return complaint
        
        # Mark as breached
        default_reason = f"SLA exceeded by {round((now - complaint.sla_due_at).total_seconds() / 3600, 2)} hours"
        
        updated_complaint = self.complaint_repo.mark_sla_breach(
            complaint_id=complaint_id,
            breach_reason=breach_reason or default_reason,
        )
        
        self.session.commit()
        
        # Trigger auto-escalation if configured
        self._trigger_sla_breach_escalation(updated_complaint)
        
        return updated_complaint

    def find_sla_at_risk(
        self,
        hostel_id: Optional[str] = None,
        hours_threshold: int = 2,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints at risk of SLA breach.
        
        Args:
            hostel_id: Optional hostel filter
            hours_threshold: Hours before breach
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of at-risk complaints
        """
        return self.complaint_repo.find_sla_at_risk(
            hostel_id=hostel_id,
            hours_threshold=hours_threshold,
            skip=skip,
            limit=limit,
        )

    def get_sla_breach_summary(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get SLA breach summary statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            SLA breach summary
        """
        stats = self.complaint_repo.get_complaint_statistics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )
        
        total = stats.get("total_complaints", 0)
        breached = stats.get("sla_breach_count", 0)
        compliance_rate = stats.get("sla_compliance_rate", 0)
        
        # Get at-risk count
        at_risk = self.find_sla_at_risk(hostel_id=hostel_id, limit=1000)
        
        return {
            "total_complaints": total,
            "sla_breached_count": breached,
            "sla_compliant_count": total - breached,
            "sla_compliance_rate": compliance_rate,
            "at_risk_count": len(at_risk),
            "breach_rate": round((breached / total * 100), 2) if total > 0 else 0,
        }

    # ==================== Batch Processing ====================

    def process_sla_monitoring(
        self,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Batch process SLA monitoring for all active complaints.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Processing summary
        """
        # Find all active complaints
        active_complaints = self.complaint_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=None,  # Will filter in loop
            limit=10000,  # Process in batches
        )
        
        breached_count = 0
        escalated_count = 0
        
        for complaint in active_complaints:
            # Skip if already resolved/closed
            if complaint.status in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
                continue
            
            # Skip if already breached
            if complaint.sla_breach:
                continue
            
            # Check for breach
            if complaint.sla_due_at and datetime.now(timezone.utc) > complaint.sla_due_at:
                self.check_sla_breach(complaint.id)
                breached_count += 1
        
        return {
            "processed": len(active_complaints),
            "newly_breached": breached_count,
            "escalated": escalated_count,
        }

    # ==================== Helper Methods ====================

    def _trigger_sla_breach_escalation(
        self,
        complaint: Complaint,
    ) -> None:
        """
        Trigger auto-escalation on SLA breach.
        
        Args:
            complaint: Complaint instance
        """
        try:
            from app.services.complaint.complaint_escalation_service import (
                ComplaintEscalationService,
            )
            
            escalation_service = ComplaintEscalationService(self.session)
            escalation_service.auto_escalate_on_sla_breach(complaint.id)
        except Exception as e:
            print(f"Auto-escalation failed for complaint {complaint.id}: {str(e)}")

    def extend_sla(
        self,
        complaint_id: str,
        extension_hours: int,
        extension_reason: str,
        extended_by: str,
    ) -> Optional[Complaint]:
        """
        Extend SLA deadline (admin override).
        
        Args:
            complaint_id: Complaint identifier
            extension_hours: Hours to extend
            extension_reason: Reason for extension
            extended_by: User extending SLA
            
        Returns:
            Updated complaint or None
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint or not complaint.sla_due_at:
            return None
        
        new_sla_due = complaint.sla_due_at + timedelta(hours=extension_hours)
        
        # Update metadata with extension info
        metadata = complaint.metadata or {}
        extensions = metadata.get("sla_extensions", [])
        extensions.append({
            "extended_by": extended_by,
            "extension_hours": extension_hours,
            "extension_reason": extension_reason,
            "extended_at": datetime.now(timezone.utc).isoformat(),
            "old_sla_due": complaint.sla_due_at.isoformat(),
            "new_sla_due": new_sla_due.isoformat(),
        })
        metadata["sla_extensions"] = extensions
        
        update_data = {
            "sla_due_at": new_sla_due,
            "metadata": metadata,
        }
        
        # If previously breached, might want to clear breach
        if complaint.sla_breach and datetime.now(timezone.utc) < new_sla_due:
            update_data["sla_breach"] = False
            update_data["sla_breach_reason"] = None
        
        updated_complaint = self.complaint_repo.update(complaint_id, update_data)
        self.session.commit()
        
        return updated_complaint