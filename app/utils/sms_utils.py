"""
SMS utilities for hostel management system
"""

import requests
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re
import time
from urllib.parse import urlencode
import hashlib
import hmac

@dataclass
class SMSConfig:
    """SMS configuration dataclass"""
    provider: str  # 'twilio', 'msg91', 'textlocal', 'aws_sns'
    api_key: str
    api_secret: str
    sender_id: str
    base_url: Optional[str] = None
    timeout: int = 30

@dataclass
class SMSMessage:
    """SMS message dataclass"""
    phone_number: str
    message: str
    sender_id: Optional[str] = None
    priority: str = 'normal'  # 'low', 'normal', 'high'
    scheduled_at: Optional[datetime] = None

class SMSHelper:
    """Main SMS sending utilities"""
    
    def __init__(self, config: SMSConfig):
        self.config = config
        self.provider_handlers = {
            'twilio': self._send_twilio,
            'msg91': self._send_msg91,
            'textlocal': self._send_textlocal,
            'aws_sns': self._send_aws_sns
        }
    
    def send_sms(self, phone_number: str, message: str, 
                 sender_id: str = None, priority: str = 'normal') -> Dict[str, Any]:
        """Send SMS message"""
        # Validate phone number
        normalized_phone = self._normalize_phone_number(phone_number)
        if not normalized_phone:
            return {
                'success': False,
                'error': 'Invalid phone number format',
                'message_id': None
            }
        
        # Validate message
        if not message.strip():
            return {
                'success': False,
                'error': 'Message cannot be empty',
                'message_id': None
            }
        
        # Check message length and optimize if needed
        optimized_message = self._optimize_message_length(message)
        
        # Get sender ID
        sender_id = sender_id or self.config.sender_id
        
        # Send via configured provider
        handler = self.provider_handlers.get(self.config.provider)
        if not handler:
            return {
                'success': False,
                'error': f'Unsupported SMS provider: {self.config.provider}',
                'message_id': None
            }
        
        try:
            return handler(normalized_phone, optimized_message, sender_id, priority)
        except Exception as e:
            return {
                'success': False,
                'error': f'SMS sending failed: {str(e)}',
                'message_id': None
            }
    
    def send_bulk_sms(self, recipients: List[Dict[str, str]], 
                     message: str, sender_id: str = None,
                     batch_size: int = 100) -> Dict[str, Any]:
        """Send SMS to multiple recipients"""
        results = {
            'total_recipients': len(recipients),
            'successful': 0,
            'failed': 0,
            'results': [],
            'errors': []
        }
        
        # Process in batches
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            for recipient in batch:
                phone_number = recipient.get('phone_number')
                personalized_message = message
                
                # Replace variables in message if provided
                if recipient.get('variables'):
                    for key, value in recipient['variables'].items():
                        personalized_message = personalized_message.replace(
                            f"{{{key}}}", str(value)
                        )
                
                result = self.send_sms(phone_number, personalized_message, sender_id)
                
                results['results'].append({
                    'phone_number': phone_number,
                    'success': result['success'],
                    'message_id': result.get('message_id'),
                    'error': result.get('error')
                })
                
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"{phone_number}: {result.get('error')}")
                
                # Small delay between messages to avoid rate limiting
                time.sleep(0.1)
            
            # Longer delay between batches
            if i + batch_size < len(recipients):
                time.sleep(1)
        
        return results
    
    def _normalize_phone_number(self, phone_number: str) -> Optional[str]:
        """Normalize phone number to international format"""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone_number)
        
        # Handle Indian numbers
        if len(digits_only) == 10 and digits_only[0] in '6789':
            return f'+91{digits_only}'
        elif len(digits_only) == 11 and digits_only.startswith('91'):
            return f'+{digits_only}'
        elif len(digits_only) == 12 and digits_only.startswith('91'):
            return f'+{digits_only}'
        elif len(digits_only) == 13 and digits_only.startswith('91'):
            return f'+{digits_only}'
        
        # Handle other international formats
        if digits_only.startswith('00'):
            digits_only = digits_only[2:]
        
        if len(digits_only) >= 10:
            return f'+{digits_only}'
        
        return None
    
    def _optimize_message_length(self, message: str) -> str:
        """Optimize message length for SMS"""
        # SMS length limits
        single_sms_limit = 160
        unicode_sms_limit = 70
        
        # Check if message contains Unicode characters
        is_unicode = any(ord(char) > 127 for char in message)
        limit = unicode_sms_limit if is_unicode else single_sms_limit
        
        if len(message) <= limit:
            return message
        
        # Truncate with ellipsis if too long
        return message[:limit-3] + '...'
    
    def _send_twilio(self, phone_number: str, message: str, 
                    sender_id: str, priority: str) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        from twilio.rest import Client
        
        try:
            client = Client(self.config.api_key, self.config.api_secret)
            
            sms = client.messages.create(
                body=message,
                from_=sender_id,
                to=phone_number
            )
            
            return {
                'success': True,
                'message_id': sms.sid,
                'status': sms.status,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }
    
    def _send_msg91(self, phone_number: str, message: str, 
                   sender_id: str, priority: str) -> Dict[str, Any]:
        """Send SMS via MSG91"""
        url = "https://control.msg91.com/api/sendhttp.php"
        
        params = {
            'authkey': self.config.api_key,
            'mobiles': phone_number.replace('+', ''),
            'message': message,
            'sender': sender_id,
            'route': '4',  # Transactional route
            'country': '91'
        }
        
        try:
            response = requests.get(url, params=params, timeout=self.config.timeout)
            
            if response.status_code == 200:
                result = response.text.strip()
                
                if result.startswith('5'):  # Success response starts with 5
                    return {
                        'success': True,
                        'message_id': result,
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'message_id': None,
                        'error': f'MSG91 error: {result}'
                    }
            else:
                return {
                    'success': False,
                    'message_id': None,
                    'error': f'HTTP error: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }
    
    def _send_textlocal(self, phone_number: str, message: str, 
                       sender_id: str, priority: str) -> Dict[str, Any]:
        """Send SMS via TextLocal"""
        url = "https://api.textlocal.in/send/"
        
        data = {
            'apikey': self.config.api_key,
            'numbers': phone_number.replace('+', ''),
            'message': message,
            'sender': sender_id
        }
        
        try:
            response = requests.post(url, data=data, timeout=self.config.timeout)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    return {
                        'success': True,
                        'message_id': result.get('messages', [{}])[0].get('id'),
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'message_id': None,
                        'error': result.get('errors', [{}])[0].get('message', 'Unknown error')
                    }
            else:
                return {
                    'success': False,
                    'message_id': None,
                    'error': f'HTTP error: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }
    
    def _send_aws_sns(self, phone_number: str, message: str, 
                     sender_id: str, priority: str) -> Dict[str, Any]:
        """Send SMS via AWS SNS"""
        try:
            import boto3
            
            sns = boto3.client(
                'sns',
                aws_access_key_id=self.config.api_key,
                aws_secret_access_key=self.config.api_secret,
                region_name=self.config.base_url or 'us-east-1'
            )
            
            response = sns.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': sender_id
                    },
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            return {
                'success': True,
                'message_id': response['MessageId'],
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }

class MessageOptimizer:
    """SMS message optimization utilities"""
    
    # Common abbreviations for SMS
    ABBREVIATIONS = {
        'and': '&',
        'you': 'u',
        'your': 'ur',
        'are': 'r',
        'for': '4',
        'to': '2',
        'tomorrow': 'tmrw',
        'today': '2day',
        'please': 'pls',
        'thanks': 'thx',
        'because': 'bcoz',
        'before': 'b4',
        'after': 'aftr',
        'without': 'w/o',
        'with': 'w/',
        'information': 'info',
        'number': 'no.',
        'address': 'addr',
        'payment': 'pymnt',
        'message': 'msg',
        'regarding': 'reg',
        'attendance': 'attnd'
    }
    
    @classmethod
    def optimize_message(cls, message: str, max_length: int = 160) -> Dict[str, Any]:
        """Optimize message for SMS length"""
        original_length = len(message)
        
        if original_length <= max_length:
            return {
                'optimized_message': message,
                'original_length': original_length,
                'optimized_length': original_length,
                'characters_saved': 0,
                'optimization_applied': False
            }
        
        optimized = message.lower()
        characters_saved = 0
        
        # Apply abbreviations
        for full_word, abbrev in cls.ABBREVIATIONS.items():
            pattern = r'\b' + re.escape(full_word) + r'\b'
            new_optimized = re.sub(pattern, abbrev, optimized, flags=re.IGNORECASE)
            if new_optimized != optimized:
                characters_saved += len(optimized) - len(new_optimized)
                optimized = new_optimized
        
        # Remove extra spaces
        optimized = re.sub(r'\s+', ' ', optimized).strip()
        
        # If still too long, truncate with ellipsis
        if len(optimized) > max_length:
            optimized = optimized[:max_length-3] + '...'
        
        return {
            'optimized_message': optimized,
            'original_length': original_length,
            'optimized_length': len(optimized),
            'characters_saved': original_length - len(optimized),
            'optimization_applied': True
        }
    
    @classmethod
    def split_long_message(cls, message: str, max_length: int = 160) -> List[str]:
        """Split long message into multiple SMS parts"""
        if len(message) <= max_length:
            return [message]
        
        parts = []
        words = message.split()
        current_part = ""
        
        for word in words:
            # Check if adding this word would exceed limit
            test_part = f"{current_part} {word}".strip()
            
            if len(test_part) <= max_length:
                current_part = test_part
            else:
                # Start new part
                if current_part:
                    parts.append(current_part)
                current_part = word
                
                # If single word is too long, split it
                if len(current_part) > max_length:
                    while len(current_part) > max_length:
                        parts.append(current_part[:max_length-3] + '...')
                        current_part = '...' + current_part[max_length-3:]
        
        if current_part:
            parts.append(current_part)
        
        return parts
    
    @classmethod
    def estimate_sms_cost(cls, message: str, 
                         cost_per_sms: float = 0.10,
                         unicode_multiplier: float = 1.5) -> Dict[str, Any]:
        """Estimate SMS sending cost"""
        # Check if message contains Unicode characters
        is_unicode = any(ord(char) > 127 for char in message)
        
        # SMS length limits
        single_sms_limit = 70 if is_unicode else 160
        multi_sms_limit = 67 if is_unicode else 153  # Overhead for concatenation
        
        message_length = len(message)
        
        if message_length <= single_sms_limit:
            sms_count = 1
        else:
            # Calculate number of parts for multi-part SMS
            sms_count = (message_length + multi_sms_limit - 1) // multi_sms_limit
        
        base_cost = sms_count * cost_per_sms
        if is_unicode:
            base_cost *= unicode_multiplier
        
        return {
            'message_length': message_length,
            'is_unicode': is_unicode,
            'sms_count': sms_count,
            'estimated_cost': round(base_cost, 2),
            'cost_per_sms': cost_per_sms,
            'unicode_multiplier': unicode_multiplier if is_unicode else 1.0
        }

class NumberValidator:
    """Phone number validation utilities"""
    
    # Country-specific validation patterns
    COUNTRY_PATTERNS = {
        'IN': {
            'pattern': r'^(\+91|91)?[6-9]\d{9}$',
            'format': '+91XXXXXXXXXX',
            'length': 10
        },
        'US': {
            'pattern': r'^(\+1|1)?[2-9]\d{2}[2-9]\d{2}\d{4}$',
            'format': '+1XXXXXXXXXX',
            'length': 10
        },
        'UK': {
            'pattern': r'^(\+44|44)?[1-9]\d{8,9}$',
            'format': '+44XXXXXXXXX',
            'length': 10
        }
    }
    
    @classmethod
    def validate_phone_number(cls, phone_number: str, 
                             country_code: str = 'IN') -> Dict[str, Any]:
        """Validate phone number format"""
        result = {
            'is_valid': False,
            'normalized_number': None,
            'country_code': country_code,
            'errors': [],
            'warnings': []
        }
        
        if not phone_number:
            result['errors'].append('Phone number is required')
            return result
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_number)
        
        if country_code not in cls.COUNTRY_PATTERNS:
            result['errors'].append(f'Unsupported country code: {country_code}')
            return result
        
        pattern_info = cls.COUNTRY_PATTERNS[country_code]
        pattern = pattern_info['pattern']
        
        if re.match(pattern, cleaned):
            result['is_valid'] = True
            
            # Normalize to international format
            if country_code == 'IN':
                digits_only = re.sub(r'\D', '', cleaned)
                if len(digits_only) == 10:
                    result['normalized_number'] = f'+91{digits_only}'
                elif len(digits_only) >= 12:
                    result['normalized_number'] = f'+{digits_only[-12:]}'
                else:
                    result['normalized_number'] = f'+{digits_only}'
            
        else:
            result['errors'].append(f'Invalid format. Expected: {pattern_info["format"]}')
        
        return result
    
    @classmethod
    def validate_phone_list(cls, phone_numbers: List[str], 
                           country_code: str = 'IN') -> Dict[str, Any]:
        """Validate list of phone numbers"""
        results = {
            'total_numbers': len(phone_numbers),
            'valid_numbers': [],
            'invalid_numbers': [],
            'duplicates': [],
            'summary': {
                'valid_count': 0,
                'invalid_count': 0,
                'duplicate_count': 0
            }
        }
        
        seen_numbers = set()
        
        for phone_number in phone_numbers:
            validation_result = cls.validate_phone_number(phone_number, country_code)
            
            if validation_result['is_valid']:
                normalized = validation_result['normalized_number']
                
                if normalized in seen_numbers:
                    results['duplicates'].append(normalized)
                    results['summary']['duplicate_count'] += 1
                else:
                    results['valid_numbers'].append(normalized)
                    seen_numbers.add(normalized)
                    results['summary']['valid_count'] += 1
            else:
                results['invalid_numbers'].append({
                    'number': phone_number,
                    'errors': validation_result['errors']
                })
                results['summary']['invalid_count'] += 1
        
        return results

