# app/utils/sms.py
from __future__ import annotations

"""
SMS utilities:
- Normalization and validation of phone numbers (E.164, Indian focus).
- SMS provider abstraction (Twilio, MSG91, TextLocal).
- Rate limiting and retry logic for outbound SMS.
- OTP generation and standardized OTP message construction.
"""

import asyncio
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping

logger = logging.getLogger(__name__)

# Indian mobile number patterns
INDIAN_MOBILE_PATTERN = re.compile(r'^(\+91|91|0)?[6-9]\d{9}$')
INTERNATIONAL_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')

# SMS limits
MAX_SMS_LENGTH_GSM = 160
MAX_SMS_LENGTH_UNICODE = 70
MAX_CONCAT_PARTS = 6


class SMSError(Exception):
    """Base exception for SMS operations."""
    pass


class SMSValidationError(SMSError):
    """SMS validation error."""
    pass


class SMSDeliveryError(SMSError):
    """SMS delivery error."""
    pass


class SMSRateLimitError(SMSError):
    """SMS rate limit exceeded."""
    pass


class SMSStatus(Enum):
    """SMS delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SMSProvider(Enum):
    """Supported SMS providers."""
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    TEXTLOCAL = "textlocal"
    MSG91 = "msg91"
    GUPSHUP = "gupshup"
    FAST2SMS = "fast2sms"


@dataclass
class SMSMessage:
    """SMS message structure with validation."""
    phone: str
    message: str
    sender_id: str | None = None
    template_id: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1=high, 2=normal, 3=low
    schedule_at: datetime | None = None
    expire_at: datetime | None = None
    
    def __post_init__(self) -> None:
        """Validate SMS message after initialization."""
        self.phone = normalize_phone_number(self.phone)
        
        if not is_valid_phone_number(self.phone):
            raise SMSValidationError(f"Invalid phone number: {self.phone}")
        
        if not self.message or not self.message.strip():
            raise SMSValidationError("SMS message cannot be empty")
        
        # Validate message length
        if len(self.message) > MAX_SMS_LENGTH_GSM * MAX_CONCAT_PARTS:
            raise SMSValidationError(
                f"SMS message too long. Maximum {MAX_SMS_LENGTH_GSM * MAX_CONCAT_PARTS} characters allowed"
            )
        
        # Validate priority
        if not isinstance(self.priority, int) or not 1 <= self.priority <= 3:
            raise SMSValidationError("Priority must be 1 (high), 2 (normal), or 3 (low)")
        
        # Validate schedule time
        if self.schedule_at and self.schedule_at < datetime.now():
            raise SMSValidationError("Schedule time cannot be in the past")
        
        # Validate expiry
        if self.expire_at and self.expire_at < datetime.now():
            raise SMSValidationError("Expiry time cannot be in the past")
        
        if self.schedule_at and self.expire_at and self.schedule_at >= self.expire_at:
            raise SMSValidationError("Schedule time must be before expiry time")


@dataclass
class SMSResult:
    """Result of SMS sending operation."""
    success: bool
    message_id: str | None = None
    status: SMSStatus = SMSStatus.PENDING
    error: str | None = None
    cost: float | None = None
    parts: int = 1
    provider: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SMSConfig:
    """SMS provider configuration."""
    provider: SMSProvider
    api_key: str
    api_secret: str | None = None
    sender_id: str | None = None
    base_url: str | None = None
    webhook_url: str | None = None
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    
    @classmethod
    def from_env(cls, provider: SMSProvider | str | None = None) -> SMSConfig:
        """Create SMS config from environment variables."""
        if isinstance(provider, str):
            provider = SMSProvider(provider)
        elif provider is None:
            provider = SMSProvider(os.getenv("SMS_PROVIDER", "twilio"))
        
        return cls(
            provider=provider,
            api_key=os.getenv("SMS_API_KEY", ""),
            api_secret=os.getenv("SMS_API_SECRET"),
            sender_id=os.getenv("SMS_SENDER_ID"),
            base_url=os.getenv("SMS_BASE_URL"),
            webhook_url=os.getenv("SMS_WEBHOOK_URL"),
            rate_limit_per_minute=int(os.getenv("SMS_RATE_LIMIT_PER_MINUTE", "100")),
            rate_limit_per_hour=int(os.getenv("SMS_RATE_LIMIT_PER_HOUR", "1000")),
            rate_limit_per_day=int(os.getenv("SMS_RATE_LIMIT_PER_DAY", "10000")),
            retry_attempts=int(os.getenv("SMS_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("SMS_RETRY_DELAY", "1.0")),
            timeout=int(os.getenv("SMS_TIMEOUT", "30")),
        )


class SMSProviderInterface(ABC):
    """Interface for SMS providers."""
    
    @abstractmethod
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send SMS message."""
        pass
    
    @abstractmethod
    async def send_sms_async(self, message: SMSMessage) -> SMSResult:
        """Send SMS message asynchronously."""
        pass
    
    @abstractmethod
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get delivery status of sent message."""
        pass
    
    @abstractmethod
    def get_balance(self) -> float | None:
        """Get account balance if supported."""
        pass


class TwilioProvider(SMSProviderInterface):
    """Twilio SMS provider implementation."""
    
    def __init__(self, config: SMSConfig):
        self.config = config
        try:
            from twilio.rest import Client
            self.client = Client(config.api_key, config.api_secret)
        except ImportError:
            raise SMSError("Twilio SDK not installed. Install with: pip install twilio")
        except Exception as e:
            raise SMSError(f"Failed to initialize Twilio client: {e}")
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send SMS via Twilio."""
        try:
            response = self.client.messages.create(
                body=message.message,
                from_=message.sender_id or self.config.sender_id,
                to=message.phone
            )
            
            return SMSResult(
                success=True,
                message_id=response.sid,
                status=SMSStatus.SENT,
                provider="twilio",
                parts=response.num_segments or 1
            )
            
        except Exception as e:
            logger.error(f"Twilio SMS failed: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                provider="twilio"
            )
    
    async def send_sms_async(self, message: SMSMessage) -> SMSResult:
        """Send SMS asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_sms, message)
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get delivery status from Twilio."""
        try:
            message = self.client.messages(message_id).fetch()
            status_map = {
                'queued': SMSStatus.PENDING,
                'sending': SMSStatus.PENDING,
                'sent': SMSStatus.SENT,
                'delivered': SMSStatus.DELIVERED,
                'failed': SMSStatus.FAILED,
                'undelivered': SMSStatus.FAILED,
            }
            return status_map.get(message.status, SMSStatus.PENDING)
        except Exception as e:
            logger.error(f"Failed to get Twilio delivery status: {e}")
            return SMSStatus.PENDING
    
    def get_balance(self) -> float | None:
        """Get Twilio account balance."""
        try:
            account = self.client.api.accounts(self.client.account_sid).fetch()
            return float(account.balance)
        except Exception as e:
            logger.error(f"Failed to get Twilio balance: {e}")
            return None


