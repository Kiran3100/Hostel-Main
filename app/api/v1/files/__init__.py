"""
File Management API Module

This module provides comprehensive file management capabilities including:
- General file uploads (direct and pre-signed)
- Image processing and optimization
- Document management and verification
"""

from fastapi import APIRouter

from . import documents, images, upload

# Initialize main router with prefix and tags
router = APIRouter(prefix="/files", tags=["files"])

# Include sub-routers
router.include_router(upload.router)
router.include_router(images.router)
router.include_router(documents.router)

__all__ = ["router"]