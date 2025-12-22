"""
PDF generation and manipulation utilities for hostel management system
"""

import os
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
import io
import base64
from datetime import datetime

from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import fitz  # PyMuPDF
from PIL import Image as PILImage

class PDFGenerator:
    """Main PDF generation utilities"""
    
    def __init__(self, page_size=A4, margins=None):
        self.page_size = page_size
        self.margins = margins or {'top': 2*cm, 'bottom': 2*cm, 'left': 2*cm, 'right': 2*cm}
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.darkblue,
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.darkblue,
            spaceBefore=20,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            alignment=TA_JUSTIFY
        ))
        
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
    
    def create_document(self, filename: str, title: str = None, 
                       author: str = None, subject: str = None) -> SimpleDocTemplate:
        """Create a new PDF document"""
        doc = SimpleDocTemplate(
            filename,
            pagesize=self.page_size,
            topMargin=self.margins['top'],
            bottomMargin=self.margins['bottom'],
            leftMargin=self.margins['left'],
            rightMargin=self.margins['right']
        )
        
        if title:
            doc.title = title
        if author:
            doc.author = author
        if subject:
            doc.subject = subject
        
        return doc
    
    def generate_simple_report(self, filename: str, title: str, 
                              content: List[Dict[str, Any]], 
                              header_info: Dict[str, str] = None) -> str:
        """Generate a simple report PDF"""
        doc = self.create_document(filename, title=title)
        story = []
        
        # Add header info if provided
        if header_info:
            for key, value in header_info.items():
                story.append(Paragraph(f"<b>{key}:</b> {value}", self.styles['CustomNormal']))
            story.append(Spacer(1, 20))
        
        # Add title
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Add content
        for item in content:
            if item.get('type') == 'heading':
                story.append(Paragraph(item['text'], self.styles['CustomHeading']))
            elif item.get('type') == 'paragraph':
                story.append(Paragraph(item['text'], self.styles['CustomNormal']))
            elif item.get('type') == 'table':
                table = self._create_table(item['data'], item.get('headers'))
                story.append(table)
            elif item.get('type') == 'spacer':
                story.append(Spacer(1, item.get('height', 12)))
            elif item.get('type') == 'page_break':
                story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        return filename
    
    def _create_table(self, data: List[List[str]], headers: List[str] = None) -> Table:
        """Create a formatted table"""
        table_data = []
        
        if headers:
            table_data.append(headers)
        
        table_data.extend(data)
        
        table = Table(table_data)
        
        # Style the table
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey) if headers else None,
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke) if headers else None,
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold') if headers else None,
            ('FONTSIZE', (0, 0), (-1, 0), 14) if headers else None,
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12) if headers else None,
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        
        # Remove None entries
        style = [s for s in style if s is not None]
        table.setStyle(TableStyle(style))
        
        return table
    
    def generate_invoice(self, filename: str, invoice_data: Dict[str, Any]) -> str:
        """Generate an invoice PDF"""
        doc = self.create_document(filename, title="Invoice")
        story = []
        
        # Invoice header
        header_data = [
            [invoice_data.get('company_name', 'Company Name'), 'INVOICE'],
            [invoice_data.get('company_address', ''), f"Invoice #: {invoice_data.get('invoice_number', '')}"],
            ['', f"Date: {invoice_data.get('date', datetime.now().strftime('%Y-%m-%d'))}"]
        ]
        
        header_table = Table(header_data, colWidths=[4*inch, 2*inch])
        header_table.setStyle(TableStyle([
            ('FONTSIZE', (1, 0), (1, 0), 20),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 30))
        
        # Bill to section
        bill_to = invoice_data.get('bill_to', {})
        story.append(Paragraph('<b>Bill To:</b>', self.styles['CustomHeading']))
        story.append(Paragraph(bill_to.get('name', ''), self.styles['CustomNormal']))
        story.append(Paragraph(bill_to.get('address', ''), self.styles['CustomNormal']))
        story.append(Spacer(1, 20))
        
        # Items table
        items = invoice_data.get('items', [])
        if items:
            headers = ['Description', 'Quantity', 'Rate', 'Amount']
            table_data = []
            
            for item in items:
                table_data.append([
                    item.get('description', ''),
                    str(item.get('quantity', 0)),
                    f"₹{item.get('rate', 0):.2f}",
                    f"₹{item.get('amount', 0):.2f}"
                ])
            
            items_table = self._create_table(table_data, headers)
            story.append(items_table)
            story.append(Spacer(1, 20))
            
            # Total section
            total_data = [
                ['', '', 'Subtotal:', f"₹{invoice_data.get('subtotal', 0):.2f}"],
                ['', '', 'Tax:', f"₹{invoice_data.get('tax', 0):.2f}"],
                ['', '', 'Total:', f"₹{invoice_data.get('total', 0):.2f}"]
            ]
            
            total_table = Table(total_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch])
            total_table.setStyle(TableStyle([
                ('FONTNAME', (2, -1), (3, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (2, -1), (3, -1), 12),
                ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
                ('LINEABOVE', (2, -1), (3, -1), 2, colors.black)
            ]))
            
            story.append(total_table)
        
        # Footer
        if invoice_data.get('notes'):
            story.append(Spacer(1, 30))
            story.append(Paragraph('<b>Notes:</b>', self.styles['CustomHeading']))
            story.append(Paragraph(invoice_data['notes'], self.styles['CustomNormal']))
        
        doc.build(story)
        return filename
    
    def generate_student_report(self, filename: str, student_data: Dict[str, Any]) -> str:
        """Generate student report PDF"""
        doc = self.create_document(filename, title="Student Report")
        story = []
        
        # Title
        story.append(Paragraph("Student Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Student info
        info_data = [
            ['Student ID:', student_data.get('student_id', '')],
            ['Name:', student_data.get('name', '')],
            ['Email:', student_data.get('email', '')],
            ['Phone:', student_data.get('phone', '')],
            ['Room:', student_data.get('room', '')],
            ['Check-in Date:', student_data.get('checkin_date', '')]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 30))
        
        # Payment history
        if student_data.get('payments'):
            story.append(Paragraph("Payment History", self.styles['CustomHeading']))
            
            payment_headers = ['Date', 'Type', 'Amount', 'Status']
            payment_data = []
            
            for payment in student_data['payments']:
                payment_data.append([
                    payment.get('date', ''),
                    payment.get('type', ''),
                    f"₹{payment.get('amount', 0):.2f}",
                    payment.get('status', '')
                ])
            
            payment_table = self._create_table(payment_data, payment_headers)
            story.append(payment_table)
            story.append(Spacer(1, 20))
        
        # Attendance summary
        if student_data.get('attendance'):
            story.append(Paragraph("Attendance Summary", self.styles['CustomHeading']))
            
            attendance = student_data['attendance']
            attendance_data = [
                ['Total Days:', str(attendance.get('total_days', 0))],
                ['Present Days:', str(attendance.get('present_days', 0))],
                ['Absent Days:', str(attendance.get('absent_days', 0))],
                ['Attendance %:', f"{attendance.get('percentage', 0):.1f}%"]
            ]
            
            attendance_table = Table(attendance_data, colWidths=[2*inch, 1*inch])
            attendance_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(attendance_table)
        
        doc.build(story)
        return filename
    
    def add_watermark(self, filename: str, watermark_text: str, 
                     output_filename: str = None) -> str:
        """Add watermark to PDF"""
        if output_filename is None:
            path = Path(filename)
            output_filename = str(path.parent / f"{path.stem}_watermarked{path.suffix}")
        
        # Create watermark
        watermark_buffer = io.BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=self.page_size)
        c.setFont("Helvetica", 50)
        c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
        c.rotate(45)
        c.drawString(200, 100, watermark_text)
        c.save()
        watermark_buffer.seek(0)
        
        # Apply watermark to existing PDF
        watermark_pdf = PdfReader(watermark_buffer)
        existing_pdf = PdfReader(filename)
        output_pdf = PdfWriter()
        
        for page_num in range(len(existing_pdf.pages)):
            page = existing_pdf.pages[page_num]
            if len(watermark_pdf.pages) > 0:
                page.merge_page(watermark_pdf.pages[0])
            output_pdf.add_page(page)
        
        with open(output_filename, 'wb') as output_file:
            output_pdf.write(output_file)
        
        return output_filename

class PDFMerger:
    """PDF merging and splitting utilities"""
    
    @staticmethod
    def merge_pdfs(pdf_files: List[str], output_filename: str, 
                   bookmarks: List[str] = None) -> str:
        """Merge multiple PDFs into one"""
        merger = PdfWriter()
        
        for i, pdf_file in enumerate(pdf_files):
            reader = PdfReader(pdf_file)
            
            # Add bookmark if provided
            if bookmarks and i < len(bookmarks):
                start_page = len(merger.pages)
                merger.append(reader, bookmark=bookmarks[i])
            else:
                merger.append(reader)
        
        with open(output_filename, 'wb') as output_file:
            merger.write(output_file)
        
        return output_filename
    
    @staticmethod
    def split_pdf(pdf_file: str, output_dir: str = None, 
                  pages_per_file: int = 1) -> List[str]:
        """Split PDF into multiple files"""
        if output_dir is None:
            output_dir = os.path.dirname(pdf_file)
        
        os.makedirs(output_dir, exist_ok=True)
        
        reader = PdfReader(pdf_file)
        base_name = Path(pdf_file).stem
        output_files = []
        
        total_pages = len(reader.pages)
        
        for start_page in range(0, total_pages, pages_per_file):
            end_page = min(start_page + pages_per_file, total_pages)
            
            writer = PdfWriter()
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            output_filename = os.path.join(output_dir, f"{base_name}_page_{start_page+1}-{end_page}.pdf")
            
            with open(output_filename, 'wb') as output_file:
                writer.write(output_file)
            
            output_files.append(output_filename)
        
        return output_files
    
    @staticmethod
    def extract_pages(pdf_file: str, page_numbers: List[int], 
                     output_filename: str) -> str:
        """Extract specific pages from PDF"""
        reader = PdfReader(pdf_file)
        writer = PdfWriter()
        
        for page_num in page_numbers:
            if 0 <= page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
        
        with open(output_filename, 'wb') as output_file:
            writer.write(output_file)
        
        return output_filename

class PDFSigner:
    """PDF digital signature utilities"""
    
    def __init__(self, certificate_path: str = None, private_key_path: str = None):
        self.certificate_path = certificate_path
        self.private_key_path = private_key_path
    
    def add_signature_field(self, pdf_file: str, output_filename: str,
                           signature_field_name: str = "Signature",
                           position: Tuple[int, int, int, int] = (100, 100, 200, 150)) -> str:
        """Add signature field to PDF"""
        # This is a simplified implementation
        # In production, use proper digital signature libraries
        
        reader = PdfReader(pdf_file)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Add signature field annotation (simplified)
        # Note: This would need proper implementation with cryptographic signatures
        
        with open(output_filename, 'wb') as output_file:
            writer.write(output_file)
        
        return output_filename
    
    def verify_signature(self, pdf_file: str) -> Dict[str, Any]:
        """Verify PDF signature"""
        # Simplified signature verification
        # In production, use proper cryptographic verification
        
        return {
            'is_signed': False,
            'is_valid': False,
            'signer': None,
            'sign_date': None,
            'verification_details': "Signature verification not implemented"
        }

class PDFValidator:
    """PDF validation utilities"""
    
    @staticmethod
    def validate_pdf(pdf_file: str) -> Dict[str, Any]:
        """Validate PDF file"""
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'info': {}
        }
        
        try:
            # Check if file exists
            if not os.path.exists(pdf_file):
                result['is_valid'] = False
                result['errors'].append("File does not exist")
                return result
            
            # Try to read PDF
            reader = PdfReader(pdf_file)
            
            # Get basic info
            result['info'] = {
                'num_pages': len(reader.pages),
                'encrypted': reader.is_encrypted,
                'metadata': reader.metadata if hasattr(reader, 'metadata') else {}
            }
            
            # Check if pages can be accessed
            try:
                for i, page in enumerate(reader.pages):
                    # Try to access page content
                    text = page.extract_text()
                    if i == 0 and not text.strip():
                        result['warnings'].append("First page appears to have no text content")
                    
                    # Check for basic page properties
                    if not hasattr(page, 'mediaBox'):
                        result['warnings'].append(f"Page {i+1} missing media box")
                        
            except Exception as e:
                result['errors'].append(f"Error reading page content: {str(e)}")
                result['is_valid'] = False
            
            # File size check
            file_size = os.path.getsize(pdf_file)
            result['info']['file_size'] = file_size
            
            if file_size > 100 * 1024 * 1024:  # 100MB
                result['warnings'].append("File is very large (>100MB)")
            
        except Exception as e:
            result['is_valid'] = False
            result['errors'].append(f"Failed to validate PDF: {str(e)}")
        
        return result
    
    @staticmethod
    def get_pdf_info(pdf_file: str) -> Dict[str, Any]:
        """Get comprehensive PDF information"""
        info = {}
        
        try:
            reader = PdfReader(pdf_file)
            
            info.update({
                'filename': os.path.basename(pdf_file),
                'file_size': os.path.getsize(pdf_file),
                'num_pages': len(reader.pages),
                'encrypted': reader.is_encrypted,
                'metadata': dict(reader.metadata) if reader.metadata else {}
            })
            
            # Get first page dimensions
            if len(reader.pages) > 0:
                first_page = reader.pages[0]
                media_box = first_page.mediaBox
                info['page_size'] = {
                    'width': float(media_box.width),
                    'height': float(media_box.height)
                }
            
        except Exception as e:
            info['error'] = str(e)
        
        return info
    
    @staticmethod
    def is_pdf_searchable(pdf_file: str) -> bool:
        """Check if PDF contains searchable text"""
        try:
            reader = PdfReader(pdf_file)
            
            # Check first few pages for text content
            for i in range(min(3, len(reader.pages))):
                text = reader.pages[i].extract_text()
                if text.strip():
                    return True
            
            return False
        except:
            return False

