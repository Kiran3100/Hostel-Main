# --- File: app/schemas/maintenance/maintenance_assignment.py ---
"""
Maintenance assignment schemas for task allocation.

Provides schemas for assigning maintenance tasks to staff, vendors,
and contractors with tracking and history management.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional, Union

from pydantic import (
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
    computed_field,
)
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "TaskAssignment",
    "VendorAssignment",
    "AssignmentUpdate",
    "BulkAssignment",
    "AssignmentHistory",
    "AssignmentEntry",
    "AssignmentResponse",
    "ReassignmentRequest",
]


class TaskAssignment(BaseSchema):
    """
    Maintenance task assignment to internal staff.
    
    Tracks assignment of maintenance tasks to hostel staff
    with deadlines and instructions.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "assigned_to_name": "John Technician",
                "assigned_by_name": "Supervisor Smith",
                "deadline": "2024-12-31",
                "priority_level": "high"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Human-readable request number",
    )
    assigned_to: UUID = Field(
        ...,
        description="Staff member user ID",
    )
    assigned_to_name: str = Field(
        ...,
        description="Staff member full name",
    )
    assigned_to_role: Optional[str] = Field(
        None,
        description="Staff member role/designation",
    )
    assigned_by: UUID = Field(
        ...,
        description="Supervisor/admin who assigned the task",
    )
    assigned_by_name: str = Field(
        ...,
        description="Assignor full name",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )
    deadline: Optional[Date] = Field(
        None,
        description="Task completion deadline",
    )
    priority_level: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent|critical)$",
        description="Assignment priority",
    )
    instructions: Optional[str] = Field(
        None,
        max_length=1000,
        description="Specific instructions for assigned staff",
    )
    estimated_hours: Union[Annotated[Decimal, Field(ge=0, le=1000, decimal_places=2)], None] = Field(
        None,
        description="Estimated hours to complete",
    )
    required_skills: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Skills required for the task",
    )
    tools_required: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Tools/equipment required",
    )

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: Optional[Date]) -> Optional[Date]:
        """
        Validate deadline is in the future.
        
        Deadlines should be reasonable and not too far out.
        """
        if v is not None:
            today = Date.today()
            
            if v < today:
                raise ValueError("Deadline cannot be in the past")
            
            # Max 6 months out for regular tasks
            days_ahead = (v - today).days
            if days_ahead > 180:
                raise ValueError(
                    "Deadline cannot be more than 6 months in the future"
                )
        
        return v

    @field_validator("instructions")
    @classmethod
    def normalize_instructions(cls, v: Optional[str]) -> Optional[str]:
        """Normalize instructions text."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class VendorAssignment(BaseCreateSchema):
    """
    Assignment to external vendor/contractor.
    
    Manages outsourced maintenance work with contract terms,
    quotes, and payment details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor_name": "ABC Contractors Ltd",
                "vendor_contact": "+919876543210",
                "quoted_amount": "15000.00",
                "estimated_completion_date": "2024-12-31",
                "payment_terms": "50% advance, 50% on completion"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    vendor_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Vendor/contractor company name",
    )
    vendor_contact_person: Optional[str] = Field(
        None,
        max_length=255,
        description="Vendor contact person name",
    )
    vendor_contact: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Vendor primary contact number",
    )
    vendor_email: Optional[EmailStr] = Field(
        None,
        description="Vendor email address",
    )
    vendor_address: Optional[str] = Field(
        None,
        max_length=500,
        description="Vendor business address",
    )

    # Quote and contract - Using Annotated for Decimal fields
    quoted_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Vendor quoted amount",
    )
    quote_reference: Optional[str] = Field(
        None,
        max_length=100,
        description="Quote reference number",
    )
    quote_valid_until: Optional[Date] = Field(
        None,
        description="Quote validity Date",
    )
    payment_terms: Optional[str] = Field(
        None,
        max_length=500,
        description="Payment terms and conditions",
    )
    advance_payment_percentage: Union[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)], None] = Field(
        None,
        description="Advance payment percentage",
    )
    advance_payment_amount: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Advance payment amount",
    )

    # Timeline
    estimated_start_date: Optional[Date] = Field(
        None,
        description="Estimated work start Date",
    )
    estimated_completion_date: Date = Field(
        ...,
        description="Estimated completion Date",
    )
    
    # Contract details
    work_order_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Work order reference number",
    )
    contract_details: Optional[str] = Field(
        None,
        max_length=2000,
        description="Contract terms and scope of work",
    )
    warranty_period_months: Optional[int] = Field(
        None,
        ge=0,
        le=120,
        description="Warranty period in months",
    )
    warranty_terms: Optional[str] = Field(
        None,
        max_length=1000,
        description="Warranty terms and conditions",
    )

    # Insurance and compliance
    vendor_insured: bool = Field(
        default=False,
        description="Whether vendor has liability insurance",
    )
    insurance_details: Optional[str] = Field(
        None,
        max_length=500,
        description="Insurance policy details",
    )
    compliance_certificates: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Required compliance certificates",
    )

    @field_validator("vendor_contact")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Normalize vendor phone number."""
        return v.replace(" ", "").replace("-", "").strip()

    @field_validator("quoted_amount", "advance_payment_amount")
    @classmethod
    def round_amounts(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round monetary amounts to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @field_validator(
        "vendor_address",
        "payment_terms",
        "contract_details",
        "warranty_terms",
        "insurance_details",
    )
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_dates_consistency(self):
        """
        Validate Date consistency.
        
        Ensures start Date is before completion Date and dates are reasonable.
        """
        # Completion Date should be in future
        if self.estimated_completion_date < Date.today():
            raise ValueError(
                "Estimated completion Date cannot be in the past"
            )
        
        # Start Date should be before completion
        if self.estimated_start_date:
            if self.estimated_start_date > self.estimated_completion_date:
                raise ValueError(
                    "Start Date must be before completion Date"
                )
        
        # Quote validity
        if self.quote_valid_until:
            if self.quote_valid_until < Date.today():
                raise ValueError(
                    "Quote validity Date cannot be in the past"
                )
        
        return self

    @model_validator(mode="after")
    def validate_advance_payment(self):
        """
        Validate advance payment calculation.
        
        Ensures advance amount matches percentage if both provided.
        """
        if self.advance_payment_percentage and self.advance_payment_amount:
            expected_advance = (
                self.quoted_amount * self.advance_payment_percentage / 100
            )
            
            # Allow small rounding differences
            if abs(expected_advance - self.advance_payment_amount) > Decimal("1.00"):
                raise ValueError(
                    f"Advance payment amount ({self.advance_payment_amount}) "
                    f"doesn't match percentage ({self.advance_payment_percentage}%) "
                    f"of quoted amount ({self.quoted_amount})"
                )
        
        # If only percentage given, calculate amount
        if self.advance_payment_percentage and not self.advance_payment_amount:
            self.advance_payment_amount = round(
                self.quoted_amount * self.advance_payment_percentage / 100,
                2,
            )
        
        return self

    @model_validator(mode="after")
    def validate_warranty_requirements(self):
        """
        Validate warranty information.
        
        If warranty period is specified, terms should be provided.
        """
        if self.warranty_period_months and self.warranty_period_months > 0:
            if not self.warranty_terms:
                raise ValueError(
                    "Warranty terms are required when warranty period is specified"
                )
        
        return self


class AssignmentUpdate(BaseCreateSchema):
    """
    Update existing maintenance assignment.
    
    Allows reassignment, deadline changes, and additional instructions.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "new_assigned_to": "123e4567-e89b-12d3-a456-426614174222",
                "reassignment_reason": "Original assignee is on leave",
                "updated_by": "123e4567-e89b-12d3-a456-426614174111"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )

    # Reassignment
    new_assigned_to: Optional[UUID] = Field(
        None,
        description="New assignee user ID (for reassignment)",
    )
    reassignment_reason: Optional[str] = Field(
        None,
        min_length=10,
        max_length=500,
        description="Reason for reassignment",
    )

    # Deadline modification
    new_deadline: Optional[Date] = Field(
        None,
        description="Updated deadline",
    )
    deadline_change_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for deadline change",
    )

    # Additional information
    additional_instructions: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional instructions to append",
    )
    priority_change: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent|critical)$",
        description="Updated priority level",
    )

    # Update context
    updated_by: UUID = Field(
        ...,
        description="User making the update",
    )
    update_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notes about the update",
    )

    @field_validator("reassignment_reason")
    @classmethod
    def validate_reassignment_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate reassignment reason if provided."""
        if v is not None:
            v = v.strip()
            if len(v) < 10:
                raise ValueError(
                    "Reassignment reason must be at least 10 characters"
                )
            return v
        return None

    @field_validator("new_deadline")
    @classmethod
    def validate_new_deadline(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate new deadline is in future."""
        if v is not None and v < Date.today():
            raise ValueError("New deadline cannot be in the past")
        return v

    @field_validator(
        "deadline_change_reason",
        "additional_instructions",
        "update_notes",
    )
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_update_requirements(self):
        """
        Validate update field requirements.
        
        Ensures proper justification for changes.
        """
        # Reassignment requires reason
        if self.new_assigned_to and not self.reassignment_reason:
            raise ValueError(
                "Reassignment reason is required when changing assignee"
            )
        
        # Deadline extension should have reason
        if self.new_deadline and self.deadline_change_reason:
            # This is good practice
            pass
        
        return self


