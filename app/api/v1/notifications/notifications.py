"""
Notification Management API Endpoints

Comprehensive notification management including sending notifications via multiple 
channels (email, SMS, push, in-app), bulk operations, and analytics.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.notification.notification_service import NotificationService
from app.services.notification.in_app_notification_service import InAppNotificationService
from app.schemas.notification import (
    NotificationResponse,
    NotificationDetail,
    NotificationCreate,
    InAppNotificationResponse,
    NotificationStats,
    BulkNotificationRequest,
    BulkNotificationResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def get_notification_service() -> NotificationService:
    """
    Dependency injection for NotificationService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "NotificationService dependency must be configured in your DI container"
    )


def get_in_app_service() -> InAppNotificationService:
    """
    Dependency injection for InAppNotificationService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "InAppNotificationService dependency must be configured in your DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()):
    """
    Extract and validate the current authenticated user.
    
    Returns:
        Current authenticated user object
    """
    try:
        return auth.get_current_user()
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


def verify_admin_user(current_user) -> None:
    """
    Verify that the current user has admin privileges.
    
    Args:
        current_user: Authenticated user object
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not getattr(current_user, 'is_admin', False) and \
       not getattr(current_user, 'is_superuser', False):
        logger.warning(
            f"Unauthorized admin access attempt by user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )


@router.post(
    "",
    response_model=NotificationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Send notification",
    description="Send a notification via configured channels (email, SMS, push, in-app)",
    response_description="Notification sent successfully",
)
async def send_notification(
    payload: NotificationCreate,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user = Depends(get_current_user),
) -> NotificationDetail:
    """
    Send a notification via one or more channels.
    
    This endpoint allows sending notifications through multiple channels including:
    - Email
    - SMS
    - Push notifications
    - In-app notifications
    
    Requires admin privileges for system-wide notifications.
    
    Args:
        payload: Notification creation data
        notification_service: Injected notification service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationDetail: Details of the sent notification
        
    Raises:
        HTTPException: If sending fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(
            f"Sending notification: type={payload.notification_type}, "
            f"channels={payload.channels}, sent_by={current_user.id}"
        )
        
        result = notification_service.send_notification(data=payload)
        notification = result.unwrap()
        
        logger.info(
            f"Notification sent successfully: notification_id={notification.id}, "
            f"channels={payload.channels}"
        )
        
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to send notification: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification: {str(e)}"
        )


@router.post(
    "/bulk",
    response_model=BulkNotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send bulk notifications",
    description="Send notifications to multiple recipients asynchronously",
    response_description="Bulk notification job accepted",
)
async def send_bulk_notifications(
    payload: BulkNotificationRequest,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user = Depends(get_current_user),
) -> BulkNotificationResponse:
    """
    Send notifications to multiple recipients.
    
    This endpoint accepts a bulk notification request and processes it asynchronously.
    Use this for sending notifications to large groups of users efficiently.
    
    Requires admin privileges.
    
    Args:
        payload: Bulk notification request data
        notification_service: Injected notification service
        current_user: Authenticated user from dependency
        
    Returns:
        BulkNotificationResponse: Job information and tracking ID
        
    Raises:
        HTTPException: If request fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        recipient_count = len(payload.recipients) if hasattr(payload, 'recipients') else 0
        logger.info(
            f"Initiating bulk notification: recipients={recipient_count}, "
            f"sent_by={current_user.id}"
        )
        
        result = notification_service.send_bulk_notifications(data=payload)
        response = result.unwrap()
        
        logger.info(
            f"Bulk notification job created: job_id={response.get('job_id')}, "
            f"recipients={recipient_count}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to send bulk notifications: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk notifications: {str(e)}"
        )


@router.get(
    "/me",
    response_model=List[InAppNotificationResponse],
    summary="Get my notifications",
    description="Retrieve in-app notifications for the current user with pagination and filtering",
    response_description="List of user notifications",
)
async def list_my_notifications(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    read_status: Optional[bool] = Query(None, description="Filter by read status (true/false)"),
    in_app_service: InAppNotificationService = Depends(get_in_app_service),
    current_user = Depends(get_current_user),
) -> List[InAppNotificationResponse]:
    """
    List in-app notifications for the current user.
    
    Supports pagination and filtering by read status. Results are typically 
    ordered by creation date (newest first).
    
    Args:
        page: Page number (starting from 1)
        page_size: Number of items per page (max 100)
        read_status: Optional filter for read/unread notifications
        in_app_service: Injected in-app notification service
        current_user: Authenticated user from dependency
        
    Returns:
        List[InAppNotificationResponse]: Paginated list of notifications
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(
            f"Fetching notifications for user_id={current_user.id}, "
            f"page={page}, page_size={page_size}, read_status={read_status}"
        )
        
        filters = {
            "read": read_status,
            "page": page,
            "page_size": page_size
        }
        
        result = in_app_service.list_notifications_for_user(
            user_id=current_user.id,
            filters=filters,
        )
        
        notifications = result.unwrap()
        
        logger.info(
            f"Retrieved {len(notifications)} notification(s) for user_id={current_user.id}"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(
            f"Failed to list notifications for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )


@router.get(
    "/me/unread-count",
    summary="Get unread notification count",
    description="Get the total number of unread notifications for the current user",
    response_description="Unread notification count",
)
async def get_unread_count(
    in_app_service: InAppNotificationService = Depends(get_in_app_service),
    current_user = Depends(get_current_user),
) -> dict:
    """
    Get the count of unread notifications for the current user.
    
    Useful for displaying notification badges in the UI.
    
    Args:
        in_app_service: Injected in-app notification service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Contains 'unread_count' field
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching unread count for user_id={current_user.id}")
        
        result = in_app_service.get_unread_count(user_id=current_user.id)
        count_data = result.unwrap()
        
        logger.debug(
            f"Unread count for user_id={current_user.id}: {count_data.get('unread_count', 0)}"
        )
        
        return count_data
        
    except Exception as e:
        logger.error(
            f"Failed to get unread count for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve unread count"
        )


@router.post(
    "/{notification_id}/read",
    summary="Mark notification as read",
    description="Mark a specific notification as read for the current user",
    response_description="Notification marked as read",
)
async def mark_as_read(
    notification_id: str,
    in_app_service: InAppNotificationService = Depends(get_in_app_service),
    current_user = Depends(get_current_user),
) -> dict:
    """
    Mark a specific notification as read.
    
    Updates the read status and timestamp for the specified notification.
    Users can only mark their own notifications as read.
    
    Args:
        notification_id: ID of the notification to mark as read
        in_app_service: Injected in-app notification service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Success confirmation
        
    Raises:
        HTTPException: If operation fails or notification not found
    """
    try:
        logger.info(
            f"Marking notification as read: notification_id={notification_id}, "
            f"user_id={current_user.id}"
        )
        
        result = in_app_service.mark_as_read(
            user_id=current_user.id,
            notification_id=notification_id,
        )
        
        response = result.unwrap()
        
        logger.info(
            f"Notification marked as read: notification_id={notification_id}"
        )
        
        return response
        
    except ValueError as e:
        logger.warning(
            f"Notification not found: notification_id={notification_id}, "
            f"user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to mark notification as read: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.post(
    "/me/read-all",
    summary="Mark all notifications as read",
    description="Mark all unread notifications as read for the current user",
    response_description="All notifications marked as read",
)
async def mark_all_as_read(
    in_app_service: InAppNotificationService = Depends(get_in_app_service),
    current_user = Depends(get_current_user),
) -> dict:
    """
    Mark all notifications as read for the current user.
    
    Efficiently updates all unread notifications to read status in a single operation.
    
    Args:
        in_app_service: Injected in-app notification service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Contains count of notifications marked as read
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        logger.info(f"Marking all notifications as read for user_id={current_user.id}")
        
        result = in_app_service.mark_all_as_read(user_id=current_user.id)
        response = result.unwrap()
        
        count = response.get('count', 0)
        logger.info(
            f"Marked {count} notification(s) as read for user_id={current_user.id}"
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"Failed to mark all as read for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read"
        )


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
    description="Delete a specific notification for the current user",
    response_description="Notification deleted successfully",
)
async def delete_notification(
    notification_id: str,
    in_app_service: InAppNotificationService = Depends(get_in_app_service),
    current_user = Depends(get_current_user),
) -> None:
    """
    Delete a specific notification.
    
    Permanently removes a notification from the user's notification list.
    Users can only delete their own notifications.
    
    Args:
        notification_id: ID of the notification to delete
        in_app_service: Injected in-app notification service
        current_user: Authenticated user from dependency
        
    Raises:
        HTTPException: If deletion fails or notification not found
    """
    try:
        logger.info(
            f"Deleting notification: notification_id={notification_id}, "
            f"user_id={current_user.id}"
        )
        
        result = in_app_service.delete_notification(
            user_id=current_user.id,
            notification_id=notification_id,
        )
        result.unwrap()
        
        logger.info(
            f"Notification deleted successfully: notification_id={notification_id}"
        )
        
    except ValueError as e:
        logger.warning(
            f"Notification not found for deletion: notification_id={notification_id}, "
            f"user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to delete notification: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )


@router.get(
    "/analytics",
    response_model=NotificationStats,
    summary="Get notification analytics",
    description="Retrieve system-wide notification analytics and statistics (Admin only)",
    response_description="Notification analytics data",
)
async def get_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    notification_service: NotificationService = Depends(get_notification_service),
    current_user = Depends(get_current_user),
) -> NotificationStats:
    """
    Get system-wide notification analytics.
    
    Provides comprehensive analytics including:
    - Total notifications sent
    - Delivery rates by channel
    - Success/failure rates
    - Time-based trends
    
    Requires admin privileges.
    
    Args:
        start_date: Optional start date for analytics range (ISO format)
        end_date: Optional end date for analytics range (ISO format)
        notification_service: Injected notification service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationStats: Comprehensive analytics data
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(
            f"Fetching notification analytics: start_date={start_date}, "
            f"end_date={end_date}, requested_by={current_user.id}"
        )
        
        # Validate date formats if provided
        if start_date:
            try:
                datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DD)"
                )
        
        if end_date:
            try:
                datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DD)"
                )
        
        result = notification_service.get_notification_analytics(
            start_date=start_date,
            end_date=end_date,
        )
        
        stats = result.unwrap()
        
        logger.info(
            f"Analytics retrieved successfully for date range: "
            f"{start_date or 'all'} to {end_date or 'all'}"
        )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to retrieve analytics: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )