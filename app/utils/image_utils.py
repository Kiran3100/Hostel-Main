"""
Image processing utilities for hostel management system
"""

import os
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont, ExifTags
from typing import Tuple, Optional, List, Dict, Any, Union
import io
import base64
from pathlib import Path
import hashlib

class ImageProcessor:
    """Main image processing utilities"""
    
    # Supported image formats
    SUPPORTED_FORMATS = ['JPEG', 'PNG', 'GIF', 'BMP', 'WEBP']
    
    @staticmethod
    def open_image(image_path: str) -> Image.Image:
        """Open and validate image file"""
        try:
            image = Image.open(image_path)
            # Verify it's a valid image
            image.verify()
            # Reopen for processing (verify closes the file)
            return Image.open(image_path)
        except Exception as e:
            raise ValueError(f"Invalid image file: {e}")
    
    @staticmethod
    def save_image(image: Image.Image, output_path: str, 
                   format: str = 'JPEG', quality: int = 95, 
                   optimize: bool = True) -> str:
        """Save image with specified format and quality"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert to RGB if saving as JPEG
        if format.upper() == 'JPEG' and image.mode in ('RGBA', 'P', 'LA'):
            # Create white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        save_kwargs = {'format': format, 'optimize': optimize}
        if format.upper() == 'JPEG':
            save_kwargs['quality'] = quality
        elif format.upper() == 'PNG':
            save_kwargs['compress_level'] = 9 if optimize else 6
        
        image.save(output_path, **save_kwargs)
        return output_path
    
    @staticmethod
    def resize_image(image: Image.Image, size: Tuple[int, int], 
                    maintain_aspect: bool = True, 
                    resample: int = Image.Resampling.LANCZOS) -> Image.Image:
        """Resize image with optional aspect ratio maintenance"""
        if maintain_aspect:
            image.thumbnail(size, resample)
            return image
        else:
            return image.resize(size, resample)
    
    @staticmethod
    def crop_image(image: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
        """Crop image to specified box (left, top, right, bottom)"""
        return image.crop(box)
    
    @staticmethod
    def crop_to_square(image: Image.Image) -> Image.Image:
        """Crop image to square using the center"""
        width, height = image.size
        size = min(width, height)
        
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        
        return image.crop((left, top, right, bottom))
    
    @staticmethod
    def rotate_image(image: Image.Image, angle: float, 
                    expand: bool = True, 
                    fillcolor: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
        """Rotate image by specified angle"""
        return image.rotate(angle, expand=expand, fillcolor=fillcolor)
    
    @staticmethod
    def flip_image(image: Image.Image, direction: str = 'horizontal') -> Image.Image:
        """Flip image horizontally or vertically"""
        if direction.lower() == 'horizontal':
            return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif direction.lower() == 'vertical':
            return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        else:
            raise ValueError("Direction must be 'horizontal' or 'vertical'")
    
    @staticmethod
    def apply_filter(image: Image.Image, filter_type: str) -> Image.Image:
        """Apply various filters to image"""
        filters = {
            'blur': ImageFilter.BLUR,
            'detail': ImageFilter.DETAIL,
            'edge_enhance': ImageFilter.EDGE_ENHANCE,
            'edge_enhance_more': ImageFilter.EDGE_ENHANCE_MORE,
            'emboss': ImageFilter.EMBOSS,
            'find_edges': ImageFilter.FIND_EDGES,
            'sharpen': ImageFilter.SHARPEN,
            'smooth': ImageFilter.SMOOTH,
            'smooth_more': ImageFilter.SMOOTH_MORE
        }
        
        if filter_type.lower() not in filters:
            raise ValueError(f"Unsupported filter: {filter_type}")
        
        return image.filter(filters[filter_type.lower()])
    
    @staticmethod
    def adjust_brightness(image: Image.Image, factor: float) -> Image.Image:
        """Adjust image brightness (1.0 = original, <1.0 = darker, >1.0 = brighter)"""
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)
    
    @staticmethod
    def adjust_contrast(image: Image.Image, factor: float) -> Image.Image:
        """Adjust image contrast (1.0 = original)"""
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    @staticmethod
    def adjust_saturation(image: Image.Image, factor: float) -> Image.Image:
        """Adjust color saturation (1.0 = original, 0.0 = grayscale)"""
        enhancer = ImageEnhance.Color(image)
        return enhancer.enhance(factor)
    
    @staticmethod
    def convert_to_grayscale(image: Image.Image) -> Image.Image:
        """Convert image to grayscale"""
        return image.convert('L')
    
    @staticmethod
    def get_image_info(image_path: str) -> Dict[str, Any]:
        """Get comprehensive image information"""
        image = ImageProcessor.open_image(image_path)
        
        info = {
            'filename': os.path.basename(image_path),
            'format': image.format,
            'mode': image.mode,
            'size': image.size,
            'width': image.width,
            'height': image.height,
            'has_transparency': image.mode in ('RGBA', 'LA') or 'transparency' in image.info
        }
        
        # Add EXIF data if available
        if hasattr(image, '_getexif') and image._getexif():
            exif = image._getexif()
            if exif:
                info['exif'] = {}
                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    info['exif'][tag] = value
        
        return info

class ThumbnailGenerator:
    """Thumbnail generation utilities"""
    
    DEFAULT_SIZES = {
        'small': (150, 150),
        'medium': (300, 300),
        'large': (600, 600)
    }
    
    @classmethod
    def generate_thumbnail(cls, image_path: str, size: Tuple[int, int], 
                          output_path: str = None, 
                          maintain_aspect: bool = True,
                          quality: int = 85) -> str:
        """Generate single thumbnail"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_thumb_{size[0]}x{size[1]}{path.suffix}")
        
        # Resize image
        thumbnail = ImageProcessor.resize_image(image, size, maintain_aspect)
        
        # Save thumbnail
        ImageProcessor.save_image(thumbnail, output_path, quality=quality)
        
        return output_path
    
    @classmethod
    def generate_multiple_thumbnails(cls, image_path: str, 
                                   sizes: Dict[str, Tuple[int, int]] = None,
                                   output_dir: str = None) -> Dict[str, str]:
        """Generate multiple thumbnail sizes"""
        if sizes is None:
            sizes = cls.DEFAULT_SIZES
        
        if output_dir is None:
            output_dir = os.path.dirname(image_path)
        
        thumbnails = {}
        path = Path(image_path)
        
        for size_name, size_dims in sizes.items():
            thumbnail_name = f"{path.stem}_thumb_{size_name}{path.suffix}"
            thumbnail_path = os.path.join(output_dir, thumbnail_name)
            
            thumbnails[size_name] = cls.generate_thumbnail(
                image_path, size_dims, thumbnail_path
            )
        
        return thumbnails
    
    @staticmethod
    def generate_smart_crop_thumbnail(image_path: str, size: Tuple[int, int], 
                                    output_path: str = None) -> str:
        """Generate thumbnail with smart cropping (center-focused)"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_smart_thumb_{size[0]}x{size[1]}{path.suffix}")
        
        # Calculate crop dimensions for center crop
        img_width, img_height = image.size
        target_width, target_height = size
        
        # Calculate aspect ratios
        img_ratio = img_width / img_height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # Image is wider than target ratio
            new_width = int(img_height * target_ratio)
            left = (img_width - new_width) // 2
            crop_box = (left, 0, left + new_width, img_height)
        else:
            # Image is taller than target ratio
            new_height = int(img_width / target_ratio)
            top = (img_height - new_height) // 2
            crop_box = (0, top, img_width, top + new_height)
        
        # Crop and resize
        cropped = image.crop(crop_box)
        thumbnail = cropped.resize(size, Image.Resampling.LANCZOS)
        
        # Save thumbnail
        ImageProcessor.save_image(thumbnail, output_path)
        
        return output_path

class ImageOptimizer:
    """Image optimization utilities"""
    
    @staticmethod
    def optimize_for_web(image_path: str, output_path: str = None,
                        max_width: int = 1920, max_height: int = 1080,
                        quality: int = 85, format: str = 'JPEG') -> str:
        """Optimize image for web usage"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_optimized{path.suffix}")
        
        # Resize if too large
        if image.width > max_width or image.height > max_height:
            image = ImageProcessor.resize_image(image, (max_width, max_height))
        
        # Save with optimization
        ImageProcessor.save_image(image, output_path, format, quality, optimize=True)
        
        return output_path
    
    @staticmethod
    def compress_image(image_path: str, output_path: str = None,
                      target_size_kb: int = 500) -> str:
        """Compress image to target file size"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_compressed{path.suffix}")
        
        # Start with high quality and reduce until target size is met
        quality = 95
        min_quality = 10
        
        while quality >= min_quality:
            # Save to bytes buffer to check size
            buffer = io.BytesIO()
            ImageProcessor.save_image(image, buffer, 'JPEG', quality)
            
            size_kb = len(buffer.getvalue()) / 1024
            
            if size_kb <= target_size_kb:
                # Save to actual file
                ImageProcessor.save_image(image, output_path, 'JPEG', quality)
                break
            
            quality -= 5
        else:
            # If we couldn't reach target size, save with minimum quality
            ImageProcessor.save_image(image, output_path, 'JPEG', min_quality)
        
        return output_path
    
    @staticmethod
    def remove_metadata(image_path: str, output_path: str = None) -> str:
        """Remove EXIF and other metadata from image"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            output_path = image_path
        
        # Create new image without metadata
        if image.mode == 'RGBA':
            clean_image = Image.new('RGBA', image.size)
        else:
            clean_image = Image.new('RGB', image.size, (255, 255, 255))
        
        clean_image.paste(image)
        
        # Save without metadata
        clean_image.save(output_path, optimize=True)
        
        return output_path

