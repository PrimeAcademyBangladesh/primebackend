"""Export views for CSV and PDF downloads."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Sum
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from api.models.models_employee import Employee
from api.models.models_order import Enrollment, Order
from api.permissions import IsAdmin
from api.utils.export_utils import CSVExporter, PDFExporter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors

from api.models.models_auth import CustomUser
from reportlab.platypus import Paragraph, Spacer
from api.utils.date_utils import uk_report_title

# ============================================================================
# Date Range Validation
# ============================================================================

def validate_and_parse_date_range(request, max_range_days=365):
    """Validate and parse date range with security checks."""
    start_date_str = request.query_params.get("start_date")
    end_date_str = request.query_params.get("end_date")

    # Get today's date properly
    today = timezone.now().date()

    # Default to last 30 days
    if not start_date_str and not end_date_str:
        default_start = today - timedelta(days=30)
        return default_start, today, None

    # Parse dates
    try:
        start_date = (
            datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if start_date_str
            else today - timedelta(days=30)
        )
        end_date = (
            datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if end_date_str
            else today
        )
    except ValueError:
        return None, None, Response(
            {"error": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate order
    if start_date > end_date:
        return None, None, Response(
            {"error": "start_date cannot be after end_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Prevent excessive ranges
    date_range = (end_date - start_date).days
    if date_range > max_range_days:
        return None, None, Response(
            {"error": f"Date range cannot exceed {max_range_days} days. Current: {date_range}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Cap future dates
    if end_date > today:
        end_date = today

    return start_date, end_date, None


# ============================================================================
# Student Exports
# ============================================================================

@extend_schema(
    tags=["Data Export"],
    summary="Export students as CSV",
    parameters=[
        OpenApiParameter("is_enabled", OpenApiTypes.BOOL, OpenApiParameter.QUERY),
    ],
    responses={200: OpenApiResponse(description="CSV file")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def export_students_csv(request):
    """Export students list as CSV."""
    queryset = (
        CustomUser.objects
        .filter(role="student")
        .prefetch_related("enrollments")
        .order_by("-date_joined")
    )

    is_enabled = request.query_params.get("is_enabled")
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled.lower() == "true")

    headers = [
        "Student ID",
        "Name",
        "Email",
        "Phone",
        "Status",
        "Enrolled Courses",
        "Completed Courses",
        "Registration Date",
        "Last Login",
    ]

    data = []
    for student in queryset:
        enrollments = student.enrollments.all()
        completed_count = enrollments.filter(progress_percentage=100).count()

        data.append([
            student.student_id or "N/A",
            student.get_full_name or "N/A",
            student.email,
            student.phone or "N/A",
            "Active" if student.is_enabled else "Disabled",
            enrollments.count(),
            completed_count,
            student.date_joined.strftime("%Y-%m-%d"),
            student.last_login.strftime("%Y-%m-%d %H:%M") if student.last_login else "Never",
        ])

    filename = f"students_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return CSVExporter.export_to_csv(filename, headers, data)



@extend_schema(
    tags=["Data Export"],
    summary="Export students as PDF",
    parameters=[
        OpenApiParameter("is_enabled", OpenApiTypes.BOOL, OpenApiParameter.QUERY),
        OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
        OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
    ],
    responses={200: OpenApiResponse(description="PDF file")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def export_students_pdf(request):
    """Export students list as PDF (Landscape, branded, UK date style)."""

    # =========================
    # QUERYSET
    # =========================
    queryset = (
        CustomUser.objects
        .filter(role="student")
        .prefetch_related("enrollments")
        .order_by("-date_joined")
    )

    is_enabled = request.query_params.get("is_enabled")
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled.lower() == "true")

    # =========================
    # DATE RANGE (OPTIONAL)
    # =========================
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    start_date = (
        datetime.strptime(start_date, "%Y-%m-%d").date()
        if start_date else None
    )
    end_date = (
        datetime.strptime(end_date, "%Y-%m-%d").date()
        if end_date else None
    )

    # =========================
    # UK STYLE TITLE
    # =========================
    title = uk_report_title(
        base_title="Student List",
        start_date=start_date,
        end_date=end_date,
    )

    exporter = PDFExporter(
        title=title,
        pagesize=landscape(A4),
    )

    # =========================
    # TABLE DATA
    # =========================
    headers = [
        "ID",
        "Name",
        "Email",
        "Phone",
        "Courses",
        "Status",
        "Registered",
    ]

    data = [
        [
            student.student_id or "N/A",
            student.get_full_name or "N/A",
            student.email,
            student.phone or "N/A",
            student.enrollments.count(),
            "Active" if student.is_enabled else "Disabled",
            student.date_joined.strftime("%d %B %Y"),
        ]
        for student in queryset
    ]

    # =========================
    # CONTENT
    # =========================
    content = []

    content.append(
        Paragraph(
            f"<b>Total Students:</b> {queryset.count()}<br/>"
            f"Active: <b>{queryset.filter(is_enabled=True).count()}</b> | "
            f"Disabled: <b>{queryset.filter(is_enabled=False).count()}</b>",
            exporter.styles["CustomBody"],
        )
    )

    content.append(Spacer(1, 14))

    table = exporter.create_table(
        headers=headers,
        data=data,
        col_widths=[70, 140, 180, 110, 80, 90, 100],
    )

    content.append(table)

    return exporter.create_pdf(content)




#
# # ============================================================================
# # Employee Exports
# # ============================================================================
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export employees as CSV",
#     parameters=[
#         OpenApiParameter("department", OpenApiTypes.UUID, OpenApiParameter.QUERY),
#     ],
#     responses={200: OpenApiResponse(description="CSV file")},
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_employees_csv(request):
#     """Export employees list as CSV."""
#     queryset = Employee.objects.select_related("department").order_by("employee_name")
#
#     department = request.query_params.get("department")
#     if department:
#         queryset = queryset.filter(department_id=department)
#
#     headers = ["Name", "Designation", "Department", "Email", "Phone", "LinkedIn", "Experience", "Specialization", "Order"]
#     data = []
#     for employee in queryset:
#         data.append([
#             employee.employee_name,
#             employee.designation,
#             employee.department.department_name if employee.department else "N/A",
#             employee.email or "N/A",
#             employee.phone_number or "N/A",
#             employee.linkedin_url or "N/A",
#             employee.experience or "N/A",
#             employee.specialization or "N/A",
#             employee.order,
#         ])
#
#     filename = f'employees_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
#     return CSVExporter.export_to_csv(filename, headers, data)
#
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export employees as PDF",
#     parameters=[
#         OpenApiParameter("department", OpenApiTypes.UUID, OpenApiParameter.QUERY),
#     ],
#     responses={200: OpenApiResponse(description="PDF file")},
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_employees_pdf(request):
#     """Export employees list as PDF."""
#     queryset = Employee.objects.select_related("department").order_by("employee_name")
#
#     department = request.query_params.get("department")
#     if department:
#         queryset = queryset.filter(department_id=department)
#
#     headers = ["Name", "Designation", "Department", "Email", "Phone", "Experience"]
#     data = []
#     for employee in queryset:
#         data.append([
#             employee.employee_name,
#             employee.designation,
#             employee.department.department_name if employee.department else "N/A",
#             employee.email or "N/A",
#             employee.phone_number or "N/A",
#             employee.experience or "N/A",
#         ])
#
#     exporter = PDFExporter(f'Employee List - {timezone.now().strftime("%B %d, %Y")}')
#
#     content = []
#     content.append(Paragraph(f"Total Employees: {queryset.count()}", exporter.styles["CustomHeading"]))
#     content.append(Spacer(1, 20))
#
#     col_widths = [100, 100, 100, 120, 80, 80]
#     content.append(exporter.create_table(headers, data, col_widths))
#
#     return exporter.create_pdf(content)
#
#
# # ============================================================================
# # Order Exports
# # ============================================================================
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export orders as CSV",
#     parameters=[
#         OpenApiParameter("payment_status", OpenApiTypes.STR, OpenApiParameter.QUERY),
#         OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#     ],
#     responses={200: OpenApiResponse(description="CSV file")},
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_orders_csv(request):
#     """Export orders list as CSV."""
#     queryset = Order.objects.select_related("user", "coupon").prefetch_related("items").order_by("-created_at")
#
#     payment_status = request.query_params.get("payment_status")
#     if payment_status:
#         queryset = queryset.filter(payment_status=payment_status)
#
#     start_date = request.query_params.get("start_date")
#     if start_date:
#         queryset = queryset.filter(created_at__date__gte=start_date)
#
#     end_date = request.query_params.get("end_date")
#     if end_date:
#         queryset = queryset.filter(created_at__date__lte=end_date)
#
#     headers = [
#         "Order Number", "Customer Name", "Customer Email", "Customer Phone",
#         "Items Count", "Subtotal", "Discount", "Total Amount", "Paid Amount",
#         "Due Amount", "Payment Status", "Payment Method", "Coupon Code", "Order Date"
#     ]
#
#     data = []
#     for order in queryset:
#         data.append([
#             order.order_number,
#             order.billing_name,
#             order.billing_email,
#             order.billing_phone,
#             order.items.count(),
#             f"{order.subtotal:.2f}",
#             f"{order.discount_amount:.2f}",
#             f"{order.total_amount:.2f}",
#             f"{order.paid_amount:.2f}",
#             f"{order.due_amount:.2f}",
#             order.get_payment_status_display(),
#             order.payment_method or "N/A",
#             order.coupon.code if order.coupon else "N/A",
#             order.created_at.strftime("%Y-%m-%d %H:%M"),
#         ])
#
#     filename = f'orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
#     return CSVExporter.export_to_csv(filename, headers, data)
#
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export order invoice as PDF (Admin)",
#     parameters=[
#         OpenApiParameter("order_id", OpenApiTypes.UUID, OpenApiParameter.PATH, required=True),
#     ],
#     responses={
#         200: OpenApiResponse(description="PDF invoice"),
#         404: OpenApiResponse(description="Order not found"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_order_invoice_pdf(request, order_id):
#     """Export single order invoice as PDF."""
#     try:
#         order = Order.objects.select_related("user", "coupon").prefetch_related("items__course").get(id=order_id)
#     except Order.DoesNotExist:
#         return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
#
#     return InvoicePDFGenerator(order).generate()
#
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export my order invoice as PDF (Student)",
#     parameters=[
#         OpenApiParameter("order_id", OpenApiTypes.UUID, OpenApiParameter.PATH, required=True),
#     ],
#     responses={
#         200: OpenApiResponse(description="PDF invoice"),
#         404: OpenApiResponse(description="Order not found"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def export_my_order_invoice_pdf(request, order_id):
#     """Export user's own order invoice as PDF."""
#     try:
#         if request.user.role == "student":
#             order = (
#                 Order.objects.select_related("user", "coupon")
#                 .prefetch_related("items__course")
#                 .get(id=order_id, user=request.user)
#             )
#         else:
#             order = Order.objects.select_related("user", "coupon").prefetch_related("items__course").get(id=order_id)
#     except Order.DoesNotExist:
#         return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
#
#     return InvoicePDFGenerator(order).generate()
#
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export my order invoice by number as PDF (Student)",
#     parameters=[
#         OpenApiParameter("order_number", OpenApiTypes.STR, OpenApiParameter.PATH, required=True),
#     ],
#     responses={
#         200: OpenApiResponse(description="PDF invoice"),
#         404: OpenApiResponse(description="Order not found"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def export_my_order_invoice_by_number_pdf(request, order_number):
#     """Export user's own order invoice as PDF using order number."""
#     try:
#         if request.user.role == "student":
#             order = (
#                 Order.objects.select_related("user", "coupon")
#                 .prefetch_related("items__course")
#                 .get(order_number=order_number, user=request.user)
#             )
#         else:
#             order = (
#                 Order.objects.select_related("user", "coupon")
#                 .prefetch_related("items__course")
#                 .get(order_number=order_number)
#             )
#     except Order.DoesNotExist:
#         return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
#
#     return InvoicePDFGenerator(order).generate()
#
#
# # ============================================================================
# # Course Completion Reports
# # ============================================================================
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export course completion report as CSV",
#     parameters=[
#         OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("course", OpenApiTypes.UUID, OpenApiParameter.QUERY),
#         OpenApiParameter("completion_status", OpenApiTypes.STR, OpenApiParameter.QUERY),
#     ],
#     responses={200: OpenApiResponse(description="CSV download")},
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_course_completion_csv(request):
#     """Export course completion report as CSV."""
#
#     # Debug: Check what's being received
#     try:
#         start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=365)
#         if error:
#             return error
#     except Exception as e:
#         return Response(
#             {"error": f"Date validation failed: {str(e)}"},
#             status=status.HTTP_400_BAD_REQUEST
#         )
#
#     try:
#         queryset = (
#             Enrollment.objects.select_related("user", "course")
#             .filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
#             .order_by("-created_at")
#         )
#
#         course_id = request.query_params.get("course")
#         if course_id:
#             queryset = queryset.filter(course_id=course_id)
#
#         completion_status = request.query_params.get("completion_status")
#         if completion_status == "completed":
#             queryset = queryset.filter(is_completed=True)
#         elif completion_status == "in_progress":
#             queryset = queryset.filter(is_completed=False)
#
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = f'attachment; filename="course_completion_{start_date}_to_{end_date}.csv"'
#
#         writer = csv.writer(response)
#         writer.writerow([
#             "Enrollment Date", "Student Name", "Student Email", "Student ID",
#             "Course Title", "Course Slug", "Progress %", "Completion Status",
#             "Completed Date", "Certificate Issued", "Days Enrolled", "Last Accessed"
#         ])
#
#         today = timezone.now().date()
#         for e in queryset:
#             writer.writerow([
#                 e.created_at.date(),
#                 e.user.get_full_name or "N/A",
#                 e.user.email,
#                 e.user.student_id or "N/A",
#                 e.course.title,
#                 e.course.slug,
#                 f"{e.progress_percentage:.2f}",
#                 "Completed" if e.is_completed else "In Progress",
#                 e.completed_at.date() if e.completed_at else "N/A",
#                 "Yes" if e.certificate_issued else "No",
#                 (today - e.created_at.date()).days,
#                 e.last_accessed.date() if e.last_accessed else "Never",
#             ])
#
#         return response
#
#     except Exception as e:
#         return Response(
#             {"error": f"Export failed: {str(e)}"},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export course completion report as PDF",
#     parameters=[
#         OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("course", OpenApiTypes.UUID, OpenApiParameter.QUERY),
#         OpenApiParameter("completion_status", OpenApiTypes.STR, OpenApiParameter.QUERY),
#     ],
#     responses={
#         200: OpenApiResponse(description="PDF file"),
#         400: OpenApiResponse(description="Invalid parameters"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_course_completion_pdf(request):
#     """Export course completion report as PDF."""
#     start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=365)
#     if error:
#         return error
#
#     queryset = Enrollment.objects.select_related("user", "course").filter(
#         created_at__date__gte=start_date, created_at__date__lte=end_date
#     )
#
#     course_id = request.query_params.get("course")
#     if course_id:
#         queryset = queryset.filter(course_id=course_id)
#
#     completion_status = request.query_params.get("completion_status")
#     if completion_status == "completed":
#         queryset = queryset.filter(is_completed=True)
#     elif completion_status == "in_progress":
#         queryset = queryset.filter(is_completed=False)
#
#     # Calculate statistics
#     total_enrollments = queryset.count()
#     completed_count = queryset.filter(is_completed=True).count()
#     in_progress_count = total_enrollments - completed_count
#     completion_rate = (completed_count / total_enrollments * 100) if total_enrollments > 0 else 0
#
#     headers = ["Student", "Course", "Progress %", "Status", "Enrolled", "Completed"]
#     data = []
#     for enrollment in queryset.order_by("-created_at"):
#         data.append([
#             enrollment.user.get_full_name or enrollment.user.email,
#             enrollment.course.title[:40],
#             f"{enrollment.progress_percentage:.1f}%",
#             "Complete" if enrollment.is_completed else "In Progress",
#             enrollment.created_at.strftime("%Y-%m-%d"),
#             enrollment.completed_at.strftime("%Y-%m-%d") if enrollment.completed_at else "-",
#         ])
#
#     title = f"Course Completion Report ({start_date} to {end_date})"
#     exporter = PDFExporter(title)
#
#     content = []
#     content.append(Paragraph(
#         f'<b>Report Period:</b> {start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")}',
#         exporter.styles["CustomBody"]
#     ))
#     content.append(Spacer(1, 10))
#     content.append(Paragraph(
#         f"<b>Total Enrollments:</b> {total_enrollments} | "
#         f"<b>Completed:</b> {completed_count} ({completion_rate:.1f}%) | "
#         f"<b>In Progress:</b> {in_progress_count}",
#         exporter.styles["CustomBody"]
#     ))
#     content.append(Spacer(1, 20))
#
#     col_widths = [120, 140, 60, 70, 70, 70]
#     content.append(exporter.create_table(headers, data, col_widths))
#
#     return exporter.create_pdf(content)
#
#
# # ============================================================================
# # Revenue Analytics
# # ============================================================================
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export revenue analytics as CSV",
#     parameters=[
#         OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("payment_status", OpenApiTypes.STR, OpenApiParameter.QUERY),
#         OpenApiParameter("course", OpenApiTypes.UUID, OpenApiParameter.QUERY),
#     ],
#     responses={
#         200: OpenApiResponse(description="CSV file"),
#         400: OpenApiResponse(description="Invalid date range"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated, IsAdmin])
# def export_revenue_analytics_csv(request):
#     """Export revenue and sales analytics as CSV."""
#     start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=730)
#     if error:
#         return error
#
#     queryset = (
#         Order.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
#         .select_related("user", "coupon")
#         .prefetch_related("items__course")
#     )
#
#     payment_status = request.query_params.get("payment_status")
#     if payment_status:
#         queryset = queryset.filter(payment_status=payment_status)
#
#     course_id = request.query_params.get("course")
#     if course_id:
#         queryset = queryset.filter(items__course_id=course_id).distinct()
#
#     headers = [
#         "Order Date", "Order Number", "Customer Name", "Customer Email",
#         "Courses Purchased", "Subtotal (৳)", "Discount (৳)", "Coupon Code",
#         "Total Amount (৳)", "Paid Amount (৳)", "Due Amount (৳)",
#         "Payment Status", "Payment Method", "Transaction ID"
#     ]
#
#     data = []
#     for order in queryset.order_by("-created_at"):
#         courses = ", ".join([item.course.title for item in order.items.all()])
#         data.append([
#             order.created_at.strftime("%Y-%m-%d %H:%M"),
#             order.order_number,
#             order.billing_name,
#             order.billing_email,
#             courses[:100],
#             f"{order.subtotal:.2f}",
#             f"{order.discount_amount:.2f}",
#             order.coupon.code if order.coupon else "N/A",
#             f"{order.total_amount:.2f}",
#             f"{order.paid_amount:.2f}",
#             f"{order.due_amount:.2f}",
#             order.get_payment_status_display(),
#             order.payment_method or "N/A",
#             order.transaction_id or "N/A",
#         ])
#
#     filename = f"revenue_analytics_{start_date}_to_{end_date}.csv"
#     return CSVExporter.export_to_csv(filename, headers, data)
#
#
# @extend_schema(
#     tags=["Data Export"],
#     summary="Export revenue analytics as PDF",
#     parameters=[
#         OpenApiParameter("start_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("end_date", OpenApiTypes.DATE, OpenApiParameter.QUERY),
#         OpenApiParameter("payment_status", OpenApiTypes.STR, OpenApiParameter.QUERY),
#     ],
#     responses={
#         200: OpenApiResponse(description="PDF file"),
#         400: OpenApiResponse(description="Invalid parameters"),
#     },
# )
# @api_view(["GET"])
# @permission_classes([IsAdmin])
# def export_revenue_analytics_pdf(request):
#     """Export revenue analytics as PDF."""
#     start_date, end_date, error = validate_and_parse_date_range(request, max_range_days=730)
#     if error:
#         return error
#
#     queryset = (
#         Order.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
#         .select_related("user", "coupon")
#         .prefetch_related("items__course")
#     )
#
#     payment_status = request.query_params.get("payment_status")
#     if payment_status:
#         queryset = queryset.filter(payment_status=payment_status)
#
#     # Statistics
#     total_orders = queryset.count()
#     paid_orders = queryset.filter(payment_status="paid")
#     total_revenue = paid_orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
#     total_paid = paid_orders.aggregate(total=Sum("paid_amount"))["total"] or Decimal("0.00")
#     total_discount = paid_orders.aggregate(total=Sum("discount_amount"))["total"] or Decimal("0.00")
#     avg_order_value = paid_orders.aggregate(avg=Avg("total_amount"))["avg"] or Decimal("0.00")
#
#     status_breakdown = {
#         "paid": queryset.filter(payment_status="paid").count(),
#         "pending": queryset.filter(payment_status="pending").count(),
#         "failed": queryset.filter(payment_status="failed").count(),
#         "refunded": queryset.filter(payment_status="refunded").count(),
#     }
#
#     # Top courses
#     top_courses = (
#         paid_orders.values(course_title=F("items__course__title"))
#         .annotate(revenue=Sum("items__price"), sales_count=Count("id", distinct=True))
#         .order_by("-revenue")[:10]
#     )
#
#     # Generate PDF
#     title = f"Revenue & Sales Analytics ({start_date} to {end_date})"
#     exporter = PDFExporter(title)
#     content = []
#
#     # Summary
#     content.append(Paragraph("<b>Executive Summary</b>", exporter.styles["CustomHeading"]))
#     content.append(Paragraph(
#         f'<b>Report Period:</b> {start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")} '
#         f"({(end_date - start_date).days + 1} days)",
#         exporter.styles["CustomBody"]
#     ))
#     content.append(Spacer(1, 10))
#
#     content.append(Paragraph(
#         f"<b>Total Orders:</b> {total_orders} | "
#         f'<b>Paid Orders:</b> {status_breakdown["paid"]} | '
#         f'<b>Pending:</b> {status_breakdown["pending"]}',
#         exporter.styles["CustomBody"]
#     ))
#     content.append(Paragraph(
#         f"<b>Total Revenue:</b> ৳{total_revenue:,.2f} | "
#         f"<b>Total Paid:</b> ৳{total_paid:,.2f} | "
#         f"<b>Avg Order:</b> ৳{avg_order_value:,.2f}",
#         exporter.styles["CustomBody"]
#     ))
#     content.append(Paragraph(f"<b>Total Discounts:</b> ৳{total_discount:,.2f}", exporter.styles["CustomBody"]))
#     content.append(Spacer(1, 20))
#
#     # Top courses table
#     if top_courses:
#         content.append(Paragraph("<b>Top Performing Courses</b>", exporter.styles["CustomHeading"]))
#         content.append(Spacer(1, 10))
#
#         headers = ["Course Title", "Sales", "Revenue (৳)"]
#         course_data = []
#         for course in top_courses:
#             if course["course_title"]:
#                 course_data.append([
#                     course["course_title"][:50],
#                     str(course["sales_count"]),
#                     f"৳{course['revenue']:,.2f}"
#                 ])
#
#         if course_data:
#             col_widths = [300, 80, 120]
#             content.append(exporter.create_table(headers, course_data, col_widths))
#             content.append(Spacer(1, 20))
#
#     # Recent orders
#     content.append(Paragraph("<b>Recent Orders</b>", exporter.styles["CustomHeading"]))
#     content.append(Spacer(1, 10))
#
#     headers = ["Date", "Order #", "Customer", "Amount (৳)", "Status"]
#     order_data = []
#     for order in queryset.order_by("-created_at")[:20]:
#         order_data.append([
#             order.created_at.strftime("%Y-%m-%d"),
#             order.order_number[:15],
#             order.billing_name[:30],
#             f"৳{order.total_amount:,.2f}",
#             order.get_payment_status_display(),
#         ])
#
#     col_widths = [70, 100, 150, 80, 80]
#     content.append(exporter.create_table(headers, order_data, col_widths))
#
#     return exporter.create_pdf(content)