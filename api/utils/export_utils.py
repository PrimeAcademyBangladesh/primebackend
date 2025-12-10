"""Export utilities for CSV and PDF generation.

Provides helper functions to export data as CSV and PDF files
for students, employees, orders, and reports.
"""

import csv
import requests
from io import BytesIO, StringIO
from datetime import datetime
from decimal import Decimal
from django.http import HttpResponse
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
try:
    from reportlab.graphics.barcode import qr
except ImportError:
    qr = None


class CSVExporter:
    """Helper class for CSV exports."""
    
    @staticmethod
    def export_to_csv(filename, headers, data):
        """
        Export data to CSV format.
        
        Args:
            filename: Name of the file to download
            headers: List of column headers
            data: List of dictionaries or tuples containing row data
            
        Returns:
            HttpResponse with CSV file
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(headers)
        
        for row in data:
            if isinstance(row, dict):
                writer.writerow([row.get(header, '') for header in headers])
            else:
                writer.writerow(row)
        
        return response


class PDFExporter:
    """Helper class for PDF exports."""
    
    def __init__(self, title, pagesize=A4):
        self.title = title
        self.pagesize = pagesize
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
    
    def _add_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
        ))
    
    def create_pdf(self, content_elements):
        """
        Create a PDF document.
        
        Args:
            content_elements: List of reportlab flowables (Paragraphs, Tables, etc.)
            
        Returns:
            HttpResponse with PDF file
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.pagesize,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
            title=self.title
        )
        
        # Build PDF
        story = []
        
        # Add title
        title = Paragraph(self.title, self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Add content
        story.extend(content_elements)
        
        doc.build(story)
        
        # Prepare response
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{self.title.replace(" ", "_")}.pdf"'
        
        return response
    
    def create_table(self, headers, data, col_widths=None):
        """
        Create a formatted table.
        
        Args:
            headers: List of column headers
            data: List of tuples/lists containing row data
            col_widths: Optional list of column widths
            
        Returns:
            Table object
        """
        # Prepare table data
        table_data = [headers]
        table_data.extend(data)
        
        # Create table
        if col_widths:
            table = Table(table_data, colWidths=col_widths)
        else:
            table = Table(table_data)
        
        # Style the table
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Body styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        return table


class InvoicePDFGenerator:
    """Generate professional invoice PDFs with logo, QR code, and watermark."""
    
    def __init__(self, order):
        self.order = order
        self.pagesize = A4
        self.buffer = BytesIO()
        self.styles = getSampleStyleSheet()
        self._register_styles()
        self.logo_url = "http://45.85.250.92/assets/prime-academy-logo-full-dark.png"
    
    def _register_styles(self):
        """Register custom styles for invoice."""
        self.styles.add(ParagraphStyle(
            name="InvTitle",
            fontSize=28,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            spaceAfter=20,
            spaceBefore=10,
            textColor=colors.HexColor('#1a202c')
        ))
        
        self.styles.add(ParagraphStyle(
            name="InvSectionTitle",
            fontSize=13,
            fontName="Helvetica-Bold",
            spaceAfter=10,
            textColor=colors.HexColor('#2d3748')
        ))
        
        self.styles.add(ParagraphStyle(
            name="InvBodyText",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#4a5568')
        ))
        
        self.styles.add(ParagraphStyle(
            name='InvoiceRight',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            alignment=TA_RIGHT
        ))
    
    def get_logo(self):
        """Download and return logo image."""
        try:
            # Try to get logo from URL
            response = requests.get(self.logo_url, timeout=5)
            if response.status_code == 200:
                logo_buffer = BytesIO(response.content)
                return Image(logo_buffer, width=138, height=50)
        except Exception:
            pass
        
        # Return text placeholder if logo fails
        return None
    
    def get_qr_verification_url(self):
        """Generate verification URL for QR code."""
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        return f"{base_url}/verify-invoice/{self.order.order_number}"
    
    def generate_qr_code(self):
        """Generate QR code for invoice verification."""
        if qr is None:
            return None
        
        try:
            qr_code = qr.QrCodeWidget(self.get_qr_verification_url())
            bounds = qr_code.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            drawing = Drawing(60, 60, transform=[
                60.0 / width, 0, 0, 60.0 / height, 0, 0
            ])
            drawing.add(qr_code)
            return drawing
        except Exception:
            return None
    
    def _draw_watermark(self, canvas, doc):
        """Draw watermark on every page."""
        canvas.saveState()
        canvas.setFillColorRGB(0.85, 0.85, 0.85)
        canvas.setFont("Helvetica-Bold", 60)
        canvas.translate(300, 400)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "PRIME ACADEMY")
        canvas.restoreState()
    
    def generate(self):
        """Generate invoice PDF matching reference design."""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=self.pagesize,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        story = []
        
        # Header: Logo (left) and Invoice Number (right)
        logo = self.get_logo()
        if not logo:
            logo = Paragraph('<b>PRIME ACADEMY</b>', self.styles['InvBodyText'])
        
        header_data = [[
            logo,
            Paragraph(f'<b>Invoice #:</b> {self.order.order_number}', self.styles['InvoiceRight'])
        ]]
        
        header_table = Table(header_data, colWidths=[4*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 10))
        
        # INVOICE title
        story.append(Paragraph('<b>INVOICE</b>', 
                              ParagraphStyle(
                                  name='InvoiceTitle',
                                  fontSize=24,
                                  fontName='Helvetica-Bold',
                                  alignment=TA_CENTER
                              )))
        story.append(Spacer(1, 15*mm))
        
        # From/To Table
        from_to_data = [
            ['From', 'To'],
            [
                Paragraph('<b>Prime Academy</b><br/>Suite 5040, Lift 5<br/>Dhanmondi, Dhaka<br/>Phone: +880 1300 290492<br/>Email: info@primeacademy.org', 
                         self.styles['InvBodyText']),
                Paragraph(f'<b>{self.order.billing_name}</b><br/>{self.order.billing_email}<br/>{self.order.billing_phone}' + 
                         (f'<br/>{self.order.billing_address}' if self.order.billing_address else ''),
                         self.styles['InvBodyText'])
            ]
        ]
        
        from_to_table = Table(from_to_data, colWidths=[3.5*inch, 3.5*inch])
        from_to_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(from_to_table)
        story.append(Spacer(1, 20))
        
        # Date, Payment Method, Status
        status_color = colors.green if self.order.status == 'completed' else colors.orange
        info_text = (f'<b>Date:</b> {self.order.created_at.strftime("%d %B %Y")}<br/>'
                    f'<b>Payment Method:</b> {self.order.payment_method if self.order.payment_method else "N/A"}<br/>'
                    f'<b>Status:</b> <font color="green">{self.order.get_status_display().upper()}</font>')
        story.append(Paragraph(info_text, self.styles['InvBodyText']))
        story.append(Spacer(1, 20))
        
        # Payment Details heading
        story.append(Paragraph('<font color="#003366"><b>Payment Details</b></font>', 
                              ParagraphStyle(
                                  name='PaymentHeading',
                                  fontSize=14,
                                  fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#003366')
                              )))
        story.append(Spacer(1, 10))
        
        # Course/Batch/Amount Table
        payment_data = [['Course', 'Batch', 'Amount']]
        
        for item in self.order.items.all():
            # Get batch info from enrollment
            batch_name = 'N/A'
            try:
                from api.models.models_order import Enrollment
                enrollment = Enrollment.objects.filter(
                    user=self.order.user,
                    course=item.course
                ).first()
                if enrollment and enrollment.batch:
                    batch_name = enrollment.batch.get_display_name()
            except Exception as e:
                # Fallback: try to get from order item if it has batch info
                pass
            
            payment_data.append([
                item.course.title,
                batch_name,
                f'{item.price:,.2f}/-'
            ])
        
        payment_table = Table(payment_data, colWidths=[3.5*inch, 2*inch, 1.5*inch])
        payment_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(payment_table)
        story.append(Spacer(1, 30))
        
        # QR Code and verification info
        qr_code = self.generate_qr_code()
        if qr_code:
            qr_data = [
                [qr_code, Paragraph('<b>Verify this invoice</b><br/>Scan QR code to verify authenticity<br/>'
                                   f'or visit: {self.get_qr_verification_url()}', 
                                   self.styles['InvBodyText'])]
            ]
            qr_table = Table(qr_data, colWidths=[70, 5*inch])
            qr_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(qr_table)
            story.append(Spacer(1, 20))
        
        # Footer with thank you message
        story.append(Spacer(1, 10))
        footer_text = ('<b>Thank you for choosing Prime Academy!</b><br/><br/>'
                      'For any queries or support, please contact us:<br/>'
                      'Email: support@primeacademy.com<br/>'
                      'Phone: +880 1234-567890')
        story.append(Paragraph(footer_text, self.styles['InvBodyText']))
        
        story.append(Spacer(1, 20))
        
        # Automated invoice notice
        automated_notice = ('<para align="center"><i>This is a computer-generated invoice and does not require a physical signature.</i></para>')
        story.append(Paragraph(automated_notice, 
                              ParagraphStyle(
                                  name='AutomatedNotice',
                                  fontSize=9,
                                  textColor=colors.HexColor('#666666'),
                                  alignment=TA_CENTER
                              )))
        
        # Build PDF with watermark
        doc.build(story, onFirstPage=self._draw_watermark, onLaterPages=self._draw_watermark)
        self.buffer.seek(0)
        
        # Prepare response
        filename = f'Invoice_{self.order.order_number}.pdf'
        response = HttpResponse(self.buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