class DeliveryTracker:
    """SMS delivery tracking and status monitoring"""
    
    def __init__(self):
        self.delivery_status = {}
    
    def track_message(self, message_id: str, phone_number: str, 
                     provider: str, sent_at: datetime = None):
        """Start tracking SMS delivery"""
        self.delivery_status[message_id] = {
            'phone_number': phone_number,
            'provider': provider,
            'sent_at': sent_at or datetime.now(),
            'status': 'sent',
            'delivered_at': None,
            'failed_at': None,
            'failure_reason': None,
            'delivery_attempts': 1
        }
    
    def update_delivery_status(self, message_id: str, status: str, 
                              timestamp: datetime = None, 
                              failure_reason: str = None):
        """Update message delivery status"""
        if message_id not in self.delivery_status:
            return False
        
        tracking_info = self.delivery_status[message_id]
        tracking_info['status'] = status
        
        if status == 'delivered':
            tracking_info['delivered_at'] = timestamp or datetime.now()
        elif status == 'failed':
            tracking_info['failed_at'] = timestamp or datetime.now()
            tracking_info['failure_reason'] = failure_reason
        
        return True
    
    def get_delivery_report(self, message_ids: List[str] = None) -> Dict[str, Any]:
        """Get delivery report for messages"""
        if message_ids is None:
            message_ids = list(self.delivery_status.keys())
        
        report = {
            'total_messages': len(message_ids),
            'delivered': 0,
            'pending': 0,
            'failed': 0,
            'delivery_rate': 0.0,
            'average_delivery_time': None,
            'messages': []
        }
        
        delivery_times = []
        
        for msg_id in message_ids:
            if msg_id in self.delivery_status:
                status_info = self.delivery_status[msg_id]
                report['messages'].append(status_info)
                
                if status_info['status'] == 'delivered':
                    report['delivered'] += 1
                    if status_info['delivered_at'] and status_info['sent_at']:
                        delivery_time = status_info['delivered_at'] - status_info['sent_at']
                        delivery_times.append(delivery_time.total_seconds())
                elif status_info['status'] == 'failed':
                    report['failed'] += 1
                else:
                    report['pending'] += 1
        
        if report['total_messages'] > 0:
            report['delivery_rate'] = report['delivered'] / report['total_messages']
        
        if delivery_times:
            report['average_delivery_time'] = sum(delivery_times) / len(delivery_times)
        
        return report
    
    def get_failed_messages(self) -> List[Dict[str, Any]]:
        """Get list of failed message deliveries"""
        failed_messages = []
        
        for msg_id, status_info in self.delivery_status.items():
            if status_info['status'] == 'failed':
                failed_messages.append({
                    'message_id': msg_id,
                    'phone_number': status_info['phone_number'],
                    'failed_at': status_info['failed_at'],
                    'failure_reason': status_info['failure_reason'],
                    'delivery_attempts': status_info['delivery_attempts']
                })
        
        return failed_messages