class BulkAssignment(BaseCreateSchema):
    """
    Assign multiple maintenance requests to same person.
    
    Efficient bulk assignment for batch processing of similar issues.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ],
                "assigned_to": "123e4567-e89b-12d3-a456-426614174222",
                "assigned_by": "123e4567-e89b-12d3-a456-426614174111",
                "common_deadline": "2024-12-31",
                "priority_level": "medium"
            }
        }
    )

    maintenance_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of maintenance request IDs",
    )
    assigned_to: UUID = Field(
        ...,
        description="User ID to assign all requests to",
    )
    assigned_by: UUID = Field(
        ...,
        description="User ID making the assignments",
    )
    common_deadline: Optional[Date] = Field(
        None,
        description="Common deadline for all requests",
    )
    instructions: Optional[str] = Field(
        None,
        max_length=1000,
        description="Common instructions for all assignments",
    )
    priority_level: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent|critical)$",
        description="Common priority for all assignments",
    )
    send_notification: bool = Field(
        default=True,
        description="Send notification to assignee",
    )
    bulk_assignment_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notes about bulk assignment",
    )

    @field_validator("maintenance_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[UUID]) -> List[UUID]:
        """
        Ensure no duplicate maintenance IDs.
        
        Prevents double-assignment errors.
        """
        if len(v) != len(set(v)):
            # Find duplicates
            seen = set()
            duplicates = set()
            for maintenance_id in v:
                if maintenance_id in seen:
                    duplicates.add(str(maintenance_id))
                seen.add(maintenance_id)
            
            raise ValueError(
                f"Duplicate maintenance IDs not allowed: {', '.join(duplicates)}"
            )
        
        return v

    @field_validator("common_deadline")
    @classmethod
    def validate_deadline(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate deadline is in future."""
        if v is not None and v < Date.today():
            raise ValueError("Deadline cannot be in the past")
        return v

    @field_validator("instructions", "bulk_assignment_notes")
    @classmethod
    def normalize_text(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class AssignmentEntry(BaseSchema):
    """
    Individual assignment history entry.
    
    Represents a single assignment in the history timeline.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assignment_id": "123e4567-e89b-12d3-a456-426614174000",
                "assigned_to_name": "John Technician",
                "assigned_by_name": "Supervisor Smith",
                "assigned_at": "2024-01-15T10:00:00",
                "completed": True,
                "was_on_time": True
            }
        }
    )

    assignment_id: UUID = Field(
        ...,
        description="Assignment unique identifier",
    )
    assigned_to: UUID = Field(
        ...,
        description="Assignee user ID",
    )
    assigned_to_name: str = Field(
        ...,
        description="Assignee full name",
    )
    assigned_to_role: Optional[str] = Field(
        None,
        description="Assignee role/designation",
    )
    assigned_by: UUID = Field(
        ...,
        description="Assignor user ID",
    )
    assigned_by_name: str = Field(
        ...,
        description="Assignor full name",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )
    deadline: Optional[Date] = Field(
        None,
        description="Task deadline",
    )
    instructions: Optional[str] = Field(
        None,
        description="Assignment instructions",
    )

    # Completion tracking
    completed: bool = Field(
        False,
        description="Whether task was completed by this assignee",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Completion timestamp",
    )
    completion_notes: Optional[str] = Field(
        None,
        description="Completion notes",
    )

    # Reassignment tracking
    reassigned: bool = Field(
        False,
        description="Whether task was reassigned to someone else",
    )
    reassigned_at: Optional[datetime] = Field(
        None,
        description="Reassignment timestamp",
    )
    reassignment_reason: Optional[str] = Field(
        None,
        description="Reason for reassignment",
    )

    # Performance metrics
    time_to_complete_hours: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Hours taken to complete (if completed)",
    )
    met_deadline: Optional[bool] = Field(
        None,
        description="Whether deadline was met (if completed)",
    )

    @model_validator(mode="after")
    def validate_completion_consistency(self):
        """
        Validate completion data consistency.
        
        Ensures completion timestamps and flags are consistent.
        """
        if self.completed:
            if not self.completed_at:
                raise ValueError(
                    "Completion timestamp required when task is completed"
                )
            
            # Can't be both completed and reassigned
            if self.reassigned:
                raise ValueError(
                    "Task cannot be both completed and reassigned"
                )
        
        if self.reassigned and not self.reassigned_at:
            raise ValueError(
                "Reassignment timestamp required when task is reassigned"
            )
        
        return self


class AssignmentHistory(BaseSchema):
    """
    Complete assignment history for maintenance request.
    
    Tracks all assignments, reassignments, and completions
    for audit trail and performance analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "total_assignments": 2,
                "current_assignee": "John Technician",
                "total_reassignments": 1
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    total_assignments: int = Field(
        ...,
        ge=0,
        description="Total number of times task was assigned",
    )
    current_assignee: Optional[str] = Field(
        None,
        description="Current assignee name (if still assigned)",
    )
    current_assignee_id: Optional[UUID] = Field(
        None,
        description="Current assignee user ID",
    )
    assignments: List[AssignmentEntry] = Field(
        ...,
        description="Chronological list of all assignments",
    )
    
    # Summary metrics
    average_assignment_duration_hours: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Average time per assignment",
    )
    total_reassignments: int = Field(
        default=0,
        ge=0,
        description="Number of reassignments",
    )

    @field_validator("assignments")
    @classmethod
    def validate_assignments_order(cls, v: List[AssignmentEntry]) -> List[AssignmentEntry]:
        """
        Validate assignments are in chronological order.
        
        Ensures history timeline is logical.
        """
        if len(v) > 1:
            for i in range(len(v) - 1):
                if v[i].assigned_at > v[i + 1].assigned_at:
                    raise ValueError(
                        "Assignment history must be in chronological order"
                    )
        
        return v