class ImageValidator:
    """Image validation utilities"""
    
    ALLOWED_FORMATS = ['JPEG', 'PNG', 'GIF', 'BMP', 'WEBP']
    MAX_DIMENSION = 10000  # Max width or height
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    @classmethod
    def validate_image(cls, image_path: str) -> Dict[str, Any]:
        """Comprehensive image validation"""
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                result['valid'] = False
                result['errors'].append('File does not exist')
                return result
            
            # Check file size
            file_size = os.path.getsize(image_path)
            if file_size > cls.MAX_FILE_SIZE:
                result['valid'] = False
                result['errors'].append(f'File too large: {file_size / 1024 / 1024:.1f}MB')
            
            if file_size == 0:
                result['valid'] = False
                result['errors'].append('File is empty')
                return result
            
            # Try to open and validate image
            image = ImageProcessor.open_image(image_path)
            
            # Check format
            if image.format not in cls.ALLOWED_FORMATS:
                result['valid'] = False
                result['errors'].append(f'Unsupported format: {image.format}')
            
            # Check dimensions
            width, height = image.size
            if width > cls.MAX_DIMENSION or height > cls.MAX_DIMENSION:
                result['valid'] = False
                result['errors'].append(f'Image too large: {width}x{height}')
            
            if width < 10 or height < 10:
                result['warnings'].append('Image very small, may not display well')
            
            # Check for corruption
            try:
                image.verify()
            except Exception:
                result['valid'] = False
                result['errors'].append('Image appears to be corrupted')
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f'Failed to process image: {str(e)}')
        
        return result
    
    @staticmethod
    def is_valid_image_dimension(width: int, height: int, 
                                min_width: int = 1, min_height: int = 1,
                                max_width: int = 10000, max_height: int = 10000) -> bool:
        """Validate image dimensions"""
        return (min_width <= width <= max_width and 
                min_height <= height <= max_height)
    
    @staticmethod
    def calculate_image_hash(image_path: str) -> str:
        """Calculate perceptual hash for image comparison"""
        image = ImageProcessor.open_image(image_path)
        
        # Resize to small size and convert to grayscale
        image = image.resize((8, 8), Image.Resampling.LANCZOS)
        image = image.convert('L')
        
        # Calculate average pixel value
        pixels = list(image.getdata())
        avg = sum(pixels) / len(pixels)
        
        # Create hash based on pixels vs average
        hash_bits = []
        for pixel in pixels:
            hash_bits.append('1' if pixel > avg else '0')
        
        # Convert binary to hex
        hash_string = ''.join(hash_bits)
        hash_int = int(hash_string, 2)
        return format(hash_int, '016x')

