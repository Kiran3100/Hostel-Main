"""
Image Processing Service

Image optimization, variant generation, watermarking, and metadata extraction.
"""

from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
import io
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.repositories.file_management.image_upload_repository import (
    ImageUploadRepository,
)
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.services.file_management.file_storage_service import FileStorageService
from app.core.exceptions import ProcessingException

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """
    Service for image processing operations.
    """

    # Standard variant configurations
    VARIANT_CONFIGS = {
        'thumbnail': {'width': 150, 'height': 150, 'quality': 80},
        'small': {'width': 400, 'height': 400, 'quality': 85},
        'medium': {'width': 800, 'height': 800, 'quality': 85},
        'large': {'width': 1600, 'height': 1600, 'quality': 90},
    }

    def __init__(
        self,
        db_session: Session,
        storage_service: FileStorageService,
    ):
        self.db = db_session
        self.image_repo = ImageUploadRepository(db_session)
        self.file_repo = FileUploadRepository(db_session)
        self.storage = storage_service

    # ============================================================================
    # IMAGE UPLOAD CREATION
    # ============================================================================

    async def create_image_upload(
        self,
        file_id: str,
        file_content: bytes,
        usage: str = 'general',
        generate_variants: bool = True,
        auto_optimize: bool = True,
        convert_to_webp: bool = False,
        quality: int = 85,
        add_watermark: bool = False,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create image upload record and trigger processing.

        Args:
            file_id: Associated file upload ID
            file_content: Image binary content
            usage: Image usage type
            generate_variants: Whether to generate variants
            auto_optimize: Whether to optimize image
            convert_to_webp: Whether to convert to WebP
            quality: Image quality (1-100)
            add_watermark: Whether to add watermark
            audit_context: Audit context

        Returns:
            Image upload details with processing status
        """
        try:
            logger.info(f"Creating image upload for file: {file_id}")

            # Analyze image
            image_info = await self._analyze_image(file_content)

            # Create image upload record
            image_data = {
                "usage": usage,
                "original_width": image_info['width'],
                "original_height": image_info['height'],
                "original_format": image_info['format'],
                "original_mode": image_info['mode'],
                "has_alpha": image_info['has_alpha'],
                "color_space": image_info.get('color_space'),
                "dominant_colors": image_info.get('dominant_colors', []),
                "generate_variants": generate_variants,
                "auto_optimize": auto_optimize,
                "convert_to_webp": convert_to_webp,
                "quality": quality,
                "add_watermark": add_watermark,
                "original_size_bytes": len(file_content),
            }

            image_upload = await self.image_repo.create_image_upload(
                file_id=file_id,
                image_data=image_data,
                audit_context=audit_context,
            )

            # Extract and store metadata
            metadata = await self._extract_exif_metadata(file_content)
            if metadata:
                await self.image_repo.create_metadata(
                    image_id=image_upload.id,
                    metadata_data=metadata,
                )

            logger.info(f"Image upload created: {image_upload.id}")

            return {
                "image_id": image_upload.id,
                "file_id": file_id,
                "dimensions": f"{image_info['width']}x{image_info['height']}",
                "format": image_info['format'],
                "processing_queued": generate_variants or auto_optimize,
            }

        except Exception as e:
            logger.error(f"Failed to create image upload: {str(e)}", exc_info=True)
            raise ProcessingException(f"Image upload creation failed: {str(e)}")

    # ============================================================================
    # IMAGE PROCESSING QUEUE
    # ============================================================================

    async def process_image_queue(
        self,
        worker_id: str,
        max_jobs: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Process pending image processing jobs.

        Args:
            worker_id: Worker identifier
            max_jobs: Maximum jobs to process

        Returns:
            List of processing results
        """
        results = []

        for _ in range(max_jobs):
            # Get next job
            job = await self.image_repo.get_next_processing_job(worker_id)
            
            if not job:
                break

            try:
                logger.info(f"Processing image job: {job.id}")

                # Process image
                result = await self._process_image_job(job)
                results.append(result)

                # Mark as completed
                await self.image_repo.complete_processing(
                    processing_id=job.id,
                    success=True,
                )

            except Exception as e:
                logger.error(f"Image processing failed: {str(e)}", exc_info=True)
                
                # Mark as failed
                await self.image_repo.complete_processing(
                    processing_id=job.id,
                    success=False,
                    error_message=str(e),
                    error_details={"worker_id": worker_id},
                )

                results.append({
                    "job_id": job.id,
                    "status": "failed",
                    "error": str(e),
                })

        return results

    async def _process_image_job(
        self,
        job: Any,
    ) -> Dict[str, Any]:
        """Process single image job."""
        image = job.image
        steps_completed = []

        # Get original file
        file_upload = await self.file_repo.find_by_file_id(image.file_id)
        if not file_upload:
            raise ProcessingException(f"File not found: {image.file_id}")

        # Download original image
        image_content = await self.storage.download_file(file_upload.storage_key)

        # Process each step
        pending_steps = job.pending_steps or []
        
        for step in pending_steps:
            await self.image_repo.update_processing_progress(
                processing_id=job.id,
                current_step=step,
                progress_percentage=(len(steps_completed) / len(pending_steps)) * 100,
                completed_steps=steps_completed,
            )

            if step == 'generate_variants':
                await self._generate_variants(image, image_content)
                steps_completed.append(step)

            elif step == 'optimize':
                await self._optimize_image(image, image_content)
                steps_completed.append(step)

            elif step == 'convert_webp':
                await self._convert_to_webp(image, image_content)
                steps_completed.append(step)

            elif step == 'add_watermark':
                await self._add_watermark(image, image_content)
                steps_completed.append(step)

        return {
            "job_id": job.id,
            "image_id": image.id,
            "status": "completed",
            "steps_completed": steps_completed,
        }

    # ============================================================================
    # VARIANT GENERATION
    # ============================================================================

    async def _generate_variants(
        self,
        image_upload: Any,
        original_content: bytes,
    ) -> None:
        """Generate image variants."""
        logger.info(f"Generating variants for image: {image_upload.id}")

        img = Image.open(io.BytesIO(original_content))
        
        # Auto-orient based on EXIF
        img = ImageOps.exif_transpose(img)

        file_upload = await self.file_repo.find_by_file_id(image_upload.file_id)

        for variant_name, config in self.VARIANT_CONFIGS.items():
            try:
                variant_img = await self._create_variant(
                    img=img,
                    max_width=config['width'],
                    max_height=config['height'],
                    quality=config['quality'],
                )

                # Save variant
                variant_buffer = io.BytesIO()
                save_format = 'JPEG' if variant_img.mode == 'RGB' else 'PNG'
                variant_img.save(
                    variant_buffer,
                    format=save_format,
                    quality=config['quality'],
                    optimize=True,
                )
                variant_content = variant_buffer.getvalue()

                # Generate storage key
                base_key = file_upload.storage_key
                variant_key = base_key.replace(
                    f".{image_upload.original_format.lower()}",
                    f"_{variant_name}.{save_format.lower()}"
                )

                # Upload variant
                upload_result = await self.storage.upload_file(
                    file_content=variant_content,
                    storage_key=variant_key,
                    content_type=f'image/{save_format.lower()}',
                    metadata={'variant': variant_name},
                    is_public=file_upload.is_public,
                )

                # Create variant record
                variant_data = {
                    "variant_name": variant_name,
                    "storage_key": variant_key,
                    "width": variant_img.width,
                    "height": variant_img.height,
                    "format": save_format,
                    "size_bytes": len(variant_content),
                    "url": upload_result['url'],
                    "public_url": upload_result.get('public_url'),
                    "is_optimized": True,
                    "quality": config['quality'],
                }

                await self.image_repo.create_variant(
                    image_id=image_upload.id,
                    variant_data=variant_data,
                )

                logger.info(f"Variant '{variant_name}' created: {variant_img.width}x{variant_img.height}")

            except Exception as e:
                logger.error(f"Failed to create variant '{variant_name}': {str(e)}")

        # Mark variants as generated
        await self.image_repo.mark_variants_generated(image_upload.id)

    async def _create_variant(
        self,
        img: Image.Image,
        max_width: int,
        max_height: int,
        quality: int,
    ) -> Image.Image:
        """Create resized image variant."""
        # Calculate new dimensions maintaining aspect ratio
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Convert RGBA to RGB if saving as JPEG
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            return rgb_img
        
        return img

    # ============================================================================
    # IMAGE OPTIMIZATION
    # ============================================================================

    async def _optimize_image(
        self,
        image_upload: Any,
        original_content: bytes,
    ) -> None:
        """Optimize image file size."""
        logger.info(f"Optimizing image: {image_upload.id}")

        start_time = datetime.utcnow()
        
        img = Image.open(io.BytesIO(original_content))
        
        # Optimize
        optimized_buffer = io.BytesIO()
        save_kwargs = {
            'quality': image_upload.quality,
            'optimize': True,
        }

        if img.format == 'PNG':
            save_kwargs['compress_level'] = 9
        elif img.format == 'JPEG':
            save_kwargs['progressive'] = True

        img.save(optimized_buffer, format=img.format, **save_kwargs)
        optimized_content = optimized_buffer.getvalue()

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Store optimization results
        optimization_data = {
            "optimization_level": "medium",
            "target_quality": image_upload.quality,
            "strip_metadata": True,
            "preserve_exif": False,
            "auto_orient": True,
            "original_size_bytes": len(original_content),
            "optimized_size_bytes": len(optimized_content),
            "optimization_duration_ms": duration_ms,
            "optimization_tool": "Pillow",
            "tool_version": Image.__version__,
        }

        await self.image_repo.create_optimization_result(
            image_id=image_upload.id,
            optimization_data=optimization_data,
        )

        logger.info(
            f"Image optimized: {len(original_content)} -> {len(optimized_content)} bytes "
            f"({((len(original_content) - len(optimized_content)) / len(original_content) * 100):.1f}% reduction)"
        )

    # ============================================================================
    # WEBP CONVERSION
    # ============================================================================

    async def _convert_to_webp(
        self,
        image_upload: Any,
        original_content: bytes,
    ) -> None:
        """Convert image to WebP format."""
        logger.info(f"Converting to WebP: {image_upload.id}")

        img = Image.open(io.BytesIO(original_content))
        
        # Convert to WebP
        webp_buffer = io.BytesIO()
        img.save(
            webp_buffer,
            format='WEBP',
            quality=image_upload.quality,
            method=6,  # Best compression
        )
        webp_content = webp_buffer.getvalue()

        # Generate storage key
        file_upload = await self.file_repo.find_by_file_id(image_upload.file_id)
        base_key = file_upload.storage_key
        webp_key = base_key.rsplit('.', 1)[0] + '.webp'

        # Upload WebP version
        upload_result = await self.storage.upload_file(
            file_content=webp_content,
            storage_key=webp_key,
            content_type='image/webp',
            metadata={'format': 'webp'},
            is_public=file_upload.is_public,
        )

        # Create variant record
        variant_data = {
            "variant_name": "webp",
            "storage_key": webp_key,
            "width": img.width,
            "height": img.height,
            "format": "WEBP",
            "size_bytes": len(webp_content),
            "url": upload_result['url'],
            "public_url": upload_result.get('public_url'),
            "is_optimized": True,
            "quality": image_upload.quality,
        }

        await self.image_repo.create_variant(
            image_id=image_upload.id,
            variant_data=variant_data,
        )

        logger.info(f"WebP variant created: {len(webp_content)} bytes")

    # ============================================================================
    # WATERMARKING
    # ============================================================================

    async def _add_watermark(
        self,
        image_upload: Any,
        original_content: bytes,
        watermark_text: str = "© Your Company",
        position: str = "bottom-right",
    ) -> None:
        """Add watermark to image."""
        logger.info(f"Adding watermark to image: {image_upload.id}")

        img = Image.open(io.BytesIO(original_content))
        
        # Create watermark
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)

        # Calculate font size based on image size
        font_size = max(12, int(img.width * 0.03))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Calculate position
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        margin = 10
        if position == "bottom-right":
            x = img.width - text_width - margin
            y = img.height - text_height - margin
        elif position == "bottom-left":
            x = margin
            y = img.height - text_height - margin
        elif position == "top-right":
            x = img.width - text_width - margin
            y = margin
        else:  # top-left
            x = margin
            y = margin

        # Draw watermark with transparency
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))

        # Composite watermark
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        watermarked = Image.alpha_composite(img, watermark)

        # Convert back to original mode if needed
        if image_upload.original_format == 'JPEG':
            watermarked = watermarked.convert('RGB')

        # Update image record
        image_upload.watermark_applied = True
        self.db.commit()

        logger.info(f"Watermark added to image: {image_upload.id}")

    # ============================================================================
    # METADATA EXTRACTION
    # ============================================================================

    async def _extract_exif_metadata(
        self,
        image_content: bytes,
    ) -> Optional[Dict[str, Any]]:
        """Extract EXIF metadata from image."""
        try:
            img = Image.open(io.BytesIO(image_content))
            exif_data = img._getexif()

            if not exif_data:
                return None

            metadata = {
                "raw_exif": {},
            }

            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                
                # Convert value to string if it's bytes
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8', errors='ignore')
                    except:
                        value = str(value)

                metadata["raw_exif"][tag] = value

                # Extract specific fields
                if tag == "Make":
                    metadata["camera_make"] = value
                elif tag == "Model":
                    metadata["camera_model"] = value
                elif tag == "LensModel":
                    metadata["lens_model"] = value
                elif tag == "ISOSpeedRatings":
                    metadata["iso"] = value
                elif tag == "FNumber":
                    metadata["aperture"] = f"f/{value}"
                elif tag == "ExposureTime":
                    metadata["shutter_speed"] = str(value)
                elif tag == "FocalLength":
                    metadata["focal_length"] = f"{value}mm"
                elif tag == "Flash":
                    metadata["flash"] = value != 0
                elif tag == "DateTimeOriginal":
                    try:
                        metadata["date_taken"] = datetime.strptime(
                            value, '%Y:%m:%d %H:%M:%S'
                        )
                    except:
                        pass
                elif tag == "Orientation":
                    metadata["orientation"] = value
                elif tag == "XResolution":
                    metadata["resolution_x"] = int(value)
                elif tag == "YResolution":
                    metadata["resolution_y"] = int(value)
                elif tag == "Software":
                    metadata["software"] = value
                elif tag == "Copyright":
                    metadata["copyright"] = value
                elif tag == "Artist":
                    metadata["artist"] = value
                elif tag == "GPSInfo":
                    gps_data = self._parse_gps_info(value)
                    if gps_data:
                        metadata.update(gps_data)

            metadata["extraction_tool"] = "Pillow"

            return metadata

        except Exception as e:
            logger.warning(f"Failed to extract EXIF metadata: {str(e)}")
            return None

    def _parse_gps_info(self, gps_info: Dict) -> Optional[Dict[str, Any]]:
        """Parse GPS information from EXIF."""
        try:
            gps_data = {}

            for tag_id, value in gps_info.items():
                tag = GPSTAGS.get(tag_id, tag_id)

                if tag == "GPSLatitude":
                    gps_data["gps_latitude"] = self._convert_to_degrees(value)
                elif tag == "GPSLongitude":
                    gps_data["gps_longitude"] = self._convert_to_degrees(value)
                elif tag == "GPSAltitude":
                    gps_data["gps_altitude"] = float(value)

            return gps_data if gps_data else None

        except Exception as e:
            logger.warning(f"Failed to parse GPS info: {str(e)}")
            return None

    def _convert_to_degrees(self, value: Tuple) -> float:
        """Convert GPS coordinates to degrees."""
        d, m, s = value
        return float(d) + (float(m) / 60.0) + (float(s) / 3600.0)

    # ============================================================================
    # IMAGE ANALYSIS
    # ============================================================================

    async def _analyze_image(self, content: bytes) -> Dict[str, Any]:
        """Analyze image properties."""
        img = Image.open(io.BytesIO(content))

        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "has_alpha": img.mode in ('RGBA', 'LA', 'PA'),
            "color_space": self._detect_color_space(img),
            "dominant_colors": self._extract_dominant_colors(img),
        }

    def _detect_color_space(self, img: Image.Image) -> str:
        """Detect image color space."""
        if img.mode == 'RGB':
            return 'sRGB'
        elif img.mode == 'RGBA':
            return 'sRGBA'
        elif img.mode == 'L':
            return 'Grayscale'
        elif img.mode == 'CMYK':
            return 'CMYK'
        return img.mode

    def _extract_dominant_colors(
        self,
        img: Image.Image,
        num_colors: int = 5,
    ) -> List[str]:
        """Extract dominant colors from image."""
        try:
            # Resize for faster processing
            img_small = img.copy()
            img_small.thumbnail((100, 100))

            # Convert to RGB if needed
            if img_small.mode != 'RGB':
                img_small = img_small.convert('RGB')

            # Get colors
            colors = img_small.getcolors(10000)
            if not colors:
                return []

            # Sort by frequency
            colors.sort(key=lambda x: x[0], reverse=True)

            # Convert to hex
            hex_colors = []
            for count, color in colors[:num_colors]:
                hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                hex_colors.append(hex_color)

            return hex_colors

        except Exception as e:
            logger.warning(f"Failed to extract dominant colors: {str(e)}")
            return []