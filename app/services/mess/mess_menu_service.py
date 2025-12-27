# app/services/mess/mess_menu_service.py
"""
Mess Menu Service

Manages daily mess menus:
- CRUD operations for menus
- Menu retrieval and filtering
- Publishing/unpublishing workflows
- Menu validation and consistency checks

Performance Optimizations:
- Efficient date-based queries
- Caching for frequently accessed menus
- Batch operations support
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, timedelta
from calendar import monthrange

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import MessMenuRepository
from app.schemas.mess import (
    MessMenu,
    MessMenuBase,
    MessMenuCreate,
    MessMenuUpdate,
    WeeklyMenu,
    DailyMenuSummary,
    TodayMenu,
)
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessLogicException,
    DuplicateEntryException,
)


class MessMenuService:
    """
    High-level service for mess menus.
    
    This service manages:
    - Menu CRUD operations
    - Menu publication workflows
    - Date-based menu retrieval
    - Menu consistency validation
    """

    def __init__(self, menu_repo: MessMenuRepository) -> None:
        """
        Initialize the mess menu service.
        
        Args:
            menu_repo: Repository for menu operations
        """
        self.menu_repo = menu_repo

    # -------------------------------------------------------------------------
    # Menu CRUD Operations
    # -------------------------------------------------------------------------

    def create_menu(
        self,
        db: Session,
        data: MessMenuCreate,
    ) -> MessMenu:
        """
        Create a new mess menu.
        
        Args:
            db: Database session
            data: MessMenuCreate schema with menu details
            
        Returns:
            Created MessMenu schema
            
        Raises:
            ValidationException: If menu data is invalid
            DuplicateEntryException: If menu already exists for the date
        """
        try:
            # Validate menu data
            self._validate_menu_create(data)
            
            # Check for duplicate menu on the same date
            existing = self.menu_repo.get_by_hostel_and_date(
                db,
                data.hostel_id,
                data.menu_date,
            )
            
            if existing:
                raise DuplicateEntryException(
                    f"Menu already exists for hostel {data.hostel_id} on {data.menu_date}"
                )
            
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            payload["is_published"] = False  # New menus start unpublished
            
            obj = self.menu_repo.create(db, payload)
            db.flush()
            
            return MessMenu.model_validate(obj)
            
        except (ValidationException, DuplicateEntryException):
            raise
        except IntegrityError as e:
            db.rollback()
            raise DuplicateEntryException(
                f"Menu already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating menu: {str(e)}"
            )

    def get_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> MessMenu:
        """
        Retrieve a specific menu by ID.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            MessMenu schema
            
        Raises:
            NotFoundException: If menu not found
        """
        try:
            menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Menu with ID {menu_id} not found"
                )
            
            return MessMenu.model_validate(menu)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving menu: {str(e)}"
            )

    def update_menu(
        self,
        db: Session,
        menu_id: UUID,
        data: MessMenuUpdate,
    ) -> MessMenu:
        """
        Update an existing mess menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            data: MessMenuUpdate schema with updated details
            
        Returns:
            Updated MessMenu schema
            
        Raises:
            NotFoundException: If menu not found
            ValidationException: If update data is invalid
            BusinessLogicException: If menu is published and locked
        """
        try:
            menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Menu with ID {menu_id} not found"
                )
            
            # Check if menu can be updated
            self._validate_menu_update(menu, data)
            
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            
            updated = self.menu_repo.update(db, menu, data=payload)
            db.flush()
            
            return MessMenu.model_validate(updated)
            
        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating menu: {str(e)}"
            )

    def delete_menu(
        self,
        db: Session,
        menu_id: UUID,
        force: bool = False,
    ) -> None:
        """
        Delete a mess menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            force: If True, delete even if published
            
        Raises:
            NotFoundException: If menu not found
            BusinessLogicException: If menu is published and force is False
        """
        try:
            menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Menu with ID {menu_id} not found"
                )
            
            # Check if menu can be deleted
            if not force and getattr(menu, 'is_published', False):
                raise BusinessLogicException(
                    "Cannot delete published menu. Unpublish first or use force=True"
                )
            
            self.menu_repo.delete(db, menu)
            db.flush()
            
        except (NotFoundException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting menu: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Menu Retrieval & Filtering
    # -------------------------------------------------------------------------

    def get_menu_by_date(
        self,
        db: Session,
        hostel_id: UUID,
        menu_date: date,
    ) -> Optional[MessMenu]:
        """
        Get menu for a specific hostel and date.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            menu_date: Date of the menu
            
        Returns:
            MessMenu if found, None otherwise
        """
        try:
            menu = self.menu_repo.get_by_hostel_and_date(
                db, hostel_id, menu_date
            )
            
            if not menu:
                return None
            
            return MessMenu.model_validate(menu)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving menu for date {menu_date}: {str(e)}"
            )

    def get_today_menu_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        target_date: Optional[date] = None,
    ) -> TodayMenu:
        """
        Get today's menu for a hostel with detailed information.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            target_date: Optional specific date (defaults to today)
            
        Returns:
            TodayMenu schema with complete menu details
            
        Raises:
            NotFoundException: If no menu exists for the date
        """
        try:
            data = self.menu_repo.get_today_menu(
                db=db,
                hostel_id=hostel_id,
                target_date=target_date or date.today(),
            )
            
            if not data:
                target = target_date or date.today()
                raise NotFoundException(
                    f"No menu available for {target.strftime('%Y-%m-%d')}"
                )
            
            return TodayMenu.model_validate(data)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving today's menu: {str(e)}"
            )

    def get_weekly_menu_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        week_start: date,
    ) -> WeeklyMenu:
        """
        Get weekly menu for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            week_start: Start date of the week (should be Monday)
            
        Returns:
            WeeklyMenu schema with menus for the week
            
        Raises:
            ValidationException: If week_start is not a Monday
            NotFoundException: If no weekly menu exists
        """
        try:
            # Validate that week_start is a Monday
            if week_start.weekday() != 0:
                raise ValidationException(
                    "Week must start on a Monday"
                )
            
            data = self.menu_repo.get_weekly_menu(
                db=db,
                hostel_id=hostel_id,
                week_start=week_start,
            )
            
            if not data:
                raise NotFoundException(
                    f"No weekly menu found starting {week_start.strftime('%Y-%m-%d')}"
                )
            
            return WeeklyMenu.model_validate(data)
            
        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving weekly menu: {str(e)}"
            )

    def list_daily_summaries_for_month(
        self,
        db: Session,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> List[DailyMenuSummary]:
        """
        List daily menu summaries for a month.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            year: Year of the month
            month: Month (1-12)
            
        Returns:
            List of DailyMenuSummary schemas
            
        Raises:
            ValidationException: If month is invalid
        """
        try:
            if not (1 <= month <= 12):
                raise ValidationException("Month must be between 1 and 12")
            
            objs = self.menu_repo.get_daily_summaries_for_month(
                db=db,
                hostel_id=hostel_id,
                year=year,
                month=month,
            )
            
            return [DailyMenuSummary.model_validate(o) for o in objs]
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error listing daily summaries for {year}-{month:02d}: {str(e)}"
            )

    def get_menus_for_date_range(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        published_only: bool = False,
    ) -> List[MessMenu]:
        """
        Get all menus for a date range.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the range
            end_date: End date of the range
            published_only: If True, return only published menus
            
        Returns:
            List of MessMenu schemas
            
        Raises:
            ValidationException: If date range is invalid
        """
        try:
            if start_date > end_date:
                raise ValidationException(
                    "Start date must be before or equal to end date"
                )
            
            # Limit date range to prevent excessive queries
            max_days = 90
            if (end_date - start_date).days > max_days:
                raise ValidationException(
                    f"Date range cannot exceed {max_days} days"
                )
            
            menus = self.menu_repo.get_by_date_range(
                db, hostel_id, start_date, end_date
            )
            
            if published_only:
                menus = [m for m in menus if getattr(m, 'is_published', False)]
            
            return [MessMenu.model_validate(m) for m in menus]
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving menus for date range: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Publishing & Unpublishing
    # -------------------------------------------------------------------------

    def publish_menu(
        self,
        db: Session,
        menu_id: UUID,
        published_by: Optional[UUID] = None,
    ) -> MessMenu:
        """
        Publish a menu to make it visible to students.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            published_by: Optional user ID who published the menu
            
        Returns:
            Published MessMenu schema
            
        Raises:
            NotFoundException: If menu not found
            ValidationException: If menu cannot be published
        """
        try:
            menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Menu with ID {menu_id} not found"
                )
            
            # Validate menu is ready for publishing
            self._validate_menu_for_publishing(menu)
            
            updated = self.menu_repo.publish(db, menu)
            
            # Log publication event
            self._log_publication_event(db, menu_id, published_by)
            
            db.flush()
            
            return MessMenu.model_validate(updated)
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error publishing menu: {str(e)}"
            )

    def unpublish_menu(
        self,
        db: Session,
        menu_id: UUID,
        unpublished_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> MessMenu:
        """
        Unpublish a menu to hide it from students.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            unpublished_by: Optional user ID who unpublished the menu
            reason: Optional reason for unpublishing
            
        Returns:
            Unpublished MessMenu schema
            
        Raises:
            NotFoundException: If menu not found
        """
        try:
            menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Menu with ID {menu_id} not found"
                )
            
            updated = self.menu_repo.unpublish(db, menu)
            
            # Log unpublication event
            self._log_unpublication_event(db, menu_id, unpublished_by, reason)
            
            db.flush()
            
            return MessMenu.model_validate(updated)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error unpublishing menu: {str(e)}"
            )

    def bulk_publish_menus(
        self,
        db: Session,
        menu_ids: List[UUID],
        published_by: Optional[UUID] = None,
    ) -> List[MessMenu]:
        """
        Publish multiple menus at once.
        
        Args:
            db: Database session
            menu_ids: List of menu IDs to publish
            published_by: Optional user ID who published the menus
            
        Returns:
            List of published MessMenu schemas
        """
        published_menus = []
        
        try:
            for menu_id in menu_ids:
                try:
                    menu = self.publish_menu(db, menu_id, published_by)
                    published_menus.append(menu)
                except (NotFoundException, ValidationException) as e:
                    # Log the error but continue with other menus
                    self._log_bulk_publish_error(menu_id, str(e))
            
            return published_menus
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk publishing menus: {str(e)}"
            )

    def bulk_unpublish_menus(
        self,
        db: Session,
        menu_ids: List[UUID],
        unpublished_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> List[MessMenu]:
        """
        Unpublish multiple menus at once.
        
        Args:
            db: Database session
            menu_ids: List of menu IDs to unpublish
            unpublished_by: Optional user ID who unpublished the menus
            reason: Optional reason for unpublishing
            
        Returns:
            List of unpublished MessMenu schemas
        """
        unpublished_menus = []
        
        try:
            for menu_id in menu_ids:
                try:
                    menu = self.unpublish_menu(db, menu_id, unpublished_by, reason)
                    unpublished_menus.append(menu)
                except NotFoundException as e:
                    # Log the error but continue with other menus
                    self._log_bulk_unpublish_error(menu_id, str(e))
            
            return unpublished_menus
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk unpublishing menus: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Menu Copying & Duplication
    # -------------------------------------------------------------------------

    def duplicate_menu(
        self,
        db: Session,
        menu_id: UUID,
        target_date: date,
        created_by: Optional[UUID] = None,
    ) -> MessMenu:
        """
        Duplicate an existing menu to a new date.
        
        Args:
            db: Database session
            menu_id: ID of the menu to duplicate
            target_date: Date for the new menu
            created_by: Optional user ID who created the duplicate
            
        Returns:
            Newly created MessMenu schema
            
        Raises:
            NotFoundException: If source menu not found
            DuplicateEntryException: If menu already exists for target date
        """
        try:
            source_menu = self.menu_repo.get_by_id(db, menu_id)
            
            if not source_menu:
                raise NotFoundException(
                    f"Source menu with ID {menu_id} not found"
                )
            
            # Check if menu already exists for target date
            hostel_id = getattr(source_menu, 'hostel_id', None)
            existing = self.menu_repo.get_by_hostel_and_date(db, hostel_id, target_date)
            
            if existing:
                raise DuplicateEntryException(
                    f"Menu already exists for {target_date}"
                )
            
            # Create duplicate
            duplicate_data = self.menu_repo.duplicate_menu(
                db, source_menu, target_date
            )
            duplicate_data["is_published"] = False  # Start unpublished
            
            obj = self.menu_repo.create(db, duplicate_data)
            db.flush()
            
            return MessMenu.model_validate(obj)
            
        except (NotFoundException, DuplicateEntryException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error duplicating menu: {str(e)}"
            )

    def copy_menu_to_week(
        self,
        db: Session,
        menu_id: UUID,
        week_start: date,
        days: Optional[List[int]] = None,
    ) -> List[MessMenu]:
        """
        Copy a menu to multiple days in a week.
        
        Args:
            db: Database session
            menu_id: ID of the menu to copy
            week_start: Start date of the week (Monday)
            days: Optional list of weekday numbers (0=Monday, 6=Sunday)
                  If None, copies to all 7 days
            
        Returns:
            List of created MessMenu schemas
        """
        try:
            if week_start.weekday() != 0:
                raise ValidationException("Week must start on a Monday")
            
            if days is None:
                days = list(range(7))  # All days of the week
            
            created_menus = []
            
            for day in days:
                if not (0 <= day <= 6):
                    raise ValidationException(f"Invalid day number: {day}")
                
                target_date = week_start + timedelta(days=day)
                
                try:
                    menu = self.duplicate_menu(db, menu_id, target_date)
                    created_menus.append(menu)
                except DuplicateEntryException:
                    # Skip if menu already exists for this date
                    continue
            
            return created_menus
            
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error copying menu to week: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Analytics & Statistics
    # -------------------------------------------------------------------------

    def get_menu_statistics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get menu statistics for a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the period
            end_date: End date of the period
            
        Returns:
            Dictionary with menu statistics
        """
        try:
            stats = self.menu_repo.get_statistics(
                db, hostel_id, start_date, end_date
            )
            
            total_days = (end_date - start_date).days + 1
            menus_created = stats.get('total_menus', 0)
            menus_published = stats.get('published_menus', 0)
            
            return {
                "hostel_id": str(hostel_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_days": total_days,
                "menus_created": menus_created,
                "menus_published": menus_published,
                "coverage_percentage": (menus_created / total_days * 100) if total_days > 0 else 0,
                "publication_rate": (menus_published / menus_created * 100) if menus_created > 0 else 0,
                "avg_items_per_menu": stats.get('avg_items', 0),
                "most_popular_items": stats.get('popular_items', []),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error generating menu statistics: {str(e)}"
            )

    def get_publication_history(
        self,
        db: Session,
        menu_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get publication history for a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            List of publication events
        """
        try:
            history = self.menu_repo.get_publication_history(db, menu_id)
            
            return [
                {
                    "action": h.get("action"),
                    "performed_by": str(h.get("performed_by")) if h.get("performed_by") else None,
                    "timestamp": h.get("timestamp"),
                    "reason": h.get("reason"),
                }
                for h in history
            ]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving publication history: {str(e)}"
            )

    def get_unpublished_menus(
        self,
        db: Session,
        hostel_id: UUID,
        upcoming_only: bool = True,
    ) -> List[MessMenu]:
        """
        Get all unpublished menus for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            upcoming_only: If True, return only future unpublished menus
            
        Returns:
            List of unpublished MessMenu schemas
        """
        try:
            if upcoming_only:
                menus = self.menu_repo.get_unpublished_upcoming(db, hostel_id)
            else:
                menus = self.menu_repo.get_unpublished(db, hostel_id)
            
            return [MessMenu.model_validate(m) for m in menus]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving unpublished menus: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_menu_create(self, data: MessMenuCreate) -> None:
        """
        Validate menu creation data.
        
        Args:
            data: MessMenuCreate schema to validate
            
        Raises:
            ValidationException: If data is invalid
        """
        if not data.menu_date:
            raise ValidationException("Menu date is required")
        
        if not data.hostel_id:
            raise ValidationException("Hostel ID is required")
        
        # Validate that menu items exist
        if hasattr(data, 'breakfast_items') or hasattr(data, 'lunch_items') or hasattr(data, 'dinner_items'):
            if not any([
                getattr(data, 'breakfast_items', None),
                getattr(data, 'lunch_items', None),
                getattr(data, 'dinner_items', None)
            ]):
                raise ValidationException(
                    "Menu must have at least one meal with items"
                )

    def _validate_menu_update(self, menu: Any, data: MessMenuUpdate) -> None:
        """
        Validate menu update data and permissions.
        
        Args:
            menu: Existing menu object
            data: MessMenuUpdate schema with updates
            
        Raises:
            BusinessLogicException: If menu cannot be updated
        """
        # Check if menu is locked for editing
        if getattr(menu, 'is_locked', False):
            raise BusinessLogicException(
                "Menu is locked and cannot be updated"
            )
        
        # Check if menu date is in the past
        menu_date = getattr(menu, 'menu_date', None)
        if menu_date and menu_date < date.today():
            if getattr(menu, 'is_published', False):
                raise BusinessLogicException(
                    "Cannot update published menus from past dates"
                )

    def _validate_menu_for_publishing(self, menu: Any) -> None:
        """
        Validate that a menu is ready for publishing.
        
        Args:
            menu: Menu object to validate
            
        Raises:
            ValidationException: If menu cannot be published
        """
        # Check if menu already published
        if getattr(menu, 'is_published', False):
            raise ValidationException("Menu is already published")
        
        # Check if menu has items
        has_items = any([
            getattr(menu, 'breakfast_items', None),
            getattr(menu, 'lunch_items', None),
            getattr(menu, 'dinner_items', None),
        ])
        
        if not has_items:
            raise ValidationException(
                "Cannot publish menu without any meal items"
            )
        
        # Check if menu date is not too far in the past
        menu_date = getattr(menu, 'menu_date', None)
        if menu_date and menu_date < (date.today() - timedelta(days=1)):
            raise ValidationException(
                "Cannot publish menus from past dates"
            )

    def _log_publication_event(
        self,
        db: Session,
        menu_id: UUID,
        published_by: Optional[UUID],
    ) -> None:
        """Log menu publication event."""
        try:
            self.menu_repo.log_publication(db, menu_id, published_by)
        except:
            # Don't fail the main operation if logging fails
            pass

    def _log_unpublication_event(
        self,
        db: Session,
        menu_id: UUID,
        unpublished_by: Optional[UUID],
        reason: Optional[str],
    ) -> None:
        """Log menu unpublication event."""
        try:
            self.menu_repo.log_unpublication(db, menu_id, unpublished_by, reason)
        except:
            pass

    def _log_bulk_publish_error(self, menu_id: UUID, error: str) -> None:
        """Log error during bulk publish operation."""
        # Implement logging as needed
        pass

    def _log_bulk_unpublish_error(self, menu_id: UUID, error: str) -> None:
        """Log error during bulk unpublish operation."""
        # Implement logging as needed
        pass