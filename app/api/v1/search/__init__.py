"""
Search API module initialization.

This module provides search functionality including:
- Basic keyword search
- Advanced filtered search
- Geospatial nearby search
- Autocomplete suggestions
"""

from fastapi import APIRouter

from . import autocomplete, search

# Initialize the main search router
router = APIRouter()

# Include sub-routers with proper ordering (more specific routes first)
router.include_router(autocomplete.router)
router.include_router(search.router)

__all__ = ["router"]