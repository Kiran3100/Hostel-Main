# app/services/workflows/__init__.py
"""
Workflow-related services.

Thin wrappers over wf_* workflow tables:

- ApprovalWorkflowService: generic approval workflow for entities.
- BookingWorkflowService: booking lifecycle workflow.
- ComplaintWorkflowService: complaint lifecycle workflow.
- MaintenanceWorkflowService: maintenance approval & execution workflow.
"""

from .approval_workflow_service import ApprovalWorkflowService
from .booking_workflow_service import BookingWorkflowService
from .complaint_workflow_service import ComplaintWorkflowService
from .maintenance_workflow_service import MaintenanceWorkflowService

__all__ = [
    "ApprovalWorkflowService",
    "BookingWorkflowService",
    "ComplaintWorkflowService",
    "MaintenanceWorkflowService",
]