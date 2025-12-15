# app/utils/email.py
from __future__ import annotations

"""
Email utilities: configuration, message structure, and SMTP-based sending.

This module provides:
- EmailMessage: validated email message dataclass.
- EmailConfig: configuration loaded from environment variables.
- build_email: convenience helper to construct EmailMessage.
- send_email / send_email_async: SMTP-based sending functions.
"""

import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, Mapping

from .validators import is_valid_email

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """Custom exception for email operations."""
    pass


@dataclass
class EmailMessage:
    """Email message structure with validation."""
    subject: str
    to: list[str]
    body_text: str | None = None
    body_html: str | None = None
    from_email: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    headers: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        """Validate email message after initialization."""
        if not self.subject.strip():
            raise EmailError("Subject cannot be empty")
        
        if not self.to:
            raise EmailError("At least one recipient is required")
        
        if not self.body_text and not self.body_html:
            raise EmailError("Either body_text or body_html must be provided")
        
        # Validate email addresses
        for email in self.to:
            if not is_valid_email(email):
                raise EmailError(f"Invalid recipient email: {email}")
        
        if self.cc:
            for email in self.cc:
                if not is_valid_email(email):
                    raise EmailError(f"Invalid CC email: {email}")
        
        if self.bcc:
            for email in self.bcc:
                if not is_valid_email(email):
                    raise EmailError(f"Invalid BCC email: {email}")


@dataclass
class EmailConfig:
    """Email configuration."""
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    from_email: str | None = None

    @classmethod
    def from_env(cls) -> EmailConfig:
        """Create email config from environment variables."""
        return cls(
            smtp_host=os.getenv("SMTP_HOST", "localhost"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USERNAME", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            from_email=os.getenv("FROM_EMAIL"),
        )


def build_email(
    *,
    subject: str,
    to: Iterable[str],
    body_text: str | None = None,
    body_html: str | None = None,
    from_email: str | None = None,
    cc: Iterable[str] | None = None,
    bcc: Iterable[str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> EmailMessage:
    """Helper to construct EmailMessage from typical arguments."""
    return EmailMessage(
        subject=subject,
        to=list(to),
        body_text=body_text,
        body_html=body_html,
        from_email=from_email,
        cc=list(cc) if cc else None,
        bcc=list(bcc) if bcc else None,
        headers=headers,
    )


def send_email(message: EmailMessage, config: EmailConfig | None = None) -> None:
    """Send an email using SMTP."""
    if config is None:
        config = EmailConfig.from_env()
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = message.subject
        msg['From'] = message.from_email or config.from_email or config.username
        msg['To'] = ', '.join(message.to)
        
        if message.cc:
            msg['Cc'] = ', '.join(message.cc)
        
        # Add custom headers
        if message.headers:
            for key, value in message.headers.items():
                msg[key] = value
        
        # Add text part
        if message.body_text:
            text_part = MIMEText(message.body_text, 'plain')
            msg.attach(text_part)
        
        # Add HTML part
        if message.body_html:
            html_part = MIMEText(message.body_html, 'html')
            msg.attach(html_part)
        
        # Get all recipients
        recipients = message.to[:]
        if message.cc:
            recipients.extend(message.cc)
        if message.bcc:
            recipients.extend(message.bcc)
        
        # Send email
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            if config.use_tls:
                server.starttls()
            
            if config.username and config.password:
                server.login(config.username, config.password)
            
            server.send_message(msg, to_addrs=recipients)
        
        logger.info(f"Email sent successfully to {len(recipients)} recipients")
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise EmailError(f"Failed to send email: {e}") from e


async def send_email_async(message: EmailMessage, config: EmailConfig | None = None) -> None:
    """Send email asynchronously using asyncio."""
    import asyncio
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_email, message, config)