class MSG91Provider(SMSProviderInterface):
    """MSG91 SMS provider (popular in India)."""
    
    def __init__(self, config: SMSConfig):
        self.config = config
        self.base_url = config.base_url or "https://api.msg91.com/api"
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send SMS via MSG91."""
        try:
            import requests
            
            url = f"{self.base_url}/sendhttp.php"
            params = {
                'authkey': self.config.api_key,
                'mobiles': message.phone,
                'message': message.message,
                'sender': message.sender_id or self.config.sender_id,
                'route': '4',  # Transactional route
                'response': 'json'
            }
            
            response = requests.get(url, params=params, timeout=self.config.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('type') == 'success':
                return SMSResult(
                    success=True,
                    message_id=data.get('message', 'Unknown'),
                    status=SMSStatus.SENT,
                    provider="msg91"
                )
            else:
                return SMSResult(
                    success=False,
                    error=data.get('message', 'Unknown error'),
                    provider="msg91"
                )
                
        except Exception as e:
            logger.error(f"MSG91 SMS failed: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                provider="msg91"
            )
    
    async def send_sms_async(self, message: SMSMessage) -> SMSResult:
        """Send SMS asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_sms, message)
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get delivery status from MSG91."""
        # MSG91 delivery status implementation placeholder
        return SMSStatus.PENDING
    
    def get_balance(self) -> float | None:
        """Get MSG91 balance."""
        try:
            import requests
            
            url = f"{self.base_url}/balance.php"
            params = {
                'authkey': self.config.api_key,
                'type': '4'
            }
            
            response = requests.get(url, params=params, timeout=self.config.timeout)
            data = response.json()
            
            return float(data.get('balance', 0))
            
        except Exception as e:
            logger.error(f"Failed to get MSG91 balance: {e}")
            return None


class TextLocalProvider(SMSProviderInterface):
    """TextLocal SMS provider (popular in India)."""
    
    def __init__(self, config: SMSConfig):
        self.config = config
        self.base_url = config.base_url or "https://api.textlocal.in"
    
    def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send SMS via TextLocal."""
        try:
            import requests
            
            url = f"{self.base_url}/send/"
            
            data = {
                'apikey': self.config.api_key,
                'numbers': message.phone,
                'message': message.message,
                'sender': message.sender_id or self.config.sender_id
            }
            
            response = requests.post(url, data=data, timeout=self.config.timeout)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('status') == 'success':
                return SMSResult(
                    success=True,
                    message_id=str(result.get('messages', [{}])[0].get('id', 'Unknown')),
                    status=SMSStatus.SENT,
                    provider="textlocal",
                    cost=result.get('cost')
                )
            else:
                return SMSResult(
                    success=False,
                    error='; '.join([error.get('message', 'Unknown') for error in result.get('errors', [])]),
                    provider="textlocal"
                )
                
        except Exception as e:
            logger.error(f"TextLocal SMS failed: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                provider="textlocal"
            )
    
    async def send_sms_async(self, message: SMSMessage) -> SMSResult:
        """Send SMS asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_sms, message)
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get delivery status from TextLocal."""
        return SMSStatus.PENDING
    
    def get_balance(self) -> float | None:
        """Get TextLocal balance."""
        try:
            import requests
            
            url = f"{self.base_url}/balance/"
            data = {'apikey': self.config.api_key}
            
            response = requests.post(url, data=data, timeout=self.config.timeout)
            result = response.json()
            
            return float(result.get('balance', {}).get('sms', 0))
            
        except Exception as e:
            logger.error(f"Failed to get TextLocal balance: {e}")
            return None


