# app.models/content/notice.py
from datetime import datetime
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import AnnouncementCategory, TargetAudience, Priority
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.core.hostel import Hostel


class Notice(BaseEntity):
    """
    Simpler notice model (from ER doc) for system-wide or hostel-specific notices.
    """
    __tablename__ = "content_notice"

    hostel_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_hostel.id"), nullable=True, index=True)

    notice_title: Mapped[str] = mapped_column(String(255))
    notice_content: Mapped[str] = mapped_column(String(5000))

    category: Mapped[AnnouncementCategory] = mapped_column(
        SAEnum(AnnouncementCategory, name="notice_category")
    )
    target_audience: Mapped[TargetAudience] = mapped_column(
        SAEnum(TargetAudience, name="notice_target_audience")
    )
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority, name="notice_priority"))

    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)

    published_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))

    hostel: Mapped[Union["Hostel", None]] = relationship()