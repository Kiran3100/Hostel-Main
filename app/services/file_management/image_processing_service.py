"""
Image Processing Service

Handles:
- Image-specific upload initialization
- Variant generation (thumbnails, different sizes)
- Image optimization and compression
- Metadata extraction (EXIF, dimensions, etc.)
- Format conversion
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.image_upload_repository import ImageUploadRepository
from app.models.file_management.image_upload import ImageUpload as ImageUploadModel
from app.schemas.file.image_upload import (
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageProcessingResult,
    ImageProcessingOptions,
    ImageVariant,
    ImageMetadata,
)

logger = logging.getLogger(__name__)


class ImageProcessingService(BaseService[ImageUploadModel, ImageUploadRepository]):
    """
    Comprehensive image processing and optimization.
    
    Features:
    - Automatic variant generation (thumbnails, previews)
    - Format optimization and conversion
    - EXIF metadata extraction and stripping
    - Image validation and sanitization
    - Retry mechanism for failed processing
    """

    # Default variant configurations
    DEFAULT_VARIANTS = {
        "thumbnail": {"width": 150, "height": 150, "quality": 85},
        "small": {"width": 320, "height": 320, "quality": 90},
        "medium": {"width": 640, "height": 640, "quality": 90},
        "large": {"width": 1024, "height": 1024, "quality": 92},
    }

    def __init__(
        self,
        repository: ImageUploadRepository,
        db_session: Session,
        auto_process: bool = True
    ):
        """
        Initialize the image processing service.
        
        Args:
            repository: Image upload repository instance
            db_session: SQLAlchemy database session
            auto_process: Whether to automatically process images after upload
        """
        super().__init__(repository, db_session)
        self.auto_process = auto_process
        self._max_image_dimension = 10000  # 10000px max width/height
        self._max_retry_attempts = 3
        logger.info(
            f"ImageProcessingService initialized, auto_process: {auto_process}"
        )

    def init_image_upload(
        self,
        request: ImageUploadInitRequest,
    ) -> ServiceResult[ImageUploadInitResponse]:
        """
        Initialize an image-specific upload with validation.
        
        Args:
            request: Image upload initialization request
            
        Returns:
            ServiceResult containing upload initialization response
        """
        try:
            logger.info(
                f"Initializing image upload: {request.filename}, "
                f"size: {request.size_bytes}, type: {request.content_type}"
            )

            # Validate image-specific constraints
            validation_result = self._validate_image_request(request)
            if not validation_result.success:
                return validation_result

            # Initialize upload
            response = self.repository.init_image_upload(request)
            self.db.commit()

            logger.info(
                f"Image upload initialized successfully with ID: {response.file_id}"
            )

            return ServiceResult.success(
                response,
                message="Image upload initialized successfully"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to initialize image upload: {str(e)}", exc_info=True)
            return self._handle_exception(e, "init image upload")

    def _validate_image_request(
        self,
        request: ImageUploadInitRequest
    ) -> ServiceResult[ImageUploadInitResponse]:
        """
        Validate image-specific upload request.
        
        Args:
            request: Image upload request
            
        Returns:
            ServiceResult indicating validation status
        """
        # Validate content type is image
        if not request.content_type.startswith('image/'):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid image content type: {request.content_type}",
                    severity=ErrorSeverity.WARNING,
                )
            )

        # Validate dimensions if provided
        if hasattr(request, 'width') and hasattr(request, 'height'):
            if request.width > self._max_image_dimension or request.height > self._max_image_dimension:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Image dimensions exceed maximum {self._max_image_dimension}px",
                        severity=ErrorSeverity.WARNING,
                    )
                )

        return ServiceResult.success(None)

    def process_image(
        self,
        file_id: UUID,
        options: Optional[ImageProcessingOptions] = None,
    ) -> ServiceResult[ImageProcessingResult]:
        """
        Process an uploaded image (variants, optimization, metadata).
        
        Args:
            file_id: Unique identifier of the image
            options: Optional processing configuration
            
        Returns:
            ServiceResult containing processing results
        """
        try:
            logger.info(f"Processing image with ID: {file_id}")

            # Use default options if none provided
            if options is None:
                options = ImageProcessingOptions(
                    generate_variants=True,
                    optimize=True,
                    extract_metadata=True,
                    strip_exif=False,
                    variants=list(self.DEFAULT_VARIANTS.keys())
                )

            # Validate options
            validation_result = self._validate_processing_options(options)
            if not validation_result.success:
                return validation_result

            # Process the image
            result = self.repository.process_image(file_id, options=options)
            self.db.commit()

            if result.status == "completed":
                logger.info(
                    f"Image processing completed successfully for {file_id}, "
                    f"variants: {len(result.variants) if result.variants else 0}"
                )
                return ServiceResult.success(
                    result,
                    message="Image processed successfully",
                    metadata={
                        "variants_generated": len(result.variants) if result.variants else 0
                    }
                )
            elif result.status == "failed":
                logger.error(
                    f"Image processing failed for {file_id}: {result.error_message}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.PROCESSING_ERROR,
                        message=result.error_message or "Image processing failed",
                        severity=ErrorSeverity.ERROR,
                        details={"result": result}
                    )
                )
            else:
                logger.warning(f"Image processing status: {result.status}")
                return ServiceResult.success(result, message=f"Processing status: {result.status}")

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Image processing error for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "process image", file_id)

    def _validate_processing_options(
        self,
        options: ImageProcessingOptions
    ) -> ServiceResult[bool]:
        """
        Validate image processing options.
        
        Args:
            options: Processing options to validate
            
        Returns:
            ServiceResult indicating validation status
        """
        if options.variants:
            for variant_name in options.variants:
                if variant_name not in self.DEFAULT_VARIANTS:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid variant name: {variant_name}",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

        return ServiceResult.success(True)

    def retry_failed(
        self,
        file_id: UUID,
        max_attempts: Optional[int] = None,
    ) -> ServiceResult[ImageProcessingResult]:
        """
        Retry failed image processing.
        
        Args:
            file_id: Unique identifier of the image
            max_attempts: Maximum retry attempts (overrides default)
            
        Returns:
            ServiceResult containing retry results
        """
        try:
            max_attempts = max_attempts or self._max_retry_attempts

            logger.info(
                f"Retrying image processing for file {file_id}, "
                f"max attempts: {max_attempts}"
            )

            result = self.repository.retry_processing(file_id, max_attempts=max_attempts)
            self.db.commit()

            if result.status == "completed":
                logger.info(f"Image processing retry successful for {file_id}")
                return ServiceResult.success(
                    result,
                    message="Image processing retry successful"
                )
            elif result.status == "failed":
                logger.error(
                    f"Image processing retry failed for {file_id}: {result.error_message}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.PROCESSING_ERROR,
                        message=result.error_message or "Retry failed",
                        severity=ErrorSeverity.ERROR,
                        details={"result": result}
                    )
                )
            else:
                logger.info(f"Retry status for {file_id}: {result.status}")
                return ServiceResult.success(result, message=f"Retry status: {result.status}")

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Image processing retry error for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "retry image processing", file_id)

    def get_metadata(
        self,
        file_id: UUID,
        include_exif: bool = True,
    ) -> ServiceResult[ImageMetadata]:
        """
        Retrieve image metadata including EXIF data.
        
        Args:
            file_id: Unique identifier of the image
            include_exif: Whether to include EXIF data
            
        Returns:
            ServiceResult containing image metadata
        """
        try:
            logger.debug(f"Retrieving metadata for image {file_id}")

            metadata = self.repository.get_image_metadata(file_id, include_exif=include_exif)

            if not metadata:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Metadata not found for image {file_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(
                metadata,
                metadata={"include_exif": include_exif}
            )

        except Exception as e:
            logger.error(
                f"Failed to get metadata for image {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get image metadata", file_id)

    def get_variant(
        self,
        file_id: UUID,
        variant_name: str,
    ) -> ServiceResult[ImageVariant]:
        """
        Retrieve a specific image variant.
        
        Args:
            file_id: Unique identifier of the original image
            variant_name: Name of the variant (thumbnail, small, medium, large)
            
        Returns:
            ServiceResult containing variant information
        """
        try:
            logger.debug(f"Retrieving variant '{variant_name}' for image {file_id}")

            if variant_name not in self.DEFAULT_VARIANTS:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid variant name: {variant_name}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            variant = self.repository.get_variant(file_id, variant_name)

            if not variant:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Variant '{variant_name}' not found for image {file_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(variant)

        except Exception as e:
            logger.error(
                f"Failed to get variant for image {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get image variant", file_id)

    def list_variants(
        self,
        file_id: UUID,
    ) -> ServiceResult[List[ImageVariant]]:
        """
        List all variants for an image.
        
        Args:
            file_id: Unique identifier of the image
            
        Returns:
            ServiceResult containing list of variants
        """
        try:
            logger.debug(f"Listing variants for image {file_id}")

            variants = self.repository.list_variants(file_id)

            return ServiceResult.success(
                variants,
                metadata={"count": len(variants)}
            )

        except Exception as e:
            logger.error(
                f"Failed to list variants for image {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list image variants", file_id)

    def optimize_image(
        self,
        file_id: UUID,
        quality: int = 85,
        format: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Optimize an existing image for file size reduction.
        
        Args:
            file_id: Unique identifier of the image
            quality: Optimization quality (0-100)
            format: Optional target format (jpg, png, webp)
            
        Returns:
            ServiceResult containing optimization results
        """
        try:
            if quality < 1 or quality > 100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Quality must be between 1 and 100",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(
                f"Optimizing image {file_id}, quality: {quality}, format: {format}"
            )

            result = self.repository.optimize_image(file_id, quality=quality, format=format)
            self.db.commit()

            logger.info(
                f"Image optimization completed for {file_id}, "
                f"original size: {result.get('original_size')}, "
                f"optimized size: {result.get('optimized_size')}"
            )

            return ServiceResult.success(
                result,
                message="Image optimized successfully"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Image optimization error for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "optimize image", file_id)

    def convert_format(
        self,
        file_id: UUID,
        target_format: str,
        quality: int = 90,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Convert image to a different format.
        
        Args:
            file_id: Unique identifier of the image
            target_format: Target format (jpg, png, webp, etc.)
            quality: Conversion quality
            
        Returns:
            ServiceResult containing conversion results
        """
        valid_formats = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'}

        try:
            target_format = target_format.lower()

            if target_format not in valid_formats:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid format. Must be one of: {', '.join(valid_formats)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(f"Converting image {file_id} to format: {target_format}")

            result = self.repository.convert_format(
                file_id,
                target_format=target_format,
                quality=quality
            )
            self.db.commit()

            logger.info(f"Image format conversion completed for {file_id}")

            return ServiceResult.success(
                result,
                message=f"Image converted to {target_format} successfully"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Format conversion error for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "convert image format", file_id)

    @property
    def max_image_dimension(self) -> int:
        """Get the maximum allowed image dimension."""
        return self._max_image_dimension

    @max_image_dimension.setter
    def max_image_dimension(self, dimension: int) -> None:
        """Set the maximum allowed image dimension."""
        if dimension < 100:
            raise ValueError("Maximum dimension must be at least 100px")
        self._max_image_dimension = dimension
        logger.info(f"Max image dimension set to: {dimension}px")

    @property
    def max_retry_attempts(self) -> int:
        """Get the maximum retry attempts for failed processing."""
        return self._max_retry_attempts

    @max_retry_attempts.setter
    def max_retry_attempts(self, attempts: int) -> None:
        """Set the maximum retry attempts."""
        if attempts < 1:
            raise ValueError("Maximum retry attempts must be at least 1")
        self._max_retry_attempts = attempts
        logger.info(f"Max retry attempts set to: {attempts}")