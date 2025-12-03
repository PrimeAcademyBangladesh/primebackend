"""Export utilities for CSV and PDF generation.

Provides helper functions to export data as CSV and PDF files
for students, employees, orders, and reports.
"""

import csv
from io import BytesIO, StringIO
from datetime import datetime
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


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
    """Generate professional invoice PDFs."""
    
    def __init__(self, order):
        self.order = order
        self.pagesize = letter
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
    
    def _add_custom_styles(self):
        """Add custom styles for invoice."""
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='InvoiceHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='InvoiceBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
        ))
        
        self.styles.add(ParagraphStyle(
            name='InvoiceRight',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            alignment=TA_RIGHT
        ))
    
    def generate(self):
        """Generate invoice PDF."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.pagesize,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=30,
        )
        
        story = []
        
        # Invoice header
        story.append(Paragraph('INVOICE', self.styles['InvoiceTitle']))
        story.append(Spacer(1, 20))
        
        # Company info and invoice details
        data = [
            ['Prime Academy', f'Invoice #: {self.order.order_number}'],
            ['Learning Management System', f'Date: {self.order.created_at.strftime("%B %d, %Y")}'],
            ['', f'Status: {self.order.get_payment_status_display()}'],
        ]
        
        info_table = Table(data, colWidths=[3*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Bill to section
        story.append(Paragraph('Bill To:', self.styles['InvoiceHeading']))
        story.append(Paragraph(f'{self.order.billing_name}', self.styles['InvoiceBody']))
        story.append(Paragraph(f'{self.order.billing_email}', self.styles['InvoiceBody']))
        story.append(Paragraph(f'{self.order.billing_phone}', self.styles['InvoiceBody']))
        if self.order.billing_address:
            story.append(Paragraph(f'{self.order.billing_address}', self.styles['InvoiceBody']))
        story.append(Spacer(1, 20))
        
        # Order items table
        story.append(Paragraph('Order Details:', self.styles['InvoiceHeading']))
        story.append(Spacer(1, 10))
        
        # Table headers
        items_data = [['Course', 'Price', 'Qty', 'Total']]
        
        # Add order items
        for item in self.order.items.all():
            items_data.append([
                item.course.title,
                f'৳{item.price:,.2f}',
                '1',
                f'৳{item.price:,.2f}'
            ])
        
        items_table = Table(items_data, colWidths=[3.5*inch, 1*inch, 0.5*inch, 1*inch])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            
            # Body
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        # Totals section
        totals_data = [
            ['Subtotal:', f'৳{self.order.subtotal:,.2f}'],
        ]
        
        if self.order.discount_amount > 0:
            totals_data.append(['Discount:', f'-৳{self.order.discount_amount:,.2f}'])
            if self.order.coupon:
                totals_data.append(['Coupon Code:', self.order.coupon.code])
        
        totals_data.append(['Total:', f'৳{self.order.total_amount:,.2f}'])
        totals_data.append(['Paid:', f'৳{self.order.paid_amount:,.2f}'])
        
        if self.order.due_amount > 0:
            totals_data.append(['Due:', f'৳{self.order.due_amount:,.2f}'])
        
        totals_table = Table(totals_data, colWidths=[4.5*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 30))
        
        # Footer
        story.append(Paragraph('Thank you for your purchase!', self.styles['InvoiceBody']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            'For any queries, please contact us at support@primeacademy.com',
            self.styles['InvoiceBody']
        ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        # Prepare response
        filename = f'Invoice_{self.order.order_number}.pdf'
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
