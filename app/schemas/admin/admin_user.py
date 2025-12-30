"""
Admin user Pydantic schemas for API request/response validation.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.base.enums import UserRole


class AdminUserBase(BaseModel):
    """Base admin user schema with common fields."""
    
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    employee_id: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    supervisor_id: Optional[UUID] = None
    can_manage_multiple_hostels: bool = False


class AdminUserCreate(AdminUserBase):
    """Schema for creating admin users."""
    
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    profile_data: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Smith",
                "email": "john.smith@hostel.com",
                "phone": "+1234567890",
                "employee_id": "EMP001",
                "department": "Administration",
                "designation": "Admin Manager",
                "password": "SecurePass123!",
                "role": "ADMIN",
                "can_manage_multiple_hostels": False,
                "profile_data": {
                    "bio": "Experienced administrator",
                    "qualifications": "MBA in Management"
                }
            }
        }


class AdminUserUpdate(BaseModel):
    """Schema for updating admin users."""
    
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    employee_id: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    supervisor_id: Optional[UUID] = None
    can_manage_multiple_hostels: Optional[bool] = None


class AdminProfileBase(BaseModel):
    """Base admin profile schema."""
    
    bio: Optional[str] = Field(None, max_length=500)
    qualifications: Optional[str] = Field(None, max_length=300)
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    specializations: Optional[List[str]] = None
    emergency_contact: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=300)


class AdminProfile(AdminProfileBase):
    """Admin profile response schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    admin_user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminUserResponse(AdminUserBase):
    """Schema for admin user responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    role: UserRole
    status: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminUserDetail(AdminUserResponse):
    """Detailed admin user schema with relationships."""
    
    supervisor: Optional['AdminUserResponse'] = None
    subordinates_count: Optional[int] = 0
    profile: Optional[AdminProfile] = None
    last_login: Optional[datetime] = None
    login_count: int = 0


class AdminUserSearch(BaseModel):
    """Schema for admin user search parameters."""
    
    search_query: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    status: Optional[str] = Field(None, pattern=r'^(active|inactive|suspended)$')
    department: Optional[str] = Field(None, max_length=100)
    supervisor_id: Optional[UUID] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class AdminHierarchy(BaseModel):
    """Schema for admin hierarchy information."""
    
    admin_id: UUID
    admin_name: str
    role: UserRole
    department: Optional[str]
    supervisor: Optional['AdminHierarchy'] = None
    subordinates: List['AdminHierarchy'] = []
    level: int = 0


class AdminStatistics(BaseModel):
    """Schema for admin statistics."""
    
    total_admins: int
    active_admins: int
    inactive_admins: int
    suspended_admins: int
    admins_by_role: Dict[str, int]
    admins_by_department: Dict[str, int]
    recent_logins: int
    last_updated: datetime


# Update forward references
AdminUserDetail.model_rebuild()
AdminHierarchy.model_rebuild()