class RateLimiter:
    """Simple rate limiter for SMS sending based on sliding time windows."""
    
    def __init__(self, per_minute: int = 100, per_hour: int = 1000, per_day: int = 10000):
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_day = per_day
        self.minute_requests: List[float] = []
        self.hour_requests: List[float] = []
        self.day_requests: List[float] = []
    
    def can_send(self) -> bool:
        """Check if we can send SMS based on rate limits."""
        now = time.time()
        
        # Clean old entries
        self.minute_requests = [t for t in self.minute_requests if now - t < 60]
        self.hour_requests = [t for t in self.hour_requests if now - t < 3600]
        self.day_requests = [t for t in self.day_requests if now - t < 86400]
        
        # Check limits
        if len(self.minute_requests) >= self.per_minute:
            return False
        if len(self.hour_requests) >= self.per_hour:
            return False
        if len(self.day_requests) >= self.per_day:
            return False
        
        return True
    
    def record_request(self) -> None:
        """Record a request timestamp."""
        now = time.time()
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.day_requests.append(now)


class SMSService:
    """Main SMS service with multiple provider support."""
    
    def __init__(self, config: SMSConfig | None = None):
        if config is None:
            config = SMSConfig.from_env()
        
        self.config = config
        self.provider = self._create_provider(config)
        self.rate_limiter = RateLimiter(
            config.rate_limit_per_minute,
            config.rate_limit_per_hour,
            config.rate_limit_per_day
        )
    
    def _create_provider(self, config: SMSConfig) -> SMSProviderInterface:
        """Create SMS provider instance."""
        providers: Dict[SMSProvider, type[SMSProviderInterface]] = {
            SMSProvider.TWILIO: TwilioProvider,
            SMSProvider.MSG91: MSG91Provider,
            SMSProvider.TEXTLOCAL: TextLocalProvider,
            # Add other providers as needed
        }
        
        provider_class = providers.get(config.provider)
        if not provider_class:
            raise SMSError(f"Unsupported SMS provider: {config.provider}")
        
        return provider_class(config)
    
    def send_sms(
        self,
        phone: str,
        message: str,
        *,
        sender_id: str | None = None,
        template_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        priority: int = 2,
        schedule_at: datetime | None = None
    ) -> SMSResult:
        """Send SMS with rate limiting and retry logic."""
        try:
            # Check rate limits
            if not self.rate_limiter.can_send():
                raise SMSRateLimitError("Rate limit exceeded")
            
            # Create SMS message
            sms_message = SMSMessage(
                phone=phone,
                message=message,
                sender_id=sender_id,
                template_id=template_id,
                metadata=dict(metadata or {}),
                priority=priority,
                schedule_at=schedule_at
            )
            
            # Retry logic
            last_error: str | None = None
            for attempt in range(self.config.retry_attempts):
                try:
                    result = self.provider.send_sms(sms_message)
                    
                    if result.success:
                        self.rate_limiter.record_request()
                        logger.info(f"SMS sent successfully to {phone}: {result.message_id}")
                        return result
                    else:
                        last_error = result.error
                        
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"SMS attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
            
            # All attempts failed
            logger.error(f"SMS failed after {self.config.retry_attempts} attempts: {last_error}")
            return SMSResult(
                success=False,
                error=last_error or "Unknown error",
                provider=self.config.provider.value
            )
            
        except SMSRateLimitError:
            raise
        except Exception as e:
            logger.error(f"SMS service error: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                provider=self.config.provider.value
            )
    
    async def send_sms_async(
        self,
        phone: str,
        message: str,
        *,
        sender_id: str | None = None,
        template_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        priority: int = 2,
        schedule_at: datetime | None = None
    ) -> SMSResult:
        """Send SMS asynchronously."""
        try:
            # Check rate limits
            if not self.rate_limiter.can_send():
                raise SMSRateLimitError("Rate limit exceeded")
            
            # Create SMS message
            sms_message = SMSMessage(
                phone=phone,
                message=message,
                sender_id=sender_id,
                template_id=template_id,
                metadata=dict(metadata or {}),
                priority=priority,
                schedule_at=schedule_at
            )
            
            # Async retry logic
            last_error: str | None = None
            for attempt in range(self.config.retry_attempts):
                try:
                    result = await self.provider.send_sms_async(sms_message)
                    
                    if result.success:
                        self.rate_limiter.record_request()
                        logger.info(f"SMS sent successfully to {phone}: {result.message_id}")
                        return result
                    else:
                        last_error = result.error
                        
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Async SMS attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
            
            # All attempts failed
            logger.error(f"Async SMS failed after {self.config.retry_attempts} attempts: {last_error}")
            return SMSResult(
                success=False,
                error=last_error or "Unknown error",
                provider=self.config.provider.value
            )
            
        except SMSRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Async SMS service error: {e}")
            return SMSResult(
                success=False,
                error=str(e),
                provider=self.config.provider.value
            )
    
    def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get delivery status of sent message."""
        try:
            return self.provider.get_delivery_status(message_id)
        except Exception as e:
            logger.error(f"Failed to get delivery status: {e}")
            return SMSStatus.PENDING
    
    def get_balance(self) -> float | None:
        """Get account balance."""
        try:
            return self.provider.get_balance()
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None


# Utility functions
def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to E.164 format.
    
    For Indian numbers: +91XXXXXXXXXX
    For international: +CCXXXXXXXXXX (must start with '+').
    """
    if not isinstance(phone, str):
        raise SMSValidationError("Phone number must be a string")
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    if not cleaned:
        raise SMSValidationError("Phone number cannot be empty")
    
    # Handle Indian numbers
    if INDIAN_MOBILE_PATTERN.match(cleaned):
        # Remove leading 0 if present
        if cleaned.startswith('0'):
            cleaned = cleaned[1:]
        
        # Add country code if missing
        if cleaned.startswith('91'):
            cleaned = '+' + cleaned
        elif not cleaned.startswith('+91'):
            cleaned = '+91' + cleaned
        
        return cleaned
    
    # Handle international numbers
    if not cleaned.startswith('+'):
        raise SMSValidationError("International numbers must start with +")
    
    if INTERNATIONAL_PATTERN.match(cleaned):
        return cleaned
    
    raise SMSValidationError(f"Invalid phone number format: {phone}")


