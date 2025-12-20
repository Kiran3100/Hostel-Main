# --- File: C:\Hostel-Main\app\services\notification\notification_routing_service.py ---
"""
Notification Routing Service - Manages intelligent routing and escalation.

Handles routing rules, escalation workflows, recipient resolution,
and automated escalation processing.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.notification.notification_routing import (
    RoutingRule,
    EscalationPath,
    NotificationEscalation,
    NotificationRoute
)
from app.models.notification.notification import Notification
from app.models.user.user import User
from app.repositories.notification.notification_routing_repository import (
    NotificationRoutingRepository
)
from app.repositories.user.user_repository import UserRepository
from app.schemas.common.enums import Priority, UserRole
from app.core.exceptions import RoutingError

logger = logging.getLogger(__name__)


class NotificationRoutingService:
    """
    Service for notification routing and escalation management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.routing_repo = NotificationRoutingRepository(db_session)
        self.user_repo = UserRepository(db_session)

    def create_routing_rule(
        self,
        rule_name: str,
        conditions: Dict[str, Any],
        recipient_roles: List[str],
        channels: List[str],
        description: Optional[str] = None,
        rule_priority: int = 0,
        specific_users: Optional[List[UUID]] = None,
        recipient_groups: Optional[List[str]] = None,
        template_code: Optional[str] = None,
        hostel_id: Optional[UUID] = None,
        stop_on_match: bool = False
    ) -> RoutingRule:
        """
        Create new routing rule.
        
        Args:
            rule_name: Rule name
            conditions: Routing conditions to match
            recipient_roles: User roles to notify
            channels: Notification channels to use
            description: Rule description
            rule_priority: Rule priority (higher evaluated first)
            specific_users: Specific user IDs to notify
            recipient_groups: User groups to notify
            template_code: Template to use
            hostel_id: Hostel scope (None = global)
            stop_on_match: Stop processing rules after match
            
        Returns:
            Created RoutingRule
        """
        try:
            rule_data = {
                'rule_name': rule_name,
                'description': description,
                'rule_priority': rule_priority,
                'conditions': conditions,
                'recipient_roles': recipient_roles,
                'specific_users': specific_users or [],
                'recipient_groups': recipient_groups or [],
                'channels': channels,
                'template_code': template_code,
                'stop_on_match': stop_on_match,
                'is_active': True
            }
            
            rule = self.routing_repo.create_routing_rule(rule_data, hostel_id)
            
            logger.info(f"Routing rule created: {rule_name}")
            
            return rule
            
        except Exception as e:
            logger.error(f"Error creating routing rule: {str(e)}", exc_info=True)
            raise RoutingError(f"Failed to create routing rule: {str(e)}")

    def apply_routing(
        self,
        notification: Notification,
        routing_context: Optional[Dict[str, Any]] = None
    ) -> Optional[NotificationRoute]:
        """
        Apply routing rules to notification.
        
        Args:
            notification: Notification to route
            routing_context: Additional routing context
            
        Returns:
            NotificationRoute if rules matched, None otherwise
        """
        try:
            # Prepare routing context
            context = routing_context or {}
            context.update({
                'notification_type': notification.notification_type.value,
                'priority': notification.priority.value,
                'hostel_id': notification.hostel_id,
            })
            
            # Add metadata to context
            if notification.metadata:
                context.update(notification.metadata)
            
            # Find matching rules
            matched_rules = self.routing_repo.find_matching_rules(
                context,
                notification.hostel_id
            )
            
            if not matched_rules:
                logger.debug(
                    f"No routing rules matched for notification {notification.id}"
                )
                return None
            
            # Apply first matching rule
            rule = matched_rules[0]
            
            route = self.routing_repo.apply_routing_rule(
                notification.id,
                rule,
                context
            )
            
            logger.info(
                f"Applied routing rule '{rule.rule_name}' to notification {notification.id}"
            )
            
            # Check if escalation should be enabled
            if rule.escalation_path_id:
                self.initiate_escalation(
                    notification.id,
                    rule.escalation_path_id,
                    context
                )
            
            return route
            
        except Exception as e:
            logger.error(f"Error applying routing: {str(e)}", exc_info=True)
            raise RoutingError(f"Failed to apply routing: {str(e)}")

    def test_routing(
        self,
        test_context: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Test routing rules against context without applying.
        
        Args:
            test_context: Context to test against
            hostel_id: Hostel scope
            
        Returns:
            List of matching rules with details
        """
        try:
            return self.routing_repo.test_routing_rules(test_context, hostel_id)
        except Exception as e:
            logger.error(f"Error testing routing: {str(e)}", exc_info=True)
            raise

    def create_escalation_path(
        self,
        path_name: str,
        event_type: str,
        levels: List[Dict[str, Any]],
        description: Optional[str] = None,
        hostel_id: Optional[UUID] = None,
        auto_escalate: bool = True
    ) -> EscalationPath:
        """
        Create escalation path.
        
        Args:
            path_name: Path name
            event_type: Event type this applies to
            levels: Escalation levels configuration
            description: Path description
            hostel_id: Hostel scope
            auto_escalate: Enable automatic escalation
            
        Returns:
            Created EscalationPath
            
        Example levels:
            [
                {
                    'level': 1,
                    'escalate_after_hours': 1,
                    'recipients': ['manager_role'],
                    'channels': ['email', 'push']
                },
                {
                    'level': 2,
                    'escalate_after_hours': 3,
                    'recipients': ['senior_manager_role'],
                    'channels': ['email', 'sms', 'push']
                }
            ]
        """
        try:
            path_data = {
                'path_name': path_name,
                'description': description,
                'event_type': event_type,
                'levels': levels,
                'is_active': True,
                'auto_escalate': auto_escalate
            }
            
            path = self.routing_repo.create_escalation_path(path_data, hostel_id)
            
            logger.info(f"Escalation path created: {path_name}")
            
            return path
            
        except Exception as e:
            logger.error(f"Error creating escalation path: {str(e)}", exc_info=True)
            raise RoutingError(f"Failed to create escalation path: {str(e)}")

    def initiate_escalation(
        self,
        notification_id: UUID,
        escalation_path_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> NotificationEscalation:
        """
        Start escalation process for notification.
        
        Args:
            notification_id: Notification to escalate
            escalation_path_id: Escalation path to use
            context: Additional context
            
        Returns:
            NotificationEscalation
        """
        try:
            escalation = self.routing_repo.initiate_escalation(
                notification_id,
                escalation_path_id,
                context
            )
            
            logger.info(
                f"Escalation initiated for notification {notification_id}"
            )
            
            return escalation
            
        except Exception as e:
            logger.error(f"Error initiating escalation: {str(e)}", exc_info=True)
            raise RoutingError(f"Failed to initiate escalation: {str(e)}")

    def process_escalations(
        self,
        batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Process pending escalations.
        
        Args:
            batch_size: Number of escalations to process
            
        Returns:
            List of processed escalations
        """
        try:
            results = self.routing_repo.process_escalations(batch_size)
            
            if results:
                logger.info(f"Processed {len(results)} escalations")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing escalations: {str(e)}", exc_info=True)
            raise

    def resolve_escalation(
        self,
        escalation_id: UUID,
        resolved_by_id: UUID,
        resolution_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark escalation as resolved.
        
        Args:
            escalation_id: Escalation to resolve
            resolved_by_id: User resolving
            resolution_context: Resolution details
            
        Returns:
            Success status
        """
        try:
            success = self.routing_repo.resolve_escalation(
                escalation_id,
                resolved_by_id,
                resolution_context
            )
            
            if success:
                logger.info(
                    f"Escalation {escalation_id} resolved by user {resolved_by_id}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error resolving escalation: {str(e)}", exc_info=True)
            return False

    def get_routing_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get routing performance analytics."""
        try:
            return self.routing_repo.get_routing_analytics(
                start_date,
                end_date,
                hostel_id
            )
        except Exception as e:
            logger.error(f"Error getting routing analytics: {str(e)}", exc_info=True)
            raise

    def get_escalation_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get escalation performance analytics."""
        try:
            return self.routing_repo.get_escalation_analytics(
                start_date,
                end_date,
                hostel_id
            )
        except Exception as e:
            logger.error(f"Error getting escalation analytics: {str(e)}", exc_info=True)
            raise

    def optimize_routing_rules(
        self,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Analyze and suggest routing optimizations."""
        try:
            return self.routing_repo.optimize_routing_rules(hostel_id)
        except Exception as e:
            logger.error(f"Error optimizing routing: {str(e)}", exc_info=True)
            raise

    def find_unused_rules(
        self,
        days: int = 90
    ) -> List[RoutingRule]:
        """Find routing rules not used recently."""
        try:
            return self.routing_repo.find_unused_rules(days)
        except Exception as e:
            logger.error(f"Error finding unused rules: {str(e)}", exc_info=True)
            return []


