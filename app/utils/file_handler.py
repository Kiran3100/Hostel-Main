# app/utils/file_handler.py
from __future__ import annotations

"""
File handling utilities:
- Filename sanitization and unique name generation.
- Validation of file extensions, sizes, and MIME types.
- Saving raw bytes or framework upload objects to disk.
- Safe file deletion.
"""

import hashlib
import logging
import mimetypes
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

# For frameworks like FastAPI
try:
    from starlette.datastructures import UploadFile
except ImportError:
    UploadFile = object  # type: ignore[misc,assignment]


class FileHandlerError(Exception):
    """Custom exception for file handling errors."""
    pass


# Allowed file extensions and MIME types
ALLOWED_EXTENSIONS = {
    'images': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
    'documents': {'.pdf', '.doc', '.docx', '.txt', '.rtf'},
    'spreadsheets': {'.xls', '.xlsx', '.csv'},
    'archives': {'.zip', '.rar', '.7z'},
}

ALLOWED_MIME_TYPES = {
    'images': {'image/jpeg', 'image/png', 'image/gif', 'image/webp'},
    'documents': {'application/pdf', 'application/msword', 'text/plain'},
    'spreadsheets': {'application/vnd.ms-excel', 'text/csv'},
}

# Precomputed unions for performance when no category is specified
ALL_ALLOWED_EXTENSIONS = {
    ext for exts in ALLOWED_EXTENSIONS.values() for ext in exts
}
ALL_ALLOWED_MIME_TYPES = {
    mime for mset in ALLOWED_MIME_TYPES.values() for mime in mset
}

# Maximum file sizes (in bytes)
MAX_FILE_SIZES = {
    'images': 10 * 1024 * 1024,      # 10MB
    'documents': 50 * 1024 * 1024,   # 50MB
    'default': 5 * 1024 * 1024,      # 5MB
}

# Filesystem permissions
DIR_PERMISSIONS = 0o755
FILE_PERMISSIONS = 0o644


def safe_filename(filename: str) -> str:
    """Generate a safe filename by stripping directory components and unsafe chars."""
    if not filename or not isinstance(filename, str):
        raise FileHandlerError("Filename must be a non-empty string")
    
    # Get basename to prevent directory traversal
    name = os.path.basename(filename)
    
    # Remove potentially dangerous characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
    name = "".join(ch for ch in name if ch in safe_chars)
    
    # Remove leading dots and dashes
    name = name.lstrip(".-")
    
    if not name:
        raise FileHandlerError("Filename contains no valid characters")
    
    # Limit length
    if len(name) > 255:
        stem, ext = os.path.splitext(name)
        max_stem = 255 - len(ext)
        name = stem[:max_stem] + ext
    
    return name


def generate_unique_filename(original_name: str, *, prefix: str | None = None) -> str:
    """Generate a unique filename with the same extension."""
    safe_name = safe_filename(original_name)
    stem, ext = os.path.splitext(safe_name)
    
    # Generate unique token
    token = secrets.token_hex(8)
    
    # Build new name
    if prefix:
        new_name = f"{prefix}_{stem}_{token}{ext}"
    else:
        new_name = f"{stem}_{token}{ext}"
    
    return new_name


def validate_file_extension(filename: str, category: str | None = None) -> bool:
    """Validate file extension against allowed types."""
    ext = os.path.splitext(filename)[1].lower()
    
    if category and category in ALLOWED_EXTENSIONS:
        return ext in ALLOWED_EXTENSIONS[category]
    
    # Check all categories if none specified or category not recognized
    return ext in ALL_ALLOWED_EXTENSIONS


def validate_file_size(size: int, category: str | None = None) -> bool:
    """Validate file size against limits."""
    max_size = MAX_FILE_SIZES.get(category, MAX_FILE_SIZES['default'])
    return 0 < size <= max_size


def validate_mime_type(mime_type: str, category: str | None = None) -> bool:
    """Validate MIME type against allowed types."""
    if category and category in ALLOWED_MIME_TYPES:
        return mime_type in ALLOWED_MIME_TYPES[category]
    
    # Check all categories if none specified or category not recognized
    return mime_type in ALL_ALLOWED_MIME_TYPES


def get_file_hash(data: bytes) -> str:
    """Generate SHA-256 hash of file content."""
    return hashlib.sha256(data).hexdigest()