class PDFTextExtractor:
    """PDF text extraction utilities"""
    
    @staticmethod
    def extract_text(pdf_file: str) -> str:
        """Extract all text from PDF"""
        try:
            reader = PdfReader(pdf_file)
            text = ""
            
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to extract text: {str(e)}")
    
    @staticmethod
    def extract_text_by_page(pdf_file: str) -> List[str]:
        """Extract text from each page separately"""
        try:
            reader = PdfReader(pdf_file)
            pages_text = []
            
            for page in reader.pages:
                pages_text.append(page.extract_text())
            
            return pages_text
        except Exception as e:
            raise ValueError(f"Failed to extract text: {str(e)}")
    
    @staticmethod
    def search_text_in_pdf(pdf_file: str, search_term: str, 
                          case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """Search for text in PDF"""
        results = []
        
        try:
            reader = PdfReader(pdf_file)
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                
                if not case_sensitive:
                    text = text.lower()
                    search_term = search_term.lower()
                
                if search_term in text:
                    # Find all occurrences in the page
                    start = 0
                    while True:
                        pos = text.find(search_term, start)
                        if pos == -1:
                            break
                        
                        results.append({
                            'page': page_num + 1,
                            'position': pos,
                            'context': text[max(0, pos-50):pos+len(search_term)+50]
                        })
                        
                        start = pos + 1
                        
        except Exception as e:
            raise ValueError(f"Failed to search PDF: {str(e)}")
        
        return results

class PDFImageExtractor:
    """PDF image extraction utilities"""
    
    @staticmethod
    def extract_images(pdf_file: str, output_dir: str = None) -> List[str]:
        """Extract images from PDF"""
        if output_dir is None:
            output_dir = os.path.dirname(pdf_file)
        
        os.makedirs(output_dir, exist_ok=True)
        
        extracted_images = []
        base_name = Path(pdf_file).stem
        
        try:
            # Use PyMuPDF for better image extraction
            doc = fitz.open(pdf_file)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    # Get image data
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        output_filename = os.path.join(
                            output_dir, 
                            f"{base_name}_page_{page_num+1}_img_{img_index+1}.png"
                        )
                        pix.save(output_filename)
                        extracted_images.append(output_filename)
                    else:  # CMYK: convert to RGB first
                        pix1 = fitz.Pixmap(fitz.csRGB, pix)
                        output_filename = os.path.join(
                            output_dir, 
                            f"{base_name}_page_{page_num+1}_img_{img_index+1}.png"
                        )
                        pix1.save(output_filename)
                        extracted_images.append(output_filename)
                        pix1 = None
                    
                    pix = None
            
            doc.close()
            
        except ImportError:
            # Fallback to PyPDF2 (limited image extraction)
            print("PyMuPDF not available, using limited image extraction")
            
        except Exception as e:
            raise ValueError(f"Failed to extract images: {str(e)}")
        
        return extracted_images
    
    @staticmethod
    def convert_pdf_to_images(pdf_file: str, output_dir: str = None,
                             dpi: int = 200, format: str = 'PNG') -> List[str]:
        """Convert PDF pages to images"""
        if output_dir is None:
            output_dir = os.path.dirname(pdf_file)
        
        os.makedirs(output_dir, exist_ok=True)
        
        image_files = []
        base_name = Path(pdf_file).stem
        
        try:
            doc = fitz.open(pdf_file)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Render page to image
                mat = fitz.Matrix(dpi/72, dpi/72)  # scaling factor
                pix = page.get_pixmap(matrix=mat)
                
                output_filename = os.path.join(
                    output_dir, 
                    f"{base_name}_page_{page_num+1}.{format.lower()}"
                )
                
                pix.save(output_filename)
                image_files.append(output_filename)
                
                pix = None
            
            doc.close()
            
        except ImportError:
            raise ValueError("PyMuPDF required for PDF to image conversion")
        except Exception as e:
            raise ValueError(f"Failed to convert PDF to images: {str(e)}")
        
        return image_files

class PDFReportGenerator:
    """Specialized report generation utilities"""
    
    def __init__(self):
        self.generator = PDFGenerator()
    
    def generate_attendance_report(self, filename: str, 
                                 attendance_data: Dict[str, Any]) -> str:
        """Generate attendance report"""
        content = [
            {'type': 'heading', 'text': 'Attendance Summary'},
            {'type': 'paragraph', 'text': f"Period: {attendance_data.get('period', 'N/A')}"},
            {'type': 'paragraph', 'text': f"Total Students: {attendance_data.get('total_students', 0)}"},
            {'type': 'spacer', 'height': 20}
        ]
        
        if attendance_data.get('student_attendance'):
            headers = ['Student ID', 'Name', 'Present Days', 'Absent Days', 'Percentage']
            table_data = []
            
            for student in attendance_data['student_attendance']:
                table_data.append([
                    student.get('student_id', ''),
                    student.get('name', ''),
                    str(student.get('present_days', 0)),
                    str(student.get('absent_days', 0)),
                    f"{student.get('percentage', 0):.1f}%"
                ])
            
            content.append({
                'type': 'table',
                'headers': headers,
                'data': table_data
            })
        
        return self.generator.generate_simple_report(
            filename, 
            "Attendance Report", 
            content,
            {
                'Generated On': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'Generated By': attendance_data.get('generated_by', 'System')
            }
        )
    
    def generate_fee_statement(self, filename: str, 
                              fee_data: Dict[str, Any]) -> str:
        """Generate fee statement"""
        content = [
            {'type': 'heading', 'text': 'Student Fee Statement'},
            {'type': 'paragraph', 'text': f"Student: {fee_data.get('student_name', 'N/A')}"},
            {'type': 'paragraph', 'text': f"Student ID: {fee_data.get('student_id', 'N/A')}"},
            {'type': 'paragraph', 'text': f"Period: {fee_data.get('period', 'N/A')}"},
            {'type': 'spacer', 'height': 20}
        ]
        
        # Fee breakdown
        if fee_data.get('fee_breakdown'):
            content.append({'type': 'heading', 'text': 'Fee Breakdown'})
            
            headers = ['Fee Type', 'Amount', 'Due Date', 'Status']
            table_data = []
            
            for fee in fee_data['fee_breakdown']:
                table_data.append([
                    fee.get('type', ''),
                    f"₹{fee.get('amount', 0):.2f}",
                    fee.get('due_date', ''),
                    fee.get('status', '')
                ])
            
            content.append({
                'type': 'table',
                'headers': headers,
                'data': table_data
            })
            
            content.append({'type': 'spacer', 'height': 20})
        
        # Payment history
        if fee_data.get('payments'):
            content.append({'type': 'heading', 'text': 'Payment History'})
            
            headers = ['Date', 'Amount', 'Method', 'Receipt No.']
            table_data = []
            
            for payment in fee_data['payments']:
                table_data.append([
                    payment.get('date', ''),
                    f"₹{payment.get('amount', 0):.2f}",
                    payment.get('method', ''),
                    payment.get('receipt_no', '')
                ])
            
            content.append({
                'type': 'table',
                'headers': headers,
                'data': table_data
            })
        
        # Summary
        total_due = fee_data.get('total_due', 0)
        total_paid = fee_data.get('total_paid', 0)
        balance = total_due - total_paid
        
        content.extend([
            {'type': 'spacer', 'height': 20},
            {'type': 'paragraph', 'text': f"<b>Total Due: ₹{total_due:.2f}</b>"},
            {'type': 'paragraph', 'text': f"<b>Total Paid: ₹{total_paid:.2f}</b>"},
            {'type': 'paragraph', 'text': f"<b>Balance: ₹{balance:.2f}</b>"}
        ])
        
        return self.generator.generate_simple_report(
            filename, 
            "Fee Statement", 
            content
        )