# --- File: app/schemas/maintenance/maintenance_vendor.py ---
"""
Maintenance vendor management schemas.

Provides schemas for vendor registration, performance tracking,
contract management, and vendor analytics.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional, Union

from pydantic import (
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)
from uuid import UUID

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)

__all__ = [
    "MaintenanceVendor",
    "VendorCreate",
    "VendorUpdate",
    "VendorPerformanceReview",
    "VendorPerformanceCreate",
    "VendorMetrics",
    "VendorContract",
    "VendorContractCreate",
]


class VendorCreate(BaseCreateSchema):
    """
    Create new maintenance vendor.
    
    Registration of vendor with contact and service details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "company_name": "ABC Electricals Pvt Ltd",
                "contact_person": "John Vendor",
                "contact_phone": "+919876543210",
                "contact_email": "john@abcelectricals.com",
                "service_categories": ["electrical", "hvac"],
                "is_verified": False
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Company details
    company_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Vendor company name",
    )
    business_registration_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Business registration/license number",
    )
    tax_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Tax ID/GST number",
    )
    
    # Contact details
    contact_person: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Primary contact person name",
    )
    contact_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Primary contact phone",
    )
    contact_email: EmailStr = Field(
        ...,
        description="Primary contact email",
    )
    alternate_phone: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Alternate contact phone",
    )
    alternate_email: Optional[EmailStr] = Field(
        None,
        description="Alternate contact email",
    )
    
    # Address
    address: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Business address",
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City",
    )
    state: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="State/Province",
    )
    postal_code: str = Field(
        ...,
        pattern=r"^\d{6}$",
        description="Postal/ZIP code",
    )
    country: str = Field(
        default="India",
        max_length=100,
        description="Country",
    )
    
    # Services
    service_categories: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Service categories (plumbing, electrical, etc.)",
    )
    service_description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed service description",
    )
    specializations: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Specific specializations",
    )
    
    # Business information
    years_in_business: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Years in business",
    )
    team_size: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Team size",
    )
    service_area_radius_km: Optional[int] = Field(
        None,
        ge=1,
        le=500,
        description="Service area radius in kilometers",
    )
    
    # Availability
    available_24x7: bool = Field(
        default=False,
        description="Available 24/7 for emergencies",
    )
    working_hours: Optional[str] = Field(
        None,
        max_length=200,
        description="Working hours (e.g., Mon-Fri 9AM-6PM)",
    )
    emergency_contact: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact number",
    )
    
    # Insurance and compliance
    is_insured: bool = Field(
        default=False,
        description="Has liability insurance",
    )
    insurance_provider: Optional[str] = Field(
        None,
        max_length=255,
        description="Insurance provider name",
    )
    insurance_policy_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Insurance policy number",
    )
    insurance_expiry_date: Optional[Date] = Field(
        None,
        description="Insurance expiry date",
    )
    
    # Certifications
    certifications: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Professional certifications",
    )
    licenses: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Professional licenses",
    )
    
    # References
    references: Optional[List[Dict[str, str]]] = Field(
        None,
        max_length=5,
        description="Business references",
    )
    website: Optional[HttpUrl] = Field(
        None,
        description="Company website",
    )
    
    # Verification
    is_verified: bool = Field(
        default=False,
        description="Whether vendor is verified",
    )
    verified_by: Optional[UUID] = Field(
        None,
        description="User who verified vendor",
    )
    
    # Banking (for payments)
    bank_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Bank name",
    )
    account_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Bank account number",
    )
    ifsc_code: Optional[str] = Field(
        None,
        pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$",
        description="IFSC code (for Indian banks)",
    )
    
    # Notes
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("contact_phone", "alternate_phone", "emergency_contact")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return None

    @field_validator("service_categories")
    @classmethod
    def validate_service_categories(cls, v: List[str]) -> List[str]:
        """Validate and normalize service categories."""
        valid_categories = {
            "plumbing",
            "electrical",
            "hvac",
            "carpentry",
            "painting",
            "masonry",
            "roofing",
            "flooring",
            "landscaping",
            "pest_control",
            "cleaning",
            "security",
            "general",
        }
        
        normalized = [cat.lower().strip() for cat in v]
        
        for cat in normalized:
            if cat not in valid_categories:
                raise ValueError(
                    f"Invalid service category '{cat}'. "
                    f"Must be one of: {', '.join(valid_categories)}"
                )
        
        return normalized

    @model_validator(mode="after")
    def validate_verification_consistency(self):
        """Validate verification requirements."""
        if self.is_verified and not self.verified_by:
            raise ValueError("verified_by is required when vendor is verified")
        
        return self


