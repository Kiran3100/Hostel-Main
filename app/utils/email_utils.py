"""
Email utilities for hostel management system
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.utils import formataddr
from typing import List, Dict, Any, Optional, Union, Tuple
import os
import re
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader
from datetime import datetime
import base64
import mimetypes
from dataclasses import dataclass

@dataclass
class EmailConfig:
    """Email configuration dataclass"""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30

@dataclass
class EmailAddress:
    """Email address with optional name"""
    email: str
    name: Optional[str] = None
    
    def __str__(self):
        if self.name:
            return formataddr((self.name, self.email))
        return self.email

class EmailHelper:
    """Main email sending and management utilities"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.smtp_connection = None
        
    def connect(self) -> bool:
        """Establish SMTP connection"""
        try:
            if self.config.use_ssl:
                self.smtp_connection = smtplib.SMTP_SSL(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=self.config.timeout
                )
            else:
                self.smtp_connection = smtplib.SMTP(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=self.config.timeout
                )
                if self.config.use_tls:
                    self.smtp_connection.starttls()
            
            self.smtp_connection.login(self.config.username, self.config.password)
            return True
            
        except Exception as e:
            print(f"Failed to connect to SMTP server: {e}")
            return False
    
    def disconnect(self):
        """Close SMTP connection"""
        if self.smtp_connection:
            try:
                self.smtp_connection.quit()
            except:
                pass
            self.smtp_connection = None
    
    def send_email(self, 
                   to: Union[str, EmailAddress, List[Union[str, EmailAddress]]],
                   subject: str,
                   body: str,
                   from_address: Union[str, EmailAddress] = None,
                   cc: Union[str, EmailAddress, List[Union[str, EmailAddress]]] = None,
                   bcc: Union[str, EmailAddress, List[Union[str, EmailAddress]]] = None,
                   attachments: List[str] = None,
                   html: bool = False,
                   priority: str = 'normal') -> bool:
        """Send email with attachments and formatting options"""
        
        try:
            if not self.smtp_connection:
                if not self.connect():
                    return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Set headers
            msg['Subject'] = subject
            msg['From'] = str(from_address or EmailAddress(self.config.username))
            
            # Handle recipients
            to_list = self._normalize_email_list(to)
            msg['To'] = ', '.join([str(addr) for addr in to_list])
            
            if cc:
                cc_list = self._normalize_email_list(cc)
                msg['Cc'] = ', '.join([str(addr) for addr in cc_list])
            else:
                cc_list = []
            
            if bcc:
                bcc_list = self._normalize_email_list(bcc)
            else:
                bcc_list = []
            
            # Set priority
            if priority.lower() == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            elif priority.lower() == 'low':
                msg['X-Priority'] = '5'
                msg['X-MSMail-Priority'] = 'Low'
            
            # Add body
            if html:
                msg.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    self._add_attachment(msg, file_path)
            
            # Send email
            all_recipients = [addr.email for addr in (to_list + cc_list + bcc_list)]
            self.smtp_connection.sendmail(
                self.config.username,
                all_recipients,
                msg.as_string()
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
    
    def _normalize_email_list(self, emails: Union[str, EmailAddress, List[Union[str, EmailAddress]]]) -> List[EmailAddress]:
        """Normalize email input to list of EmailAddress objects"""
        if isinstance(emails, (str, EmailAddress)):
            emails = [emails]
        
        result = []
        for email in emails:
            if isinstance(email, str):
                result.append(EmailAddress(email))
            elif isinstance(email, EmailAddress):
                result.append(email)
        
        return result
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """Add file attachment to email message"""
        try:
            if not os.path.exists(file_path):
                print(f"Attachment file not found: {file_path}")
                return
            
            # Guess content type
            content_type, encoding = mimetypes.guess_type(file_path)
            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'
            
            main_type, sub_type = content_type.split('/', 1)
            
            with open(file_path, 'rb') as fp:
                if main_type == 'text':
                    attachment = MIMEText(fp.read().decode('utf-8'), _subtype=sub_type)
                elif main_type == 'image':
                    attachment = MIMEImage(fp.read(), _subtype=sub_type)
                else:
                    attachment = MIMEBase(main_type, sub_type)
                    attachment.set_payload(fp.read())
                    encoders.encode_base64(attachment)
            
            filename = os.path.basename(file_path)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename={filename}'
            )
            
            msg.attach(attachment)
            
        except Exception as e:
            print(f"Failed to add attachment {file_path}: {e}")
    
    def send_bulk_email(self, 
                       recipients: List[Union[str, EmailAddress]],
                       subject: str,
                       body: str,
                       batch_size: int = 50,
                       delay_between_batches: int = 1,
                       **kwargs) -> Dict[str, Any]:
        """Send email to multiple recipients in batches"""
        import time
        
        results = {
            'total_recipients': len(recipients),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        # Split recipients into batches
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            try:
                success = self.send_email(
                    to=batch,
                    subject=subject,
                    body=body,
                    **kwargs
                )
                
                if success:
                    results['successful'] += len(batch)
                else:
                    results['failed'] += len(batch)
                    results['errors'].append(f"Failed to send batch {i//batch_size + 1}")
                
            except Exception as e:
                results['failed'] += len(batch)
                results['errors'].append(f"Error in batch {i//batch_size + 1}: {str(e)}")
            
            # Delay between batches to avoid rate limiting
            if i + batch_size < len(recipients):
                time.sleep(delay_between_batches)
        
        return results
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

class TemplateRenderer:
    """Email template rendering utilities"""
    
    def __init__(self, templates_dir: str = 'templates/email'):
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True
        )
        
        # Create templates directory if it doesn't exist
        os.makedirs(templates_dir, exist_ok=True)
    
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render email template with variables"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**variables)
        except Exception as e:
            raise ValueError(f"Failed to render template {template_name}: {e}")
    
    def render_string_template(self, template_string: str, variables: Dict[str, Any]) -> str:
        """Render template from string"""
        try:
            template = Template(template_string)
            return template.render(**variables)
        except Exception as e:
            raise ValueError(f"Failed to render string template: {e}")
    
    def create_welcome_template(self) -> str:
        """Create welcome email template"""
        template_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to {{ hostel_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #366092; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; }
        .button { 
            display: inline-block; 
            background: #366092; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome to {{ hostel_name }}</h1>
    </div>
    
    <div class="content">
        <h2>Hello {{ student_name }},</h2>
        
        <p>Welcome to {{ hostel_name }}! We're excited to have you as part of our community.</p>
        
        <h3>Your Details:</h3>
        <ul>
            <li><strong>Student ID:</strong> {{ student_id }}</li>
            <li><strong>Room Number:</strong> {{ room_number }}</li>
            <li><strong>Check-in Date:</strong> {{ checkin_date }}</li>
        </ul>
        
        <h3>What's Next:</h3>
        <ol>
            <li>Complete your profile information</li>
            <li>Review hostel rules and regulations</li>
            <li>Complete fee payment if pending</li>
            <li>Collect your room keys from reception</li>
        </ol>
        
        <p>If you have any questions, please don't hesitate to contact us.</p>
        
        <a href="{{ portal_url }}" class="button">Access Student Portal</a>
    </div>
    
    <div class="footer">
        <p>{{ hostel_name }} | {{ hostel_address }}</p>
        <p>Phone: {{ hostel_phone }} | Email: {{ hostel_email }}</p>
    </div>
</body>
</html>
        """
        
        template_path = os.path.join(self.templates_dir, 'welcome.html')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content.strip())
        
        return template_path
    
    def create_payment_reminder_template(self) -> str:
        """Create payment reminder template"""
        template_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Payment Reminder - {{ hostel_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #d9534f; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; }
        .amount { font-size: 24px; font-weight: bold; color: #d9534f; }
        .due-date { background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .button { 
            display: inline-block; 
            background: #d9534f; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Payment Reminder</h1>
    </div>
    
    <div class="content">
        <h2>Hello {{ student_name }},</h2>
        
        <p>This is a reminder that you have an outstanding payment for {{ hostel_name }}.</p>
        
        <div class="due-date">
            <strong>Due Date:</strong> {{ due_date }}
        </div>
        
        <h3>Payment Details:</h3>
        <ul>
            <li><strong>Amount Due:</strong> <span class="amount">₹{{ amount_due }}</span></li>
            <li><strong>Fee Type:</strong> {{ fee_type }}</li>
            <li><strong>Period:</strong> {{ period }}</li>
        </ul>
        
        {% if late_fee %}
        <p><strong>Note:</strong> A late fee of ₹{{ late_fee }} will be applied if payment is not received by {{ due_date }}.</p>
        {% endif %}
        
        <p>Please make the payment as soon as possible to avoid any inconvenience.</p>
        
        <a href="{{ payment_url }}" class="button">Make Payment Now</a>
    </div>
    
    <div class="footer">
        <p>{{ hostel_name }} | {{ hostel_address }}</p>
        <p>Phone: {{ hostel_phone }} | Email: {{ hostel_email }}</p>
    </div>
</body>
</html>
        """
        
        template_path = os.path.join(self.templates_dir, 'payment_reminder.html')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content.strip())
        
        return template_path

class AttachmentHandler:
    """Email attachment handling utilities"""
    
    @staticmethod
    def create_pdf_attachment(content: str, filename: str) -> str:
        """Create PDF attachment from HTML content"""
        try:
            # This would require additional libraries like weasyprint or reportlab
            # For now, return a simple implementation
            temp_path = f"/tmp/{filename}"
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return temp_path
        except Exception as e:
            raise ValueError(f"Failed to create PDF attachment: {e}")
    
    @staticmethod
    def create_csv_attachment(data: List[Dict[str, Any]], filename: str) -> str:
        """Create CSV attachment from data"""
        import csv
        
        try:
            temp_path = f"/tmp/{filename}"
            
            if not data:
                return temp_path
            
            with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
            
            return temp_path
            
        except Exception as e:
            raise ValueError(f"Failed to create CSV attachment: {e}")
    
    @staticmethod
    def embed_image(image_path: str, cid: str = None) -> Tuple[str, str]:
        """Embed image in email for inline display"""
        try:
            if cid is None:
                cid = f"image_{os.path.basename(image_path).split('.')[0]}"
            
            with open(image_path, 'rb') as f:
                img_data = f.read()
            
            img_base64 = base64.b64encode(img_data).decode()
            content_type = mimetypes.guess_type(image_path)[0]
            
            # Return both the CID and the MIMEImage object data
            return cid, f"data:{content_type};base64,{img_base64}"
            
        except Exception as e:
            raise ValueError(f"Failed to embed image: {e}")

class EmailValidator:
    """Email validation utilities"""
    
    # Comprehensive email regex pattern
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Common disposable email providers
    DISPOSABLE_DOMAINS = {
        '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
        'tempmail.org', 'yopmail.com', 'throwaway.email'
    }
    
    @classmethod
    def validate_email(cls, email: str) -> Dict[str, Any]:
        """Comprehensive email validation"""
        result = {
            'is_valid': True,
            'email': email.lower().strip(),
            'errors': [],
            'warnings': []
        }
        
        email = email.strip().lower()
        
        # Basic format validation
        if not cls.EMAIL_PATTERN.match(email):
            result['is_valid'] = False
            result['errors'].append('Invalid email format')
            return result
        
        # Check for disposable email
        domain = email.split('@')[1]
        if domain in cls.DISPOSABLE_DOMAINS:
            result['warnings'].append('Disposable email address detected')
        
        # Check for common typos
        common_domains = {
            'gmail.com': ['gmai.com', 'gmial.com', 'gamail.com'],
            'yahoo.com': ['yaho.com', 'yahooo.com'],
            'hotmail.com': ['hotmial.com', 'hotmailc.om']
        }
        
        for correct_domain, typos in common_domains.items():
            if domain in typos:
                result['warnings'].append(f'Possible typo, did you mean {correct_domain}?')
        
        return result
    
    @classmethod
    def validate_email_list(cls, emails: List[str]) -> Dict[str, Any]:
        """Validate list of email addresses"""
        result = {
            'valid_emails': [],
            'invalid_emails': [],
            'total_count': len(emails),
            'valid_count': 0,
            'invalid_count': 0,
            'warnings': []
        }
        
        seen_emails = set()
        
        for email in emails:
            email_result = cls.validate_email(email)
            
            if email_result['is_valid']:
                if email_result['email'] in seen_emails:
                    result['warnings'].append(f'Duplicate email: {email_result["email"]}')
                else:
                    result['valid_emails'].append(email_result['email'])
                    seen_emails.add(email_result['email'])
                    result['valid_count'] += 1
            else:
                result['invalid_emails'].append({
                    'email': email,
                    'errors': email_result['errors']
                })
                result['invalid_count'] += 1
        
        return result

class EmailAnalytics:
    """Email analytics and tracking utilities"""
    
    def __init__(self):
        self.tracking_data = {}
    
    def generate_tracking_pixel(self, email_id: str) -> str:
        """Generate tracking pixel for email open tracking"""
        tracking_url = f"https://your-domain.com/track/open/{email_id}"
        return f'<img src="{tracking_url}" width="1" height="1" style="display:none;">'
    
    def generate_click_tracking_url(self, original_url: str, email_id: str, link_id: str) -> str:
        """Generate click tracking URL"""
        import urllib.parse
        
        encoded_url = urllib.parse.quote(original_url)
        return f"https://your-domain.com/track/click/{email_id}/{link_id}?url={encoded_url}"
    
    def track_email_sent(self, email_id: str, recipient: str, subject: str):
        """Record email sent event"""
        if email_id not in self.tracking_data:
            self.tracking_data[email_id] = {
                'recipient': recipient,
                'subject': subject,
                'sent_at': datetime.now(),
                'opened': False,
                'clicked_links': [],
                'bounce_status': None
            }
    
    def track_email_open(self, email_id: str):
        """Record email open event"""
        if email_id in self.tracking_data:
            self.tracking_data[email_id]['opened'] = True
            self.tracking_data[email_id]['opened_at'] = datetime.now()
    
    def track_link_click(self, email_id: str, link_id: str, url: str):
        """Record link click event"""
        if email_id in self.tracking_data:
            click_data = {
                'link_id': link_id,
                'url': url,
                'clicked_at': datetime.now()
            }
            self.tracking_data[email_id]['clicked_links'].append(click_data)
    
    def get_email_stats(self, email_id: str) -> Dict[str, Any]:
        """Get statistics for specific email"""
        return self.tracking_data.get(email_id, {})
    
    def get_campaign_stats(self, email_ids: List[str]) -> Dict[str, Any]:
        """Get aggregated statistics for email campaign"""
        stats = {
            'total_sent': len(email_ids),
            'total_opened': 0,
            'total_clicked': 0,
            'open_rate': 0.0,
            'click_rate': 0.0,
            'click_to_open_rate': 0.0
        }
        
        opened_emails = 0
        clicked_emails = 0
        
        for email_id in email_ids:
            if email_id in self.tracking_data:
                email_data = self.tracking_data[email_id]
                
                if email_data.get('opened'):
                    opened_emails += 1
                
                if email_data.get('clicked_links'):
                    clicked_emails += 1
        
        stats['total_opened'] = opened_emails
        stats['total_clicked'] = clicked_emails
        
        if stats['total_sent'] > 0:
            stats['open_rate'] = opened_emails / stats['total_sent']
            stats['click_rate'] = clicked_emails / stats['total_sent']
        
        if opened_emails > 0:
            stats['click_to_open_rate'] = clicked_emails / opened_emails
        
        return stats

class EmailQueueManager:
    """Email queue management for batch processing"""
    
    def __init__(self, max_queue_size: int = 1000):
        self.queue = []
        self.max_queue_size = max_queue_size
        self.failed_emails = []
    
    def add_to_queue(self, email_data: Dict[str, Any]) -> bool:
        """Add email to sending queue"""
        if len(self.queue) >= self.max_queue_size:
            return False
        
        email_data['queued_at'] = datetime.now()
        email_data['status'] = 'queued'
        self.queue.append(email_data)
        return True
    
    def process_queue(self, email_helper: EmailHelper, batch_size: int = 50) -> Dict[str, Any]:
        """Process email queue in batches"""
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        while self.queue and results['processed'] < batch_size:
            email_data = self.queue.pop(0)
            results['processed'] += 1
            
            try:
                success = email_helper.send_email(**email_data)
                
                if success:
                    results['successful'] += 1
                    email_data['status'] = 'sent'
                    email_data['sent_at'] = datetime.now()
                else:
                    results['failed'] += 1
                    email_data['status'] = 'failed'
                    self.failed_emails.append(email_data)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
                email_data['status'] = 'error'
                email_data['error'] = str(e)
                self.failed_emails.append(email_data)
        
        return results
    
    def retry_failed_emails(self, email_helper: EmailHelper) -> Dict[str, Any]:
        """Retry sending failed emails"""
        if not self.failed_emails:
            return {'message': 'No failed emails to retry'}
        
        retry_results = {
            'retried': 0,
            'successful': 0,
            'still_failed': 0
        }
        
        failed_to_retry = []
        
        for email_data in self.failed_emails:
            retry_results['retried'] += 1
            
            try:
                # Remove error status for retry
                email_data.pop('error', None)
                
                success = email_helper.send_email(**email_data)
                
                if success:
                    retry_results['successful'] += 1
                    email_data['status'] = 'sent'
                    email_data['sent_at'] = datetime.now()
                else:
                    retry_results['still_failed'] += 1
                    failed_to_retry.append(email_data)
                    
            except Exception as e:
                retry_results['still_failed'] += 1
                email_data['error'] = str(e)
                failed_to_retry.append(email_data)
        
        self.failed_emails = failed_to_retry
        return retry_results
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'queued_emails': len(self.queue),
            'failed_emails': len(self.failed_emails),
            'queue_capacity': self.max_queue_size,
            'queue_full': len(self.queue) >= self.max_queue_size
        }

class EmailTemplateManager:
    """Advanced email template management"""
    
    def __init__(self, templates_dir: str = 'templates/email'):
        self.templates_dir = templates_dir
        self.renderer = TemplateRenderer(templates_dir)
        
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Get list of available email templates"""
        templates = []
        
        if os.path.exists(self.templates_dir):
            for filename in os.listdir(self.templates_dir):
                if filename.endswith(('.html', '.txt')):
                    template_info = {
                        'name': filename,
                        'path': os.path.join(self.templates_dir, filename),
                        'type': 'html' if filename.endswith('.html') else 'text'
                    }
                    templates.append(template_info)
        
        return templates
    
    def create_template_from_data(self, template_name: str, template_data: Dict[str, Any]) -> str:
        """Create template file from structured data"""
        template_content = self._build_template_html(template_data)
        
        template_path = os.path.join(self.templates_dir, f"{template_name}.html")
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        return template_path
    
    def _build_template_html(self, data: Dict[str, Any]) -> str:
        """Build HTML template from structured data"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { background: {{ header_color|default('#366092') }}; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; }
        .button { 
            display: inline-block; 
            background: {{ button_color|default('#366092') }}; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
"""
        
        # Add header if specified
        if data.get('header'):
            html += f"""
        <div class="header">
            <h1>{data['header']['title']}</h1>
            {f"<p>{data['header']['subtitle']}</p>" if data['header'].get('subtitle') else ''}
        </div>
"""
        
        # Add content sections
        html += """
        <div class="content">
"""
        
        if data.get('sections'):
            for section in data['sections']:
                if section.get('type') == 'text':
                    html += f"<p>{section['content']}</p>\n"
                elif section.get('type') == 'heading':
                    level = section.get('level', 2)
                    html += f"<h{level}>{section['content']}</h{level}>\n"
                elif section.get('type') == 'list':
                    list_type = 'ol' if section.get('ordered') else 'ul'
                    html += f"<{list_type}>\n"
                    for item in section['items']:
                        html += f"<li>{item}</li>\n"
                    html += f"</{list_type}>\n"
                elif section.get('type') == 'button':
                    html += f'<a href="{section["url"]}" class="button">{section["text"]}</a>\n'
        
        html += """
        </div>
"""
        
        # Add footer if specified
        if data.get('footer'):
            html += f"""
        <div class="footer">
            {data['footer']['content']}
        </div>
"""
        
        html += """
    </div>
</body>
</html>"""
        
        return html