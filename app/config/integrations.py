"""
Third-party integration configurations for the hostel management system.
Manages connections to payment gateways, SMS providers, email services, etc.
"""

from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import httpx
import asyncio
import time
from dataclasses import dataclass

from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IntegrationType(Enum):
    """Types of integrations supported by the system"""
    PAYMENT = "payment"
    EMAIL = "email"
    SMS = "sms"
    OAUTH = "oauth"
    STORAGE = "storage"
    MAPS = "maps"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    CALENDAR = "calendar"

@dataclass
class IntegrationConfig:
    """Configuration for an integration"""
    name: str
    type: IntegrationType
    enabled: bool
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    sandbox: bool = True
    timeout_seconds: int = 30
    retries: int = 3
    additional_config: Dict[str, Any] = None
    health_check_url: Optional[str] = None

class IntegrationRegistry:
    """Registry for all integrations"""
    
    def __init__(self):
        self.integrations: Dict[str, IntegrationConfig] = {}
        self.clients: Dict[str, Any] = {}
    
    def register_integration(self, config: IntegrationConfig) -> bool:
        """Register an integration"""
        if config.name in self.integrations:
            logger.warning(f"Integration {config.name} already registered, updating")
            
        self.integrations[config.name] = config
        logger.info(f"Registered integration: {config.name} ({config.type.value})")
        return True
    
    def get_integration(self, name: str) -> Optional[IntegrationConfig]:
        """Get integration by name"""
        return self.integrations.get(name)
    
    def get_integrations_by_type(self, integration_type: IntegrationType) -> List[IntegrationConfig]:
        """Get all integrations of specific type"""
        return [
            config for config in self.integrations.values()
            if config.type == integration_type and config.enabled
        ]
    
    def get_client(self, integration_name: str):
        """Get or create integration client"""
        if integration_name in self.clients:
            return self.clients[integration_name]
        
        config = self.get_integration(integration_name)
        if not config:
            raise ValueError(f"Integration {integration_name} not registered")
        
        if not config.enabled:
            raise ValueError(f"Integration {integration_name} is disabled")
        
        # Create appropriate client based on integration type
        client = self._create_client(config)
        self.clients[integration_name] = client
        return client
    
    def _create_client(self, config: IntegrationConfig):
        """Create appropriate client for integration type"""
        if config.type == IntegrationType.PAYMENT:
            return self._create_payment_client(config)
        elif config.type == IntegrationType.EMAIL:
            return self._create_email_client(config)
        elif config.type == IntegrationType.SMS:
            return self._create_sms_client(config)
        elif config.type == IntegrationType.OAUTH:
            return self._create_oauth_client(config)
        elif config.type == IntegrationType.STORAGE:
            return self._create_storage_client(config)
        else:
            # Generic HTTP client for other integration types
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
            )
    
    def _create_payment_client(self, config: IntegrationConfig):
        """Create payment gateway client"""
        if config.name == "stripe":
            import stripe
            stripe.api_key = config.api_key
            stripe.api_version = "2023-08-16"
            return stripe
        elif config.name == "razorpay":
            import razorpay
            client = razorpay.Client(auth=(config.api_key, config.api_secret))
            return client
        elif config.name == "paypal":
            # Custom PayPal client using httpx
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                auth=(config.api_key, config.api_secret)
            )
        else:
            # Generic payment client
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
            )
    
    def _create_email_client(self, config: IntegrationConfig):
        """Create email client"""
        if config.name == "sendgrid":
            import sendgrid
            return sendgrid.SendGridAPIClient(config.api_key)
        elif config.name == "smtp":
            import smtplib
            smtp_config = config.additional_config or {}
            server = smtplib.SMTP(
                host=config.base_url or smtp_config.get("host", "localhost"),
                port=smtp_config.get("port", 25)
            )
            if smtp_config.get("tls", True):
                server.starttls()
            if config.api_key and config.api_secret:
                server.login(config.api_key, config.api_secret)
            return server
        else:
            # Generic email client
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
            )
    
    def _create_sms_client(self, config: IntegrationConfig):
        """Create SMS client"""
        if config.name == "twilio":
            from twilio.rest import Client
            return Client(config.api_key, config.api_secret)
        else:
            # Generic SMS client
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
            )
    
    def _create_oauth_client(self, config: IntegrationConfig):
        """Create OAuth client"""
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        return AsyncOAuth2Client(
            client_id=config.api_key,
            client_secret=config.api_secret,
            redirect_uri=config.additional_config.get("redirect_uri") if config.additional_config else None
        )
    
    def _create_storage_client(self, config: IntegrationConfig):
        """Create storage client"""
        if config.name == "s3":
            import boto3
            return boto3.client(
                's3',
                aws_access_key_id=config.api_key,
                aws_secret_access_key=config.api_secret,
                region_name=config.additional_config.get("region") if config.additional_config else None
            )
        elif config.name == "cloudinary":
            import cloudinary
            cloudinary.config(
                cloud_name=config.additional_config.get("cloud_name") if config.additional_config else None,
                api_key=config.api_key,
                api_secret=config.api_secret
            )
            return cloudinary
        else:
            # Generic storage client
            return httpx.AsyncClient(
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
            )
    
    async def check_integration_health(self, name: str) -> Dict[str, Any]:
        """Check if integration is healthy"""
        try:
            config = self.get_integration(name)
            if not config:
                return {"status": "error", "message": f"Integration {name} not found"}
            
            if not config.enabled:
                return {"status": "disabled", "message": f"Integration {name} is disabled"}
            
            if not config.health_check_url:
                return {"status": "unknown", "message": "No health check URL defined"}
            
            # Get client
            client = self.get_client(name)
            
            # Special handling for different integration types
            if config.type == IntegrationType.PAYMENT:
                if name == "stripe":
                    # Stripe-specific health check
                    try:
                        balance = client.Balance.retrieve()
                        return {"status": "healthy", "details": {"available": bool(balance)}}
                    except Exception as e:
                        return {"status": "error", "message": str(e)}
                else:
                    # Generic payment gateway health check
                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.get(
                            config.health_check_url,
                            timeout=config.timeout_seconds,
                            headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
                        )
                        return {
                            "status": "healthy" if response.status_code < 300 else "error",
                            "message": "OK" if response.status_code < 300 else f"Error: {response.status_code}",
                            "details": {"status_code": response.status_code}
                        }
            else:
                # Generic health check
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        config.health_check_url,
                        timeout=config.timeout_seconds
                    )
                    return {
                        "status": "healthy" if response.status_code < 300 else "error",
                        "message": "OK" if response.status_code < 300 else f"Error: {response.status_code}",
                        "details": {"status_code": response.status_code}
                    }
        except Exception as e:
            logger.error(f"Health check failed for integration {name}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def check_all_integrations(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all integrations"""
        results = {}
        
        for name in self.integrations:
            results[name] = await self.check_integration_health(name)
        
        return results

class WebhookManager:
    """Manage incoming and outgoing webhooks"""
    
    def __init__(self):
        self.webhook_handlers = {}
        self.webhook_subscriptions = {}
    
    def register_webhook_handler(self, webhook_type: str, handler: callable):
        """Register webhook handler"""
        if webhook_type not in self.webhook_handlers:
            self.webhook_handlers[webhook_type] = []
        
        self.webhook_handlers[webhook_type].append(handler)
        logger.info(f"Registered webhook handler for {webhook_type}")
    
    async def process_webhook(self, webhook_type: str, payload: Dict[str, Any]):
        """Process incoming webhook"""
        if webhook_type not in self.webhook_handlers:
            logger.warning(f"No handler registered for webhook type: {webhook_type}")
            return False
        
        handlers = self.webhook_handlers[webhook_type]
        results = []
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(payload)
                else:
                    result = handler(payload)
                results.append(result)
            except Exception as e:
                logger.error(f"Webhook handler error: {str(e)}")
                results.append(False)
        
        return all(results)
    
    def subscribe_to_webhook(self, provider: str, event_type: str, callback_url: str):
        """Subscribe to webhook from external provider"""
        key = f"{provider}:{event_type}"
        if key not in self.webhook_subscriptions:
            self.webhook_subscriptions[key] = []
        
        self.webhook_subscriptions[key].append(callback_url)
        logger.info(f"Subscribed to webhook: {key} -> {callback_url}")
    
    def validate_webhook_signature(self, provider: str, signature: str, payload: str, secret: str) -> bool:
        """Validate webhook signature"""
        if provider == "stripe":
            import stripe
            try:
                stripe.WebhookSignature.verify_header(
                    payload,
                    signature,
                    secret,
                    tolerance=300  # 5 minute tolerance
                )
                return True
            except stripe.error.SignatureVerificationError:
                return False
        elif provider == "razorpay":
            import hmac
            import hashlib
            generated_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(generated_signature, signature)
        else:
            # Generic HMAC-SHA256 validation
            import hmac
            import hashlib
            generated_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(generated_signature, signature)

# Initialize global registry
integration_registry = IntegrationRegistry()
webhook_manager = WebhookManager()

# Register default integrations based on settings
def register_default_integrations():
    """Register default integrations from settings"""
    
    # Stripe Payment Gateway
    if settings.PAYMENT_GATEWAY_API_KEY:
        integration_registry.register_integration(
            IntegrationConfig(
                name="stripe",
                type=IntegrationType.PAYMENT,
                enabled=True,
                api_key=settings.PAYMENT_GATEWAY_API_KEY,
                api_secret=settings.PAYMENT_GATEWAY_SECRET,
                base_url="https://api.stripe.com/v1",
                sandbox=settings.PAYMENT_GATEWAY_MODE == "sandbox",
                health_check_url="https://api.stripe.com/v1/health",
                additional_config={
                    "webhook_secret": settings.PAYMENT_GATEWAY_SECRET,
                    "mode": settings.PAYMENT_GATEWAY_MODE
                }
            )
        )
    
    # Email integration
    if settings.SMTP_HOST:
        integration_registry.register_integration(
            IntegrationConfig(
                name="smtp",
                type=IntegrationType.EMAIL,
                enabled=True,
                api_key=settings.SMTP_USER,
                api_secret=settings.SMTP_PASSWORD,
                base_url=settings.SMTP_HOST,
                additional_config={
                    "port": settings.SMTP_PORT,
                    "tls": settings.SMTP_TLS,
                    "from_name": settings.EMAIL_FROM_NAME,
                    "from_email": settings.EMAIL_FROM_ADDRESS
                }
            )
        )
    
    # SMS integration
    if settings.SMS_API_KEY:
        integration_registry.register_integration(
            IntegrationConfig(
                name=settings.SMS_PROVIDER or "generic",
                type=IntegrationType.SMS,
                enabled=True,
                api_key=settings.SMS_API_KEY,
                additional_config={
                    "from_number": settings.SMS_FROM_NUMBER
                }
            )
        )
    
    # Google OAuth integration
    if settings.GOOGLE_CLIENT_ID:
        integration_registry.register_integration(
            IntegrationConfig(
                name="google_oauth",
                type=IntegrationType.OAUTH,
                enabled=True,
                api_key=settings.GOOGLE_CLIENT_ID,
                api_secret=settings.GOOGLE_CLIENT_SECRET,
                base_url="https://accounts.google.com",
                additional_config={
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "scope": "email profile"
                }
            )
        )
    
    logger.info(f"Registered {len(integration_registry.integrations)} default integrations")

# Register integrations on module load
register_default_integrations()

# API clients for common third-party integrations
class PaymentGatewayClient:
    """Client for payment gateway operations"""
    
    def __init__(self, gateway_name: str = "stripe"):
        self.gateway_name = gateway_name
        self.client = None
    
    async def initialize(self):
        """Initialize payment gateway client"""
        self.client = integration_registry.get_client(self.gateway_name)
    
    async def create_payment_intent(self, amount: int, currency: str, customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a payment intent"""
        if not self.client:
            await self.initialize()
        
        if self.gateway_name == "stripe":
            params = {
                "amount": amount,
                "currency": currency,
                "automatic_payment_methods": {"enabled": True}
            }
            
            if customer_id:
                params["customer"] = customer_id
                
            try:
                intent = self.client.PaymentIntent.create(**params)
                return {
                    "id": intent.id,
                    "client_secret": intent.client_secret,
                    "amount": intent.amount,
                    "currency": intent.currency,
                    "status": intent.status,
                }
            except Exception as e:
                logger.error(f"Payment intent creation error: {str(e)}")
                raise ValueError(f"Failed to create payment: {str(e)}")
        else:
            # Generic payment gateway implementation
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{integration_registry.get_integration(self.gateway_name).base_url}/payment_intents",
                    json={
                        "amount": amount,
                        "currency": currency,
                        "customer_id": customer_id
                    },
                    headers={"Authorization": f"Bearer {integration_registry.get_integration(self.gateway_name).api_key}"}
                )
                
                if response.status_code >= 300:
                    logger.error(f"Payment intent creation error: {response.text}")
                    raise ValueError(f"Failed to create payment: {response.status_code}")
                
                return response.json()
    
    async def process_refund(self, payment_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Process a refund"""
        if not self.client:
            await self.initialize()
        
        if self.gateway_name == "stripe":
            params = {"payment_intent": payment_id}
            if amount:
                params["amount"] = amount
                
            try:
                refund = self.client.Refund.create(**params)
                return {
                    "id": refund.id,
                    "amount": refund.amount,
                    "currency": refund.currency,
                    "status": refund.status,
                    "payment_intent": refund.payment_intent
                }
            except Exception as e:
                logger.error(f"Refund processing error: {str(e)}")
                raise ValueError(f"Failed to process refund: {str(e)}")
        else:
            # Generic payment gateway implementation
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{integration_registry.get_integration(self.gateway_name).base_url}/refunds",
                    json={
                        "payment_id": payment_id,
                        "amount": amount
                    },
                    headers={"Authorization": f"Bearer {integration_registry.get_integration(self.gateway_name).api_key}"}
                )
                
                if response.status_code >= 300:
                    logger.error(f"Refund processing error: {response.text}")
                    raise ValueError(f"Failed to process refund: {response.status_code}")
                
                return response.json()

class EmailClient:
    """Client for email operations"""
    
    def __init__(self, provider_name: str = "smtp"):
        self.provider_name = provider_name
        self.client = None
        self.config = None
    
    async def initialize(self):
        """Initialize email client"""
        self.client = integration_registry.get_client(self.provider_name)
        self.config = integration_registry.get_integration(self.provider_name)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: List[Dict[str, Any]] = None
    ) -> bool:
        """Send an email"""
        if not self.client:
            await self.initialize()
        
        try:
            if self.provider_name == "smtp":
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                
                # Create message
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = from_email or self.config.additional_config.get("from_email")
                msg['To'] = to_email
                
                if reply_to:
                    msg['Reply-To'] = reply_to
                
                # Attach parts
                if body_text:
                    msg.attach(MIMEText(body_text, 'plain'))
                
                msg.attach(MIMEText(body_html, 'html'))
                
                # Add attachments
                if attachments:
                    from email.mime.application import MIMEApplication
                    
                    for attachment in attachments:
                        part = MIMEApplication(attachment['data'])
                        part.add_header(
                            'Content-Disposition', 
                            f'attachment; filename="{attachment["filename"]}"'
                        )
                        msg.attach(part)
                
                # Send email
                self.client.send_message(msg)
                return True
            
            elif self.provider_name == "sendgrid":
                from_email = from_email or self.config.additional_config.get("from_email")
                
                message = {
                    "personalizations": [{
                        "to": [{"email": to_email}],
                        "subject": subject
                    }],
                    "from": {"email": from_email},
                    "content": []
                }
                
                if body_text:
                    message["content"].append({
                        "type": "text/plain",
                        "value": body_text
                    })
                
                message["content"].append({
                    "type": "text/html",
                    "value": body_html
                })
                
                if reply_to:
                    message["reply_to"] = {"email": reply_to}
                
                # Add attachments
                if attachments:
                    message["attachments"] = []
                    import base64
                    
                    for attachment in attachments:
                        message["attachments"].append({
                            "content": base64.b64encode(attachment['data']).decode(),
                            "filename": attachment["filename"],
                            "type": attachment.get("content_type", "application/octet-stream"),
                            "disposition": "attachment"
                        })
                
                response = self.client.send(message)
                return response.status_code < 300
            
            else:
                # Generic email client implementation
                async with httpx.AsyncClient() as http_client:
                    from_email = from_email or self.config.additional_config.get("from_email")
                    
                    response = await http_client.post(
                        f"{self.config.base_url}/send",
                        json={
                            "to": to_email,
                            "from": from_email,
                            "subject": subject,
                            "html": body_html,
                            "text": body_text,
                            "reply_to": reply_to
                        },
                        headers={"Authorization": f"Bearer {self.config.api_key}"}
                    )
                    
                    return response.status_code < 300
                
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False

