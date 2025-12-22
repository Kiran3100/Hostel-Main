"""
Date and time utility classes for hostel management system
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Tuple, Union
import pytz
from dateutil import tz, parser
from dateutil.relativedelta import relativedelta
import calendar
import re

class DateTimeHelper:
    """Comprehensive date and time manipulation utilities"""
    
    @staticmethod
    def now(timezone: str = 'UTC') -> datetime:
        """Get current datetime in specified timezone"""
        tz_obj = pytz.timezone(timezone)
        return datetime.now(tz_obj)
    
    @staticmethod
    def today(timezone: str = 'UTC') -> date:
        """Get current date in specified timezone"""
        tz_obj = pytz.timezone(timezone)
        return datetime.now(tz_obj).date()
    
    @staticmethod
    def parse_datetime(dt_string: str) -> datetime:
        """Parse datetime string with flexible formats"""
        try:
            # Try to parse with dateutil parser (very flexible)
            parsed_dt = parser.parse(dt_string)
            return parsed_dt
        except (ValueError, TypeError):
            # Try common formats manually
            common_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%d/%m/%Y',
                '%d-%m-%Y %H:%M:%S',
                '%d-%m-%Y %H:%M',
                '%d-%m-%Y',
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y %H:%M',
                '%m/%d/%Y',
            ]
            
            for fmt in common_formats:
                try:
                    return datetime.strptime(dt_string, fmt)
                except ValueError:
                    continue
            
            raise ValueError(f"Unable to parse datetime string: {dt_string}")
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = None, timezone: str = None) -> str:
        """Format datetime with timezone conversion"""
        if timezone:
            # Convert to specified timezone
            tz_obj = pytz.timezone(timezone)
            if dt.tzinfo is None:
                # Assume UTC if no timezone info
                dt = pytz.UTC.localize(dt)
            dt = dt.astimezone(tz_obj)
        
        if format_str is None:
            format_str = '%Y-%m-%d %H:%M:%S'
        
        return dt.strftime(format_str)
    
    @staticmethod
    def is_weekend(dt: Union[datetime, date]) -> bool:
        """Check if date falls on weekend"""
        if isinstance(dt, datetime):
            dt = dt.date()
        
        # 5 = Saturday, 6 = Sunday
        return dt.weekday() in (5, 6)
    
    @staticmethod
    def is_business_day(dt: Union[datetime, date], holidays: List[date] = None) -> bool:
        """Check if date is a business day"""
        if isinstance(dt, datetime):
            dt = dt.date()
        
        # Check if weekend
        if DateTimeHelper.is_weekend(dt):
            return False
        
        # Check if holiday
        if holidays and dt in holidays:
            return False
        
        return True
    
    @staticmethod
    def add_business_days(start_date: date, days: int, holidays: List[date] = None) -> date:
        """Add business days excluding weekends and holidays"""
        if holidays is None:
            holidays = []
        
        current_date = start_date
        days_added = 0
        direction = 1 if days > 0 else -1
        days_to_add = abs(days)
        
        while days_added < days_to_add:
            current_date += timedelta(days=direction)
            
            if DateTimeHelper.is_business_day(current_date, holidays):
                days_added += 1
        
        return current_date
    
    @staticmethod
    def time_until(target_dt: datetime, from_dt: datetime = None) -> timedelta:
        """Calculate time until target datetime"""
        if from_dt is None:
            from_dt = datetime.now()
        
        return target_dt - from_dt
    
    @staticmethod
    def time_since(past_dt: datetime, from_dt: datetime = None) -> timedelta:
        """Calculate time since past datetime"""
        if from_dt is None:
            from_dt = datetime.now()
        
        return from_dt - past_dt
    
    @staticmethod
    def humanize_timedelta(delta: timedelta) -> str:
        """Convert timedelta to human readable format"""
        seconds = int(delta.total_seconds())
        
        if seconds < 0:
            return "in the future"
        
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''} ago"
        
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        
        days = hours // 24
        if days < 7:
            return f"{days} day{'s' if days != 1 else ''} ago"
        
        weeks = days // 7
        if weeks < 4:
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        
        months = days // 30
        if months < 12:
            return f"{months} month{'s' if months != 1 else ''} ago"
        
        years = days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"


class TimezoneConverter:
    """Timezone conversion and management utilities"""
    
    def __init__(self, default_timezone: str = 'UTC'):
        self.default_timezone = default_timezone
    
    def convert_timezone(self, dt: datetime, from_tz: str, to_tz: str) -> datetime:
        """Convert datetime between timezones"""
        # Localize to source timezone if naive
        if dt.tzinfo is None:
            from_tz_obj = pytz.timezone(from_tz)
            dt = from_tz_obj.localize(dt)
        else:
            # Ensure it's in the from_tz
            from_tz_obj = pytz.timezone(from_tz)
            dt = dt.astimezone(from_tz_obj)
        
        # Convert to target timezone
        to_tz_obj = pytz.timezone(to_tz)
        return dt.astimezone(to_tz_obj)
    
    def to_utc(self, dt: datetime, from_tz: str = None) -> datetime:
        """Convert datetime to UTC"""
        if from_tz is None:
            from_tz = self.default_timezone
        
        return self.convert_timezone(dt, from_tz, 'UTC')
    
    def from_utc(self, dt: datetime, to_tz: str) -> datetime:
        """Convert UTC datetime to specified timezone"""
        return self.convert_timezone(dt, 'UTC', to_tz)
    
    def get_timezone_offset(self, timezone: str) -> int:
        """Get timezone offset in seconds"""
        tz_obj = pytz.timezone(timezone)
        now = datetime.now(tz_obj)
        offset = now.utcoffset()
        return int(offset.total_seconds()) if offset else 0
    
    def get_common_timezones(self) -> List[str]:
        """Get list of common timezones for selection"""
        common_timezones = [
            'UTC',
            'Asia/Kolkata',
            'America/New_York',
            'America/Chicago',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Dubai',
            'Australia/Sydney',
            'Pacific/Auckland'
        ]
        return common_timezones
    
    def detect_timezone(self, ip_address: str = None) -> str:
        """Detect timezone from IP address or browser"""
        # This is a simplified version - in production, you'd use a geo-IP service
        # For now, return default
        if ip_address:
            # You could integrate with services like ipapi.co or geoip2
            # Example: requests.get(f'https://ipapi.co/{ip_address}/timezone/').text
            pass
        
        return self.default_timezone


class DateRangeCalculator:
    """Date range calculation and validation utilities"""
    
    @staticmethod
    def create_date_range(start: date, end: date) -> List[date]:
        """Generate list of dates in range"""
        date_list = []
        current_date = start
        
        while current_date <= end:
            date_list.append(current_date)
            current_date += timedelta(days=1)
        
        return date_list
    
    @staticmethod
    def get_month_range(year: int, month: int) -> Tuple[date, date]:
        """Get first and last date of month"""
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        
        return (first_day, last_day)
    
    @staticmethod
    def get_quarter_range(year: int, quarter: int) -> Tuple[date, date]:
        """Get first and last date of quarter"""
        if quarter not in [1, 2, 3, 4]:
            raise ValueError("Quarter must be between 1 and 4")
        
        first_month = (quarter - 1) * 3 + 1
        last_month = first_month + 2
        
        first_day = date(year, first_month, 1)
        last_day_num = calendar.monthrange(year, last_month)[1]
        last_day = date(year, last_month, last_day_num)
        
        return (first_day, last_day)
    
    @staticmethod
    def get_year_range(year: int) -> Tuple[date, date]:
        """Get first and last date of year"""
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)
        
        return (first_day, last_day)
    
    @staticmethod
    def get_week_range(year: int, week: int) -> Tuple[date, date]:
        """Get first and last date of week"""
        # Get first day of the year
        jan_1 = date(year, 1, 1)
        
        # Calculate the first Monday of the year
        days_to_monday = (7 - jan_1.weekday()) % 7
        if days_to_monday == 0 and jan_1.weekday() != 0:
            days_to_monday = 7
        first_monday = jan_1 + timedelta(days=days_to_monday)
        
        # Calculate week start
        week_start = first_monday + timedelta(weeks=week-1)
        week_end = week_start + timedelta(days=6)
        
        return (week_start, week_end)
    
    @staticmethod
    def calculate_overlap(range1: Tuple[date, date], range2: Tuple[date, date]) -> Optional[Tuple[date, date]]:
        """Calculate overlap between two date ranges"""
        start1, end1 = range1
        start2, end2 = range2
        
        # Check if ranges overlap
        if end1 < start2 or end2 < start1:
            return None
        
        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        return (overlap_start, overlap_end)
    
    @staticmethod
    def days_in_range(start: date, end: date) -> int:
        """Calculate number of days in date range"""
        return (end - start).days + 1
    
    @staticmethod
    def months_in_range(start: date, end: date) -> int:
        """Calculate number of months in date range"""
        delta = relativedelta(end, start)
        return delta.years * 12 + delta.months + (1 if delta.days > 0 else 0)


class BusinessHoursChecker:
    """Business hours validation and calculation utilities"""
    
    def __init__(self, 
                 business_hours: dict = None, 
                 timezone: str = 'UTC',
                 holidays: List[date] = None):
        self.business_hours = business_hours or self._default_business_hours()
        self.timezone = timezone
        self.holidays = holidays or []
    
    def _default_business_hours(self) -> dict:
        """Default business hours configuration"""
        return {
            'monday': {'start': time(9, 0), 'end': time(18, 0)},
            'tuesday': {'start': time(9, 0), 'end': time(18, 0)},
            'wednesday': {'start': time(9, 0), 'end': time(18, 0)},
            'thursday': {'start': time(9, 0), 'end': time(18, 0)},
            'friday': {'start': time(9, 0), 'end': time(18, 0)},
            'saturday': {'start': time(9, 0), 'end': time(13, 0)},
            'sunday': None  # Closed
        }
    
    def is_business_hours(self, dt: datetime = None) -> bool:
        """Check if datetime falls within business hours"""
        if dt is None:
            dt = datetime.now(pytz.timezone(self.timezone))
        
        # Check if it's a holiday
        if dt.date() in self.holidays:
            return False
        
        # Get day name
        day_name = dt.strftime('%A').lower()
        
        # Check if day has business hours
        if day_name not in self.business_hours or self.business_hours[day_name] is None:
            return False
        
        hours = self.business_hours[day_name]
        current_time = dt.time()
        
        return hours['start'] <= current_time <= hours['end']
    
    def next_business_hour(self, from_dt: datetime = None) -> datetime:
        """Get next business hour datetime"""
        if from_dt is None:
            from_dt = datetime.now(pytz.timezone(self.timezone))
        
        current_dt = from_dt
        max_iterations = 365  # Prevent infinite loop
        iterations = 0
        
        while iterations < max_iterations:
            # Check if current time is within business hours
            if self.is_business_hours(current_dt):
                return current_dt
            
            day_name = current_dt.strftime('%A').lower()
            
            # If day has business hours
            if day_name in self.business_hours and self.business_hours[day_name] is not None:
                hours = self.business_hours[day_name]
                
                # If before business hours, return start of business
                if current_dt.time() < hours['start']:
                    return datetime.combine(current_dt.date(), hours['start'])
                
                # If after business hours, move to next day
                current_dt = datetime.combine(
                    current_dt.date() + timedelta(days=1),
                    time(0, 0)
                )
            else:
                # Move to next day
                current_dt = datetime.combine(
                    current_dt.date() + timedelta(days=1),
                    time(0, 0)
                )
            
            iterations += 1
        
        # If no business hours found, return original datetime
        return from_dt
    
    def previous_business_hour(self, from_dt: datetime = None) -> datetime:
        """Get previous business hour datetime"""
        if from_dt is None:
            from_dt = datetime.now(pytz.timezone(self.timezone))
        
        current_dt = from_dt
        max_iterations = 365
        iterations = 0
        
        while iterations < max_iterations:
            if self.is_business_hours(current_dt):
                return current_dt
            
            day_name = current_dt.strftime('%A').lower()
            
            if day_name in self.business_hours and self.business_hours[day_name] is not None:
                hours = self.business_hours[day_name]
                
                if current_dt.time() > hours['end']:
                    return datetime.combine(current_dt.date(), hours['end'])
                
                # Move to previous day
                current_dt = datetime.combine(
                    current_dt.date() - timedelta(days=1),
                    time(23, 59, 59)
                )
            else:
                # Move to previous day
                current_dt = datetime.combine(
                    current_dt.date() - timedelta(days=1),
                    time(23, 59, 59)
                )
            
            iterations += 1
        
        return from_dt
    
    def business_hours_between(self, start: datetime, end: datetime) -> timedelta:
        """Calculate business hours between two datetimes"""
        total_hours = timedelta()
        current_dt = start
        
        while current_dt < end:
            day_name = current_dt.strftime('%A').lower()
            
            if day_name in self.business_hours and self.business_hours[day_name] is not None:
                if current_dt.date() not in self.holidays:
                    hours = self.business_hours[day_name]
                    
                    # Calculate business hours for this day
                    day_start = datetime.combine(current_dt.date(), hours['start'])
                    day_end = datetime.combine(current_dt.date(), hours['end'])
                    
                    # Adjust for actual time range
                    actual_start = max(current_dt, day_start)
                    actual_end = min(end, day_end)
                    
                    if actual_start < actual_end:
                        total_hours += actual_end - actual_start
            
            # Move to next day
            current_dt = datetime.combine(current_dt.date() + timedelta(days=1), time(0, 0))
        
        return total_hours
    
    def add_business_hours(self, start: datetime, hours: int) -> datetime:
        """Add business hours to datetime"""
        current_dt = start
        hours_remaining = hours
        
        while hours_remaining > 0:
            if self.is_business_hours(current_dt):
                current_dt += timedelta(hours=1)
                hours_remaining -= 1
            else:
                current_dt = self.next_business_hour(current_dt)
        
        return current_dt


class AgeCalculator:
    """Age calculation utilities for student management"""
    
    @staticmethod
    def calculate_age(birth_date: date, as_of_date: date = None) -> int:
        """Calculate age in years"""
        if as_of_date is None:
            as_of_date = date.today()
        
        age = as_of_date.year - birth_date.year
        
        # Adjust if birthday hasn't occurred yet this year
        if (as_of_date.month, as_of_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    @staticmethod
    def calculate_age_precise(birth_date: date, as_of_date: date = None) -> Tuple[int, int, int]:
        """Calculate precise age (years, months, days)"""
        if as_of_date is None:
            as_of_date = date.today()
        
        delta = relativedelta(as_of_date, birth_date)
        
        return (delta.years, delta.months, delta.days)
    
    @staticmethod
    def is_minor(birth_date: date, as_of_date: date = None, adult_age: int = 18) -> bool:
        """Check if person is a minor"""
        age = AgeCalculator.calculate_age(birth_date, as_of_date)
        return age < adult_age
    
    @staticmethod
    def age_category(birth_date: date, as_of_date: date = None) -> str:
        """Determine age category (child, teen, adult, senior)"""
        age = AgeCalculator.calculate_age(birth_date, as_of_date)
        
        if age < 13:
            return "child"
        elif age < 18:
            return "teen"
        elif age < 60:
            return "adult"
        else:
            return "senior"
    
    @staticmethod
    def next_birthday(birth_date: date, from_date: date = None) -> date:
        """Calculate next birthday date"""
        if from_date is None:
            from_date = date.today()
        
        # This year's birthday
        this_year_birthday = date(from_date.year, birth_date.month, birth_date.day)
        
        # If birthday already passed this year, get next year's
        if this_year_birthday <= from_date:
            return date(from_date.year + 1, birth_date.month, birth_date.day)
        
        return this_year_birthday
    
    @staticmethod
    def days_until_birthday(birth_date: date, from_date: date = None) -> int:
        """Calculate days until next birthday"""
        next_bday = AgeCalculator.next_birthday(birth_date, from_date)
        
        if from_date is None:
            from_date = date.today()
        
        return (next_bday - from_date).days


class ScheduleHelper:
    """Scheduling and recurring event utilities"""
    
    @staticmethod
    def generate_recurring_dates(start_date: date, 
                               end_date: date,
                               frequency: str,
                               interval: int = 1,
                               weekdays: List[int] = None) -> List[date]:
        """Generate recurring dates based on frequency"""
        dates = []
        current_date = start_date
        
        frequency = frequency.lower()
        
        while current_date <= end_date:
            # Check weekday filter if provided
            if weekdays is None or current_date.weekday() in weekdays:
                dates.append(current_date)
            
            # Calculate next date based on frequency
            if frequency == 'daily':
                current_date += timedelta(days=interval)
            elif frequency == 'weekly':
                current_date += timedelta(weeks=interval)
            elif frequency == 'monthly':
                current_date += relativedelta(months=interval)
            elif frequency == 'yearly':
                current_date += relativedelta(years=interval)
            else:
                raise ValueError(f"Unsupported frequency: {frequency}")
        
        return dates
    
    @staticmethod
    def next_occurrence(last_occurrence: date, 
                       frequency: str, 
                       interval: int = 1) -> date:
        """Calculate next occurrence of recurring event"""
        frequency = frequency.lower()
        
        if frequency == 'daily':
            return last_occurrence + timedelta(days=interval)
        elif frequency == 'weekly':
            return last_occurrence + timedelta(weeks=interval)
        elif frequency == 'monthly':
            return last_occurrence + relativedelta(months=interval)
        elif frequency == 'yearly':
            return last_occurrence + relativedelta(years=interval)
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
    
    @staticmethod
    def is_due(last_occurrence: date,
              frequency: str,
              interval: int = 1,
              as_of_date: date = None) -> bool:
        """Check if recurring event is due"""
        if as_of_date is None:
            as_of_date = date.today()
        
        next_due = ScheduleHelper.next_occurrence(last_occurrence, frequency, interval)
        
        return as_of_date >= next_due


class AttendanceDateHelper:
    """Attendance-specific date utilities"""
    
    @staticmethod
    def get_attendance_month_dates(year: int, month: int) -> List[date]:
        """Get all dates for attendance tracking in a month"""
        first_day, last_day = DateRangeCalculator.get_month_range(year, month)
        return DateRangeCalculator.create_date_range(first_day, last_day)
    
    @staticmethod
    def get_semester_dates(start_date: date, duration_months: int) -> Tuple[date, date]:
        """Calculate semester start and end dates"""
        end_date = start_date + relativedelta(months=duration_months) - timedelta(days=1)
        return (start_date, end_date)
    
    @staticmethod
    def get_academic_year_dates(year: int) -> Tuple[date, date]:
        """Get academic year start and end dates"""
        # Typically July to June in India
        start_date = date(year, 7, 1)
        end_date = date(year + 1, 6, 30)
        return (start_date, end_date)
    
    @staticmethod
    def calculate_attendance_percentage(present_days: int, total_days: int) -> float:
        """Calculate attendance percentage"""
        if total_days == 0:
            return 0.0
        
        percentage = (present_days / total_days) * 100
        return round(percentage, 2)


class LeaveCalculator:
    """Leave calculation and validation utilities"""
    
    @staticmethod
    def calculate_leave_days(start_date: date, 
                           end_date: date,
                           exclude_weekends: bool = True,
                           exclude_holidays: List[date] = None) -> int:
        """Calculate number of leave days"""
        if exclude_holidays is None:
            exclude_holidays = []
        
        total_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            include_day = True
            
            # Check if weekend
            if exclude_weekends and DateTimeHelper.is_weekend(current_date):
                include_day = False
            
            # Check if holiday
            if current_date in exclude_holidays:
                include_day = False
            
            if include_day:
                total_days += 1
            
            current_date += timedelta(days=1)
        
        return total_days
    
    @staticmethod
    def get_leave_balance_expiry(balance_date: date, 
                               policy_months: int = 12) -> date:
        """Calculate leave balance expiry date"""
        expiry_date = balance_date + relativedelta(months=policy_months)
        return expiry_date
    
    @staticmethod
    def is_leave_period_valid(start_date: date, 
                            end_date: date,
                            max_consecutive_days: int = None) -> bool:
        """Validate leave period according to policy"""
        # Check if end date is after start date
        if end_date < start_date:
            return False
        
        # Check maximum consecutive days if specified
        if max_consecutive_days is not None:
            days = (end_date - start_date).days + 1
            if days > max_consecutive_days:
                return False
        
        return True


class DateTimeValidator:
    """Date and time validation utilities"""
    
    @staticmethod
    def is_valid_date(date_str: str, format_str: str = '%Y-%m-%d') -> bool:
        """Validate date string"""
        try:
            datetime.strptime(date_str, format_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_future_date(check_date: date) -> bool:
        """Check if date is in the future"""
        return check_date > date.today()
    
    @staticmethod
    def is_past_date(check_date: date) -> bool:
        """Check if date is in the past"""
        return check_date < date.today()
    
    @staticmethod
    def is_valid_date_range(start_date: date, end_date: date) -> bool:
        """Validate that end date is after start date"""
        return end_date >= start_date
    
    @staticmethod
    def is_within_range(check_date: date, start_date: date, end_date: date) -> bool:
        """Check if date is within a range"""
        return start_date <= check_date <= end_date


class DateTimeFormatter:
    """Advanced date and time formatting utilities"""
    
    @staticmethod
    def format_relative_date(target_date: date, from_date: date = None) -> str:
        """Format date relative to current date"""
        if from_date is None:
            from_date = date.today()
        
        delta = (target_date - from_date).days
        
        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Tomorrow"
        elif delta == -1:
            return "Yesterday"
        elif 0 < delta < 7:
            return f"In {delta} days"
        elif -7 < delta < 0:
            return f"{abs(delta)} days ago"
        elif delta > 0:
            weeks = delta // 7
            if weeks < 4:
                return f"In {weeks} week{'s' if weeks > 1 else ''}"
            months = delta // 30
            if months < 12:
                return f"In {months} month{'s' if months > 1 else ''}"
            years = delta // 365
            return f"In {years} year{'s' if years > 1 else ''}"
        else:
            weeks = abs(delta) // 7
            if weeks < 4:
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            months = abs(delta) // 30
            if months < 12:
                return f"{months} month{'s' if months > 1 else ''} ago"
            years = abs(delta) // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
    
    @staticmethod
    def format_duration(start: datetime, end: datetime) -> str:
        """Format duration between two datetimes"""
        delta = end - start
        
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        
        if days > 0:
            parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if seconds > 0 and not parts:  # Only show seconds if nothing else
            parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")
        
        return ", ".join(parts) if parts else "0 seconds"
    
    @staticmethod
    def format_time_of_day(dt: datetime) -> str:
        """Format time of day in readable format"""
        hour = dt.hour
        
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
    
    @staticmethod
    def format_indian_date(dt: date) -> str:
        """Format date in Indian format (DD/MM/YYYY)"""
        return dt.strftime('%d/%m/%Y')
    
    @staticmethod
    def format_month_year(dt: date) -> str:
        """Format as Month Year (e.g., January 2024)"""
        return dt.strftime('%B %Y')