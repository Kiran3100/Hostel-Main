# app/models/maintenance/maintenance_completion.py
"""
Maintenance completion models.

Completion tracking with quality checks, material usage,
and certification documentation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin, MediaMixin, AuditMixin


class MaintenanceCompletion(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, MediaMixin, AuditMixin):
    """
    Maintenance work completion record.
    
    Comprehensive completion tracking with work details,
    materials, labor, and quality verification.
    """
    
    __tablename__ = "maintenance_completions"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Related maintenance request",
    )
    
    completed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="User who completed the work",
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Completion timestamp",
    )
    
    # Work details
    work_notes = Column(
        Text,
        nullable=False,
        comment="Detailed notes about work performed",
    )
    
    work_summary = Column(
        String(500),
        nullable=True,
        comment="Brief work summary",
    )
    
    # Labor tracking
    labor_hours = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Total labor hours spent",
    )
    
    labor_rate_per_hour = Column(
        Numeric(8, 2),
        nullable=True,
        comment="Labor rate per hour",
    )
    
    number_of_workers = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of workers involved",
    )
    
    # Cost breakdown
    materials_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total materials cost",
    )
    
    labor_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total labor cost",
    )
    
    vendor_charges = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="External vendor charges",
    )
    
    other_costs = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Other miscellaneous costs",
    )
    
    actual_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total actual cost",
    )
    
    cost_breakdown = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Detailed cost breakdown",
    )
    
    # Timeline
    actual_start_date = Column(
        Date,
        nullable=True,
        comment="Actual work start date",
    )
    
    actual_completion_date = Column(
        Date,
        nullable=False,
        comment="Actual completion date",
    )
    
    total_working_days = Column(
        Integer,
        nullable=True,
        comment="Total working days taken",
    )
    
    # Follow-up
    follow_up_required = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether follow-up inspection needed",
    )
    
    follow_up_notes = Column(
        Text,
        nullable=True,
        comment="Follow-up requirements",
    )
    
    follow_up_date = Column(
        Date,
        nullable=True,
        comment="Scheduled follow-up date",
    )
    
    # Warranty
    warranty_applicable = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether warranty applies to this work",
    )
    
    warranty_period_months = Column(
        Integer,
        nullable=True,
        comment="Warranty period in months",
    )
    
    warranty_terms = Column(
        Text,
        nullable=True,
        comment="Warranty terms and conditions",
    )
    
    warranty_expiry_date = Column(
        Date,
        nullable=True,
        comment="Warranty expiry date",
    )
    
    # Quality verification
    quality_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether quality was verified",
    )
    
    quality_verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who verified quality",
    )
    
    quality_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quality verification timestamp",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional flexible metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="completion_record"
    )
    completer = relationship(
        "User",
        foreign_keys=[completed_by],
        back_populates="completed_maintenance"
    )
    quality_verifier = relationship(
        "User",
        foreign_keys=[quality_verified_by]
    )
    materials = relationship(
        "MaintenanceMaterial",
        back_populates="completion",
        cascade="all, delete-orphan"
    )
    quality_checks = relationship(
        "MaintenanceQualityCheck",
        back_populates="completion",
        cascade="all, delete-orphan"
    )
    certificate = relationship(
        "MaintenanceCertificate",
        back_populates="completion",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "labor_hours >= 0",
            name="ck_completion_labor_hours_positive"
        ),
        CheckConstraint(
            "labor_rate_per_hour >= 0",
            name="ck_completion_labor_rate_positive"
        ),
        CheckConstraint(
            "number_of_workers >= 1",
            name="ck_completion_workers_positive"
        ),
        CheckConstraint(
            "materials_cost >= 0",
            name="ck_completion_materials_cost_positive"
        ),
        CheckConstraint(
            "labor_cost >= 0",
            name="ck_completion_labor_cost_positive"
        ),
        CheckConstraint(
            "vendor_charges >= 0",
            name="ck_completion_vendor_charges_positive"
        ),
        CheckConstraint(
            "other_costs >= 0",
            name="ck_completion_other_costs_positive"
        ),
        CheckConstraint(
            "actual_cost >= 0",
            name="ck_completion_actual_cost_positive"
        ),
        CheckConstraint(
            "total_working_days >= 0",
            name="ck_completion_working_days_positive"
        ),
        CheckConstraint(
            "warranty_period_months >= 0",
            name="ck_completion_warranty_period_positive"
        ),
        Index("idx_completion_completed_by", "completed_by", "completed_at"),
        Index("idx_completion_date", "actual_completion_date"),
        {"comment": "Maintenance work completion records"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceCompletion request={self.maintenance_request_id}>"
    
    @validates("labor_hours", "labor_rate_per_hour", "materials_cost", "labor_cost", "vendor_charges", "other_costs", "actual_cost")
    def validate_positive_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate amounts are positive."""
        if value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @hybrid_property
    def total_cost_calculated(self) -> Decimal:
        """Calculate total cost from components."""
        return (
            self.materials_cost +
            self.labor_cost +
            self.vendor_charges +
            self.other_costs
        )
    
    @hybrid_property
    def is_within_budget(self) -> bool:
        """Check if completion was within approved budget."""
        if hasattr(self.maintenance_request, 'approved_cost') and self.maintenance_request.approved_cost:
            return self.actual_cost <= self.maintenance_request.approved_cost
        return True


