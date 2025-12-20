"""
Announcement Approval Service

Approval workflow orchestration service providing multi-level approval,
SLA tracking, auto-approval rules, and complete audit trail.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementApprovalRepository,
    AnnouncementRepository,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
    PermissionError,
)
from app.core.events import EventPublisher
from app.core.notifications import NotificationService


# ==================== DTOs ====================

class RequestApprovalDTO(BaseModel):
    """DTO for requesting approval."""
    approval_reason: Optional[str] = Field(None, max_length=1000)
    is_urgent: bool = False
    preferred_approver_id: Optional[UUID] = None
    auto_publish_on_approval: bool = True
    
    @validator('approval_reason')
    def validate_reason(cls, v, values):
        if values.get('is_urgent') and not v:
            raise ValueError('Approval reason required for urgent requests')
        return v


class ApproveAnnouncementDTO(BaseModel):
    """DTO for approving announcement."""
    approval_notes: Optional[str] = Field(None, max_length=1000)
    auto_publish: Optional[bool] = None


class RejectAnnouncementDTO(BaseModel):
    """DTO for rejecting announcement."""
    rejection_reason: str = Field(..., min_length=10, max_length=1000)
    suggested_modifications: Optional[str] = Field(None, max_length=1000)
    allow_resubmission: bool = True


class ResubmitApprovalDTO(BaseModel):
    """DTO for resubmitting after rejection."""
    changes_made: str = Field(..., min_length=10, max_length=1000)
    new_approval_reason: Optional[str] = Field(None, max_length=1000)


class AssignApproverDTO(BaseModel):
    """DTO for assigning approver."""
    approver_id: UUID


class EscalateApprovalDTO(BaseModel):
    """DTO for escalating approval."""
    escalation_reason: str = Field(..., min_length=10, max_length=500)


class CreateApprovalWorkflowDTO(BaseModel):
    """DTO for creating approval workflow."""
    workflow_name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    steps: List[Dict[str, Any]] = Field(..., min_items=1)
    default_approvers: Optional[List[UUID]] = None
    sla_hours: Optional[int] = Field(None, ge=1, le=168)  # Max 1 week
    escalation_enabled: bool = True
    escalation_after_hours: Optional[int] = Field(None, ge=1, le=72)
    escalation_approvers: Optional[List[UUID]] = None
    auto_approval_enabled: bool = False
    auto_approval_rules: Optional[List[Dict[str, Any]]] = None


class CreateApprovalRuleDTO(BaseModel):
    """DTO for creating auto-approval rule."""
    rule_name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    conditions: List[Dict[str, Any]] = Field(..., min_items=1)
    priority: int = Field(0, ge=0, le=100)


@dataclass
class ServiceResult:
    """Standard service result wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def ok(cls, data: Any = None, **metadata) -> 'ServiceResult':
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, error_code: str = None, **metadata) -> 'ServiceResult':
        return cls(success=False, error=error, error_code=error_code, metadata=metadata)


# ==================== Service ====================