class AssignmentResponse(BaseSchema):
    """
    Assignment response with complete details.
    
    Returned after successful assignment creation or update.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174001",
                "request_number": "MNT-2024-001",
                "assigned_to_name": "John Technician",
                "assigned_by_name": "Supervisor Smith",
                "assignment_type": "staff",
                "status": "active"
            }
        }
    )

    id: UUID = Field(
        ...,
        description="Assignment unique identifier",
    )
    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    
    # Assignment details
    assignment_type: str = Field(
        ...,
        pattern=r"^(staff|vendor|contractor)$",
        description="Type of assignment",
    )
    assigned_to: UUID = Field(
        ...,
        description="Assignee user/vendor ID",
    )
    assigned_to_name: str = Field(
        ...,
        description="Assignee name",
    )
    assigned_to_role: Optional[str] = Field(
        None,
        description="Assignee role/designation",
    )
    assigned_by: UUID = Field(
        ...,
        description="User who made the assignment",
    )
    assigned_by_name: str = Field(
        ...,
        description="Assignor name",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )
    
    # Status and timeline
    status: str = Field(
        ...,
        pattern=r"^(active|in_progress|completed|cancelled|reassigned)$",
        description="Assignment status",
    )
    deadline: Optional[Date] = Field(
        None,
        description="Assignment deadline",
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Work start timestamp",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Completion timestamp",
    )
    
    # Instructions and notes
    instructions: Optional[str] = Field(
        None,
        description="Assignment instructions",
    )
    priority_level: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent|critical)$",
        description="Assignment priority",
    )
    
    # Vendor-specific (if applicable)
    vendor_name: Optional[str] = Field(
        None,
        description="Vendor company name (if vendor assignment)",
    )
    estimated_cost: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Estimated cost (for vendor assignments)",
    )
    
    # Performance tracking
    estimated_hours: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Estimated hours to complete",
    )
    actual_hours: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Actual hours spent (if completed)",
    )
    
    # Metadata
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp",
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp",
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        """Check if assignment is currently active."""
        return self.status in ["active", "in_progress"]

    @computed_field  # type: ignore[misc]
    @property
    def is_overdue(self) -> bool:
        """Check if assignment is overdue."""
        if not self.deadline or self.status in ["completed", "cancelled"]:
            return False
        return self.deadline < Date.today()


class ReassignmentRequest(BaseCreateSchema):
    """
    Request to reassign maintenance task to different staff/vendor.
    
    Captures reason for reassignment and new assignee details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_assigned_to": "123e4567-e89b-12d3-a456-426614174222",
                "assignment_type": "staff",
                "reassignment_reason": "Original assignee is on leave",
                "reassigned_by": "123e4567-e89b-12d3-a456-426614174111",
                "priority_level": "high"
            }
        }
    )

    new_assigned_to: UUID = Field(
        ...,
        description="New assignee user/vendor ID",
    )
    assignment_type: str = Field(
        ...,
        pattern=r"^(staff|vendor|contractor)$",
        description="Type of new assignment",
    )
    reassignment_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for reassignment",
    )
    reassigned_by: UUID = Field(
        ...,
        description="User performing the reassignment",
    )
    
    # Optional updates
    new_deadline: Optional[Date] = Field(
        None,
        description="Updated deadline (if changed)",
    )
    additional_instructions: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional instructions for new assignee",
    )
    priority_level: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent|critical)$",
        description="Updated priority level",
    )
    
    # Vendor-specific (if reassigning to vendor)
    vendor_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Vendor company name (if reassigning to vendor)",
    )
    estimated_cost: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Estimated cost (for vendor reassignments)",
    )
    
    # Notification
    notify_previous_assignee: bool = Field(
        default=True,
        description="Send notification to previous assignee",
    )
    notify_new_assignee: bool = Field(
        default=True,
        description="Send notification to new assignee",
    )

    @field_validator("reassignment_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reassignment reason is meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Reassignment reason must be at least 10 characters")
        return v

    @field_validator("new_deadline")
    @classmethod
    def validate_deadline(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate new deadline is in future."""
        if v is not None and v < Date.today():
            raise ValueError("New deadline cannot be in the past")
        return v

    @model_validator(mode="after")
    def validate_vendor_reassignment(self):
        """Validate vendor-specific fields for vendor reassignments."""
        if self.assignment_type == "vendor":
            if not self.vendor_name:
                raise ValueError(
                    "vendor_name is required when reassigning to vendor"
                )
            if self.estimated_cost is None:
                raise ValueError(
                    "estimated_cost is required when reassigning to vendor"
                )
        
        return self