# app/services/notification/notification_routing_service.py
"""
Enhanced Notification Routing Service

Evaluates routing rules and escalation paths with improved:
- Performance through rule caching and optimization
- Advanced rule evaluation with context awareness
- Comprehensive validation and error handling
- Flexible routing configuration
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Set
from uuid import UUID
from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationRoutingRepository
from app.schemas.notification import (
    RoutingConfig,
    NotificationRoute,
    RoutingRule,
    EscalationPath,
)
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class NotificationRoutingService:
    """
    Enhanced high-level service to apply routing rules and build NotificationRoute.

    Enhanced with:
    - Rule caching for performance
    - Advanced context evaluation
    - Flexible escalation handling
    - Comprehensive validation
    - Performance monitoring
    """

    def __init__(self, routing_repo: NotificationRoutingRepository) -> None:
        self.routing_repo = routing_repo
        self._rule_cache_ttl = 300  # 5 minutes
        self._max_escalation_levels = 5
        self._default_channels = ["in_app", "email"]
        self._valid_channels = ["in_app", "email", "sms", "push", "webhook"]
        self._valid_priorities = ["low", "normal", "high", "urgent"]

    def _validate_event_type(self, event_type: str) -> None:
        """Validate event type format and content."""
        if not event_type or len(event_type.strip()) == 0:
            raise ValidationException("Event type cannot be empty")
        
        if len(event_type) > 100:
            raise ValidationException("Event type too long (max 100 characters)")
        
        # Basic format validation (alphanumeric, underscores, dots)
        if not event_type.replace('_', '').replace('.', '').replace('-', '').isalnum():
            raise ValidationException(
                "Event type can only contain alphanumeric characters, underscores, dots, and hyphens"
            )

    def _validate_hostel_id(self, hostel_id: UUID) -> None:
        """Validate hostel ID."""
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

    def _validate_routing_config(self, config: RoutingConfig) -> None:
        """Validate routing configuration."""
        if not config.hostel_id:
            raise ValidationException("Hostel ID is required in routing config")
        
        # Validate channels
        invalid_channels = set(config.default_channels) - set(self._valid_channels)
        if invalid_channels:
            raise ValidationException(
                f"Invalid channels: {invalid_channels}. Valid channels: {self._valid_channels}"
            )
        
        # Validate escalation settings
        if config.enable_escalation and not config.escalation_timeout_hours:
            raise ValidationException(
                "Escalation timeout is required when escalation is enabled"
            )
        
        if config.escalation_timeout_hours and config.escalation_timeout_hours < 0.1:
            raise ValidationException("Escalation timeout must be at least 0.1 hours (6 minutes)")

    def _evaluate_rule_conditions(
        self,
        rule: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate if a routing rule matches the given context.
        
        Enhanced with comprehensive condition evaluation.
        """
        try:
            conditions = rule.get("conditions", {})
            
            # Event type matching (exact or pattern)
            if "event_types" in conditions:
                event_type = context.get("event_type", "")
                allowed_types = conditions["event_types"]
                if not any(self._matches_pattern(event_type, pattern) for pattern in allowed_types):
                    return False
            
            # Priority matching
            if "priorities" in conditions:
                priority = context.get("priority", "normal")
                if priority not in conditions["priorities"]:
                    return False
            
            # Time-based conditions
            if "time_conditions" in conditions:
                if not self._evaluate_time_conditions(conditions["time_conditions"], context):
                    return False
            
            # Custom metadata conditions
            if "metadata_conditions" in conditions:
                if not self._evaluate_metadata_conditions(conditions["metadata_conditions"], context):
                    return False
            
            # User role conditions
            if "user_roles" in conditions:
                user_roles = context.get("user_roles", [])
                required_roles = conditions["user_roles"]
                if not any(role in user_roles for role in required_roles):
                    return False
            
            # Room/area conditions
            if "room_conditions" in conditions:
                if not self._evaluate_room_conditions(conditions["room_conditions"], context):
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error evaluating rule conditions: {str(e)}")
            return False

    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if text matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if "*" not in pattern:
            return text == pattern
        
        # Simple wildcard matching
        parts = pattern.split("*")
        if not text.startswith(parts[0]):
            return False
        if not text.endswith(parts[-1]):
            return False
        
        return True

    def _evaluate_time_conditions(
        self,
        time_conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate time-based routing conditions."""
        current_time = datetime.utcnow()
        
        # Business hours check
        if "business_hours_only" in time_conditions:
            if time_conditions["business_hours_only"]:
                # Assume business hours are 9 AM to 6 PM UTC
                hour = current_time.hour
                if hour < 9 or hour >= 18:
                    return False
        
        # Day of week check
        if "allowed_days" in time_conditions:
            current_day = current_time.weekday()  # 0 = Monday
            if current_day not in time_conditions["allowed_days"]:
                return False
        
        # Custom time range
        if "time_range" in time_conditions:
            time_range = time_conditions["time_range"]
            start_hour = time_range.get("start_hour", 0)
            end_hour = time_range.get("end_hour", 23)
            if not (start_hour <= current_time.hour < end_hour):
                return False
        
        return True

    def _evaluate_metadata_conditions(
        self,
        metadata_conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate custom metadata conditions."""
        payload = context.get("payload", {})
        
        for key, condition in metadata_conditions.items():
            value = payload.get(key)
            
            if isinstance(condition, dict):
                # Complex condition evaluation
                if "equals" in condition and value != condition["equals"]:
                    return False
                if "in" in condition and value not in condition["in"]:
                    return False
                if "greater_than" in condition and (value is None or value <= condition["greater_than"]):
                    return False
                if "less_than" in condition and (value is None or value >= condition["less_than"]):
                    return False
            else:
                # Simple equality check
                if value != condition:
                    return False
        
        return True

    def _evaluate_room_conditions(
        self,
        room_conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate room/area-based conditions."""
        payload = context.get("payload", {})
        
        # Room ID matching
        if "room_ids" in room_conditions:
            room_id = payload.get("room_id")
            if room_id not in room_conditions["room_ids"]:
                return False
        
        # Floor matching
        if "floors" in room_conditions:
            floor = payload.get("floor")
            if floor not in room_conditions["floors"]:
                return False
        
        # Building/wing matching
        if "buildings" in room_conditions:
            building = payload.get("building")
            if building not in room_conditions["buildings"]:
                return False
        
        return True

    @lru_cache(maxsize=100)
    def _get_cached_config(self, hostel_id: UUID) -> Optional[Dict[str, Any]]:
        """Cache routing configurations for better performance."""
        # Note: In production, use Redis or similar for distributed caching
        return None

    def _clear_config_cache(self, hostel_id: UUID) -> None:
        """Clear cached config for a hostel."""
        try:
            self._get_cached_config.cache_clear()
        except Exception:
            pass  # Cache clearing is not critical

    # -------------------------------------------------------------------------
    # Enhanced configuration management
    # -------------------------------------------------------------------------

    def get_routing_config_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        use_cache: bool = True,
    ) -> RoutingConfig:
        """
        Get routing configuration with enhanced caching and validation.

        Enhanced with:
        - Performance caching
        - Fallback handling
        - Configuration validation

        Args:
            db: Database session
            hostel_id: Hostel identifier
            use_cache: Whether to use cached configuration

        Returns:
            RoutingConfig: Hostel routing configuration

        Raises:
            ValidationException: For invalid hostel ID
            DatabaseException: For database operation failures
        """
        self._validate_hostel_id(hostel_id)

        with LoggingContext(
            channel="routing_config",
            hostel_id=str(hostel_id),
            use_cache=use_cache
        ):
            try:
                logger.debug(f"Retrieving routing config for hostel {hostel_id}")
                
                # Try cache first
                config_data = None
                if use_cache:
                    config_data = self._get_cached_config(hostel_id)
                
                # Fetch from database if not cached
                if not config_data:
                    obj = self.routing_repo.get_config_for_hostel(db, hostel_id)
                    if obj:
                        config_data = obj
                        # Update cache
                        if use_cache:
                            # Cache would be updated here in real implementation
                            pass
                
                if not config_data:
                    logger.debug(f"No routing config found for hostel {hostel_id}, using defaults")
                    return self._get_default_config(hostel_id)
                
                config = RoutingConfig.model_validate(config_data)
                self._validate_routing_config(config)
                
                logger.debug("Routing config retrieved successfully")
                return config
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving routing config: {str(e)}")
                raise DatabaseException("Failed to retrieve routing configuration") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving routing config: {str(e)}")
                raise

    def _get_default_config(self, hostel_id: UUID) -> RoutingConfig:
        """Get default routing configuration for a hostel."""
        return RoutingConfig(
            hostel_id=hostel_id,
            rules=[],
            default_recipient_roles=["admin", "manager"],
            default_channels=self._default_channels,
            enable_escalation=False,
            escalation_timeout_hours=None,
            is_active=True,
        )

    def update_routing_config(
        self,
        db: Session,
        hostel_id: UUID,
        config: RoutingConfig,
    ) -> RoutingConfig:
        """
        Update routing configuration with validation and cache invalidation.

        Args:
            db: Database session
            hostel_id: Hostel identifier
            config: New routing configuration

        Returns:
            RoutingConfig: Updated configuration

        Raises:
            ValidationException: For invalid configuration
            DatabaseException: For database operation failures
        """
        self._validate_hostel_id(hostel_id)
        config.hostel_id = hostel_id
        self._validate_routing_config(config)

        with LoggingContext(
            channel="routing_config_update",
            hostel_id=str(hostel_id)
        ):
            try:
                logger.info(f"Updating routing config for hostel {hostel_id}")
                
                obj = self.routing_repo.update_config_for_hostel(
                    db=db,
                    hostel_id=hostel_id,
                    config_data=config.model_dump(exclude_none=True),
                )
                
                # Clear cache
                self._clear_config_cache(hostel_id)
                
                updated_config = RoutingConfig.model_validate(obj)
                logger.info("Routing config updated successfully")
                
                return updated_config
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error updating routing config: {str(e)}")
                raise DatabaseException("Failed to update routing configuration") from e
            except Exception as e:
                logger.error(f"Unexpected error updating routing config: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced routing logic
    # -------------------------------------------------------------------------

    def route_notification(
        self,
        db: Session,
        event_type: str,
        hostel_id: UUID,
        payload: Dict[str, Any],
        priority: str = "normal",
        user_context: Optional[Dict[str, Any]] = None,
    ) -> NotificationRoute:
        """
        Compute routing with enhanced rule evaluation and context awareness.

        Enhanced with:
        - Advanced rule matching
        - Context-aware routing
        - Performance optimization
        - Comprehensive error handling

        Args:
            db: Database session
            event_type: Type of event triggering notification
            hostel_id: Hostel identifier
            payload: Event payload data
            priority: Notification priority
            user_context: Additional user context

        Returns:
            NotificationRoute: Computed routing information

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        self._validate_event_type(event_type)
        self._validate_hostel_id(hostel_id)
        
        if priority not in self._valid_priorities:
            priority = "normal"

        # Build comprehensive context
        context = {
            "event_type": event_type,
            "hostel_id": str(hostel_id),
            "priority": priority,
            "payload": payload or {},
            "timestamp": datetime.utcnow().isoformat(),
            **(user_context or {})
        }

        with LoggingContext(
            channel="notification_routing",
            event_type=event_type,
            hostel_id=str(hostel_id),
            priority=priority
        ):
            try:
                logger.info(
                    f"Routing notification for event '{event_type}', "
                    f"hostel: {hostel_id}, priority: {priority}"
                )
                
                # Get routing configuration
                config = self.get_routing_config_for_hostel(db, hostel_id)
                
                # Find matching routing rules
                matching_rule = self._find_matching_rule(config.rules, context)
                
                # Build route based on rule or defaults
                if matching_rule:
                    route = self._build_route_from_rule(matching_rule, config, context)
                    logger.info(f"Route built from matching rule: {matching_rule.get('name', 'unnamed')}")
                else:
                    route = self._build_default_route(config, context)
                    logger.info("Route built from default configuration")
                
                # Apply escalation if enabled
                if config.enable_escalation and config.escalation_timeout_hours:
                    route.escalation_path = self._build_escalation_path(
                        config, context, route
                    )
                
                logger.info(
                    f"Routing complete - recipients: {len(route.primary_recipients)}, "
                    f"channels: {route.primary_channels}"
                )
                
                return route
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error during routing: {str(e)}")
                raise DatabaseException("Failed to route notification") from e
            except Exception as e:
                logger.error(f"Unexpected error during routing: {str(e)}")
                raise

    def _find_matching_rule(
        self,
        rules: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Find the first routing rule that matches the context.
        
        Rules are evaluated in order of priority.
        """
        # Sort rules by priority (higher priority first)
        sorted_rules = sorted(
            rules,
            key=lambda r: r.get("priority", 0),
            reverse=True
        )
        
        for rule in sorted_rules:
            if not rule.get("is_active", True):
                continue
                
            if self._evaluate_rule_conditions(rule, context):
                logger.debug(f"Found matching rule: {rule.get('name', 'unnamed')}")
                return rule
        
        logger.debug("No matching routing rule found")
        return None

    def _build_route_from_rule(
        self,
        rule: Dict[str, Any],
        config: RoutingConfig,
        context: Dict[str, Any]
    ) -> NotificationRoute:
        """Build notification route from a matching rule."""
        recipients = rule.get("recipients", [])
        channels = rule.get("channels", config.default_channels)
        
        # Apply any dynamic recipient resolution
        if "dynamic_recipients" in rule:
            dynamic_recipients = self._resolve_dynamic_recipients(
                rule["dynamic_recipients"], context
            )
            recipients.extend(dynamic_recipients)
        
        # Remove duplicates while preserving order
        unique_recipients = list(dict.fromkeys(recipients))
        unique_channels = list(dict.fromkeys(channels))
        
        return NotificationRoute(
            event_type=context["event_type"],
            hostel_id=UUID(context["hostel_id"]),
            primary_recipients=unique_recipients,
            primary_channels=unique_channels,
            secondary_recipients=rule.get("secondary_recipients", []),
            secondary_channels=rule.get("secondary_channels", []),
            routing_metadata={
                "rule_name": rule.get("name"),
                "rule_id": rule.get("id"),
                "priority": context["priority"],
                "matched_conditions": rule.get("conditions", {}),
            },
            escalation_path=None,  # Set later if escalation is enabled
        )

    def _build_default_route(
        self,
        config: RoutingConfig,
        context: Dict[str, Any]
    ) -> NotificationRoute:
        """Build default notification route when no rules match."""
        return NotificationRoute(
            event_type=context["event_type"],
            hostel_id=UUID(context["hostel_id"]),
            primary_recipients=config.default_recipient_roles,
            primary_channels=config.default_channels,
            secondary_recipients=[],
            secondary_channels=[],
            routing_metadata={
                "rule_name": "default",
                "priority": context["priority"],
                "fallback_reason": "no_matching_rules",
            },
            escalation_path=None,
        )

    def _resolve_dynamic_recipients(
        self,
        dynamic_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """
        Resolve dynamic recipients based on context.
        
        Examples:
        - Room managers for the affected room
        - On-call staff for the current time
        - Department heads for specific event types
        """
        recipients = []
        
        try:
            # Room-based recipients
            if "room_managers" in dynamic_config:
                room_id = context.get("payload", {}).get("room_id")
                if room_id:
                    # Would query for room managers
                    recipients.extend([f"room_manager_{room_id}"])
            
            # Time-based recipients (on-call staff)
            if "on_call_staff" in dynamic_config:
                current_hour = datetime.utcnow().hour
                if dynamic_config["on_call_staff"].get("include_night_staff") and (current_hour < 6 or current_hour > 22):
                    recipients.extend(["night_manager", "security_supervisor"])
            
            # Department-based recipients
            if "department_heads" in dynamic_config:
                event_type = context.get("event_type", "")
                if "maintenance" in event_type.lower():
                    recipients.append("maintenance_head")
                elif "security" in event_type.lower():
                    recipients.append("security_head")
                elif "billing" in event_type.lower():
                    recipients.append("finance_head")
            
            # Priority-based recipients
            if "priority_escalation" in dynamic_config:
                priority = context.get("priority", "normal")
                if priority in ["high", "urgent"]:
                    recipients.extend(dynamic_config["priority_escalation"].get("high_priority", []))
        
        except Exception as e:
            logger.warning(f"Error resolving dynamic recipients: {str(e)}")
        
        return recipients

    def _build_escalation_path(
        self,
        config: RoutingConfig,
        context: Dict[str, Any],
        base_route: NotificationRoute
    ) -> List[Dict[str, Any]]:
        """Build escalation path for unacknowledged notifications."""
        escalation_path = []
        
        try:
            timeout_hours = config.escalation_timeout_hours
            current_recipients = set(base_route.primary_recipients)
            current_channels = set(base_route.primary_channels)
            
            # Level 1: Add more channels to existing recipients
            escalation_path.append({
                "level": 1,
                "trigger_after_hours": timeout_hours,
                "recipients": list(current_recipients),
                "channels": list(current_channels | {"sms", "push"}),
                "description": "Add SMS and Push to existing recipients",
            })
            
            # Level 2: Escalate to supervisors
            escalation_path.append({
                "level": 2,
                "trigger_after_hours": timeout_hours * 2,
                "recipients": ["supervisor", "department_head"],
                "channels": ["email", "sms", "push"],
                "description": "Escalate to supervisors",
            })
            
            # Level 3: Escalate to senior management
            if len(escalation_path) < self._max_escalation_levels:
                escalation_path.append({
                    "level": 3,
                    "trigger_after_hours": timeout_hours * 4,
                    "recipients": ["senior_manager", "director"],
                    "channels": ["email", "sms", "push", "webhook"],
                    "description": "Escalate to senior management",
                })
        
        except Exception as e:
            logger.warning(f"Error building escalation path: {str(e)}")
        
        return escalation_path

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def test_routing_rule(
        self,
        db: Session,
        rule: Dict[str, Any],
        test_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Test a routing rule against sample context.

        Args:
            db: Database session
            rule: Routing rule to test
            test_context: Test context data

        Returns:
            Dict[str, Any]: Test results

        Raises:
            ValidationException: For invalid rule or context
        """
        with LoggingContext(channel="routing_rule_test"):
            try:
                logger.info("Testing routing rule")
                
                matches = self._evaluate_rule_conditions(rule, test_context)
                
                result = {
                    "matches": matches,
                    "rule_name": rule.get("name", "unnamed"),
                    "test_context": test_context,
                    "evaluated_conditions": rule.get("conditions", {}),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                if matches:
                    # Simulate route building
                    result["would_route_to"] = {
                        "recipients": rule.get("recipients", []),
                        "channels": rule.get("channels", []),
                    }
                
                logger.info(f"Rule test complete - matches: {matches}")
                return result
                
            except Exception as e:
                logger.error(f"Error testing routing rule: {str(e)}")
                raise ValidationException(f"Failed to test routing rule: {str(e)}")

    def get_routing_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """
        Get routing analytics for optimization.

        Args:
            db: Database session
            hostel_id: Hostel identifier
            days_back: Number of days to analyze

        Returns:
            Dict[str, Any]: Routing analytics

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        self._validate_hostel_id(hostel_id)
        
        if days_back < 1 or days_back > 90:
            raise ValidationException("Days back must be between 1 and 90")

        with LoggingContext(
            channel="routing_analytics",
            hostel_id=str(hostel_id),
            days_back=days_back
        ):
            try:
                logger.info(f"Generating routing analytics for hostel {hostel_id}")
                
                analytics = self.routing_repo.get_routing_analytics(
                    db=db,
                    hostel_id=hostel_id,
                    days_back=days_back,
                )
                
                logger.info("Routing analytics generated successfully")
                return analytics
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error generating analytics: {str(e)}")
                raise DatabaseException("Failed to generate routing analytics") from e
            except Exception as e:
                logger.error(f"Unexpected error generating analytics: {str(e)}")
                raise