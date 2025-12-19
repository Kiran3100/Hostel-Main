"""
File Aggregate Repository

Cross-cutting aggregations, analytics, and complex queries across
all file management entities.
"""

from datetime import datetime, timedelta, date as Date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc, asc, case, distinct
from sqlalchemy.orm import Session, joinedload

from app.repositories.base.base_repository import BaseRepository
from app.models.file_management.file_upload import FileUpload, FileQuota
from app.models.file_management.image_upload import (
    ImageUpload,
    ImageProcessing,
    ImageOptimization,
)
from app.models.file_management.document_upload import (
    DocumentUpload,
    DocumentExpiry,
    DocumentVerification,
)
from app.models.file_management.file_metadata import (
    FileAnalytics,
    FileAccessLog,
    FileFavorite,
)


class FileAggregateRepository(BaseRepository[FileUpload]):
    """
    Repository for cross-cutting file management operations,
    aggregations, and complex analytics.
    """

    def __init__(self, db_session: Session):
        super().__init__(FileUpload, db_session)

    # ============================================================================
    # COMPREHENSIVE DASHBOARD ANALYTICS
    # ============================================================================

    async def get_dashboard_summary(
        self,
        user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary for files, images, and documents.

        Args:
            user_id: Filter by user
            hostel_id: Filter by hostel
            start_date: Start date for time-based metrics
            end_date: End date for time-based metrics

        Returns:
            Complete dashboard summary with all metrics
        """
        # File upload metrics
        file_query = self.db_session.query(
            func.count(FileUpload.id).label("total_files"),
            func.sum(FileUpload.size_bytes).label("total_storage"),
            func.count(
                case([(FileUpload.processing_status == "completed", 1)])
            ).label("processed_files"),
            func.count(
                case([(FileUpload.virus_scan_status == "clean", 1)])
            ).label("clean_files"),
            func.count(
                case([(FileUpload.virus_scan_status == "infected", 1)])
            ).label("infected_files"),
        ).filter(FileUpload.deleted_at.is_(None))

        if user_id:
            file_query = file_query.filter(FileUpload.uploaded_by_user_id == user_id)
        if hostel_id:
            file_query = file_query.filter(FileUpload.hostel_id == hostel_id)
        if start_date:
            file_query = file_query.filter(FileUpload.created_at >= start_date)
        if end_date:
            file_query = file_query.filter(FileUpload.created_at <= end_date)

        file_stats = file_query.first()

        # Image metrics
        image_query = (
            self.db_session.query(
                func.count(ImageUpload.id).label("total_images"),
                func.count(
                    case([(ImageUpload.variants_generated == True, 1)])
                ).label("images_with_variants"),
                func.count(
                    case([(ImageUpload.optimization_completed == True, 1)])
                ).label("optimized_images"),
            )
            .join(FileUpload, ImageUpload.file_id == FileUpload.file_id)
            .filter(FileUpload.deleted_at.is_(None))
        )

        if user_id:
            image_query = image_query.filter(
                FileUpload.uploaded_by_user_id == user_id
            )
        if hostel_id:
            image_query = image_query.filter(FileUpload.hostel_id == hostel_id)
        if start_date:
            image_query = image_query.filter(ImageUpload.created_at >= start_date)
        if end_date:
            image_query = image_query.filter(ImageUpload.created_at <= end_date)

        image_stats = image_query.first()

        # Document metrics
        doc_query = self.db_session.query(
            func.count(DocumentUpload.id).label("total_documents"),
            func.count(
                case([(DocumentUpload.verified == True, 1)])
            ).label("verified_documents"),
            func.count(
                case([(DocumentUpload.verification_status == "pending", 1)])
            ).label("pending_verification"),
            func.count(
                case([(DocumentUpload.is_expired == True, 1)])
            ).label("expired_documents"),
            func.count(
                case([(DocumentUpload.ocr_completed == True, 1)])
            ).label("ocr_completed"),
        )

        if user_id:
            doc_query = doc_query.filter(
                DocumentUpload.uploaded_by_user_id == user_id
            )
        if start_date:
            doc_query = doc_query.filter(DocumentUpload.created_at >= start_date)
        if end_date:
            doc_query = doc_query.filter(DocumentUpload.created_at <= end_date)

        doc_stats = doc_query.first()

        # Access analytics
        access_query = self.db_session.query(
            func.count(FileAccessLog.id).label("total_accesses"),
            func.count(
                case([(FileAccessLog.access_type == "view", 1)])
            ).label("views"),
            func.count(
                case([(FileAccessLog.access_type == "download", 1)])
            ).label("downloads"),
            func.count(distinct(FileAccessLog.accessed_by_user_id)).label(
                "unique_users"
            ),
        )

        if start_date:
            access_query = access_query.filter(
                FileAccessLog.accessed_at >= start_date
            )
        if end_date:
            access_query = access_query.filter(FileAccessLog.accessed_at <= end_date)

        access_stats = access_query.first()

        return {
            "files": {
                "total_files": file_stats.total_files or 0,
                "total_storage_bytes": file_stats.total_storage or 0,
                "processed_files": file_stats.processed_files or 0,
                "clean_files": file_stats.clean_files or 0,
                "infected_files": file_stats.infected_files or 0,
            },
            "images": {
                "total_images": image_stats.total_images or 0,
                "images_with_variants": image_stats.images_with_variants or 0,
                "optimized_images": image_stats.optimized_images or 0,
            },
            "documents": {
                "total_documents": doc_stats.total_documents or 0,
                "verified_documents": doc_stats.verified_documents or 0,
                "pending_verification": doc_stats.pending_verification or 0,
                "expired_documents": doc_stats.expired_documents or 0,
                "ocr_completed": doc_stats.ocr_completed or 0,
            },
            "access": {
                "total_accesses": access_stats.total_accesses or 0,
                "total_views": access_stats.views or 0,
                "total_downloads": access_stats.downloads or 0,
                "unique_users": access_stats.unique_users or 0,
            },
        }

    async def get_storage_analytics(
        self,
        user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed storage analytics and breakdown.

        Args:
            user_id: Filter by user
            hostel_id: Filter by hostel

        Returns:
            Storage analytics with breakdowns
        """
        # Overall storage
        query = self.db_session.query(
            func.count(FileUpload.id).label("total_files"),
            func.sum(FileUpload.size_bytes).label("total_bytes"),
            func.avg(FileUpload.size_bytes).label("avg_file_size"),
            func.max(FileUpload.size_bytes).label("largest_file"),
            func.min(FileUpload.size_bytes).label("smallest_file"),
        ).filter(FileUpload.deleted_at.is_(None))

        if user_id:
            query = query.filter(FileUpload.uploaded_by_user_id == user_id)
        if hostel_id:
            query = query.filter(FileUpload.hostel_id == hostel_id)

        overall = query.first()

        # Storage by category
        category_query = (
            self.db_session.query(
                FileUpload.category,
                func.count(FileUpload.id).label("count"),
                func.sum(FileUpload.size_bytes).label("total_bytes"),
            )
            .filter(FileUpload.deleted_at.is_(None))
            .group_by(FileUpload.category)
        )

        if user_id:
            category_query = category_query.filter(
                FileUpload.uploaded_by_user_id == user_id
            )
        if hostel_id:
            category_query = category_query.filter(FileUpload.hostel_id == hostel_id)

        category_breakdown = [
            {
                "category": row.category or "uncategorized",
                "file_count": row.count,
                "total_bytes": row.total_bytes or 0,
                "percentage": (
                    (row.total_bytes / overall.total_bytes * 100)
                    if overall.total_bytes
                    else 0
                ),
            }
            for row in category_query.all()
        ]

        # Storage by content type
        content_type_query = (
            self.db_session.query(
                FileUpload.content_type,
                func.count(FileUpload.id).label("count"),
                func.sum(FileUpload.size_bytes).label("total_bytes"),
            )
            .filter(FileUpload.deleted_at.is_(None))
            .group_by(FileUpload.content_type)
            .order_by(desc("total_bytes"))
            .limit(10)
        )

        if user_id:
            content_type_query = content_type_query.filter(
                FileUpload.uploaded_by_user_id == user_id
            )
        if hostel_id:
            content_type_query = content_type_query.filter(
                FileUpload.hostel_id == hostel_id
            )

        content_type_breakdown = [
            {
                "content_type": row.content_type,
                "file_count": row.count,
                "total_bytes": row.total_bytes or 0,
            }
            for row in content_type_query.all()
        ]

        return {
            "overall": {
                "total_files": overall.total_files or 0,
                "total_bytes": overall.total_bytes or 0,
                "average_file_size_bytes": round(overall.avg_file_size or 0, 2),
                "largest_file_bytes": overall.largest_file or 0,
                "smallest_file_bytes": overall.smallest_file or 0,
            },
            "by_category": category_breakdown,
            "by_content_type": content_type_breakdown,
        }

    async def get_quota_overview(
        self,
        owner_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive quota overview across all owners.

        Args:
            owner_type: Filter by owner type

        Returns:
            Quota overview statistics
        """
        query = self.db_session.query(
            func.count(FileQuota.id).label("total_quotas"),
            func.sum(FileQuota.quota_bytes).label("total_allocated"),
            func.sum(FileQuota.used_bytes).label("total_used"),
            func.sum(FileQuota.reserved_bytes).label("total_reserved"),
            func.count(
                case([(FileQuota.is_exceeded == True, 1)])
            ).label("exceeded_quotas"),
            func.avg(
                (FileQuota.used_bytes + FileQuota.reserved_bytes)
                / FileQuota.quota_bytes
                * 100
            ).label("avg_usage_percentage"),
        )

        if owner_type:
            query = query.filter(FileQuota.owner_type == owner_type)

        result = query.first()

        # Get quotas nearing limit (>80%)
        nearing_limit = (
            self.db_session.query(FileQuota)
            .filter(
                (FileQuota.used_bytes + FileQuota.reserved_bytes)
                / FileQuota.quota_bytes
                >= 0.8,
                FileQuota.is_exceeded == False,
            )
            .count()
        )

        return {
            "total_quotas": result.total_quotas or 0,
            "total_allocated_bytes": result.total_allocated or 0,
            "total_used_bytes": result.total_used or 0,
            "total_reserved_bytes": result.total_reserved or 0,
            "exceeded_quotas": result.exceeded_quotas or 0,
            "quotas_nearing_limit": nearing_limit,
            "average_usage_percentage": round(result.avg_usage_percentage or 0, 2),
        }

    # ============================================================================
    # TREND ANALYSIS
    # ============================================================================

    async def get_upload_trends(
        self,
        period_days: int = 30,
        user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get upload trends over time period.

        Args:
            period_days: Number of days to analyze
            user_id: Filter by user
            hostel_id: Filter by hostel

        Returns:
            Daily upload statistics
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)

        query = (
            self.db_session.query(
                func.date(FileUpload.created_at).label("date"),
                func.count(FileUpload.id).label("upload_count"),
                func.sum(FileUpload.size_bytes).label("total_bytes"),
            )
            .filter(
                FileUpload.created_at >= start_date,
                FileUpload.deleted_at.is_(None),
            )
            .group_by(func.date(FileUpload.created_at))
            .order_by(asc("date"))
        )

        if user_id:
            query = query.filter(FileUpload.uploaded_by_user_id == user_id)
        if hostel_id:
            query = query.filter(FileUpload.hostel_id == hostel_id)

        results = query.all()

        return [
            {
                "date": row.date.isoformat(),
                "upload_count": row.upload_count,
                "total_bytes": row.total_bytes or 0,
            }
            for row in results
        ]

    async def get_access_trends(
        self,
        period_days: int = 30,
        file_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get file access trends over time period.

        Args:
            period_days: Number of days to analyze
            file_id: Filter by specific file

        Returns:
            Daily access statistics
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)

        query = (
            self.db_session.query(
                func.date(FileAccessLog.accessed_at).label("date"),
                func.count(FileAccessLog.id).label("total_accesses"),
                func.count(
                    case([(FileAccessLog.access_type == "view", 1)])
                ).label("views"),
                func.count(
                    case([(FileAccessLog.access_type == "download", 1)])
                ).label("downloads"),
                func.count(distinct(FileAccessLog.accessed_by_user_id)).label(
                    "unique_users"
                ),
            )
            .filter(FileAccessLog.accessed_at >= start_date)
            .group_by(func.date(FileAccessLog.accessed_at))
            .order_by(asc("date"))
        )

        if file_id:
            query = query.filter(FileAccessLog.file_id == file_id)

        results = query.all()

        return [
            {
                "date": row.date.isoformat(),
                "total_accesses": row.total_accesses,
                "views": row.views,
                "downloads": row.downloads,
                "unique_users": row.unique_users,
            }
            for row in results
        ]

    # ============================================================================
    # TOP FILES AND RANKINGS
    # ============================================================================

    async def get_most_popular_files(
        self,
        limit: int = 20,
        period_days: Optional[int] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get most popular files by access metrics.

        Args:
            limit: Maximum results
            period_days: Limit to recent period
            category: Filter by category

        Returns:
            List of popular files with metrics
        """
        query = (
            self.db_session.query(
                FileUpload.file_id,
                FileUpload.filename,
                FileUpload.category,
                FileAnalytics.total_views,
                FileAnalytics.total_downloads,
                FileAnalytics.popularity_score,
                FileAnalytics.unique_viewers,
            )
            .join(FileAnalytics, FileUpload.file_id == FileAnalytics.file_id)
            .filter(FileUpload.deleted_at.is_(None))
        )

        if period_days:
            start_date = datetime.utcnow() - timedelta(days=period_days)
            query = query.filter(FileUpload.created_at >= start_date)

        if category:
            query = query.filter(FileUpload.category == category)

        results = query.order_by(desc(FileAnalytics.popularity_score)).limit(limit).all()

        return [
            {
                "file_id": row.file_id,
                "filename": row.filename,
                "category": row.category,
                "total_views": row.total_views,
                "total_downloads": row.total_downloads,
                "popularity_score": row.popularity_score,
                "unique_viewers": row.unique_viewers,
            }
            for row in results
        ]

    async def get_trending_files(
        self,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get currently trending files based on recent activity.

        Args:
            limit: Maximum results
            category: Filter by category

        Returns:
            List of trending files
        """
        query = (
            self.db_session.query(
                FileUpload.file_id,
                FileUpload.filename,
                FileUpload.category,
                FileAnalytics.trending_score,
                FileAnalytics.views_today,
                FileAnalytics.views_this_week,
            )
            .join(FileAnalytics, FileUpload.file_id == FileAnalytics.file_id)
            .filter(FileUpload.deleted_at.is_(None))
        )

        if category:
            query = query.filter(FileUpload.category == category)

        results = query.order_by(desc(FileAnalytics.trending_score)).limit(limit).all()

        return [
            {
                "file_id": row.file_id,
                "filename": row.filename,
                "category": row.category,
                "trending_score": row.trending_score,
                "views_today": row.views_today,
                "views_this_week": row.views_this_week,
            }
            for row in results
        ]

    async def get_largest_files(
        self,
        limit: int = 20,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get largest files by size.

        Args:
            limit: Maximum results
            category: Filter by category
            user_id: Filter by user

        Returns:
            List of largest files
        """
        query = (
            self.db_session.query(
                FileUpload.file_id,
                FileUpload.filename,
                FileUpload.category,
                FileUpload.size_bytes,
                FileUpload.content_type,
                FileUpload.created_at,
            )
            .filter(FileUpload.deleted_at.is_(None))
        )

        if category:
            query = query.filter(FileUpload.category == category)

        if user_id:
            query = query.filter(FileUpload.uploaded_by_user_id == user_id)

        results = query.order_by(desc(FileUpload.size_bytes)).limit(limit).all()

        return [
            {
                "file_id": row.file_id,
                "filename": row.filename,
                "category": row.category,
                "size_bytes": row.size_bytes,
                "content_type": row.content_type,
                "created_at": row.created_at.isoformat(),
            }
            for row in results
        ]

    # ============================================================================
    # PROCESSING STATUS OVERVIEW
    # ============================================================================

    async def get_processing_overview(self) -> Dict[str, Any]:
        """
        Get comprehensive processing status overview.

        Returns:
            Processing status across all file types
        """
        # File processing
        file_processing = self.db_session.query(
            func.count(FileUpload.id).label("total"),
            func.count(
                case([(FileUpload.processing_status == "pending", 1)])
            ).label("pending"),
            func.count(
                case([(FileUpload.processing_status == "processing", 1)])
            ).label("processing"),
            func.count(
                case([(FileUpload.processing_status == "completed", 1)])
            ).label("completed"),
            func.count(
                case([(FileUpload.processing_status == "failed", 1)])
            ).label("failed"),
        ).filter(FileUpload.deleted_at.is_(None)).first()

        # Image processing queue
        image_processing = self.db_session.query(
            func.count(ImageProcessing.id).label("total"),
            func.count(
                case([(ImageProcessing.status == "pending", 1)])
            ).label("pending"),
            func.count(
                case([(ImageProcessing.status == "processing", 1)])
            ).label("processing"),
            func.count(
                case([(ImageProcessing.status == "completed", 1)])
            ).label("completed"),
            func.count(
                case([(ImageProcessing.status == "failed", 1)])
            ).label("failed"),
        ).first()

        # Document OCR
        doc_ocr = self.db_session.query(
            func.count(DocumentUpload.id).label("total"),
            func.count(
                case([(DocumentUpload.ocr_status == "pending", 1)])
            ).label("pending"),
            func.count(
                case([(DocumentUpload.ocr_status == "processing", 1)])
            ).label("processing"),
            func.count(
                case([(DocumentUpload.ocr_status == "completed", 1)])
            ).label("completed"),
            func.count(
                case([(DocumentUpload.ocr_status == "failed", 1)])
            ).label("failed"),
        ).first()

        # Document verification
        doc_verification = self.db_session.query(
            func.count(DocumentUpload.id).label("total"),
            func.count(
                case([(DocumentUpload.verification_status == "pending", 1)])
            ).label("pending"),
            func.count(
                case([(DocumentUpload.verification_status == "verified", 1)])
            ).label("verified"),
            func.count(
                case([(DocumentUpload.verification_status == "rejected", 1)])
            ).label("rejected"),
        ).first()

        return {
            "file_processing": {
                "total": file_processing.total or 0,
                "pending": file_processing.pending or 0,
                "processing": file_processing.processing or 0,
                "completed": file_processing.completed or 0,
                "failed": file_processing.failed or 0,
            },
            "image_processing": {
                "total": image_processing.total or 0,
                "pending": image_processing.pending or 0,
                "processing": image_processing.processing or 0,
                "completed": image_processing.completed or 0,
                "failed": image_processing.failed or 0,
            },
            "document_ocr": {
                "total": doc_ocr.total or 0,
                "pending": doc_ocr.pending or 0,
                "processing": doc_ocr.processing or 0,
                "completed": doc_ocr.completed or 0,
                "failed": doc_ocr.failed or 0,
            },
            "document_verification": {
                "total": doc_verification.total or 0,
                "pending": doc_verification.pending or 0,
                "verified": doc_verification.verified or 0,
                "rejected": doc_verification.rejected or 0,
            },
        }

    # ============================================================================
    # OPTIMIZATION OPPORTUNITIES
    # ============================================================================

    async def identify_optimization_opportunities(
        self,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Identify files that could benefit from optimization.

        Args:
            limit: Maximum files to analyze

        Returns:
            Optimization opportunities and recommendations
        """
        # Large unoptimized images
        large_images = (
            self.db_session.query(
                ImageUpload.id,
                FileUpload.file_id,
                FileUpload.filename,
                ImageUpload.original_size_bytes,
                ImageUpload.original_width,
                ImageUpload.original_height,
            )
            .join(FileUpload, ImageUpload.file_id == FileUpload.file_id)
            .filter(
                ImageUpload.optimization_completed == False,
                ImageUpload.original_size_bytes > 1024 * 1024,  # > 1MB
                FileUpload.deleted_at.is_(None),
            )
            .order_by(desc(ImageUpload.original_size_bytes))
            .limit(limit)
            .all()
        )

        # Images without variants
        images_without_variants = (
            self.db_session.query(ImageUpload)
            .join(FileUpload, ImageUpload.file_id == FileUpload.file_id)
            .filter(
                ImageUpload.generate_variants == True,
                ImageUpload.variants_generated == False,
                FileUpload.deleted_at.is_(None),
            )
            .count()
        )

        # Unused files (not accessed in 90 days)
        unused_threshold = datetime.utcnow() - timedelta(days=90)
        unused_files = (
            self.db_session.query(
                func.count(FileUpload.id).label("count"),
                func.sum(FileUpload.size_bytes).label("total_bytes"),
            )
            .filter(
                FileUpload.deleted_at.is_(None),
                or_(
                    FileUpload.last_accessed_at.is_(None),
                    FileUpload.last_accessed_at < unused_threshold,
                ),
                FileUpload.created_at < unused_threshold,
            )
            .first()
        )

        # Calculate potential savings from optimization
        unoptimized_images = (
            self.db_session.query(
                func.sum(ImageUpload.original_size_bytes).label("total_size")
            )
            .join(FileUpload, ImageUpload.file_id == FileUpload.file_id)
            .filter(
                ImageUpload.optimization_completed == False,
                FileUpload.deleted_at.is_(None),
            )
            .first()
        )

        # Get average optimization savings from completed optimizations
        avg_savings = (
            self.db_session.query(
                func.avg(ImageOptimization.reduction_percentage).label("avg_reduction")
            ).first()
        )

        estimated_savings = 0
        if unoptimized_images.total_size and avg_savings.avg_reduction:
            estimated_savings = int(
                unoptimized_images.total_size * (avg_savings.avg_reduction / 100)
            )

        return {
            "large_unoptimized_images": {
                "count": len(large_images),
                "files": [
                    {
                        "file_id": img.file_id,
                        "filename": img.filename,
                        "size_bytes": img.original_size_bytes,
                        "dimensions": f"{img.original_width}x{img.original_height}",
                    }
                    for img in large_images[:10]  # Return top 10
                ],
            },
            "images_needing_variants": images_without_variants,
            "unused_files": {
                "count": unused_files.count or 0,
                "total_bytes": unused_files.total_bytes or 0,
            },
            "optimization_potential": {
                "unoptimized_bytes": unoptimized_images.total_size or 0,
                "estimated_savings_bytes": estimated_savings,
                "average_reduction_percentage": round(
                    avg_savings.avg_reduction or 0, 2
                ),
            },
        }

    # ============================================================================
    # COMPLIANCE AND ALERTS
    # ============================================================================

    async def get_compliance_alerts(self) -> Dict[str, Any]:
        """
        Get compliance alerts for documents and files.

        Returns:
            Compliance alerts and warnings
        """
        # Expiring documents (within 30 days)
        expiring_threshold = Date.today() + timedelta(days=30)
        expiring_docs = (
            self.db_session.query(DocumentExpiry)
            .filter(
                DocumentExpiry.is_expired == False,
                DocumentExpiry.expiry_date <= expiring_threshold,
            )
            .count()
        )

        # Expired documents
        expired_docs = (
            self.db_session.query(DocumentExpiry)
            .filter(DocumentExpiry.is_expired == True)
            .count()
        )

        # Documents pending verification
        pending_verification = (
            self.db_session.query(DocumentUpload)
            .filter(DocumentUpload.verification_status == "pending")
            .count()
        )

        # Infected files
        infected_files = (
            self.db_session.query(FileUpload)
            .filter(
                FileUpload.virus_scan_status == "infected",
                FileUpload.deleted_at.is_(None),
            )
            .count()
        )

        # Failed processing
        failed_processing = (
            self.db_session.query(FileUpload)
            .filter(
                FileUpload.processing_status == "failed",
                FileUpload.deleted_at.is_(None),
            )
            .count()
        )

        # Quota exceeded
        quota_exceeded = (
            self.db_session.query(FileQuota)
            .filter(
                FileQuota.is_exceeded == True,
                FileQuota.is_enforced == True,
            )
            .count()
        )

        # Quota warnings (>80% usage)
        quota_warnings = (
            self.db_session.query(FileQuota)
            .filter(
                (FileQuota.used_bytes + FileQuota.reserved_bytes)
                / FileQuota.quota_bytes
                >= 0.8,
                FileQuota.is_exceeded == False,
            )
            .count()
        )

        return {
            "documents": {
                "expiring_soon": expiring_docs,
                "expired": expired_docs,
                "pending_verification": pending_verification,
            },
            "files": {
                "infected": infected_files,
                "failed_processing": failed_processing,
            },
            "quotas": {
                "exceeded": quota_exceeded,
                "warnings": quota_warnings,
            },
        }

    # ============================================================================
    # USER ACTIVITY INSIGHTS
    # ============================================================================

    async def get_user_file_activity(
        self,
        user_id: str,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get comprehensive file activity for a user.

        Args:
            user_id: User identifier
            period_days: Period to analyze

        Returns:
            User's file activity summary
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)

        # Upload activity
        uploads = (
            self.db_session.query(
                func.count(FileUpload.id).label("count"),
                func.sum(FileUpload.size_bytes).label("total_bytes"),
            )
            .filter(
                FileUpload.uploaded_by_user_id == user_id,
                FileUpload.created_at >= start_date,
                FileUpload.deleted_at.is_(None),
            )
            .first()
        )

        # Access activity
        accesses = (
            self.db_session.query(
                func.count(FileAccessLog.id).label("total"),
                func.count(
                    case([(FileAccessLog.access_type == "view", 1)])
                ).label("views"),
                func.count(
                    case([(FileAccessLog.access_type == "download", 1)])
                ).label("downloads"),
            )
            .filter(
                FileAccessLog.accessed_by_user_id == user_id,
                FileAccessLog.accessed_at >= start_date,
            )
            .first()
        )

        # Favorites
        favorites_count = (
            self.db_session.query(FileFavorite)
            .filter(FileFavorite.user_id == user_id)
            .count()
        )

        # Recent uploads
        recent_uploads = (
            self.db_session.query(FileUpload)
            .filter(
                FileUpload.uploaded_by_user_id == user_id,
                FileUpload.deleted_at.is_(None),
            )
            .order_by(desc(FileUpload.created_at))
            .limit(5)
            .all()
        )

        # Recent accesses
        recent_accesses = (
            self.db_session.query(FileAccessLog)
            .filter(FileAccessLog.accessed_by_user_id == user_id)
            .order_by(desc(FileAccessLog.accessed_at))
            .limit(5)
            .all()
        )

        return {
            "period_days": period_days,
            "uploads": {
                "count": uploads.count or 0,
                "total_bytes": uploads.total_bytes or 0,
            },
            "accesses": {
                "total": accesses.total or 0,
                "views": accesses.views or 0,
                "downloads": accesses.downloads or 0,
            },
            "favorites_count": favorites_count,
            "recent_uploads": [
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "size_bytes": f.size_bytes,
                    "created_at": f.created_at.isoformat(),
                }
                for f in recent_uploads
            ],
            "recent_accesses": [
                {
                    "file_id": a.file_id,
                    "access_type": a.access_type,
                    "accessed_at": a.accessed_at.isoformat(),
                }
                for a in recent_accesses
            ],
        }

    # ============================================================================
    # BATCH CLEANUP OPERATIONS
    # ============================================================================

    async def cleanup_orphaned_records(
        self,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Clean up orphaned records across all file management tables.

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Count of cleaned records by type
        """
        cleaned = {
            "orphaned_analytics": 0,
            "orphaned_access_logs": 0,
            "orphaned_favorites": 0,
        }

        # Find and delete analytics for deleted files
        orphaned_analytics = (
            self.db_session.query(FileAnalytics)
            .outerjoin(FileUpload, FileAnalytics.file_id == FileUpload.file_id)
            .filter(FileUpload.id.is_(None))
            .limit(batch_size)
            .all()
        )

        for analytics in orphaned_analytics:
            self.db_session.delete(analytics)
            cleaned["orphaned_analytics"] += 1

        # Find and delete access logs for deleted files
        orphaned_logs = (
            self.db_session.query(FileAccessLog)
            .outerjoin(FileUpload, FileAccessLog.file_id == FileUpload.file_id)
            .filter(FileUpload.id.is_(None))
            .limit(batch_size)
            .all()
        )

        for log in orphaned_logs:
            self.db_session.delete(log)
            cleaned["orphaned_access_logs"] += 1

        # Find and delete favorites for deleted files
        orphaned_favorites = (
            self.db_session.query(FileFavorite)
            .outerjoin(FileUpload, FileFavorite.file_id == FileUpload.file_id)
            .filter(FileUpload.id.is_(None))
            .limit(batch_size)
            .all()
        )

        for favorite in orphaned_favorites:
            self.db_session.delete(favorite)
            cleaned["orphaned_favorites"] += 1

        self.db_session.commit()
        return cleaned

    async def archive_old_access_logs(
        self,
        days_old: int = 365,
        batch_size: int = 1000,
    ) -> int:
        """
        Archive old access logs.

        Args:
            days_old: Age threshold in days
            batch_size: Number of logs to archive

        Returns:
            Number of logs archived
        """
        threshold_date = datetime.utcnow() - timedelta(days=days_old)

        old_logs = (
            self.db_session.query(FileAccessLog)
            .filter(FileAccessLog.accessed_at < threshold_date)
            .limit(batch_size)
            .all()
        )

        # In a real implementation, you would archive to cold storage
        # For now, we'll just delete them
        for log in old_logs:
            self.db_session.delete(log)

        self.db_session.commit()
        return len(old_logs)