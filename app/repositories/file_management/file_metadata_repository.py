"""
File Metadata Repository

Metadata, tagging, access control, versioning, analytics, and audit operations.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager, PaginatedResult
from app.models.file_management.file_metadata import (
    FileTag,
    FileAccess,
    FileVersion,
    FileAnalytics,
    FileAccessLog,
    FileFavorite,
)
from app.models.file_management.file_upload import FileUpload


class FileMetadataRepository(BaseRepository[FileTag]):
    """
    Repository for file metadata, tagging, access control, versioning,
    and analytics operations.
    """

    def __init__(self, db_session: Session):
        super().__init__(FileTag, db_session)

    # ============================================================================
    # FILE TAG OPERATIONS
    # ============================================================================

    async def create_tag(
        self,
        tag_data: Dict[str, Any],
        created_by_user_id: Optional[str] = None,
    ) -> FileTag:
        """
        Create file tag.

        Args:
            tag_data: Tag configuration
            created_by_user_id: User creating the tag

        Returns:
            Created FileTag
        """
        tag = FileTag(
            tag_name=tag_data["tag_name"].lower().strip(),
            tag_type=tag_data.get("tag_type", "user"),
            parent_tag_id=tag_data.get("parent_tag_id"),
            description=tag_data.get("description"),
            color=tag_data.get("color"),
            icon=tag_data.get("icon"),
            created_by_user_id=created_by_user_id,
            usage_count=0,
            is_active=tag_data.get("is_active", True),
        )

        self.db_session.add(tag)
        self.db_session.commit()
        return tag

    async def get_tag_by_name(
        self,
        tag_name: str,
        tag_type: Optional[str] = None,
    ) -> Optional[FileTag]:
        """
        Get tag by name.

        Args:
            tag_name: Tag name
            tag_type: Optional tag type filter

        Returns:
            FileTag if found
        """
        query = self.db_session.query(FileTag).filter(
            FileTag.tag_name == tag_name.lower().strip(),
            FileTag.is_active == True,
        )

        if tag_type:
            query = query.filter(FileTag.tag_type == tag_type)

        return query.first()

    async def get_or_create_tag(
        self,
        tag_name: str,
        tag_type: str = "user",
        created_by_user_id: Optional[str] = None,
    ) -> FileTag:
        """
        Get existing tag or create new one.

        Args:
            tag_name: Tag name
            tag_type: Tag type
            created_by_user_id: User creating tag

        Returns:
            Existing or new FileTag
        """
        tag = await self.get_tag_by_name(tag_name, tag_type)

        if not tag:
            tag = await self.create_tag(
                {
                    "tag_name": tag_name,
                    "tag_type": tag_type,
                },
                created_by_user_id=created_by_user_id,
            )

        return tag

    async def get_popular_tags(
        self,
        limit: int = 50,
        tag_type: Optional[str] = None,
    ) -> List[FileTag]:
        """
        Get most popular tags by usage count.

        Args:
            limit: Maximum results
            tag_type: Filter by tag type

        Returns:
            List of popular tags
        """
        query = self.db_session.query(FileTag).filter(FileTag.is_active == True)

        if tag_type:
            query = query.filter(FileTag.tag_type == tag_type)

        return query.order_by(desc(FileTag.usage_count)).limit(limit).all()

    async def increment_tag_usage(
        self,
        tag_id: str,
    ) -> FileTag:
        """
        Increment tag usage count.

        Args:
            tag_id: Tag identifier

        Returns:
            Updated FileTag
        """
        tag = await self.find_by_id(tag_id)
        if tag:
            tag.usage_count += 1
            self.db_session.commit()
        return tag

    async def decrement_tag_usage(
        self,
        tag_id: str,
    ) -> FileTag:
        """
        Decrement tag usage count.

        Args:
            tag_id: Tag identifier

        Returns:
            Updated FileTag
        """
        tag = await self.find_by_id(tag_id)
        if tag and tag.usage_count > 0:
            tag.usage_count -= 1
            self.db_session.commit()
        return tag

    async def search_tags(
        self,
        query: str,
        tag_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[FileTag]:
        """
        Search tags by name.

        Args:
            query: Search query
            tag_type: Filter by tag type
            limit: Maximum results

        Returns:
            List of matching tags
        """
        db_query = self.db_session.query(FileTag).filter(
            FileTag.tag_name.like(f"%{query.lower()}%"),
            FileTag.is_active == True,
        )

        if tag_type:
            db_query = db_query.filter(FileTag.tag_type == tag_type)

        return db_query.order_by(desc(FileTag.usage_count)).limit(limit).all()

    # ============================================================================
    # FILE ACCESS CONTROL OPERATIONS
    # ============================================================================

    async def grant_access(
        self,
        file_id: str,
        access_data: Dict[str, Any],
        granted_by_user_id: str,
    ) -> FileAccess:
        """
        Grant file access to user/role/group.

        Args:
            file_id: File identifier (file_id, not internal id)
            access_data: Access configuration
            granted_by_user_id: User granting access

        Returns:
            Created FileAccess

        Raises:
            ValueError: If access already exists
        """
        # Check if access already exists
        existing = await self.get_access(
            file_id=file_id,
            subject_type=access_data["subject_type"],
            subject_id=access_data["subject_id"],
        )

        if existing and not existing.is_revoked:
            raise ValueError("Access already granted to this subject")

        access = FileAccess(
            file_id=file_id,
            access_type=access_data.get("access_type", "user"),
            subject_type=access_data["subject_type"],
            subject_id=access_data["subject_id"],
            can_view=access_data.get("can_view", True),
            can_download=access_data.get("can_download", True),
            can_edit=access_data.get("can_edit", False),
            can_delete=access_data.get("can_delete", False),
            can_share=access_data.get("can_share", False),
            expires_at=access_data.get("expires_at"),
            granted_by_user_id=granted_by_user_id,
            granted_at=datetime.utcnow(),
        )

        self.db_session.add(access)
        self.db_session.commit()
        return access

    async def get_access(
        self,
        file_id: str,
        subject_type: str,
        subject_id: str,
    ) -> Optional[FileAccess]:
        """
        Get access record for specific subject.

        Args:
            file_id: File identifier
            subject_type: Subject type
            subject_id: Subject identifier

        Returns:
            FileAccess if exists
        """
        return (
            self.db_session.query(FileAccess)
            .filter(
                FileAccess.file_id == file_id,
                FileAccess.subject_type == subject_type,
                FileAccess.subject_id == subject_id,
            )
            .first()
        )

    async def get_file_access_list(
        self,
        file_id: str,
        include_revoked: bool = False,
    ) -> List[FileAccess]:
        """
        Get all access records for a file.

        Args:
            file_id: File identifier
            include_revoked: Whether to include revoked access

        Returns:
            List of access records
        """
        query = self.db_session.query(FileAccess).filter(FileAccess.file_id == file_id)

        if not include_revoked:
            query = query.filter(FileAccess.is_revoked == False)

        return query.order_by(desc(FileAccess.granted_at)).all()

    async def check_access_permission(
        self,
        file_id: str,
        subject_type: str,
        subject_id: str,
        permission: str,
    ) -> bool:
        """
        Check if subject has specific permission on file.

        Args:
            file_id: File identifier
            subject_type: Subject type
            subject_id: Subject identifier
            permission: Permission to check (view, download, edit, delete, share)

        Returns:
            True if permission granted
        """
        access = await self.get_access(file_id, subject_type, subject_id)

        if not access or access.is_revoked:
            return False

        # Check expiration
        if access.expires_at and access.expires_at < datetime.utcnow():
            access.is_expired = True
            self.db_session.commit()
            return False

        permission_map = {
            "view": access.can_view,
            "download": access.can_download,
            "edit": access.can_edit,
            "delete": access.can_delete,
            "share": access.can_share,
        }

        return permission_map.get(permission, False)

    async def revoke_access(
        self,
        access_id: str,
        revoked_by_user_id: str,
        revocation_reason: Optional[str] = None,
    ) -> FileAccess:
        """
        Revoke file access.

        Args:
            access_id: FileAccess identifier
            revoked_by_user_id: User revoking access
            revocation_reason: Reason for revocation

        Returns:
            Updated FileAccess
        """
        access = self.db_session.query(FileAccess).get(access_id)

        if not access:
            raise ValueError(f"Access not found: {access_id}")

        access.is_revoked = True
        access.revoked_by_user_id = revoked_by_user_id
        access.revoked_at = datetime.utcnow()
        access.revocation_reason = revocation_reason

        self.db_session.commit()
        return access

    async def cleanup_expired_access(
        self,
        batch_size: int = 100,
    ) -> int:
        """
        Mark expired access records.

        Args:
            batch_size: Number of records to process

        Returns:
            Number of records marked as expired
        """
        expired_access = (
            self.db_session.query(FileAccess)
            .filter(
                FileAccess.expires_at < datetime.utcnow(),
                FileAccess.is_expired == False,
                FileAccess.is_revoked == False,
            )
            .limit(batch_size)
            .all()
        )

        for access in expired_access:
            access.is_expired = True

        self.db_session.commit()
        return len(expired_access)

    # ============================================================================
    # FILE VERSION OPERATIONS
    # ============================================================================

    async def create_version(
        self,
        file_id: str,
        version_data: Dict[str, Any],
        created_by_user_id: str,
    ) -> FileVersion:
        """
        Create new file version.

        Args:
            file_id: File identifier (file_id)
            version_data: Version details
            created_by_user_id: User creating version

        Returns:
            Created FileVersion
        """
        # Get current version number
        current_version = await self.get_current_version(file_id)
        version_number = (current_version.version_number + 1) if current_version else 1

        # Mark all previous versions as not current
        if current_version:
            current_version.is_current = False

        version = FileVersion(
            file_id=file_id,
            version_number=version_number,
            version_label=version_data.get("version_label"),
            storage_key=version_data["storage_key"],
            size_bytes=version_data["size_bytes"],
            checksum=version_data.get("checksum"),
            change_type=version_data.get("change_type", "upload"),
            change_description=version_data.get("change_description"),
            change_summary=version_data.get("change_summary", {}),
            created_by_user_id=created_by_user_id,
            is_current=True,
            version_metadata=version_data.get("metadata", {}),
        )

        self.db_session.add(version)
        self.db_session.commit()
        return version

    async def get_current_version(
        self,
        file_id: str,
    ) -> Optional[FileVersion]:
        """
        Get current version of file.

        Args:
            file_id: File identifier

        Returns:
            Current FileVersion
        """
        return (
            self.db_session.query(FileVersion)
            .filter(
                FileVersion.file_id == file_id,
                FileVersion.is_current == True,
                FileVersion.is_deleted == False,
            )
            .first()
        )

    async def get_version_history(
        self,
        file_id: str,
        include_deleted: bool = False,
    ) -> List[FileVersion]:
        """
        Get complete version history for file.

        Args:
            file_id: File identifier
            include_deleted: Include deleted versions

        Returns:
            List of versions ordered by version number
        """
        query = self.db_session.query(FileVersion).filter(
            FileVersion.file_id == file_id
        )

        if not include_deleted:
            query = query.filter(FileVersion.is_deleted == False)

        return query.order_by(desc(FileVersion.version_number)).all()

    async def get_version_by_number(
        self,
        file_id: str,
        version_number: int,
    ) -> Optional[FileVersion]:
        """
        Get specific version by number.

        Args:
            file_id: File identifier
            version_number: Version number

        Returns:
            FileVersion if found
        """
        return (
            self.db_session.query(FileVersion)
            .filter(
                FileVersion.file_id == file_id,
                FileVersion.version_number == version_number,
                FileVersion.is_deleted == False,
            )
            .first()
        )

    async def restore_version(
        self,
        file_id: str,
        version_number: int,
        restored_by_user_id: str,
    ) -> FileVersion:
        """
        Restore previous version as current.

        Args:
            file_id: File identifier
            version_number: Version number to restore
            restored_by_user_id: User performing restoration

        Returns:
            New current version (copy of restored version)
        """
        version_to_restore = await self.get_version_by_number(file_id, version_number)

        if not version_to_restore:
            raise ValueError(
                f"Version {version_number} not found for file {file_id}"
            )

        # Create new version based on restored version
        new_version = await self.create_version(
            file_id=file_id,
            version_data={
                "storage_key": version_to_restore.storage_key,
                "size_bytes": version_to_restore.size_bytes,
                "checksum": version_to_restore.checksum,
                "change_type": "restore",
                "change_description": f"Restored from version {version_number}",
                "change_summary": {
                    "restored_from_version": version_number,
                    "restored_at": datetime.utcnow().isoformat(),
                },
            },
            created_by_user_id=restored_by_user_id,
        )

        return new_version

    # ============================================================================
    # FILE ANALYTICS OPERATIONS
    # ============================================================================

    async def get_or_create_analytics(
        self,
        file_id: str,
    ) -> FileAnalytics:
        """
        Get or create analytics record for file.

        Args:
            file_id: File identifier (file_id)

        Returns:
            FileAnalytics record
        """
        analytics = (
            self.db_session.query(FileAnalytics)
            .filter(FileAnalytics.file_id == file_id)
            .first()
        )

        if not analytics:
            analytics = FileAnalytics(
                file_id=file_id,
                total_views=0,
                total_downloads=0,
                unique_viewers=0,
                unique_downloaders=0,
                popularity_score=0.0,
                trending_score=0.0,
                views_today=0,
                views_this_week=0,
                views_this_month=0,
                last_calculated_at=datetime.utcnow(),
            )
            self.db_session.add(analytics)
            self.db_session.commit()

        return analytics

    async def increment_view_count(
        self,
        file_id: str,
        viewer_user_id: Optional[str] = None,
    ) -> FileAnalytics:
        """
        Increment view count for file.

        Args:
            file_id: File identifier
            viewer_user_id: User viewing file

        Returns:
            Updated FileAnalytics
        """
        analytics = await self.get_or_create_analytics(file_id)

        analytics.total_views += 1
        analytics.views_today += 1
        analytics.views_this_week += 1
        analytics.views_this_month += 1
        analytics.last_viewed_at = datetime.utcnow()

        if not analytics.first_viewed_at:
            analytics.first_viewed_at = datetime.utcnow()

        # Update unique viewers count (simplified - should use actual tracking)
        if viewer_user_id:
            analytics.unique_viewers = len(
                set(
                    [
                        log.accessed_by_user_id
                        for log in self.db_session.query(FileAccessLog)
                        .filter(
                            FileAccessLog.file_id == file_id,
                            FileAccessLog.access_type == "view",
                        )
                        .distinct(FileAccessLog.accessed_by_user_id)
                        .all()
                    ]
                )
            )

        self.db_session.commit()
        return analytics

    async def increment_download_count(
        self,
        file_id: str,
        downloader_user_id: Optional[str] = None,
    ) -> FileAnalytics:
        """
        Increment download count for file.

        Args:
            file_id: File identifier
            downloader_user_id: User downloading file

        Returns:
            Updated FileAnalytics
        """
        analytics = await self.get_or_create_analytics(file_id)

        analytics.total_downloads += 1
        analytics.last_downloaded_at = datetime.utcnow()

        # Update unique downloaders count
        if downloader_user_id:
            analytics.unique_downloaders = len(
                set(
                    [
                        log.accessed_by_user_id
                        for log in self.db_session.query(FileAccessLog)
                        .filter(
                            FileAccessLog.file_id == file_id,
                            FileAccessLog.access_type == "download",
                        )
                        .distinct(FileAccessLog.accessed_by_user_id)
                        .all()
                    ]
                )
            )

        self.db_session.commit()
        return analytics

    async def calculate_popularity_scores(
        self,
        batch_size: int = 100,
    ) -> int:
        """
        Calculate popularity and trending scores for files.

        Args:
            batch_size: Number of files to process

        Returns:
            Number of files updated
        """
        # Get analytics records to update
        analytics_list = (
            self.db_session.query(FileAnalytics)
            .order_by(asc(FileAnalytics.last_calculated_at))
            .limit(batch_size)
            .all()
        )

        for analytics in analytics_list:
            # Popularity score (weighted combination of views and downloads)
            view_weight = 1.0
            download_weight = 3.0
            analytics.popularity_score = (
                analytics.total_views * view_weight
                + analytics.total_downloads * download_weight
            )

            # Trending score (recent activity weighted more heavily)
            recent_weight = 5.0
            analytics.trending_score = (
                analytics.views_today * recent_weight
                + analytics.views_this_week * 2.0
                + analytics.views_this_month * 1.0
            )

            analytics.last_calculated_at = datetime.utcnow()

        self.db_session.commit()
        return len(analytics_list)

    async def reset_period_counters(
        self,
        period: str,
    ) -> int:
        """
        Reset period counters (daily, weekly, monthly).

        Args:
            period: Period to reset ('daily', 'weekly', 'monthly')

        Returns:
            Number of records updated
        """
        query = self.db_session.query(FileAnalytics)

        if period == "daily":
            query.update({"views_today": 0})
        elif period == "weekly":
            query.update({"views_this_week": 0})
        elif period == "monthly":
            query.update({"views_this_month": 0})

        count = query.count()
        self.db_session.commit()
        return count

    # ============================================================================
    # FILE ACCESS LOG OPERATIONS
    # ============================================================================

    async def log_file_access(
        self,
        file_id: str,
        access_data: Dict[str, Any],
    ) -> FileAccessLog:
        """
        Log file access event.

        Args:
            file_id: File identifier (file_id)
            access_data: Access event details

        Returns:
            Created FileAccessLog
        """
        access_log = FileAccessLog(
            file_id=file_id,
            storage_key=access_data["storage_key"],
            accessed_by_user_id=access_data.get("accessed_by_user_id"),
            access_type=access_data["access_type"],
            access_method=access_data.get("access_method", "web"),
            ip_address=access_data.get("ip_address"),
            user_agent=access_data.get("user_agent"),
            referrer=access_data.get("referrer"),
            device_type=access_data.get("device_type"),
            browser=access_data.get("browser"),
            operating_system=access_data.get("operating_system"),
            country_code=access_data.get("country_code"),
            country_name=access_data.get("country_name"),
            city=access_data.get("city"),
            region=access_data.get("region"),
            accessed_at=datetime.utcnow(),
            session_duration_seconds=access_data.get("session_duration_seconds"),
            success=access_data.get("success", True),
            status_code=access_data.get("status_code"),
            error_message=access_data.get("error_message"),
            response_time_ms=access_data.get("response_time_ms"),
            bytes_transferred=access_data.get("bytes_transferred"),
            access_context=access_data.get("context", {}),
        )

        self.db_session.add(access_log)
        self.db_session.commit()

        # Update analytics
        if access_data["access_type"] == "view":
            await self.increment_view_count(
                file_id, access_data.get("accessed_by_user_id")
            )
        elif access_data["access_type"] == "download":
            await self.increment_download_count(
                file_id, access_data.get("accessed_by_user_id")
            )

        return access_log

    async def get_access_logs(
        self,
        file_id: str,
        access_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FileAccessLog]:
        """
        Get access logs for file.

        Args:
            file_id: File identifier
            access_type: Filter by access type
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results

        Returns:
            List of access logs
        """
        query = self.db_session.query(FileAccessLog).filter(
            FileAccessLog.file_id == file_id
        )

        if access_type:
            query = query.filter(FileAccessLog.access_type == access_type)

        if start_date:
            query = query.filter(FileAccessLog.accessed_at >= start_date)

        if end_date:
            query = query.filter(FileAccessLog.accessed_at <= end_date)

        return query.order_by(desc(FileAccessLog.accessed_at)).limit(limit).all()

    async def get_user_access_history(
        self,
        user_id: str,
        access_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[FileAccessLog]:
        """
        Get user's file access history.

        Args:
            user_id: User identifier
            access_type: Filter by access type
            limit: Maximum results

        Returns:
            List of access logs
        """
        query = self.db_session.query(FileAccessLog).filter(
            FileAccessLog.accessed_by_user_id == user_id
        )

        if access_type:
            query = query.filter(FileAccessLog.access_type == access_type)

        return query.order_by(desc(FileAccessLog.accessed_at)).limit(limit).all()

    async def get_access_analytics(
        self,
        file_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get access analytics for file.

        Args:
            file_id: File identifier
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Access analytics summary
        """
        query = self.db_session.query(
            func.count(FileAccessLog.id).label("total_accesses"),
            func.count(
                case([(FileAccessLog.access_type == "view", 1)])
            ).label("views"),
            func.count(
                case([(FileAccessLog.access_type == "download", 1)])
            ).label("downloads"),
            func.count(
                case([(FileAccessLog.success == True, 1)])
            ).label("successful"),
            func.count(
                case([(FileAccessLog.success == False, 1)])
            ).label("failed"),
            func.avg(FileAccessLog.response_time_ms).label("avg_response_time"),
        ).filter(FileAccessLog.file_id == file_id)

        if start_date:
            query = query.filter(FileAccessLog.accessed_at >= start_date)

        if end_date:
            query = query.filter(FileAccessLog.accessed_at <= end_date)

        result = query.first()

        return {
            "total_accesses": result.total_accesses or 0,
            "views": result.views or 0,
            "downloads": result.downloads or 0,
            "successful_accesses": result.successful or 0,
            "failed_accesses": result.failed or 0,
            "average_response_time_ms": round(result.avg_response_time or 0, 2),
        }

    # ============================================================================
    # FILE FAVORITE OPERATIONS
    # ============================================================================

    async def add_favorite(
        self,
        file_id: str,
        user_id: str,
        note: Optional[str] = None,
        folder_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> FileFavorite:
        """
        Add file to user favorites.

        Args:
            file_id: File identifier (file_id)
            user_id: User identifier
            note: Personal note
            folder_name: Favorite folder
            tags: Personal tags

        Returns:
            Created FileFavorite

        Raises:
            ValueError: If already favorited
        """
        # Check if already favorited
        existing = await self.get_favorite(file_id, user_id)
        if existing:
            raise ValueError("File already in favorites")

        favorite = FileFavorite(
            file_id=file_id,
            user_id=user_id,
            favorited_at=datetime.utcnow(),
            note=note,
            folder_name=folder_name,
            tags=tags or [],
            access_count=0,
        )

        self.db_session.add(favorite)
        self.db_session.commit()
        return favorite

    async def get_favorite(
        self,
        file_id: str,
        user_id: str,
    ) -> Optional[FileFavorite]:
        """
        Get favorite record.

        Args:
            file_id: File identifier
            user_id: User identifier

        Returns:
            FileFavorite if exists
        """
        return (
            self.db_session.query(FileFavorite)
            .filter(
                FileFavorite.file_id == file_id,
                FileFavorite.user_id == user_id,
            )
            .first()
        )

    async def get_user_favorites(
        self,
        user_id: str,
        folder_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[FileFavorite]:
        """
        Get user's favorite files.

        Args:
            user_id: User identifier
            folder_name: Filter by folder
            tags: Filter by tags
            limit: Maximum results

        Returns:
            List of favorite files
        """
        query = self.db_session.query(FileFavorite).filter(
            FileFavorite.user_id == user_id
        )

        if folder_name:
            query = query.filter(FileFavorite.folder_name == folder_name)

        if tags:
            for tag in tags:
                query = query.filter(FileFavorite.tags.contains([tag]))

        return query.order_by(desc(FileFavorite.favorited_at)).limit(limit).all()

    async def remove_favorite(
        self,
        file_id: str,
        user_id: str,
    ) -> bool:
        """
        Remove file from favorites.

        Args:
            file_id: File identifier
            user_id: User identifier

        Returns:
            True if removed
        """
        favorite = await self.get_favorite(file_id, user_id)

        if favorite:
            self.db_session.delete(favorite)
            self.db_session.commit()
            return True

        return False

    async def track_favorite_access(
        self,
        file_id: str,
        user_id: str,
    ) -> FileFavorite:
        """
        Track access via favorite.

        Args:
            file_id: File identifier
            user_id: User identifier

        Returns:
            Updated FileFavorite
        """
        favorite = await self.get_favorite(file_id, user_id)

        if favorite:
            favorite.last_accessed_at = datetime.utcnow()
            favorite.access_count += 1
            self.db_session.commit()

        return favorite