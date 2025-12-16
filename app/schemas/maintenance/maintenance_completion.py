# --- File: app/schemas/maintenance/maintenance_completion.py ---
"""
Maintenance completion schemas with quality tracking.

Provides schemas for marking maintenance as completed, quality checks,
material tracking, and completion certificates.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Annotated, List, Union

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "CompletionRequest",
    "MaterialItem",
    "QualityCheck",
    "ChecklistItem",
    "CompletionResponse",
    "CompletionCertificate",
]


class MaterialItem(BaseSchema):
    """
    Material used in maintenance work.
    
    Tracks individual materials with quantities and costs
    for accurate billing and inventory management.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "material_name": "Electrical wire 2.5mm",
                "quantity": "50.5",
                "unit": "meters",
                "unit_cost": "25.00",
                "total_cost": "1262.50"
            }
        }
    )

    material_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Material/item name",
    )
    material_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Material code/SKU",
    )
    category: Union[str, None] = Field(
        None,
        max_length=100,
        description="Material category",
    )
    # Quantity with 3 decimal places
    quantity: Annotated[Decimal, Field(gt=0, decimal_places=3)] = Field(
        ...,
        description="Quantity used",
    )
    unit: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unit of measurement (pcs, kg, liters, meters, etc.)",
    )
    # Cost fields with 2 decimal places
    unit_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Cost per unit",
    )
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total cost for this material",
    )
    supplier: Union[str, None] = Field(
        None,
        max_length=255,
        description="Material supplier name",
    )
    supplier_invoice: Union[str, None] = Field(
        None,
        max_length=100,
        description="Supplier invoice number",
    )
    warranty_months: Union[int, None] = Field(
        None,
        ge=0,
        le=120,
        description="Material warranty period in months",
    )

    @field_validator("quantity", "unit_cost", "total_cost")
    @classmethod
    def round_decimals(cls, v: Decimal) -> Decimal:
        """Round decimal values appropriately."""
        # Quantity can have 3 decimals, costs have 2
        return v

    @field_validator("material_name", "category", "unit", "supplier")
    @classmethod
    def normalize_text(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_cost_calculation(self) -> "MaterialItem":
        """
        Validate total cost calculation.
        
        Ensures total_cost = quantity × unit_cost (with rounding tolerance).
        """
        calculated_total = self.quantity * self.unit_cost
        
        # Allow small rounding differences (0.01)
        if abs(calculated_total - self.total_cost) > Decimal("0.01"):
            raise ValueError(
                f"Total cost ({self.total_cost}) doesn't match "
                f"quantity ({self.quantity}) × unit cost ({self.unit_cost}) "
                f"= {calculated_total}"
            )
        
        return self


class CompletionRequest(BaseCreateSchema):
    """
    Mark maintenance work as completed.
    
    Comprehensive completion with work notes, materials,
    labor tracking, and cost documentation.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "completed_by": "123e4567-e89b-12d3-a456-426614174222",
                "work_notes": "Replaced ceiling fan, checked all electrical connections",
                "labor_hours": "2.5",
                "actual_cost": "3500.00",
                "actual_completion_date": "2024-01-20"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    completed_by: UUID = Field(
        ...,
        description="User ID who completed the work",
    )
    
    # Completion details
    work_notes: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Detailed notes about work performed",
    )
    work_summary: Union[str, None] = Field(
        None,
        max_length=500,
        description="Brief work summary",
    )
    
    # Materials used
    materials_used: List[MaterialItem] = Field(
        default_factory=list,
        max_length=100,
        description="List of materials used",
    )
    
    # Labor tracking - Using Annotated for Decimal
    labor_hours: Annotated[Decimal, Field(ge=0, le=1000, decimal_places=2)] = Field(
        ...,
        description="Total labor hours spent",
    )
    labor_rate_per_hour: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Labor rate per hour",
    )
    number_of_workers: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of workers involved",
    )
    
    # Cost breakdown - All Decimal fields with 2 decimal places
    materials_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Total materials cost",
    )
    labor_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Total labor cost",
    )
    vendor_charges: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="External vendor charges",
    )
    other_costs: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Other miscellaneous costs",
    )
    actual_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total actual cost",
    )
    cost_breakdown: Union[dict, None] = Field(
        None,
        description="Detailed cost breakdown",
    )
    
    # Photos
    completion_photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=15,
        description="After-completion photographs",
    )
    before_photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=15,
        description="Before work photographs (if available)",
    )
    
    # Timeline
    actual_start_date: Union[Date, None] = Field(
        None,
        description="Actual work start Date",
    )
    actual_completion_date: Date = Field(
        ...,
        description="Actual completion Date",
    )
    total_working_days: Union[int, None] = Field(
        None,
        ge=0,
        description="Total working days taken",
    )
    
    # Follow-up
    follow_up_required: bool = Field(
        False,
        description="Whether follow-up inspection needed",
    )
    follow_up_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Follow-up requirements",
    )
    follow_up_date: Union[Date, None] = Field(
        None,
        description="Scheduled follow-up Date",
    )
    
    # Warranty
    warranty_applicable: bool = Field(
        default=False,
        description="Whether warranty applies to this work",
    )
    warranty_period_months: Union[int, None] = Field(
        None,
        ge=0,
        le=120,
        description="Warranty period in months",
    )
    warranty_terms: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Warranty terms and conditions",
    )

    @field_validator(
        "labor_hours",
        "materials_cost",
        "labor_cost",
        "vendor_charges",
        "other_costs",
        "actual_cost",
        "labor_rate_per_hour",
    )
    @classmethod
    def round_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round decimal values to 2 places."""
        return round(v, 2) if v is not None else None

    @field_validator("work_notes", "work_summary", "follow_up_notes", "warranty_terms")
    @classmethod
    def normalize_text(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_completion_dates(self) -> "CompletionRequest":
        """
        Validate completion Date consistency.
        
        Ensures dates are logical and in proper sequence.
        """
        # Completion Date can't be in future
        if self.actual_completion_date > Date.today():
            raise ValueError("Completion Date cannot be in the future")
        
        # Start Date should be before completion
        if self.actual_start_date:
            if self.actual_start_date > self.actual_completion_date:
                raise ValueError(
                    "Start Date must be before or equal to completion Date"
                )
            
            # Calculate working days if not provided
            if self.total_working_days is None:
                self.total_working_days = (
                    self.actual_completion_date - self.actual_start_date
                ).days + 1
        
        return self

    @model_validator(mode="after")
    def validate_cost_breakdown(self) -> "CompletionRequest":
        """
        Validate cost breakdown matches total.
        
        Sum of components should equal actual cost.
        """
        total_components = (
            self.materials_cost
            + self.labor_cost
            + self.vendor_charges
            + self.other_costs
        )
        
        # Allow small rounding differences
        if abs(total_components - self.actual_cost) > Decimal("1.00"):
            raise ValueError(
                f"Cost breakdown ({total_components}) doesn't match "
                f"actual cost ({self.actual_cost})"
            )
        
        return self

    @model_validator(mode="after")
    def validate_materials_cost(self) -> "CompletionRequest":
        """
        Validate materials cost matches materials list.
        
        Sum of material items should match materials_cost.
        """
        if self.materials_used:
            calculated_materials_cost = sum(
                item.total_cost for item in self.materials_used
            )
            
            # Allow small variance
            if abs(calculated_materials_cost - self.materials_cost) > Decimal("1.00"):
                raise ValueError(
                    f"Materials cost ({self.materials_cost}) doesn't match "
                    f"sum of material items ({calculated_materials_cost})"
                )
        
        return self

    @model_validator(mode="after")
    def validate_labor_cost(self) -> "CompletionRequest":
        """
        Validate labor cost calculation.
        
        If labor rate provided, cost should match hours × rate.
        """
        if self.labor_rate_per_hour is not None:
            calculated_labor_cost = self.labor_hours * self.labor_rate_per_hour
            
            if abs(calculated_labor_cost - self.labor_cost) > Decimal("1.00"):
                raise ValueError(
                    f"Labor cost ({self.labor_cost}) doesn't match "
                    f"hours ({self.labor_hours}) × rate ({self.labor_rate_per_hour})"
                )
        
        return self

    @model_validator(mode="after")
    def validate_follow_up_requirements(self) -> "CompletionRequest":
        """
        Validate follow-up information.
        
        If follow-up required, notes and Date should be provided.
        """
        if self.follow_up_required:
            if not self.follow_up_notes:
                raise ValueError(
                    "Follow-up notes are required when follow-up is needed"
                )
            
            if not self.follow_up_date:
                raise ValueError(
                    "Follow-up Date is required when follow-up is needed"
                )
            
            # Follow-up Date should be in future
            if self.follow_up_date <= self.actual_completion_date:
                raise ValueError(
                    "Follow-up Date must be after completion Date"
                )
        
        return self

    @model_validator(mode="after")
    def validate_warranty_requirements(self) -> "CompletionRequest":
        """
        Validate warranty information.
        
        If warranty applicable, period and terms should be provided.
        """
        if self.warranty_applicable:
            if not self.warranty_period_months:
                raise ValueError(
                    "Warranty period is required when warranty is applicable"
                )
            
            if not self.warranty_terms:
                raise ValueError(
                    "Warranty terms are required when warranty is applicable"
                )
        
        return self


class ChecklistItem(BaseSchema):
    """
    Quality check checklist item.
    
    Individual item in quality inspection checklist.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "item_description": "Check fan rotation speed",
                "status": "pass",
                "is_critical": True,
                "notes": "Fan operating at normal speed"
            }
        }
    )

    item_id: Union[str, None] = Field(
        None,
        max_length=50,
        description="Checklist item unique ID",
    )
    item_description: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="What to check/verify",
    )
    category: Union[str, None] = Field(
        None,
        max_length=100,
        description="Check category",
    )
    status: str = Field(
        ...,
        pattern=r"^(pass|fail|na|partial)$",
        description="Check result status",
    )
    is_critical: bool = Field(
        default=False,
        description="Whether this is a critical check",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes or observations",
    )
    checked_by: Union[str, None] = Field(
        None,
        max_length=255,
        description="Person who performed this check",
    )
    photo_evidence: Union[HttpUrl, None] = Field(
        None,
        description="Photo evidence URL",
    )

    @field_validator("item_description", "notes")
    @classmethod
    def normalize_text(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class QualityCheck(BaseCreateSchema):
    """
    Quality check for completed maintenance work.
    
    Inspection and verification of work quality with
    detailed checklist and approval/rejection.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "quality_check_passed": True,
                "overall_rating": 4,
                "checked_by": "123e4567-e89b-12d3-a456-426614174333",
                "inspection_date": "2024-01-21",
                "rework_required": False
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    
    # Overall result
    quality_check_passed: bool = Field(
        ...,
        description="Overall quality check result",
    )
    overall_rating: Union[int, None] = Field(
        None,
        ge=1,
        le=5,
        description="Overall quality rating (1-5 stars)",
    )
    
    # Detailed checklist
    checklist_items: List[ChecklistItem] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Quality check checklist items",
    )
    
    # Inspection details
    quality_check_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Detailed quality check notes",
    )
    defects_found: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Any defects or issues found",
    )
    
    # Inspector
    checked_by: UUID = Field(
        ...,
        description="User ID who performed quality check",
    )
    inspection_date: Date = Field(
        ...,
        description="Inspection Date",
    )
    inspection_time: Union[time, None] = Field(
        None,
        description="Inspection time",
    )
    
    # Rework requirements
    rework_required: bool = Field(
        False,
        description="Whether rework is needed",
    )
    rework_details: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Details of required rework",
    )
    rework_deadline: Union[Date, None] = Field(
        None,
        description="Deadline for completing rework",
    )
    
    # Sign-off
    customer_acceptance: Union[bool, None] = Field(
        None,
        description="Customer/requester acceptance",
    )
    customer_feedback: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Customer feedback",
    )
    
    # Photos
    inspection_photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=20,
        description="Quality inspection photographs",
    )

    @field_validator("inspection_date")
    @classmethod
    def validate_inspection_date(cls, v: Date) -> Date:
        """Validate inspection Date is not in future."""
        if v > Date.today():
            raise ValueError("Inspection Date cannot be in the future")
        return v

    @field_validator(
        "quality_check_notes",
        "defects_found",
        "rework_details",
        "customer_feedback",
    )
    @classmethod
    def normalize_text(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_rework_requirements(self) -> "QualityCheck":
        """
        Validate rework information consistency.
        
        If rework required, details and deadline should be provided.
        """
        if self.rework_required:
            if not self.rework_details:
                raise ValueError(
                    "Rework details are required when rework is needed"
                )
            
            if not self.rework_deadline:
                raise ValueError(
                    "Rework deadline is required when rework is needed"
                )
            
            # Rework deadline should be in future
            if self.rework_deadline < Date.today():
                raise ValueError("Rework deadline cannot be in the past")
            
            # Quality check should fail if rework needed
            if self.quality_check_passed:
                raise ValueError(
                    "Quality check cannot pass if rework is required"
                )
        
        return self

    @model_validator(mode="after")
    def validate_critical_failures(self) -> "QualityCheck":
        """
        Validate critical checklist items.
        
        Quality check should fail if any critical item fails.
        """
        critical_failures = [
            item for item in self.checklist_items
            if item.is_critical and item.status == "fail"
        ]
        
        if critical_failures and self.quality_check_passed:
            raise ValueError(
                f"Quality check cannot pass with {len(critical_failures)} critical failures"
            )
        
        return self


class CompletionResponse(BaseSchema):
    """
    Maintenance completion response.
    
    Provides summary of completion with cost variance
    and quality status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "completed": True,
                "estimated_cost": "3000.00",
                "actual_cost": "3500.00",
                "cost_variance": "500.00",
                "within_budget": False
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
    
    # Completion status
    completed: bool = Field(
        ...,
        description="Whether work is marked as completed",
    )
    completed_at: datetime = Field(
        ...,
        description="Completion timestamp",
    )
    completed_by: UUID = Field(
        ...,
        description="User ID who completed",
    )
    completed_by_name: str = Field(
        ...,
        description="Name of person who completed",
    )
    
    # Cost summary - Using Annotated for Decimal fields
    estimated_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Original estimated cost",
    )
    actual_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Actual cost incurred",
    )
    cost_variance: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Cost variance (actual - estimated)",
    )
    cost_variance_percentage: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Cost variance as percentage",
    )
    within_budget: bool = Field(
        ...,
        description="Whether work was completed within budget",
    )
    
    # Quality status
    quality_checked: bool = Field(
        ...,
        description="Whether quality check was performed",
    )
    quality_check_passed: Union[bool, None] = Field(
        None,
        description="Quality check result (if performed)",
    )
    quality_rating: Union[int, None] = Field(
        None,
        ge=1,
        le=5,
        description="Quality rating (1-5 stars)",
    )
    
    # Timeline
    actual_completion_date: Date = Field(
        ...,
        description="Actual completion Date",
    )
    total_days_taken: Union[int, None] = Field(
        None,
        ge=0,
        description="Total days from request to completion",
    )
    
    # Response message
    message: str = Field(
        ...,
        description="Human-readable response message",
    )
    
    # Next steps
    follow_up_required: bool = Field(
        default=False,
        description="Whether follow-up is needed",
    )
    warranty_applicable: bool = Field(
        default=False,
        description="Whether warranty applies",
    )

    @field_validator(
        "estimated_cost",
        "actual_cost",
        "cost_variance",
        "cost_variance_percentage",
    )
    @classmethod
    def round_decimals(cls, v: Decimal) -> Decimal:
        """Round decimal values to 2 places."""
        return round(v, 2)


class CompletionCertificate(BaseSchema):
    """
    Work completion certificate.
    
    Formal certificate documenting completed maintenance work
    with all details, parties, and warranties.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "certificate_number": "CERT-2024-001",
                "work_title": "Ceiling fan replacement",
                "completed_by": "John Technician",
                "verified_by": "Supervisor Smith",
                "approved_by": "Admin Manager"
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
    certificate_number: str = Field(
        ...,
        description="Unique certificate number",
    )
    
    # Work details
    work_title: str = Field(
        ...,
        description="Work title/description",
    )
    work_description: str = Field(
        ...,
        description="Detailed work description",
    )
    work_category: str = Field(
        ...,
        description="Work category",
    )
    materials_used: List[MaterialItem] = Field(
        default_factory=list,
        description="Materials used in work",
    )
    labor_hours: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total labor hours",
    )
    
    # Cost summary
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total work cost",
    )
    cost_breakdown: Union[dict, None] = Field(
        None,
        description="Detailed cost breakdown",
    )
    
    # Parties involved
    completed_by: str = Field(
        ...,
        description="Person/team who completed work",
    )
    completed_by_designation: Union[str, None] = Field(
        None,
        description="Designation of person who completed",
    )
    verified_by: str = Field(
        ...,
        description="Person who verified completion",
    )
    verified_by_designation: Union[str, None] = Field(
        None,
        description="Designation of verifier",
    )
    approved_by: str = Field(
        ...,
        description="Person who approved completion",
    )
    approved_by_designation: Union[str, None] = Field(
        None,
        description="Designation of approver",
    )
    
    # Dates
    work_start_date: Date = Field(
        ...,
        description="Work start Date",
    )
    completion_date: Date = Field(
        ...,
        description="Work completion Date",
    )
    verification_date: Date = Field(
        ...,
        description="Verification Date",
    )
    certificate_issue_date: Date = Field(
        ...,
        description="Certificate issue Date",
    )
    
    # Warranty
    warranty_applicable: bool = Field(
        default=False,
        description="Whether warranty applies",
    )
    warranty_period_months: Union[int, None] = Field(
        None,
        ge=0,
        le=120,
        description="Warranty period in months",
    )
    warranty_terms: Union[str, None] = Field(
        None,
        description="Warranty terms and conditions",
    )
    warranty_valid_until: Union[Date, None] = Field(
        None,
        description="Warranty expiry Date",
    )
    
    # Quality assurance
    quality_rating: Union[int, None] = Field(
        None,
        ge=1,
        le=5,
        description="Quality rating",
    )
    quality_remarks: Union[str, None] = Field(
        None,
        description="Quality remarks",
    )
    
    # Digital signatures (placeholders)
    completed_by_signature: Union[str, None] = Field(
        None,
        description="Completed by signature data",
    )
    verified_by_signature: Union[str, None] = Field(
        None,
        description="Verified by signature data",
    )
    approved_by_signature: Union[str, None] = Field(
        None,
        description="Approved by signature data",
    )

    @field_validator("total_cost", "labor_hours")
    @classmethod
    def round_decimals(cls, v: Decimal) -> Decimal:
        """Round decimal values."""
        return round(v, 2)

    @model_validator(mode="after")
    def validate_dates_sequence(self) -> "CompletionCertificate":
        """
        Validate dates are in logical sequence.
        
        Start < Completion <= Verification <= Certificate Issue
        """
        if self.work_start_date > self.completion_date:
            raise ValueError("Start Date must be before completion Date")
        
        if self.completion_date > self.verification_date:
            raise ValueError("Completion Date must be before verification Date")
        
        if self.verification_date > self.certificate_issue_date:
            raise ValueError("Verification Date must be before certificate issue Date")
        
        return self

    @model_validator(mode="after")
    def validate_warranty_details(self) -> "CompletionCertificate":
        """
        Validate warranty information.
        
        If warranty applicable, all warranty details should be provided.
        """
        if self.warranty_applicable:
            if not self.warranty_period_months:
                raise ValueError(
                    "Warranty period is required when warranty is applicable"
                )
            
            if not self.warranty_terms:
                raise ValueError(
                    "Warranty terms are required when warranty is applicable"
                )
            
            if not self.warranty_valid_until:
                raise ValueError(
                    "Warranty expiry Date is required when warranty is applicable"
                )
        
        return self