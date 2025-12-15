# app/api/v1/payments/gateway.py
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentGatewayService
from app.schemas.payment.payment_gateway import (
    GatewayRequest,
    GatewayResponse,
    GatewayWebhook,
    GatewayCallback,
)
from . import CurrentUser, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Gateway"])


def _get_service(session: Session) -> PaymentGatewayService:
    uow = UnitOfWork(session)
    return PaymentGatewayService(uow)


@router.post("/order", response_model=GatewayResponse)
def create_gateway_order(
    payload: GatewayRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> GatewayResponse:
    """
    Create/refresh a gateway order for an existing Payment.
    """
    service = _get_service(session)
    # Expected: create_order(data: GatewayRequest, requester_id: UUID) -> GatewayResponse
    return service.create_order(
        data=payload,
        requester_id=current_user.id,
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def gateway_webhook(
    payload: GatewayWebhook,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """
    Gateway webhook endpoint to update payment status (unauthenticated; secured by gateway secret).
    """
    service = _get_service(session)
    # Expected: handle_webhook(webhook: GatewayWebhook, raw_request: Request) -> None
    await service.handle_webhook(
        webhook=payload,
        raw_request=request,
    )
    return Response(status_code=status.HTTP_200_OK)


@router.post("/callback", response_model=GatewayResponse)
async def gateway_callback(
    payload: GatewayCallback,
    request: Request,
    session: Session = Depends(get_session),
) -> GatewayResponse:
    """
    Browser/server callback endpoint after payment completion.
    """
    service = _get_service(session)
    # Expected: handle_callback(callback: GatewayCallback, raw_request: Request) -> GatewayResponse
    return await service.handle_callback(
        callback=payload,
        raw_request=request,
    )