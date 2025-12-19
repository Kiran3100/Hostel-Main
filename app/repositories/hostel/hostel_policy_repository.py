"""
Hostel policy repository for comprehensive policy and rules management.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import selectinload

from app.models.hostel.hostel_policy import HostelPolicy, PolicyAcknowledgment, PolicyViolation
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationRequest, PaginationResult


class ActivePoliciesSpecification(Specification[HostelPolicy]):
    """Specification for active and published policies."""
    
    def __init__(self, require_published: bool = True):
        self.require_published = require_published
    
    def is_satisfied_by(self, entity: HostelPolicy) -> bool:
        base_condition = entity.is_active and entity.is_current
        if self.require_published:
            return base_condition and entity.is_published
        return base_condition
    
    def to_sql_condition(self):
        current_time = datetime.utcnow()
        current_condition = and_(
            HostelPolicy.is_active == True,
            HostelPolicy.effective_from <= current_time,
            or_(
                HostelPolicy.effective_until.is_(None),
                HostelPolicy.effective_until > current_time
            )
        )
        
        if self.require_published:
            return and_(current_condition, HostelPolicy.is_published == True)
        return current_condition


class MandatoryPoliciesSpecification(Specification[HostelPolicy]):
    """Specification for mandatory policies requiring acknowledgment."""
    
    def is_satisfied_by(self, entity: HostelPolicy) -> bool:
        return entity.is_mandatory and entity.is_published and entity.is_current
    
    def to_sql_condition(self):
        current_time = datetime.utcnow()
        return and_(
            HostelPolicy.is_mandatory == True,
            HostelPolicy.is_published == True,
            HostelPolicy.is_active == True,
            HostelPolicy.effective_from <= current_time,
            or_(
                HostelPolicy.effective_until.is_(None),
                HostelPolicy.effective_until > current_time
            )
        )


class HostelPolicyRepository(BaseRepository[HostelPolicy]):
    """Repository for hostel policy and rules management."""
    
    def __init__(self, session):
        super().__init__(session, HostelPolicy)
    
    # ===== Core Policy Operations =====
    
    async def create_policy(
        self,
        hostel_id: UUID,
        policy_data: Dict[str, Any],
        created_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """Create a new policy with version control."""
        # Check for existing policies of the same type
        existing_policies = await self.find_by_criteria({
            "hostel_id": hostel_id,
            "policy_type": policy_data["policy_type"]
        })
        
        # Auto-increment version if needed
        if "version" not in policy_data and existing_policies:
            latest_version = max(p.version for p in existing_policies)
            try:
                major, minor = latest_version.split(".")
                new_version = f"{major}.{int(minor) + 1}"
            except (ValueError, AttributeError):
                new_version = "1.1"
            policy_data["version"] = new_version
        elif "version" not in policy_data:
            policy_data["version"] = "1.0"
        
        policy_data.update({
            "hostel_id": hostel_id,
            "created_by": created_by,
            "effective_from": policy_data.get("effective_from", datetime.utcnow())
        })
        
        return await self.create(policy_data)
    
    async def find_by_hostel(
        self,
        hostel_id: UUID,
        policy_type: Optional[str] = None,
        only_current: bool = True
    ) -> List[HostelPolicy]:
        """Find policies for a hostel."""
        criteria = {"hostel_id": hostel_id}
        
        if policy_type:
            criteria["policy_type"] = policy_type
        
        custom_filter = None
        if only_current:
            spec = ActivePoliciesSpecification(require_published=False)
            custom_filter = spec.to_sql_condition()
        
        return await self.find_by_criteria(
            criteria,
            custom_filter=custom_filter,
            order_by=[
                asc(HostelPolicy.policy_type),
                asc(HostelPolicy.display_order),
                desc(HostelPolicy.effective_from)
            ]
        )
    
    async def find_published_policies(
        self,
        hostel_id: UUID,
        category: Optional[str] = None
    ) -> List[HostelPolicy]:
        """Find published policies visible to students."""
        criteria = {"hostel_id": hostel_id}
        
        if category:
            criteria["category"] = category
        
        spec = ActivePoliciesSpecification(require_published=True)
        
        return await self.find_by_criteria(
            criteria,
            custom_filter=spec.to_sql_condition(),
            order_by=[
                asc(HostelPolicy.category),
                asc(HostelPolicy.display_order)
            ]
        )
    
    async def find_mandatory_policies(
        self,
        hostel_id: UUID,
        student_id: Optional[UUID] = None
    ) -> List[HostelPolicy]:
        """Find mandatory policies requiring acknowledgment."""
        spec = MandatoryPoliciesSpecification()
        policies = await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=spec.to_sql_condition(),
            order_by=[asc(HostelPolicy.display_order)]
        )
        
        # Filter out already acknowledged policies if student_id provided
        if student_id:
            unacknowledged_policies = []
            for policy in policies:
                acknowledged = await self.session.query(PolicyAcknowledgment).filter(
                    and_(
                        PolicyAcknowledgment.policy_id == policy.id,
                        PolicyAcknowledgment.student_id == student_id,
                        PolicyAcknowledgment.policy_version == policy.version
                    )
                ).first()
                
                if not acknowledged:
                    unacknowledged_policies.append(policy)
            
            return unacknowledged_policies
        
        return policies
    
    # ===== Policy Lifecycle Management =====
    
    async def publish_policy(
        self,
        policy_id: UUID,
        approved_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """Publish a policy to make it visible to students."""
        policy = await self.get_by_id(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        policy.is_published = True
        policy.approved_by = approved_by
        policy.approved_at = datetime.utcnow()
        
        await self.session.commit()
        return policy
    
    async def archive_policy(
        self,
        policy_id: UUID,
        effective_until: Optional[datetime] = None
    ) -> HostelPolicy:
        """Archive a policy by setting its end date."""
        policy = await self.get_by_id(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        policy.effective_until = effective_until or datetime.utcnow()
        policy.is_active = False
        
        await self.session.commit()
        return policy
    
    async def update_policy_version(
        self,
        policy_id: UUID,
        new_content: str,
        version_notes: Optional[str] = None,
        updated_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """Create a new version of an existing policy."""
        original_policy = await self.get_by_id(policy_id)
        if not original_policy:
            raise ValueError(f"Policy {policy_id} not found")
        
        # Generate new version number
        try:
            major, minor = original_policy.version.split(".")
            new_version = f"{major}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            new_version = "1.1"
        
        # Archive the current version
        await self.archive_policy(policy_id)
        
        # Create new version
        new_policy_data = {
            "hostel_id": original_policy.hostel_id,
            "policy_type": original_policy.policy_type,
            "title": original_policy.title,
            "description": original_policy.description,
            "content": new_content,
            "version": new_version,
            "version_notes": version_notes,
            "category": original_policy.category,
            "display_order": original_policy.display_order,
            "is_mandatory": original_policy.is_mandatory,
            "effective_from": datetime.utcnow(),
            "last_modified_by": updated_by
        }
        
        return await self.create(new_policy_data)
    
    # ===== Analytics and Reporting =====
    
    async def increment_views(self, policy_id: UUID) -> None:
        """Increment view count for a policy."""
        await self.session.query(HostelPolicy).filter(
            HostelPolicy.id == policy_id
        ).update({
            HostelPolicy.view_count: HostelPolicy.view_count + 1
        })
        await self.session.commit()
    
    async def get_policy_analytics(
        self,
        hostel_id: UUID,
        policy_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get policy engagement and compliance analytics."""
        base_query = self.session.query(HostelPolicy).filter(
            HostelPolicy.hostel_id == hostel_id
        )
        
        if policy_id:
            base_query = base_query.filter(HostelPolicy.id == policy_id)
        
        policies = await base_query.all()
        
        analytics = {}
        
        for policy in policies:
            # Get acknowledgment statistics
            total_acknowledgments = await self.session.query(
                func.count(PolicyAcknowledgment.id)
            ).filter(
                PolicyAcknowledgment.policy_id == policy.id
            ).scalar()
            
            # Get violation statistics
            total_violations = await self.session.query(
                func.count(PolicyViolation.id)
            ).filter(
                PolicyViolation.policy_id == policy.id
            ).scalar()
            
            analytics[str(policy.id)] = {
                "policy_title": policy.title,
                "policy_type": policy.policy_type,
                "view_count": policy.view_count,
                "acknowledgment_count": total_acknowledgments,
                "violation_count": total_violations,
                "compliance_rate": (total_acknowledgments / max(policy.acknowledgment_count, 1)) * 100 if policy.acknowledgment_count > 0 else 0,
                "violation_rate": (total_violations / max(total_acknowledgments, 1)) * 100 if total_acknowledgments > 0 else 0
            }
        
        return analytics
    
    async def get_compliance_report(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive compliance report."""
        end_date = end_date or date.today()
        start_date = start_date or date.today().replace(day=1)  # Start of current month
        
        # Get mandatory policies
        mandatory_policies = await self.find_mandatory_policies(hostel_id)
        
        # Get acknowledgments in date range
        acknowledgments = await self.session.query(PolicyAcknowledgment).join(
            HostelPolicy
        ).filter(
            and_(
                HostelPolicy.hostel_id == hostel_id,
                PolicyAcknowledgment.acknowledged_at >= start_date,
                PolicyAcknowledgment.acknowledged_at <= end_date
            )
        ).all()
        
        # Get violations in date range
        violations = await self.session.query(PolicyViolation).filter(
            and_(
                PolicyViolation.hostel_id == hostel_id,
                PolicyViolation.violation_date >= start_date,
                PolicyViolation.violation_date <= end_date
            )
        ).all()
        
        report = {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "mandatory_policies": len(mandatory_policies),
            "total_acknowledgments": len(acknowledgments),
            "total_violations": len(violations),
            "policy_breakdown": {},
            "violation_breakdown": {},
            "compliance_trends": []
        }
        
        # Policy breakdown
        policy_ack_count = {}
        for ack in acknowledgments:
            policy_id = str(ack.policy_id)
            policy_ack_count[policy_id] = policy_ack_count.get(policy_id, 0) + 1
        
        for policy in mandatory_policies:
            report["policy_breakdown"][str(policy.id)] = {
                "title": policy.title,
                "acknowledgments": policy_ack_count.get(str(policy.id), 0),
                "is_mandatory": policy.is_mandatory
            }
        
        # Violation breakdown
        violation_severity_count = {}
        for violation in violations:
            severity = violation.severity
            violation_severity_count[severity] = violation_severity_count.get(severity, 0) + 1
        
        report["violation_breakdown"] = violation_severity_count
        
        return report
    
    # ===== Search and Discovery =====
    
    async def search_policies(
        self,
        hostel_id: UUID,
        search_query: str,
        policy_type: Optional[str] = None,
        pagination: Optional[PaginationRequest] = None
    ) -> PaginationResult[HostelPolicy]:
        """Search policies with text query."""
        criteria = {"hostel_id": hostel_id}
        
        if policy_type:
            criteria["policy_type"] = policy_type
        
        # Build search conditions
        search_conditions = [
            HostelPolicy.title.ilike(f"%{search_query}%"),
            HostelPolicy.content.ilike(f"%{search_query}%"),
            HostelPolicy.description.ilike(f"%{search_query}%")
        ]
        
        custom_filter = and_(
            ActivePoliciesSpecification().to_sql_condition(),
            or_(*search_conditions)
        )
        
        query = self.build_query(
            criteria,
            custom_filter=custom_filter,
            order_by=[desc(HostelPolicy.effective_from)]
        )
        
        if pagination:
            return await self.paginate(query, pagination)
        else:
            return await query.all()


class PolicyAcknowledgmentRepository(BaseRepository[PolicyAcknowledgment]):
    """Repository for policy acknowledgment tracking."""
    
    def __init__(self, session):
        super().__init__(session, PolicyAcknowledgment)
    
    async def acknowledge_policy(
        self,
        policy_id: UUID,
        student_id: UUID,
        policy_version: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        digital_signature: Optional[str] = None
    ) -> PolicyAcknowledgment:
        """Record policy acknowledgment by student."""
        # Check if already acknowledged
        existing = await self.find_one_by_criteria({
            "policy_id": policy_id,
            "student_id": student_id,
            "policy_version": policy_version
        })
        
        if existing:
            return existing
        
        acknowledgment_data = {
            "policy_id": policy_id,
            "student_id": student_id,
            "policy_version": policy_version,
            "acknowledged_at": datetime.utcnow(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "digital_signature": digital_signature
        }
        
        # Increment policy acknowledgment count
        await self.session.query(HostelPolicy).filter(
            HostelPolicy.id == policy_id
        ).update({
            HostelPolicy.acknowledgment_count: HostelPolicy.acknowledgment_count + 1
        })
        
        return await self.create(acknowledgment_data)
    
    async def find_student_acknowledgments(
        self,
        student_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> List[PolicyAcknowledgment]:
        """Find acknowledgments by a student."""
        query = self.session.query(PolicyAcknowledgment).join(HostelPolicy)
        
        if hostel_id:
            query = query.filter(HostelPolicy.hostel_id == hostel_id)
        
        return await query.filter(
            PolicyAcknowledgment.student_id == student_id
        ).order_by(
            desc(PolicyAcknowledgment.acknowledged_at)
        ).all()
    
    async def get_acknowledgment_status(
        self,
        student_id: UUID,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive acknowledgment status for a student."""
        # Get all mandatory policies for the hostel
        mandatory_policies = await self.session.query(HostelPolicy).filter(
            and_(
                HostelPolicy.hostel_id == hostel_id,
                HostelPolicy.is_mandatory == True,
                HostelPolicy.is_published == True,
                HostelPolicy.is_active == True
            )
        ).all()
        
        # Get student's acknowledgments
        acknowledgments = await self.find_student_acknowledgments(student_id, hostel_id)
        ack_dict = {
            (str(ack.policy_id), ack.policy_version): ack 
            for ack in acknowledgments
        }
        
        status = {
            "student_id": str(student_id),
            "total_mandatory_policies": len(mandatory_policies),
            "acknowledged_policies": 0,
            "pending_policies": [],
            "acknowledged_policies_list": [],
            "compliance_percentage": 0
        }
        
        for policy in mandatory_policies:
            key = (str(policy.id), policy.version)
            if key in ack_dict:
                status["acknowledged_policies"] += 1
                status["acknowledged_policies_list"].append({
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "acknowledged_at": ack_dict[key].acknowledged_at
                })
            else:
                status["pending_policies"].append({
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "policy_type": policy.policy_type,
                    "effective_from": policy.effective_from
                })
        
        if len(mandatory_policies) > 0:
            status["compliance_percentage"] = (status["acknowledged_policies"] / len(mandatory_policies)) * 100
        
        return status


class PolicyViolationRepository(BaseRepository[PolicyViolation]):
    """Repository for policy violation tracking and management."""
    
    def __init__(self, session):
        super().__init__(session, PolicyViolation)
    
    async def report_violation(
        self,
        policy_id: UUID,
        student_id: UUID,
        hostel_id: UUID,
        violation_data: Dict[str, Any],
        reported_by: UUID
    ) -> PolicyViolation:
        """Report a policy violation."""
        violation_data.update({
            "policy_id": policy_id,
            "student_id": student_id,
            "hostel_id": hostel_id,
            "reported_by": reported_by,
            "reported_at": datetime.utcnow(),
            "status": "reported"
        })
        
        return await self.create(violation_data)
    
    async def find_violations_by_student(
        self,
        student_id: UUID,
        status: Optional[str] = None
    ) -> List[PolicyViolation]:
        """Find violations by a student."""
        criteria = {"student_id": student_id}
        if status:
            criteria["status"] = status
        
        return await self.find_by_criteria(
            criteria,
            order_by=[desc(PolicyViolation.violation_date)]
        )
    
    async def find_violations_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[PolicyViolation]:
        """Find violations for a hostel."""
        criteria = {"hostel_id": hostel_id}
        if status:
            criteria["status"] = status
        if severity:
            criteria["severity"] = severity
        
        return await self.find_by_criteria(
            criteria,
            order_by=[desc(PolicyViolation.violation_date)]
        )
    
    async def resolve_violation(
        self,
        violation_id: UUID,
        action_taken: str,
        resolved_by: UUID,
        resolution_notes: Optional[str] = None,
        fine_amount: Optional[int] = None
    ) -> PolicyViolation:
        """Resolve a policy violation."""
        violation = await self.get_by_id(violation_id)
        if not violation:
            raise ValueError(f"Violation {violation_id} not found")
        
        violation.status = "resolved"
        violation.action_taken = action_taken
        violation.action_date = datetime.utcnow()
        violation.resolved_by = resolved_by
        violation.resolved_at = datetime.utcnow()
        violation.resolution_notes = resolution_notes
        
        if fine_amount:
            violation.fine_amount = fine_amount
        
        await self.session.commit()
        return violation
    
    async def get_violation_statistics(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get violation statistics for a hostel."""
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)
        
        query = self.session.query(
            func.count(PolicyViolation.id).label("total_violations"),
            func.sum(func.case([(PolicyViolation.status == "resolved", 1)], else_=0)).label("resolved_violations"),
            func.sum(func.case([(PolicyViolation.severity == "critical", 1)], else_=0)).label("critical_violations"),
            func.sum(func.case([(PolicyViolation.fine_amount.isnot(None), 1)], else_=0)).label("violations_with_fines"),
            func.sum(PolicyViolation.fine_amount).label("total_fines"),
            func.sum(func.case([(PolicyViolation.fine_paid == True, PolicyViolation.fine_amount)], else_=0)).label("fines_collected")
        ).filter(
            and_(
                PolicyViolation.hostel_id == hostel_id,
                PolicyViolation.violation_date >= cutoff_date
            )
        )
        
        result = await query.first()
        
        # Get breakdown by severity
        severity_breakdown = await self.session.query(
            PolicyViolation.severity,
            func.count(PolicyViolation.id).label("count")
        ).filter(
            and_(
                PolicyViolation.hostel_id == hostel_id,
                PolicyViolation.violation_date >= cutoff_date
            )
        ).group_by(PolicyViolation.severity).all()
        
        return {
            "period_days": period_days,
            "total_violations": result.total_violations or 0,
            "resolved_violations": result.resolved_violations or 0,
            "pending_violations": (result.total_violations or 0) - (result.resolved_violations or 0),
            "resolution_rate": (result.resolved_violations / max(result.total_violations, 1)) * 100,
            "critical_violations": result.critical_violations or 0,
            "violations_with_fines": result.violations_with_fines or 0,
            "total_fines": float(result.total_fines or 0),
            "fines_collected": float(result.fines_collected or 0),
            "fine_collection_rate": (float(result.fines_collected or 0) / max(float(result.total_fines or 1), 1)) * 100,
            "severity_breakdown": {
                row.severity: row.count for row in severity_breakdown
            }
        }