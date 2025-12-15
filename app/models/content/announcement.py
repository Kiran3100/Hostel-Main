# app.models/content/announcement.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import AnnouncementCategory, Priority, TargetAudience
from app.models.base import BaseEntity


class Announcement(BaseEntity):
    """Notices & announcements."""
    __tablename__ = "content_announcement"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)

    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(String(5000))

    category: Mapped[AnnouncementCategory] = mapped_column(
        SAEnum(AnnouncementCategory, name="announcement_category")
    )
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority, name="announcement_priority"))

    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    target_audience: Mapped[TargetAudience] = mapped_column(
        SAEnum(TargetAudience, name="announcement_target_audience")
    )
    target_room_ids: Mapped[List[UUID]] = mapped_column(JSON, default=list)
    target_student_ids: Mapped[List[UUID]] = mapped_column(JSON, default=list)
    target_floor_numbers: Mapped[List[int]] = mapped_column(JSON, default=list)

    attachments: Mapped[List[str]] = mapped_column(JSON, default=list)

    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"))
    created_by_role: Mapped[str] = mapped_column(String(50))

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)