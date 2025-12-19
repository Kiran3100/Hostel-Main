"""
Image Upload Repository

Image-specific operations with variant generation, processing queue,
optimization, and metadata extraction.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload, selectinload

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager, PaginatedResult
from app.models.file_management.image_upload import (
    ImageUpload,
    ImageVariant,
    ImageProcessing,
    ImageOptimization,
    ImageMetadata,
)
from app.models.file_management.file_upload import FileUpload


class ImageUploadRepository(BaseRepository[ImageUpload]):
    """
    Repository for image upload operations with variant management,
    processing queue, and optimization tracking.
    """

    def __init__(self, db_session: Session):
        super().__init__(ImageUpload, db_session)

    # ============================================================================
    # CORE IMAGE OPERATIONS
    # ============================================================================

    async def create_image_upload(
        self,
        file_id: str,
        image_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> ImageUpload:
        """
        Create image upload record with processing configuration.

        Args:
            file_id: Associated file upload ID
            image_data: Image properties and configuration
            audit_context: Audit context

        Returns:
            Created ImageUpload
        """
        image = ImageUpload(
            file_id=file_id,
            usage=image_data["usage"],
            original_width=image_data["original_width"],
            original_height=image_data["original_height"],
            original_format=image_data["original_format"],
            original_mode=image_data.get("original_mode"),
            has_alpha=image_data.get("has_alpha", False),
            color_space=image_data.get("color_space"),
            dominant_colors=image_data.get("dominant_colors", []),
            generate_variants=image_data.get("generate_variants", True),
            auto_optimize=image_data.get("auto_optimize", True),
            convert_to_webp=image_data.get("convert_to_webp", False),
            quality=image_data.get("quality", 85),
            add_watermark=image_data.get("add_watermark", False),
            original_size_bytes=image_data["original_size_bytes"],
        )

        created_image = await self.create(image, audit_context)

        # Create processing queue entry if auto-processing enabled
        if image_data.get("generate_variants") or image_data.get("auto_optimize"):
            await self.queue_for_processing(
                created_image.id,
                priority=image_data.get("processing_priority", 5),
            )

        return created_image

    async def find_by_file_id(
        self,
        file_id: str,
        load_relationships: bool = False,
    ) -> Optional[ImageUpload]:
        """
        Find image by file ID.

        Args:
            file_id: File upload ID
            load_relationships: Whether to load relationships

        Returns:
            ImageUpload if found
        """
        query = self.db_session.query(ImageUpload).filter(
            ImageUpload.file_id == file_id
        )

        if load_relationships:
            query = query.options(
                joinedload(ImageUpload.file),
                selectinload(ImageUpload.variants),
                joinedload(ImageUpload.processing),
                joinedload(ImageUpload.optimization),
                joinedload(ImageUpload.metadata),
            )

        return query.first()

    async def search_images(
        self,
        criteria: Dict[str, Any],
        pagination: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResult[ImageUpload]:
        """
        Search images with flexible criteria.

        Args:
            criteria: Search criteria
            pagination: Pagination parameters
            sort_by: Sort field
            sort_order: Sort order

        Returns:
            Paginated image results

        Criteria:
            - usage: Filter by usage type
            - min_width: Minimum width
            - max_width: Maximum width
            - min_height: Minimum height
            - max_height: Maximum height
            - format: Original format
            - has_alpha: Filter by alpha channel
            - variants_generated: Filter by variant status
            - optimization_completed: Filter by optimization status
            - created_after: Images created after date
            - created_before: Images created before date
        """
        query = QueryBuilder(ImageUpload, self.db_session)

        if "usage" in criteria:
            query = query.where(ImageUpload.usage == criteria["usage"])

        if "min_width" in criteria:
            query = query.where(ImageUpload.original_width >= criteria["min_width"])

        if "max_width" in criteria:
            query = query.where(ImageUpload.original_width <= criteria["max_width"])

        if "min_height" in criteria:
            query = query.where(ImageUpload.original_height >= criteria["min_height"])

        if "max_height" in criteria:
            query = query.where(ImageUpload.original_height <= criteria["max_height"])

        if "format" in criteria:
            query = query.where(ImageUpload.original_format == criteria["format"])

        if "has_alpha" in criteria:
            query = query.where(ImageUpload.has_alpha == criteria["has_alpha"])

        if "variants_generated" in criteria:
            query = query.where(
                ImageUpload.variants_generated == criteria["variants_generated"]
            )

        if "optimization_completed" in criteria:
            query = query.where(
                ImageUpload.optimization_completed == criteria["optimization_completed"]
            )

        if "created_after" in criteria:
            query = query.where(ImageUpload.created_at >= criteria["created_after"])

        if "created_before" in criteria:
            query = query.where(ImageUpload.created_at <= criteria["created_before"])

        # Apply sorting
        sort_field = getattr(ImageUpload, sort_by, ImageUpload.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        return await PaginationManager.paginate(
            query.build(),
            pagination or {"page": 1, "page_size": 50}
        )

    # ============================================================================
    # IMAGE VARIANT OPERATIONS
    # ============================================================================

    async def create_variant(
        self,
        image_id: str,
        variant_data: Dict[str, Any],
    ) -> ImageVariant:
        """
        Create image variant record.

        Args:
            image_id: Parent image ID
            variant_data: Variant properties

        Returns:
            Created ImageVariant
        """
        variant = ImageVariant(
            image_id=image_id,
            variant_name=variant_data["variant_name"],
            storage_key=variant_data["storage_key"],
            width=variant_data["width"],
            height=variant_data["height"],
            format=variant_data["format"],
            size_bytes=variant_data["size_bytes"],
            url=variant_data["url"],
            public_url=variant_data.get("public_url"),
            is_optimized=variant_data.get("is_optimized", False),
            quality=variant_data.get("quality"),
            generated_at=datetime.utcnow(),
            generation_duration_ms=variant_data.get("generation_duration_ms"),
        )

        self.db_session.add(variant)
        self.db_session.commit()
        return variant

    async def get_variants(
        self,
        image_id: str,
        variant_name: Optional[str] = None,
    ) -> List[ImageVariant]:
        """
        Get image variants.

        Args:
            image_id: Image ID
            variant_name: Optional specific variant name

        Returns:
            List of variants
        """
        query = self.db_session.query(ImageVariant).filter(
            ImageVariant.image_id == image_id
        )

        if variant_name:
            query = query.filter(ImageVariant.variant_name == variant_name)

        return query.all()

    async def get_variant_by_name(
        self,
        image_id: str,
        variant_name: str,
    ) -> Optional[ImageVariant]:
        """
        Get specific variant by name.

        Args:
            image_id: Image ID
            variant_name: Variant name

        Returns:
            ImageVariant if found
        """
        return (
            self.db_session.query(ImageVariant)
            .filter(
                ImageVariant.image_id == image_id,
                ImageVariant.variant_name == variant_name,
            )
            .first()
        )

    async def mark_variants_generated(
        self,
        image_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> ImageUpload:
        """
        Mark image variants as generated.

        Args:
            image_id: Image ID
            audit_context: Audit context

        Returns:
            Updated ImageUpload
        """
        return await self.update(
            image_id,
            {
                "variants_generated": True,
                "processing_completed_at": datetime.utcnow(),
            },
            audit_context=audit_context,
        )

    # ============================================================================
    # IMAGE PROCESSING OPERATIONS
    # ============================================================================

    async def queue_for_processing(
        self,
        image_id: str,
        priority: int = 5,
        processing_config: Optional[Dict[str, Any]] = None,
    ) -> ImageProcessing:
        """
        Add image to processing queue.

        Args:
            image_id: Image ID
            priority: Processing priority (1-10, higher is more urgent)
            processing_config: Processing configuration

        Returns:
            Created ImageProcessing record
        """
        # Determine required processing steps
        image = await self.find_by_id(image_id)
        steps = []

        if image.generate_variants:
            steps.append("generate_variants")

        if image.auto_optimize:
            steps.append("optimize")

        if image.convert_to_webp:
            steps.append("convert_webp")

        if image.add_watermark:
            steps.append("add_watermark")

        processing = ImageProcessing(
            image_id=image_id,
            status="pending",
            priority=priority,
            pending_steps=steps,
            completed_steps=[],
            queued_at=datetime.utcnow(),
            processing_config=processing_config or {},
        )

        self.db_session.add(processing)
        self.db_session.commit()
        return processing

    async def get_next_processing_job(
        self,
        worker_id: str,
    ) -> Optional[ImageProcessing]:
        """
        Get next image processing job for worker.

        Args:
            worker_id: Worker identifier

        Returns:
            ImageProcessing job if available
        """
        job = (
            self.db_session.query(ImageProcessing)
            .filter(ImageProcessing.status == "pending")
            .order_by(desc(ImageProcessing.priority), asc(ImageProcessing.queued_at))
            .first()
        )

        if job:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            job.worker_id = worker_id
            self.db_session.commit()

        return job

    async def update_processing_progress(
        self,
        processing_id: str,
        current_step: str,
        progress_percentage: float,
        completed_steps: Optional[List[str]] = None,
    ) -> ImageProcessing:
        """
        Update processing progress.

        Args:
            processing_id: Processing job ID
            current_step: Current step being processed
            progress_percentage: Progress percentage
            completed_steps: List of completed steps

        Returns:
            Updated ImageProcessing
        """
        processing = self.db_session.query(ImageProcessing).get(processing_id)

        if not processing:
            raise ValueError(f"Processing job not found: {processing_id}")

        processing.current_step = current_step
        processing.progress_percentage = progress_percentage

        if completed_steps:
            processing.completed_steps = completed_steps

        self.db_session.commit()
        return processing

    async def complete_processing(
        self,
        processing_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> ImageProcessing:
        """
        Mark processing as completed.

        Args:
            processing_id: Processing job ID
            success: Whether processing succeeded
            error_message: Error message if failed
            error_details: Detailed error information

        Returns:
            Updated ImageProcessing
        """
        processing = self.db_session.query(ImageProcessing).get(processing_id)

        if not processing:
            raise ValueError(f"Processing job not found: {processing_id}")

        processing.status = "completed" if success else "failed"
        processing.completed_at = datetime.utcnow()
        processing.progress_percentage = 100.0 if success else processing.progress_percentage

        if not success:
            processing.error_message = error_message
            processing.error_details = error_details

            # Retry if under limit
            if processing.retry_count < processing.max_retries:
                processing.status = "pending"
                processing.retry_count += 1
                processing.last_retry_at = datetime.utcnow()
                processing.started_at = None
                processing.worker_id = None

        self.db_session.commit()
        return processing

    async def get_processing_queue_stats(self) -> Dict[str, Any]:
        """
        Get processing queue statistics.

        Returns:
            Queue statistics
        """
        stats = self.db_session.query(
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

        return {
            "total_jobs": stats.total or 0,
            "pending": stats.pending or 0,
            "processing": stats.processing or 0,
            "completed": stats.completed or 0,
            "failed": stats.failed or 0,
        }

    # ============================================================================
    # IMAGE OPTIMIZATION OPERATIONS
    # ============================================================================

    async def create_optimization_result(
        self,
        image_id: str,
        optimization_data: Dict[str, Any],
    ) -> ImageOptimization:
        """
        Store image optimization results.

        Args:
            image_id: Image ID
            optimization_data: Optimization results

        Returns:
            Created ImageOptimization
        """
        optimization = ImageOptimization(
            image_id=image_id,
            optimization_level=optimization_data.get("optimization_level", "medium"),
            target_format=optimization_data.get("target_format"),
            target_quality=optimization_data.get("target_quality", 85),
            compression_algorithm=optimization_data.get("compression_algorithm"),
            compression_level=optimization_data.get("compression_level"),
            strip_metadata=optimization_data.get("strip_metadata", True),
            preserve_exif=optimization_data.get("preserve_exif", False),
            auto_orient=optimization_data.get("auto_orient", True),
            original_size_bytes=optimization_data["original_size_bytes"],
            optimized_size_bytes=optimization_data["optimized_size_bytes"],
            bytes_saved=optimization_data["original_size_bytes"] - optimization_data["optimized_size_bytes"],
            reduction_percentage=(
                (optimization_data["original_size_bytes"] - optimization_data["optimized_size_bytes"])
                / optimization_data["original_size_bytes"] * 100
            ),
            visual_quality_score=optimization_data.get("visual_quality_score"),
            ssim_score=optimization_data.get("ssim_score"),
            optimization_duration_ms=optimization_data.get("optimization_duration_ms"),
            optimized_at=datetime.utcnow(),
            optimization_tool=optimization_data.get("optimization_tool"),
            tool_version=optimization_data.get("tool_version"),
        )

        self.db_session.add(optimization)
        self.db_session.commit()

        # Update parent image
        image = await self.find_by_id(image_id)
        image.optimization_completed = True
        image.optimized_size_bytes = optimization_data["optimized_size_bytes"]
        image.size_reduction_percentage = optimization.reduction_percentage
        self.db_session.commit()

        return optimization

    async def get_optimization_result(
        self,
        image_id: str,
    ) -> Optional[ImageOptimization]:
        """
        Get optimization result for image.

        Args:
            image_id: Image ID

        Returns:
            ImageOptimization if exists
        """
        return (
            self.db_session.query(ImageOptimization)
            .filter(ImageOptimization.image_id == image_id)
            .first()
        )

    async def get_optimization_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get optimization statistics.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Optimization statistics
        """
        query = self.db_session.query(
            func.count(ImageOptimization.id).label("total_optimizations"),
            func.sum(ImageOptimization.bytes_saved).label("total_bytes_saved"),
            func.avg(ImageOptimization.reduction_percentage).label("avg_reduction"),
            func.avg(ImageOptimization.optimization_duration_ms).label("avg_duration"),
        )

        if start_date:
            query = query.filter(ImageOptimization.optimized_at >= start_date)

        if end_date:
            query = query.filter(ImageOptimization.optimized_at <= end_date)

        result = query.first()

        return {
            "total_optimizations": result.total_optimizations or 0,
            "total_bytes_saved": result.total_bytes_saved or 0,
            "average_reduction_percentage": round(result.avg_reduction or 0, 2),
            "average_duration_ms": round(result.avg_duration or 0, 2),
        }

    # ============================================================================
    # IMAGE METADATA OPERATIONS
    # ============================================================================

    async def create_metadata(
        self,
        image_id: str,
        metadata_data: Dict[str, Any],
    ) -> ImageMetadata:
        """
        Store image metadata (EXIF, etc.).

        Args:
            image_id: Image ID
            metadata_data: Extracted metadata

        Returns:
            Created ImageMetadata
        """
        metadata = ImageMetadata(
            image_id=image_id,
            camera_make=metadata_data.get("camera_make"),
            camera_model=metadata_data.get("camera_model"),
            lens_model=metadata_data.get("lens_model"),
            iso=metadata_data.get("iso"),
            aperture=metadata_data.get("aperture"),
            shutter_speed=metadata_data.get("shutter_speed"),
            focal_length=metadata_data.get("focal_length"),
            flash=metadata_data.get("flash"),
            date_taken=metadata_data.get("date_taken"),
            date_modified=metadata_data.get("date_modified"),
            gps_latitude=metadata_data.get("gps_latitude"),
            gps_longitude=metadata_data.get("gps_longitude"),
            gps_altitude=metadata_data.get("gps_altitude"),
            location_name=metadata_data.get("location_name"),
            orientation=metadata_data.get("orientation"),
            resolution_x=metadata_data.get("resolution_x"),
            resolution_y=metadata_data.get("resolution_y"),
            bit_depth=metadata_data.get("bit_depth"),
            software=metadata_data.get("software"),
            copyright=metadata_data.get("copyright"),
            artist=metadata_data.get("artist"),
            description=metadata_data.get("description"),
            keywords=metadata_data.get("keywords", []),
            raw_exif=metadata_data.get("raw_exif", {}),
            extracted_at=datetime.utcnow(),
            extraction_tool=metadata_data.get("extraction_tool"),
        )

        self.db_session.add(metadata)
        self.db_session.commit()
        return metadata

    async def get_metadata(
        self,
        image_id: str,
    ) -> Optional[ImageMetadata]:
        """
        Get image metadata.

        Args:
            image_id: Image ID

        Returns:
            ImageMetadata if exists
        """
        return (
            self.db_session.query(ImageMetadata)
            .filter(ImageMetadata.image_id == image_id)
            .first()
        )

    async def search_by_location(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        limit: int = 100,
    ) -> List[ImageMetadata]:
        """
        Search images by geographic location.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            limit: Maximum results

        Returns:
            List of images within radius
        """
        # Simple bounding box search (for precise distance, use PostGIS or similar)
        lat_delta = radius_km / 111.0  # Approximate km per degree latitude
        lon_delta = radius_km / (111.0 * abs(latitude))  # Adjust for latitude

        return (
            self.db_session.query(ImageMetadata)
            .filter(
                ImageMetadata.gps_latitude.between(
                    latitude - lat_delta, latitude + lat_delta
                ),
                ImageMetadata.gps_longitude.between(
                    longitude - lon_delta, longitude + lon_delta
                ),
            )
            .limit(limit)
            .all()
        )

    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================

    async def get_image_statistics(
        self,
        usage: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get image upload statistics.

        Args:
            usage: Filter by usage type
            start_date: Start date
            end_date: End date

        Returns:
            Image statistics
        """
        query = self.db_session.query(
            func.count(ImageUpload.id).label("total_images"),
            func.avg(ImageUpload.original_width).label("avg_width"),
            func.avg(ImageUpload.original_height).label("avg_height"),
            func.sum(ImageUpload.original_size_bytes).label("total_size"),
            func.count(
                case([(ImageUpload.variants_generated == True, 1)])
            ).label("with_variants"),
            func.count(
                case([(ImageUpload.optimization_completed == True, 1)])
            ).label("optimized"),
        )

        if usage:
            query = query.filter(ImageUpload.usage == usage)

        if start_date:
            query = query.filter(ImageUpload.created_at >= start_date)

        if end_date:
            query = query.filter(ImageUpload.created_at <= end_date)

        result = query.first()

        return {
            "total_images": result.total_images or 0,
            "average_width": round(result.avg_width or 0, 2),
            "average_height": round(result.avg_height or 0, 2),
            "total_size_bytes": result.total_size or 0,
            "images_with_variants": result.with_variants or 0,
            "optimized_images": result.optimized or 0,
        }

    async def get_format_distribution(self) -> List[Dict[str, Any]]:
        """
        Get distribution of image formats.

        Returns:
            List of format statistics
        """
        results = (
            self.db_session.query(
                ImageUpload.original_format,
                func.count(ImageUpload.id).label("count"),
                func.sum(ImageUpload.original_size_bytes).label("total_size"),
            )
            .group_by(ImageUpload.original_format)
            .order_by(desc("count"))
            .all()
        )

        return [
            {
                "format": row.original_format,
                "count": row.count,
                "total_size_bytes": row.total_size or 0,
            }
            for row in results
        ]

    async def find_images_needing_optimization(
        self,
        limit: int = 100,
    ) -> List[ImageUpload]:
        """
        Find images that need optimization.

        Args:
            limit: Maximum results

        Returns:
            List of images needing optimization
        """
        return (
            self.db_session.query(ImageUpload)
            .filter(
                ImageUpload.auto_optimize == True,
                ImageUpload.optimization_completed == False,
            )
            .order_by(desc(ImageUpload.original_size_bytes))
            .limit(limit)
            .all()
        )

    async def find_images_needing_variants(
        self,
        limit: int = 100,
    ) -> List[ImageUpload]:
        """
        Find images that need variant generation.

        Args:
            limit: Maximum results

        Returns:
            List of images needing variants
        """
        return (
            self.db_session.query(ImageUpload)
            .filter(
                ImageUpload.generate_variants == True,
                ImageUpload.variants_generated == False,
            )
            .order_by(asc(ImageUpload.created_at))
            .limit(limit)
            .all()
        )