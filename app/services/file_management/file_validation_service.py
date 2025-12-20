"""
File Validation Service

Comprehensive file validation including type checking, size limits,
content validation, and virus scanning.
"""

import magic
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import re

from app.core.config import settings
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class FileValidationService:
    """
    Service for comprehensive file validation.
    """

    # Default file size limits (in bytes)
    DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    DEFAULT_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    DEFAULT_MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20 MB

    # Allowed MIME types by category
    ALLOWED_MIME_TYPES = {
        'image': [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
            'image/svg+xml',
            'image/bmp',
            'image/tiff',
        ],
        'document': [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/csv',
        ],
        'archive': [
            'application/zip',
            'application/x-rar-compressed',
            'application/x-7z-compressed',
            'application/gzip',
            'application/x-tar',
        ],
        'video': [
            'video/mp4',
            'video/mpeg',
            'video/quicktime',
            'video/x-msvideo',
            'video/webm',
        ],
        'audio': [
            'audio/mpeg',
            'audio/wav',
            'audio/ogg',
            'audio/webm',
            'audio/aac',
        ],
    }

    # Dangerous file extensions
    BLOCKED_EXTENSIONS = {
        'exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'js',
        'jar', 'app', 'deb', 'rpm', 'msi', 'dmg',
    }

    # Malicious file signatures (magic bytes)
    MALICIOUS_SIGNATURES = [
        b'MZ',  # Windows executable
        b'\x7fELF',  # Linux executable
    ]

    def __init__(self):
        """Initialize validation service."""
        try:
            self.magic = magic.Magic(mime=True)
        except Exception as e:
            logger.warning(f"Failed to initialize python-magic: {e}")
            self.magic = None

    async def validate_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        size_bytes: int,
        category: Optional[str] = None,
        uploaded_by_user_id: Optional[str] = None,
        custom_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive file validation.

        Args:
            file_content: File binary content
            filename: Original filename
            content_type: Declared MIME type
            size_bytes: File size in bytes
            category: File category
            uploaded_by_user_id: User uploading the file
            custom_rules: Custom validation rules

        Returns:
            Validation result dictionary with is_valid flag and details

        Result structure:
            {
                "is_valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "checks_passed": List[str],
                "checks_failed": List[str],
                "detected_mime_type": str,
                "validation_details": Dict[str, Any],
            }
        """
        errors = []
        warnings = []
        checks_passed = []
        checks_failed = []

        try:
            # 1. Filename validation
            filename_result = self._validate_filename(filename)
            if filename_result['valid']:
                checks_passed.append('filename_format')
            else:
                checks_failed.append('filename_format')
                errors.extend(filename_result['errors'])

            # 2. Extension validation
            extension = self._extract_extension(filename)
            extension_result = self._validate_extension(extension)
            if extension_result['valid']:
                checks_passed.append('extension_allowed')
            else:
                checks_failed.append('extension_allowed')
                errors.extend(extension_result['errors'])

            # 3. File size validation
            size_result = self._validate_file_size(
                size_bytes=size_bytes,
                category=category,
                custom_rules=custom_rules,
            )
            if size_result['valid']:
                checks_passed.append('file_size')
            else:
                checks_failed.append('file_size')
                errors.extend(size_result['errors'])

            # 4. MIME type validation
            detected_mime = self._detect_mime_type(file_content, filename)
            mime_result = self._validate_mime_type(
                declared_mime=content_type,
                detected_mime=detected_mime,
                category=category,
            )
            if mime_result['valid']:
                checks_passed.append('mime_type')
            else:
                checks_failed.append('mime_type')
                errors.extend(mime_result['errors'])
                if mime_result.get('warnings'):
                    warnings.extend(mime_result['warnings'])

            # 5. Content validation
            content_result = self._validate_content(file_content, detected_mime)
            if content_result['valid']:
                checks_passed.append('content_safety')
            else:
                checks_failed.append('content_safety')
                errors.extend(content_result['errors'])

            # 6. Malicious signature detection
            malware_result = self._check_malicious_signatures(file_content)
            if malware_result['valid']:
                checks_passed.append('malware_signatures')
            else:
                checks_failed.append('malware_signatures')
                errors.extend(malware_result['errors'])

            # 7. Image-specific validation
            if detected_mime and detected_mime.startswith('image/'):
                image_result = self._validate_image(file_content, size_bytes)
                if image_result['valid']:
                    checks_passed.append('image_validation')
                else:
                    checks_failed.append('image_validation')
                    errors.extend(image_result['errors'])
                    if image_result.get('warnings'):
                        warnings.extend(image_result['warnings'])

            # 8. Document-specific validation
            if category == 'document' or (detected_mime and 'pdf' in detected_mime):
                doc_result = self._validate_document(file_content, detected_mime)
                if doc_result['valid']:
                    checks_passed.append('document_validation')
                else:
                    checks_failed.append('document_validation')
                    if doc_result.get('warnings'):
                        warnings.extend(doc_result['warnings'])

            is_valid = len(errors) == 0

            validation_result = {
                "is_valid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "detected_mime_type": detected_mime,
                "validation_details": {
                    "filename": filename,
                    "extension": extension,
                    "size_bytes": size_bytes,
                    "declared_mime": content_type,
                    "detected_mime": detected_mime,
                    "category": category,
                    "validated_at": datetime.utcnow().isoformat(),
                    "validator_version": "1.0.0",
                },
            }

            if is_valid:
                logger.info(f"File validation passed: {filename}")
            else:
                logger.warning(f"File validation failed: {filename}, errors: {errors}")

            return validation_result

        except Exception as e:
            logger.error(f"File validation error: {str(e)}", exc_info=True)
            return {
                "is_valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "detected_mime_type": None,
                "validation_details": {},
            }

    def _validate_filename(self, filename: str) -> Dict[str, Any]:
        """Validate filename format and characters."""
        errors = []

        # Check length
        if len(filename) > 255:
            errors.append("Filename too long (max 255 characters)")

        # Check for null bytes
        if '\x00' in filename:
            errors.append("Filename contains null bytes")

        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            errors.append("Filename contains invalid path characters")

        # Check for control characters
        if any(ord(c) < 32 for c in filename):
            errors.append("Filename contains control characters")

        # Must have an extension
        if '.' not in filename:
            errors.append("Filename must have an extension")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _validate_extension(self, extension: Optional[str]) -> Dict[str, Any]:
        """Validate file extension."""
        errors = []

        if not extension:
            errors.append("File has no extension")
            return {"valid": False, "errors": errors}

        # Check if extension is blocked
        if extension.lower() in self.BLOCKED_EXTENSIONS:
            errors.append(f"File extension '{extension}' is not allowed for security reasons")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _validate_file_size(
        self,
        size_bytes: int,
        category: Optional[str] = None,
        custom_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate file size against limits."""
        errors = []

        # Check custom rules first
        if custom_rules and 'max_size_bytes' in custom_rules:
            max_size = custom_rules['max_size_bytes']
        elif category == 'image':
            max_size = self.DEFAULT_MAX_IMAGE_SIZE
        elif category == 'document':
            max_size = self.DEFAULT_MAX_DOCUMENT_SIZE
        else:
            max_size = self.DEFAULT_MAX_FILE_SIZE

        if size_bytes > max_size:
            errors.append(
                f"File size {size_bytes} bytes exceeds maximum allowed {max_size} bytes"
            )

        if size_bytes == 0:
            errors.append("File is empty")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _detect_mime_type(self, content: bytes, filename: str) -> Optional[str]:
        """Detect MIME type from file content."""
        try:
            if self.magic:
                return self.magic.from_buffer(content[:2048])  # Check first 2KB
            else:
                # Fallback to basic detection
                return self._basic_mime_detection(content)
        except Exception as e:
            logger.warning(f"MIME type detection failed: {e}")
            return None

    def _basic_mime_detection(self, content: bytes) -> str:
        """Basic MIME type detection from magic bytes."""
        if content.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg'
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
            return 'image/gif'
        elif content.startswith(b'%PDF'):
            return 'application/pdf'
        elif content.startswith(b'PK\x03\x04'):
            return 'application/zip'
        elif content.startswith(b'RIFF') and b'WEBP' in content[:12]:
            return 'image/webp'
        else:
            return 'application/octet-stream'

    def _validate_mime_type(
        self,
        declared_mime: str,
        detected_mime: Optional[str],
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate MIME type."""
        errors = []
        warnings = []

        # Check if MIME type is allowed for category
        if category and category in self.ALLOWED_MIME_TYPES:
            allowed_mimes = self.ALLOWED_MIME_TYPES[category]
            
            if detected_mime and detected_mime not in allowed_mimes:
                errors.append(
                    f"MIME type '{detected_mime}' not allowed for category '{category}'"
                )

        # Check for MIME type mismatch
        if detected_mime and declared_mime != detected_mime:
            warnings.append(
                f"Declared MIME type '{declared_mime}' differs from detected '{detected_mime}'"
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_content(self, content: bytes, mime_type: Optional[str]) -> Dict[str, Any]:
        """Validate file content for safety."""
        errors = []

        # Check minimum content size
        if len(content) < 10:
            errors.append("File content too small, possibly corrupted")

        # Check for embedded scripts in certain file types
        if mime_type in ['image/svg+xml', 'text/html', 'application/xhtml+xml']:
            if self._contains_scripts(content):
                errors.append("File contains potentially malicious scripts")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _check_malicious_signatures(self, content: bytes) -> Dict[str, Any]:
        """Check for known malicious file signatures."""
        errors = []

        # Check for executable signatures
        for signature in self.MALICIOUS_SIGNATURES:
            if content.startswith(signature):
                errors.append("File contains executable signature and is not allowed")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _contains_scripts(self, content: bytes) -> bool:
        """Check if content contains script tags."""
        try:
            content_str = content.decode('utf-8', errors='ignore').lower()
            script_patterns = [
                '<script',
                'javascript:',
                'onerror=',
                'onload=',
                'onclick=',
            ]
            return any(pattern in content_str for pattern in script_patterns)
        except Exception:
            return False

    def _validate_image(self, content: bytes, size_bytes: int) -> Dict[str, Any]:
        """Image-specific validation."""
        errors = []
        warnings = []

        try:
            from PIL import Image
            import io

            # Try to open image
            img = Image.open(io.BytesIO(content))
            
            # Verify image is not corrupted
            img.verify()
            
            # Check image dimensions
            img = Image.open(io.BytesIO(content))  # Reopen after verify
            width, height = img.size
            
            # Maximum dimensions
            max_dimension = 50000  # 50k pixels
            if width > max_dimension or height > max_dimension:
                errors.append(
                    f"Image dimensions too large: {width}x{height} (max {max_dimension})"
                )

            # Check for decompression bomb
            max_pixels = 178956970  # PIL default
            if width * height > max_pixels:
                errors.append("Image may be a decompression bomb")

            # Warn about large images
            if width > 10000 or height > 10000:
                warnings.append(f"Large image dimensions: {width}x{height}")

        except ImportError:
            logger.warning("PIL not available for image validation")
        except Exception as e:
            errors.append(f"Image validation failed: {str(e)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_document(self, content: bytes, mime_type: Optional[str]) -> Dict[str, Any]:
        """Document-specific validation."""
        warnings = []

        # Check for password-protected PDFs
        if mime_type == 'application/pdf':
            if b'/Encrypt' in content[:1024]:
                warnings.append("PDF appears to be encrypted/password-protected")

        # Check for macros in Office documents
        office_mimes = [
            'application/vnd.ms-excel',
            'application/vnd.ms-powerpoint',
            'application/msword',
        ]
        if mime_type in office_mimes:
            if b'macroEnabled' in content or b'VBA' in content:
                warnings.append("Document may contain macros")

        return {
            "valid": True,
            "errors": [],
            "warnings": warnings,
        }

    def _extract_extension(self, filename: str) -> Optional[str]:
        """Extract file extension."""
        parts = filename.rsplit('.', 1)
        if len(parts) > 1:
            return parts[1].lower()
        return None

    async def validate_upload_session(
        self,
        filename: str,
        content_type: str,
        size_bytes: int,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate file metadata before creating upload session.
        Used for pre-validation without file content.

        Args:
            filename: Original filename
            content_type: MIME type
            size_bytes: Expected file size
            category: File category

        Returns:
            Validation result
        """
        errors = []
        warnings = []

        # Validate filename
        filename_result = self._validate_filename(filename)
        if not filename_result['valid']:
            errors.extend(filename_result['errors'])

        # Validate extension
        extension = self._extract_extension(filename)
        extension_result = self._validate_extension(extension)
        if not extension_result['valid']:
            errors.extend(extension_result['errors'])

        # Validate size
        size_result = self._validate_file_size(size_bytes, category)
        if not size_result['valid']:
            errors.extend(size_result['errors'])

        # Validate MIME type
        if category and category in self.ALLOWED_MIME_TYPES:
            if content_type not in self.ALLOWED_MIME_TYPES[category]:
                errors.append(
                    f"MIME type '{content_type}' not allowed for category '{category}'"
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    async def scan_for_viruses(
        self,
        file_content: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        Scan file for viruses using ClamAV or similar.
        This is a placeholder - integrate with actual antivirus solution.

        Args:
            file_content: File binary content
            filename: Original filename

        Returns:
            Scan result
        """
        try:
            # TODO: Integrate with actual virus scanner (ClamAV, VirusTotal, etc.)
            # For now, return clean status
            logger.info(f"Virus scan for: {filename}")

            return {
                "status": "clean",
                "scanner": "placeholder",
                "scanned_at": datetime.utcnow().isoformat(),
                "threats_found": [],
            }

        except Exception as e:
            logger.error(f"Virus scan failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "scanner": "placeholder",
                "scanned_at": datetime.utcnow().isoformat(),
                "error": str(e),
            }