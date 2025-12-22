"""
Data formatting utilities for hostel management system
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, time
from decimal import Decimal
import json
from enum import Enum

class CurrencyFormatter:
    """Currency formatting utilities"""
    
    CURRENCY_SYMBOLS = {
        'INR': '₹',
        'USD': '$',
        'EUR': '€',
        'GBP': '£'
    }
    
    @classmethod
    def format_amount(cls, amount: Union[Decimal, float], 
                     currency: str = 'INR',
                     include_symbol: bool = True,
                     decimal_places: int = 2) -> str:
        """Format monetary amount"""
        
    @classmethod
    def format_indian_currency(cls, amount: Union[Decimal, float]) -> str:
        """Format amount in Indian currency format with lakhs/crores"""
        
    @classmethod
    def format_compact_currency(cls, amount: Union[Decimal, float],
                               currency: str = 'INR') -> str:
        """Format currency in compact form (K, M, B)"""
        
    @classmethod
    def parse_amount(cls, amount_str: str) -> Decimal:
        """Parse formatted amount string to Decimal"""

class DateTimeFormatter:
    """Date and time formatting utilities"""
    
    COMMON_FORMATS = {
        'short_date': '%d/%m/%Y',
        'long_date': '%B %d, %Y',
        'iso_date': '%Y-%m-%d',
        'short_datetime': '%d/%m/%Y %H:%M',
        'long_datetime': '%B %d, %Y at %I:%M %p',
        'time_12h': '%I:%M %p',
        'time_24h': '%H:%M'
    }
    
    @classmethod
    def format_date(cls, date_obj: date, format_type: str = 'short_date') -> str:
        """Format date with predefined formats"""
        
    @classmethod
    def format_datetime(cls, datetime_obj: datetime, 
                       format_type: str = 'short_datetime',
                       timezone: str = None) -> str:
        """Format datetime with timezone handling"""
        
    @classmethod
    def format_time_duration(cls, seconds: int) -> str:
        """Format duration in human readable format"""
        
    @classmethod
    def format_relative_time(cls, datetime_obj: datetime) -> str:
        """Format relative time (2 hours ago, tomorrow, etc.)"""
        
    @classmethod
    def format_age(cls, birth_date: date) -> str:
        """Format age in human readable format"""

class NumberFormatter:
    """Number formatting utilities"""
    
    @classmethod
    def format_percentage(cls, value: float, decimal_places: int = 1) -> str:
        """Format percentage value"""
        
    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """Format file size in human readable units"""
        
    @classmethod
    def format_phone_number(cls, phone: str, country_code: str = 'IN') -> str:
        """Format phone number for display"""
        
    @classmethod
    def format_decimal(cls, value: Decimal, decimal_places: int = 2) -> str:
        """Format decimal number"""
        
    @classmethod
    def format_ordinal(cls, number: int) -> str:
        """Format ordinal number (1st, 2nd, 3rd, etc.)"""
        
    @classmethod
    def format_with_separators(cls, number: Union[int, float], separator: str = ',') -> str:
        """Format number with thousands separators"""

class AddressFormatter:
    """Address formatting utilities"""
    
    @classmethod
    def format_full_address(cls, address_data: Dict[str, str],
                           country: str = 'India',
                           single_line: bool = False) -> str:
        """Format complete address"""
        
    @classmethod
    def format_city_state(cls, city: str, state: str) -> str:
        """Format city, state combination"""
        
    @classmethod
    def format_postal_code(cls, postal_code: str, country: str = 'IN') -> str:
        """Format postal code according to country standards"""
        
    @classmethod
    def format_address_label(cls, address_data: Dict[str, str]) -> List[str]:
        """Format address for mailing label"""

class ContactFormatter:
    """Contact information formatting utilities"""
    
    @classmethod
    def format_contact_card(cls, contact_data: Dict[str, Any]) -> Dict[str, str]:
        """Format contact information for display"""
        
    @classmethod
    def format_emergency_contact(cls, contact_data: Dict[str, Any]) -> str:
        """Format emergency contact information"""
        
    @classmethod
    def mask_sensitive_info(cls, data: Dict[str, Any],
                           fields_to_mask: List[str]) -> Dict[str, Any]:
        """Mask sensitive contact information"""

class TableFormatter:
    """Table and list formatting utilities"""
    
    @classmethod
    def format_table_data(cls, data: List[Dict[str, Any]],
                         column_config: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format data for table display"""
        
    @classmethod
    def format_csv_row(cls, data: Dict[str, Any], columns: List[str]) -> List[str]:
        """Format row data for CSV export"""
        
    @classmethod
    def format_key_value_pairs(cls, data: Dict[str, Any],
                              exclude_fields: List[str] = None) -> List[Dict[str, str]]:
        """Format data as key-value pairs"""

