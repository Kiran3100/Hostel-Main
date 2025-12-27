from typing import Any, Optional, List
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.core.logging import get_logger
from app.core.cache import cache_response, invalidate_cache
from app.schemas.attendance import (
    AttendancePolicy,
    PolicyConfig,
    PolicyUpdate,
    PolicyViolation,
    ViolationSummary,
    PolicyTemplate,
)
from app.services.attendance.attendance_policy_service import AttendancePolicyService

logger = get_logger(__name__)
router = APIRouter(prefix="/attendance/policies", tags=["attendance:policies"])


def get_policy_service(db: Session = Depends(deps.get_db)) -> AttendancePolicyService:
    """
    Dependency to provide AttendancePolicyService instance.
    
    Args:
        db: Database session
        
    Returns:
        AttendancePolicyService instance configured for policy operations
    """
    return AttendancePolicyService(db=db)


@router.get(
    "",
    response_model=AttendancePolicy,
    summary="Get current attendance policy configuration",
    description="Retrieve the active attendance policy with all rules, thresholds, "
                "and enforcement settings for a specific hostel.",
    responses={
        200: {"description": "Policy retrieved successfully"},
        404: {"description": "No policy found for the specified hostel"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=600)  # Cache for 10 minutes
async def get_attendance_policy(
    hostel_id: str = Query(
        ..., 
        description="Unique hostel identifier",
        min_length=1,
        max_length=50
    ),
    include_history: bool = Query(
        False, 
        description="Include policy change history"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Retrieve current attendance policy configuration for a hostel.

    **Policy Components:**
    - Attendance percentage requirements
    - Late arrival and early departure rules
    - Consecutive absence limits
    - Excuse and justification policies
    - Escalation and notification rules

    **Features:**
    - Active policy configuration
    - Enforcement thresholds and actions
    - Grace periods and exceptions
    - Integration settings with external systems

    **Optional History:**
    - Policy modification timeline
    - Previous policy versions
    - Change rationale documentation
    - Implementation dates and actors

    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} requesting policy for hostel {hostel_id}")
        
        result = service.get_policy(
            hostel_id=hostel_id, 
            include_history=include_history,
            actor_id=_admin.id
        )
        
        logger.info(f"Policy retrieved for hostel {hostel_id}")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Policy not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for policy access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving policy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "",
    response_model=AttendancePolicy,
    status_code=status.HTTP_201_CREATED,
    summary="Create comprehensive attendance policy",
    description="Create a new attendance policy with detailed rules, thresholds, "
                "and enforcement mechanisms for a hostel.",
    responses={
        201: {"description": "Policy created successfully"},
        400: {"description": "Invalid policy configuration"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Policy already exists for this hostel"},
    }
)
async def create_attendance_policy(
    payload: PolicyConfig,
    background_tasks: BackgroundTasks,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Create comprehensive attendance policy for a hostel.

    **Policy Configuration:**
    - Minimum attendance percentage requirements
    - Late arrival tolerance and penalties
    - Consecutive absence limits and actions
    - Excuse validation and approval workflows
    - Parent/guardian notification thresholds

    **Enforcement Rules:**
    - Automatic violation detection
    - Progressive disciplinary actions
    - Grace period and exception handling
    - Appeal and review processes

    **Integration Settings:**
    - External system notifications
    - Academic record integration
    - Parent portal connections
    - Emergency contact protocols

    **Validation:**
    - Rule consistency checking
    - Threshold reasonableness validation
    - Implementation timeline verification
    - Resource requirement assessment

    **Access:** Super Admin users only
    """
    try:
        logger.info(
            f"Super Admin {_super_admin.id} creating policy for hostel {payload.hostel_id}"
        )
        
        result = service.create_policy(payload=payload, actor_id=_super_admin.id)
        
        # Invalidate related caches
        background_tasks.add_task(
            invalidate_cache, 
            f"policy_{payload.hostel_id}"
        )
        
        # Schedule policy validation and testing
        background_tasks.add_task(
            service.validate_policy_implementation,
            result.id,
            _super_admin.id
        )
        
        logger.info(f"Policy {result.id} created successfully for hostel {payload.hostel_id}")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in policy creation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for policy creation: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating policy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{policy_id}",
    response_model=AttendancePolicy,
    summary="Update existing attendance policy",
    description="Modify attendance policy configuration with versioning, "
                "impact analysis, and gradual rollout capabilities.",
    responses={
        200: {"description": "Policy updated successfully"},
        400: {"description": "Invalid policy update"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Policy not found"},
    }
)
async def update_attendance_policy(
    policy_id: str = Query(..., description="Policy identifier"),
    payload: PolicyUpdate,
    background_tasks: BackgroundTasks,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Update existing attendance policy with comprehensive change management.

    **Update Features:**
    - Incremental policy modifications
    - Version control and change tracking
    - Impact assessment and preview
    - Gradual rollout and testing capabilities

    **Change Management:**
    - Pre-update validation and simulation
    - Rollback capabilities for safety
    - Stakeholder notification and approval
    - Implementation timeline management

    **Impact Analysis:**
    - Student population affected
    - Violation threshold changes
    - System integration impacts
    - Resource requirement adjustments

    **Audit and Compliance:**
    - Complete change history
    - Approval workflow tracking
    - Regulatory compliance validation
    - Documentation and justification

    **Access:** Super Admin users only
    """
    try:
        logger.info(f"Super Admin {_super_admin.id} updating policy {policy_id}")
        
        # Perform impact analysis before update
        impact_analysis = service.analyze_update_impact(policy_id, payload)
        
        result = service.update_policy(
            policy_id=policy_id,
            payload=payload,
            actor_id=_super_admin.id,
        )
        
        # Invalidate related caches
        background_tasks.add_task(
            service.invalidate_policy_caches,
            policy_id
        )
        
        # Schedule stakeholder notifications
        background_tasks.add_task(
            service.notify_policy_update,
            policy_id,
            impact_analysis,
            _super_admin.id
        )
        
        logger.info(f"Policy {policy_id} updated successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Policy not found for update: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in policy update: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for policy update: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating policy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/detect-violations",
    response_model=List[PolicyViolation],
    summary="Detect and analyze attendance policy violations",
    description="Comprehensive violation detection with severity assessment, "
                "trend analysis, and automated intervention recommendations.",
    responses={
        200: {"description": "Violation detection completed successfully"},
        400: {"description": "Invalid detection parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
async def detect_policy_violations(
    hostel_id: str = Query(..., description="Hostel identifier"),
    start_date: Optional[str] = Query(
        None, 
        description="Analysis start date (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    end_date: Optional[str] = Query(
        None, 
        description="Analysis end date (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    severity_threshold: Optional[str] = Query(
        None, 
        description="Minimum violation severity to include",
        regex="^(low|medium|high|critical)$"
    ),
    student_ids: Optional[List[str]] = Query(
        None,
        description="Specific students to analyze"
    ),
    include_recommendations: bool = Query(
        True,
        description="Include intervention recommendations"
    ),
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Detect attendance policy violations with comprehensive analysis.

    **Violation Detection:**
    - Attendance percentage below thresholds
    - Consecutive absence violations
    - Chronic lateness patterns
    - Unauthorized early departures
    - Policy exemption abuse

    **Analysis Features:**
    - Severity classification and ranking
    - Trend identification and prediction
    - Pattern recognition for intervention
    - Risk assessment for escalation

    **Intervention Recommendations:**
    - Counseling and support referrals
    - Parent/guardian engagement
    - Academic intervention plans
    - Disciplinary action suggestions

    **Performance Optimization:**
    - Efficient database queries
    - Parallel processing for large datasets
    - Intelligent caching strategies
    - Background analysis scheduling

    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} detecting violations for hostel {hostel_id} "
            f"from {start_date} to {end_date}"
        )
        
        result = service.detect_violations(
            hostel_id=hostel_id,
            start_date_str=start_date,
            end_date_str=end_date,
            severity_threshold=severity_threshold,
            student_ids=student_ids,
            include_recommendations=include_recommendations,
            actor_id=_admin.id,
        )
        
        # Schedule background processing for large result sets
        if len(result) > 50:
            background_tasks.add_task(
                service.process_bulk_violations,
                [violation.id for violation in result],
                _admin.id
            )
        
        logger.info(f"Detected {len(result)} policy violations")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in violation detection: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for violation detection: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting violations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/violations/summary",
    response_model=ViolationSummary,
    summary="Get comprehensive violation analytics summary",
    description="Generate detailed violation analytics with trends, patterns, "
                "and actionable insights for administrative decision-making.",
    responses={
        200: {"description": "Violation summary generated successfully"},
        400: {"description": "Invalid summary parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=900)  # Cache for 15 minutes
async def get_violation_summary(
    hostel_id: str = Query(..., description="Hostel identifier"),
    days: int = Query(
        30, 
        ge=1, 
        le=365, 
        description="Number of days for analysis"
    ),
    include_trends: bool = Query(
        True, 
        description="Include trend analysis and predictions"
    ),
    include_interventions: bool = Query(
        True,
        description="Include intervention effectiveness analysis"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Generate comprehensive attendance policy violation analytics.

    **Summary Analytics:**
    - Total violation counts by severity and type
    - Student population impact percentages
    - Violation trend analysis and forecasting
    - Policy effectiveness measurements

    **Trend Analysis:**
    - Weekly and monthly violation patterns
    - Seasonal variation identification
    - Student cohort comparisons
    - Policy change impact assessment

    **Intervention Insights:**
    - Success rates of different interventions
    - Time-to-resolution analytics
    - Recurrence pattern analysis
    - Resource allocation optimization

    **Dashboard Metrics:**
    - Real-time violation rates
    - Critical alerts and escalations
    - Comparative hostel performance
    - Policy compliance scorecards

    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} requesting violation summary for "
            f"hostel {hostel_id}, {days} days"
        )
        
        result = service.get_violation_summary(
            hostel_id=hostel_id,
            days=days,
            include_trends=include_trends,
            include_interventions=include_interventions,
            actor_id=_admin.id,
        )
        
        logger.info(f"Violation summary generated successfully")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in violation summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for violation summary: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating violation summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/templates",
    response_model=List[PolicyTemplate],
    summary="Get attendance policy templates",
    description="Retrieve pre-configured policy templates for different hostel types and requirements",
    responses={
        200: {"description": "Templates retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=3600)  # Cache for 1 hour
async def get_policy_templates(
    hostel_type: Optional[str] = Query(
        None,
        description="Filter by hostel type (residential, day, mixed)"
    ),
    student_level: Optional[str] = Query(
        None,
        description="Filter by student level (elementary, middle, high, college)"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Get pre-configured attendance policy templates for easy setup.

    **Template Categories:**
    - Standard educational institution policies
    - Hostel-specific attendance requirements
    - Age-appropriate rule configurations
    - Regulatory compliance templates

    **Customization Options:**
    - Template modification and adaptation
    - Institution-specific adjustments
    - Phased implementation strategies
    - Integration with existing systems

    **Access:** Admin users only
    """
    try:
        result = service.get_policy_templates(
            hostel_type=hostel_type,
            student_level=student_level,
            actor_id=_admin.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving policy templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{policy_id}/simulate",
    summary="Simulate policy changes and impact",
    description="Run policy simulation to analyze potential impacts before implementation",
    responses={
        200: {"description": "Simulation completed successfully"},
        400: {"description": "Invalid simulation parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Policy not found"},
    }
)
async def simulate_policy_changes(
    policy_id: str = Query(..., description="Policy identifier"),
    payload: PolicyUpdate,
    simulation_days: int = Query(
        30, 
        ge=7, 
        le=90, 
        description="Number of days to simulate"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Simulate attendance policy changes to predict impacts and outcomes.

    **Simulation Features:**
    - Historical data replay with new policy rules
    - Violation prediction and analysis
    - Resource requirement estimation
    - Stakeholder impact assessment

    **Analysis Output:**
    - Predicted violation changes
    - Student population impacts
    - Administrative workload changes
    - System integration effects

    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} simulating policy changes for {policy_id}")
        
        result = service.simulate_policy_changes(
            policy_id=policy_id,
            changes=payload,
            simulation_days=simulation_days,
            actor_id=_admin.id
        )
        
        logger.info(f"Policy simulation completed for {policy_id}")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Policy not found for simulation: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in policy simulation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error simulating policy changes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/compliance-report",
    summary="Generate policy compliance report",
    description="Generate comprehensive compliance report for auditing and review purposes",
    responses={
        200: {"description": "Compliance report generated successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
async def generate_compliance_report(
    hostel_id: str = Query(..., description="Hostel identifier"),
    period_months: int = Query(
        12, 
        ge=1, 
        le=24, 
        description="Report period in months"
    ),
    include_details: bool = Query(
        True,
        description="Include detailed violation breakdowns"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Generate comprehensive attendance policy compliance report.

    **Report Components:**
    - Overall compliance percentage
    - Violation trends and patterns
    - Policy effectiveness analysis
    - Improvement recommendations

    **Detailed Breakdown:**
    - Student-level compliance rates
    - Violation category analysis
    - Intervention success rates
    - Resource utilization metrics

    **Access:** Admin users only
    """
    try:
        result = service.generate_compliance_report(
            hostel_id=hostel_id,
            period_months=period_months,
            include_details=include_details,
            actor_id=_admin.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")