class SMSTemplateManager:
    """SMS template management utilities"""
    
    def __init__(self):
        self.templates = {}
    
    def add_template(self, name: str, content: str, variables: List[str] = None):
        """Add SMS template"""
        self.templates[name] = {
            'content': content,
            'variables': variables or [],
            'created_at': datetime.now(),
            'usage_count': 0
        }
    
    def get_template(self, name: str) -> Dict[str, Any]:
        """Get SMS template"""
        return self.templates.get(name)
    
    def render_template(self, name: str, variables: Dict[str, Any]) -> str:
        """Render SMS template with variables"""
        template = self.templates.get(name)
        if not template:
            raise ValueError(f"Template '{name}' not found")
        
        content = template['content']
        
        # Replace variables
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            content = content.replace(placeholder, str(var_value))
        
        # Increment usage count
        template['usage_count'] += 1
        
        return content
    
    def create_default_templates(self):
        """Create default SMS templates"""
        templates = {
            'welcome': {
                'content': 'Welcome to {hostel_name}! Your room {room_number} is ready. Check-in: {checkin_date}. Contact: {contact_number}',
                'variables': ['hostel_name', 'room_number', 'checkin_date', 'contact_number']
            },
            'payment_reminder': {
                'content': 'Payment reminder: Rs.{amount} due on {due_date} for {fee_type}. Pay now: {payment_link}',
                'variables': ['amount', 'due_date', 'fee_type', 'payment_link']
            },
            'payment_received': {
                'content': 'Payment received! Rs.{amount} for {fee_type}. Receipt: {receipt_number}. Thank you!',
                'variables': ['amount', 'fee_type', 'receipt_number']
            },
            'attendance_alert': {
                'content': 'Attendance alert for {student_name}: {status} on {date}. Contact hostel for more info.',
                'variables': ['student_name', 'status', 'date']
            },
            'maintenance_update': {
                'content': 'Maintenance update for room {room_number}: {status}. Expected completion: {completion_date}',
                'variables': ['room_number', 'status', 'completion_date']
            },
            'announcement': {
                'content': 'Announcement: {title}. {message}. For details: {contact_info}',
                'variables': ['title', 'message', 'contact_info']
            }
        }
        
        for name, template_info in templates.items():
            self.add_template(name, template_info['content'], template_info['variables'])