class ReportFormatter:
    """Report formatting utilities"""
    
    @classmethod
    def format_summary_stats(cls, stats: Dict[str, Union[int, float]]) -> Dict[str, str]:
        """Format summary statistics for reports"""
        
    @classmethod
    def format_trend_data(cls, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format trend data for visualization"""
        
    @classmethod
    def format_comparison_data(cls, current: Dict[str, Any],
                              previous: Dict[str, Any]) -> Dict[str, Any]:
        """Format comparison data showing changes"""

class DataExportFormatter:
    """Data export formatting utilities"""
    
    @classmethod
    def format_for_excel(cls, data: List[Dict[str, Any]],
                        column_mappings: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """Format data for Excel export"""
        
    @classmethod
    def format_for_csv(cls, data: List[Dict[str, Any]]) -> List[List[str]]:
        """Format data for CSV export"""
        
    @classmethod
    def format_for_pdf(cls, data: List[Dict[str, Any]],
                      formatting_rules: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Format data for PDF export"""
        
    @classmethod
    def format_for_json(cls, data: Any) -> str:
        """Format data for JSON export"""

class StudentFormatter:
    """Student-specific formatting utilities"""
    
    @classmethod
    def format_student_profile(cls, student_data: Dict[str, Any]) -> Dict[str, str]:
        """Format student profile for display"""
        
    @classmethod
    def format_attendance_summary(cls, attendance_data: Dict[str, Any]) -> Dict[str, str]:
        """Format attendance summary"""
        
    @classmethod
    def format_fee_statement(cls, fee_data: Dict[str, Any]) -> Dict[str, str]:
        """Format fee statement"""

class BookingFormatter:
    """Booking-specific formatting utilities"""
    
    @classmethod
    def format_booking_confirmation(cls, booking_data: Dict[str, Any]) -> Dict[str, str]:
        """Format booking confirmation details"""
        
    @classmethod
    def format_booking_summary(cls, booking_data: Dict[str, Any]) -> Dict[str, str]:
        """Format booking summary for display"""

class PaymentFormatter:
    """Payment-specific formatting utilities"""
    
    @classmethod
    def format_payment_receipt(cls, payment_data: Dict[str, Any]) -> Dict[str, str]:
        """Format payment receipt"""
        
    @classmethod
    def format_transaction_history(cls, transactions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format transaction history"""

class NotificationFormatter:
    """Notification formatting utilities"""
    
    @classmethod
    def format_email_template(cls, template_data: Dict[str, Any],
                             variables: Dict[str, Any]) -> Dict[str, str]:
        """Format email template with variables"""
        
    @classmethod
    def format_sms_message(cls, template: str, variables: Dict[str, Any],
                          max_length: int = 160) -> str:
        """Format SMS message with character limit"""
        
    @classmethod
    def format_push_notification(cls, notification_data: Dict[str, Any]) -> Dict[str, str]:
        """Format push notification"""

class TemplateFormatter:
    """Template variable formatting utilities"""
    
    @classmethod
    def replace_variables(cls, template: str, variables: Dict[str, Any]) -> str:
        """Replace template variables with actual values"""
        
    @classmethod
    def format_conditional_content(cls, template: str, 
                                  conditions: Dict[str, bool]) -> str:
        """Format template with conditional content"""
        
    @classmethod
    def escape_html_variables(cls, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Escape HTML in template variables"""

class ValidationMessageFormatter:
    """Validation message formatting utilities"""
    
    @classmethod
    def format_field_errors(cls, errors: Dict[str, List[str]]) -> List[str]:
        """Format field validation errors"""
        
    @classmethod
    def format_summary_message(cls, errors: List[str]) -> str:
        """Format summary validation message"""
        
    @classmethod
    def format_success_message(cls, action: str, entity: str) -> str:
        """Format success message"""