class SMSClient:
    """Client for SMS operations"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.client = None
        self.config = None
    
    async def initialize(self):
        """Initialize SMS client"""
        self.client = integration_registry.get_client(self.provider_name)
        self.config = integration_registry.get_integration(self.provider_name)
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None
    ) -> bool:
        """Send an SMS"""
        if not self.client:
            await self.initialize()
        
        try:
            from_number = from_number or self.config.additional_config.get("from_number")
            
            if self.provider_name == "twilio":
                response = self.client.messages.create(
                    body=message,
                    from_=from_number,
                    to=to_number
                )
                return response.status == 'sent'
            else:
                # Generic SMS client implementation
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.post(
                        f"{self.config.base_url}/messages",
                        json={
                            "to": to_number,
                            "from": from_number,
                            "message": message
                        },
                        headers={"Authorization": f"Bearer {self.config.api_key}"}
                    )
                    
                    return response.status_code < 300
                
        except Exception as e:
            logger.error(f"SMS sending error: {str(e)}")
            return False

# Storage client for file operations
class StorageClient:
    """Client for storage operations"""
    
    def __init__(self, provider_name: str = "s3"):
        self.provider_name = provider_name
        self.client = None
        self.config = None
    
    async def initialize(self):
        """Initialize storage client"""
        self.client = integration_registry.get_client(self.provider_name)
        self.config = integration_registry.get_integration(self.provider_name)
    
    async def upload_file(
        self,
        file_data: bytes,
        destination_path: str,
        content_type: Optional[str] = None,
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Upload a file to storage"""
        if not self.client:
            await self.initialize()
        
        try:
            if self.provider_name == "s3":
                bucket = self.config.additional_config.get("bucket", "hostel-management")
                
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                    
                if metadata:
                    extra_args["Metadata"] = metadata
                    
                if public:
                    extra_args["ACL"] = "public-read"
                
                # Upload to S3
                self.client.put_object(
                    Bucket=bucket,
                    Key=destination_path,
                    Body=file_data,
                    **extra_args
                )
                
                # Generate URL
                url = f"https://{bucket}.s3.amazonaws.com/{destination_path}"
                if not public:
                    # Generate presigned URL
                    url = self.client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket, 'Key': destination_path},
                        ExpiresIn=3600  # 1 hour
                    )
                
                return {
                    "url": url,
                    "path": destination_path,
                    "bucket": bucket,
                    "content_type": content_type,
                    "public": public
                }
                
            elif self.provider_name == "cloudinary":
                import cloudinary.uploader
                
                # Upload options
                options = {
                    "resource_type": "auto",
                    "public_id": destination_path
                }
                
                if metadata:
                    options["context"] = metadata
                    
                if not public:
                    options["type"] = "private"
                
                # Upload to Cloudinary
                result = cloudinary.uploader.upload(file_data, **options)
                
                return {
                    "url": result["secure_url"],
                    "path": result["public_id"],
                    "content_type": result["resource_type"],
                    "public": public,
                    "version": result["version"]
                }
                
            else:
                # Generic storage client implementation
                import aiofiles
                import os
                
                # Ensure upload directory exists
                upload_dir = settings.UPLOAD_DIR
                os.makedirs(os.path.dirname(os.path.join(upload_dir, destination_path)), exist_ok=True)
                
                # Write file
                async with aiofiles.open(os.path.join(upload_dir, destination_path), "wb") as f:
                    await f.write(file_data)
                
                # Generate URL
                url = f"/uploads/{destination_path}"
                
                return {
                    "url": url,
                    "path": destination_path,
                    "content_type": content_type,
                    "public": public
                }
                
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            raise ValueError(f"Failed to upload file: {str(e)}")
    
    async def get_file(self, file_path: str) -> bytes:
        """Get file from storage"""
        if not self.client:
            await self.initialize()
        
        try:
            if self.provider_name == "s3":
                bucket = self.config.additional_config.get("bucket", "hostel-management")
                
                response = self.client.get_object(
                    Bucket=bucket,
                    Key=file_path
                )
                
                return response['Body'].read()
                
            elif self.provider_name == "cloudinary":
                import cloudinary.api
                
                # Get file URL
                result = cloudinary.api.resource(file_path)
                file_url = result["secure_url"]
                
                # Download file
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(file_url)
                    return response.content
                
            else:
                # Generic storage client implementation
                import aiofiles
                
                upload_dir = settings.UPLOAD_DIR
                async with aiofiles.open(os.path.join(upload_dir, file_path), "rb") as f:
                    return await f.read()
                
        except Exception as e:
            logger.error(f"File download error: {str(e)}")
            raise ValueError(f"Failed to download file: {str(e)}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        if not self.client:
            await self.initialize()
        
        try:
            if self.provider_name == "s3":
                bucket = self.config.additional_config.get("bucket", "hostel-management")
                
                self.client.delete_object(
                    Bucket=bucket,
                    Key=file_path
                )
                
                return True
                
            elif self.provider_name == "cloudinary":
                import cloudinary.uploader
                
                # Delete file
                result = cloudinary.uploader.destroy(file_path)
                return result["result"] == "ok"
                
            else:
                # Generic storage client implementation
                import os
                
                upload_dir = settings.UPLOAD_DIR
                os.remove(os.path.join(upload_dir, file_path))
                return True
                
        except Exception as e:
            logger.error(f"File deletion error: {str(e)}")
            return False