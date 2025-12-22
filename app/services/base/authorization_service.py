# authorization_service.py

from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum
import uuid

class AccessLevel(Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3
    SUPER_ADMIN = 4

@dataclass
class AuthorizationContext:
    """Context for authorization decisions"""
    user_id: str
    roles: List[str]
    permissions: Set[str]
    tenant_id: str
    resource_type: str
    resource_id: Optional[str]
    action: str
    metadata: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()

    @classmethod
    def create(
        cls,
        user_id: str,
        roles: List[str],
        permissions: Set[str],
        tenant_id: str,
        resource_type: str,
        action: str
    ) -> 'AuthorizationContext':
        return cls(
            user_id=user_id,
            roles=roles,
            permissions=permissions,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=None,
            action=action,
            metadata={}
        )

class PermissionChecker:
    """Checks user permissions against required permissions"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def check_permission(
        self,
        context: AuthorizationContext,
        required_permission: str
    ) -> bool:
        """Check if user has required permission"""
        try:
            # Direct permission check
            if required_permission in context.permissions:
                return True

            # Wildcard permission check
            resource_type = context.resource_type
            wildcard_permission = f"{resource_type}.*"
            if wildcard_permission in context.permissions:
                return True

            # Super admin check
            if "admin.*" in context.permissions:
                return True

            self.logger.debug(
                f"Permission denied: {context.user_id} lacks {required_permission}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Permission check error: {str(e)}")
            return False

    async def check_multiple_permissions(
        self,
        context: AuthorizationContext,
        required_permissions: Set[str],
        require_all: bool = True
    ) -> bool:
        """Check multiple permissions"""
        try:
            results = [
                await self.check_permission(context, perm)
                for perm in required_permissions
            ]
            
            return all(results) if require_all else any(results)
        except Exception as e:
            self.logger.error(f"Multiple permission check error: {str(e)}")
            return False

class RoleValidator:
    """Validates user roles and role hierarchies"""
    
    def __init__(self):
        self._role_hierarchy: Dict[str, Set[str]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_role_hierarchy(
        self,
        role: str,
        inherited_roles: Set[str]
    ) -> None:
        """Add role hierarchy definition"""
        self._role_hierarchy[role] = inherited_roles
        self.logger.info(f"Added role hierarchy for {role}")

    def get_effective_roles(self, roles: List[str]) -> Set[str]:
        """Get all effective roles including inherited ones"""
        effective_roles = set(roles)
        
        for role in roles:
            inherited = self._role_hierarchy.get(role, set())
            effective_roles.update(inherited)
            
            # Recursive inheritance
            for inherited_role in inherited:
                effective_roles.update(
                    self.get_effective_roles([inherited_role])
                )
        
        return effective_roles

    async def validate_role(
        self,
        context: AuthorizationContext,
        required_role: str
    ) -> bool:
        """Validate if user has required role"""
        try:
            effective_roles = self.get_effective_roles(context.roles)
            return required_role in effective_roles
        except Exception as e:
            self.logger.error(f"Role validation error: {str(e)}")
            return False

class AccessControlList:
    """Manages ACL-based access control"""
    
    def __init__(self):
        self._acl: Dict[str, Dict[str, AccessLevel]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_acl_entry(
        self,
        resource_id: str,
        user_id: str,
        access_level: AccessLevel
    ) -> None:
        """Add ACL entry"""
        if resource_id not in self._acl:
            self._acl[resource_id] = {}
        self._acl[resource_id][user_id] = access_level
        self.logger.info(
            f"Added ACL entry: {user_id} -> {access_level.name} for {resource_id}"
        )

    def remove_acl_entry(
        self,
        resource_id: str,
        user_id: str
    ) -> None:
        """Remove ACL entry"""
        if resource_id in self._acl:
            self._acl[resource_id].pop(user_id, None)
            self.logger.info(f"Removed ACL entry for {user_id} on {resource_id}")

    async def check_access(
        self,
        context: AuthorizationContext,
        required_level: AccessLevel
    ) -> bool:
        """Check if user has required access level"""
        try:
            if not context.resource_id:
                return False

            resource_acl = self._acl.get(context.resource_id, {})
            user_level = resource_acl.get(context.user_id, AccessLevel.NONE)
            
            return user_level.value >= required_level.value
        except Exception as e:
            self.logger.error(f"ACL check error: {str(e)}")
            return False

class PolicyEnforcer:
    """Enforces authorization policies"""
    
    def __init__(self):
        self._policies: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_policy(
        self,
        policy_name: str,
        policy_func: Callable
    ) -> None:
        """Add authorization policy"""
        self._policies[policy_name] = policy_func
        self.logger.info(f"Added policy: {policy_name}")

    async def enforce_policy(
        self,
        policy_name: str,
        context: AuthorizationContext,
        **kwargs: Any
    ) -> bool:
        """Enforce a specific policy"""
        try:
            policy = self._policies.get(policy_name)
            if not policy:
                self.logger.warning(f"Policy not found: {policy_name}")
                return False

            return await policy(context, **kwargs)
        except Exception as e:
            self.logger.error(f"Policy enforcement error: {str(e)}")
            return False

class AuthorizationService:
    """Main authorization service interface"""
    
    def __init__(self):
        self.permission_checker = PermissionChecker()
        self.role_validator = RoleValidator()
        self.acl = AccessControlList()
        self.policy_enforcer = PolicyEnforcer()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def authorize(
        self,
        context: AuthorizationContext,
        required_permissions: Optional[Set[str]] = None,
        required_roles: Optional[List[str]] = None,
        required_access_level: Optional[AccessLevel] = None,
        policies: Optional[List[str]] = None
    ) -> bool:
        """Comprehensive authorization check"""
        try:
            # Permission check
            if required_permissions:
                if not await self.permission_checker.check_multiple_permissions(
                    context,
                    required_permissions
                ):
                    return False

            # Role check
            if required_roles:
                for role in required_roles:
                    if not await self.role_validator.validate_role(context, role):
                        return False

            # ACL check
            if required_access_level:
                if not await self.acl.check_access(context, required_access_level):
                    return False

            # Policy check
            if policies:
                for policy in policies:
                    if not await self.policy_enforcer.enforce_policy(policy, context):
                        return False

            return True
        except Exception as e:
            self.logger.error(f"Authorization error: {str(e)}")
            return False

    async def check_permission(
        self,
        context: AuthorizationContext,
        permission: str
    ) -> bool:
        """Check single permission"""
        return await self.permission_checker.check_permission(context, permission)

    async def validate_role(
        self,
        context: AuthorizationContext,
        role: str
    ) -> bool:
        """Validate single role"""
        return await self.role_validator.validate_role(context, role)

    async def check_access(
        self,
        context: AuthorizationContext,
        access_level: AccessLevel
    ) -> bool:
        """Check ACL access"""
        return await self.acl.check_access(context, access_level)

    async def enforce_policy(
        self,
        context: AuthorizationContext,
        policy: str,
        **kwargs: Any
    ) -> bool:
        """Enforce single policy"""
        return await self.policy_enforcer.enforce_policy(policy, context, **kwargs)

    def configure_role_hierarchy(
        self,
        hierarchies: Dict[str, Set[str]]
    ) -> None:
        """Configure role hierarchies"""
        for role, inherited in hierarchies.items():
            self.role_validator.add_role_hierarchy(role, inherited)

    def add_acl_entry(
        self,
        resource_id: str,
        user_id: str,
        access_level: AccessLevel
    ) -> None:
        """Add ACL entry"""
        self.acl.add_acl_entry(resource_id, user_id, access_level)

    def add_policy(
        self,
        policy_name: str,
        policy_func: Callable
    ) -> None:
        """Add authorization policy"""
        self.policy_enforcer.add_policy(policy_name, policy_func)