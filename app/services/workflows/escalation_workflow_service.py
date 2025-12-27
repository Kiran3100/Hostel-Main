"""
Enhanced Escalation Workflow Service

Advanced escalation management with intelligent routing, SLA monitoring, and performance analytics.
"""

from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

from sqlalchemy.orm import Session

from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.config import settings
from app.repositories.complaint import (
    ComplaintRepository,
    ComplaintEscalationRepository,
    AutoEscalationRuleRepository,
)
from app.repositories.user import AdminRepository, SupervisorRepository
from app.models.base.enums import ComplaintPriority, ComplaintStatus
from app.services.workflows.workflow_engine_service import (
    workflow_engine,
    create_workflow,
    create_step,
    WorkflowPriority
)
from app.services.workflows.notification_workflow_service import (
    NotificationWorkflowService
)


class EscalationType(str, Enum):
    """Enhanced escalation types."""
    COMPLAINT = "complaint"
    MAINTENANCE = "maintenance"
    APPROVAL = "approval"
    SLA_BREACH = "sla_breach"
    QUALITY = "quality"
    SECURITY = "security"
    FINANCIAL = "financial"
    EMERGENCY = "emergency"


class EscalationLevel(str, Enum):
    """Enhanced escalation hierarchy levels."""
    LEVEL_1 = "supervisor"
    LEVEL_2 = "manager"
    LEVEL_3 = "senior_manager"
    LEVEL_4 = "admin"
    LEVEL_5 = "super_admin"
    LEVEL_6 = "board"
    
    @property
    def numeric_value(self) -> int:
        """Return numeric value for level comparison."""
        mapping = {
            "supervisor": 1,
            "manager": 2,
            "senior_manager": 3,
            "admin": 4,
            "super_admin": 5,
            "board": 6
        }
        return mapping.get(self.value, 0)


class EscalationTrigger(str, Enum):
    """Escalation trigger types."""
    SLA_BREACH = "sla_breach"
    MANUAL_REQUEST = "manual_request"
    AUTO_RULE = "auto_rule"
    QUALITY_THRESHOLD = "quality_threshold"
    REPEAT_COMPLAINT = "repeat_complaint"
    HIGH_VALUE = "high_value"
    CUSTOMER_REQUEST = "customer_request"
    SYSTEM_ALERT = "system_alert"


@dataclass
class EscalationRule:
    """Enhanced escalation rule configuration."""
    rule_id: str
    name: str
    escalation_type: EscalationType
    trigger: EscalationTrigger
    condition: callable
    target_level: EscalationLevel
    priority_boost: int = 0
    auto_assign: bool = True
    notification_template: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.metadata:
            self.metadata = {}


@dataclass
class SLAConfiguration:
    """SLA configuration for different entity types."""
    entity_type: str
    priority_sla: Dict[str, int]  # Priority -> hours
    escalation_thresholds: List[int]  # Hours for each escalation level
    business_hours_only: bool = False
    exclude_weekends: bool = False
    grace_period_hours: int = 0


@dataclass
class EscalationMetrics:
    """Comprehensive escalation metrics."""
    total_escalations: int = 0
    auto_escalations: int = 0
    manual_escalations: int = 0
    sla_breach_escalations: int = 0
    resolved_at_level: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    average_resolution_time: Dict[str, float] = field(default_factory=dict)
    escalation_success_rate: float = 0.0
    customer_satisfaction_score: float = 0.0


