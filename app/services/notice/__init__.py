# app/services/notice/__init__.py
"""
Notice-related services.

- NoticeService: core CRUD, listing, and active/public retrieval
  for content_notice records.
"""

from .notice_service import NoticeService

__all__ = [
    "NoticeService",
]