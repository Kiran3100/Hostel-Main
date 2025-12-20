# --- File: C:\Hostel-Main\app\services\analytics\analytics_engine_service.py ---
"""
Analytics Engine Service - Core computation and orchestration.

Coordinates analytics generation across all modules with:
- Automated metric calculation and aggregation
- Batch processing for periodic updates
- Cross-module data synthesis
- Cache management and optimization
- Scheduled analytics refresh
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.repositories.analytics import (
    BookingAnalyticsRepository,
    ComplaintAnalyticsRepository,
    DashboardAnalyticsRepository,
    FinancialAnalyticsRepository,
    OccupancyAnalyticsRepository,
    PlatformAnalyticsRepository,
    SupervisorAnalyticsRepository,
    VisitorAnalyticsRepository,
    AnalyticsAggregateRepository,
)


logger = logging.getLogger(__name__)


class AnalyticsEngineService:
    """
    Core analytics engine for orchestrating analytics generation.
    
    Manages the lifecycle of analytics data including calculation,
    aggregation, caching, and scheduled updates.
    """
    
    def __init__(self, db: Session):
        """Initialize analytics engine with all repositories."""
        self.db = db
        
        # Initialize all repositories
        self.booking_repo = BookingAnalyticsRepository(db)
        self.complaint_repo = ComplaintAnalyticsRepository(db)
        self.dashboard_repo = DashboardAnalyticsRepository(db)
        self.financial_repo = FinancialAnalyticsRepository(db)
        self.occupancy_repo = OccupancyAnalyticsRepository(db)
        self.platform_repo = PlatformAnalyticsRepository(db)
        self.supervisor_repo = SupervisorAnalyticsRepository(db)
        self.visitor_repo = VisitorAnalyticsRepository(db)
        self.aggregate_repo = AnalyticsAggregateRepository(db)
    
    # ==================== Comprehensive Analytics Generation ====================
    
    def generate_all_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        modules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive analytics across all modules.
        
        Args:
            hostel_id: Hostel ID (None for platform-wide)
            period_start: Period start date
            period_end: Period end date
            modules: Specific modules to generate (None for all)
            
        Returns:
            Dictionary with generation results and status
        """
        logger.info(
            f"Starting analytics generation for hostel {hostel_id}, "
            f"period {period_start} to {period_end}"
        )
        
        # Default to all modules
        if modules is None:
            modules = [
                'booking', 'complaint', 'financial', 'occupancy',
                'supervisor', 'dashboard'
            ]
        
        results = {
            'success': True,
            'modules_generated': [],
            'modules_failed': [],
            'errors': [],
            'metadata': {
                'hostel_id': str(hostel_id) if hostel_id else 'platform',
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'generated_at': datetime.utcnow().isoformat(),
            }
        }
        
        # Use thread pool for parallel generation
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            
            if 'booking' in modules:
                futures['booking'] = executor.submit(
                    self._generate_booking_analytics,
                    hostel_id, period_start, period_end
                )
            
            if 'complaint' in modules:
                futures['complaint'] = executor.submit(
                    self._generate_complaint_analytics,
                    hostel_id, period_start, period_end
                )
            
            if 'financial' in modules:
                futures['financial'] = executor.submit(
                    self._generate_financial_analytics,
                    hostel_id, period_start, period_end
                )
            
            if 'occupancy' in modules:
                futures['occupancy'] = executor.submit(
                    self._generate_occupancy_analytics,
                    hostel_id, period_start, period_end
                )
            
            if 'supervisor' in modules:
                futures['supervisor'] = executor.submit(
                    self._generate_supervisor_analytics,
                    hostel_id, period_start, period_end
                )
            
            # Wait for all to complete
            for module, future in futures.items():
                try:
                    result = future.result(timeout=300)  # 5 min timeout
                    if result.get('success'):
                        results['modules_generated'].append(module)
                    else:
                        results['modules_failed'].append(module)
                        results['errors'].append({
                            'module': module,
                            'error': result.get('error', 'Unknown error')
                        })
                except Exception as e:
                    logger.error(f"Error generating {module} analytics: {str(e)}")
                    results['modules_failed'].append(module)
                    results['errors'].append({
                        'module': module,
                        'error': str(e)
                    })
                    results['success'] = False
        
        # Generate dashboard after all modules complete
        if 'dashboard' in modules and results['success']:
            try:
                self._generate_dashboard_analytics(
                    hostel_id, period_start, period_end
                )
                results['modules_generated'].append('dashboard')
            except Exception as e:
                logger.error(f"Error generating dashboard analytics: {str(e)}")
                results['modules_failed'].append('dashboard')
                results['errors'].append({
                    'module': 'dashboard',
                    'error': str(e)
                })
        
        logger.info(
            f"Analytics generation complete. "
            f"Success: {len(results['modules_generated'])}, "
            f"Failed: {len(results['modules_failed'])}"
        )
        
        return results
    
    def _generate_booking_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate booking analytics for period."""
        try:
            # This would call the BookingAnalyticsService
            # For now, placeholder
            logger.info(f"Generating booking analytics for {hostel_id}")
            
            return {
                'success': True,
                'module': 'booking',
                'records_created': 0
            }
        except Exception as e:
            logger.error(f"Booking analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'booking',
                'error': str(e)
            }
    
    def _generate_complaint_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate complaint analytics for period."""
        try:
            logger.info(f"Generating complaint analytics for {hostel_id}")
            
            return {
                'success': True,
                'module': 'complaint',
                'records_created': 0
            }
        except Exception as e:
            logger.error(f"Complaint analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'complaint',
                'error': str(e)
            }
    
    def _generate_financial_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate financial analytics for period."""
        try:
            logger.info(f"Generating financial analytics for {hostel_id}")
            
            return {
                'success': True,
                'module': 'financial',
                'records_created': 0
            }
        except Exception as e:
            logger.error(f"Financial analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'financial',
                'error': str(e)
            }
    
    def _generate_occupancy_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate occupancy analytics for period."""
        try:
            logger.info(f"Generating occupancy analytics for {hostel_id}")
            
            return {
                'success': True,
                'module': 'occupancy',
                'records_created': 0
            }
        except Exception as e:
            logger.error(f"Occupancy analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'occupancy',
                'error': str(e)
            }
    
    def _generate_supervisor_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate supervisor analytics for period."""
        try:
            logger.info(f"Generating supervisor analytics for {hostel_id}")
            
            return {
                'success': True,
                'module': 'supervisor',
                'records_created': 0
            }
        except Exception as e:
            logger.error(f"Supervisor analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'supervisor',
                'error': str(e)
            }
    
    def _generate_dashboard_analytics(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate dashboard analytics aggregating all modules."""
        try:
            logger.info(f"Generating dashboard analytics for {hostel_id}")
            
            # Get unified metrics
            metrics = self.aggregate_repo.get_unified_dashboard_metrics(
                hostel_id, period_start, period_end
            )
            
            return {
                'success': True,
                'module': 'dashboard',
                'metrics': metrics
            }
        except Exception as e:
            logger.error(f"Dashboard analytics generation failed: {str(e)}")
            return {
                'success': False,
                'module': 'dashboard',
                'error': str(e)
            }
    
    # ==================== Scheduled Analytics Updates ====================
    
    def run_daily_analytics_update(self) -> Dict[str, Any]:
        """
        Run daily analytics update for all active hostels.
        
        Should be called by a scheduled task (e.g., Celery beat).
        """
        logger.info("Starting daily analytics update")
        
        # Get yesterday's date
        yesterday = date.today() - timedelta(days=1)
        
        # Update for platform-wide
        platform_result = self.generate_all_analytics(
            hostel_id=None,
            period_start=yesterday,
            period_end=yesterday,
            modules=['booking', 'complaint', 'financial', 'occupancy', 'platform']
        )
        
        # Get all active hostels (would query from database)
        # For now, placeholder
        active_hostels = []
        
        hostel_results = []
        for hostel_id in active_hostels:
            result = self.generate_all_analytics(
                hostel_id=hostel_id,
                period_start=yesterday,
                period_end=yesterday
            )
            hostel_results.append(result)
        
        # Update quick stats
        self._update_quick_stats()
        
        return {
            'success': True,
            'date': yesterday.isoformat(),
            'platform_result': platform_result,
            'hostel_count': len(active_hostels),
            'hostel_results': hostel_results
        }
    
    def run_weekly_analytics_update(self) -> Dict[str, Any]:
        """Run weekly analytics update."""
        logger.info("Starting weekly analytics update")
        
        # Last 7 days
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        
        # Generate weekly summaries
        result = self.generate_all_analytics(
            hostel_id=None,
            period_start=start_date,
            period_end=end_date
        )
        
        return result
    
    def run_monthly_analytics_update(self) -> Dict[str, Any]:
        """Run monthly analytics update."""
        logger.info("Starting monthly analytics update")
        
        # Last month
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        # Generate monthly summaries
        result = self.generate_all_analytics(
            hostel_id=None,
            period_start=last_month_start,
            period_end=last_month_end
        )
        
        return result
    
    def _update_quick_stats(self) -> None:
        """Update quick stats for all hostels."""
        logger.info("Updating quick stats")
        
        # Would query all hostels and update their quick stats
        # Placeholder for now
        pass
    
    # ==================== Cache Management ====================
    
    def invalidate_analytics_cache(
        self,
        hostel_id: Optional[UUID] = None,
        modules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Invalidate analytics cache for specified scope.
        
        Args:
            hostel_id: Hostel ID (None for all)
            modules: Modules to invalidate (None for all)
            
        Returns:
            Invalidation results
        """
        logger.info(f"Invalidating analytics cache for hostel {hostel_id}")
        
        results = {
            'invalidated_count': 0,
            'modules': []
        }
        
        # Invalidate by module
        if modules is None or 'booking' in modules:
            # Invalidate booking analytics cache
            results['modules'].append('booking')
        
        if modules is None or 'complaint' in modules:
            # Invalidate complaint analytics cache
            results['modules'].append('complaint')
        
        # ... similar for other modules
        
        return results
    
    # ==================== Health Check ====================
    
    def check_analytics_health(self) -> Dict[str, Any]:
        """
        Check health of analytics system.
        
        Returns:
            Health status and diagnostics
        """
        health = {
            'status': 'healthy',
            'checks': {},
            'issues': []
        }
        
        # Check database connectivity
        try:
            # Simple query to verify DB
            self.db.execute("SELECT 1")
            health['checks']['database'] = 'ok'
        except Exception as e:
            health['checks']['database'] = 'failed'
            health['issues'].append(f"Database connectivity: {str(e)}")
            health['status'] = 'unhealthy'
        
        # Check if recent analytics exist
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        try:
            platform_metrics = self.platform_repo.get_platform_metrics(
                yesterday, yesterday
            )
            
            if platform_metrics:
                health['checks']['recent_analytics'] = 'ok'
            else:
                health['checks']['recent_analytics'] = 'warning'
                health['issues'].append("No analytics generated for yesterday")
                if health['status'] == 'healthy':
                    health['status'] = 'degraded'
        except Exception as e:
            health['checks']['recent_analytics'] = 'failed'
            health['issues'].append(f"Analytics check failed: {str(e)}")
            health['status'] = 'unhealthy'
        
        return health
    
    # ==================== Batch Operations ====================
    
    def backfill_analytics(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date,
        modules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Backfill analytics for a date range.
        
        Useful for historical data or fixing gaps.
        """
        logger.info(
            f"Backfilling analytics for {hostel_id} "
            f"from {start_date} to {end_date}"
        )
        
        results = {
            'success': True,
            'dates_processed': [],
            'dates_failed': [],
            'total_days': (end_date - start_date).days + 1
        }
        
        current_date = start_date
        while current_date <= end_date:
            try:
                result = self.generate_all_analytics(
                    hostel_id=hostel_id,
                    period_start=current_date,
                    period_end=current_date,
                    modules=modules
                )
                
                if result['success']:
                    results['dates_processed'].append(current_date.isoformat())
                else:
                    results['dates_failed'].append(current_date.isoformat())
                    results['success'] = False
                    
            except Exception as e:
                logger.error(f"Backfill failed for {current_date}: {str(e)}")
                results['dates_failed'].append(current_date.isoformat())
                results['success'] = False
            
            current_date += timedelta(days=1)
        
        return results