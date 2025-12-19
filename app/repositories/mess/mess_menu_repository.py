# --- File: C:\Hostel-Main\app\repositories\mess\mess_menu_repository.py ---

"""
Mess Menu Repository Module.

Manages daily mess menus with publication, versioning, availability
tracking, and comprehensive menu operations.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.mess_menu import (
    MenuAvailability,
    MenuCycle,
    MenuPublishing,
    MenuVersion,
    MessMenu,
)
from app.repositories.base.base_repository import BaseRepository


class MessMenuRepository(BaseRepository[MessMenu]):
    """
    Repository for managing mess menus.
    
    Handles daily menu CRUD, publication, approval integration,
    and statistical tracking with version control.
    """

    def __init__(self, db_session):
        """Initialize repository with MessMenu model."""
        super().__init__(MessMenu, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        published_only: bool = False,
        include_deleted: bool = False
    ) -> List[MessMenu]:
        """
        Get menus for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            published_only: Only published menus
            include_deleted: Include soft-deleted menus
            
        Returns:
            List of mess menus
        """
        conditions = [MessMenu.hostel_id == hostel_id]
        
        if start_date:
            conditions.append(MessMenu.menu_date >= start_date)
        if end_date:
            conditions.append(MessMenu.menu_date <= end_date)
            
        if published_only:
            conditions.append(MessMenu.is_published == True)
            
        if not include_deleted:
            conditions.append(MessMenu.deleted_at.is_(None))
            
        query = (
            select(MessMenu)
            .where(and_(*conditions))
            .order_by(desc(MessMenu.menu_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_date(
        self,
        hostel_id: UUID,
        menu_date: date
    ) -> Optional[MessMenu]:
        """
        Get menu for specific date.
        
        Args:
            hostel_id: Hostel identifier
            menu_date: Menu date
            
        Returns:
            MessMenu if found
        """
        query = (
            select(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(MessMenu.menu_date == menu_date)
            .where(MessMenu.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_current_week_menus(
        self,
        hostel_id: UUID
    ) -> List[MessMenu]:
        """
        Get menus for current week.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of menus for current week
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        return await self.find_by_hostel(
            hostel_id=hostel_id,
            start_date=week_start,
            end_date=week_end
        )

    async def get_upcoming_menus(
        self,
        hostel_id: UUID,
        days_ahead: int = 7,
        published_only: bool = True
    ) -> List[MessMenu]:
        """
        Get upcoming published menus.
        
        Args:
            hostel_id: Hostel identifier
            days_ahead: Number of days to look ahead
            published_only: Only published menus
            
        Returns:
            List of upcoming menus
        """
        today = date.today()
        future_date = today + timedelta(days=days_ahead)
        
        return await self.find_by_hostel(
            hostel_id=hostel_id,
            start_date=today,
            end_date=future_date,
            published_only=published_only
        )

    async def get_with_relationships(
        self,
        menu_id: UUID
    ) -> Optional[MessMenu]:
        """
        Get menu with all relationships loaded.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            MessMenu with relationships
        """
        query = (
            select(MessMenu)
            .where(MessMenu.id == menu_id)
            .options(
                joinedload(MessMenu.hostel),
                joinedload(MessMenu.creator),
                selectinload(MessMenu.feedbacks),
                selectinload(MessMenu.approvals),
                selectinload(MessMenu.versions),
                joinedload(MessMenu.availability)
            )
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def create_menu(
        self,
        menu_data: Dict,
        creator_id: UUID
    ) -> MessMenu:
        """
        Create new menu with initial version.
        
        Args:
            menu_data: Menu data
            creator_id: User creating menu
            
        Returns:
            Created MessMenu
        """
        # Calculate day of week
        menu_date = menu_data.get('menu_date')
        if menu_date:
            day_of_week = menu_date.strftime('%A')
            menu_data['day_of_week'] = day_of_week
            
        menu_data['created_by'] = creator_id
        menu_data['version'] = 1
        
        menu = MessMenu(**menu_data)
        
        # Update statistics
        menu.update_statistics()
        
        self.db_session.add(menu)
        await self.db_session.commit()
        await self.db_session.refresh(menu)
        
        return menu

    async def update_menu(
        self,
        menu_id: UUID,
        update_data: Dict,
        updater_id: UUID
    ) -> Optional[MessMenu]:
        """
        Update menu and create new version.
        
        Args:
            menu_id: Menu identifier
            update_data: Update data
            updater_id: User updating
            
        Returns:
            Updated MessMenu
        """
        menu = await self.get_by_id(menu_id)
        if not menu:
            return None
            
        # Create version snapshot before update
        await MenuVersionRepository(self.db_session).create_version(
            menu_id=menu_id,
            changed_by=updater_id,
            version_type='update',
            menu=menu
        )
        
        # Update menu
        for key, value in update_data.items():
            if hasattr(menu, key):
                setattr(menu, key, value)
                
        menu.version += 1
        menu.updated_by = updater_id
        menu.update_statistics()
        
        await self.db_session.commit()
        await self.db_session.refresh(menu)
        
        return menu

    async def publish_menu(
        self,
        menu_id: UUID,
        publisher_id: UUID,
        send_notification: bool = True
    ) -> Optional[MessMenu]:
        """
        Publish menu to students.
        
        Args:
            menu_id: Menu identifier
            publisher_id: User publishing
            send_notification: Whether to send notification
            
        Returns:
            Published MessMenu
        """
        menu = await self.get_by_id(menu_id)
        if not menu:
            return None
            
        menu.is_published = True
        menu.published_by = publisher_id
        menu.published_at = datetime.utcnow()
        menu.send_notification = send_notification
        
        # Create version for publication
        await MenuVersionRepository(self.db_session).create_version(
            menu_id=menu_id,
            changed_by=publisher_id,
            version_type='publish',
            menu=menu
        )
        
        await self.db_session.commit()
        await self.db_session.refresh(menu)
        
        return menu

    async def unpublish_menu(
        self,
        menu_id: UUID,
        unpublisher_id: UUID
    ) -> Optional[MessMenu]:
        """
        Unpublish menu.
        
        Args:
            menu_id: Menu identifier
            unpublisher_id: User unpublishing
            
        Returns:
            Unpublished MessMenu
        """
        menu = await self.get_by_id(menu_id)
        if not menu:
            return None
            
        menu.is_published = False
        menu.updated_by = unpublisher_id
        
        await self.db_session.commit()
        await self.db_session.refresh(menu)
        
        return menu

    async def find_special_menus(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[MessMenu]:
        """
        Get special occasion menus.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            List of special menus
        """
        conditions = [
            MessMenu.hostel_id == hostel_id,
            MessMenu.is_special_menu == True,
            MessMenu.deleted_at.is_(None)
        ]
        
        if start_date:
            conditions.append(MessMenu.menu_date >= start_date)
        if end_date:
            conditions.append(MessMenu.menu_date <= end_date)
            
        query = (
            select(MessMenu)
            .where(and_(*conditions))
            .order_by(MessMenu.menu_date)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_pending_approval(
        self,
        hostel_id: UUID
    ) -> List[MessMenu]:
        """
        Get menus pending approval.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of menus pending approval
        """
        query = (
            select(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(MessMenu.is_approved == False)
            .where(MessMenu.deleted_at.is_(None))
            .order_by(MessMenu.menu_date)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_menu_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, any]:
        """
        Get menu statistics for period.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Dictionary of statistics
        """
        query = (
            select(
                func.count(MessMenu.id).label('total_menus'),
                func.count(MessMenu.id).filter(MessMenu.is_published == True).label('published_count'),
                func.count(MessMenu.id).filter(MessMenu.is_approved == True).label('approved_count'),
                func.count(MessMenu.id).filter(MessMenu.is_special_menu == True).label('special_count'),
                func.avg(MessMenu.average_rating).label('avg_rating'),
                func.avg(MessMenu.total_feedback_count).label('avg_feedback')
            )
            .where(MessMenu.hostel_id == hostel_id)
            .where(MessMenu.menu_date.between(start_date, end_date))
            .where(MessMenu.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        row = result.first()
        
        if not row:
            return {
                'total_menus': 0,
                'published_count': 0,
                'approved_count': 0,
                'special_count': 0,
                'average_rating': 0.0,
                'average_feedback_count': 0.0
            }
            
        return {
            'total_menus': row.total_menus or 0,
            'published_count': row.published_count or 0,
            'approved_count': row.approved_count or 0,
            'special_count': row.special_count or 0,
            'average_rating': float(row.avg_rating or 0),
            'average_feedback_count': float(row.avg_feedback or 0)
        }

    async def get_top_rated_menus(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_feedback: int = 5,
        limit: int = 10
    ) -> List[MessMenu]:
        """
        Get highest rated menus.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            min_feedback: Minimum feedback count
            limit: Maximum number of results
            
        Returns:
            List of top-rated menus
        """
        conditions = [
            MessMenu.hostel_id == hostel_id,
            MessMenu.total_feedback_count >= min_feedback,
            MessMenu.average_rating.isnot(None),
            MessMenu.deleted_at.is_(None)
        ]
        
        if start_date:
            conditions.append(MessMenu.menu_date >= start_date)
        if end_date:
            conditions.append(MessMenu.menu_date <= end_date)
            
        query = (
            select(MessMenu)
            .where(and_(*conditions))
            .order_by(desc(MessMenu.average_rating))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def update_menu_rating(
        self,
        menu_id: UUID,
        new_rating: Decimal
    ) -> Optional[MessMenu]:
        """
        Update menu rating statistics.
        
        Args:
            menu_id: Menu identifier
            new_rating: New rating to incorporate
            
        Returns:
            Updated MessMenu
        """
        menu = await self.get_by_id(menu_id)
        if not menu:
            return None
            
        current_count = menu.total_feedback_count
        current_avg = menu.average_rating or Decimal('0.0')
        
        # Calculate new average
        new_count = current_count + 1
        new_avg = ((current_avg * current_count) + new_rating) / new_count
        
        menu.average_rating = new_avg
        menu.total_feedback_count = new_count
        
        await self.db_session.commit()
        await self.db_session.refresh(menu)
        
        return menu

    async def bulk_publish_menus(
        self,
        menu_ids: List[UUID],
        publisher_id: UUID
    ) -> Tuple[int, int]:
        """
        Bulk publish multiple menus.
        
        Args:
            menu_ids: List of menu identifiers
            publisher_id: User publishing
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        from sqlalchemy import update
        
        # Update all menus in one query
        stmt = (
            update(MessMenu)
            .where(MessMenu.id.in_(menu_ids))
            .where(MessMenu.deleted_at.is_(None))
            .values(
                is_published=True,
                published_by=publisher_id,
                published_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        
        success_count = result.rowcount
        failure_count = len(menu_ids) - success_count
        
        return success_count, failure_count

    async def find_incomplete_menus(
        self,
        hostel_id: UUID
    ) -> List[MessMenu]:
        """
        Find menus missing required meals.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of incomplete menus
        """
        # Menus are incomplete if they don't have breakfast AND (lunch OR dinner)
        query = (
            select(MessMenu)
            .where(MessMenu.hostel_id == hostel_id)
            .where(MessMenu.deleted_at.is_(None))
            .where(
                or_(
                    func.array_length(MessMenu.breakfast_items, 1).is_(None),
                    and_(
                        func.array_length(MessMenu.lunch_items, 1).is_(None),
                        func.array_length(MessMenu.dinner_items, 1).is_(None)
                    )
                )
            )
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class MenuCycleRepository(BaseRepository[MenuCycle]):
    """
    Repository for menu cycles.
    
    Manages recurring menu patterns with automated menu
    creation and cycle performance tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuCycle model."""
        super().__init__(MenuCycle, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        active_only: bool = True
    ) -> List[MenuCycle]:
        """
        Get menu cycles for hostel.
        
        Args:
            hostel_id: Hostel identifier
            active_only: Only active cycles
            
        Returns:
            List of menu cycles
        """
        conditions = [MenuCycle.hostel_id == hostel_id]
        
        if active_only:
            conditions.append(MenuCycle.is_active == True)
            
        query = select(MenuCycle).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_active_cycle(
        self,
        hostel_id: UUID,
        current_date: date
    ) -> Optional[MenuCycle]:
        """
        Get active cycle for current date.
        
        Args:
            hostel_id: Hostel identifier
            current_date: Date to check
            
        Returns:
            Active MenuCycle if found
        """
        query = (
            select(MenuCycle)
            .where(MenuCycle.hostel_id == hostel_id)
            .where(MenuCycle.is_active == True)
            .where(MenuCycle.start_date <= current_date)
            .where(
                or_(
                    MenuCycle.end_date.is_(None),
                    MenuCycle.end_date >= current_date
                )
            )
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_type(
        self,
        hostel_id: UUID,
        cycle_type: str
    ) -> List[MenuCycle]:
        """
        Find cycles by type.
        
        Args:
            hostel_id: Hostel identifier
            cycle_type: Type of cycle
            
        Returns:
            List of matching cycles
        """
        query = (
            select(MenuCycle)
            .where(MenuCycle.hostel_id == hostel_id)
            .where(MenuCycle.cycle_type == cycle_type)
            .where(MenuCycle.is_active == True)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def record_cycle_usage(
        self,
        cycle_id: UUID
    ) -> Optional[MenuCycle]:
        """
        Record cycle usage.
        
        Args:
            cycle_id: Cycle identifier
            
        Returns:
            Updated MenuCycle
        """
        cycle = await self.get_by_id(cycle_id)
        if not cycle:
            return None
            
        cycle.times_used += 1
        
        await self.db_session.commit()
        await self.db_session.refresh(cycle)
        
        return cycle


class MenuVersionRepository(BaseRepository[MenuVersion]):
    """
    Repository for menu versions.
    
    Manages menu version history with change tracking
    and audit trail.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuVersion model."""
        super().__init__(MenuVersion, db_session)

    async def find_by_menu(
        self,
        menu_id: UUID
    ) -> List[MenuVersion]:
        """
        Get all versions for a menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            List of versions in chronological order
        """
        query = (
            select(MenuVersion)
            .where(MenuVersion.menu_id == menu_id)
            .order_by(MenuVersion.version_number)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        menu_id: UUID
    ) -> Optional[MenuVersion]:
        """
        Get latest version of menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            Latest MenuVersion
        """
        query = (
            select(MenuVersion)
            .where(MenuVersion.menu_id == menu_id)
            .order_by(desc(MenuVersion.version_number))
            .limit(1)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_version(
        self,
        menu_id: UUID,
        changed_by: UUID,
        version_type: str,
        menu: MessMenu,
        change_reason: Optional[str] = None
    ) -> MenuVersion:
        """
        Create new version snapshot.
        
        Args:
            menu_id: Menu identifier
            changed_by: User making change
            version_type: Type of version
            menu: Current menu state
            change_reason: Reason for change (optional)
            
        Returns:
            Created MenuVersion
        """
        # Get current max version
        latest = await self.get_latest_version(menu_id)
        version_number = (latest.version_number + 1) if latest else 1
        
        # Create snapshot
        snapshot = {
            'breakfast_items': menu.breakfast_items,
            'lunch_items': menu.lunch_items,
            'snacks_items': menu.snacks_items,
            'dinner_items': menu.dinner_items,
            'is_special_menu': menu.is_special_menu,
            'special_occasion': menu.special_occasion,
            'vegetarian_available': menu.vegetarian_available,
            'non_vegetarian_available': menu.non_vegetarian_available,
            'vegan_available': menu.vegan_available,
            'jain_available': menu.jain_available,
        }
        
        version = MenuVersion(
            menu_id=menu_id,
            version_number=version_number,
            version_type=version_type,
            changed_by=changed_by,
            change_reason=change_reason,
            menu_snapshot=snapshot
        )
        
        self.db_session.add(version)
        await self.db_session.commit()
        await self.db_session.refresh(version)
        
        return version

    async def compare_versions(
        self,
        version1_id: UUID,
        version2_id: UUID
    ) -> Dict[str, any]:
        """
        Compare two versions.
        
        Args:
            version1_id: First version identifier
            version2_id: Second version identifier
            
        Returns:
            Dictionary of changes
        """
        version1 = await self.get_by_id(version1_id)
        version2 = await self.get_by_id(version2_id)
        
        if not version1 or not version2:
            return {}
            
        snapshot1 = version1.menu_snapshot
        snapshot2 = version2.menu_snapshot
        
        changes = {}
        
        for key in snapshot1.keys():
            if snapshot1.get(key) != snapshot2.get(key):
                changes[key] = {
                    'old': snapshot1.get(key),
                    'new': snapshot2.get(key)
                }
                
        return changes


class MenuPublishingRepository(BaseRepository[MenuPublishing]):
    """
    Repository for menu publishing workflow.
    
    Manages publication process with multi-channel distribution
    and engagement tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuPublishing model."""
        super().__init__(MenuPublishing, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[MenuPublishing]:
        """
        Get publishing record for menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            MenuPublishing if found
        """
        query = select(MenuPublishing).where(
            MenuPublishing.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_publishing_record(
        self,
        menu_id: UUID,
        publishing_data: Dict
    ) -> MenuPublishing:
        """
        Create publishing record.
        
        Args:
            menu_id: Menu identifier
            publishing_data: Publishing configuration
            
        Returns:
            Created MenuPublishing
        """
        publishing = MenuPublishing(
            menu_id=menu_id,
            **publishing_data
        )
        
        self.db_session.add(publishing)
        await self.db_session.commit()
        await self.db_session.refresh(publishing)
        
        return publishing

    async def mark_as_published(
        self,
        publishing_id: UUID,
        publisher_id: UUID,
        total_recipients: int
    ) -> Optional[MenuPublishing]:
        """
        Mark publishing as completed.
        
        Args:
            publishing_id: Publishing record identifier
            publisher_id: User who published
            total_recipients: Total number of recipients
            
        Returns:
            Updated MenuPublishing
        """
        publishing = await self.get_by_id(publishing_id)
        if not publishing:
            return None
            
        publishing.is_published = True
        publishing.published_by = publisher_id
        publishing.published_at = datetime.utcnow()
        publishing.total_recipients = total_recipients
        
        await self.db_session.commit()
        await self.db_session.refresh(publishing)
        
        return publishing

    async def update_delivery_status(
        self,
        publishing_id: UUID,
        successful: int,
        failed: int
    ) -> Optional[MenuPublishing]:
        """
        Update delivery statistics.
        
        Args:
            publishing_id: Publishing record identifier
            successful: Number of successful deliveries
            failed: Number of failed deliveries
            
        Returns:
            Updated MenuPublishing
        """
        publishing = await self.get_by_id(publishing_id)
        if not publishing:
            return None
            
        publishing.successful_deliveries = successful
        publishing.failed_deliveries = failed
        
        await self.db_session.commit()
        await self.db_session.refresh(publishing)
        
        return publishing

    async def record_view(
        self,
        publishing_id: UUID,
        viewer_id: UUID
    ) -> Optional[MenuPublishing]:
        """
        Record menu view.
        
        Args:
            publishing_id: Publishing record identifier
            viewer_id: User who viewed
            
        Returns:
            Updated MenuPublishing
        """
        publishing = await self.get_by_id(publishing_id)
        if not publishing:
            return None
            
        publishing.total_views += 1
        
        # Track unique viewers (simplified)
        # In production, would use a separate table or cache
        publishing.unique_viewers += 1
        
        await self.db_session.commit()
        await self.db_session.refresh(publishing)
        
        return publishing

    async def get_scheduled_publications(
        self,
        before_datetime: Optional[datetime] = None
    ) -> List[MenuPublishing]:
        """
        Get scheduled publications.
        
        Args:
            before_datetime: Get publications scheduled before this time
            
        Returns:
            List of scheduled publications
        """
        conditions = [
            MenuPublishing.publish_type == 'scheduled',
            MenuPublishing.is_published == False,
            MenuPublishing.scheduled_publish_time.isnot(None)
        ]
        
        if before_datetime:
            conditions.append(MenuPublishing.scheduled_publish_time <= before_datetime)
        else:
            conditions.append(MenuPublishing.scheduled_publish_time <= datetime.utcnow())
            
        query = (
            select(MenuPublishing)
            .where(and_(*conditions))
            .order_by(MenuPublishing.scheduled_publish_time)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class MenuAvailabilityRepository(BaseRepository[MenuAvailability]):
    """
    Repository for real-time menu availability.
    
    Tracks dynamic availability of menu items throughout
    service hours.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuAvailability model."""
        super().__init__(MenuAvailability, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Get availability record for menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            MenuAvailability if found
        """
        query = select(MenuAvailability).where(
            MenuAvailability.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_availability_record(
        self,
        menu_id: UUID
    ) -> MenuAvailability:
        """
        Create availability tracking record.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            Created MenuAvailability
        """
        availability = MenuAvailability(
            menu_id=menu_id,
            is_fully_available=True
        )
        
        self.db_session.add(availability)
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability

    async def mark_item_unavailable(
        self,
        menu_id: UUID,
        meal_type: str,
        item_name: str,
        updater_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Mark specific item as unavailable.
        
        Args:
            menu_id: Menu identifier
            meal_type: Type of meal (breakfast/lunch/snacks/dinner)
            item_name: Name of unavailable item
            updater_id: User updating
            
        Returns:
            Updated MenuAvailability
        """
        availability = await self.get_by_menu(menu_id)
        
        if not availability:
            availability = await self.create_availability_record(menu_id)
            
        # Add item to unavailable list
        meal_field_map = {
            'breakfast': 'breakfast_unavailable_items',
            'lunch': 'lunch_unavailable_items',
            'snacks': 'snacks_unavailable_items',
            'dinner': 'dinner_unavailable_items'
        }
        
        field_name = meal_field_map.get(meal_type.lower())
        if not field_name:
            return None
            
        unavailable_items = getattr(availability, field_name, [])
        if item_name not in unavailable_items:
            unavailable_items.append(item_name)
            setattr(availability, field_name, unavailable_items)
            
        availability.last_updated_by = updater_id
        availability.update_overall_availability()
        
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability

    async def mark_meal_unavailable(
        self,
        menu_id: UUID,
        meal_type: str,
        updater_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Mark entire meal as unavailable.
        
        Args:
            menu_id: Menu identifier
            meal_type: Type of meal
            updater_id: User updating
            
        Returns:
            Updated MenuAvailability
        """
        availability = await self.get_by_menu(menu_id)
        
        if not availability:
            availability = await self.create_availability_record(menu_id)
            
        meal_field_map = {
            'breakfast': 'breakfast_available',
            'lunch': 'lunch_available',
            'snacks': 'snacks_available',
            'dinner': 'dinner_available'
        }
        
        field_name = meal_field_map.get(meal_type.lower())
        if not field_name:
            return None
            
        setattr(availability, field_name, False)
        availability.last_updated_by = updater_id
        availability.update_overall_availability()
        
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability

    async def restore_item_availability(
        self,
        menu_id: UUID,
        meal_type: str,
        item_name: str,
        updater_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Restore item availability.
        
        Args:
            menu_id: Menu identifier
            meal_type: Type of meal
            item_name: Name of item to restore
            updater_id: User updating
            
        Returns:
            Updated MenuAvailability
        """
        availability = await self.get_by_menu(menu_id)
        if not availability:
            return None
            
        meal_field_map = {
            'breakfast': 'breakfast_unavailable_items',
            'lunch': 'lunch_unavailable_items',
            'snacks': 'snacks_unavailable_items',
            'dinner': 'dinner_unavailable_items'
        }
        
        field_name = meal_field_map.get(meal_type.lower())
        if not field_name:
            return None
            
        unavailable_items = getattr(availability, field_name, [])
        if item_name in unavailable_items:
            unavailable_items.remove(item_name)
            setattr(availability, field_name, unavailable_items)
            
        availability.last_updated_by = updater_id
        availability.update_overall_availability()
        
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability

    async def start_meal_service(
        self,
        menu_id: UUID,
        meal_type: str,
        updater_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Mark meal service as started.
        
        Args:
            menu_id: Menu identifier
            meal_type: Type of meal
            updater_id: User updating
            
        Returns:
            Updated MenuAvailability
        """
        availability = await self.get_by_menu(menu_id)
        
        if not availability:
            availability = await self.create_availability_record(menu_id)
            
        service_field_map = {
            'breakfast': 'breakfast_service_start',
            'lunch': 'lunch_service_start',
            'snacks': 'snacks_service_start',
            'dinner': 'dinner_service_start'
        }
        
        field_name = service_field_map.get(meal_type.lower())
        if not field_name:
            return None
            
        setattr(availability, field_name, datetime.utcnow())
        availability.last_updated_by = updater_id
        
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability

    async def end_meal_service(
        self,
        menu_id: UUID,
        meal_type: str,
        updater_id: UUID
    ) -> Optional[MenuAvailability]:
        """
        Mark meal service as ended.
        
        Args:
            menu_id: Menu identifier
            meal_type: Type of meal
            updater_id: User updating
            
        Returns:
            Updated MenuAvailability
        """
        availability = await self.get_by_menu(menu_id)
        if not availability:
            return None
            
        service_field_map = {
            'breakfast': 'breakfast_service_end',
            'lunch': 'lunch_service_end',
            'snacks': 'snacks_service_end',
            'dinner': 'dinner_service_end'
        }
        
        field_name = service_field_map.get(meal_type.lower())
        if not field_name:
            return None
            
        setattr(availability, field_name, datetime.utcnow())
        availability.last_updated_by = updater_id
        
        await self.db_session.commit()
        await self.db_session.refresh(availability)
        
        return availability