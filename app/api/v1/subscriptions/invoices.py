# --- File: C:\Hostel-Main\app\api\v1\subscriptions\invoices.py ---
"""
Subscription invoice management endpoints.

This module handles invoice operations including generation, retrieval,
payment tracking, and status management.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.subscription.subscription_invoice_service import SubscriptionInvoiceService
from app.schemas.subscription import (
    SubscriptionInvoice,
    InvoiceSummary,
)
from .dependencies import (
    get_invoice_service,
    get_current_user,
    get_subscription_service,
    verify_subscription_access,
    verify_hostel_access,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions - Invoices"],
)


class MarkPaidRequest(BaseModel):
    """Request body for marking invoice as paid."""
    paid_amount: float = Field(..., gt=0, description="Amount paid")
    payment_reference: str = Field(..., min_length=1, max_length=200, description="Payment reference/transaction ID")
    payment_date: Optional[str] = Field(None, description="Payment date (ISO format)")
    payment_method: Optional[str] = Field(None, description="Payment method used")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class UpdateStatusRequest(BaseModel):
    """Request body for updating invoice status."""
    status: str = Field(..., description="New status (pending, paid, overdue, cancelled)")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for status change")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class VoidInvoiceRequest(BaseModel):
    """Request body for voiding invoice."""
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for voiding")


class BatchGenerateRequest(BaseModel):
    """Request body for batch invoice generation."""
    subscription_ids: List[str] = Field(..., min_items=1, description="List of subscription IDs")
    date: Optional[str] = Field(None, description="Invoice date (ISO format)")
    due_date: Optional[str] = Field(None, description="Due date (ISO format)")


@router.post(
    "/{subscription_id}/billing-cycles/{billing_cycle_id}/invoices",
    response_model=SubscriptionInvoice,
    status_code=status.HTTP_201_CREATED,
    summary="Generate invoice for billing cycle",
    description="Generate an invoice for a specific billing cycle.",
    responses={
        201: {"description": "Invoice generated successfully"},
        400: {"description": "Invalid request or invoice already exists"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription or billing cycle not found"},
    }
)
async def generate_invoice_for_cycle(
    subscription_id: str,
    billing_cycle_id: str,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Generate invoice for a billing cycle.
    
    Args:
        subscription_id: Subscription identifier
        billing_cycle_id: Billing cycle identifier
        invoice_service: Invoice service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Generated invoice
    """
    logger.info(f"User {current_user.id} generating invoice for cycle {billing_cycle_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = invoice_service.generate_invoice(
        subscription_id=subscription_id,
        billing_cycle_id=billing_cycle_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to generate invoice: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    invoice = result.unwrap()
    logger.info(f"Successfully generated invoice {invoice.id}")
    
    return invoice


@router.post(
    "/invoices/batch-generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch generate invoices",
    description="Generate invoices for multiple subscriptions (admin only).",
    responses={
        202: {"description": "Batch generation initiated"},
        400: {"description": "Invalid request"},
        403: {"description": "Admin access required"},
    }
)
async def generate_invoices_batch(
    payload: BatchGenerateRequest,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Batch generate invoices.
    
    Args:
        payload: Batch generation request
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Batch generation status
    """
    logger.info(f"User {current_user.id} batch generating {len(payload.subscription_ids)} invoices")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for batch operations"
        )
    
    result = invoice_service.generate_invoices_batch(data=payload.dict())
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to batch generate invoices: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/invoices/{invoice_id}",
    response_model=SubscriptionInvoice,
    summary="Get invoice by ID",
    description="Retrieve detailed invoice information.",
    responses={
        200: {"description": "Invoice details"},
        403: {"description": "Access forbidden"},
        404: {"description": "Invoice not found"},
    }
)
async def get_invoice(
    invoice_id: str,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Get invoice by ID.
    
    Args:
        invoice_id: Invoice identifier
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Invoice details
    """
    logger.info(f"User {current_user.id} retrieving invoice {invoice_id}")
    
    result = invoice_service.get_invoice(invoice_id=invoice_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get invoice: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )
    
    invoice = result.unwrap()
    
    # Verify access to invoice's subscription
    if not getattr(current_user, 'is_admin', False):
        user_hostels = set(getattr(current_user, 'hostel_ids', []))
        if invoice.hostel_id not in user_hostels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this invoice"
            )
    
    return invoice


@router.get(
    "/invoices/by-number/{invoice_number}",
    response_model=SubscriptionInvoice,
    summary="Get invoice by number",
    description="Retrieve invoice by its unique invoice number.",
    responses={
        200: {"description": "Invoice details"},
        403: {"description": "Access forbidden"},
        404: {"description": "Invoice not found"},
    }
)
async def get_invoice_by_number(
    invoice_number: str,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Get invoice by invoice number.
    
    Args:
        invoice_number: Invoice number
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Invoice details
    """
    logger.info(f"User {current_user.id} retrieving invoice by number: {invoice_number}")
    
    result = invoice_service.get_invoice_by_number(invoice_number=invoice_number)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get invoice by number: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_number} not found"
        )
    
    invoice = result.unwrap()
    
    # Verify access
    if not getattr(current_user, 'is_admin', False):
        user_hostels = set(getattr(current_user, 'hostel_ids', []))
        if invoice.hostel_id not in user_hostels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this invoice"
            )
    
    return invoice


@router.get(
    "/{subscription_id}/invoices",
    response_model=List[SubscriptionInvoice],
    summary="List invoices for subscription",
    description="Get all invoices for a specific subscription.",
    responses={
        200: {"description": "List of invoices"},
        403: {"description": "Access forbidden"},
    }
)
async def list_invoices_for_subscription(
    subscription_id: str,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
) -> List[SubscriptionInvoice]:
    """
    List invoices for subscription.
    
    Args:
        subscription_id: Subscription identifier
        invoice_service: Invoice service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        status_filter: Optional status filter
        
    Returns:
        List of invoices
    """
    logger.info(f"User {current_user.id} listing invoices for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = invoice_service.list_invoices_for_subscription(
        subscription_id=subscription_id,
        filters={"status": status_filter} if status_filter else {}
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list invoices: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/hostels/{hostel_id}/invoices",
    response_model=List[SubscriptionInvoice],
    summary="List invoices for hostel",
    description="Get all invoices for a specific hostel.",
    responses={
        200: {"description": "List of invoices"},
        403: {"description": "Access forbidden"},
    }
)
async def list_invoices_for_hostel(
    hostel_id: str,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, description="Filter by status (pending, paid, overdue, cancelled)"),
) -> List[SubscriptionInvoice]:
    """
    List invoices for hostel.
    
    Args:
        hostel_id: Hostel identifier
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        status_filter: Optional status filter
        
    Returns:
        List of invoices
    """
    logger.info(f"User {current_user.id} listing invoices for hostel {hostel_id}")
    
    # Verify access
    await verify_hostel_access(hostel_id, current_user)
    
    result = invoice_service.list_invoices_for_hostel(
        hostel_id=hostel_id,
        filters={"status": status_filter} if status_filter else {},
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list invoices: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/invoices/search",
    response_model=List[SubscriptionInvoice],
    summary="Search invoices",
    description="Search invoices by various criteria.",
    responses={
        200: {"description": "Search results"},
    }
)
async def search_invoices(
    query: Optional[str] = Query(None, description="Search query (invoice number, hostel name, etc.)"),
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> List[SubscriptionInvoice]:
    """
    Search invoices.
    
    Args:
        query: Search query
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        List of matching invoices
    """
    logger.info(f"User {current_user.id} searching invoices: {query}")
    
    result = invoice_service.search_invoices(filters={"query": query})
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to search invoices: {error}")
        return []
    
    invoices = result.unwrap()
    
    # Filter by user's hostels if not admin
    if not getattr(current_user, 'is_admin', False):
        user_hostels = set(getattr(current_user, 'hostel_ids', []))
        invoices = [inv for inv in invoices if inv.hostel_id in user_hostels]
    
    return invoices


@router.get(
    "/invoices/overdue",
    response_model=List[SubscriptionInvoice],
    summary="Get overdue invoices",
    description="Retrieve all overdue invoices.",
    responses={
        200: {"description": "List of overdue invoices"},
    }
)
async def get_overdue_invoices(
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> List[SubscriptionInvoice]:
    """
    Get overdue invoices.
    
    Args:
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        List of overdue invoices
    """
    logger.info(f"User {current_user.id} retrieving overdue invoices")
    
    result = invoice_service.get_overdue_invoices()
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get overdue invoices: {error}")
        return []
    
    invoices = result.unwrap()
    
    # Filter by user's hostels if not admin
    if not getattr(current_user, 'is_admin', False):
        user_hostels = set(getattr(current_user, 'hostel_ids', []))
        invoices = [inv for inv in invoices if inv.hostel_id in user_hostels]
    
    return invoices


@router.post(
    "/invoices/{invoice_id}/mark-paid",
    response_model=SubscriptionInvoice,
    summary="Mark invoice as paid",
    description="Record payment for an invoice.",
    responses={
        200: {"description": "Invoice marked as paid"},
        400: {"description": "Invalid payment data"},
        403: {"description": "Access forbidden"},
        404: {"description": "Invoice not found"},
    }
)
async def mark_invoice_paid(
    invoice_id: str,
    payload: MarkPaidRequest,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Mark invoice as paid.
    
    Args:
        invoice_id: Invoice identifier
        payload: Payment details
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Updated invoice
    """
    logger.info(f"User {current_user.id} marking invoice {invoice_id} as paid")
    
    # Verify admin access (only admins can mark invoices as paid)
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to mark invoices as paid"
        )
    
    result = invoice_service.mark_invoice_paid(
        invoice_id=invoice_id,
        data=payload.dict()
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to mark invoice as paid: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    invoice = result.unwrap()
    logger.info(f"Successfully marked invoice {invoice_id} as paid")
    
    return invoice


@router.post(
    "/invoices/{invoice_id}/status",
    response_model=SubscriptionInvoice,
    summary="Update invoice status",
    description="Update the status of an invoice (admin only).",
    responses={
        200: {"description": "Invoice status updated"},
        400: {"description": "Invalid status or request"},
        403: {"description": "Admin access required"},
        404: {"description": "Invoice not found"},
    }
)
async def update_invoice_status(
    invoice_id: str,
    payload: UpdateStatusRequest,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Update invoice status.
    
    Args:
        invoice_id: Invoice identifier
        payload: Status update request
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Updated invoice
    """
    logger.info(f"User {current_user.id} updating invoice {invoice_id} status to {payload.status}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to update invoice status"
        )
    
    result = invoice_service.update_invoice_status(
        invoice_id=invoice_id,
        data=payload.dict()
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update invoice status: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    invoice = result.unwrap()
    logger.info(f"Successfully updated invoice {invoice_id} status")
    
    return invoice


@router.post(
    "/invoices/{invoice_id}/void",
    response_model=SubscriptionInvoice,
    summary="Void invoice",
    description="Void an invoice (admin only). Voided invoices cannot be paid.",
    responses={
        200: {"description": "Invoice voided"},
        400: {"description": "Cannot void invoice"},
        403: {"description": "Admin access required"},
        404: {"description": "Invoice not found"},
    }
)
async def void_invoice(
    invoice_id: str,
    payload: VoidInvoiceRequest,
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionInvoice:
    """
    Void an invoice.
    
    Args:
        invoice_id: Invoice identifier
        payload: Void request with reason
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Voided invoice
    """
    logger.info(f"User {current_user.id} voiding invoice {invoice_id}, reason: {payload.reason}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to void invoices"
        )
    
    result = invoice_service.void_invoice(
        invoice_id=invoice_id,
        data=payload.dict()
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to void invoice: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    invoice = result.unwrap()
    logger.info(f"Successfully voided invoice {invoice_id}")
    
    return invoice


@router.get(
    "/invoices/summary",
    response_model=InvoiceSummary,
    summary="Get invoice summary",
    description="Get aggregated invoice statistics (admin only).",
    responses={
        200: {"description": "Invoice summary"},
        403: {"description": "Admin access required"},
    }
)
async def get_invoice_summary(
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> InvoiceSummary:
    """
    Get invoice summary.
    
    Args:
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Invoice summary statistics
    """
    logger.info(f"User {current_user.id} retrieving invoice summary")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view invoice summary"
        )
    
    result = invoice_service.get_invoice_summary()
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get invoice summary: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/invoices/revenue",
    summary="Get total revenue",
    description="Calculate total revenue for a period (admin only).",
    responses={
        200: {"description": "Revenue data"},
        403: {"description": "Admin access required"},
    }
)
async def get_total_revenue(
    start_date: Optional[str] = Query(None, description="Period start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Period end date (ISO format)"),
    invoice_service: SubscriptionInvoiceService = Depends(get_invoice_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get total revenue for period.
    
    Args:
        start_date: Optional period start
        end_date: Optional period end
        invoice_service: Invoice service dependency
        current_user: Current authenticated user
        
    Returns:
        Revenue data and breakdown
    """
    logger.info(f"User {current_user.id} calculating revenue from {start_date} to {end_date}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view revenue data"
        )
    
    result = invoice_service.get_total_revenue(
        start_date=start_date,
        end_date=end_date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to calculate revenue: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()