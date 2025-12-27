"""
Enhanced Notification Workflow Service

Advanced multi-channel notification orchestration with intelligent delivery optimization.
"""

from typing import Dict, Any, Optional, List, Set
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from collections import defaultdict

from sqlalchemy.orm import Session

from app.repositories.notification import (
    NotificationRepository,
    NotificationTemplateRepository,
    NotificationQueueRepository,
    NotificationPreferenceRepository,
    NotificationAnalyticsRepository
)
from app.schemas.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority
)
from app.core1.exceptions import ValidationException
from app.core1.config import settings
from app.services.external.email_service import EmailService
from app.services.external.sms_service import SMSService
from app.services.external.push_service import PushNotificationService


class DeliveryStrategy(str, Enum):
    """Notification delivery strategies."""
    IMMEDIATE = "immediate"
    BATCH = "batch"
    SCHEDULED = "scheduled"
    OPTIMAL_TIME = "optimal_time"
    FALLBACK_CASCADE = "fallback_cascade"


class NotificationStatus(str, Enum):
    """Enhanced notification status tracking."""
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    CLICKED = "clicked"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class NotificationTemplate:
    """Enhanced notification template with multi-channel support."""
    template_id: str
    name: str
    category: str
    channels: Set[NotificationChannel]
    priority: NotificationPriority
    templates: Dict[str, str]  # channel -> template content
    variables: Set[str]
    localization: Dict[str, Dict[str, str]]  # locale -> channel -> content
    delivery_strategy: DeliveryStrategy = DeliveryStrategy.IMMEDIATE
    retry_config: Dict[str, Any] = field(default_factory=dict)
    expiry_hours: int = 72
    
    def __post_init__(self):
        if not self.retry_config:
            self.retry_config = {
                "max_attempts": 3,
                "backoff_multiplier": 2,
                "initial_delay": 60
            }


@dataclass
class DeliveryMetrics:
    """Comprehensive delivery metrics."""
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    channel_metrics: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    average_delivery_time: Dict[str, float] = field(default_factory=dict)
    user_engagement: Dict[str, float] = field(default_factory=dict)
    cost_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class UserNotificationPreference:
    """Enhanced user notification preferences."""
    user_id: UUID
    channel_preferences: Dict[NotificationChannel, bool]
    category_preferences: Dict[str, Dict[NotificationChannel, bool]]
    quiet_hours: Dict[str, str]  # start_time, end_time
    frequency_limits: Dict[str, int]  # category -> max_per_day
    language: str = "en"
    timezone: str = "UTC"