class AnnouncementApprovalService:
    """
    Approval workflow orchestration service.
    
    Provides comprehensive approval management including:
    - Multi-level approval workflows
    - Auto-approval rule evaluation
    - SLA monitoring and enforcement
    - Escalation handling
    - Assignment and routing
    - Complete audit trail
    - Notification to approvers
    - Performance analytics
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None,
        notification_service: Optional[NotificationService] = None
    ):
        self.session = session
        self.repository = AnnouncementApprovalRepository(session)
        self.announcement_repository = AnnouncementRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
        self.notification_service = notification_service or NotificationService()
    
    # ==================== Approval Request Management ====================
    
    def request_approval(
        self,
        announcement_id: UUID,
        dto: RequestApprovalDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Request approval for announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Approval request data
            user_id: User requesting approval
            
        Returns:
            ServiceResult with approval request data
        """
        try:
            # Validate announcement
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if announcement.is_published:
                return ServiceResult.fail(
                    "Cannot request approval for already published announcement",
                    error_code="INVALID_STATE"
                )
            
            # Create approval request
            approval = self.repository.create_approval_request(
                announcement_id=announcement_id,
                requested_by_id=user_id,
                approval_reason=dto.approval_reason,
                is_urgent=dto.is_urgent,
                preferred_approver_id=dto.preferred_approver_id,
                auto_publish=dto.auto_publish_on_approval
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('approval.requested', {
                'approval_id': str(approval.id),
                'announcement_id': str(announcement_id),
                'requested_by': str(user_id),
                'is_urgent': dto.is_urgent,
                'assigned_to': str(approval.assigned_to_id) if approval.assigned_to_id else None,
            })
            
            # Notify assigned approver
            if approval.assigned_to_id:
                self._notify_approver(approval)
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval.id),
                auto_approved=False
            )
            
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ALREADY_EXISTS")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="REQUEST_FAILED")
    
    def approve_announcement(
        self,
        approval_id: UUID,
        dto: ApproveAnnouncementDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Approve announcement.
        
        Args:
            approval_id: Approval request UUID
            dto: Approval data
            user_id: Approver user UUID
            
        Returns:
            ServiceResult with approval data
        """
        try:
            # Approve
            approval = self.repository.approve_announcement(
                approval_id=approval_id,
                approved_by_id=user_id,
                approval_notes=dto.approval_notes,
                auto_publish=dto.auto_publish
            )
            
            self.session.commit()
            
            # Determine if published
            published = (
                dto.auto_publish if dto.auto_publish is not None
                else approval.auto_publish_on_approval
            )
            
            # Publish event
            self.event_publisher.publish('approval.approved', {
                'approval_id': str(approval_id),
                'announcement_id': str(approval.announcement_id),
                'approved_by': str(user_id),
                'auto_published': published,
            })
            
            # Notify requester
            self._notify_requester(approval, 'approved')
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval_id),
                published=published
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="INVALID_STATE")
        except PermissionError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="PERMISSION_DENIED")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="APPROVAL_FAILED")
    
    def reject_announcement(
        self,
        approval_id: UUID,
        dto: RejectAnnouncementDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Reject announcement.
        
        Args:
            approval_id: Approval request UUID
            dto: Rejection data
            user_id: Rejector user UUID
            
        Returns:
            ServiceResult with rejection data
        """
        try:
            approval = self.repository.reject_announcement(
                approval_id=approval_id,
                rejected_by_id=user_id,
                rejection_reason=dto.rejection_reason,
                suggested_modifications=dto.suggested_modifications,
                allow_resubmission=dto.allow_resubmission
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('approval.rejected', {
                'approval_id': str(approval_id),
                'announcement_id': str(approval.announcement_id),
                'rejected_by': str(user_id),
                'allow_resubmission': dto.allow_resubmission,
            })
            
            # Notify requester
            self._notify_requester(approval, 'rejected')
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="INVALID_STATE")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="REJECTION_FAILED")
    
    def resubmit_for_approval(
        self,
        approval_id: UUID,
        dto: ResubmitApprovalDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Resubmit rejected announcement for approval.
        
        Args:
            approval_id: Original approval UUID
            dto: Resubmission data
            user_id: User resubmitting
            
        Returns:
            ServiceResult with updated approval
        """
        try:
            approval = self.repository.resubmit_for_approval(
                approval_id=approval_id,
                resubmitted_by_id=user_id,
                changes_made=dto.changes_made,
                new_approval_reason=dto.new_approval_reason
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('approval.resubmitted', {
                'approval_id': str(approval_id),
                'announcement_id': str(approval.announcement_id),
                'resubmitted_by': str(user_id),
            })
            
            # Notify approver
            if approval.assigned_to_id:
                self._notify_approver(approval)
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except BusinessLogicError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RESUBMISSION_NOT_ALLOWED")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RESUBMIT_FAILED")
    
    # ==================== Assignment and Routing ====================
    
    def assign_to_approver(
        self,
        approval_id: UUID,
        dto: AssignApproverDTO,
        assigned_by_id: UUID
    ) -> ServiceResult:
        """
        Manually assign approval to specific approver.
        
        Args:
            approval_id: Approval UUID
            dto: Assignment data
            assigned_by_id: User making assignment
            
        Returns:
            ServiceResult with updated approval
        """
        try:
            approval = self.repository.assign_to_approver(
                approval_id=approval_id,
                approver_id=dto.approver_id,
                assigned_by_id=assigned_by_id
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('approval.assigned', {
                'approval_id': str(approval_id),
                'assigned_to': str(dto.approver_id),
                'assigned_by': str(assigned_by_id),
            })
            
            # Notify approver
            self._notify_approver(approval)
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ASSIGNMENT_FAILED")
    
    def escalate_approval(
        self,
        approval_id: UUID,
        dto: EscalateApprovalDTO,
        escalated_by_id: Optional[UUID] = None
    ) -> ServiceResult:
        """
        Escalate approval request.
        
        Args:
            approval_id: Approval UUID
            dto: Escalation data
            escalated_by_id: User escalating (None for auto-escalation)
            
        Returns:
            ServiceResult with escalated approval
        """
        try:
            approval = self.repository.escalate_approval(
                approval_id=approval_id,
                escalation_reason=dto.escalation_reason,
                escalated_by_id=escalated_by_id
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('approval.escalated', {
                'approval_id': str(approval_id),
                'escalated_by': str(escalated_by_id) if escalated_by_id else 'system',
                'reason': dto.escalation_reason,
                'assigned_to': str(approval.assigned_to_id) if approval.assigned_to_id else None,
            })
            
            # Notify escalation approver
            if approval.assigned_to_id:
                self._notify_approver(approval, is_escalation=True)
            
            return ServiceResult.ok(
                data=self._serialize_approval(approval),
                approval_id=str(approval_id)
            )
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="ESCALATION_FAILED")
    
    # ==================== Query Operations ====================
    
    def get_pending_approvals(
        self,
        hostel_id: UUID,
        assigned_to_id: Optional[UUID] = None,
        urgent_only: bool = False,
        page: int = 1,
        page_size: int = 20
    ) -> ServiceResult:
        """
        Get pending approval requests.
        
        Args:
            hostel_id: Hostel UUID
            assigned_to_id: Optional assignee filter
            urgent_only: Only urgent requests
            page: Page number
            page_size: Items per page
            
        Returns:
            ServiceResult with pending approvals
        """
        try:
            from app.repositories.base.pagination import PaginationParams
            
            pagination = PaginationParams(page=page, page_size=page_size)
            
            result = self.repository.find_pending_approvals(
                hostel_id=hostel_id,
                assigned_to_id=assigned_to_id,
                urgent_only=urgent_only,
                pagination=pagination
            )
            
            return ServiceResult.ok(data={
                'items': [self._serialize_approval(a) for a in result.items],
                'total': result.total,
                'page': result.page,
                'page_size': result.page_size,
                'total_pages': result.total_pages,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def get_approval_by_announcement(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get approval request for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with approval data
        """
        try:
            approval = self.repository.find_by_announcement(announcement_id)
            
            if not approval:
                return ServiceResult.fail(
                    f"No approval found for announcement {announcement_id}",
                    error_code="NOT_FOUND"
                )
            
            return ServiceResult.ok(data=self._serialize_approval(approval))
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def get_approval_history(
        self,
        approval_id: UUID,
        limit: int = 50
    ) -> ServiceResult:
        """
        Get approval history with audit trail.
        
        Args:
            approval_id: Approval UUID
            limit: Maximum records
            
        Returns:
            ServiceResult with history
        """
        try:
            history = self.repository.get_approval_history(
                approval_id=approval_id,
                limit=limit
            )
            
            return ServiceResult.ok(data={
                'history': [self._serialize_history_entry(h) for h in history],
                'total': len(history),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="HISTORY_FETCH_FAILED")
    
    # ==================== SLA Monitoring ====================
    
    def check_sla_breaches(
        self,
        hostel_id: Optional[UUID] = None
    ) -> ServiceResult:
        """
        Check for SLA breaches and trigger alerts.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            ServiceResult with breached approvals
        """
        try:
            breached = self.repository.check_sla_breaches(hostel_id=hostel_id)
            
            if breached:
                # Publish alert
                self.event_publisher.publish('approval.sla_breached', {
                    'count': len(breached),
                    'approvals': [str(a.id) for a in breached],
                })
                
                # Auto-escalate if configured
                for approval in breached:
                    if not approval.is_escalated:
                        self.escalate_approval(
                            approval_id=approval.id,
                            dto=EscalateApprovalDTO(
                                escalation_reason="SLA deadline exceeded"
                            ),
                            escalated_by_id=None  # System escalation
                        )
            
            return ServiceResult.ok(data={
                'breached_count': len(breached),
                'approvals': [self._serialize_approval(a) for a in breached],
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="SLA_CHECK_FAILED")
    
    # ==================== Workflow Management ====================
    
    def create_approval_workflow(
        self,
        hostel_id: UUID,
        dto: CreateApprovalWorkflowDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create approval workflow configuration.
        
        Args:
            hostel_id: Hostel UUID
            dto: Workflow configuration
            user_id: User creating workflow
            
        Returns:
            ServiceResult with workflow data
        """
        try:
            workflow = self.repository.create_approval_workflow(
                hostel_id=hostel_id,
                created_by_id=user_id,
                workflow_name=dto.workflow_name,
                steps=dto.steps,
                description=dto.description,
                default_approvers=dto.default_approvers,
                sla_hours=dto.sla_hours,
                escalation_enabled=dto.escalation_enabled,
                escalation_after_hours=dto.escalation_after_hours,
                escalation_approvers=dto.escalation_approvers,
                auto_approval_enabled=dto.auto_approval_enabled,
                auto_approval_rules=dto.auto_approval_rules
            )
            
            self.session.commit()
            
            self.event_publisher.publish('workflow.created', {
                'workflow_id': str(workflow.id),
                'hostel_id': str(hostel_id),
                'workflow_name': dto.workflow_name,
            })
            
            return ServiceResult.ok(
                data=self._serialize_workflow(workflow),
                workflow_id=str(workflow.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="WORKFLOW_CREATE_FAILED")
    
    def create_approval_rule(
        self,
        hostel_id: UUID,
        dto: CreateApprovalRuleDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create auto-approval rule.
        
        Args:
            hostel_id: Hostel UUID
            dto: Rule configuration
            user_id: User creating rule
            
        Returns:
            ServiceResult with rule data
        """
        try:
            rule = self.repository.create_approval_rule(
                hostel_id=hostel_id,
                created_by_id=user_id,
                rule_name=dto.rule_name,
                conditions=dto.conditions,
                priority=dto.priority,
                description=dto.description
            )
            
            self.session.commit()
            
            self.event_publisher.publish('approval_rule.created', {
                'rule_id': str(rule.id),
                'hostel_id': str(hostel_id),
                'rule_name': dto.rule_name,
            })
            
            return ServiceResult.ok(
                data=self._serialize_rule(rule),
                rule_id=str(rule.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="RULE_CREATE_FAILED")
    
    # ==================== Analytics ====================
    
    def get_approval_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ServiceResult:
        """
        Get approval statistics and metrics.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            ServiceResult with statistics
        """
        try:
            stats = self.repository.get_approval_statistics(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return ServiceResult.ok(data=stats)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="STATS_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _notify_approver(self, approval, is_escalation: bool = False):
        """Send notification to assigned approver."""
        if not approval.assigned_to_id:
            return
        
        message_type = 'approval_escalated' if is_escalation else 'approval_requested'
        
        self.notification_service.send_notification(
            user_id=approval.assigned_to_id,
            notification_type=message_type,
            title='Approval Request' + (' (Escalated)' if is_escalation else ''),
            message=f'You have a new approval request for announcement',
            data={
                'approval_id': str(approval.id),
                'announcement_id': str(approval.announcement_id),
                'is_urgent': approval.is_urgent_request,
                'sla_deadline': approval.sla_deadline.isoformat() if approval.sla_deadline else None,
            }
        )
    
    def _notify_requester(self, approval, action: str):
        """Send notification to requester about approval decision."""
        if not approval.requested_by_id:
            return
        
        self.notification_service.send_notification(
            user_id=approval.requested_by_id,
            notification_type=f'approval_{action}',
            title=f'Approval {action.title()}',
            message=f'Your announcement has been {action}',
            data={
                'approval_id': str(approval.id),
                'announcement_id': str(approval.announcement_id),
                'decision_notes': approval.approval_notes if action == 'approved' else approval.rejection_reason,
            }
        )
    
    def _serialize_approval(self, approval) -> Dict[str, Any]:
        """Serialize approval to dictionary."""
        return {
            'id': str(approval.id),
            'announcement_id': str(approval.announcement_id),
            'requested_by_id': str(approval.requested_by_id) if approval.requested_by_id else None,
            'approval_status': approval.approval_status,
            'is_urgent': approval.is_urgent_request,
            'approved': approval.approved,
            'decided_by_id': str(approval.decided_by_id) if approval.decided_by_id else None,
            'decided_at': approval.decided_at.isoformat() if approval.decided_at else None,
            'approval_notes': approval.approval_notes,
            'rejection_reason': approval.rejection_reason,
            'suggested_modifications': approval.suggested_modifications,
            'allow_resubmission': approval.allow_resubmission,
            'assigned_to_id': str(approval.assigned_to_id) if approval.assigned_to_id else None,
            'is_escalated': approval.is_escalated,
            'sla_deadline': approval.sla_deadline.isoformat() if approval.sla_deadline else None,
            'sla_breached': approval.sla_breached,
            'submitted_at': approval.submitted_at.isoformat(),
            'time_pending_hours': float(approval.time_pending_hours) if approval.time_pending_hours else None,
            'created_at': approval.created_at.isoformat(),
        }
    
    def _serialize_history_entry(self, entry) -> Dict[str, Any]:
        """Serialize history entry to dictionary."""
        return {
            'id': str(entry.id),
            'action': entry.action,
            'previous_status': entry.previous_status,
            'new_status': entry.new_status,
            'performed_by_id': str(entry.performed_by_id) if entry.performed_by_id else None,
            'performed_by_name': entry.performed_by_name,
            'performed_by_role': entry.performed_by_role,
            'notes': entry.notes,
            'performed_at': entry.performed_at.isoformat(),
        }
    
    def _serialize_workflow(self, workflow) -> Dict[str, Any]:
        """Serialize workflow to dictionary."""
        return {
            'id': str(workflow.id),
            'hostel_id': str(workflow.hostel_id),
            'workflow_name': workflow.workflow_name,
            'description': workflow.description,
            'steps': workflow.steps,
            'sla_hours': workflow.sla_hours,
            'escalation_enabled': workflow.escalation_enabled,
            'is_active': workflow.is_active,
            'created_at': workflow.created_at.isoformat(),
        }
    
    def _serialize_rule(self, rule) -> Dict[str, Any]:
        """Serialize approval rule to dictionary."""
        return {
            'id': str(rule.id),
            'hostel_id': str(rule.hostel_id),
            'rule_name': rule.rule_name,
            'description': rule.description,
            'conditions': rule.conditions,
            'priority': rule.priority,
            'is_active': rule.is_active,
            'times_applied': rule.times_applied,
            'created_at': rule.created_at.isoformat(),
        }