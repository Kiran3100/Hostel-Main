"""
File handling utilities for hostel management system
"""

import os
import shutil
import tempfile
import mimetypes
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from datetime import datetime
import zipfile
import tarfile
import json
from urllib.parse import urlparse
import requests

# Try to import magic, but make it optional
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    print("Warning: python-magic not available. Falling back to mimetypes for file type detection.")

class FileHelper:
    """General file manipulation utilities"""
    
    @staticmethod
    def ensure_directory(directory_path: str) -> str:
        """Create directory if it doesn't exist"""
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Get file size in bytes"""
        return os.path.getsize(file_path)
    
    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, Any]:
        """Get comprehensive file information"""
        path = Path(file_path)
        stat = path.stat()
        
        return {
            'name': path.name,
            'stem': path.stem,
            'suffix': path.suffix,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'accessed': datetime.fromtimestamp(stat.st_atime),
            'is_file': path.is_file(),
            'is_directory': path.is_dir(),
            'absolute_path': str(path.absolute()),
            'mime_type': FileTypeDetector.detect_mime_type(file_path)
        }
    
    @staticmethod
    def copy_file(source: str, destination: str, overwrite: bool = False) -> str:
        """Copy file to destination"""
        dest_path = Path(destination)
        
        if dest_path.exists() and not overwrite:
            # Generate unique filename
            counter = 1
            while dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                parent = dest_path.parent
                dest_path = parent / f"{stem}_{counter}{suffix}"
                counter += 1
        
        FileHelper.ensure_directory(str(dest_path.parent))
        shutil.copy2(source, dest_path)
        return str(dest_path)
    
    @staticmethod
    def move_file(source: str, destination: str, overwrite: bool = False) -> str:
        """Move file to destination"""
        dest_path = Path(destination)
        
        if dest_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {destination}")
        
        FileHelper.ensure_directory(str(dest_path.parent))
        shutil.move(source, dest_path)
        return str(dest_path)
    
    @staticmethod
    def delete_file(file_path: str, force: bool = False) -> bool:
        """Delete file safely"""
        try:
            path = Path(file_path)
            if path.exists():
                if force or path.is_file():
                    path.unlink()
                    return True
                else:
                    shutil.rmtree(path)
                    return True
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
        return False
    
    @staticmethod
    def read_file(file_path: str, encoding: str = 'utf-8') -> str:
        """Read text file content"""
        with open(file_path, 'r', encoding=encoding) as file:
            return file.read()
    
    @staticmethod
    def write_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
        """Write content to file"""
        path = Path(file_path)
        FileHelper.ensure_directory(str(path.parent))
        
        with open(file_path, 'w', encoding=encoding) as file:
            file.write(content)
    
    @staticmethod
    def append_to_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
        """Append content to file"""
        with open(file_path, 'a', encoding=encoding) as file:
            file.write(content)
    
    @staticmethod
    def read_json_file(file_path: str) -> Dict[str, Any]:
        """Read JSON file"""
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    @staticmethod
    def write_json_file(file_path: str, data: Dict[str, Any], indent: int = 2) -> None:
        """Write data to JSON file"""
        path = Path(file_path)
        FileHelper.ensure_directory(str(path.parent))
        
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=indent, ensure_ascii=False)
    
    @staticmethod
    def get_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
        """Calculate file hash"""
        hash_algorithms = {
            'md5': hashlib.md5(),
            'sha1': hashlib.sha1(),
            'sha256': hashlib.sha256(),
            'sha512': hashlib.sha512()
        }
        
        if algorithm not in hash_algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        hasher = hash_algorithms[algorithm]
        
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    @staticmethod
    def find_files(directory: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        """Find files matching pattern"""
        path = Path(directory)
        
        if recursive:
            files = path.rglob(pattern)
        else:
            files = path.glob(pattern)
        
        return [str(f) for f in files if f.is_file()]
    
    @staticmethod
    def get_directory_size(directory: str) -> int:
        """Calculate total directory size"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """Clean filename for safe storage"""
        # Remove dangerous characters
        dangerous_chars = '<>:"|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename

class DirectoryManager:
    """Directory management utilities"""
    
    @staticmethod
    def create_directory_structure(base_path: str, structure: Dict[str, Any]) -> Dict[str, str]:
        """Create nested directory structure"""
        created_paths = {}
        
        def _create_recursive(current_path: str, current_structure: Dict[str, Any]):
            for name, content in current_structure.items():
                new_path = os.path.join(current_path, name)
                
                if isinstance(content, dict):
                    # It's a directory
                    FileHelper.ensure_directory(new_path)
                    created_paths[name] = new_path
                    _create_recursive(new_path, content)
                else:
                    # It's a file
                    FileHelper.ensure_directory(os.path.dirname(new_path))
                    if content:  # If content is provided
                        FileHelper.write_file(new_path, str(content))
                    created_paths[name] = new_path
        
        FileHelper.ensure_directory(base_path)
        _create_recursive(base_path, structure)
        return created_paths
    
    @staticmethod
    def copy_directory(source: str, destination: str, overwrite: bool = False) -> str:
        """Copy entire directory"""
        if os.path.exists(destination) and not overwrite:
            raise FileExistsError(f"Directory already exists: {destination}")
        
        shutil.copytree(source, destination, dirs_exist_ok=overwrite)
        return destination
    
    @staticmethod
    def move_directory(source: str, destination: str, overwrite: bool = False) -> str:
        """Move entire directory"""
        if os.path.exists(destination) and not overwrite:
            raise FileExistsError(f"Directory already exists: {destination}")
        
        shutil.move(source, destination)
        return destination
    
    @staticmethod
    def delete_directory(directory: str, force: bool = False) -> bool:
        """Delete directory and contents"""
        try:
            if os.path.exists(directory):
                if force:
                    shutil.rmtree(directory)
                else:
                    os.rmdir(directory)  # Only works if empty
                return True
        except Exception as e:
            print(f"Error deleting directory {directory}: {e}")
            return False
        return False
    
    @staticmethod
    def list_directory_contents(directory: str, include_hidden: bool = False) -> Dict[str, List[str]]:
        """List directory contents categorized"""
        contents = {'files': [], 'directories': []}
        
        try:
            for item in os.listdir(directory):
                if not include_hidden and item.startswith('.'):
                    continue
                
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    contents['files'].append(item)
                elif os.path.isdir(item_path):
                    contents['directories'].append(item)
        except OSError as e:
            print(f"Error listing directory {directory}: {e}")
        
        return contents

class FileTypeDetector:
    """File type detection utilities"""
    
    # Enhanced MIME type mappings for better fallback support
    MIME_MAPPINGS = {
        # Images
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.ico': 'image/x-icon',
        '.svg': 'image/svg+xml',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
        
        # Documents
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.rtf': 'application/rtf',
        '.odt': 'application/vnd.oasis.opendocument.text',
        '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
        
        # Video
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.wmv': 'video/x-ms-wmv',
        '.flv': 'video/x-flv',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.m4v': 'video/x-m4v',
        
        # Audio
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.aac': 'audio/aac',
        '.ogg': 'audio/ogg',
        '.wma': 'audio/x-ms-wma',
        '.m4a': 'audio/mp4',
        
        # Archives
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
        '.7z': 'application/x-7z-compressed',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
        '.bz2': 'application/x-bzip2',
        
        # Other
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.py': 'text/x-python',
        '.sql': 'application/sql',
    }
    
    @staticmethod
    def detect_mime_type(file_path: str) -> Optional[str]:
        """Detect MIME type using python-magic or fallback to mimetypes"""
        if MAGIC_AVAILABLE:
            try:
                return magic.from_file(file_path, mime=True)
            except Exception as e:
                print(f"Warning: Magic detection failed for {file_path}: {e}")
        
        # Get extension
        ext = Path(file_path).suffix.lower()
        
        # Try custom mapping first
        if ext in FileTypeDetector.MIME_MAPPINGS:
            return FileTypeDetector.MIME_MAPPINGS[ext]
        
        # Fallback to mimetypes
        mime_type, encoding = mimetypes.guess_type(file_path)
        return mime_type
    
    @staticmethod
    def is_image(file_path: str) -> bool:
        """Check if file is an image"""
        mime_type = FileTypeDetector.detect_mime_type(file_path)
        return mime_type and mime_type.startswith('image/')
    
    @staticmethod
    def is_document(file_path: str) -> bool:
        """Check if file is a document"""
        document_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/csv',
            'application/rtf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.oasis.opendocument.spreadsheet'
        ]
        mime_type = FileTypeDetector.detect_mime_type(file_path)
        return mime_type in document_types
    
    @staticmethod
    def is_video(file_path: str) -> bool:
        """Check if file is a video"""
        mime_type = FileTypeDetector.detect_mime_type(file_path)
        return mime_type and mime_type.startswith('video/')
    
    @staticmethod
    def is_audio(file_path: str) -> bool:
        """Check if file is audio"""
        mime_type = FileTypeDetector.detect_mime_type(file_path)
        return mime_type and mime_type.startswith('audio/')
    
    @staticmethod
    def is_archive(file_path: str) -> bool:
        """Check if file is an archive"""
        archive_types = [
            'application/zip',
            'application/x-rar-compressed',
            'application/x-7z-compressed',
            'application/x-tar',
            'application/gzip',
            'application/x-bzip2'
        ]
        mime_type = FileTypeDetector.detect_mime_type(file_path)
        return mime_type in archive_types
    
    @staticmethod
    def get_file_category(file_path: str) -> str:
        """Get general file category"""
        if FileTypeDetector.is_image(file_path):
            return 'image'
        elif FileTypeDetector.is_document(file_path):
            return 'document'
        elif FileTypeDetector.is_video(file_path):
            return 'video'
        elif FileTypeDetector.is_audio(file_path):
            return 'audio'
        elif FileTypeDetector.is_archive(file_path):
            return 'archive'
        else:
            return 'other'

class FileValidator:
    """File validation utilities"""
    
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.svg', '.tiff', '.tif']
    ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.csv', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.odt', '.ods']
    ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v']
    ALLOWED_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a']
    
    MAX_FILE_SIZES = {
        'image': 10 * 1024 * 1024,  # 10MB
        'document': 50 * 1024 * 1024,  # 50MB
        'video': 500 * 1024 * 1024,  # 500MB
        'audio': 100 * 1024 * 1024,  # 100MB
        'archive': 200 * 1024 * 1024,  # 200MB
        'other': 25 * 1024 * 1024,  # 25MB
    }
    
    @classmethod
    def validate_file_extension(cls, filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension"""
        ext = Path(filename).suffix.lower()
        return ext in [e.lower() for e in allowed_extensions]
    
    @classmethod
    def validate_file_size(cls, file_path: str, max_size: int) -> bool:
        """Validate file size"""
        size = FileHelper.get_file_size(file_path)
        return size <= max_size
    
    @classmethod
    def validate_image_file(cls, file_path: str) -> Dict[str, Any]:
        """Validate image file"""
        result = {'valid': True, 'errors': []}
        
        # Check extension
        if not cls.validate_file_extension(file_path, cls.ALLOWED_IMAGE_EXTENSIONS):
            result['valid'] = False
            result['errors'].append('Invalid image file extension')
        
        # Check size
        if not cls.validate_file_size(file_path, cls.MAX_FILE_SIZES['image']):
            result['valid'] = False
            result['errors'].append('Image file too large')
        
        # Check if it's actually an image
        if not FileTypeDetector.is_image(file_path):
            result['valid'] = False
            result['errors'].append('File is not a valid image')
        
        return result
    
    @classmethod
    def validate_document_file(cls, file_path: str) -> Dict[str, Any]:
        """Validate document file"""
        result = {'valid': True, 'errors': []}
        
        # Check extension
        if not cls.validate_file_extension(file_path, cls.ALLOWED_DOCUMENT_EXTENSIONS):
            result['valid'] = False
            result['errors'].append('Invalid document file extension')
        
        # Check size
        if not cls.validate_file_size(file_path, cls.MAX_FILE_SIZES['document']):
            result['valid'] = False
            result['errors'].append('Document file too large')
        
        return result
    
    @classmethod
    def validate_file_by_category(cls, file_path: str) -> Dict[str, Any]:
        """Validate file based on its detected category"""
        category = FileTypeDetector.get_file_category(file_path)
        
        validation_methods = {
            'image': cls.validate_image_file,
            'document': cls.validate_document_file,
        }
        
        if category in validation_methods:
            return validation_methods[category](file_path)
        
        # Generic validation for other categories
        result = {'valid': True, 'errors': []}
        max_size = cls.MAX_FILE_SIZES.get(category, cls.MAX_FILE_SIZES['other'])
        
        if not cls.validate_file_size(file_path, max_size):
            result['valid'] = False
            result['errors'].append(f'{category.title()} file too large')
        
        return result
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Check if filename is safe"""
        dangerous_patterns = ['../', '.\\', '<', '>', ':', '"', '|', '?', '*']
        filename_lower = filename.lower()
        
        for pattern in dangerous_patterns:
            if pattern in filename_lower:
                return False
        
        # Check for reserved names (Windows)
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                         'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                         'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = Path(filename).stem.upper()
        return name_without_ext not in reserved_names

class TempFileManager:
    """Temporary file management utilities"""
    
    def __init__(self, cleanup_on_exit: bool = True):
        self.temp_files: List[str] = []
        self.temp_dirs: List[str] = []
        self.cleanup_on_exit = cleanup_on_exit
        
        if cleanup_on_exit:
            import atexit
            atexit.register(self.cleanup_all)
    
    def create_temp_file(self, suffix: str = None, prefix: str = None, 
                        content: str = None) -> str:
        """Create temporary file"""
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        
        try:
            if content:
                with os.fdopen(fd, 'w') as temp_file:
                    temp_file.write(content)
            else:
                os.close(fd)
        except:
            os.close(fd)
            raise
        
        self.temp_files.append(temp_path)
        return temp_path
    
    def create_temp_directory(self, prefix: str = None) -> str:
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def cleanup_file(self, file_path: str) -> bool:
        """Clean up specific temporary file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
            if file_path in self.temp_files:
                self.temp_files.remove(file_path)
            return True
        except Exception as e:
            print(f"Error cleaning up temp file {file_path}: {e}")
            return False
    
    def cleanup_directory(self, dir_path: str) -> bool:
        """Clean up specific temporary directory"""
        try:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
            if dir_path in self.temp_dirs:
                self.temp_dirs.remove(dir_path)
            return True
        except Exception as e:
            print(f"Error cleaning up temp directory {dir_path}: {e}")
            return False
    
    def cleanup_all(self) -> None:
        """Clean up all temporary files and directories"""
        for temp_file in self.temp_files[:]:
            self.cleanup_file(temp_file)
        
        for temp_dir in self.temp_dirs[:]:
            self.cleanup_directory(temp_dir)

