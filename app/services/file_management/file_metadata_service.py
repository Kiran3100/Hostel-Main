"""
File Metadata and Access Control Service

Manages:
- File tags and categorization
- Access Control Lists (ACL)
- Version history
- Analytics and access logs
- File statistics and reporting
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.file_metadata_repository import FileMetadataRepository
from app.models.file_management.file_metadata import (
    FileTag as FileTagModel,
    FileAccess as FileAccessModel,
    FileVersion as FileVersionModel,
    FileAnalytics as FileAnalyticsModel
)
from app.schemas.file.file_response import FileInfo, FileStats

logger = logging.getLogger(__name__)


class FileMetadataService(BaseService[FileTagModel, FileMetadataRepository]):
    """
    Comprehensive metadata and access control management.
    
    Features:
    - Tag-based file organization
    - Fine-grained permission management
    - Complete version history
    - Detailed analytics and access tracking
    """

    def __init__(self, repository: FileMetadataRepository, db_session: Session):
        """
        Initialize the file metadata service.
        
        Args:
            repository: File metadata repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._max_tags_per_file = 50
        self._max_acl_entries = 100
        logger.info("FileMetadataService initialized")

    # ==================================================================================
    # TAG MANAGEMENT
    # ==================================================================================

    def add_tag(
        self,
        file_id: UUID,
        tag: str,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Add a tag to a file.
        
        Args:
            file_id: Unique identifier of the file
            tag: Tag string to add
            created_by: User ID who created the tag
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            # Validate tag
            tag = tag.strip().lower()
            if not tag or len(tag) < 2:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Tag must be at least 2 characters long",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if len(tag) > 50:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Tag cannot exceed 50 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Check tag limit
            existing_tags = self.repository.list_tags(file_id)
            if len(existing_tags) >= self._max_tags_per_file:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Maximum {self._max_tags_per_file} tags allowed per file",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            logger.info(f"Adding tag '{tag}' to file ID: {file_id}")
            
            success = self.repository.add_tag(file_id, tag, created_by=created_by)
            
            if success:
                self.db.commit()
                logger.info(f"Tag '{tag}' added successfully to file {file_id}")
                return ServiceResult.success(True, message=f"Tag '{tag}' added successfully")
            else:
                logger.warning(f"Tag '{tag}' already exists for file {file_id}")
                return ServiceResult.success(True, message="Tag already exists")
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add tag to file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "add tag", file_id)

    def add_tags_bulk(
        self,
        file_id: UUID,
        tags: List[str],
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Add multiple tags to a file in bulk.
        
        Args:
            file_id: Unique identifier of the file
            tags: List of tags to add
            created_by: User ID who created the tags
            
        Returns:
            ServiceResult with count of added tags
        """
        try:
            # Normalize tags
            normalized_tags = [t.strip().lower() for t in tags if t.strip()]
            normalized_tags = list(set(normalized_tags))  # Remove duplicates
            
            if not normalized_tags:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No valid tags provided",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            logger.info(f"Adding {len(normalized_tags)} tags to file ID: {file_id}")
            
            added_count = 0
            skipped_count = 0
            
            for tag in normalized_tags:
                result = self.add_tag(file_id, tag, created_by=created_by)
                if result.success:
                    added_count += 1
                else:
                    skipped_count += 1
            
            return ServiceResult.success(
                {"added": added_count, "skipped": skipped_count},
                message=f"Added {added_count} tags, skipped {skipped_count}"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to bulk add tags to file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk add tags", file_id)

    def remove_tag(
        self,
        file_id: UUID,
        tag: str,
    ) -> ServiceResult[bool]:
        """
        Remove a tag from a file.
        
        Args:
            file_id: Unique identifier of the file
            tag: Tag string to remove
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            tag = tag.strip().lower()
            logger.info(f"Removing tag '{tag}' from file ID: {file_id}")
            
            success = self.repository.remove_tag(file_id, tag)
            
            if success:
                self.db.commit()
                logger.info(f"Tag '{tag}' removed successfully from file {file_id}")
                return ServiceResult.success(True, message=f"Tag '{tag}' removed successfully")
            else:
                logger.warning(f"Tag '{tag}' not found for file {file_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Tag '{tag}' not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove tag from file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "remove tag", file_id)

    def list_tags(
        self,
        file_id: UUID,
    ) -> ServiceResult[List[str]]:
        """
        List all tags for a file.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult containing list of tags
        """
        try:
            logger.debug(f"Listing tags for file ID: {file_id}")
            
            tags = self.repository.list_tags(file_id)
            
            return ServiceResult.success(
                tags,
                metadata={"count": len(tags)}
            )
            
        except Exception as e:
            logger.error(f"Failed to list tags for file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "list tags", file_id)

    def clear_all_tags(
        self,
        file_id: UUID,
    ) -> ServiceResult[int]:
        """
        Remove all tags from a file.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult with count of removed tags
        """
        try:
            logger.info(f"Clearing all tags for file ID: {file_id}")
            
            count = self.repository.clear_all_tags(file_id)
            self.db.commit()
            
            logger.info(f"Removed {count} tags from file {file_id}")
            
            return ServiceResult.success(
                count,
                message=f"Removed {count} tags"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to clear tags for file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "clear all tags", file_id)

    # ==================================================================================
    # ACCESS CONTROL LIST (ACL)
    # ==================================================================================

    def grant_access(
        self,
        file_id: UUID,
        principal_id: UUID,
        permission: str = "read",
        granted_by: Optional[UUID] = None,
        expires_at: Optional[datetime] = None,
    ) -> ServiceResult[bool]:
        """
        Grant access permission to a user or group.
        
        Args:
            file_id: Unique identifier of the file
            principal_id: User or group ID to grant access to
            permission: Permission level (read, write, delete, admin)
            granted_by: User ID who granted the permission
            expires_at: Optional expiration datetime
            
        Returns:
            ServiceResult indicating success or failure
        """
        valid_permissions = {"read", "write", "delete", "admin"}
        
        try:
            # Validate permission
            if permission not in valid_permissions:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid permission. Must be one of: {', '.join(valid_permissions)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Check ACL limit
            existing_acl = self.repository.list_access(file_id)
            if len(existing_acl) >= self._max_acl_entries:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Maximum {self._max_acl_entries} ACL entries allowed",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            logger.info(
                f"Granting '{permission}' access to principal {principal_id} "
                f"for file ID: {file_id}"
            )
            
            success = self.repository.grant_access(
                file_id,
                principal_id,
                permission,
                granted_by=granted_by,
                expires_at=expires_at
            )
            
            if success:
                self.db.commit()
                logger.info(
                    f"Access granted successfully to principal {principal_id} "
                    f"for file {file_id}"
                )
                return ServiceResult.success(True, message="Access granted successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to grant access",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to grant access for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "grant access", file_id)

    def revoke_access(
        self,
        file_id: UUID,
        principal_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Revoke access permission from a user or group.
        
        Args:
            file_id: Unique identifier of the file
            principal_id: User or group ID to revoke access from
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(
                f"Revoking access for principal {principal_id} from file ID: {file_id}"
            )
            
            success = self.repository.revoke_access(file_id, principal_id)
            
            if success:
                self.db.commit()
                logger.info(
                    f"Access revoked successfully for principal {principal_id} "
                    f"from file {file_id}"
                )
                return ServiceResult.success(True, message="Access revoked successfully")
            else:
                logger.warning(
                    f"No access found for principal {principal_id} on file {file_id}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Access entry not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to revoke access for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "revoke access", file_id)

    def update_access_permission(
        self,
        file_id: UUID,
        principal_id: UUID,
        new_permission: str,
    ) -> ServiceResult[bool]:
        """
        Update an existing access permission.
        
        Args:
            file_id: Unique identifier of the file
            principal_id: User or group ID
            new_permission: New permission level
            
        Returns:
            ServiceResult indicating success or failure
        """
        valid_permissions = {"read", "write", "delete", "admin"}
        
        try:
            if new_permission not in valid_permissions:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid permission. Must be one of: {', '.join(valid_permissions)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            logger.info(
                f"Updating permission to '{new_permission}' for principal {principal_id} "
                f"on file ID: {file_id}"
            )
            
            success = self.repository.update_access_permission(
                file_id,
                principal_id,
                new_permission
            )
            
            if success:
                self.db.commit()
                logger.info(f"Permission updated successfully for file {file_id}")
                return ServiceResult.success(True, message="Permission updated successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Access entry not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to update permission for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update access permission", file_id)

    def list_access(
        self,
        file_id: UUID,
        include_expired: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List all access permissions for a file.
        
        Args:
            file_id: Unique identifier of the file
            include_expired: Whether to include expired permissions
            
        Returns:
            ServiceResult containing list of ACL entries
        """
        try:
            logger.debug(f"Listing access permissions for file ID: {file_id}")
            
            acl = self.repository.list_access(file_id, include_expired=include_expired)
            
            return ServiceResult.success(
                acl,
                metadata={"count": len(acl), "include_expired": include_expired}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to list access for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list access", file_id)

    def check_access(
        self,
        file_id: UUID,
        principal_id: UUID,
        required_permission: str = "read",
    ) -> ServiceResult[bool]:
        """
        Check if a principal has specific permission on a file.
        
        Args:
            file_id: Unique identifier of the file
            principal_id: User or group ID to check
            required_permission: Required permission level
            
        Returns:
            ServiceResult indicating whether access is granted
        """
        try:
            logger.debug(
                f"Checking {required_permission} access for principal {principal_id} "
                f"on file {file_id}"
            )
            
            has_access = self.repository.check_access(
                file_id,
                principal_id,
                required_permission
            )
            
            return ServiceResult.success(
                has_access,
                message="Access check completed"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to check access for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "check access", file_id)

    # ==================================================================================
    # VERSION MANAGEMENT
    # ==================================================================================

    def create_version(
        self,
        file_id: UUID,
        notes: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[FileVersionModel]:
        """
        Create a new version snapshot of a file.
        
        Args:
            file_id: Unique identifier of the file
            notes: Optional version notes
            created_by: User ID who created the version
            
        Returns:
            ServiceResult containing the new version record
        """
        try:
            logger.info(f"Creating new version for file ID: {file_id}")
            
            version = self.repository.create_version(
                file_id,
                notes=notes,
                created_by=created_by
            )
            
            self.db.commit()
            
            logger.info(
                f"Version created successfully for file {file_id}: "
                f"version {version.version_number if hasattr(version, 'version_number') else 'unknown'}"
            )
            
            return ServiceResult.success(
                version,
                message="Version created successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to create version for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "create version", file_id)

    def list_versions(
        self,
        file_id: UUID,
        limit: Optional[int] = None,
    ) -> ServiceResult[List[FileVersionModel]]:
        """
        List all versions of a file.
        
        Args:
            file_id: Unique identifier of the file
            limit: Optional maximum number of versions to return
            
        Returns:
            ServiceResult containing list of versions
        """
        try:
            logger.debug(f"Listing versions for file ID: {file_id}")
            
            versions = self.repository.list_versions(file_id, limit=limit)
            
            return ServiceResult.success(
                versions,
                metadata={"count": len(versions), "limit": limit}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to list versions for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list versions", file_id)

    def restore_version(
        self,
        file_id: UUID,
        version_id: UUID,
        restored_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Restore a file to a specific version.
        
        Args:
            file_id: Unique identifier of the file
            version_id: Version ID to restore
            restored_by: User ID who performed the restoration
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(
                f"Restoring file {file_id} to version {version_id}"
            )
            
            success = self.repository.restore_version(
                file_id,
                version_id,
                restored_by=restored_by
            )
            
            if success:
                self.db.commit()
                logger.info(f"Version restored successfully for file {file_id}")
                return ServiceResult.success(True, message="Version restored successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to restore version",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to restore version for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "restore version", file_id)

    # ==================================================================================
    # ANALYTICS & ACCESS LOGS
    # ==================================================================================

    def increment_access_count(
        self,
        file_id: UUID,
        user_id: Optional[UUID] = None,
        method: str = "download",
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[bool]:
        """
        Record a file access event and increment counters.
        
        Args:
            file_id: Unique identifier of the file
            user_id: User who accessed the file
            method: Access method (download, view, preview, etc.)
            ip: Client IP address
            user_agent: Client user agent string
            metadata: Additional metadata
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.debug(
                f"Recording {method} access for file {file_id} by user {user_id}"
            )
            
            success = self.repository.increment_access(
                file_id,
                user_id=user_id,
                method=method,
                ip=ip,
                user_agent=user_agent,
                metadata=metadata
            )
            
            if success:
                self.db.commit()
                return ServiceResult.success(True, message="Access recorded")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to record access",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to increment access for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "increment access", file_id)

    def get_access_logs(
        self,
        file_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Retrieve access logs for a file.
        
        Args:
            file_id: Unique identifier of the file
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            
        Returns:
            ServiceResult containing access log entries
        """
        try:
            logger.debug(f"Retrieving access logs for file ID: {file_id}")
            
            logs = self.repository.get_access_logs(file_id, limit=limit, offset=offset)
            
            return ServiceResult.success(
                logs,
                metadata={"count": len(logs), "limit": limit, "offset": offset}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to get access logs for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get access logs", file_id)

    def get_stats(
        self,
        owner_user_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ServiceResult[FileStats]:
        """
        Get file statistics and analytics.
        
        Args:
            owner_user_id: Filter by file owner
            hostel_id: Filter by hostel
            date_from: Start date for analytics
            date_to: End date for analytics
            
        Returns:
            ServiceResult containing file statistics
        """
        try:
            logger.info(
                f"Retrieving file stats for owner: {owner_user_id}, "
                f"hostel: {hostel_id}"
            )
            
            stats = self.repository.get_stats(
                owner_user_id=owner_user_id,
                hostel_id=hostel_id,
                date_from=date_from,
                date_to=date_to
            )
            
            return ServiceResult.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to get file stats: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get file stats")

    def get_file_analytics(
        self,
        file_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed analytics for a specific file.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult containing detailed analytics
        """
        try:
            logger.debug(f"Retrieving analytics for file ID: {file_id}")
            
            analytics = self.repository.get_file_analytics(file_id)
            
            return ServiceResult.success(analytics)
            
        except Exception as e:
            logger.error(
                f"Failed to get analytics for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get file analytics", file_id)

    @property
    def max_tags_per_file(self) -> int:
        """Get the maximum number of tags allowed per file."""
        return self._max_tags_per_file

    @max_tags_per_file.setter
    def max_tags_per_file(self, value: int) -> None:
        """Set the maximum number of tags allowed per file."""
        if value < 1:
            raise ValueError("Maximum tags must be at least 1")
        self._max_tags_per_file = value
        logger.info(f"Max tags per file set to: {value}")

    @property
    def max_acl_entries(self) -> int:
        """Get the maximum number of ACL entries allowed."""
        return self._max_acl_entries

    @max_acl_entries.setter
    def max_acl_entries(self, value: int) -> None:
        """Set the maximum number of ACL entries allowed."""
        if value < 1:
            raise ValueError("Maximum ACL entries must be at least 1")
        self._max_acl_entries = value
        logger.info(f"Max ACL entries set to: {value}")