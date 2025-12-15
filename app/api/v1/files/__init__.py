# api/v1/files/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import upload
from . import images
from . import documents

router = APIRouter(prefix="/files")

router.include_router(upload.router, tags=["Files - Upload"])
router.include_router(images.router, tags=["Files - Images"])
router.include_router(documents.router, tags=["Files - Documents"])

__all__ = ["router"]