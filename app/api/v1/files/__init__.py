from fastapi import APIRouter

from . import documents, images, upload

router = APIRouter()

router.include_router(upload.router)
router.include_router(images.router)
router.include_router(documents.router)

__all__ = ["router"]