def ensure_directory(path: str | Path) -> None:
    """Ensure directory exists with proper permissions."""
    try:
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True, mode=DIR_PERMISSIONS)
        logger.debug(f"Ensured directory exists: {path}")
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        raise FileHandlerError(f"Failed to create directory: {e}") from e


def save_bytes_to_path(
    data: bytes, 
    path: str | Path, 
    *, 
    validate: bool = True,
    category: str | None = None
) -> dict[str, str]:
    """
    Save raw bytes to a file with validation.
    Returns file info including path and hash.
    """
    if not isinstance(data, bytes):
        raise FileHandlerError("Data must be bytes")
    
    if not data:
        raise FileHandlerError("Data cannot be empty")
    
    path_obj = Path(path)
    
    if validate:
        # Validate file size
        if not validate_file_size(len(data), category):
            max_size = MAX_FILE_SIZES.get(category, MAX_FILE_SIZES['default'])
            raise FileHandlerError(f"File size exceeds limit of {max_size} bytes")
        
        # Validate extension
        if not validate_file_extension(path_obj.name, category):
            raise FileHandlerError(f"File extension not allowed for category: {category}")
        
        # Validate MIME type
        mime_type, _ = mimetypes.guess_type(str(path_obj))
        if mime_type and not validate_mime_type(mime_type, category):
            raise FileHandlerError(f"MIME type not allowed: {mime_type}")
    
    try:
        ensure_directory(path_obj.parent)
        
        # Generate file hash
        file_hash = get_file_hash(data)
        
        # Write file with secure permissions
        path_obj.write_bytes(data)
        path_obj.chmod(FILE_PERMISSIONS)
        
        logger.info(f"File saved: {path_obj} (hash: {file_hash[:8]}...)")
        
        return {
            'path': str(path_obj),
            'filename': path_obj.name,
            'size': str(len(data)),
            'hash': file_hash,
        }
        
    except Exception as e:
        logger.error(f"Failed to save file {path}: {e}")
        raise FileHandlerError(f"Failed to save file: {e}") from e


async def save_upload_file(
    upload: UploadFile,  # type: ignore[valid-type]
    destination_dir: str | Path,
    *,
    filename: str | None = None,
    category: str | None = None,
    max_size: int | None = None,
) -> dict[str, str]:
    """
    Save an UploadFile with comprehensive validation.
    Returns file info.
    """
    if not hasattr(upload, 'filename') or not upload.filename:
        raise FileHandlerError("Upload file must have a filename")
    
    if not hasattr(upload, 'size'):
        # Read content to check size
        content = await upload.read()
        await upload.seek(0)  # Reset file pointer
        upload.size = len(content)
    
    # Validate file size
    file_size = getattr(upload, 'size', 0)
    if max_size and file_size > max_size:
        raise FileHandlerError(f"File size {file_size} exceeds limit {max_size}")
    
    if not validate_file_size(file_size, category):
        max_allowed = MAX_FILE_SIZES.get(category, MAX_FILE_SIZES['default'])
        raise FileHandlerError(f"File size exceeds limit of {max_allowed} bytes")
    
    # Generate safe filename
    original_name = upload.filename
    final_name = filename or generate_unique_filename(original_name)
    
    # Validate extension
    if not validate_file_extension(final_name, category):
        raise FileHandlerError(f"File extension not allowed for category: {category}")
    
    # Validate MIME type if available
    if hasattr(upload, 'content_type') and upload.content_type:
        if not validate_mime_type(upload.content_type, category):
            raise FileHandlerError(f"MIME type not allowed: {upload.content_type}")
    
    dest_dir = Path(destination_dir)
    dest_path = dest_dir / final_name
    
    try:
        ensure_directory(dest_dir)
        
        # Read and save content
        content = await upload.read()
        
        if not content:
            raise FileHandlerError("Upload file is empty")
        
        return save_bytes_to_path(content, dest_path, validate=False, category=category)
        
    except Exception as e:
        logger.error(f"Failed to save upload file: {e}")
        raise FileHandlerError(f"Failed to save upload file: {e}") from e


def delete_file(path: str | Path) -> None:
    """Safely delete a file."""
    try:
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_file():
            path_obj.unlink()
            logger.info(f"File deleted: {path_obj}")
        else:
            logger.warning(f"File not found or not a file: {path_obj}")
    except Exception as e:
        logger.error(f"Failed to delete file {path}: {e}")
        raise FileHandlerError(f"Failed to delete file: {e}") from e