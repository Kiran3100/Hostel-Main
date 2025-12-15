# app/utils/__init__.py
from __future__ import annotations

"""
Utility helpers for the hostel management SaaS project.

This package includes:
- date_utils: date/datetime helpers.
- email: abstract email sending utilities.
- sms: abstract SMS sending utilities.
- file_handler: file saving / naming helpers.
- formatters: small formatting helpers for dates, currency, etc.
- string_utils: generic string helpers (slugify, tokens, etc.).
- validators: basic validation helpers.

Typical usage:

    from app.utils import date_utils, sms
    now = date_utils.now_utc()
    sms_result = sms.send_sms(phone="+911234567890", message="Hello")
"""

from . import date_utils
from . import email
from . import file_handler
from . import formatters
from . import sms
from . import string_utils
from . import validators

__all__ = [
    "date_utils",
    "email",
    "file_handler",
    "formatters",
    "sms",
    "string_utils",
    "validators",
]