# --- File: C:\Hostel-Main\app\repositories\fee_structure\fee_aggregate_repository.py ---
"""
Fee Aggregate Repository

Provides aggregated queries and analytics across all fee structure entities.
Combines data from fee structures, components, calculations, and discounts.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, select, desc, distinct
from sqlalchemy.orm import Session, joinedload

from app.models.fee_structure.fee_structure import FeeStructure
from app.models.fee_structure.charge_component import (
    ChargeComponent,
    DiscountConfiguration,
)
from app.models.fee_structure.fee_calculation import FeeCalculation
from app.models.base.enums import RoomType, FeeType
from app.repositories.base.base_repository import BaseRepository


class FeeAggregateRepository:
    """
    Fee Aggregate Repository
    
    Provides complex aggregated queries and analytics that span
    multiple fee structure entities.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    # ============================================================
    # Comprehensive Fee Structure Analytics
    # ============================================================
    
    def get_hostel_fee_summary(
        self,
        hostel_id: UUID,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive fee summary for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            as_of_date: Date to check (defaults to today)
            
        Returns:
            Dictionary with comprehensive fee summary
        """
        check_date = as_of_date or Date.today()
        
        # Get fee structures
        fee_structures = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        ).all()
        
        # Calculate statistics
        by_room_type = {}
        for fs in fee_structures:
            room_type = fs.room_type.value
            if room_type not in by_room_type:
                by_room_type[room_type] = []
            
            # Get component count
            component_count = self.session.query(func.count(ChargeComponent.id)).filter(
                ChargeComponent.fee_structure_id == fs.id,
                ChargeComponent.deleted_at.is_(None)
            ).scalar()
            
            by_room_type[room_type].append({
                'fee_structure_id': str(fs.id),
                'fee_type': fs.fee_type.value,
                'amount': float(fs.amount),
                'security_deposit': float(fs.security_deposit),
                'monthly_minimum': float(fs.monthly_total_minimum),
                'includes_mess': fs.includes_mess,
                'component_count': component_count,
                'effective_from': fs.effective_from.isoformat(),
                'effective_to': fs.effective_to.isoformat() if fs.effective_to else None
            })
        
        return {
            'hostel_id': str(hostel_id),
            'as_of_date': check_date.isoformat(),
            'total_fee_structures': len(fee_structures),
            'by_room_type': by_room_type,
            'room_types_available': list(by_room_type.keys())
        }
    
    def get_pricing_analytics(
        self,
        hostel_ids: Optional[List[UUID]] = None,
        room_type: Optional[RoomType] = None,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive pricing analytics.
        
        Args:
            hostel_ids: Optional list of hostel IDs
            room_type: Optional room type filter
            as_of_date: Date to check
            
        Returns:
            Dictionary with pricing analytics
        """
        check_date = as_of_date or Date.today()
        
        query = self.session.query(
            func.count(distinct(FeeStructure.hostel_id)).label('hostel_count'),
            func.count(FeeStructure.id).label('structure_count'),
            func.avg(FeeStructure.amount).label('avg_amount'),
            func.min(FeeStructure.amount).label('min_amount'),
            func.max(FeeStructure.amount).label('max_amount'),
            func.avg(FeeStructure.security_deposit).label('avg_deposit'),
            func.avg(FeeStructure.mess_charges_monthly).label('avg_mess'),
            func.sum(case(
                (FeeStructure.includes_mess == True, 1),
                else_=0
            )).label('includes_mess_count'),
            func.sum(case(
                (FeeStructure.electricity_charges == 'INCLUDED', 1),
                else_=0
            )).label('electricity_included_count'),
            func.sum(case(
                (FeeStructure.water_charges == 'INCLUDED', 1),
                else_=0
            )).label('water_included_count')
        ).filter(
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        )
        
        if hostel_ids:
            query = query.filter(FeeStructure.hostel_id.in_(hostel_ids))
        
        if room_type:
            query = query.filter(FeeStructure.room_type == room_type)
        
        result = query.first()
        
        return {
            'hostel_count': result.hostel_count or 0,
            'fee_structure_count': result.structure_count or 0,
            'average_rent': float(result.avg_amount or 0),
            'minimum_rent': float(result.min_amount or 0),
            'maximum_rent': float(result.max_amount or 0),
            'average_security_deposit': float(result.avg_deposit or 0),
            'average_mess_charges': float(result.avg_mess or 0),
            'includes_mess_count': result.includes_mess_count or 0,
            'electricity_included_count': result.electricity_included_count or 0,
            'water_included_count': result.water_included_count or 0,
            'as_of_date': check_date.isoformat()
        }
    
    def get_component_analytics(
        self,
        hostel_id: Optional[UUID] = None,
        component_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get analytics on charge components.
        
        Args:
            hostel_id: Optional hostel filter
            component_type: Optional component type filter
            
        Returns:
            Dictionary with component analytics
        """
        query = self.session.query(
            ChargeComponent.component_type,
            func.count(ChargeComponent.id).label('count'),
            func.avg(ChargeComponent.amount).label('avg_amount'),
            func.sum(ChargeComponent.amount).label('total_amount'),
            func.sum(case(
                (ChargeComponent.is_mandatory == True, 1),
                else_=0
            )).label('mandatory_count'),
            func.sum(case(
                (ChargeComponent.is_taxable == True, 1),
                else_=0
            )).label('taxable_count'),
            func.avg(ChargeComponent.tax_percentage).label('avg_tax_rate')
        ).filter(
            ChargeComponent.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(FeeStructure).filter(
                FeeStructure.hostel_id == hostel_id
            )
        
        if component_type:
            query = query.filter(ChargeComponent.component_type == component_type)
        
        query = query.group_by(ChargeComponent.component_type)
        
        results = query.all()
        
        by_type = {}
        total_components = 0
        total_amount = Decimal('0')
        
        for r in results:
            by_type[r.component_type] = {
                'count': r.count,
                'average_amount': float(r.avg_amount or 0),
                'total_amount': float(r.total_amount or 0),
                'mandatory_count': r.mandatory_count or 0,
                'taxable_count': r.taxable_count or 0,
                'average_tax_rate': float(r.avg_tax_rate or 0)
            }
            total_components += r.count
            total_amount += (r.total_amount or Decimal('0'))
        
        return {
            'total_components': total_components,
            'total_amount': float(total_amount),
            'by_type': by_type,
            'unique_types': len(by_type)
        }
    
    def get_discount_analytics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive discount analytics.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary with discount analytics
        """
        # Discount configuration stats
        discount_query = self.session.query(
            func.count(DiscountConfiguration.id).label('total_discounts'),
            func.sum(case(
                (DiscountConfiguration.is_active == True, 1),
                else_=0
            )).label('active_discounts'),
            func.sum(DiscountConfiguration.current_usage_count).label('total_usage'),
            func.avg(DiscountConfiguration.discount_percentage).label('avg_percentage'),
            func.sum(case(
                (DiscountConfiguration.discount_type == 'percentage', 1),
                else_=0
            )).label('percentage_type_count'),
            func.sum(case(
                (DiscountConfiguration.discount_type == 'fixed_amount', 1),
                else_=0
            )).label('fixed_type_count')
        ).filter(
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if hostel_id:
            discount_query = discount_query.filter(
                or_(
                    DiscountConfiguration.hostel_ids.is_(None),
                    DiscountConfiguration.hostel_ids.like(f'%{hostel_id}%')
                )
            )
        
        discount_result = discount_query.first()
        
        # Calculation discount stats
        calc_query = self.session.query(
            func.count(FeeCalculation.id).label('total_calculations'),
            func.sum(case(
                (FeeCalculation.discount_applied > 0, 1),
                else_=0
            )).label('calculations_with_discount'),
            func.sum(FeeCalculation.discount_applied).label('total_discount_amount'),
            func.avg(FeeCalculation.discount_applied).label('avg_discount_amount')
        )
        
        if start_date:
            calc_query = calc_query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            calc_query = calc_query.filter(FeeCalculation.calculation_date <= end_date)
        
        calc_result = calc_query.first()
        
        return {
            'discount_configurations': {
                'total': discount_result.total_discounts or 0,
                'active': discount_result.active_discounts or 0,
                'total_usage': discount_result.total_usage or 0,
                'average_percentage': float(discount_result.avg_percentage or 0),
                'percentage_type_count': discount_result.percentage_type_count or 0,
                'fixed_type_count': discount_result.fixed_type_count or 0
            },
            'discount_application': {
                'total_calculations': calc_result.total_calculations or 0,
                'calculations_with_discount': calc_result.calculations_with_discount or 0,
                'usage_rate': (calc_result.calculations_with_discount / calc_result.total_calculations * 100)
                            if calc_result.total_calculations else 0,
                'total_discount_given': float(calc_result.total_discount_amount or 0),
                'average_discount': float(calc_result.avg_discount_amount or 0)
            }
        }
    
    # ============================================================
    # Revenue and Financial Analytics
    # ============================================================
    
    def get_revenue_summary(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive revenue summary from calculations.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary with revenue summary
        """
        query = self.session.query(
            func.count(FeeCalculation.id).label('total_calculations'),
            func.sum(FeeCalculation.total_payable).label('total_revenue'),
            func.sum(FeeCalculation.security_deposit).label('total_deposits'),
            func.sum(FeeCalculation.monthly_recurring).label('total_recurring'),
            func.sum(FeeCalculation.discount_applied).label('total_discounts'),
            func.sum(FeeCalculation.tax_amount).label('total_tax'),
            func.avg(FeeCalculation.total_payable).label('avg_revenue'),
            func.sum(case(
                (FeeCalculation.is_approved == True, FeeCalculation.total_payable),
                else_=0
            )).label('approved_revenue')
        )
        
        if hostel_id:
            query = query.join(FeeStructure).filter(
                FeeStructure.hostel_id == hostel_id
            )
        
        if start_date:
            query = query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.calculation_date <= end_date)
        
        result = query.first()
        
        total_revenue = float(result.total_revenue or 0)
        total_discounts = float(result.total_discounts or 0)
        
        return {
            'total_calculations': result.total_calculations or 0,
            'total_revenue': total_revenue,
            'total_deposits_collected': float(result.total_deposits or 0),
            'total_recurring_revenue': float(result.total_recurring or 0),
            'total_discounts_given': total_discounts,
            'total_tax_collected': float(result.total_tax or 0),
            'average_revenue_per_calculation': float(result.avg_revenue or 0),
            'approved_revenue': float(result.approved_revenue or 0),
            'discount_percentage_of_revenue': (total_discounts / total_revenue * 100) 
                                             if total_revenue else 0,
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    
    def get_revenue_by_room_type(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get revenue breakdown by room type.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary with revenue by room type
        """
        query = self.session.query(
            FeeCalculation.room_type,
            func.count(FeeCalculation.id).label('count'),
            func.sum(FeeCalculation.total_payable).label('total_revenue'),
            func.avg(FeeCalculation.total_payable).label('avg_revenue'),
            func.sum(FeeCalculation.discount_applied).label('total_discount')
        )
        
        if hostel_id:
            query = query.join(FeeStructure).filter(
                FeeStructure.hostel_id == hostel_id
            )
        
        if start_date:
            query = query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.calculation_date <= end_date)
        
        query = query.group_by(FeeCalculation.room_type)
        
        results = query.all()
        
        by_room_type = {}
        total_revenue = Decimal('0')
        
        for r in results:
            revenue = float(r.total_revenue or 0)
            by_room_type[r.room_type] = {
                'calculation_count': r.count,
                'total_revenue': revenue,
                'average_revenue': float(r.avg_revenue or 0),
                'total_discount': float(r.total_discount or 0)
            }
            total_revenue += (r.total_revenue or Decimal('0'))
        
        # Calculate percentages
        for room_type, data in by_room_type.items():
            data['revenue_percentage'] = (data['total_revenue'] / float(total_revenue) * 100) \
                                        if total_revenue else 0
        
        return {
            'total_revenue': float(total_revenue),
            'by_room_type': by_room_type,
            'room_types': list(by_room_type.keys())
        }
    
    def get_monthly_revenue_trend(
        self,
        hostel_id: Optional[UUID] = None,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get monthly revenue trends.
        
        Args:
            hostel_id: Optional hostel filter
            months: Number of months to analyze
            
        Returns:
            List of monthly revenue data
        """
        start_date = Date.fromordinal(Date.today().toordinal() - (months * 30))
        
        query = self.session.query(
            func.date_trunc('month', FeeCalculation.calculation_date).label('month'),
            func.count(FeeCalculation.id).label('count'),
            func.sum(FeeCalculation.total_payable).label('revenue'),
            func.sum(FeeCalculation.discount_applied).label('discount'),
            func.avg(FeeCalculation.total_payable).label('avg_revenue')
        ).filter(
            FeeCalculation.calculation_date >= start_date
        )
        
        if hostel_id:
            query = query.join(FeeStructure).filter(
                FeeStructure.hostel_id == hostel_id
            )
        
        query = query.group_by(
            func.date_trunc('month', FeeCalculation.calculation_date)
        ).order_by(
            func.date_trunc('month', FeeCalculation.calculation_date)
        )
        
        results = query.all()
        
        return [
            {
                'month': r.month.isoformat() if r.month else None,
                'calculation_count': r.count,
                'total_revenue': float(r.revenue or 0),
                'total_discount': float(r.discount or 0),
                'average_revenue': float(r.avg_revenue or 0),
                'net_revenue': float((r.revenue or 0) - (r.discount or 0))
            }
            for r in results
        ]
    
    # ============================================================
    # Comparative Analytics
    # ============================================================
    
    def compare_fee_structures(
        self,
        fee_structure_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple fee structures.
        
        Args:
            fee_structure_ids: List of fee structure IDs to compare
            
        Returns:
            List of fee structure comparisons
        """
        fee_structures = self.session.query(FeeStructure).filter(
            FeeStructure.id.in_(fee_structure_ids),
            FeeStructure.deleted_at.is_(None)
        ).all()
        
        comparisons = []
        
        for fs in fee_structures:
            # Get component count and total
            component_stats = self.session.query(
                func.count(ChargeComponent.id).label('count'),
                func.sum(ChargeComponent.amount).label('total')
            ).filter(
                ChargeComponent.fee_structure_id == fs.id,
                ChargeComponent.deleted_at.is_(None)
            ).first()
            
            # Get calculation stats
            calc_stats = self.session.query(
                func.count(FeeCalculation.id).label('count'),
                func.avg(FeeCalculation.total_payable).label('avg_total')
            ).filter(
                FeeCalculation.fee_structure_id == fs.id
            ).first()
            
            comparisons.append({
                'fee_structure_id': str(fs.id),
                'hostel_id': str(fs.hostel_id),
                'room_type': fs.room_type.value,
                'fee_type': fs.fee_type.value,
                'base_amount': float(fs.amount),
                'security_deposit': float(fs.security_deposit),
                'monthly_minimum': float(fs.monthly_total_minimum),
                'includes_mess': fs.includes_mess,
                'all_inclusive': fs.is_all_inclusive,
                'component_count': component_stats.count or 0,
                'component_total': float(component_stats.total or 0),
                'calculation_count': calc_stats.count or 0,
                'average_total_payable': float(calc_stats.avg_total or 0),
                'effective_from': fs.effective_from.isoformat(),
                'is_active': fs.is_active
            })
        
        return comparisons
    
    def get_market_positioning(
        self,
        hostel_id: UUID,
        room_type: RoomType
    ) -> Dict[str, Any]:
        """
        Analyze market positioning for a hostel's room type.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type to analyze
            
        Returns:
            Dictionary with market positioning analysis
        """
        # Get hostel's pricing
        hostel_fs = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.is_active == True,
            FeeStructure.deleted_at.is_(None)
        ).first()
        
        if not hostel_fs:
            return {'error': 'No active fee structure found'}
        
        # Get market statistics
        market_stats = self.session.query(
            func.count(FeeStructure.id).label('competitor_count'),
            func.avg(FeeStructure.amount).label('market_avg'),
            func.min(FeeStructure.amount).label('market_min'),
            func.max(FeeStructure.amount).label('market_max'),
            func.percentile_cont(0.25).within_group(FeeStructure.amount).label('percentile_25'),
            func.percentile_cont(0.50).within_group(FeeStructure.amount).label('percentile_50'),
            func.percentile_cont(0.75).within_group(FeeStructure.amount).label('percentile_75')
        ).filter(
            FeeStructure.room_type == room_type,
            FeeStructure.is_active == True,
            FeeStructure.deleted_at.is_(None),
            FeeStructure.hostel_id != hostel_id  # Exclude self
        ).first()
        
        hostel_amount = float(hostel_fs.amount)
        market_avg = float(market_stats.market_avg or 0)
        
        return {
            'hostel_id': str(hostel_id),
            'room_type': room_type.value,
            'hostel_amount': hostel_amount,
            'market_statistics': {
                'competitor_count': market_stats.competitor_count or 0,
                'average': market_avg,
                'minimum': float(market_stats.market_min or 0),
                'maximum': float(market_stats.market_max or 0),
                'percentile_25': float(market_stats.percentile_25 or 0),
                'percentile_50': float(market_stats.percentile_50 or 0),
                'percentile_75': float(market_stats.percentile_75 or 0)
            },
            'positioning': {
                'difference_from_average': hostel_amount - market_avg,
                'percentage_of_average': (hostel_amount / market_avg * 100) if market_avg else 0,
                'is_below_market': hostel_amount < market_avg,
                'is_above_market': hostel_amount > market_avg,
                'percentile_position': self._calculate_percentile_position(
                    hostel_amount,
                    float(market_stats.percentile_25 or 0),
                    float(market_stats.percentile_50 or 0),
                    float(market_stats.percentile_75 or 0)
                )
            }
        }
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _calculate_percentile_position(
        self,
        value: float,
        p25: float,
        p50: float,
        p75: float
    ) -> str:
        """Calculate which percentile range a value falls into."""
        if value < p25:
            return 'bottom_quartile'
        elif value < p50:
            return 'below_median'
        elif value < p75:
            return 'above_median'
        else:
            return 'top_quartile'