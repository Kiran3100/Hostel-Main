# --- File: C:\Hostel-Main\app\repositories\notification\notification_routing_repository.py ---
"""
Notification Routing Repository for intelligent routing and escalation.

Handles routing rules, escalation paths, decision tracking, and automated
escalation with comprehensive analytics and performance monitoring.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import json

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification_routing import (
    RoutingRule,
    EscalationPath,
    NotificationEscalation,
    NotificationRoute
)
from app.models.notification.notification import Notification
from app.models.hostel.hostel import Hostel
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import Priority, UserRole


class ActiveRoutingRulesSpec(Specification):
    """Specification for active routing rules."""
    
    def __init__(self, hostel_id: Optional[UUID] = None):
        self.hostel_id = hostel_id
    
    def is_satisfied_by(self, query):
        conditions = [RoutingRule.is_active == True]
        if self.hostel_id:
            conditions.append(
                or_(
                    RoutingRule.hostel_id == self.hostel_id,
                    RoutingRule.hostel_id.is_(None)  # Global rules
                )
            )
        return query.filter(and_(*conditions))


class PendingEscalationsSpec(Specification):
    """Specification for escalations ready for next level."""
    
    def is_satisfied_by(self, query):
        return query.filter(
            and_(
                NotificationEscalation.is_resolved == False,
                NotificationEscalation.next_escalation_at <= datetime.utcnow()
            )
        )


class NotificationRoutingRepository(BaseRepository[RoutingRule]):
    """
    Repository for notification routing and escalation management.
    """

    def __init__(self, db_session: Session):
        super().__init__(RoutingRule, db_session)

    # Routing rule management
    def create_routing_rule(
        self,
        rule_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> RoutingRule:
        """Create new routing rule with validation."""
        # Validate recipients
        if not any([
            rule_data.get('recipient_roles'),
            rule_data.get('specific_users'),
            rule_data.get('recipient_groups')
        ]):
            raise ValueError("At least one recipient type must be specified")
        
        # Validate channels
        if not rule_data.get('channels'):
            raise ValueError("At least one notification channel must be specified")
        
        rule_data['hostel_id'] = hostel_id
        rule = RoutingRule(**rule_data)
        
        return self.create(rule)

    def find_matching_rules(
        self,
        notification_context: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> List[RoutingRule]:
        """Find routing rules that match notification context."""
        query = self.db_session.query(RoutingRule).filter(
            and_(
                RoutingRule.is_active == True,
                or_(
                    RoutingRule.hostel_id == hostel_id,
                    RoutingRule.hostel_id.is_(None)  # Global rules
                )
            )
        ).order_by(desc(RoutingRule.rule_priority))
        
        matching_rules = []
        for rule in query.all():
            if self._evaluate_rule_conditions(rule.conditions, notification_context):
                matching_rules.append(rule)
                if rule.stop_on_match:
                    break
        
        return matching_rules

    def apply_routing_rule(
        self,
        notification_id: UUID,
        rule: RoutingRule,
        routing_context: Dict[str, Any]
    ) -> NotificationRoute:
        """Apply routing rule and create route record."""
        # Resolve recipients
        primary_recipients = self._resolve_recipients(
            rule.recipient_roles,
            rule.specific_users,
            rule.recipient_groups,
            routing_context.get('hostel_id')
        )
        
        # Create route record
        route = NotificationRoute(
            notification_id=notification_id,
            matched_rule_id=rule.id,
            matched_rule_name=rule.rule_name,
            primary_recipients=primary_recipients,
            channels=rule.channels,
            template_code=rule.template_code,
            routing_metadata=routing_context
        )
        
        self.db_session.add(route)
        self.db_session.commit()
        
        return route

    def test_routing_rules(
        self,
        test_context: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Test routing rules against context without applying them."""
        matching_rules = self.find_matching_rules(test_context, hostel_id)
        
        results = []
        for rule in matching_rules:
            recipients = self._resolve_recipients(
                rule.recipient_roles,
                rule.specific_users,
                rule.recipient_groups,
                hostel_id
            )
            
            results.append({
                'rule_id': str(rule.id),
                'rule_name': rule.rule_name,
                'priority': rule.rule_priority,
                'matched_conditions': self._get_matched_conditions(rule.conditions, test_context),
                'recipients': [str(uid) for uid in recipients],
                'channels': rule.channels,
                'template_code': rule.template_code,
                'stop_on_match': rule.stop_on_match
            })
        
        return results

    # Escalation management
    def create_escalation_path(
        self,
        path_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> EscalationPath:
        """Create escalation path with level validation."""
        # Validate escalation levels
        levels = path_data.get('levels', [])
        if not levels:
            raise ValueError("Escalation path must have at least one level")
        
        # Validate level structure
        for i, level in enumerate(levels):
            required_fields = ['level', 'escalate_after_hours', 'recipients']
            if not all(field in level for field in required_fields):
                raise ValueError(f"Level {i+1} missing required fields: {required_fields}")
            
            if level['level'] != i + 1:
                raise ValueError(f"Level numbers must be sequential starting from 1")
        
        path_data['hostel_id'] = hostel_id
        escalation_path = EscalationPath(**path_data)
        
        return self.create(escalation_path)

    def initiate_escalation(
        self,
        notification_id: UUID,
        escalation_path_id: UUID,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> NotificationEscalation:
        """Start escalation process for notification."""
        escalation_path = self.db_session.query(EscalationPath).filter(
            EscalationPath.id == escalation_path_id
        ).first()
        
        if not escalation_path:
            raise ValueError("Escalation path not found")
        
        if not escalation_path.is_active:
            raise ValueError("Escalation path is not active")
        
        escalation = NotificationEscalation(
            notification_id=notification_id,
            escalation_path_id=escalation_path_id,
            current_level=0,
            max_level=len(escalation_path.levels),
            escalation_history=[{
                'action': 'escalation_initiated',
                'timestamp': datetime.utcnow().isoformat(),
                'context': initial_context or {}
            }]
        )
        
        # Schedule first escalation
        first_level = escalation_path.levels[0]
        escalation.next_escalation_at = datetime.utcnow() + timedelta(
            hours=first_level['escalate_after_hours']
        )
        
        self.db_session.add(escalation)
        self.db_session.commit()
        
        return escalation

    def process_escalations(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Process pending escalations."""
        pending_escalations = self.db_session.query(NotificationEscalation).filter(
            and_(
                NotificationEscalation.is_resolved == False,
                NotificationEscalation.next_escalation_at <= datetime.utcnow(),
                NotificationEscalation.current_level < NotificationEscalation.max_level
            )
        ).limit(batch_size).all()
        
        processed = []
        for escalation in pending_escalations:
            result = self._escalate_to_next_level(escalation)
            processed.append(result)
        
        self.db_session.commit()
        return processed

    def resolve_escalation(
        self,
        escalation_id: UUID,
        resolved_by_id: UUID,
        resolution_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark escalation as resolved."""
        escalation = self.db_session.query(NotificationEscalation).filter(
            NotificationEscalation.id == escalation_id
        ).first()
        
        if not escalation:
            return False
        
        escalation.is_resolved = True
        escalation.resolved_at = datetime.utcnow()
        escalation.resolved_by_id = resolved_by_id
        
        # Add to escalation history
        history_entry = {
            'action': 'escalation_resolved',
            'timestamp': datetime.utcnow().isoformat(),
            'resolved_by': str(resolved_by_id),
            'level_when_resolved': escalation.current_level,
            'context': resolution_context or {}
        }
        
        escalation.escalation_history = escalation.escalation_history + [history_entry]
        
        self.db_session.commit()
        return True

    # Analytics and monitoring
    def get_routing_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get comprehensive routing analytics."""
        base_query = self.db_session.query(NotificationRoute)
        
        if hostel_id:
            base_query = base_query.join(
                Notification, NotificationRoute.notification_id == Notification.id
            ).filter(Notification.hostel_id == hostel_id)
        
        base_query = base_query.join(
            Notification, NotificationRoute.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        # Rule usage statistics
        rule_stats = base_query.with_entities(
            NotificationRoute.matched_rule_name,
            func.count().label('usage_count'),
            func.array_agg(NotificationRoute.channels).label('channels_used')
        ).group_by(NotificationRoute.matched_rule_name).all()
        
        # Channel distribution
        channel_stats = self.db_session.query(
            func.unnest(NotificationRoute.channels).label('channel'),
            func.count().label('usage_count')
        ).select_from(
            base_query.subquery()
        ).group_by('channel').all()
        
        # Template usage
        template_stats = base_query.with_entities(
            NotificationRoute.template_code,
            func.count().label('usage_count')
        ).filter(
            NotificationRoute.template_code.isnot(None)
        ).group_by(NotificationRoute.template_code).all()
        
        return {
            'rule_performance': [
                {
                    'rule_name': stat.matched_rule_name,
                    'usage_count': stat.usage_count,
                    'channels_used': list(set([ch for channels in stat.channels_used for ch in channels]))
                }
                for stat in rule_stats
            ],
            'channel_distribution': [
                {
                    'channel': stat.channel,
                    'usage_count': stat.usage_count
                }
                for stat in channel_stats
            ],
            'template_usage': [
                {
                    'template_code': stat.template_code,
                    'usage_count': stat.usage_count
                }
                for stat in template_stats
            ]
        }

    def get_escalation_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get escalation performance analytics."""
        base_query = self.db_session.query(NotificationEscalation).join(
            Notification, NotificationEscalation.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        # Escalation level statistics
        level_stats = base_query.with_entities(
            NotificationEscalation.current_level,
            func.count().label('escalation_count'),
            func.sum(
                case([(NotificationEscalation.is_resolved == True, 1)], else_=0)
            ).label('resolved_count'),
            func.avg(
                func.extract('epoch', 
                    NotificationEscalation.resolved_at - 
                    NotificationEscalation.created_at
                )
            ).label('avg_resolution_time')
        ).group_by(NotificationEscalation.current_level).all()
        
        # Path performance
        path_stats = base_query.join(
            EscalationPath, NotificationEscalation.escalation_path_id == EscalationPath.id
        ).with_entities(
            EscalationPath.path_name,
            EscalationPath.event_type,
            func.count().label('total_escalations'),
            func.sum(
                case([(NotificationEscalation.is_resolved == True, 1)], else_=0)
            ).label('resolved_escalations'),
            func.avg(NotificationEscalation.current_level).label('avg_escalation_level')
        ).group_by(
            EscalationPath.path_name,
            EscalationPath.event_type
        ).all()
        
        # Resolution patterns
        total_escalations = base_query.count()
        resolved_escalations = base_query.filter(
            NotificationEscalation.is_resolved == True
        ).count()
        
        return {
            'summary': {
                'total_escalations': total_escalations,
                'resolved_escalations': resolved_escalations,
                'resolution_rate': (resolved_escalations / total_escalations * 100) if total_escalations > 0 else 0
            },
            'level_performance': [
                {
                    'level': stat.current_level,
                    'escalation_count': stat.escalation_count,
                    'resolved_count': stat.resolved_count,
                    'resolution_rate': (stat.resolved_count / stat.escalation_count * 100) if stat.escalation_count > 0 else 0,
                    'avg_resolution_time_hours': (stat.avg_resolution_time / 3600) if stat.avg_resolution_time else 0
                }
                for stat in level_stats
            ],
            'path_performance': [
                {
                    'path_name': stat.path_name,
                    'event_type': stat.event_type,
                    'total_escalations': stat.total_escalations,
                    'resolved_escalations': stat.resolved_escalations,
                    'resolution_rate': (stat.resolved_escalations / stat.total_escalations * 100) if stat.total_escalations > 0 else 0,
                    'avg_escalation_level': float(stat.avg_escalation_level or 0)
                }
                for stat in path_stats
            ]
        }

    def get_routing_performance_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get routing performance metrics."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Rule effectiveness
        rule_effectiveness = self.db_session.query(
            RoutingRule.rule_name,
            RoutingRule.rule_priority,
            func.count(NotificationRoute.id).label('usage_count'),
            func.avg(
                func.extract('epoch',
                    Notification.delivered_at - Notification.created_at
                )
            ).label('avg_delivery_time'),
            func.sum(
                case([(Notification.read_at.isnot(None), 1)], else_=0)
            ).label('read_count')
        ).join(
            NotificationRoute, RoutingRule.id == NotificationRoute.matched_rule_id
        ).join(
            Notification, NotificationRoute.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            rule_effectiveness = rule_effectiveness.filter(
                or_(
                    RoutingRule.hostel_id == hostel_id,
                    RoutingRule.hostel_id.is_(None)
                )
            )
        
        rule_effectiveness = rule_effectiveness.group_by(
            RoutingRule.rule_name,
            RoutingRule.rule_priority
        ).all()
        
        # Escalation trends
        escalation_trends = self.db_session.query(
            func.date(NotificationEscalation.created_at).label('date'),
            func.count().label('new_escalations'),
            func.sum(
                case([(NotificationEscalation.is_resolved == True, 1)], else_=0)
            ).label('resolved_escalations')
        ).join(
            Notification, NotificationEscalation.notification_id == Notification.id
        ).filter(
            and_(
                NotificationEscalation.created_at >= start_date,
                NotificationEscalation.created_at <= end_date
            )
        )
        
        if hostel_id:
            escalation_trends = escalation_trends.filter(
                Notification.hostel_id == hostel_id
            )
        
        escalation_trends = escalation_trends.group_by(
            func.date(NotificationEscalation.created_at)
        ).order_by(func.date(NotificationEscalation.created_at)).all()
        
        return {
            'rule_effectiveness': [
                {
                    'rule_name': rule.rule_name,
                    'priority': rule.rule_priority,
                    'usage_count': rule.usage_count,
                    'avg_delivery_time_seconds': rule.avg_delivery_time or 0,
                    'read_count': rule.read_count,
                    'engagement_rate': (rule.read_count / rule.usage_count * 100) if rule.usage_count > 0 else 0
                }
                for rule in rule_effectiveness
            ],
            'escalation_trends': [
                {
                    'date': trend.date.isoformat(),
                    'new_escalations': trend.new_escalations,
                    'resolved_escalations': trend.resolved_escalations,
                    'resolution_rate': (trend.resolved_escalations / trend.new_escalations * 100) if trend.new_escalations > 0 else 0
                }
                for trend in escalation_trends
            ]
        }

    # Helper methods
    def _evaluate_rule_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate if routing rule conditions match context."""
        if not conditions:
            return True
        
        for condition_key, condition_value in conditions.items():
            context_value = context.get(condition_key)
            
            if isinstance(condition_value, dict):
                # Handle complex conditions (e.g., {"operator": "in", "values": [...]})
                operator = condition_value.get('operator', 'equals')
                values = condition_value.get('values', condition_value.get('value'))
                
                if operator == 'equals':
                    if context_value != values:
                        return False
                elif operator == 'in':
                    if context_value not in values:
                        return False
                elif operator == 'not_in':
                    if context_value in values:
                        return False
                elif operator == 'greater_than':
                    if not (context_value and context_value > values):
                        return False
                elif operator == 'less_than':
                    if not (context_value and context_value < values):
                        return False
            else:
                # Simple equality check
                if context_value != condition_value:
                    return False
        
        return True

    def _get_matched_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """Get list of conditions that matched for debugging."""
        matched = []
        
        if not conditions:
            return ['no_conditions']
        
        for condition_key, condition_value in conditions.items():
            context_value = context.get(condition_key)
            
            if isinstance(condition_value, dict):
                operator = condition_value.get('operator', 'equals')
                values = condition_value.get('values', condition_value.get('value'))
                matched.append(f"{condition_key} {operator} {values} (got: {context_value})")
            else:
                matched.append(f"{condition_key} == {condition_value} (got: {context_value})")
        
        return matched

    def _resolve_recipients(
        self,
        recipient_roles: List[str],
        specific_users: List[UUID],
        recipient_groups: List[str],
        hostel_id: Optional[UUID] = None
    ) -> List[UUID]:
        """Resolve recipients from roles, specific users, and groups."""
        recipients = set()
        
        # Add specific users
        if specific_users:
            recipients.update(specific_users)
        
        # Add users by roles
        if recipient_roles:
            role_users = self.db_session.query(User.id).filter(
                User.role.in_(recipient_roles)
            )
            
            if hostel_id:
                # Filter by hostel association if needed
                # This would depend on your user-hostel relationship model
                pass
            
            recipients.update([user.id for user in role_users.all()])
        
        # Add users by groups (implementation depends on group model)
        if recipient_groups:
            # This would be implemented based on your group/team model
            pass
        
        return list(recipients)

    def _escalate_to_next_level(self, escalation: NotificationEscalation) -> Dict[str, Any]:
        """Escalate notification to next level."""
        escalation_path = escalation.escalation_path
        
        if not escalation_path or escalation.current_level >= escalation.max_level:
            return {
                'escalation_id': str(escalation.id),
                'status': 'max_level_reached',
                'current_level': escalation.current_level
            }
        
        # Move to next level
        escalation.current_level += 1
        current_level_config = escalation_path.levels[escalation.current_level - 1]
        
        # Update escalation history
        history_entry = {
            'action': 'escalated_to_level',
            'timestamp': datetime.utcnow().isoformat(),
            'level': escalation.current_level,
            'level_config': current_level_config
        }
        
        escalation.escalation_history = escalation.escalation_history + [history_entry]
        escalation.last_escalated_at = datetime.utcnow()
        
        # Schedule next escalation if not at max level
        if escalation.current_level < escalation.max_level:
            next_level_config = escalation_path.levels[escalation.current_level]
            escalation.next_escalation_at = datetime.utcnow() + timedelta(
                hours=next_level_config['escalate_after_hours']
            )
        else:
            escalation.next_escalation_at = None
        
        return {
            'escalation_id': str(escalation.id),
            'status': 'escalated',
            'current_level': escalation.current_level,
            'next_escalation_at': escalation.next_escalation_at.isoformat() if escalation.next_escalation_at else None,
            'recipients': current_level_config.get('recipients', [])
        }

    def find_unused_rules(self, days: int = 90) -> List[RoutingRule]:
        """Find routing rules that haven't been used recently."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        used_rule_ids = self.db_session.query(NotificationRoute.matched_rule_id).join(
            Notification, NotificationRoute.notification_id == Notification.id
        ).filter(
            Notification.created_at >= cutoff_date
        ).distinct().subquery()
        
        return self.db_session.query(RoutingRule).filter(
            and_(
                RoutingRule.is_active == True,
                ~RoutingRule.id.in_(used_rule_ids)
            )
        ).all()

    def optimize_routing_rules(self, hostel_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Analyze and suggest routing rule optimizations."""
        recommendations = []
        
        # Find conflicting rules
        rules = self.db_session.query(RoutingRule).filter(
            RoutingRule.is_active == True
        )
        
        if hostel_id:
            rules = rules.filter(
                or_(
                    RoutingRule.hostel_id == hostel_id,
                    RoutingRule.hostel_id.is_(None)
                )
            )
        
        rules = rules.order_by(desc(RoutingRule.rule_priority)).all()
        
        # Check for rule conflicts and overlaps
        for i, rule1 in enumerate(rules):
            for rule2 in rules[i+1:]:
                if self._rules_overlap(rule1.conditions, rule2.conditions):
                    recommendations.append({
                        'type': 'rule_overlap',
                        'rule1': rule1.rule_name,
                        'rule2': rule2.rule_name,
                        'suggestion': f"Rules '{rule1.rule_name}' and '{rule2.rule_name}' have overlapping conditions. Consider consolidating or adjusting priorities."
                    })
        
        # Find unused rules
        unused_rules = self.find_unused_rules()
        if unused_rules:
            recommendations.extend([
                {
                    'type': 'unused_rule',
                    'rule_name': rule.rule_name,
                    'suggestion': f"Rule '{rule.rule_name}' hasn't been used recently. Consider deactivating or reviewing conditions."
                }
                for rule in unused_rules
            ])
        
        return {
            'recommendations': recommendations,
            'total_rules': len(rules),
            'unused_rules_count': len(unused_rules)
        }

    def _rules_overlap(self, conditions1: Dict[str, Any], conditions2: Dict[str, Any]) -> bool:
        """Check if two rule condition sets overlap."""
        if not conditions1 or not conditions2:
            return True  # Empty conditions match everything
        
        # Simple overlap detection - can be made more sophisticated
        common_keys = set(conditions1.keys()) & set(conditions2.keys())
        
        for key in common_keys:
            val1, val2 = conditions1[key], conditions2[key]
            
            # If both are simple values and equal, there's overlap
            if not isinstance(val1, dict) and not isinstance(val2, dict):
                if val1 == val2:
                    return True
            
            # More complex overlap detection for dict conditions would go here
        
        return False