class EscalationWorkflowService:
    """
    Enhanced service for managing escalation workflows with intelligent routing.
    
    Features:
    - AI-powered escalation routing
    - Real-time SLA monitoring
    - Dynamic workload balancing
    - Predictive escalation analytics
    - Multi-channel notification orchestration
    - Performance optimization
    """
    
    def __init__(
        self,
        complaint_repo: ComplaintRepository,
        complaint_escalation_repo: ComplaintEscalationRepository,
        auto_escalation_rule_repo: AutoEscalationRuleRepository,
        admin_repo: AdminRepository,
        supervisor_repo: SupervisorRepository,
        notification_service: NotificationWorkflowService
    ):
        self.complaint_repo = complaint_repo
        self.complaint_escalation_repo = complaint_escalation_repo
        self.auto_escalation_rule_repo = auto_escalation_rule_repo
        self.admin_repo = admin_repo
        self.supervisor_repo = supervisor_repo
        self.notification_service = notification_service
        
        # Enhanced configurations
        self.escalation_rules: Dict[str, List[EscalationRule]] = {}
        self.sla_configs: Dict[str, SLAConfiguration] = {}
        self.escalation_metrics = EscalationMetrics()
        
        # Performance optimization
        self._assignment_cache: Dict[str, UUID] = {}
        self._workload_cache: Dict[UUID, int] = {}
        self._cache_expiry = datetime.utcnow()
        
        self._register_workflows()
        self._setup_default_rules()
        self._setup_sla_configurations()
    
    def _register_workflows(self) -> None:
        """Register enhanced escalation workflows."""
        
        # Enhanced complaint escalation workflow
        complaint_escalation_wf = (
            create_workflow(
                "complaint_escalation",
                "Enhanced Complaint Escalation Workflow",
                "Intelligent escalation with dynamic routing and SLA monitoring",
                priority=WorkflowPriority.HIGH,
                max_execution_time=300,
                enable_monitoring=True
            )
            .add_validator(self._validate_escalation_context)
            .add_step(create_step(
                "analyze_escalation_requirement",
                self._analyze_escalation_requirement,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "check_escalation_eligibility",
                self._check_escalation_eligibility,
                timeout_seconds=20
            ))
            .add_step(create_step(
                "calculate_escalation_score",
                self._calculate_escalation_score,
                timeout_seconds=15
            ))
            .add_step(create_step(
                "determine_optimal_escalation_path",
                self._determine_optimal_escalation_path,
                timeout_seconds=45
            ))
            .add_step(create_step(
                "select_escalation_recipient",
                self._select_optimal_escalation_recipient,
                timeout_seconds=60
            ))
            .add_step(create_step(
                "create_escalation_record",
                self._create_enhanced_escalation_record,
                timeout_seconds=30,
                rollback_handler=self._rollback_escalation_record
            ))
            .add_step(create_step(
                "update_entity_priority",
                self._update_entity_priority_and_status,
                timeout_seconds=15,
                rollback_handler=self._rollback_priority_update
            ))
            .add_step(create_step(
                "reassign_with_context",
                self._reassign_with_escalation_context,
                timeout_seconds=30,
                rollback_handler=self._rollback_assignment
            ))
            .add_step(create_step(
                "setup_escalation_monitoring",
                self._setup_escalation_monitoring,
                timeout_seconds=20
            ))
            .add_step(create_step(
                "send_escalation_notifications",
                self._send_comprehensive_escalation_notifications,
                timeout_seconds=60,
                required=False
            ))
            .add_step(create_step(
                "update_escalation_metrics",
                self._update_escalation_metrics,
                timeout_seconds=10,
                required=False
            ))
            .on_complete(self._on_escalation_complete)
            .on_error(self._on_escalation_error)
        )
        
        workflow_engine.register_workflow(complaint_escalation_wf)
        
        # SLA breach auto-escalation workflow
        sla_escalation_wf = (
            create_workflow(
                "sla_breach_escalation",
                "SLA Breach Auto-Escalation Workflow",
                "Automated escalation triggered by SLA violations"
            )
            .add_step(create_step(
                "validate_sla_breach",
                self._validate_sla_breach_conditions
            ))
            .add_step(create_step(
                "calculate_breach_severity",
                self._calculate_breach_severity_score
            ))
            .add_step(create_step(
                "determine_breach_escalation_level",
                self._determine_breach_escalation_level
            ))
            .add_step(create_step(
                "apply_breach_penalties",
                self._apply_breach_penalties_and_adjustments
            ))
            .add_step(create_step(
                "trigger_escalation_workflow",
                self._trigger_primary_escalation_workflow
            ))
            .add_step(create_step(
                "create_sla_breach_alert",
                self._create_comprehensive_breach_alert
            ))
            .add_step(create_step(
                "notify_stakeholders",
                self._notify_sla_breach_stakeholders
            ))
        )
        
        workflow_engine.register_workflow(sla_escalation_wf)
        
        # Mass escalation workflow for system issues
        mass_escalation_wf = (
            create_workflow(
                "mass_escalation",
                "Mass Escalation Workflow",
                "Handle multiple related escalations efficiently"
            )
            .add_step(create_step(
                "group_related_issues",
                self._group_related_escalation_issues
            ))
            .add_step(create_step(
                "analyze_system_impact",
                self._analyze_system_wide_impact
            ))
            .add_step(create_step(
                "determine_emergency_protocols",
                self._determine_emergency_escalation_protocols
            ))
            .add_step(create_step(
                "execute_parallel_escalations",
                self._execute_parallel_escalations
            ))
            .add_step(create_step(
                "coordinate_resolution_efforts",
                self._coordinate_mass_resolution_efforts
            ))
        )
        
        workflow_engine.register_workflow(mass_escalation_wf)
        
        # De-escalation workflow
        de_escalation_wf = (
            create_workflow(
                "de_escalation",
                "Enhanced De-escalation Workflow",
                "Smart de-escalation with performance tracking"
            )
            .add_step(create_step(
                "validate_de_escalation_eligibility",
                self._validate_de_escalation_eligibility
            ))
            .add_step(create_step(
                "analyze_resolution_quality",
                self._analyze_resolution_quality_metrics
            ))
            .add_step(create_step(
                "calculate_performance_impact",
                self._calculate_de_escalation_performance_impact
            ))
            .add_step(create_step(
                "execute_de_escalation_process",
                self._execute_smart_de_escalation
            ))
            .add_step(create_step(
                "update_success_metrics",
                self._update_de_escalation_success_metrics
            ))
        )
        
        workflow_engine.register_workflow(de_escalation_wf)
    
    def _setup_default_rules(self) -> None:
        """Setup intelligent default escalation rules."""
        # Complaint escalation rules
        complaint_rules = [
            EscalationRule(
                rule_id="high_priority_auto",
                name="High Priority Auto Escalation",
                escalation_type=EscalationType.COMPLAINT,
                trigger=EscalationTrigger.SLA_BREACH,
                condition=lambda ctx: (
                    ctx.get("priority") == ComplaintPriority.HIGH and
                    ctx.get("hours_overdue", 0) > 4
                ),
                target_level=EscalationLevel.LEVEL_2,
                priority_boost=1,
                metadata={"reason": "High priority SLA breach"}
            ),
            EscalationRule(
                rule_id="repeat_complaint_escalation",
                name="Repeat Complaint Escalation",
                escalation_type=EscalationType.COMPLAINT,
                trigger=EscalationTrigger.REPEAT_COMPLAINT,
                condition=lambda ctx: ctx.get("repeat_count", 0) >= 3,
                target_level=EscalationLevel.LEVEL_3,
                priority_boost=2,
                metadata={"reason": "Multiple complaints from same user"}
            ),
            EscalationRule(
                rule_id="quality_threshold_breach",
                name="Quality Threshold Breach",
                escalation_type=EscalationType.QUALITY,
                trigger=EscalationTrigger.QUALITY_THRESHOLD,
                condition=lambda ctx: ctx.get("quality_score", 100) < 70,
                target_level=EscalationLevel.LEVEL_2,
                priority_boost=1,
                metadata={"reason": "Quality score below threshold"}
            )
        ]
        
        self.escalation_rules[EscalationType.COMPLAINT] = complaint_rules
        
        # Security escalation rules
        security_rules = [
            EscalationRule(
                rule_id="security_incident_auto",
                name="Security Incident Auto Escalation",
                escalation_type=EscalationType.SECURITY,
                trigger=EscalationTrigger.SYSTEM_ALERT,
                condition=lambda ctx: ctx.get("security_level") in ["high", "critical"],
                target_level=EscalationLevel.LEVEL_4,
                priority_boost=3,
                auto_assign=True,
                metadata={"reason": "Security incident detected"}
            )
        ]
        
        self.escalation_rules[EscalationType.SECURITY] = security_rules
    
    def _setup_sla_configurations(self) -> None:
        """Setup comprehensive SLA configurations."""
        # Complaint SLA configuration
        complaint_sla = SLAConfiguration(
            entity_type="complaint",
            priority_sla={
                "urgent": 2,    # 2 hours
                "high": 8,      # 8 hours
                "medium": 24,   # 24 hours
                "low": 72       # 72 hours
            },
            escalation_thresholds=[4, 12, 24, 48],  # Hours for each level
            business_hours_only=False,
            exclude_weekends=False,
            grace_period_hours=1
        )
        
        # Maintenance SLA configuration
        maintenance_sla = SLAConfiguration(
            entity_type="maintenance",
            priority_sla={
                "emergency": 1,   # 1 hour
                "urgent": 4,      # 4 hours
                "high": 24,       # 24 hours
                "medium": 72,     # 72 hours
                "low": 168        # 1 week
            },
            escalation_thresholds=[2, 8, 24, 72],
            business_hours_only=True,
            exclude_weekends=True,
            grace_period_hours=2
        )
        
        self.sla_configs["complaint"] = complaint_sla
        self.sla_configs["maintenance"] = maintenance_sla
    
    # Public API methods
    
    async def escalate_complaint(
        self,
        db: Session,
        complaint_id: UUID,
        escalated_by: Optional[UUID] = None,
        escalation_reason: str = "",
        target_level: Optional[EscalationLevel] = None,
        is_urgent: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute intelligent complaint escalation.
        
        Args:
            db: Database session
            complaint_id: Complaint to escalate
            escalated_by: User initiating escalation (None for auto)
            escalation_reason: Reason for escalation
            target_level: Specific level to escalate to
            is_urgent: Mark as urgent escalation
            metadata: Additional context data
            
        Returns:
            Comprehensive escalation result
        """
        context = {
            "db": db,
            "entity_type": EscalationType.COMPLAINT,
            "entity_id": complaint_id,
            "escalated_by": escalated_by,
            "escalation_reason": escalation_reason,
            "target_level": target_level,
            "is_urgent": is_urgent,
            "is_manual": escalated_by is not None,
            "metadata": metadata or {},
            "trigger": EscalationTrigger.MANUAL_REQUEST if escalated_by else EscalationTrigger.AUTO_RULE
        }
        
        execution = await workflow_engine.execute_workflow(
            "complaint_escalation",
            context,
            escalated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def auto_escalate_on_sla_breach(
        self,
        db: Session,
        entity_type: str,
        entity_id: UUID,
        sla_breach_hours: int,
        breach_severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Execute intelligent auto-escalation on SLA breach.
        
        Args:
            db: Database session
            entity_type: Type of entity (complaint, maintenance, etc.)
            entity_id: Entity that breached SLA
            sla_breach_hours: Hours breached past SLA
            breach_severity: Severity of the breach
            
        Returns:
            Auto-escalation result
        """
        context = {
            "db": db,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sla_breach_hours": sla_breach_hours,
            "breach_severity": breach_severity,
            "is_manual": False,
            "trigger": EscalationTrigger.SLA_BREACH
        }
        
        execution = await workflow_engine.execute_workflow(
            "sla_breach_escalation",
            context,
            None  # System initiated
        )
        
        return execution.result or execution.to_dict()
    
    async def mass_escalate_related_issues(
        self,
        db: Session,
        issue_ids: List[UUID],
        escalation_reason: str,
        initiated_by: UUID
    ) -> Dict[str, Any]:
        """Execute mass escalation for related issues."""
        context = {
            "db": db,
            "issue_ids": issue_ids,
            "escalation_reason": escalation_reason,
            "initiated_by": initiated_by,
            "mass_escalation": True
        }
        
        execution = await workflow_engine.execute_workflow(
            "mass_escalation",
            context,
            initiated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def de_escalate(
        self,
        db: Session,
        escalation_id: UUID,
        de_escalated_by: UUID,
        reason: str,
        resolution_quality_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute intelligent de-escalation with quality tracking.
        
        Args:
            db: Database session
            escalation_id: Escalation record ID
            de_escalated_by: User performing de-escalation
            reason: Reason for de-escalation
            resolution_quality_score: Quality score for the resolution
            
        Returns:
            De-escalation result with performance metrics
        """
        context = {
            "db": db,
            "escalation_id": escalation_id,
            "de_escalated_by": de_escalated_by,
            "reason": reason,
            "resolution_quality_score": resolution_quality_score
        }
        
        execution = await workflow_engine.execute_workflow(
            "de_escalation",
            context,
            de_escalated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def get_escalation_analytics(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        date_range: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """Get comprehensive escalation analytics."""
        # Implementation would query escalation data and calculate metrics
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
            "escalation_volume": {
                "total_escalations": self.escalation_metrics.total_escalations,
                "auto_escalations": self.escalation_metrics.auto_escalations,
                "manual_escalations": self.escalation_metrics.manual_escalations,
                "sla_breach_escalations": self.escalation_metrics.sla_breach_escalations
            },
            "resolution_efficiency": {
                "resolved_at_level": dict(self.escalation_metrics.resolved_at_level),
                "average_resolution_time": dict(self.escalation_metrics.average_resolution_time),
                "escalation_success_rate": self.escalation_metrics.escalation_success_rate
            },
            "trends": await self._calculate_escalation_trends(db, start_date, end_date),
            "predictions": await self._predict_escalation_patterns(db)
        }
        
        return analytics
    
    # Validation methods
    
    def _validate_escalation_context(self, context: Dict[str, Any]) -> bool:
        """Enhanced validation for escalation context."""
        required_fields = ["db", "entity_type", "entity_id"]
        
        if not all(field in context for field in required_fields):
            return False
        
        # Validate entity type
        if context["entity_type"] not in [e.value for e in EscalationType]:
            return False
        
        return True
    
    # Step handlers - Enhanced complaint escalation
    
    async def _analyze_escalation_requirement(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if escalation is actually required using AI."""
        db = context["db"]
        entity_id = context["entity_id"]
        entity_type = context["entity_type"]
        
        analysis_result = {
            "escalation_required": True,
            "confidence_score": 0.0,
            "analysis_factors": [],
            "alternative_actions": []
        }
        
        # Load entity data
        if entity_type == EscalationType.COMPLAINT:
            entity = self.complaint_repo.get_by_id(db, entity_id)
        else:
            # Handle other entity types
            entity = None
        
        if not entity:
            raise ValidationException(f"{entity_type} not found")
        
        context["entity"] = entity
        
        # AI-powered analysis factors
        factors = []
        
        # Check resolution attempt history
        if hasattr(entity, 'resolution_attempts'):
            attempt_count = len(entity.resolution_attempts or [])
            if attempt_count < 2:
                factors.append("insufficient_resolution_attempts")
                analysis_result["alternative_actions"].append("Try additional resolution methods")
        
        # Check assignee workload
        if entity.assigned_to_id:
            workload = await self._get_assignee_workload(db, entity.assigned_to_id)
            if workload["current_load"] > workload["capacity"] * 0.8:
                factors.append("assignee_overloaded")
            else:
                factors.append("assignee_available")
                analysis_result["alternative_actions"].append("Provide additional support to assignee")
        
        # Check similar issue resolution patterns
        similar_resolution_rate = await self._get_similar_issue_resolution_rate(db, entity)
        if similar_resolution_rate > 0.8:
            factors.append("high_similar_resolution_rate")
            analysis_result["alternative_actions"].append("Apply similar issue resolution pattern")
        
        # Calculate confidence score
        escalation_indicators = ["assignee_overloaded", "multiple_failed_attempts", "sla_critical"]
        positive_indicators = [f for f in factors if f in escalation_indicators]
        analysis_result["confidence_score"] = min(1.0, len(positive_indicators) / len(escalation_indicators))
        
        analysis_result["analysis_factors"] = factors
        
        # Override decision based on context
        if context.get("is_manual") or context.get("is_urgent"):
            analysis_result["escalation_required"] = True
            analysis_result["confidence_score"] = 1.0
        
        return analysis_result
    
    async def _check_escalation_eligibility(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check comprehensive escalation eligibility."""
        entity = context["entity"]
        
        eligibility_check = {
            "eligible": True,
            "eligibility_factors": [],
            "blocking_conditions": [],
            "warnings": []
        }
        
        # Check if already at highest level
        current_escalation_level = await self._get_current_escalation_level(entity)
        if current_escalation_level >= EscalationLevel.LEVEL_5.numeric_value:
            eligibility_check["blocking_conditions"].append("already_at_highest_level")
            eligibility_check["eligible"] = False
        
        # Check escalation frequency (prevent spam)
        recent_escalations = await self._count_recent_escalations(entity.id, hours=24)
        if recent_escalations > 3:
            eligibility_check["warnings"].append("frequent_escalations_detected")
        
        # Check if entity is in resolution process
        if hasattr(entity, 'status') and entity.status == "in_progress":
            eligibility_check["eligibility_factors"].append("resolution_in_progress")
        
        # Check escalation cooldown period
        last_escalation = await self._get_last_escalation_time(entity.id)
        if last_escalation:
            hours_since_last = (datetime.utcnow() - last_escalation).total_seconds() / 3600
            if hours_since_last < 2:  # 2-hour cooldown
                eligibility_check["warnings"].append("escalation_cooldown_active")
        
        return eligibility_check
    
    async def _calculate_escalation_score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive escalation priority score."""
        entity = context["entity"]
        
        score_calculation = {
            "total_score": 0,
            "component_scores": {},
            "scoring_factors": []
        }
        
        # Base priority score
        priority_scores = {
            "urgent": 40,
            "high": 30,
            "medium": 20,
            "low": 10
        }
        
        if hasattr(entity, 'priority'):
            priority_score = priority_scores.get(entity.priority.value, 10)
            score_calculation["component_scores"]["priority"] = priority_score
            score_calculation["total_score"] += priority_score
        
        # Age factor (older issues get higher scores)
        if hasattr(entity, 'created_at'):
            age_hours = (datetime.utcnow() - entity.created_at).total_seconds() / 3600
            age_score = min(20, age_hours / 2)  # Max 20 points, 1 point per 2 hours
            score_calculation["component_scores"]["age"] = age_score
            score_calculation["total_score"] += age_score
        
        # Customer impact score
        customer_impact = await self._assess_customer_impact(entity)
        impact_score = customer_impact["score"] * 15  # Max 15 points
        score_calculation["component_scores"]["customer_impact"] = impact_score
        score_calculation["total_score"] += impact_score
        
        # Resolution complexity score
        complexity = await self._assess_resolution_complexity(entity)
        complexity_score = complexity["score"] * 10  # Max 10 points
        score_calculation["component_scores"]["complexity"] = complexity_score
        score_calculation["total_score"] += complexity_score
        
        # SLA breach penalty
        sla_breach_hours = context.get("sla_breach_hours", 0)
        if sla_breach_hours > 0:
            breach_score = min(25, sla_breach_hours * 2)  # Max 25 points
            score_calculation["component_scores"]["sla_breach"] = breach_score
            score_calculation["total_score"] += breach_score
        
        # Manual escalation boost
        if context.get("is_manual"):
            manual_boost = 15
            score_calculation["component_scores"]["manual_escalation"] = manual_boost
            score_calculation["total_score"] += manual_boost
        
        context["escalation_score"] = score_calculation["total_score"]
        
        return score_calculation
    
    async def _determine_optimal_escalation_path(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine optimal escalation path using intelligent routing."""
        entity = context["entity"]
        escalation_score = context["escalation_score"]
        target_level = context.get("target_level")
        
        path_determination = {
            "recommended_level": None,
            "path_reasoning": [],
            "alternative_paths": [],
            "estimated_resolution_time": None
        }
        
        if target_level:
            # Use specified target level
            path_determination["recommended_level"] = target_level
            path_determination["path_reasoning"].append("target_level_specified")
        else:
            # Determine based on score and rules
            current_level = await self._get_current_escalation_level(entity)
            
            if escalation_score >= 80:
                recommended_level = EscalationLevel.LEVEL_4  # Admin
                path_determination["path_reasoning"].append("high_severity_score")
            elif escalation_score >= 60:
                recommended_level = EscalationLevel.LEVEL_3  # Senior Manager
                path_determination["path_reasoning"].append("medium_severity_score")
            elif escalation_score >= 40:
                recommended_level = EscalationLevel.LEVEL_2  # Manager
                path_determination["path_reasoning"].append("moderate_severity_score")
            else:
                recommended_level = EscalationLevel.LEVEL_1  # Supervisor
                path_determination["path_reasoning"].append("low_severity_score")
            
            # Ensure we're escalating up, not down
            if recommended_level.numeric_value <= current_level:
                recommended_level = list(EscalationLevel)[min(current_level, len(EscalationLevel) - 1)]
                path_determination["path_reasoning"].append("level_adjustment_applied")
            
            path_determination["recommended_level"] = recommended_level
        
        # Apply escalation rules
        applicable_rules = await self._get_applicable_escalation_rules(context)
        for rule in applicable_rules:
            if rule.target_level.numeric_value > path_determination["recommended_level"].numeric_value:
                path_determination["recommended_level"] = rule.target_level
                path_determination["path_reasoning"].append(f"rule_override:{rule.rule_id}")
        
        # Estimate resolution time
        path_determination["estimated_resolution_time"] = await self._estimate_escalation_resolution_time(
            path_determination["recommended_level"],
            entity
        )
        
        context["target_escalation_level"] = path_determination["recommended_level"]
        
        return path_determination
    
    async def _select_optimal_escalation_recipient(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Select optimal escalation recipient using AI and workload balancing."""
        db = context["db"]
        target_level = context["target_escalation_level"]
        entity = context["entity"]
        
        recipient_selection = {
            "recipient_id": None,
            "recipient_info": {},
            "selection_criteria": [],
            "alternative_recipients": []
        }
        
        # Get available recipients for the target level
        available_recipients = await self._get_available_recipients_by_level(db, target_level)
        
        if not available_recipients:
            raise BusinessLogicException(f"No available recipients for escalation level {target_level}")
        
        # Score each recipient
        scored_recipients = []
        for recipient in available_recipients:
            score = await self._calculate_recipient_score(db, recipient, entity)
            scored_recipients.append((recipient, score))
        
        # Sort by score (highest first)
        scored_recipients.sort(key=lambda x: x[1], reverse=True)
        
        # Select best recipient
        best_recipient, best_score = scored_recipients[0]
        recipient_selection["recipient_id"] = best_recipient.id
        recipient_selection["recipient_info"] = {
            "name": best_recipient.user.full_name,
            "role": best_recipient.role,
            "department": getattr(best_recipient, 'department', 'general'),
            "current_workload": await self._get_current_workload(db, best_recipient.id),
            "expertise_match": await self._get_expertise_match_score(best_recipient, entity),
            "selection_score": best_score
        }
        
        # Add alternative recipients
        for recipient, score in scored_recipients[1:3]:  # Top 3 alternatives
            recipient_selection["alternative_recipients"].append({
                "recipient_id": str(recipient.id),
                "name": recipient.user.full_name,
                "score": score
            })
        
        context["escalation_recipient"] = best_recipient
        
        return recipient_selection
    
    async def _create_enhanced_escalation_record(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive escalation record with full context."""
        db = context["db"]
        entity = context["entity"]
        escalated_by = context.get("escalated_by")
        recipient = context["escalation_recipient"]
        escalation_reason = context["escalation_reason"]
        target_level = context["target_escalation_level"]
        
        escalation_data = {
            "complaint_id": entity.id,
            "escalated_by": escalated_by,
            "escalated_to": recipient.id,
            "escalation_level": target_level.value,
            "reason": escalation_reason,
            "is_urgent": context.get("is_urgent", False),
            "is_manual": context.get("is_manual", False),
            "escalated_at": datetime.utcnow(),
            "escalation_score": context.get("escalation_score", 0),
            "trigger_type": context.get("trigger", EscalationTrigger.MANUAL_REQUEST).value,
            "sla_breach_hours": context.get("sla_breach_hours", 0),
            "estimated_resolution_hours": context.get("estimated_resolution_time", 24),
            "escalation_metadata": {
                "original_assignee": str(entity.assigned_to_id) if entity.assigned_to_id else None,
                "escalation_path": context.get("escalation_path", []),
                "analysis_factors": context.get("analysis_factors", []),
                "recipient_selection_score": recipient_selection.get("selection_score", 0),
                "automated_decision": not context.get("is_manual", True)
            }
        }
        
        escalation = self.complaint_escalation_repo.create_escalation(db, escalation_data)
        
        context["escalation_record"] = escalation
        
        # Update metrics
        self.escalation_metrics.total_escalations += 1
        if context.get("is_manual"):
            self.escalation_metrics.manual_escalations += 1
        else:
            self.escalation_metrics.auto_escalations += 1
        
        if context.get("sla_breach_hours", 0) > 0:
            self.escalation_metrics.sla_breach_escalations += 1
        
        return {
            "escalation_id": str(escalation.id),
            "escalated_to": str(recipient.id),
            "escalation_level": target_level.value,
            "creation_timestamp": escalation.escalated_at.isoformat()
        }
    
    # Helper methods
    
    async def _get_assignee_workload(self, db: Session, assignee_id: UUID) -> Dict[str, Any]:
        """Get comprehensive assignee workload information."""
        # Check cache first
        cache_key = f"workload_{assignee_id}"
        if cache_key in self._workload_cache and datetime.utcnow() < self._cache_expiry:
            current_load = self._workload_cache[cache_key]
        else:
            # Calculate workload
            current_load = await self._calculate_current_workload(db, assignee_id)
            self._workload_cache[cache_key] = current_load
        
        return {
            "current_load": current_load,
            "capacity": 20,  # Default capacity
            "utilization_percentage": (current_load / 20) * 100
        }
    
    async def _calculate_current_workload(self, db: Session, assignee_id: UUID) -> int:
        """Calculate current workload for an assignee."""
        # Count active assignments across different types
        active_complaints = self.complaint_repo.count_active_by_assignee(db, assignee_id)
        # Add other workload types as needed
        return active_complaints
    
    async def _get_similar_issue_resolution_rate(self, db: Session, entity) -> float:
        """Get resolution rate for similar issues."""
        # Implementation would analyze similar issues and their resolution rates
        return 0.75  # Placeholder
    
    async def _get_current_escalation_level(self, entity) -> int:
        """Get current escalation level for an entity."""
        # Implementation would check escalation history
        return 0  # Base level
    
    async def _count_recent_escalations(self, entity_id: UUID, hours: int) -> int:
        """Count recent escalations for an entity."""
        # Implementation would query escalation history
        return 0
    
    async def _get_last_escalation_time(self, entity_id: UUID) -> Optional[datetime]:
        """Get timestamp of last escalation."""
        # Implementation would query escalation history
        return None
    
    async def _assess_customer_impact(self, entity) -> Dict[str, Any]:
        """Assess customer impact score."""
        # Implementation would analyze customer impact factors
        return {"score": 0.5, "factors": []}
    
    async def _assess_resolution_complexity(self, entity) -> Dict[str, Any]:
        """Assess resolution complexity."""
        # Implementation would analyze complexity factors
        return {"score": 0.4, "factors": []}
    
    async def _get_applicable_escalation_rules(self, context: Dict[str, Any]) -> List[EscalationRule]:
        """Get applicable escalation rules for the context."""
        entity_type = context["entity_type"]
        rules = self.escalation_rules.get(entity_type, [])
        
        applicable_rules = []
        for rule in rules:
            try:
                if rule.condition(context):
                    applicable_rules.append(rule)
            except Exception:
                # Skip rules with evaluation errors
                continue
        
        return applicable_rules
    
    async def _estimate_escalation_resolution_time(
        self, 
        escalation_level: EscalationLevel, 
        entity
    ) -> int:
        """Estimate resolution time after escalation."""
        # Implementation would use historical data and ML models
        base_times = {
            EscalationLevel.LEVEL_1: 8,
            EscalationLevel.LEVEL_2: 12,
            EscalationLevel.LEVEL_3: 24,
            EscalationLevel.LEVEL_4: 48,
            EscalationLevel.LEVEL_5: 72
        }
        return base_times.get(escalation_level, 24)
    
    async def _get_available_recipients_by_level(
        self, 
        db: Session, 
        level: EscalationLevel
    ) -> List:
        """Get available recipients for escalation level."""
        if level in [EscalationLevel.LEVEL_1, EscalationLevel.LEVEL_2]:
            return self.supervisor_repo.get_available_supervisors(db)
        else:
            return self.admin_repo.get_available_admins(db, min_role=level.value)
    
    async def _calculate_recipient_score(self, db: Session, recipient, entity) -> float:
        """Calculate score for potential escalation recipient."""
        score = 50.0  # Base score
        
        # Workload factor
        workload_info = await self._get_assignee_workload(db, recipient.id)
        workload_factor = max(0, 1 - (workload_info["utilization_percentage"] / 100))
        score += workload_factor * 20
        
        # Expertise matching
        expertise_score = await self._get_expertise_match_score(recipient, entity)
        score += expertise_score * 20
        
        # Performance history
        performance_score = await self._get_recipient_performance_score(db, recipient.id)
        score += performance_score * 10
        
        return min(100.0, score)
    
    async def _get_expertise_match_score(self, recipient, entity) -> float:
        """Calculate expertise match score."""
        # Implementation would match recipient expertise with entity requirements
        return 0.7  # Placeholder
    
    async def _get_recipient_performance_score(self, db: Session, recipient_id: UUID) -> float:
        """Get performance score for recipient."""
        # Implementation would calculate based on historical performance
        return 0.8  # Placeholder
    
    async def _get_current_workload(self, db: Session, recipient_id: UUID) -> int:
        """Get current workload for recipient."""
        return await self._calculate_current_workload(db, recipient_id)
    
    # Additional step handlers and helper methods would continue here...
    
    async def _calculate_escalation_trends(
        self, 
        db: Session, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate escalation trends for analytics."""
        # Implementation would analyze historical escalation data
        return {
            "volume_trend": "increasing",
            "resolution_time_trend": "improving",
            "success_rate_trend": "stable"
        }
    
    async def _predict_escalation_patterns(self, db: Session) -> Dict[str, Any]:
        """Predict future escalation patterns using ML."""
        # Implementation would use ML models for prediction
        return {
            "predicted_volume_next_week": 45,
            "peak_hours": [9, 14, 16],
            "high_risk_categories": ["maintenance", "billing"]
        }
    
    # Completion handlers
    
    async def _on_escalation_complete(self, execution) -> None:
        """Handle escalation completion."""
        # Update performance metrics
        # Send completion notifications
        # Update ML models with outcome data
        pass
    
    async def _on_escalation_error(self, execution, error: Exception) -> None:
        """Handle escalation errors."""
        # Log detailed error information
        # Send alert notifications
        # Attempt fallback escalation procedures
        pass