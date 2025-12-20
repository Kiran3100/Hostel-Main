"""
File Metadata Service

Tagging, access control, versioning, analytics, and favorites management.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.repositories.file_management.file_metadata_repository import (
    FileMetadataRepository,
)
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
)

logger = logging.getLogger(__name__)


class FileMetadataService:
    """
    Service for file metadata operations.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.metadata_repo = FileMetadataRepository(db_session)
        self.file_repo = FileUploadRepository(db_session)

    # ============================================================================
    # TAG OPERATIONS
    # ============================================================================

    async def add_tags_to_file(
        self,
        file_id: str,
        tags: List[str],
        created_by_user_id: str,
    ) -> Dict[str, Any]:
        """
        Add tags to file.

        Args:
            file_id: File identifier
            tags: List of tag names
            created_by_user_id: User adding tags

        Returns:
            Updated tag list

        Raises:
            NotFoundException: If file not found
        """
        try:
            # Get file
            file_upload = await self.file_repo.find_by_file_id(file_id)
            if not file_upload:
                raise NotFoundException(f"File not found: {file_id}")

            # Get or create tags
            tag_objects = []
            for tag_name in tags:
                tag = await self.metadata_repo.get_or_create_tag(
                    tag_name=tag_name,
                    tag_type="user",
                    created_by_user_id=created_by_user_id,
                )
                tag_objects.append(tag)

            # Update file tags
            current_tags = set(file_upload.tags or [])
            new_tags = set(tags)
            updated_tags = list(current_tags | new_tags)

            await self.file_repo.update(
                file_upload.id,
                {"tags": updated_tags},
            )

            # Increment tag usage counts
            for tag in tag_objects:
                if tag.tag_name not in current_tags:
                    await self.metadata_repo.increment_tag_usage(tag.id)

            logger.info(f"Tags added to file {file_id}: {tags}")

            return {
                "file_id": file_id,
                "tags": updated_tags,
                "tags_added": list(new_tags - current_tags),
            }

        except Exception as e:
            logger.error(f"Failed to add tags: {str(e)}", exc_info=True)
            raise

    async def remove_tags_from_file(
        self,
        file_id: str,
        tags: List[str],
    ) -> Dict[str, Any]:
        """
        Remove tags from file.

        Args:
            file_id: File identifier
            tags: List of tag names to remove

        Returns:
            Updated tag list
        """
        try:
            file_upload = await self.file_repo.find_by_file_id(file_id)
            if not file_upload:
                raise NotFoundException(f"File not found: {file_id}")

            current_tags = set(file_upload.tags or [])
            tags_to_remove = set(tags)
            updated_tags = list(current_tags - tags_to_remove)

            await self.file_repo.update(
                file_upload.id,
                {"tags": updated_tags},
            )

            # Decrement tag usage counts
            for tag_name in tags_to_remove:
                tag = await self.metadata_repo.get_tag_by_name(tag_name)
                if tag:
                    await self.metadata_repo.decrement_tag_usage(tag.id)

            return {
                "file_id": file_id,
                "tags": updated_tags,
                "tags_removed": list(tags_to_remove & current_tags),
            }

        except Exception as e:
            logger.error(f"Failed to remove tags: {str(e)}", exc_info=True)
            raise

    async def get_popular_tags(
        self,
        limit: int = 50,
        tag_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get most popular tags."""
        tags = await self.metadata_repo.get_popular_tags(
            limit=limit,
            tag_type=tag_type,
        )

        return [
            {
                "tag_name": tag.tag_name,
                "tag_type": tag.tag_type,
                "usage_count": tag.usage_count,
                "color": tag.color,
                "icon": tag.icon,
            }
            for tag in tags
        ]

    async def search_tags(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search tags by name."""
        tags = await self.metadata_repo.search_tags(
            query=query,
            limit=limit,
        )

        return [
            {
                "tag_name": tag.tag_name,
                "tag_type": tag.tag_type,
                "usage_count": tag.usage_count,
            }
            for tag in tags
        ]

    # ============================================================================
    # ACCESS CONTROL
    # ============================================================================

    async def grant_file_access(
        self,
        file_id: str,
        subject_type: str,
        subject_id: str,
        permissions: Dict[str, bool],
        granted_by_user_id: str,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Grant access to file.

        Args:
            file_id: File identifier
            subject_type: Subject type (user, role, group)
            subject_id: Subject identifier
            permissions: Permission flags
            granted_by_user_id: User granting access
            expires_at: Optional expiration datetime

        Returns:
            Access grant details
        """
        try:
            # Verify file exists
            file_upload = await self.file_repo.find_by_file_id(file_id)
            if not file_upload:
                raise NotFoundException(f"File not found: {file_id}")

            access_data = {
                "access_type": subject_type,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "can_view": permissions.get("can_view", True),
                "can_download": permissions.get("can_download", True),
                "can_edit": permissions.get("can_edit", False),
                "can_delete": permissions.get("can_delete", False),
                "can_share": permissions.get("can_share", False),
                "expires_at": expires_at,
            }

            access = await self.metadata_repo.grant_access(
                file_id=file_id,
                access_data=access_data,
                granted_by_user_id=granted_by_user_id,
            )

            logger.info(f"Access granted to {subject_type}:{subject_id} for file {file_id}")

            return {
                "file_id": file_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "permissions": permissions,
                "granted_at": access.granted_at.isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
            }

        except Exception as e:
            logger.error(f"Failed to grant access: {str(e)}", exc_info=True)
            raise

    async def revoke_file_access(
        self,
        file_id: str,
        subject_type: str,
        subject_id: str,
        revoked_by_user_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Revoke file access."""
        try:
            access = await self.metadata_repo.get_access(
                file_id=file_id,
                subject_type=subject_type,
                subject_id=subject_id,
            )

            if not access:
                raise NotFoundException(f"Access not found for {subject_type}:{subject_id}")

            await self.metadata_repo.revoke_access(
                access_id=access.id,
                revoked_by_user_id=revoked_by_user_id,
                revocation_reason=reason,
            )

            return {
                "file_id": file_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "revoked": True,
            }

        except Exception as e:
            logger.error(f"Failed to revoke access: {str(e)}", exc_info=True)
            raise

    async def check_file_permission(
        self,
        file_id: str,
        user_id: str,
        permission: str,
    ) -> bool:
        """
        Check if user has specific permission on file.

        Args:
            file_id: File identifier
            user_id: User identifier
            permission: Permission to check

        Returns:
            True if user has permission
        """
        # Check direct user access
        has_permission = await self.metadata_repo.check_access_permission(
            file_id=file_id,
            subject_type="user",
            subject_id=user_id,
            permission=permission,
        )

        if has_permission:
            return True

        # TODO: Check role-based access
        # TODO: Check group-based access

        return False

    async def get_file_access_list(
        self,
        file_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all access records for file."""
        access_list = await self.metadata_repo.get_file_access_list(file_id)

        return [
            {
                "subject_type": access.subject_type,
                "subject_id": access.subject_id,
                "permissions": {
                    "can_view": access.can_view,
                    "can_download": access.can_download,
                    "can_edit": access.can_edit,
                    "can_delete": access.can_delete,
                    "can_share": access.can_share,
                },
                "granted_at": access.granted_at.isoformat(),
                "expires_at": access.expires_at.isoformat() if access.expires_at else None,
                "is_expired": access.is_expired,
                "is_revoked": access.is_revoked,
            }
            for access in access_list
        ]

    # ============================================================================
    # VERSION CONTROL
    # ============================================================================

    async def create_file_version(
        self,
        file_id: str,
        version_data: Dict[str, Any],
        created_by_user_id: str,
    ) -> Dict[str, Any]:
        """
        Create new file version.

        Args:
            file_id: File identifier
            version_data: Version details
            created_by_user_id: User creating version

        Returns:
            Version details
        """
        try:
            version = await self.metadata_repo.create_version(
                file_id=file_id,
                version_data=version_data,
                created_by_user_id=created_by_user_id,
            )

            return {
                "version_id": version.id,
                "version_number": version.version_number,
                "version_label": version.version_label,
                "storage_key": version.storage_key,
                "is_current": version.is_current,
                "created_at": version.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to create version: {str(e)}", exc_info=True)
            raise

    async def get_version_history(
        self,
        file_id: str,
    ) -> List[Dict[str, Any]]:
        """Get complete version history for file."""
        versions = await self.metadata_repo.get_version_history(file_id)

        return [
            {
                "version_id": version.id,
                "version_number": version.version_number,
                "version_label": version.version_label,
                "change_type": version.change_type,
                "change_description": version.change_description,
                "size_bytes": version.size_bytes,
                "is_current": version.is_current,
                "created_at": version.created_at.isoformat(),
                "created_by_user_id": version.created_by_user_id,
            }
            for version in versions
        ]

    async def restore_file_version(
        self,
        file_id: str,
        version_number: int,
        restored_by_user_id: str,
    ) -> Dict[str, Any]:
        """Restore previous version as current."""
        try:
            new_version = await self.metadata_repo.restore_version(
                file_id=file_id,
                version_number=version_number,
                restored_by_user_id=restored_by_user_id,
            )

            return {
                "restored": True,
                "new_version_number": new_version.version_number,
                "restored_from_version": version_number,
            }

        except Exception as e:
            logger.error(f"Failed to restore version: {str(e)}", exc_info=True)
            raise

    # ============================================================================
    # ANALYTICS AND ACCESS LOGGING
    # ============================================================================

    async def log_file_access(
        self,
        file_id: str,
        access_type: str,
        accessed_by_user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ) -> None:
        """
        Log file access event.

        Args:
            file_id: File identifier
            access_type: Access type (view, download, edit, etc.)
            accessed_by_user_id: User accessing the file
            ip_address: Client IP address
            user_agent: User agent string
            success: Whether access was successful
            **kwargs: Additional context
        """
        try:
            file_upload = await self.file_repo.find_by_file_id(file_id)
            if not file_upload:
                return

            access_data = {
                "storage_key": file_upload.storage_key,
                "access_type": access_type,
                "accessed_by_user_id": accessed_by_user_id,
                "access_method": kwargs.get("access_method", "web"),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "status_code": kwargs.get("status_code"),
                "error_message": kwargs.get("error_message"),
                "response_time_ms": kwargs.get("response_time_ms"),
                "bytes_transferred": kwargs.get("bytes_transferred"),
                "device_type": kwargs.get("device_type"),
                "browser": kwargs.get("browser"),
                "operating_system": kwargs.get("operating_system"),
                "context": kwargs.get("context", {}),
            }

            await self.metadata_repo.log_file_access(
                file_id=file_id,
                access_data=access_data,
            )

        except Exception as e:
            logger.error(f"Failed to log access: {str(e)}", exc_info=True)
            # Don't raise - logging failure shouldn't break the main flow

    async def get_file_analytics(
        self,
        file_id: str,
    ) -> Dict[str, Any]:
        """Get analytics for file."""
        analytics = await self.metadata_repo.get_or_create_analytics(file_id)

        return {
            "file_id": file_id,
            "total_views": analytics.total_views,
            "total_downloads": analytics.total_downloads,
            "unique_viewers": analytics.unique_viewers,
            "unique_downloaders": analytics.unique_downloaders,
            "popularity_score": analytics.popularity_score,
            "trending_score": analytics.trending_score,
            "last_viewed_at": analytics.last_viewed_at.isoformat() if analytics.last_viewed_at else None,
            "last_downloaded_at": analytics.last_downloaded_at.isoformat() if analytics.last_downloaded_at else None,
        }

    async def get_access_logs(
        self,
        file_id: str,
        access_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get access logs for file."""
        logs = await self.metadata_repo.get_access_logs(
            file_id=file_id,
            access_type=access_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return [
            {
                "access_type": log.access_type,
                "accessed_by_user_id": log.accessed_by_user_id,
                "accessed_at": log.accessed_at.isoformat(),
                "ip_address": log.ip_address,
                "success": log.success,
                "device_type": log.device_type,
                "browser": log.browser,
            }
            for log in logs
        ]

    # ============================================================================
    # FAVORITES
    # ============================================================================

    async def add_to_favorites(
        self,
        file_id: str,
        user_id: str,
        note: Optional[str] = None,
        folder_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Add file to user favorites."""
        try:
            favorite = await self.metadata_repo.add_favorite(
                file_id=file_id,
                user_id=user_id,
                note=note,
                folder_name=folder_name,
                tags=tags,
            )

            return {
                "file_id": file_id,
                "favorited": True,
                "favorited_at": favorite.favorited_at.isoformat(),
            }

        except ValueError as e:
            # Already favorited
            return {
                "file_id": file_id,
                "favorited": True,
                "message": str(e),
            }
        except Exception as e:
            logger.error(f"Failed to add favorite: {str(e)}", exc_info=True)
            raise

    async def remove_from_favorites(
        self,
        file_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Remove file from favorites."""
        removed = await self.metadata_repo.remove_favorite(
            file_id=file_id,
            user_id=user_id,
        )

        return {
            "file_id": file_id,
            "removed": removed,
        }

    async def get_user_favorites(
        self,
        user_id: str,
        folder_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get user's favorite files."""
        favorites = await self.metadata_repo.get_user_favorites(
            user_id=user_id,
            folder_name=folder_name,
            tags=tags,
        )

        return [
            {
                "file_id": favorite.file_id,
                "note": favorite.note,
                "folder_name": favorite.folder_name,
                "tags": favorite.tags,
                "favorited_at": favorite.favorited_at.isoformat(),
                "access_count": favorite.access_count,
            }
            for favorite in favorites
        ]

    # ============================================================================
    # PERIODIC TASKS
    # ============================================================================

    async def cleanup_expired_access(
        self,
        batch_size: int = 100,
    ) -> int:
        """Mark expired access records."""
        return await self.metadata_repo.cleanup_expired_access(batch_size)

    async def calculate_analytics_scores(
        self,
        batch_size: int = 100,
    ) -> int:
        """Calculate popularity and trending scores."""
        return await self.metadata_repo.calculate_popularity_scores(batch_size)

    async def reset_period_counters(
        self,
        period: str,
    ) -> int:
        """Reset period counters (daily, weekly, monthly)."""
        return await self.metadata_repo.reset_period_counters(period)