class WatermarkManager:
    """Image watermarking utilities"""
    
    @staticmethod
    def add_text_watermark(image_path: str, text: str, 
                          output_path: str = None,
                          position: str = 'bottom_right',
                          opacity: int = 128,
                          font_size: int = 36) -> str:
        """Add text watermark to image"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_watermarked{path.suffix}")
        
        # Create transparent overlay
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Calculate text size and position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        positions = {
            'top_left': (10, 10),
            'top_right': (image.width - text_width - 10, 10),
            'bottom_left': (10, image.height - text_height - 10),
            'bottom_right': (image.width - text_width - 10, image.height - text_height - 10),
            'center': ((image.width - text_width) // 2, (image.height - text_height) // 2)
        }
        
        if position not in positions:
            position = 'bottom_right'
        
        x, y = positions[position]
        
        # Draw text with specified opacity
        draw.text((x, y), text, fill=(255, 255, 255, opacity), font=font)
        
        # Composite with original image
        watermarked = Image.alpha_composite(image.convert('RGBA'), overlay)
        
        # Save image
        ImageProcessor.save_image(watermarked.convert('RGB'), output_path)
        
        return output_path
    
    @staticmethod
    def add_image_watermark(image_path: str, watermark_path: str,
                           output_path: str = None,
                           position: str = 'bottom_right',
                           opacity: int = 128,
                           scale: float = 0.2) -> str:
        """Add image watermark"""
        image = ImageProcessor.open_image(image_path)
        watermark = ImageProcessor.open_image(watermark_path)
        
        if output_path is None:
            path = Path(image_path)
            output_path = str(path.parent / f"{path.stem}_watermarked{path.suffix}")
        
        # Scale watermark
        wm_width = int(image.width * scale)
        wm_height = int(watermark.height * (wm_width / watermark.width))
        watermark = watermark.resize((wm_width, wm_height), Image.Resampling.LANCZOS)
        
        # Adjust opacity
        if watermark.mode != 'RGBA':
            watermark = watermark.convert('RGBA')
        
        # Apply opacity
        watermark_with_opacity = watermark.copy()
        alpha = watermark_with_opacity.split()[-1]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity / 255.0)
        watermark_with_opacity.putalpha(alpha)
        
        # Calculate position
        positions = {
            'top_left': (10, 10),
            'top_right': (image.width - wm_width - 10, 10),
            'bottom_left': (10, image.height - wm_height - 10),
            'bottom_right': (image.width - wm_width - 10, image.height - wm_height - 10),
            'center': ((image.width - wm_width) // 2, (image.height - wm_height) // 2)
        }
        
        if position not in positions:
            position = 'bottom_right'
        
        x, y = positions[position]
        
        # Paste watermark
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        image.paste(watermark_with_opacity, (x, y), watermark_with_opacity)
        
        # Save image
        ImageProcessor.save_image(image.convert('RGB'), output_path)
        
        return output_path

class ImageConverter:
    """Image format conversion utilities"""
    
    @staticmethod
    def convert_format(image_path: str, target_format: str, 
                      output_path: str = None, **kwargs) -> str:
        """Convert image to different format"""
        image = ImageProcessor.open_image(image_path)
        
        if output_path is None:
            path = Path(image_path)
            extension = '.jpg' if target_format.upper() == 'JPEG' else f'.{target_format.lower()}'
            output_path = str(path.parent / f"{path.stem}_converted{extension}")
        
        ImageProcessor.save_image(image, output_path, target_format, **kwargs)
        return output_path
    
    @staticmethod
    def batch_convert(input_dir: str, target_format: str, 
                     output_dir: str = None, **kwargs) -> List[str]:
        """Batch convert images in directory"""
        if output_dir is None:
            output_dir = input_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        converted_files = []
        
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                input_path = os.path.join(input_dir, filename)
                
                path = Path(filename)
                extension = '.jpg' if target_format.upper() == 'JPEG' else f'.{target_format.lower()}'
                output_filename = f"{path.stem}{extension}"
                output_path = os.path.join(output_dir, output_filename)
                
                try:
                    ImageConverter.convert_format(input_path, target_format, output_path, **kwargs)
                    converted_files.append(output_path)
                except Exception as e:
                    print(f"Failed to convert {filename}: {e}")
        
        return converted_files

class Base64ImageHandler:
    """Base64 image encoding/decoding utilities"""
    
    @staticmethod
    def image_to_base64(image_path: str, format: str = 'JPEG') -> str:
        """Convert image to base64 string"""
        image = ImageProcessor.open_image(image_path)
        
        buffer = io.BytesIO()
        ImageProcessor.save_image(image, buffer, format)
        
        img_data = buffer.getvalue()
        base64_string = base64.b64encode(img_data).decode('utf-8')
        
        mime_type = f"image/{format.lower()}"
        return f"data:{mime_type};base64,{base64_string}"
    
    @staticmethod
    def base64_to_image(base64_string: str, output_path: str) -> str:
        """Convert base64 string to image file"""
        # Remove data URL prefix if present
        if base64_string.startswith('data:'):
            base64_string = base64_string.split(',')[1]
        
        img_data = base64.b64decode(base64_string)
        
        with open(output_path, 'wb') as file:
            file.write(img_data)
        
        return output_path
    
    @staticmethod
    def get_image_data_url(image_path: str) -> str:
        """Get data URL for image"""
        mime_type = ImageProcessor.get_image_info(image_path).get('format', 'JPEG').lower()
        return ImageHandler.image_to_base64(image_path, mime_type.upper())