# --- File: C:\Hostel-Main\app\services\hostel\hostel_policy_service.py ---
"""
Hostel policy service for comprehensive policy and rules management.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_policy import HostelPolicy, PolicyAcknowledgment, PolicyViolation
from app.repositories.hostel.hostel_policy_repository import (
    HostelPolicyRepository,
    PolicyAcknowledgmentRepository,
    PolicyViolationRepository
)
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    BusinessRuleViolationError,
    DuplicateResourceError
)
from app.services.base.base_service import BaseService


class HostelPolicyService(BaseService):
    """
    Hostel policy service for policy and rules management.
    
    Handles policy CRUD, version control, acknowledgments,
    violations, and compliance tracking.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.policy_repo = HostelPolicyRepository(session)
        self.acknowledgment_repo = PolicyAcknowledgmentRepository(session)
        self.violation_repo = PolicyViolationRepository(session)

    # ===== Policy Management =====

    async def create_policy(
        self,
        hostel_id: UUID,
        policy_data: Dict[str, Any],
        created_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """
        Create a new hostel policy.
        
        Args:
            hostel_id: Hostel UUID
            policy_data: Policy information
            created_by: User ID creating the policy
            
        Returns:
            Created HostelPolicy instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        required_fields = ['policy_type', 'title', 'content']
        for field in required_fields:
            if field not in policy_data or not policy_data[field]:
                raise ValidationError(f"'{field}' is required")
        
        # Validate policy type
        valid_types = [
            'general', 'visitor', 'payment', 'conduct', 
            'security', 'maintenance', 'mess', 'leave'
        ]
        if policy_data['policy_type'] not in valid_types:
            raise ValidationError(
                f"Invalid policy type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Set defaults
        policy_data.setdefault('is_active', True)
        policy_data.setdefault('is_published', False)
        policy_data.setdefault('is_mandatory', False)
        policy_data.setdefault('display_order', 0)
        
        # Create policy
        policy = await self.policy_repo.create_policy(
            hostel_id,
            policy_data,
            created_by
        )
        
        # Log event
        await self._log_event('policy_created', {
            'policy_id': policy.id,
            'hostel_id': hostel_id,
            'policy_type': policy.policy_type,
            'created_by': created_by
        })
        
        return policy

    async def get_policy_by_id(self, policy_id: UUID) -> HostelPolicy:
        """
        Get policy by ID and increment view count.
        
        Args:
            policy_id: Policy UUID
            
        Returns:
            HostelPolicy instance
            
        Raises:
            ResourceNotFoundError: If policy not found
        """
        policy = await self.policy_repo.get_by_id(policy_id)
        if not policy:
            raise ResourceNotFoundError(f"Policy {policy_id} not found")
        
        # Increment view count
        await self.policy_repo.increment_views(policy_id)
        
        return policy

    async def update_policy(
        self,
        policy_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """
        Update policy information.
        
        Args:
            policy_id: Policy UUID
            update_data: Fields to update
            updated_by: User ID performing update
            
        Returns:
            Updated HostelPolicy instance
        """
        policy = await self.get_policy_by_id(policy_id)
        
        # If content is being updated, create new version instead
        if 'content' in update_data and update_data['content'] != policy.content:
            return await self.create_policy_version(
                policy_id,
                update_data['content'],
                update_data.get('version_notes'),
                updated_by
            )
        
        # Regular update
        update_data['last_modified_by'] = updated_by
        updated_policy = await self.policy_repo.update(policy_id, update_data)
        
        # Log event
        await self._log_event('policy_updated', {
            'policy_id': policy_id,
            'updated_fields': list(update_data.keys()),
            'updated_by': updated_by
        })
        
        return updated_policy

    async def delete_policy(
        self,
        policy_id: UUID,
        deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Delete a policy (archives it).
        
        Args:
            policy_id: Policy UUID
            deleted_by: User ID performing deletion
            
        Returns:
            True if successful
        """
        policy = await self.get_policy_by_id(policy_id)
        
        # Check if policy has acknowledgments
        acknowledgments = await self.acknowledgment_repo.find_by_criteria({
            'policy_id': policy_id
        })
        
        if acknowledgments and policy.is_mandatory:
            raise BusinessRuleViolationError(
                f"Cannot delete mandatory policy with {len(acknowledgments)} acknowledgments. Archive instead."
            )
        
        # Archive policy instead of hard delete
        await self.policy_repo.archive_policy(policy_id)
        
        # Log event
        await self._log_event('policy_deleted', {
            'policy_id': policy_id,
            'deleted_by': deleted_by
        })
        
        return True

    # ===== Policy Queries =====

    async def get_hostel_policies(
        self,
        hostel_id: UUID,
        policy_type: Optional[str] = None,
        only_published: bool = True
    ) -> List[HostelPolicy]:
        """
        Get policies for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            policy_type: Filter by policy type
            only_published: Show only published policies
            
        Returns:
            List of policies
        """
        if only_published:
            return await self.policy_repo.find_published_policies(
                hostel_id,
                category=policy_type
            )
        else:
            return await self.policy_repo.find_by_hostel(
                hostel_id,
                policy_type,
                only_current=True
            )

    async def get_mandatory_policies(
        self,
        hostel_id: UUID,
        student_id: Optional[UUID] = None
    ) -> List[HostelPolicy]:
        """
        Get mandatory policies requiring acknowledgment.
        
        Args:
            hostel_id: Hostel UUID
            student_id: Optional student ID to filter unacknowledged
            
        Returns:
            List of mandatory policies
        """
        return await self.policy_repo.find_mandatory_policies(hostel_id, student_id)

    async def get_policies_by_category(
        self,
        hostel_id: UUID
    ) -> Dict[str, List[HostelPolicy]]:
        """
        Get policies grouped by category.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary mapping category to policies
        """
        policies = await self.policy_repo.find_published_policies(hostel_id)
        
        categorized = {}
        for policy in policies:
            category = policy.category or policy.policy_type
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(policy)
        
        return categorized

    # ===== Policy Lifecycle =====

    async def publish_policy(
        self,
        policy_id: UUID,
        approved_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """
        Publish a policy to make it visible to students.
        
        Args:
            policy_id: Policy UUID
            approved_by: User ID approving publication
            
        Returns:
            Published HostelPolicy instance
        """
        policy = await self.policy_repo.publish_policy(policy_id, approved_by)
        
        # Log event
        await self._log_event('policy_published', {
            'policy_id': policy_id,
            'approved_by': approved_by
        })
        
        return policy

    async def unpublish_policy(
        self,
        policy_id: UUID,
        reason: Optional[str] = None
    ) -> HostelPolicy:
        """
        Unpublish a policy.
        
        Args:
            policy_id: Policy UUID
            reason: Reason for unpublishing
            
        Returns:
            Updated HostelPolicy instance
        """
        policy = await self.policy_repo.update(policy_id, {
            'is_published': False
        })
        
        # Log event
        await self._log_event('policy_unpublished', {
            'policy_id': policy_id,
            'reason': reason
        })
        
        return policy

    async def archive_policy(
        self,
        policy_id: UUID,
        effective_until: Optional[datetime] = None
    ) -> HostelPolicy:
        """
        Archive a policy.
        
        Args:
            policy_id: Policy UUID
            effective_until: Optional end date
            
        Returns:
            Archived HostelPolicy instance
        """
        return await self.policy_repo.archive_policy(policy_id, effective_until)

    async def create_policy_version(
        self,
        policy_id: UUID,
        new_content: str,
        version_notes: Optional[str] = None,
        updated_by: Optional[UUID] = None
    ) -> HostelPolicy:
        """
        Create a new version of an existing policy.
        
        Args:
            policy_id: Original policy UUID
            new_content: Updated policy content
            version_notes: Notes about changes
            updated_by: User ID making the update
            
        Returns:
            New policy version
        """
        new_policy = await self.policy_repo.update_policy_version(
            policy_id,
            new_content,
            version_notes,
            updated_by
        )
        
        # Log event
        await self._log_event('policy_version_created', {
            'original_policy_id': policy_id,
            'new_policy_id': new_policy.id,
            'version': new_policy.version,
            'updated_by': updated_by
        })
        
        return new_policy

    # ===== Acknowledgments =====

    async def acknowledge_policy(
        self,
        policy_id: UUID,
        student_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        digital_signature: Optional[str] = None
    ) -> PolicyAcknowledgment:
        """
        Record student acknowledgment of a policy.
        
        Args:
            policy_id: Policy UUID
            student_id: Student UUID
            ip_address: Client IP address
            user_agent: Client user agent
            digital_signature: Optional digital signature
            
        Returns:
            Created PolicyAcknowledgment instance
            
        Raises:
            ResourceNotFoundError: If policy not found
        """
        policy = await self.get_policy_by_id(policy_id)
        
        # Create acknowledgment
        acknowledgment = await self.acknowledgment_repo.acknowledge_policy(
            policy_id,
            student_id,
            policy.version,
            ip_address,
            user_agent,
            digital_signature
        )
        
        # Log event
        await self._log_event('policy_acknowledged', {
            'policy_id': policy_id,
            'student_id': student_id,
            'acknowledgment_id': acknowledgment.id
        })
        
        return acknowledgment

    async def get_student_acknowledgments(
        self,
        student_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> List[PolicyAcknowledgment]:
        """
        Get acknowledgments by a student.
        
        Args:
            student_id: Student UUID
            hostel_id: Optional hostel filter
            
        Returns:
            List of acknowledgments
        """
        return await self.acknowledgment_repo.find_student_acknowledgments(
            student_id,
            hostel_id
        )

    async def get_acknowledgment_status(
        self,
        student_id: UUID,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive acknowledgment status for a student.
        
        Args:
            student_id: Student UUID
            hostel_id: Hostel UUID
            
        Returns:
            Acknowledgment status summary
        """
        return await self.acknowledgment_repo.get_acknowledgment_status(
            student_id,
            hostel_id
        )

    async def check_compliance(
        self,
        student_id: UUID,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Check if student is compliant with mandatory policies.
        
        Args:
            student_id: Student UUID
            hostel_id: Hostel UUID
            
        Returns:
            Compliance status
        """
        status = await self.get_acknowledgment_status(student_id, hostel_id)
        
        is_compliant = status['compliance_percentage'] == 100
        
        return {
            'student_id': student_id,
            'hostel_id': hostel_id,
            'is_compliant': is_compliant,
            'compliance_percentage': status['compliance_percentage'],
            'pending_count': len(status['pending_policies']),
            'pending_policies': status['pending_policies']
        }

    # ===== Violations =====

    async def report_violation(
        self,
        policy_id: UUID,
        student_id: UUID,
        hostel_id: UUID,
        violation_data: Dict[str, Any],
        reported_by: UUID
    ) -> PolicyViolation:
        """
        Report a policy violation.
        
        Args:
            policy_id: Policy UUID
            student_id: Student UUID
            hostel_id: Hostel UUID
            violation_data: Violation details
            reported_by: User ID reporting violation
            
        Returns:
            Created PolicyViolation instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        required_fields = ['violation_date', 'description', 'severity']
        for field in required_fields:
            if field not in violation_data:
                raise ValidationError(f"'{field}' is required")
        
        # Validate severity
        valid_severities = ['minor', 'moderate', 'major', 'critical']
        if violation_data['severity'] not in valid_severities:
            raise ValidationError(
                f"Invalid severity. Must be one of: {', '.join(valid_severities)}"
            )
        
        # Create violation
        violation = await self.violation_repo.report_violation(
            policy_id,
            student_id,
            hostel_id,
            violation_data,
            reported_by
        )
        
        # Log event
        await self._log_event('violation_reported', {
            'violation_id': violation.id,
            'policy_id': policy_id,
            'student_id': student_id,
            'severity': violation.severity,
            'reported_by': reported_by
        })
        
        return violation

    async def get_student_violations(
        self,
        student_id: UUID,
        status: Optional[str] = None
    ) -> List[PolicyViolation]:
        """
        Get violations by a student.
        
        Args:
            student_id: Student UUID
            status: Optional status filter
            
        Returns:
            List of violations
        """
        return await self.violation_repo.find_violations_by_student(
            student_id,
            status
        )

    async def get_hostel_violations(
        self,
        hostel_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[PolicyViolation]:
        """
        Get violations for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            status: Optional status filter
            severity: Optional severity filter
            
        Returns:
            List of violations
        """
        return await self.violation_repo.find_violations_by_hostel(
            hostel_id,
            status,
            severity
        )

    async def resolve_violation(
        self,
        violation_id: UUID,
        action_taken: str,
        resolved_by: UUID,
        resolution_notes: Optional[str] = None,
        fine_amount: Optional[int] = None
    ) -> PolicyViolation:
        """
        Resolve a policy violation.
        
        Args:
            violation_id: Violation UUID
            action_taken: Action taken description
            resolved_by: User ID resolving violation
            resolution_notes: Resolution notes
            fine_amount: Optional fine amount
            
        Returns:
            Resolved PolicyViolation instance
        """
        violation = await self.violation_repo.resolve_violation(
            violation_id,
            action_taken,
            resolved_by,
            resolution_notes,
            fine_amount
        )
        
        # Log event
        await self._log_event('violation_resolved', {
            'violation_id': violation_id,
            'resolved_by': resolved_by,
            'fine_amount': fine_amount
        })
        
        return violation

    async def dismiss_violation(
        self,
        violation_id: UUID,
        reason: str,
        dismissed_by: UUID
    ) -> PolicyViolation:
        """
        Dismiss a violation as invalid.
        
        Args:
            violation_id: Violation UUID
            reason: Dismissal reason
            dismissed_by: User ID dismissing violation
            
        Returns:
            Updated PolicyViolation instance
        """
        violation = await self.violation_repo.update(violation_id, {
            'status': 'dismissed',
            'resolved_by': dismissed_by,
            'resolved_at': datetime.utcnow(),
            'resolution_notes': reason
        })
        
        # Log event
        await self._log_event('violation_dismissed', {
            'violation_id': violation_id,
            'reason': reason,
            'dismissed_by': dismissed_by
        })
        
        return violation

    # ===== Analytics and Reporting =====

    async def get_policy_analytics(
        self,
        hostel_id: UUID,
        policy_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get policy engagement and compliance analytics.
        
        Args:
            hostel_id: Hostel UUID
            policy_id: Optional specific policy
            
        Returns:
            Policy analytics
        """
        return await self.policy_repo.get_policy_analytics(hostel_id, policy_id)

    async def get_compliance_report(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Compliance report
        """
        return await self.policy_repo.get_compliance_report(
            hostel_id,
            start_date,
            end_date
        )

    async def get_violation_statistics(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get violation statistics for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            period_days: Analysis period in days
            
        Returns:
            Violation statistics
        """
        return await self.violation_repo.get_violation_statistics(
            hostel_id,
            period_days
        )

    async def identify_policy_gaps(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Identify missing or weak policy areas.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of identified gaps
        """
        policies = await self.policy_repo.find_by_hostel(hostel_id)
        
        # Essential policy types
        essential_types = [
            'general', 'visitor', 'payment', 'conduct', 'security'
        ]
        
        existing_types = set(p.policy_type for p in policies)
        missing_types = set(essential_types) - existing_types
        
        gaps = []
        
        # Check for missing essential policies
        for policy_type in missing_types:
            gaps.append({
                'type': 'missing_policy',
                'policy_type': policy_type,
                'severity': 'high',
                'recommendation': f'Create {policy_type} policy to ensure comprehensive coverage'
            })
        
        # Check for outdated policies (not updated in 1 year)
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        for policy in policies:
            if policy.updated_at < one_year_ago:
                gaps.append({
                    'type': 'outdated_policy',
                    'policy_id': policy.id,
                    'policy_title': policy.title,
                    'last_updated': policy.updated_at,
                    'severity': 'medium',
                    'recommendation': 'Review and update policy to ensure relevance'
                })
        
        return gaps

    # ===== Search =====

    async def search_policies(
        self,
        hostel_id: UUID,
        search_query: str,
        policy_type: Optional[str] = None
    ) -> List[HostelPolicy]:
        """
        Search policies with text query.
        
        Args:
            hostel_id: Hostel UUID
            search_query: Search text
            policy_type: Optional policy type filter
            
        Returns:
            List of matching policies
        """
        return await self.policy_repo.search_policies(
            hostel_id,
            search_query,
            policy_type
        )

    # ===== Helper Methods =====

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        pass