class VendorUpdate(BaseUpdateSchema):
    """
    Update vendor details.
    
    Allows updating contact information, services, and verification status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contact_phone": "+919876543210",
                "contact_email": "newemail@abcelectricals.com",
                "service_categories": ["electrical", "hvac", "plumbing"],
                "is_active": True
            }
        }
    )

    # Contact updates
    contact_person: Optional[str] = Field(
        None,
        min_length=2,
        max_length=255,
        description="Updated contact person",
    )
    contact_phone: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Updated phone",
    )
    contact_email: Optional[EmailStr] = Field(
        None,
        description="Updated email",
    )
    alternate_phone: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Updated alternate phone",
    )
    
    # Address updates
    address: Optional[str] = Field(
        None,
        min_length=10,
        max_length=500,
        description="Updated address",
    )
    city: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Updated city",
    )
    
    # Service updates
    service_categories: Optional[List[str]] = Field(
        None,
        min_length=1,
        max_length=20,
        description="Updated service categories",
    )
    service_description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated service description",
    )
    
    # Availability updates
    available_24x7: Optional[bool] = Field(
        None,
        description="Updated 24/7 availability",
    )
    working_hours: Optional[str] = Field(
        None,
        max_length=200,
        description="Updated working hours",
    )
    
    # Insurance updates
    is_insured: Optional[bool] = Field(
        None,
        description="Updated insurance status",
    )
    insurance_expiry_date: Optional[Date] = Field(
        None,
        description="Updated insurance expiry",
    )
    
    # Status
    is_active: Optional[bool] = Field(
        None,
        description="Active status",
    )
    is_verified: Optional[bool] = Field(
        None,
        description="Verification status",
    )
    
    # Notes
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated notes",
    )

    @field_validator("contact_phone", "alternate_phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return None


class MaintenanceVendor(BaseResponseSchema):
    """
    Maintenance vendor response.
    
    Complete vendor information with performance metrics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "company_name": "ABC Electricals Pvt Ltd",
                "contact_person": "John Vendor",
                "contact_phone": "+919876543210",
                "service_categories": ["electrical", "hvac"],
                "average_rating": "4.5",
                "total_jobs": 50,
                "is_active": True
            }
        }
    )

    company_name: str = Field(
        ...,
        description="Vendor company name",
    )
    business_registration_number: Optional[str] = Field(
        None,
        description="Business registration number",
    )
    tax_id: Optional[str] = Field(
        None,
        description="Tax ID/GST number",
    )
    
    # Contact details
    contact_person: str = Field(
        ...,
        description="Primary contact person",
    )
    contact_phone: str = Field(
        ...,
        description="Primary contact phone",
    )
    contact_email: EmailStr = Field(
        ...,
        description="Primary contact email",
    )
    alternate_phone: Optional[str] = Field(
        None,
        description="Alternate phone",
    )
    
    # Address
    address: str = Field(
        ...,
        description="Business address",
    )
    city: str = Field(
        ...,
        description="City",
    )
    state: str = Field(
        ...,
        description="State",
    )
    postal_code: str = Field(
        ...,
        description="Postal code",
    )
    
    # Services
    service_categories: List[str] = Field(
        ...,
        description="Service categories",
    )
    service_description: Optional[str] = Field(
        None,
        description="Service description",
    )
    specializations: Optional[List[str]] = Field(
        None,
        description="Specializations",
    )
    
    # Business info
    years_in_business: Optional[int] = Field(
        None,
        description="Years in business",
    )
    team_size: Optional[int] = Field(
        None,
        description="Team size",
    )
    
    # Availability
    available_24x7: bool = Field(
        ...,
        description="24/7 availability",
    )
    working_hours: Optional[str] = Field(
        None,
        description="Working hours",
    )
    
    # Insurance
    is_insured: bool = Field(
        ...,
        description="Has insurance",
    )
    insurance_expiry_date: Optional[Date] = Field(
        None,
        description="Insurance expiry date",
    )
    
    # Performance metrics
    average_rating: Union[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)], None] = Field(
        None,
        description="Average performance rating",
    )
    total_jobs: int = Field(
        default=0,
        ge=0,
        description="Total jobs completed",
    )
    completed_jobs: int = Field(
        default=0,
        ge=0,
        description="Successfully completed jobs",
    )
    on_time_completion_rate: Union[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)], None] = Field(
        None,
        description="On-time completion percentage",
    )
    
    # Status
    is_active: bool = Field(
        ...,
        description="Active status",
    )
    is_verified: bool = Field(
        ...,
        description="Verification status",
    )
    
    # Metadata
    registered_at: datetime = Field(
        ...,
        description="Registration timestamp",
    )
    last_job_date: Optional[Date] = Field(
        None,
        description="Last job date",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate job completion rate."""
        if self.total_jobs == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_jobs) / Decimal(self.total_jobs) * 100,
            2,
        )

    @computed_field  # type: ignore[misc]
    @property
    def performance_tier(self) -> str:
        """Calculate performance tier based on metrics."""
        if not self.average_rating:
            return "unrated"
        
        rating = float(self.average_rating)
        on_time = float(self.on_time_completion_rate or 0)
        
        if rating >= 4.5 and on_time >= 90:
            return "platinum"
        elif rating >= 4.0 and on_time >= 80:
            return "gold"
        elif rating >= 3.5 and on_time >= 70:
            return "silver"
        elif rating >= 3.0:
            return "bronze"
        else:
            return "needs_improvement"


class VendorPerformanceCreate(BaseCreateSchema):
    """
    Create vendor performance review.
    
    Submit performance review after job completion.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "overall_rating": 4,
                "quality_rating": 5,
                "timeliness_rating": 4,
                "communication_rating": 4,
                "review_comments": "Excellent work quality, completed on time"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request ID",
    )
    reviewed_by: UUID = Field(
        ...,
        description="User submitting review",
    )
    
    # Ratings (1-5 stars)
    overall_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall rating (1-5 stars)",
    )
    quality_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Work quality rating",
    )
    timeliness_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Timeliness rating",
    )
    communication_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Communication rating",
    )
    professionalism_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Professionalism rating",
    )
    
    # Review details
    review_comments: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed review comments",
    )
    strengths: Optional[str] = Field(
        None,
        max_length=500,
        description="Vendor strengths",
    )
    areas_for_improvement: Optional[str] = Field(
        None,
        max_length=500,
        description="Areas needing improvement",
    )
    
    # Specific metrics
    was_on_time: bool = Field(
        ...,
        description="Whether work completed on time",
    )
    within_budget: bool = Field(
        ...,
        description="Whether work completed within budget",
    )
    would_recommend: bool = Field(
        ...,
        description="Would recommend this vendor",
    )
    would_use_again: bool = Field(
        ...,
        description="Would use this vendor again",
    )
    
    # Issues
    issues_encountered: Optional[str] = Field(
        None,
        max_length=1000,
        description="Any issues encountered",
    )
    complaints: Optional[str] = Field(
        None,
        max_length=1000,
        description="Specific complaints",
    )

    @field_validator("review_comments")
    @classmethod
    def validate_comments(cls, v: str) -> str:
        """Validate review comments are meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Review comments must be at least 10 characters")
        return v


class VendorPerformanceReview(BaseResponseSchema):
    """
    Vendor performance review response.
    
    Complete performance review details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor_id": "123e4567-e89b-12d3-a456-426614174001",
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174002",
                "overall_rating": 4,
                "quality_rating": 5,
                "review_comments": "Excellent work",
                "would_recommend": True
            }
        }
    )

    vendor_id: UUID = Field(
        ...,
        description="Vendor unique identifier",
    )
    vendor_name: str = Field(
        ...,
        description="Vendor company name",
    )
    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request ID",
    )
    reviewed_by: UUID = Field(
        ...,
        description="Reviewer user ID",
    )
    reviewed_by_name: str = Field(
        ...,
        description="Reviewer name",
    )
    review_date: Date = Field(
        ...,
        description="Review date",
    )
    
    # Ratings
    overall_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall rating",
    )
    quality_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality rating",
    )
    timeliness_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Timeliness rating",
    )
    communication_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Communication rating",
    )
    professionalism_rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Professionalism rating",
    )
    
    # Comments
    review_comments: str = Field(
        ...,
        description="Review comments",
    )
    strengths: Optional[str] = Field(
        None,
        description="Strengths",
    )
    areas_for_improvement: Optional[str] = Field(
        None,
        description="Areas for improvement",
    )
    
    # Metrics
    was_on_time: bool = Field(
        ...,
        description="Completed on time",
    )
    within_budget: bool = Field(
        ...,
        description="Within budget",
    )
    would_recommend: bool = Field(
        ...,
        description="Would recommend",
    )
    would_use_again: bool = Field(
        ...,
        description="Would use again",
    )

    @computed_field  # type: ignore[misc]
    @property
    def average_category_rating(self) -> Decimal:
        """Calculate average of all category ratings."""
        total = (
            self.quality_rating
            + self.timeliness_rating
            + self.communication_rating
            + self.professionalism_rating
        )
        return round(Decimal(total) / Decimal("4"), 2)


