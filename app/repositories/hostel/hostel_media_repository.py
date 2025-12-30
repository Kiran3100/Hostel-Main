"""
Hostel media repository for comprehensive media content management.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import selectinload

from app.models.hostel.hostel_media import HostelMedia, MediaCategory
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class ActiveMediaSpecification(Specification[HostelMedia]):
    """Specification for active and approved media."""
    
    def __init__(self, require_approval: bool = True):
        self.require_approval = require_approval
    
    def is_satisfied_by(self, entity: HostelMedia) -> bool:
        base_condition = entity.is_active
        if self.require_approval:
            return base_condition and entity.is_approved
        return base_condition
    
    def to_sql_condition(self):
        base_condition = HostelMedia.is_active == True
        if self.require_approval:
            return and_(base_condition, HostelMedia.is_approved == True)
        return base_condition


class MediaByCategorySpecification(Specification[HostelMedia]):
    """Specification for filtering media by category."""
    
    def __init__(self, category: str, media_type: Optional[str] = None):
        self.category = category
        self.media_type = media_type
    
    def to_sql_condition(self):
        conditions = [HostelMedia.category == self.category]
        if self.media_type:
            conditions.append(HostelMedia.media_type == self.media_type)
        return and_(*conditions)


class HostelMediaRepository(BaseRepository[HostelMedia]):
    """Repository for hostel media content management."""
    
    def __init__(self, session):
        super().__init__(session, HostelMedia)
    
    # ===== Core Media Operations =====
    
    async def upload_media(
        self,
        hostel_id: UUID,
        media_data: Dict[str, Any],
        uploaded_by: Optional[UUID] = None
    ) -> HostelMedia:
        """Upload new media content."""
        media_data.update({
            "hostel_id": hostel_id,
            "uploaded_by": uploaded_by,
            "uploaded_at": datetime.utcnow(),
            "is_active": True,
            "is_approved": False  # Requires approval by default
        })
        
        # Set display order if not provided
        if "display_order" not in media_data:
            max_order = await self.session.query(
                func.max(HostelMedia.display_order)
            ).filter(
                and_(
                    HostelMedia.hostel_id == hostel_id,
                    HostelMedia.category == media_data.get("category", "")
                )
            ).scalar()
            
            media_data["display_order"] = (max_order or 0) + 1
        
        return await self.create(media_data)
    
    async def find_by_hostel(
        self,
        hostel_id: UUID,
        media_type: Optional[str] = None,
        category: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[HostelMedia]:
        """Find media by hostel with filtering options."""
        criteria = {"hostel_id": hostel_id}
        
        if media_type:
            criteria["media_type"] = media_type
        if category:
            criteria["category"] = category
        
        custom_filter = None
        if not include_inactive:
            spec = ActiveMediaSpecification(require_approval=True)
            custom_filter = spec.to_sql_condition()
        
        return await self.find_by_criteria(
            criteria,
            custom_filter=custom_filter,
            order_by=[
                asc(HostelMedia.category),
                asc(HostelMedia.display_order),
                desc(HostelMedia.uploaded_at)
            ]
        )
    
    async def find_gallery_images(
        self,
        hostel_id: UUID,
        limit: Optional[int] = None
    ) -> List[HostelMedia]:
        """Find approved gallery images for a hostel."""
        spec = ActiveMediaSpecification(require_approval=True)
        media_spec = MediaByCategorySpecification("gallery", "image")
        
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=and_(
                spec.to_sql_condition(),
                media_spec.to_sql_condition()
            ),
            order_by=[asc(HostelMedia.display_order)],
            limit=limit
        )
    
    async def find_cover_images(self, hostel_id: UUID) -> List[HostelMedia]:
        """Find cover/primary images for a hostel."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "is_cover": True,
                "media_type": "image"
            },
            custom_filter=ActiveMediaSpecification().to_sql_condition(),
            order_by=[desc(HostelMedia.is_featured), asc(HostelMedia.display_order)]
        )
    
    async def find_featured_media(
        self,
        hostel_id: UUID,
        limit: int = 6
    ) -> List[HostelMedia]:
        """Find featured media for a hostel."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "is_featured": True
            },
            custom_filter=ActiveMediaSpecification().to_sql_condition(),
            order_by=[asc(HostelMedia.display_order)],
            limit=limit
        )
    
    # ===== Media Management =====
    
    async def approve_media(
        self,
        media_id: UUID,
        approved_by: UUID,
        approved_at: Optional[datetime] = None
    ) -> HostelMedia:
        """Approve media content."""
        media = await self.get_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        media.is_approved = True
        media.approved_by = approved_by
        media.approved_at = approved_at or datetime.utcnow()
        
        await self.session.commit()
        return media
    
    async def set_as_cover(self, media_id: UUID) -> HostelMedia:
        """Set media as cover image."""
        media = await self.get_by_id(media_id)
        if not media:
            raise ValueError(f"Media {media_id} not found")
        
        if media.media_type != "image":
            raise ValueError("Only images can be set as cover")
        
        # Remove cover status from other media
        await self.session.query(HostelMedia).filter(
            and_(
                HostelMedia.hostel_id == media.hostel_id,
                HostelMedia.is_cover == True
            )
        ).update({"is_cover": False})
        
        # Set this media as cover
        media.is_cover = True
        await self.session.commit()
        return media
    
    async def reorder_media(
        self,
        hostel_id: UUID,
        category: str,
        media_order: List[UUID]
    ) -> List[HostelMedia]:
        """Reorder media within a category."""
        media_items = await self.find_by_criteria({
            "hostel_id": hostel_id,
            "category": category
        })
        
        media_dict = {media.id: media for media in media_items}
        
        for index, media_id in enumerate(media_order):
            if media_id in media_dict:
                media_dict[media_id].display_order = index + 1
        
        await self.session.commit()
        return list(media_dict.values())
    
    async def bulk_delete_media(self, media_ids: List[UUID]) -> int:
        """Bulk delete media items."""
        deleted_count = await self.session.query(HostelMedia).filter(
            HostelMedia.id.in_(media_ids)
        ).delete(synchronize_session=False)
        
        await self.session.commit()
        return deleted_count
    
    # ===== Media Analytics =====
    
    async def increment_views(self, media_id: UUID) -> None:
        """Increment view count for media."""
        await self.session.query(HostelMedia).filter(
            HostelMedia.id == media_id
        ).update({
            HostelMedia.view_count: HostelMedia.view_count + 1
        })
        await self.session.commit()
    
    async def increment_clicks(self, media_id: UUID) -> None:
        """Increment click count for media."""
        await self.session.query(HostelMedia).filter(
            HostelMedia.id == media_id
        ).update({
            HostelMedia.click_count: HostelMedia.click_count + 1
        })
        await self.session.commit()
    
    async def get_media_performance(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get media performance analytics."""
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)
        
        query = self.session.query(
            HostelMedia.category,
            HostelMedia.media_type,
            func.count(HostelMedia.id).label("total_media"),
            func.sum(HostelMedia.view_count).label("total_views"),
            func.sum(HostelMedia.click_count).label("total_clicks"),
            func.avg(HostelMedia.view_count).label("avg_views"),
            func.max(HostelMedia.view_count).label("max_views")
        ).filter(
            and_(
                HostelMedia.hostel_id == hostel_id,
                HostelMedia.is_active == True,
                HostelMedia.uploaded_at >= cutoff_date
            )
        ).group_by(
            HostelMedia.category,
            HostelMedia.media_type
        )
        
        results = await query.all()
        
        performance = {}
        for row in results:
            key = f"{row.category}_{row.media_type}"
            performance[key] = {
                "category": row.category,
                "media_type": row.media_type,
                "total_media": row.total_media,
                "total_views": row.total_views or 0,
                "total_clicks": row.total_clicks or 0,
                "avg_views": float(row.avg_views or 0),
                "max_views": row.max_views or 0,
                "click_through_rate": (row.total_clicks / max(row.total_views, 1)) * 100 if row.total_views else 0
            }
        
        return performance
    
    async def get_popular_media(
        self,
        hostel_id: UUID,
        limit: int = 10,
        metric: str = "view_count"
    ) -> List[HostelMedia]:
        """Get most popular media by specified metric."""
        order_column = getattr(HostelMedia, metric)
        
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=ActiveMediaSpecification().to_sql_condition(),
            order_by=[desc(order_column)],
            limit=limit
        )
    
    # ===== Search and Filtering =====
    
    async def search_media(
        self,
        hostel_id: UUID,
        search_query: str,
        media_type: Optional[str] = None,
        category: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[HostelMedia]:
        """Search media with text query."""
        criteria = {"hostel_id": hostel_id}
        
        # Build search conditions
        search_conditions = [
            HostelMedia.title.ilike(f"%{search_query}%"),
            HostelMedia.description.ilike(f"%{search_query}%"),
            HostelMedia.alt_text.ilike(f"%{search_query}%")
        ]
        
        custom_filter = and_(
            ActiveMediaSpecification().to_sql_condition(),
            or_(*search_conditions)
        )
        
        if media_type:
            criteria["media_type"] = media_type
        if category:
            criteria["category"] = category
        
        query = self.build_query(
            criteria,
            custom_filter=custom_filter,
            order_by=[desc(HostelMedia.uploaded_at)]
        )
        
        if pagination:
            return await self.paginate(query, pagination)
        else:
            return await query.all()
    
    async def find_media_by_tags(
        self,
        hostel_id: UUID,
        tags: List[str]
    ) -> List[HostelMedia]:
        """Find media by SEO keywords/tags."""
        tag_conditions = [
            HostelMedia.seo_keywords.ilike(f"%{tag}%") for tag in tags
        ]
        
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=and_(
                ActiveMediaSpecification().to_sql_condition(),
                or_(*tag_conditions)
            ),
            order_by=[desc(HostelMedia.view_count)]
        )
    
    # ===== Moderation =====
    
    async def find_pending_approval(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[HostelMedia]:
        """Find media pending approval."""
        criteria = {
            "is_active": True,
            "is_approved": False
        }
        if hostel_id:
            criteria["hostel_id"] = hostel_id
        
        return await self.find_by_criteria(
            criteria,
            order_by=[asc(HostelMedia.uploaded_at)],
            limit=limit
        )
    
    async def bulk_approve_media(
        self,
        media_ids: List[UUID],
        approved_by: UUID
    ) -> List[HostelMedia]:
        """Bulk approve multiple media items."""
        approved_at = datetime.utcnow()
        
        await self.session.query(HostelMedia).filter(
            HostelMedia.id.in_(media_ids)
        ).update({
            "is_approved": True,
            "approved_by": approved_by,
            "approved_at": approved_at
        }, synchronize_session=False)
        
        await self.session.commit()
        
        return await self.find_by_ids(media_ids)
    
    # ===== Storage Management =====
    
    async def get_storage_usage(self, hostel_id: UUID) -> Dict[str, Any]:
        """Get storage usage statistics for a hostel."""
        query = self.session.query(
            func.count(HostelMedia.id).label("total_files"),
            func.sum(HostelMedia.file_size).label("total_size"),
            func.avg(HostelMedia.file_size).label("avg_size"),
            func.max(HostelMedia.file_size).label("max_size")
        ).filter(
            and_(
                HostelMedia.hostel_id == hostel_id,
                HostelMedia.is_active == True,
                HostelMedia.file_size.isnot(None)
            )
        )
        
        result = await query.first()
        
        # Get breakdown by media type
        type_breakdown = await self.session.query(
            HostelMedia.media_type,
            func.count(HostelMedia.id).label("count"),
            func.sum(HostelMedia.file_size).label("size")
        ).filter(
            and_(
                HostelMedia.hostel_id == hostel_id,
                HostelMedia.is_active == True,
                HostelMedia.file_size.isnot(None)
            )
        ).group_by(HostelMedia.media_type).all()
        
        return {
            "total_files": result.total_files or 0,
            "total_size_bytes": result.total_size or 0,
            "total_size_mb": (result.total_size or 0) / (1024 * 1024),
            "avg_size_bytes": result.avg_size or 0,
            "max_size_bytes": result.max_size or 0,
            "breakdown_by_type": {
                row.media_type: {
                    "count": row.count,
                    "size_bytes": row.size or 0,
                    "size_mb": (row.size or 0) / (1024 * 1024)
                }
                for row in type_breakdown
            }
        }


class MediaCategoryRepository(BaseRepository[MediaCategory]):
    """Repository for media category management."""
    
    def __init__(self, session):
        super().__init__(session, MediaCategory)
    
    async def find_active_categories(self) -> List[MediaCategory]:
        """Find all active media categories."""
        return await self.find_by_criteria(
            {"is_active": True},
            order_by=[asc(MediaCategory.display_order), asc(MediaCategory.name)]
        )
    
    async def find_categories_for_media_type(self, media_type: str) -> List[MediaCategory]:
        """Find categories applicable to a specific media type."""
        return await self.find_by_criteria(
            {
                "is_active": True
            },
            custom_filter=MediaCategory.applicable_media_types.contains([media_type]),
            order_by=[asc(MediaCategory.display_order)]
        )
    
    async def validate_category_limits(
        self,
        hostel_id: UUID,
        category_name: str
    ) -> Dict[str, Any]:
        """Validate if more items can be added to a category."""
        category = await self.find_one_by_criteria({"name": category_name})
        if not category:
            raise ValueError(f"Category '{category_name}' not found")
        
        if category.max_items is None:
            return {"can_add": True, "limit": None, "current": 0}
        
        current_count = await self.session.query(func.count(HostelMedia.id)).filter(
            and_(
                HostelMedia.hostel_id == hostel_id,
                HostelMedia.category == category_name,
                HostelMedia.is_active == True
            )
        ).scalar()
        
        return {
            "can_add": current_count < category.max_items,
            "limit": category.max_items,
            "current": current_count,
            "remaining": max(0, category.max_items - current_count)
        }