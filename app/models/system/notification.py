# app.models/system/notification.py
from typing import Union
from uuid import UUID

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class NotificationConfig(BaseItem):
    """Notification configuration settings."""
    __tablename__ = "sys_notification_config"

    notification_type: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Union[str, None]] = mapped_column(String(500))

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    email_template: Mapped[Union[str, None]] = mapped_column(String(100))
    sms_template: Mapped[Union[str, None]] = mapped_column(String(100))
    push_template: Mapped[Union[str, None]] = mapped_column(String(100))