class ArchiveManager:
    """Archive file management utilities"""
    
    @staticmethod
    def create_zip_archive(source_path: str, archive_path: str, 
                          compression: int = zipfile.ZIP_DEFLATED) -> str:
        """Create ZIP archive from directory or file"""
        with zipfile.ZipFile(archive_path, 'w', compression) as zipf:
            if os.path.isfile(source_path):
                zipf.write(source_path, os.path.basename(source_path))
            elif os.path.isdir(source_path):
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, source_path)
                        zipf.write(file_path, arc_name)
        
        return archive_path
    
    @staticmethod
    def extract_zip_archive(archive_path: str, extract_to: str) -> str:
        """Extract ZIP archive"""
        FileHelper.ensure_directory(extract_to)
        
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(extract_to)
        
        return extract_to
    
    @staticmethod
    def create_tar_archive(source_path: str, archive_path: str, 
                          compression: str = 'gz') -> str:
        """Create TAR archive"""
        mode = f'w:{compression}' if compression else 'w'
        
        with tarfile.open(archive_path, mode) as tarf:
            if os.path.isfile(source_path):
                tarf.add(source_path, arcname=os.path.basename(source_path))
            elif os.path.isdir(source_path):
                tarf.add(source_path, arcname=os.path.basename(source_path))
        
        return archive_path
    
    @staticmethod
    def extract_tar_archive(archive_path: str, extract_to: str) -> str:
        """Extract TAR archive"""
        FileHelper.ensure_directory(extract_to)
        
        with tarfile.open(archive_path, 'r') as tarf:
            tarf.extractall(extract_to)
        
        return extract_to
    
    @staticmethod
    def list_archive_contents(archive_path: str) -> List[str]:
        """List contents of archive file"""
        ext = Path(archive_path).suffix.lower()
        
        if ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                return zipf.namelist()
        elif ext in ['.tar', '.tar.gz', '.tar.bz2', '.tar.xz']:
            with tarfile.open(archive_path, 'r') as tarf:
                return tarf.getnames()
        else:
            raise ValueError(f"Unsupported archive format: {ext}")