class VendorMetrics(BaseSchema):
    """
    Comprehensive vendor performance metrics.
    
    Aggregated metrics for vendor performance analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vendor_id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor_name": "ABC Electricals",
                "total_jobs": 50,
                "completed_jobs": 48,
                "average_rating": "4.5",
                "on_time_completion_rate": "92.00",
                "would_recommend_rate": "95.00"
            }
        }
    )

    vendor_id: UUID = Field(
        ...,
        description="Vendor unique identifier",
    )
    vendor_name: str = Field(
        ...,
        description="Vendor company name",
    )
    period_months: int = Field(
        ...,
        ge=1,
        description="Analysis period in months",
    )
    
    # Job statistics
    total_jobs: int = Field(
        ...,
        ge=0,
        description="Total jobs assigned",
    )
    completed_jobs: int = Field(
        ...,
        ge=0,
        description="Completed jobs",
    )
    in_progress_jobs: int = Field(
        default=0,
        ge=0,
        description="Jobs in progress",
    )
    cancelled_jobs: int = Field(
        default=0,
        ge=0,
        description="Cancelled jobs",
    )
    
    # Performance ratings
    average_rating: Union[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)], None] = Field(
        None,
        description="Average overall rating",
    )
    average_quality_rating: Union[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)], None] = Field(
        None,
        description="Average quality rating",
    )
    average_timeliness_rating: Union[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)], None] = Field(
        None,
        description="Average timeliness rating",
    )
    
    # Completion metrics
    completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Job completion rate percentage",
    )
    on_time_completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="On-time completion percentage",
    )
    within_budget_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Within budget percentage",
    )
    
    # Cost metrics
    total_spent: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total amount spent",
    )
    average_job_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per job",
    )
    cost_variance_percentage: Union[Annotated[Decimal, Field(decimal_places=2)], None] = Field(
        None,
        description="Average cost variance from estimates",
    )
    
    # Recommendation metrics
    would_recommend_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Would recommend percentage",
    )
    would_use_again_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Would use again percentage",
    )
    
    # Issue tracking
    total_complaints: int = Field(
        default=0,
        ge=0,
        description="Total complaints received",
    )
    total_reviews: int = Field(
        default=0,
        ge=0,
        description="Total reviews received",
    )
    
    # Timeline
    average_completion_days: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Average days to complete",
    )
    average_response_time_hours: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Average response time in hours",
    )

    @computed_field  # type: ignore[misc]
    @property
    def performance_score(self) -> Decimal:
        """Calculate overall performance score (0-100)."""
        if not self.average_rating:
            return Decimal("0.00")
        
        # Weighted score
        rating_score = float(self.average_rating) * 20  # Convert 1-5 to 0-100
        completion_score = float(self.completion_rate)
        timeliness_score = float(self.on_time_completion_rate)
        
        overall = (
            rating_score * 0.4
            + completion_score * 0.3
            + timeliness_score * 0.3
        )
        
        return round(Decimal(str(overall)), 2)


class VendorContractCreate(BaseCreateSchema):
    """
    Create vendor contract.
    
    Define contract terms and rates with vendor.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_title": "Annual Electrical Maintenance Contract",
                "contract_type": "annual",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "contract_value": "500000.00",
                "payment_terms": "Monthly billing"
            }
        }
    )

    contract_title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Contract title",
    )
    contract_type: str = Field(
        ...,
        pattern=r"^(one_time|monthly|quarterly|annual|multi_year)$",
        description="Contract type",
    )
    
    # Duration
    start_date: Date = Field(
        ...,
        description="Contract start date",
    )
    end_date: Date = Field(
        ...,
        description="Contract end date",
    )
    auto_renew: bool = Field(
        default=False,
        description="Auto-renew on expiry",
    )
    
    # Financial
    contract_value: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total contract value",
    )
    payment_terms: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Payment terms and conditions",
    )
    payment_schedule: Optional[str] = Field(
        None,
        pattern=r"^(upfront|milestone|monthly|quarterly|on_completion)$",
        description="Payment schedule",
    )
    
    # Scope
    scope_of_work: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Detailed scope of work",
    )
    service_categories: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Covered service categories",
    )
    exclusions: Optional[str] = Field(
        None,
        max_length=2000,
        description="Work exclusions",
    )
    
    # SLA
    response_time_hours: Optional[int] = Field(
        None,
        ge=1,
        le=168,
        description="Guaranteed response time in hours",
    )
    resolution_time_hours: Optional[int] = Field(
        None,
        ge=1,
        le=720,
        description="Guaranteed resolution time in hours",
    )
    availability_percentage: Optional[Decimal] = Field(
        None,
        ge=0,
        le=100,
        description="Guaranteed availability percentage",
    )
    
    # Penalties and incentives
    penalty_clause: Optional[str] = Field(
        None,
        max_length=1000,
        description="Penalty terms for SLA breaches",
    )
    incentive_clause: Optional[str] = Field(
        None,
        max_length=1000,
        description="Performance incentives",
    )
    
    # Termination
    termination_notice_days: int = Field(
        default=30,
        ge=0,
        le=365,
        description="Termination notice period in days",
    )
    termination_terms: Optional[str] = Field(
        None,
        max_length=1000,
        description="Contract termination terms",
    )
    
    # Documents
    contract_document_url: Optional[str] = Field(
        None,
        description="URL to contract document",
    )
    signed_copy_url: Optional[str] = Field(
        None,
        description="URL to signed contract copy",
    )

    @model_validator(mode="after")
    def validate_dates(self):
        """Validate contract dates."""
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date")
        
        # Contract shouldn't be longer than 5 years
        duration_years = (self.end_date - self.start_date).days / 365
        if duration_years > 5:
            raise ValueError("Contract duration cannot exceed 5 years")
        
        return self


