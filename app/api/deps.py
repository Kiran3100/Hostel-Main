# D:\Last Github Push\Last\Hostel-Main\app\api\deps.py

from typing import Any, Callable

from app.core1.dependencies import (
    AdminDependency,
    AuthenticationDependency,
    AuthorizationDependency,
    CacheDependency,
    CurrentUserDependency,
    DatabaseDependency,
    FileUploadDependency,
    HostelContextDependency,
    PaginationDependency,
    StudentDependency,
    SupervisorDependency,
    SuperAdminDependency,
    TenantContextDependency,
    NotificationDependency,
    FilterDependency,
)

# Instantiate once and expose plain callables that FastAPI can use
# directly as dependencies in your route functions.
#
# Example usage in a router:
#   from fastapi import Depends, APIRouter
#   from app.api import deps
#
#   router = APIRouter()
#
#   @router.get("/me")
#   def read_me(current_user = Depends(deps.get_current_user)):
#       return current_user


# --- Database & context --------------------------------------------------------

_db_dep = DatabaseDependency()
get_db = _db_dep.get_db  # db = Depends(deps.get_db)

_tenant_ctx_dep = TenantContextDependency()
get_tenant_context = _tenant_ctx_dep.get_tenant_context  # tenant_ctx = Depends(...)

_hostel_ctx_dep = HostelContextDependency()
get_hostel_context = _hostel_ctx_dep.get_hostel_context  # hostel_ctx = Depends(...)


# --- Authentication & Authorization -------------------------------------------

_auth_dep = AuthenticationDependency()
get_current_user = _auth_dep.get_current_user  # current_user = Depends(...)

_current_user_dep = CurrentUserDependency()
get_current_user_with_roles = _current_user_dep.get_current_user_with_roles

_super_admin_dep = SuperAdminDependency()
get_super_admin_user = _super_admin_dep.get_super_admin_user

_admin_dep = AdminDependency()
get_admin_user = _admin_dep.get_admin_user

_supervisor_dep = SupervisorDependency()
get_supervisor_user = _supervisor_dep.get_supervisor_user

_student_dep = StudentDependency()
get_student_user = _student_dep.get_student_user

_authz_dep = AuthorizationDependency()
require_permission: Callable[..., Any] = _authz_dep.require_permission  # used as dependency/decorator


# --- Pagination & Filtering ----------------------------------------------------

_pagination_dep = PaginationDependency()
get_pagination_params = _pagination_dep.get_pagination_params

_filter_dep = FilterDependency()
get_filter_params = _filter_dep.get_filter_params


# --- Cross‑cutting services: cache, notifications, file uploads ---------------

_cache_dep = CacheDependency()
get_cache_service = _cache_dep.get_cache_service

_notification_dep = NotificationDependency()
get_notification_service = _notification_dep.get_notification_service

_file_upload_dep = FileUploadDependency()
validate_file_upload = _file_upload_dep.validate_file_upload


__all__ = [
    # DB / context
    "get_db",
    "get_tenant_context",
    "get_hostel_context",
    # Authn / authz
    "get_current_user",
    "get_current_user_with_roles",
    "get_super_admin_user",
    "get_admin_user",
    "get_supervisor_user",
    "get_student_user",
    "require_permission",
    # Pagination / filtering
    "get_pagination_params",
    "get_filter_params",
    # Services
    "get_cache_service",
    "get_notification_service",
    "validate_file_upload",
]