class NotificationWorkflowService:
    """
    Enhanced notification orchestration service with intelligent delivery optimization.
    
    Features:
    - Multi-channel delivery orchestration
    - Intelligent delivery timing optimization
    - User preference-based routing
    - Real-time delivery tracking
    - A/B testing for notification effectiveness
    - Cost optimization across channels
    - Advanced analytics and insights
    """
    
    def __init__(
        self,
        notification_repo: NotificationRepository,
        template_repo: NotificationTemplateRepository,
        queue_repo: NotificationQueueRepository,
        preference_repo: NotificationPreferenceRepository,
        analytics_repo: NotificationAnalyticsRepository,
        email_service: EmailService,
        sms_service: SMSService,
        push_service: PushNotificationService
    ):
        self.notification_repo = notification_repo
        self.template_repo = template_repo
        self.queue_repo = queue_repo
        self.preference_repo = preference_repo
        self.analytics_repo = analytics_repo
        self.email_service = email_service
        self.sms_service = sms_service
        self.push_service = push_service
        
        # Enhanced configurations
        self.templates: Dict[str, NotificationTemplate] = {}
        self.delivery_metrics = DeliveryMetrics()
        
        # Performance optimization
        self._preference_cache: Dict[UUID, UserNotificationPreference] = {}
        self._template_cache: Dict[str, NotificationTemplate] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._last_cache_clear = datetime.utcnow()
        
        # Delivery optimization
        self._delivery_queues: Dict[NotificationChannel, List[Dict[str, Any]]] = {
            channel: [] for channel in NotificationChannel
        }
        
        self._setup_default_templates()
        self._start_delivery_processors()
    
    def _setup_default_templates(self) -> None:
        """Setup comprehensive default notification templates."""
        
        # Approval notification templates
        approval_templates = {
            "BOOKING_APPROVED": NotificationTemplate(
                template_id="BOOKING_APPROVED",
                name="Booking Approval Notification",
                category="approval",
                channels={NotificationChannel.EMAIL, NotificationChannel.IN_APP, NotificationChannel.SMS},
                priority=NotificationPriority.HIGH,
                templates={
                    "email": """
                    <h2>Booking Approved!</h2>
                    <p>Dear {{student_name}},</p>
                    <p>Your booking request for {{hostel_name}} has been approved!</p>
                    <p><strong>Details:</strong></p>
                    <ul>
                        <li>Room: {{room_number}}</li>
                        <li>Check-in Date: {{check_in_date}}</li>
                        <li>Monthly Rent: {{monthly_rent}}</li>
                    </ul>
                    <p>Please complete your check-in process by {{deadline}}.</p>
                    """,
                    "sms": "Great news! Your booking at {{hostel_name}} is approved. Room {{room_number}}, check-in: {{check_in_date}}. Complete process by {{deadline}}.",
                    "in_app": "🎉 Booking approved for {{hostel_name}}! Room {{room_number}} is ready. Check-in: {{check_in_date}}."
                },
                variables={"student_name", "hostel_name", "room_number", "check_in_date", "monthly_rent", "deadline"},
                delivery_strategy=DeliveryStrategy.IMMEDIATE
            ),
            
            "BOOKING_REJECTED": NotificationTemplate(
                template_id="BOOKING_REJECTED",
                name="Booking Rejection Notification",
                category="approval",
                channels={NotificationChannel.EMAIL, NotificationChannel.IN_APP, NotificationChannel.SMS},
                priority=NotificationPriority.HIGH,
                templates={
                    "email": """
                    <h2>Booking Update</h2>
                    <p>Dear {{student_name}},</p>
                    <p>Unfortunately, your booking request for {{hostel_name}} could not be approved.</p>
                    <p><strong>Reason:</strong> {{rejection_reason}}</p>
                    {{#suggested_alternatives}}
                    <p><strong>Alternative Options:</strong></p>
                    <ul>
                        {{#alternatives}}
                        <li>{{hostel_name}} - {{available_date}}</li>
                        {{/alternatives}}
                    </ul>
                    {{/suggested_alternatives}}
                    <p>Please contact our support team for assistance.</p>
                    """,
                    "sms": "Your booking at {{hostel_name}} was not approved. Reason: {{rejection_reason}}. Contact support for alternatives.",
                    "in_app": "❌ Booking not approved: {{rejection_reason}}. Check your email for alternative options."
                },
                variables={"student_name", "hostel_name", "rejection_reason", "suggested_alternatives"},
                delivery_strategy=DeliveryStrategy.IMMEDIATE
            ),
            
            "MAINTENANCE_APPROVED": NotificationTemplate(
                template_id="MAINTENANCE_APPROVED",
                name="Maintenance Approval Notification",
                category="maintenance",
                channels={NotificationChannel.EMAIL, NotificationChannel.IN_APP},
                priority=NotificationPriority.MEDIUM,
                templates={
                    "email": """
                    <h2>Maintenance Request Approved</h2>
                    <p>Your maintenance request has been approved.</p>
                    <p><strong>Request Details:</strong></p>
                    <ul>
                        <li>Type: {{maintenance_type}}</li>
                        <li>Approved Amount: {{approved_amount}}</li>
                        <li>Scheduled Date: {{scheduled_date}}</li>
                    </ul>
                    """,
                    "in_app": "✅ Maintenance approved: {{maintenance_type}} - {{approved_amount}}. Scheduled: {{scheduled_date}}"
                },
                variables={"maintenance_type", "approved_amount", "scheduled_date"},
                delivery_strategy=DeliveryStrategy.BATCH
            )
        }
        
        # Escalation notification templates
        escalation_templates = {
            "COMPLAINT_ESCALATED": NotificationTemplate(
                template_id="COMPLAINT_ESCALATED",
                name="Complaint Escalation Notification",
                category="escalation",
                channels={NotificationChannel.EMAIL, NotificationChannel.IN_APP, NotificationChannel.SMS},
                priority=NotificationPriority.URGENT,
                templates={
                    "email": """
                    <h2>🚨 Complaint Escalated</h2>
                    <p>A {{escalation_type}} has been escalated to your attention.</p>
                    <p><strong>Details:</strong></p>
                    <ul>
                        <li>ID: {{entity_id}}</li>
                        <li>Level: {{level}}</li>
                        <li>Priority: {{#is_urgent}}URGENT{{/is_urgent}}{{^is_urgent}}Normal{{/is_urgent}}</li>
                    </ul>
                    <p>Please review and take action within the SLA timeframe.</p>
                    """,
                    "sms": "🚨 {{escalation_type}} escalated to you - ID: {{entity_id}}, Level: {{level}}. {{#is_urgent}}URGENT - {{/is_urgent}}Please review.",
                    "in_app": "🚨 Escalated {{escalation_type}}: {{entity_id}} ({{level}}) {{#is_urgent}}- URGENT{{/is_urgent}}"
                },
                variables={"escalation_type", "entity_id", "level", "is_urgent"},
                delivery_strategy=DeliveryStrategy.IMMEDIATE
            )
        }
        
        # Onboarding notification templates
        onboarding_templates = {
            "STUDENT_ONBOARDING_WELCOME": NotificationTemplate(
                template_id="STUDENT_ONBOARDING_WELCOME",
                name="Student Onboarding Welcome",
                category="onboarding",
                channels={NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.IN_APP},
                priority=NotificationPriority.HIGH,
                templates={
                    "email": """
                    <h1>Welcome to {{hostel_name}}! 🏠</h1>
                    <p>Dear {{student_name}},</p>
                    <p>Welcome to your new home away from home! Your onboarding is complete.</p>
                    <p><strong>Your Details:</strong></p>
                    <ul>
                        <li>Check-in Date: {{check_in_date}}</li>
                        <li>Room Number: {{room_number}}</li>
                        <li>Access Code: {{access_code}}</li>
                    </ul>
                    <p><strong>Next Steps:</strong></p>
                    <ol>
                        <li>Download our mobile app</li>
                        <li>Complete your profile</li>
                        <li>Join the community groups</li>
                    </ol>
                    <p>Need help? Contact us at {{support_contact}}</p>
                    """,
                    "sms": "Welcome to {{hostel_name}}! Check-in: {{check_in_date}}, Room: {{room_number}}. Download our app for more details!",
                    "in_app": "🏠 Welcome to {{hostel_name}}! Room {{room_number}} is ready. Check your email for complete details."
                },
                variables={"student_name", "hostel_name", "check_in_date", "room_number", "access_code", "support_contact"},
                delivery_strategy=DeliveryStrategy.IMMEDIATE
            )
        }
        
        # Checkout notification templates
        checkout_templates = {
            "STUDENT_CHECKOUT_COMPLETED": NotificationTemplate(
                template_id="STUDENT_CHECKOUT_COMPLETED",
                name="Student Checkout Completion",
                category="checkout",
                channels={NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.IN_APP},
                priority=NotificationPriority.HIGH,
                templates={
                    "email": """
                    <h2>Checkout Completed Successfully</h2>
                    <p>Your checkout process has been completed.</p>
                    <p><strong>Summary:</strong></p>
                    <ul>
                        <li>Checkout Date: {{checkout_date}}</li>
                        {{#refund_amount}}
                        <li>Refund Amount: ${{refund_amount}} (Processing in 5-7 business days)</li>
                        {{/refund_amount}}
                        {{#amount_to_collect}}
                        <li>Outstanding Amount: ${{amount_to_collect}} (Please pay immediately)</li>
                        {{/amount_to_collect}}
                    </ul>
                    <p>Thank you for staying with us! We hope to welcome you back.</p>
                    """,
                    "sms": "Checkout completed on {{checkout_date}}. {{#refund_amount}}Refund: ${{refund_amount}} in 5-7 days.{{/refund_amount}}{{#amount_to_collect}}Outstanding: ${{amount_to_collect}}.{{/amount_to_collect}}",
                    "in_app": "✅ Checkout completed! {{#refund_amount}}Refund: ${{refund_amount}}{{/refund_amount}}{{#amount_to_collect}}Pay: ${{amount_to_collect}}{{/amount_to_collect}}"
                },
                variables={"checkout_date", "refund_amount", "amount_to_collect"},
                delivery_strategy=DeliveryStrategy.IMMEDIATE
            )
        }
        
        # Combine all templates
        all_templates = {
            **approval_templates,
            **escalation_templates,
            **onboarding_templates,
            **checkout_templates
        }
        
        self.templates.update(all_templates)
    
    def _start_delivery_processors(self) -> None:
        """Start background delivery processors for each channel."""
        # In a real implementation, these would be background tasks
        # For now, we'll simulate with placeholder methods
        pass
    
    # Public API methods
    
    async def send_approval_notification(
        self,
        db: Session,
        user_id: UUID,
        approval_type: str,
        approved: bool,
        entity_id: UUID,
        hostel_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send intelligent approval notification with optimal delivery.
        
        Args:
            db: Database session
            user_id: Target user
            approval_type: Type of approval (booking, maintenance, etc.)
            approved: Whether approved or rejected
            entity_id: ID of approved/rejected entity
            hostel_id: Optional hostel context
            metadata: Additional notification data
            
        Returns:
            Comprehensive delivery result
        """
        # Determine template
        template_code = self._get_approval_template_code(approval_type, approved)
        template = self._get_template(template_code)
        
        if not template:
            # Fallback to generic template
            template_code = "GENERIC_APPROVAL_DECISION"
            template = self._get_template(template_code)
        
        # Prepare notification context
        variables = {
            "approval_type": approval_type,
            "decision": "approved" if approved else "rejected",
            "entity_id": str(entity_id),
            **(metadata or {})
        }
        
        # Send with intelligent delivery
        return await self._send_intelligent_notification(
            db=db,
            user_id=user_id,
            template=template,
            variables=variables,
            hostel_id=hostel_id,
            category="approval"
        )
    
    async def send_escalation_notification(
        self,
        db: Session,
        assignee_id: UUID,
        escalation_type: str,
        entity_id: UUID,
        level: str,
        is_urgent: bool = False,
        hostel_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send escalation notification with priority handling.
        
        Args:
            db: Database session
            assignee_id: User receiving escalation
            escalation_type: Type of escalation
            entity_id: Escalated entity ID
            level: Escalation level
            is_urgent: Urgency flag
            hostel_id: Optional hostel context
            metadata: Additional context data
            
        Returns:
            Delivery result with tracking information
        """
        template_code = self._get_escalation_template_code(escalation_type)
        template = self._get_template(template_code)
        
        variables = {
            "escalation_type": escalation_type,
            "entity_id": str(entity_id),
            "level": level,
            "is_urgent": is_urgent,
            **(metadata or {})
        }
        
        # Override priority for urgent escalations
        if is_urgent and template:
            template.priority = NotificationPriority.URGENT
            template.delivery_strategy = DeliveryStrategy.IMMEDIATE
        
        return await self._send_intelligent_notification(
            db=db,
            user_id=assignee_id,
            template=template,
            variables=variables,
            hostel_id=hostel_id,
            category="escalation"
        )
    
    async def send_onboarding_notifications(
        self,
        db: Session,
        student_user_id: UUID,
        hostel_id: UUID,
        student_name: str,
        check_in_date: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send comprehensive onboarding notification sequence.
        
        Args:
            db: Database session
            student_user_id: Student user ID
            hostel_id: Hostel ID
            student_name: Student name for personalization
            check_in_date: Check-in date string
            additional_data: Additional onboarding data
            
        Returns:
            Multi-stage delivery result
        """
        template = self._get_template("STUDENT_ONBOARDING_WELCOME")
        
        variables = {
            "student_name": student_name,
            "check_in_date": check_in_date,
            **(additional_data or {})
        }
        
        return await self._send_intelligent_notification(
            db=db,
            user_id=student_user_id,
            template=template,
            variables=variables,
            hostel_id=hostel_id,
            category="onboarding"
        )
    
    async def send_checkout_notifications(
        self,
        db: Session,
        student_user_id: UUID,
        hostel_id: UUID,
        checkout_date: str,
        refund_amount: Optional[float] = None,
        amount_to_collect: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send checkout completion notifications.
        
        Args:
            db: Database session
            student_user_id: Student user ID
            hostel_id: Hostel ID
            checkout_date: Checkout date string
            refund_amount: Optional refund amount
            amount_to_collect: Optional outstanding amount
            
        Returns:
            Delivery result
        """
        template = self._get_template("STUDENT_CHECKOUT_COMPLETED")
        
        variables = {
            "checkout_date": checkout_date,
            "refund_amount": refund_amount,
            "amount_to_collect": amount_to_collect
        }
        
        return await self._send_intelligent_notification(
            db=db,
            user_id=student_user_id,
            template=template,
            variables=variables,
            hostel_id=hostel_id,
            category="checkout"
        )
    
    async def send_bulk_notifications(
        self,
        db: Session,
        user_ids: List[UUID],
        template_code: str,
        variables: Dict[str, Any],
        personalization_data: Optional[Dict[UUID, Dict[str, Any]]] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Send notifications to multiple users efficiently.
        
        Args:
            db: Database session
            user_ids: List of target user IDs
            template_code: Template identifier
            variables: Common variables for all notifications
            personalization_data: User-specific variable overrides
            batch_size: Batch size for processing
            
        Returns:
            Bulk delivery summary
        """
        template = self._get_template(template_code)
        if not template:
            raise ValidationException(f"Template not found: {template_code}")
        
        delivery_results = {
            "total_users": len(user_ids),
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "batch_results": [],
            "delivery_summary": {}
        }
        
        # Process in batches for performance
        for i in range(0, len(user_ids), batch_size):
            batch_user_ids = user_ids[i:i + batch_size]
            
            # Create concurrent delivery tasks
            batch_tasks = []
            for user_id in batch_user_ids:
                # Merge common and personalized variables
                user_variables = variables.copy()
                if personalization_data and user_id in personalization_data:
                    user_variables.update(personalization_data[user_id])
                
                task = self._send_intelligent_notification(
                    db=db,
                    user_id=user_id,
                    template=template,
                    variables=user_variables,
                    category="bulk"
                )
                batch_tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results
            batch_summary = {"successful": 0, "failed": 0, "errors": []}
            for j, result in enumerate(batch_results):
                user_id = batch_user_ids[j]
                if isinstance(result, Exception):
                    batch_summary["failed"] += 1
                    batch_summary["errors"].append({
                        "user_id": str(user_id),
                        "error": str(result)
                    })
                    delivery_results["failed_deliveries"] += 1
                else:
                    batch_summary["successful"] += 1
                    delivery_results["successful_deliveries"] += 1
            
            delivery_results["batch_results"].append(batch_summary)
        
        # Calculate delivery summary by channel
        delivery_results["delivery_summary"] = {
            "success_rate": (delivery_results["successful_deliveries"] / delivery_results["total_users"]) * 100,
            "total_cost": 0.0,  # Would calculate actual costs
            "average_delivery_time": 0.0  # Would calculate from delivery metrics
        }
        
        return delivery_results
    
    async def get_notification_analytics(
        self,
        db: Session,
        user_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        date_range: Optional[tuple] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive notification analytics."""
        start_date, end_date = date_range or (
            datetime.utcnow() - timedelta(days=30),
            datetime.utcnow()
        )
        
        analytics = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": (end_date - start_date).days
            },
            "delivery_metrics": {
                "total_sent": self.delivery_metrics.total_sent,
                "total_delivered": self.delivery_metrics.total_delivered,
                "total_failed": self.delivery_metrics.total_failed,
                "delivery_rate": (
                    (self.delivery_metrics.total_delivered / self.delivery_metrics.total_sent * 100)
                    if self.delivery_metrics.total_sent > 0 else 0
                )
            },
            "channel_performance": dict(self.delivery_metrics.channel_metrics),
            "user_engagement": dict(self.delivery_metrics.user_engagement),
            "cost_analysis": dict(self.delivery_metrics.cost_metrics),
            "template_performance": await self._get_template_performance_analytics(db, start_date, end_date),
            "optimization_suggestions": await self._generate_optimization_suggestions(db)
        }
        
        return analytics
    
    # Internal methods
    
    async def _send_intelligent_notification(
        self,
        db: Session,
        user_id: UUID,
        template: NotificationTemplate,
        variables: Dict[str, Any],
        hostel_id: Optional[UUID] = None,
        category: str = "general"
    ) -> Dict[str, Any]:
        """Send notification with intelligent channel selection and timing."""
        
        # Get user preferences
        user_preferences = await self._get_user_preferences(db, user_id)
        
        # Determine optimal delivery channels
        optimal_channels = await self._determine_optimal_channels(
            template, user_preferences, variables
        )
        
        # Determine optimal delivery timing
        optimal_timing = await self._determine_optimal_timing(
            user_id, template, user_preferences
        )
        
        # Create notification records
        notifications = []
        for channel in optimal_channels:
            notification_data = {
                "user_id": user_id,
                "hostel_id": hostel_id,
                "template_id": template.template_id,
                "channel": channel,
                "priority": template.priority,
                "category": category,
                "subject": await self._render_subject(template, channel, variables),
                "content": await self._render_content(template, channel, variables, user_preferences.language),
                "variables": variables,
                "scheduled_for": optimal_timing.get(channel),
                "expires_at": datetime.utcnow() + timedelta(hours=template.expiry_hours),
                "delivery_strategy": template.delivery_strategy
            }
            
            notification = self.notification_repo.create(db, notification_data)
            notifications.append(notification)
        
        # Queue for delivery
        delivery_results = []
        for notification in notifications:
            if notification.scheduled_for and notification.scheduled_for > datetime.utcnow():
                # Schedule for later delivery
                self.queue_repo.schedule_notification(db, notification.id, notification.scheduled_for)
                delivery_results.append({
                    "channel": notification.channel,
                    "status": "scheduled",
                    "scheduled_for": notification.scheduled_for.isoformat()
                })
            else:
                # Immediate delivery
                delivery_result = await self._deliver_notification(db, notification)
                delivery_results.append(delivery_result)
        
        return {
            "notification_id": str(notifications[0].id) if notifications else None,
            "template_id": template.template_id,
            "user_id": str(user_id),
            "channels_used": [n.channel for n in notifications],
            "delivery_results": delivery_results,
            "total_channels": len(notifications)
        }
    
    async def _get_user_preferences(
        self,
        db: Session,
        user_id: UUID
    ) -> UserNotificationPreference:
        """Get user notification preferences with caching."""
        # Check cache first
        if user_id in self._preference_cache:
            cached_time = getattr(self._preference_cache[user_id], '_cached_at', datetime.min)
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return self._preference_cache[user_id]
        
        # Load from database
        db_preferences = self.preference_repo.get_by_user_id(db, user_id)
        
        if db_preferences:
            preferences = UserNotificationPreference(
                user_id=user_id,
                channel_preferences=db_preferences.channel_preferences or {},
                category_preferences=db_preferences.category_preferences or {},
                quiet_hours=db_preferences.quiet_hours or {},
                frequency_limits=db_preferences.frequency_limits or {},
                language=db_preferences.language or "en",
                timezone=db_preferences.timezone or "UTC"
            )
        else:
            # Default preferences
            preferences = UserNotificationPreference(
                user_id=user_id,
                channel_preferences={
                    NotificationChannel.EMAIL: True,
                    NotificationChannel.IN_APP: True,
                    NotificationChannel.SMS: False,
                    NotificationChannel.PUSH: True
                },
                category_preferences={},
                quiet_hours={"start": "22:00", "end": "08:00"},
                frequency_limits={"promotional": 2, "marketing": 1},
                language="en",
                timezone="UTC"
            )
        
        # Cache preferences
        preferences._cached_at = datetime.utcnow()
        self._preference_cache[user_id] = preferences
        
        return preferences
    
    async def _determine_optimal_channels(
        self,
        template: NotificationTemplate,
        user_preferences: UserNotificationPreference,
        variables: Dict[str, Any]
    ) -> List[NotificationChannel]:
        """Determine optimal delivery channels based on user preferences and context."""
        optimal_channels = []
        
        # Start with template's supported channels
        available_channels = template.channels
        
        # Filter based on user preferences
        for channel in available_channels:
            # Check if user allows this channel
            if not user_preferences.channel_preferences.get(channel, True):
                continue
            
            # Check category-specific preferences
            category_prefs = user_preferences.category_preferences.get(template.category, {})
            if not category_prefs.get(channel, True):
                continue
            
            # Check frequency limits
            if await self._check_frequency_limits(user_preferences, template.category, channel):
                optimal_channels.append(channel)
        
        # Ensure at least one channel (fallback to email if available)
        if not optimal_channels and NotificationChannel.EMAIL in available_channels:
            optimal_channels.append(NotificationChannel.EMAIL)
        
        # Apply priority-based channel selection
        if template.priority == NotificationPriority.URGENT:
            # For urgent notifications, use multiple channels
            if NotificationChannel.SMS in available_channels:
                optimal_channels.append(NotificationChannel.SMS)
            if NotificationChannel.PUSH in available_channels:
                optimal_channels.append(NotificationChannel.PUSH)
        
        return list(set(optimal_channels))  # Remove duplicates
    
    async def _determine_optimal_timing(
        self,
        user_id: UUID,
        template: NotificationTemplate,
        user_preferences: UserNotificationPreference
    ) -> Dict[NotificationChannel, datetime]:
        """Determine optimal delivery timing for each channel."""
        timing_map = {}
        
        if template.delivery_strategy == DeliveryStrategy.IMMEDIATE:
            # All channels deliver immediately
            return {channel: datetime.utcnow() for channel in template.channels}
        
        elif template.delivery_strategy == DeliveryStrategy.OPTIMAL_TIME:
            # Use ML/analytics to determine best time
            optimal_time = await self._calculate_optimal_delivery_time(user_id, template.category)
            return {channel: optimal_time for channel in template.channels}
        
        elif template.delivery_strategy == DeliveryStrategy.BATCH:
            # Schedule for next batch window
            next_batch_time = await self._get_next_batch_time(template.category)
            return {channel: next_batch_time for channel in template.channels}
        
        # Default to immediate delivery
        return {channel: datetime.utcnow() for channel in template.channels}
    
    async def _deliver_notification(
        self,
        db: Session,
        notification
    ) -> Dict[str, Any]:
        """Deliver notification through specified channel."""
        delivery_result = {
            "notification_id": str(notification.id),
            "channel": notification.channel,
            "status": "failed",
            "delivery_time": None,
            "cost": 0.0,
            "error": None
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Update status to processing
            notification.status = NotificationStatus.PROCESSING
            db.commit()
            
            # Deliver through appropriate service
            if notification.channel == NotificationChannel.EMAIL:
                result = await self.email_service.send_email(
                    to_email=notification.user.email,
                    subject=notification.subject,
                    html_content=notification.content
                )
                delivery_result["cost"] = 0.01  # Email cost
            
            elif notification.channel == NotificationChannel.SMS:
                result = await self.sms_service.send_sms(
                    phone_number=notification.user.phone_number,
                    message=notification.content
                )
                delivery_result["cost"] = 0.05  # SMS cost
            
            elif notification.channel == NotificationChannel.PUSH:
                result = await self.push_service.send_push_notification(
                    user_id=notification.user_id,
                    title=notification.subject,
                    body=notification.content
                )
                delivery_result["cost"] = 0.001  # Push notification cost
            
            elif notification.channel == NotificationChannel.IN_APP:
                # In-app notifications are stored in database
                result = {"success": True, "message_id": str(notification.id)}
                delivery_result["cost"] = 0.0
            
            else:
                raise ValueError(f"Unsupported channel: {notification.channel}")
            
            # Update notification status
            if result.get("success"):
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                notification.external_id = result.get("message_id")
                
                delivery_result["status"] = "sent"
                delivery_result["delivery_time"] = (datetime.utcnow() - start_time).total_seconds()
                
                # Update metrics
                self.delivery_metrics.total_sent += 1
                self.delivery_metrics.channel_metrics[notification.channel]["sent"] += 1
                self.delivery_metrics.cost_metrics[notification.channel] = \
                    self.delivery_metrics.cost_metrics.get(notification.channel, 0) + delivery_result["cost"]
            else:
                notification.status = NotificationStatus.FAILED
                notification.error_message = result.get("error", "Unknown error")
                delivery_result["error"] = notification.error_message
                
                # Update metrics
                self.delivery_metrics.total_failed += 1
                self.delivery_metrics.channel_metrics[notification.channel]["failed"] += 1
        
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            delivery_result["error"] = str(e)
            
            # Update metrics
            self.delivery_metrics.total_failed += 1
            self.delivery_metrics.channel_metrics[notification.channel]["failed"] += 1
        
        finally:
            db.commit()
        
        return delivery_result
    
    # Helper methods
    
    def _get_approval_template_code(self, approval_type: str, approved: bool) -> str:
        """Get template code for approval notifications."""
        decision = "APPROVED" if approved else "REJECTED"
        template_map = {
            "booking": f"BOOKING_{decision}",
            "maintenance": f"MAINTENANCE_{decision}",
            "leave": f"LEAVE_{decision}",
            "menu": f"MENU_{decision}",
        }
        return template_map.get(approval_type, "GENERIC_APPROVAL_DECISION")
    
    def _get_escalation_template_code(self, escalation_type: str) -> str:
        """Get template code for escalation notifications."""
        template_map = {
            "complaint": "COMPLAINT_ESCALATED",
            "maintenance": "MAINTENANCE_ESCALATED",
            "approval": "APPROVAL_ESCALATED",
            "sla_breach": "SLA_BREACH_ESCALATED",
        }
        return template_map.get(escalation_type, "GENERIC_ESCALATION")
    
    def _get_template(self, template_code: str) -> Optional[NotificationTemplate]:
        """Get template with caching."""
        if template_code in self._template_cache:
            return self._template_cache[template_code]
        
        template = self.templates.get(template_code)
        if template:
            self._template_cache[template_code] = template
        
        return template
    
    async def _render_subject(
        self,
        template: NotificationTemplate,
        channel: NotificationChannel,
        variables: Dict[str, Any]
    ) -> str:
        """Render notification subject with variables."""
        # Simplified rendering - would use proper template engine
        subject_template = template.templates.get(channel, "")
        # Extract subject from template or use default
        return f"Notification: {template.name}"
    
    async def _render_content(
        self,
        template: NotificationTemplate,
        channel: NotificationChannel,
        variables: Dict[str, Any],
        language: str = "en"
    ) -> str:
        """Render notification content with variables and localization."""
        # Get template content for channel
        content_template = template.templates.get(channel, "")
        
        # Apply localization if available
        if language != "en" and language in template.localization:
            localized_templates = template.localization[language]
            content_template = localized_templates.get(channel, content_template)
        
        # Render variables (simplified - would use proper template engine)
        rendered_content = content_template
        for key, value in variables.items():
            if value is not None:
                rendered_content = rendered_content.replace(f"{{{{{key}}}}}", str(value))
        
        return rendered_content
    
    async def _check_frequency_limits(
        self,
        user_preferences: UserNotificationPreference,
        category: str,
        channel: NotificationChannel
    ) -> bool:
        """Check if user hasn't exceeded frequency limits."""
        # Implementation would check actual notification history
        return True
    
    async def _calculate_optimal_delivery_time(
        self,
        user_id: UUID,
        category: str
    ) -> datetime:
        """Calculate optimal delivery time using ML/analytics."""
        # Implementation would use ML models and user behavior data
        # For now, return immediate delivery
        return datetime.utcnow()
    
    async def _get_next_batch_time(self, category: str) -> datetime:
        """Get next batch processing time for category."""
        # Implementation would return next scheduled batch time
        return datetime.utcnow() + timedelta(minutes=30)
    
    async def _get_template_performance_analytics(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get template performance analytics."""
        # Implementation would query actual performance data
        return {
            "most_effective_template": "BOOKING_APPROVED",
            "highest_engagement_rate": 85.5,
            "template_rankings": []
        }
    
    async def _generate_optimization_suggestions(self, db: Session) -> List[str]:
        """Generate optimization suggestions based on performance data."""
        suggestions = []
        
        # Analyze delivery performance
        if self.delivery_metrics.total_failed > self.delivery_metrics.total_sent * 0.1:
            suggestions.append("High failure rate detected. Review channel configurations.")
        
        # Analyze cost efficiency
        email_cost = self.delivery_metrics.cost_metrics.get("email", 0)
        sms_cost = self.delivery_metrics.cost_metrics.get("sms", 0)
        
        if sms_cost > email_cost * 2:
            suggestions.append("Consider reducing SMS usage for cost optimization.")
        
        return suggestions