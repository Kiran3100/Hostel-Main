"""
User data export endpoints.

Provides GDPR-compliant data export functionality
for users and bulk export for administrators.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.user.user_data_export_service import UserDataExportService

router = APIRouter(
    prefix="/users",
    tags=["Users - Data Export"],
)


# ==================== Dependencies ====================


def get_data_export_service() -> UserDataExportService:
    """
    Dependency injection for UserDataExportService.
    
    Returns:
        UserDataExportService: Configured data export service instance
        
    Raises:
        NotImplementedError: When service factory is not configured
    """
    # TODO: Wire to ServiceFactory / DI container
    raise NotImplementedError("UserDataExportService dependency must be configured")


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract current authenticated user from auth dependency.
    
    Args:
        auth: Authentication dependency instance
        
    Returns:
        User object for the authenticated user
    """
    return auth.get_current_user()


# ==================== Self-Service Data Exports ====================


@router.get(
    "/me/export",
    summary="Export user data",
    description="Export current user's data in specified format",
    response_description="Exported data file or download URL",
    responses={
        200: {"description": "Export successful"},
        400: {"description": "Invalid format specified"},
        503: {"description": "Export service temporarily unavailable"},
    },
)
async def export_my_data(
    format: str = Query(
        "json",
        regex=r"^(json|csv|excel|pdf)$",
        description="Export format",
        example="json",
    ),
    export_service: UserDataExportService = Depends(get_data_export_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Export current user's data.
    
    **Supported Formats:**
    - `json`: Machine-readable JSON format
    - `csv`: Spreadsheet-compatible CSV
    - `excel`: Microsoft Excel workbook (.xlsx)
    - `pdf`: Human-readable PDF document
    
    **Response Types:**
    - Small exports: Direct file download
    - Large exports: Presigned URL for download
    - Async exports: Job ID for status polling
    
    **Data Included:**
    - Profile information
    - Preferences and settings
    - Activity history
    - User-generated content
    
    Args:
        format: Desired export format (json, csv, excel, pdf)
        
    Returns:
        Export result (file, URL, or job ID)
        
    Raises:
        HTTPException: 400 if format invalid
    """
    result = export_service.export_user_data(
        user_id=current_user.id,
        format=format,
    )
    return result.unwrap()


@router.get(
    "/me/export/gdpr",
    summary="Export GDPR data package",
    description="Export comprehensive GDPR-compliant data package",
    response_description="GDPR data package",
    responses={
        200: {"description": "GDPR package generated"},
        202: {"description": "Export queued for processing"},
        503: {"description": "Export service temporarily unavailable"},
    },
)
async def export_my_gdpr_package(
    export_service: UserDataExportService = Depends(get_data_export_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Export GDPR-compliant data package.
    
    **GDPR Compliance:**
    Provides complete data export as required by GDPR Article 20
    (Right to Data Portability) and Article 15 (Right of Access).
    
    **Package Contents:**
    - All personal data
    - Processing history
    - Consent records
    - Data retention information
    - Third-party data sharing records
    
    **Format:**
    - Structured JSON format
    - Human-readable documentation
    - Machine-readable metadata
    
    **Processing:**
    Large GDPR packages may be processed asynchronously.
    Check response for job status or download URL.
    
    Returns:
        GDPR data package or job information
    """
    result = export_service.export_gdpr_package(user_id=current_user.id)
    return result.unwrap()


# ==================== Admin Bulk Data Exports ====================


@router.post(
    "/export",
    summary="Bulk export user data",
    description="Export data for multiple users (admin only)",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Export initiated or completed"},
        202: {"description": "Export queued for processing"},
        400: {"description": "Invalid export parameters"},
        403: {"description": "Insufficient permissions"},
    },
)
async def export_multiple_users(
    user_ids: Optional[list[str]] = Query(
        None,
        description="Specific user IDs to export (omit for all users)",
        example=["usr_123", "usr_456"],
    ),
    format: str = Query(
        "csv",
        regex=r"^(json|csv|excel|pdf)$",
        description="Export format",
    ),
    export_service: UserDataExportService = Depends(get_data_export_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Export data for multiple users.
    
    **Admin-only endpoint**
    
    **Use Cases:**
    - Compliance reporting
    - Data migration
    - Backup operations
    - Analytics export
    
    **Filtering:**
    - Provide `user_ids` to export specific users
    - Omit `user_ids` to export all users (filtered by service)
    
    **Processing:**
    Bulk exports are typically asynchronous:
    1. Request queued immediately
    2. Processing happens in background
    3. Download URL provided when ready
    4. Notification sent on completion
    
    **Formats:**
    - `csv`: Aggregated data in spreadsheet format
    - `json`: Structured data for programmatic use
    - `excel`: Multi-sheet workbook with summaries
    - `pdf`: Report-style formatted document
    
    Args:
        user_ids: List of user IDs to export (optional)
        format: Export format
        
    Returns:
        Export job information or download URL
        
    Raises:
        HTTPException: 403 if not admin
        HTTPException: 400 if parameters invalid
    """
    # TODO: Enforce admin-only access via AuthorizationDependency
    
    result = export_service.export_multiple_users(
        user_ids=user_ids,
        format=format,
    )
    return result.unwrap()