class FileDownloader:
    """File download utilities"""
    
    @staticmethod
    def download_file(url: str, destination: str = None, chunk_size: int = 8192, 
                     timeout: int = 30) -> str:
        """Download file from URL"""
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to download file from {url}: {e}")
        
        if destination is None:
            # Generate filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path) or 'downloaded_file'
            destination = os.path.join(tempfile.gettempdir(), filename)
        
        FileHelper.ensure_directory(os.path.dirname(destination))
        
        try:
            with open(destination, 'wb') as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
        except IOError as e:
            # Clean up partial file
            if os.path.exists(destination):
                os.unlink(destination)
            raise Exception(f"Failed to write downloaded file to {destination}: {e}")
        
        return destination
    
    @staticmethod
    def download_with_progress(url: str, destination: str = None, 
                              progress_callback: callable = None,
                              timeout: int = 30) -> str:
        """Download file with progress tracking"""
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to download file from {url}: {e}")
        
        total_size = int(response.headers.get('content-length', 0))
        
        if destination is None:
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path) or 'downloaded_file'
            destination = os.path.join(tempfile.gettempdir(), filename)
        
        FileHelper.ensure_directory(os.path.dirname(destination))
        
        downloaded_size = 0
        try:
            with open(destination, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress, downloaded_size, total_size)
        except IOError as e:
            # Clean up partial file
            if os.path.exists(destination):
                os.unlink(destination)
            raise Exception(f"Failed to write downloaded file to {destination}: {e}")
        
        return destination

# Utility functions for easy access
def get_file_info(file_path: str) -> Dict[str, Any]:
    """Quick access to file information"""
    return FileHelper.get_file_info(file_path)

def detect_file_type(file_path: str) -> str:
    """Quick access to file type detection"""
    return FileTypeDetector.get_file_category(file_path)

def validate_upload_file(file_path: str) -> Dict[str, Any]:
    """Quick validation for uploaded files"""
    return FileValidator.validate_file_by_category(file_path)

def create_temp_file(content: str = None, suffix: str = None) -> str:
    """Quick temporary file creation"""
    temp_manager = TempFileManager()
    return temp_manager.create_temp_file(content=content, suffix=suffix)