def is_valid_phone_number(phone: str) -> bool:
    """Check if phone number is valid."""
    try:
        normalized = normalize_phone_number(phone)
        return bool(INDIAN_MOBILE_PATTERN.match(normalized) or INTERNATIONAL_PATTERN.match(normalized))
    except SMSValidationError:
        return False


def is_valid_indian_mobile(phone: str) -> bool:
    """Check if phone number is a valid Indian mobile number."""
    try:
        normalized = normalize_phone_number(phone)
        return bool(INDIAN_MOBILE_PATTERN.match(normalized))
    except SMSValidationError:
        return False


def calculate_sms_parts(message: str) -> int:
    """Calculate number of SMS parts required based on GSM/Unicode length."""
    # Check if message contains non-GSM characters
    gsm_chars = set(
        "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ "
        "!\"#¤%&'()*+,-./0123456789:;<=>?¡"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
        "abcdefghijklmnopqrstuvwxyzäöñüà"
    )
    
    if all(char in gsm_chars for char in message):
        # GSM 7-bit encoding
        if len(message) <= MAX_SMS_LENGTH_GSM:
            return 1
        else:
            return (len(message) + 152) // 153  # 153 chars per part for concatenated SMS
    else:
        # Unicode encoding
        if len(message) <= MAX_SMS_LENGTH_UNICODE:
            return 1
        else:
            return (len(message) + 66) // 67  # 67 chars per part for concatenated Unicode SMS