class MaintenanceMaterial(BaseModel, UUIDMixin, TimestampModel):
    """
    Materials used in maintenance work.
    
    Tracks individual materials with quantities and costs
    for accurate billing and inventory management.
    """
    
    __tablename__ = "maintenance_materials"
    
    completion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_completions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related completion record",
    )
    
    # Material details
    material_name = Column(
        String(255),
        nullable=False,
        comment="Material/item name",
    )
    
    material_code = Column(
        String(50),
        nullable=True,
        comment="Material code/SKU",
    )
    
    category = Column(
        String(100),
        nullable=True,
        comment="Material category",
    )
    
    # Quantity
    quantity = Column(
        Numeric(10, 3),
        nullable=False,
        comment="Quantity used",
    )
    
    unit = Column(
        String(20),
        nullable=False,
        comment="Unit of measurement",
    )
    
    # Cost
    unit_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Cost per unit",
    )
    
    total_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total cost for this material",
    )
    
    # Supplier information
    supplier = Column(
        String(255),
        nullable=True,
        comment="Material supplier name",
    )
    
    supplier_invoice = Column(
        String(100),
        nullable=True,
        comment="Supplier invoice number",
    )
    
    # Warranty
    warranty_months = Column(
        Integer,
        nullable=True,
        comment="Material warranty period in months",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional material metadata",
    )
    
    # Relationships
    completion = relationship(
        "MaintenanceCompletion",
        back_populates="materials"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_material_quantity_positive"
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_material_unit_cost_positive"
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="ck_material_total_cost_positive"
        ),
        CheckConstraint(
            "warranty_months >= 0",
            name="ck_material_warranty_positive"
        ),
        Index("idx_material_completion", "completion_id"),
        {"comment": "Materials used in maintenance work"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceMaterial {self.material_name} qty={self.quantity} {self.unit}>"
    
    @validates("quantity", "unit_cost", "total_cost")
    def validate_positive_values(self, key: str, value: Decimal) -> Decimal:
        """Validate numeric values are positive."""
        if key == "quantity" and value <= 0:
            raise ValueError("Quantity must be positive")
        if key in ["unit_cost", "total_cost"] and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value


class MaintenanceQualityCheck(BaseModel, UUIDMixin, TimestampModel):
    """
    Quality check record for completed maintenance work.
    
    Inspection and verification of work quality with
    detailed checklist and approval/rejection.
    """
    
    __tablename__ = "maintenance_quality_checks"
    
    completion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_completions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related completion record",
    )
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    # Overall result
    quality_check_passed = Column(
        Boolean,
        nullable=False,
        comment="Overall quality check result",
    )
    
    overall_rating = Column(
        Integer,
        nullable=True,
        comment="Overall quality rating (1-5 stars)",
    )
    
    # Inspector details
    checked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="User who performed quality check",
    )
    
    inspection_date = Column(
        Date,
        nullable=False,
        comment="Inspection date",
    )
    
    inspection_time = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Inspection time",
    )
    
    # Inspection details
    quality_check_notes = Column(
        Text,
        nullable=True,
        comment="Detailed quality check notes",
    )
    
    defects_found = Column(
        Text,
        nullable=True,
        comment="Any defects or issues found",
    )
    
    # Rework requirements
    rework_required = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether rework is needed",
    )
    
    rework_details = Column(
        Text,
        nullable=True,
        comment="Details of required rework",
    )
    
    rework_deadline = Column(
        Date,
        nullable=True,
        comment="Deadline for completing rework",
    )
    
    # Customer acceptance
    customer_acceptance = Column(
        Boolean,
        nullable=True,
        comment="Customer/requester acceptance",
    )
    
    customer_feedback = Column(
        Text,
        nullable=True,
        comment="Customer feedback",
    )
    
    # Checklist results
    checklist_results = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Detailed checklist item results",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional quality check metadata",
    )
    
    # Relationships
    completion = relationship(
        "MaintenanceCompletion",
        back_populates="quality_checks"
    )
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="quality_checks"
    )
    inspector = relationship("User")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "overall_rating >= 1 AND overall_rating <= 5",
            name="ck_quality_rating_range"
        ),
        Index("idx_quality_check_inspector", "checked_by", "inspection_date"),
        Index("idx_quality_check_passed", "quality_check_passed"),
        {"comment": "Quality check records for completed maintenance"}
    )
    
    def __repr__(self) -> str:
        status = "Passed" if self.quality_check_passed else "Failed"
        return f"<MaintenanceQualityCheck {self.maintenance_request_id} - {status}>"
    
    @validates("overall_rating")
    def validate_rating(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Overall rating must be between 1 and 5")
        return value


class MaintenanceCertificate(BaseModel, UUIDMixin, TimestampModel):
    """
    Work completion certificate.
    
    Formal certificate documenting completed maintenance work
    with all details, parties, and warranties.
    """
    
    __tablename__ = "maintenance_certificates"
    
    completion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_completions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Related completion record",
    )
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    certificate_number = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Unique certificate number",
    )
    
    # Work details
    work_title = Column(
        String(255),
        nullable=False,
        comment="Work title/description",
    )
    
    work_description = Column(
        Text,
        nullable=False,
        comment="Detailed work description",
    )
    
    work_category = Column(
        String(100),
        nullable=False,
        comment="Work category",
    )
    
    labor_hours = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Total labor hours",
    )
    
    total_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total work cost",
    )
    
    cost_breakdown = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Detailed cost breakdown",
    )
    
    # Parties involved
    completed_by = Column(
        String(255),
        nullable=False,
        comment="Person/team who completed work",
    )
    
    completed_by_designation = Column(
        String(100),
        nullable=True,
        comment="Designation of person who completed",
    )
    
    verified_by = Column(
        String(255),
        nullable=False,
        comment="Person who verified completion",
    )
    
    verified_by_designation = Column(
        String(100),
        nullable=True,
        comment="Designation of verifier",
    )
    
    approved_by = Column(
        String(255),
        nullable=False,
        comment="Person who approved completion",
    )
    
    approved_by_designation = Column(
        String(100),
        nullable=True,
        comment="Designation of approver",
    )
    
    # Dates
    work_start_date = Column(
        Date,
        nullable=False,
        comment="Work start date",
    )
    
    completion_date = Column(
        Date,
        nullable=False,
        comment="Work completion date",
    )
    
    verification_date = Column(
        Date,
        nullable=False,
        comment="Verification date",
    )
    
    certificate_issue_date = Column(
        Date,
        nullable=False,
        comment="Certificate issue date",
    )
    
    # Warranty
    warranty_applicable = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether warranty applies",
    )
    
    warranty_period_months = Column(
        Integer,
        nullable=True,
        comment="Warranty period in months",
    )
    
    warranty_terms = Column(
        Text,
        nullable=True,
        comment="Warranty terms and conditions",
    )
    
    warranty_valid_until = Column(
        Date,
        nullable=True,
        comment="Warranty expiry date",
    )
    
    # Quality assurance
    quality_rating = Column(
        Integer,
        nullable=True,
        comment="Quality rating",
    )
    
    quality_remarks = Column(
        Text,
        nullable=True,
        comment="Quality remarks",
    )
    
    # Digital signatures (base64 encoded)
    completed_by_signature = Column(
        Text,
        nullable=True,
        comment="Completed by signature data",
    )
    
    verified_by_signature = Column(
        Text,
        nullable=True,
        comment="Verified by signature data",
    )
    
    approved_by_signature = Column(
        Text,
        nullable=True,
        comment="Approved by signature data",
    )
    
    # Relationships
    completion = relationship(
        "MaintenanceCompletion",
        back_populates="certificate"
    )
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="certificates"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "labor_hours >= 0",
            name="ck_certificate_labor_hours_positive"
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="ck_certificate_total_cost_positive"
        ),
        CheckConstraint(
            "warranty_period_months >= 0",
            name="ck_certificate_warranty_period_positive"
        ),
        CheckConstraint(
            "quality_rating >= 1 AND quality_rating <= 5",
            name="ck_certificate_quality_rating_range"
        ),
        Index("idx_certificate_number", "certificate_number"),
        Index("idx_certificate_issue_date", "certificate_issue_date"),
        {"comment": "Work completion certificates"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceCertificate {self.certificate_number}>"