class VendorContract(BaseResponseSchema):
    """
    Vendor contract response.
    
    Complete contract details with status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor_id": "123e4567-e89b-12d3-a456-426614174001",
                "vendor_name": "ABC Electricals",
                "contract_title": "Annual Maintenance",
                "contract_type": "annual",
                "status": "active",
                "contract_value": "500000.00"
            }
        }
    )

    vendor_id: UUID = Field(
        ...,
        description="Vendor unique identifier",
    )
    vendor_name: str = Field(
        ...,
        description="Vendor company name",
    )
    contract_title: str = Field(
        ...,
        description="Contract title",
    )
    contract_type: str = Field(
        ...,
        description="Contract type",
    )
    
    # Duration
    start_date: Date = Field(
        ...,
        description="Start date",
    )
    end_date: Date = Field(
        ...,
        description="End date",
    )
    auto_renew: bool = Field(
        ...,
        description="Auto-renew status",
    )
    
    # Status
    status: str = Field(
        ...,
        pattern=r"^(draft|active|expired|terminated|renewed)$",
        description="Contract status",
    )
    is_active: bool = Field(
        ...,
        description="Whether contract is currently active",
    )
    
    # Financial
    contract_value: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Contract value",
    )
    amount_utilized: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Amount utilized so far",
    )
    payment_terms: str = Field(
        ...,
        description="Payment terms",
    )
    
    # Scope
    scope_of_work: str = Field(
        ...,
        description="Scope of work",
    )
    service_categories: List[str] = Field(
        ...,
        description="Service categories",
    )
    
    # SLA
    response_time_hours: Optional[int] = Field(
        None,
        description="Response time SLA",
    )
    resolution_time_hours: Optional[int] = Field(
        None,
        description="Resolution time SLA",
    )
    
    # Metadata
    created_by: UUID = Field(
        ...,
        description="User who created contract",
    )
    signed_date: Optional[Date] = Field(
        None,
        description="Contract signing date",
    )

    @computed_field  # type: ignore[misc]
    @property
    def utilization_percentage(self) -> Decimal:
        """Calculate contract value utilization percentage."""
        if self.contract_value == 0:
            return Decimal("0.00")
        return round(
            self.amount_utilized / self.contract_value * 100,
            2,
        )

    @computed_field  # type: ignore[misc]
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in contract."""
        if not self.is_active:
            return 0
        return max(0, (self.end_date - Date.today()).days)

    @computed_field  # type: ignore[misc]
    @property
    def is_expiring_soon(self) -> bool:
        """Check if contract is expiring within 30 days."""
        return 0 < self.days_remaining <= 30