def generate_otp(length: int = 6) -> str:
    """Generate numeric OTP."""
    import secrets
    
    if not isinstance(length, int) or length < 4 or length > 10:
        raise SMSValidationError("OTP length must be between 4 and 10")
    
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def create_otp_message(otp: str, app_name: str = "App", expiry_minutes: int = 10) -> str:
    """Create standardized OTP message."""
    if not otp or not isinstance(otp, str):
        raise SMSValidationError("OTP must be a non-empty string")
    
    if not app_name or not isinstance(app_name, str):
        raise SMSValidationError("App name must be a non-empty string")
    
    return f"Your {app_name} verification code is {otp}. Valid for {expiry_minutes} minutes. Do not share with anyone."


# Default SMS service instance
_default_service: SMSService | None = None


def get_sms_service() -> SMSService:
    """Get default SMS service instance (singleton-style)."""
    global _default_service
    if _default_service is None:
        _default_service = SMSService()
    return _default_service


def send_sms(
    phone: str,
    message: str,
    *,
    sender_id: str | None = None,
    template_id: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> SMSResult:
    """Send SMS using default service."""
    service = get_sms_service()
    return service.send_sms(
        phone=phone,
        message=message,
        sender_id=sender_id,
        template_id=template_id,
        metadata=metadata
    )


async def send_sms_async(
    phone: str,
    message: str,
    *,
    sender_id: str | None = None,
    template_id: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> SMSResult:
    """Send SMS asynchronously using default service."""
    service = get_sms_service()
    return await service.send_sms_async(
        phone=phone,
        message=message,
        sender_id=sender_id,
        template_id=template_id,
        metadata=metadata
    )


def send_otp_sms(phone: str, otp_length: int = 6, app_name: str = "App") -> tuple[str, SMSResult]:
    """
    Send OTP SMS and return both OTP and result.
    
    Returns:
        tuple: (otp, sms_result)
    """
    try:
        otp = generate_otp(otp_length)
        message = create_otp_message(otp, app_name)
        
        result = send_sms(phone, message)
        return otp, result
        
    except Exception as e:
        logger.error(f"Failed to send OTP SMS: {e}")
        return "", SMSResult(success=False, error=str(e))


async def send_otp_sms_async(phone: str, otp_length: int = 6, app_name: str = "App") -> tuple[str, SMSResult]:
    """
    Send OTP SMS asynchronously and return both OTP and result.
    
    Returns:
        tuple: (otp, sms_result)
    """
    try:
        otp = generate_otp(otp_length)
        message = create_otp_message(otp, app_name)
        
        result = await send_sms_async(phone, message)
        return otp, result
        
    except Exception as e:
        logger.error(f"Failed to send OTP SMS: {e}")
        return "", SMSResult(success=False, error=str(e))