class SMSAnalytics:
    """SMS analytics and reporting utilities"""
    
    def __init__(self):
        self.analytics_data = {}
    
    def record_sms_sent(self, message_id: str, phone_number: str, 
                       provider: str, cost: float, message_length: int):
        """Record SMS sending event"""
        self.analytics_data[message_id] = {
            'phone_number': phone_number,
            'provider': provider,
            'cost': cost,
            'message_length': message_length,
            'sent_at': datetime.now(),
            'delivered': False,
            'delivery_time': None,
            'failed': False,
            'failure_reason': None
        }
    
    def record_delivery(self, message_id: str, delivered_at: datetime):
        """Record SMS delivery"""
        if message_id in self.analytics_data:
            data = self.analytics_data[message_id]
            data['delivered'] = True
            data['delivery_time'] = (delivered_at - data['sent_at']).total_seconds()
    
    def record_failure(self, message_id: str, failure_reason: str):
        """Record SMS delivery failure"""
        if message_id in self.analytics_data:
            data = self.analytics_data[message_id]
            data['failed'] = True
            data['failure_reason'] = failure_reason
    
    def get_analytics_summary(self, start_date: datetime = None, 
                             end_date: datetime = None) -> Dict[str, Any]:
        """Get SMS analytics summary"""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        filtered_data = []
        for data in self.analytics_data.values():
            if start_date <= data['sent_at'] <= end_date:
                filtered_data.append(data)
        
        if not filtered_data:
            return {'message': 'No data available for the specified period'}
        
        total_sent = len(filtered_data)
        total_delivered = sum(1 for d in filtered_data if d['delivered'])
        total_failed = sum(1 for d in filtered_data if d['failed'])
        total_cost = sum(d['cost'] for d in filtered_data)
        
        # Calculate average delivery time
        delivery_times = [d['delivery_time'] for d in filtered_data if d['delivery_time']]
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        
        # Provider breakdown
        provider_stats = {}
        for data in filtered_data:
            provider = data['provider']
            if provider not in provider_stats:
                provider_stats[provider] = {'sent': 0, 'delivered': 0, 'failed': 0, 'cost': 0}
            
            provider_stats[provider]['sent'] += 1
            provider_stats[provider]['cost'] += data['cost']
            
            if data['delivered']:
                provider_stats[provider]['delivered'] += 1
            if data['failed']:
                provider_stats[provider]['failed'] += 1
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'total_sent': total_sent,
                'total_delivered': total_delivered,
                'total_failed': total_failed,
                'delivery_rate': total_delivered / total_sent if total_sent > 0 else 0,
                'total_cost': round(total_cost, 2),
                'average_cost_per_sms': round(total_cost / total_sent, 4) if total_sent > 0 else 0,
                'average_delivery_time': round(avg_delivery_time, 2)
            },
            'provider_breakdown': provider_stats
        }