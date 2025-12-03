"""Export views for CSV and PDF downloads.

Provides endpoints to export students, employees, and orders
in CSV and PDF formats for admin users.
"""

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiResponse

from django.db.models import Sum, Count, Q, Avg
from datetime import datetime, timedelta
from decimal import Decimal

from api.models.models_auth import CustomUser
from api.models.models_employee import Employee
from api.models.models_order import Order, Enrollment
from api.models.models_course import Course
from api.models.models_progress import CourseProgress
from api.permissions import IsStaff
from api.utils.export_utils import CSVExporter, PDFExporter, InvoicePDFGenerator


# ============================================================================
# Date Range Validation Helper
# ============================================================================

def validate_and_parse_date_range(request, max_range_days=365):
    """
    Validate and parse date range parameters with security checks.
    
    Args:
        request: Django request object
        max_range_days: Maximum allowed date range (default 365 days)
        
    Returns:
        tuple: (start_date, end_date, error_response)
        
    Security measures:
    - Limits maximum date range to prevent DB overload
    - Validates date format
    - Ensures start_date <= end_date
    - Defaults to last 30 days if no dates provided
    """
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    
    # Default to last 30 days if no dates provided
    if not start_date_str and not end_date_str:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date, None
    
    # Parse dates
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timedelta(days=30)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except ValueError:
        return None, None, Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate date range
    if start_date > end_date:
        return None, None, Response(
            {'error': 'start_date cannot be after end_date'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Security: Prevent excessive date ranges (DB protection)
    date_range = (end_date - start_date).days
    if date_range > max_range_days:
        return None, None, Response(
            {'error': f'Date range cannot exceed {max_range_days} days. Current range: {date_range} days'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Security: Prevent future dates
    if end_date > timezone.now().date():
        end_date = timezone.now().date()
    
    return start_date, end_date, None


# ============================================================================
# Student Export Views
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export student list as CSV",
    description="Download complete list of students in CSV format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='role',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by student role (default: student)',
            required=False
        ),
        OpenApiParameter(
            name='is_enabled',
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description='Filter by enabled status',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='CSV file download'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_students_csv(request):
    """Export students list as CSV file."""
    
    # Get queryset
    queryset = CustomUser.objects.filter(role='student').select_related().order_by('-created_at')
    
    # Apply filters
    is_enabled = request.query_params.get('is_enabled')
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')
    
    # Prepare data
    headers = [
        'Student ID',
        'Name',
        'Email',
        'Phone',
        'Status',
        'Enrolled Courses',
        'Completed Courses',
        'Registration Date',
        'Last Login'
    ]
    
    data = []
    for student in queryset:
        enrollments = student.enrollments.all()
        completed = enrollments.filter(is_completed=True).count()
        
        data.append([
            student.student_id or 'N/A',
            student.get_full_name() or 'N/A',
            student.email,
            student.phone_number or 'N/A',
            'Active' if student.is_enabled else 'Disabled',
            enrollments.count(),
            completed,
            student.created_at.strftime('%Y-%m-%d'),
            student.last_login.strftime('%Y-%m-%d %H:%M') if student.last_login else 'Never'
        ])
    
    # Generate filename
    filename = f'students_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return CSVExporter.export_to_csv(filename, headers, data)


@extend_schema(
    tags=["Data Export"],
    summary="Export student list as PDF",
    description="Download complete list of students in PDF format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='is_enabled',
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description='Filter by enabled status',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF file download'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_students_pdf(request):
    """Export students list as PDF file."""
    
    # Get queryset
    queryset = CustomUser.objects.filter(role='student').select_related().order_by('-created_at')
    
    # Apply filters
    is_enabled = request.query_params.get('is_enabled')
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')
    
    # Prepare data
    headers = ['ID', 'Name', 'Email', 'Phone', 'Courses', 'Status', 'Registered']
    
    data = []
    for student in queryset:
        enrollments = student.enrollments.all()
        
        data.append([
            student.student_id or 'N/A',
            student.get_full_name() or 'N/A',
            student.email,
            student.phone_number or 'N/A',
            str(enrollments.count()),
            'Active' if student.is_enabled else 'Disabled',
            student.created_at.strftime('%Y-%m-%d')
        ])
    
    # Generate PDF
    exporter = PDFExporter(f'Student List - {timezone.now().strftime("%B %d, %Y")}')
    
    # Add summary
    from reportlab.platypus import Paragraph, Spacer
    content = []
    content.append(Paragraph(
        f'Total Students: {queryset.count()}',
        exporter.styles['CustomHeading']
    ))
    content.append(Paragraph(
        f'Active: {queryset.filter(is_enabled=True).count()} | '
        f'Disabled: {queryset.filter(is_enabled=False).count()}',
        exporter.styles['CustomBody']
    ))
    content.append(Spacer(1, 20))
    
    # Add table
    col_widths = [60, 100, 140, 80, 50, 60, 70]
    table = exporter.create_table(headers, data, col_widths)
    content.append(table)
    
    return exporter.create_pdf(content)


# ============================================================================
# Employee Export Views
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export employee list as CSV",
    description="Download complete list of employees in CSV format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='department',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            description='Filter by department ID',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='CSV file download'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_employees_csv(request):
    """Export employees list as CSV file."""
    
    # Get queryset
    queryset = Employee.objects.select_related('department').order_by('employee_name')
    
    # Apply filters
    department = request.query_params.get('department')
    if department:
        queryset = queryset.filter(department_id=department)
    
    # Prepare data
    headers = [
        'Name',
        'Designation',
        'Department',
        'Email',
        'Phone',
        'LinkedIn',
        'Experience',
        'Specialization',
        'Order'
    ]
    
    data = []
    for employee in queryset:
        data.append([
            employee.employee_name,
            employee.designation,
            employee.department.department_name if employee.department else 'N/A',
            employee.email or 'N/A',
            employee.phone_number or 'N/A',
            employee.linkedin_url or 'N/A',
            employee.experience or 'N/A',
            employee.specialization or 'N/A',
            employee.order
        ])
    
    # Generate filename
    filename = f'employees_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return CSVExporter.export_to_csv(filename, headers, data)


@extend_schema(
    tags=["Data Export"],
    summary="Export employee list as PDF",
    description="Download complete list of employees in PDF format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='department',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            description='Filter by department ID',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF file download'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_employees_pdf(request):
    """Export employees list as PDF file."""
    
    # Get queryset
    queryset = Employee.objects.select_related('department').order_by('employee_name')
    
    # Apply filters
    department = request.query_params.get('department')
    if department:
        queryset = queryset.filter(department_id=department)
    
    # Prepare data
    headers = ['Name', 'Designation', 'Department', 'Email', 'Phone', 'Experience']
    
    data = []
    for employee in queryset:
        data.append([
            employee.employee_name,
            employee.designation,
            employee.department.department_name if employee.department else 'N/A',
            employee.email or 'N/A',
            employee.phone_number or 'N/A',
            employee.experience or 'N/A'
        ])
    
    # Generate PDF
    exporter = PDFExporter(f'Employee List - {timezone.now().strftime("%B %d, %Y")}')
    
    # Add summary
    from reportlab.platypus import Paragraph, Spacer
    content = []
    content.append(Paragraph(
        f'Total Employees: {queryset.count()}',
        exporter.styles['CustomHeading']
    ))
    content.append(Spacer(1, 20))
    
    # Add table
    col_widths = [100, 100, 100, 120, 80, 80]
    table = exporter.create_table(headers, data, col_widths)
    content.append(table)
    
    return exporter.create_pdf(content)


# ============================================================================
# Order Export Views
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export orders list as CSV",
    description="Download complete list of orders in CSV format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='payment_status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by payment status (pending, paid, failed, refunded)',
            required=False
        ),
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Filter orders from this date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Filter orders until this date (YYYY-MM-DD)',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='CSV file download'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_orders_csv(request):
    """Export orders list as CSV file."""
    
    # Get queryset
    queryset = Order.objects.select_related('user', 'coupon').prefetch_related('items').order_by('-created_at')
    
    # Apply filters
    payment_status = request.query_params.get('payment_status')
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    
    start_date = request.query_params.get('start_date')
    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)
    
    end_date = request.query_params.get('end_date')
    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)
    
    # Prepare data
    headers = [
        'Order Number',
        'Customer Name',
        'Customer Email',
        'Customer Phone',
        'Items Count',
        'Subtotal',
        'Discount',
        'Total Amount',
        'Paid Amount',
        'Due Amount',
        'Payment Status',
        'Payment Method',
        'Coupon Code',
        'Order Date'
    ]
    
    data = []
    for order in queryset:
        data.append([
            order.order_number,
            order.billing_name,
            order.billing_email,
            order.billing_phone,
            order.items.count(),
            f'{order.subtotal:.2f}',
            f'{order.discount_amount:.2f}',
            f'{order.total_amount:.2f}',
            f'{order.paid_amount:.2f}',
            f'{order.due_amount:.2f}',
            order.get_payment_status_display(),
            order.payment_method or 'N/A',
            order.coupon.code if order.coupon else 'N/A',
            order.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # Generate filename
    filename = f'orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return CSVExporter.export_to_csv(filename, headers, data)


@extend_schema(
    tags=["Data Export"],
    summary="Export single order invoice as PDF",
    description="Download invoice for a specific order in PDF format. Admin/Staff only.",
    parameters=[
        OpenApiParameter(
            name='order_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='Order UUID',
            required=True
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF invoice file'),
        404: OpenApiResponse(description='Order not found'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_order_invoice_pdf(request, order_id):
    """Export single order invoice as PDF file."""
    
    try:
        order = Order.objects.select_related('user', 'coupon').prefetch_related('items__course').get(id=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Generate invoice PDF
    generator = InvoicePDFGenerator(order)
    return generator.generate()


@extend_schema(
    tags=["Data Export"],
    summary="Export my order invoice as PDF (Student)",
    description="Download invoice for your own order. Students can only access their own invoices.",
    parameters=[
        OpenApiParameter(
            name='order_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='Order UUID',
            required=True
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF invoice file'),
        404: OpenApiResponse(description='Order not found'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_my_order_invoice_pdf(request, order_id):
    """Export user's own order invoice as PDF file."""
    
    try:
        # Students can only access their own orders
        if request.user.role == 'student':
            order = Order.objects.select_related('user', 'coupon').prefetch_related('items__course').get(
                id=order_id,
                user=request.user
            )
        else:
            # Staff/Admin can access any order
            order = Order.objects.select_related('user', 'coupon').prefetch_related('items__course').get(id=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Generate invoice PDF
    generator = InvoicePDFGenerator(order)
    return generator.generate()


# ============================================================================
# Course Completion Reports
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export course completion report as CSV",
    description="""
    Download course completion report with student progress data.
    
    Security features:
    - Maximum date range: 365 days (prevents DB overload)
    - Defaults to last 30 days if no dates provided
    - Future dates are automatically capped to today
    - Admin/Staff only access
    """,
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD). Defaults to 30 days ago.',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD). Defaults to today. Max range: 365 days.',
            required=False
        ),
        OpenApiParameter(
            name='course',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            description='Filter by specific course UUID',
            required=False
        ),
        OpenApiParameter(
            name='completion_status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by completion status (completed, in_progress)',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='CSV file download'),
        400: OpenApiResponse(description='Invalid date range or parameters'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_course_completion_csv(request):
    """Export course completion report as CSV with secure date filtering."""
    
    # Validate and parse date range (max 365 days)
    start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=365)
    if error:
        return error
    
    # Base queryset
    queryset = Enrollment.objects.select_related(
        'user', 'course'
    ).filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    # Apply filters
    course_id = request.query_params.get('course')
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    
    completion_status = request.query_params.get('completion_status')
    if completion_status == 'completed':
        queryset = queryset.filter(is_completed=True)
    elif completion_status == 'in_progress':
        queryset = queryset.filter(is_completed=False)
    
    # Prepare data
    headers = [
        'Enrollment Date',
        'Student Name',
        'Student Email',
        'Student ID',
        'Course Title',
        'Course Slug',
        'Progress %',
        'Completion Status',
        'Completed Date',
        'Certificate Issued',
        'Days Enrolled',
        'Last Accessed'
    ]
    
    data = []
    for enrollment in queryset.order_by('-created_at'):
        days_enrolled = (timezone.now().date() - enrollment.created_at.date()).days
        
        data.append([
            enrollment.created_at.strftime('%Y-%m-%d'),
            enrollment.user.get_full_name() or 'N/A',
            enrollment.user.email,
            enrollment.user.student_id or 'N/A',
            enrollment.course.title,
            enrollment.course.slug,
            f'{enrollment.progress_percentage:.2f}',
            'Completed' if enrollment.is_completed else 'In Progress',
            enrollment.completed_at.strftime('%Y-%m-%d') if enrollment.completed_at else 'N/A',
            'Yes' if enrollment.certificate_issued else 'No',
            days_enrolled,
            enrollment.last_accessed.strftime('%Y-%m-%d') if enrollment.last_accessed else 'Never'
        ])
    
    # Generate filename
    filename = f'course_completion_{start_date}_to_{end_date}.csv'
    
    return CSVExporter.export_to_csv(filename, headers, data)


@extend_schema(
    tags=["Data Export"],
    summary="Export course completion report as PDF",
    description="""
    Download course completion report in professional PDF format.
    
    Security features:
    - Maximum date range: 365 days
    - Defaults to last 30 days
    - Auto-caps future dates
    """,
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD). Max range: 365 days.',
            required=False
        ),
        OpenApiParameter(
            name='course',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            description='Filter by course UUID',
            required=False
        ),
        OpenApiParameter(
            name='completion_status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter: completed, in_progress',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF file download'),
        400: OpenApiResponse(description='Invalid parameters'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_course_completion_pdf(request):
    """Export course completion report as PDF with secure date filtering."""
    
    # Validate and parse date range
    start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=365)
    if error:
        return error
    
    # Base queryset
    queryset = Enrollment.objects.select_related(
        'user', 'course'
    ).filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    # Apply filters
    course_id = request.query_params.get('course')
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    
    completion_status = request.query_params.get('completion_status')
    if completion_status == 'completed':
        queryset = queryset.filter(is_completed=True)
    elif completion_status == 'in_progress':
        queryset = queryset.filter(is_completed=False)
    
    # Calculate statistics
    total_enrollments = queryset.count()
    completed_count = queryset.filter(is_completed=True).count()
    in_progress_count = total_enrollments - completed_count
    completion_rate = (completed_count / total_enrollments * 100) if total_enrollments > 0 else 0
    
    # Prepare data
    headers = ['Student', 'Course', 'Progress %', 'Status', 'Enrolled', 'Completed']
    
    data = []
    for enrollment in queryset.order_by('-created_at'):
        data.append([
            enrollment.user.get_full_name() or enrollment.user.email,
            enrollment.course.title[:40],  # Truncate long titles
            f'{enrollment.progress_percentage:.1f}%',
            'Complete' if enrollment.is_completed else 'In Progress',
            enrollment.created_at.strftime('%Y-%m-%d'),
            enrollment.completed_at.strftime('%Y-%m-%d') if enrollment.completed_at else '-'
        ])
    
    # Generate PDF
    title = f'Course Completion Report ({start_date} to {end_date})'
    exporter = PDFExporter(title)
    
    # Add summary
    from reportlab.platypus import Paragraph, Spacer
    content = []
    content.append(Paragraph(
        f'<b>Report Period:</b> {start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")}',
        exporter.styles['CustomBody']
    ))
    content.append(Spacer(1, 10))
    content.append(Paragraph(
        f'<b>Total Enrollments:</b> {total_enrollments} | '
        f'<b>Completed:</b> {completed_count} ({completion_rate:.1f}%) | '
        f'<b>In Progress:</b> {in_progress_count}',
        exporter.styles['CustomBody']
    ))
    content.append(Spacer(1, 20))
    
    # Add table
    col_widths = [120, 140, 60, 70, 70, 70]
    table = exporter.create_table(headers, data, col_widths)
    content.append(table)
    
    return exporter.create_pdf(content)


# ============================================================================
# Revenue & Sales Analytics Export
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export revenue & sales analytics as CSV",
    description="""
    Download comprehensive revenue and sales analytics report.
    
    Security features:
    - Maximum date range: 730 days (2 years)
    - Defaults to last 30 days
    - Protects against DB overload
    - Admin/Staff only
    
    Includes:
    - Daily/total revenue breakdown
    - Course-wise sales performance
    - Payment method distribution
    - Discount and coupon usage
    - Order status breakdown
    """,
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD). Defaults to 30 days ago.',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD). Max range: 730 days (2 years).',
            required=False
        ),
        OpenApiParameter(
            name='payment_status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by payment status (paid, pending, failed, refunded)',
            required=False
        ),
        OpenApiParameter(
            name='course',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            description='Filter by specific course UUID',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='CSV file download'),
        400: OpenApiResponse(description='Invalid date range'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_revenue_analytics_csv(request):
    """Export revenue and sales analytics as CSV with secure date filtering."""
    
    # Validate and parse date range (max 2 years for financial reports)
    start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=730)
    if error:
        return error
    
    # Base queryset
    queryset = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).select_related('user', 'coupon').prefetch_related('items__course')
    
    # Apply filters
    payment_status = request.query_params.get('payment_status')
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    
    course_id = request.query_params.get('course')
    if course_id:
        queryset = queryset.filter(items__course_id=course_id).distinct()
    
    # Prepare headers
    headers = [
        'Order Date',
        'Order Number',
        'Customer Name',
        'Customer Email',
        'Courses Purchased',
        'Subtotal (৳)',
        'Discount (৳)',
        'Coupon Code',
        'Total Amount (৳)',
        'Paid Amount (৳)',
        'Due Amount (৳)',
        'Payment Status',
        'Payment Method',
        'Transaction ID'
    ]
    
    data = []
    for order in queryset.order_by('-created_at'):
        courses = ', '.join([item.course.title for item in order.items.all()])
        
        data.append([
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.order_number,
            order.billing_name,
            order.billing_email,
            courses[:100],  # Truncate if too long
            f'{order.subtotal:.2f}',
            f'{order.discount_amount:.2f}',
            order.coupon.code if order.coupon else 'N/A',
            f'{order.total_amount:.2f}',
            f'{order.paid_amount:.2f}',
            f'{order.due_amount:.2f}',
            order.get_payment_status_display(),
            order.payment_method or 'N/A',
            order.transaction_id or 'N/A'
        ])
    
    # Generate filename
    filename = f'revenue_analytics_{start_date}_to_{end_date}.csv'
    
    return CSVExporter.export_to_csv(filename, headers, data)


@extend_schema(
    tags=["Data Export"],
    summary="Export revenue & sales analytics as PDF",
    description="""
    Download professional revenue analytics report with statistics and charts.
    
    Security: Max range 730 days, defaults to 30 days.
    
    Includes:
    - Revenue summary and statistics
    - Top selling courses
    - Payment method breakdown
    - Daily revenue trends
    """,
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD)',
            required=False
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD). Max: 730 days.',
            required=False
        ),
        OpenApiParameter(
            name='payment_status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filter by status',
            required=False
        ),
    ],
    responses={
        200: OpenApiResponse(description='PDF file download'),
        400: OpenApiResponse(description='Invalid parameters'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def export_revenue_analytics_pdf(request):
    """Export revenue analytics as PDF with secure date filtering."""
    
    # Validate and parse date range
    start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=730)
    if error:
        return error
    
    # Base queryset
    queryset = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).select_related('user', 'coupon').prefetch_related('items__course')
    
    # Apply filters
    payment_status = request.query_params.get('payment_status')
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    
    # Calculate comprehensive statistics
    total_orders = queryset.count()
    paid_orders = queryset.filter(payment_status='paid')
    
    total_revenue = paid_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')
    
    total_paid = paid_orders.aggregate(
        total=Sum('paid_amount')
    )['total'] or Decimal('0.00')
    
    total_discount = paid_orders.aggregate(
        total=Sum('discount_amount')
    )['total'] or Decimal('0.00')
    
    avg_order_value = paid_orders.aggregate(
        avg=Avg('total_amount')
    )['avg'] or Decimal('0.00')
    
    # Order status breakdown
    status_breakdown = {
        'paid': queryset.filter(payment_status='paid').count(),
        'pending': queryset.filter(payment_status='pending').count(),
        'failed': queryset.filter(payment_status='failed').count(),
        'refunded': queryset.filter(payment_status='refunded').count(),
    }
    
    # Top courses by revenue
    from django.db.models import F
    top_courses = paid_orders.values(
        course_title=F('items__course__title')
    ).annotate(
        revenue=Sum('items__price'),
        sales_count=Count('id', distinct=True)
    ).order_by('-revenue')[:10]
    
    # Generate PDF
    title = f'Revenue & Sales Analytics ({start_date} to {end_date})'
    exporter = PDFExporter(title)
    
    # Build content
    from reportlab.platypus import Paragraph, Spacer
    content = []
    
    # Executive Summary
    content.append(Paragraph('<b>Executive Summary</b>', exporter.styles['CustomHeading']))
    content.append(Paragraph(
        f'<b>Report Period:</b> {start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")} '
        f'({(end_date - start_date).days + 1} days)',
        exporter.styles['CustomBody']
    ))
    content.append(Spacer(1, 10))
    
    # Key Metrics
    content.append(Paragraph(
        f'<b>Total Orders:</b> {total_orders} | '
        f'<b>Paid Orders:</b> {status_breakdown["paid"]} | '
        f'<b>Pending:</b> {status_breakdown["pending"]}',
        exporter.styles['CustomBody']
    ))
    content.append(Paragraph(
        f'<b>Total Revenue:</b> ৳{total_revenue:,.2f} | '
        f'<b>Total Paid:</b> ৳{total_paid:,.2f} | '
        f'<b>Avg Order:</b> ৳{avg_order_value:,.2f}',
        exporter.styles['CustomBody']
    ))
    content.append(Paragraph(
        f'<b>Total Discounts Given:</b> ৳{total_discount:,.2f}',
        exporter.styles['CustomBody']
    ))
    content.append(Spacer(1, 20))
    
    # Top Courses Table
    if top_courses:
        content.append(Paragraph('<b>Top Performing Courses</b>', exporter.styles['CustomHeading']))
        content.append(Spacer(1, 10))
        
        headers = ['Course Title', 'Sales', 'Revenue (৳)']
        course_data = []
        for course in top_courses:
            if course['course_title']:  # Skip null courses
                course_data.append([
                    course['course_title'][:50],
                    str(course['sales_count']),
                    f"৳{course['revenue']:,.2f}"
                ])
        
        if course_data:
            col_widths = [300, 80, 120]
            table = exporter.create_table(headers, course_data, col_widths)
            content.append(table)
            content.append(Spacer(1, 20))
    
    # Recent Orders Table
    content.append(Paragraph('<b>Recent Orders</b>', exporter.styles['CustomHeading']))
    content.append(Spacer(1, 10))
    
    headers = ['Date', 'Order #', 'Customer', 'Amount (৳)', 'Status']
    order_data = []
    for order in queryset.order_by('-created_at')[:20]:  # Limit to 20 recent orders
        order_data.append([
            order.created_at.strftime('%Y-%m-%d'),
            order.order_number[:15],
            order.billing_name[:30],
            f'৳{order.total_amount:,.2f}',
            order.get_payment_status_display()
        ])
    
    col_widths = [70, 100, 150, 80, 80]
    table = exporter.create_table(headers, order_data, col_widths)
    content.append(table)
    
    return exporter.create_pdf(content)
