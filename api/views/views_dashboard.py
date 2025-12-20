"""Dashboard API views for admin analytics and statistics."""

from datetime import datetime, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.models.models_auth import CustomUser
from api.models.models_course import Course
from api.models.models_order import Enrollment, Order
from api.permissions import IsAdmin
from api.utils.response_utils import api_response


def get_date_range(period):
    """
    Calculate date range based on the period filter.

    Available periods:
    - today: Last 24 hours
    - week: Last 7 days
    - 2weeks: Last 14 days
    - month: Last 30 days
    - 3months: Last 90 days
    - 6months: Last 180 days
    - year: Last 365 days
    - all: All time
    """
    now = timezone.now()

    period_mapping = {
        "today": timedelta(days=1),
        "week": timedelta(days=7),
        "2weeks": timedelta(days=14),
        "month": timedelta(days=30),
        "3months": timedelta(days=90),
        "6months": timedelta(days=180),
        "year": timedelta(days=365),
    }

    if period == "all":
        return None  # No filter, return all data

    delta = period_mapping.get(period, timedelta(days=30))  # Default to month
    return now - delta


def get_previous_period_date(current_start_date, period):
    """Calculate the start date for the previous period for comparison."""
    if current_start_date is None:
        return None

    now = timezone.now()
    delta = now - current_start_date
    return current_start_date - delta


@extend_schema(
    summary="Get dashboard overview statistics",
    description="""
    Get comprehensive dashboard statistics with cards and charts.

    **Filter Periods:**
    - `today`: Last 24 hours
    - `week`: Last 7 days (recommended for quick overview)
    - `2weeks`: Last 14 days
    - `month`: Last 30 days (default, recommended for monthly reports)
    - `3months`: Last 90 days (quarterly)
    - `6months`: Last 180 days (bi-annual)
    - `year`: Last 365 days (annual report)
    - `all`: All time data

    **Response includes:**
    - Statistics cards (students, courses, teachers, earnings)
    - Enrollment trends (last 12 months bar chart)
    - Popular courses (top 5 pie chart)
    """,
    parameters=[
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Time period filter (today, week, 2weeks, month, 3months, 6months, year, all)",
            enum=["today", "week", "2weeks", "month", "3months", "6months", "year", "all"],
            default="month",
        )
    ],
    tags=["Dashboard"],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([IsAdmin])
def dashboard_overview(request):
    """Get dashboard overview with statistics cards and charts."""

    # Get period filter
    period = request.query_params.get("period", "month")
    start_date = get_date_range(period)
    previous_start_date = get_previous_period_date(start_date, period) if start_date else None

    # Build base filters
    current_filter = Q()
    current_filter_users = Q()
    previous_filter = Q()
    previous_filter_users = Q()

    if start_date:
        current_filter = Q(created_at__gte=start_date)
        current_filter_users = Q(date_joined__gte=start_date)
        if previous_start_date:
            previous_filter = Q(created_at__gte=previous_start_date, created_at__lt=start_date)
            previous_filter_users = Q(date_joined__gte=previous_start_date, date_joined__lt=start_date)

    # ========== STATISTICS CARDS ==========

    # 1. Total Students
    total_students = CustomUser.objects.filter(role="student", is_enabled=True).count()
    new_students = CustomUser.objects.filter(role="student", is_enabled=True).filter(current_filter_users).count()

    prev_students = (
        CustomUser.objects.filter(role="student", is_enabled=True).filter(previous_filter_users).count()
        if previous_start_date
        else 0
    )

    student_growth = new_students - prev_students if prev_students > 0 else new_students
    student_growth_percentage = (student_growth / prev_students * 100) if prev_students > 0 else 0

    # 2. Total Courses
    total_courses = Course.objects.filter(is_active=True).count()
    new_courses = Course.objects.filter(is_active=True).filter(current_filter).count()

    prev_courses = Course.objects.filter(is_active=True).filter(previous_filter).count() if previous_start_date else 0
    course_growth = new_courses - prev_courses if prev_courses > 0 else new_courses

    # 3. Total Teachers
    total_teachers = CustomUser.objects.filter(role__in=["teacher", "staff"], is_enabled=True).count()
    new_teachers = (
        CustomUser.objects.filter(role__in=["teacher", "staff"], is_enabled=True).filter(current_filter_users).count()
    )

    prev_teachers = (
        CustomUser.objects.filter(role__in=["teacher", "staff"], is_enabled=True).filter(previous_filter_users).count()
        if previous_start_date
        else 0
    )
    teacher_growth = new_teachers - prev_teachers if prev_teachers > 0 else new_teachers

    # 4. Total Earnings (Only completed orders - paid and verified)
    total_earnings = (
        Order.objects.filter(status="completed").aggregate(total=Sum("total_amount"))["total"]  # Only count completed orders
        or 0
    )

    period_earnings = (
        Order.objects.filter(status="completed")  # Only count completed orders
        .filter(current_filter)
        .aggregate(total=Sum("total_amount"))["total"]
        or 0
    )

    prev_earnings = (
        Order.objects.filter(status="completed")  # Only count completed orders
        .filter(previous_filter)
        .aggregate(total=Sum("total_amount"))["total"]
        or 0
        if previous_start_date
        else 0
    )

    earnings_growth = period_earnings - prev_earnings if prev_earnings > 0 else period_earnings
    earnings_growth_percentage = (earnings_growth / prev_earnings * 100) if prev_earnings > 0 else 0

    # ========== CHARTS DATA ==========

    # Chart 1: Enrollment Overview - Last 12 Months (Bar Chart)
    twelve_months_ago = timezone.now() - timedelta(days=365)
    enrollments_by_month = (
        Enrollment.objects.filter(created_at__gte=twelve_months_ago, is_active=True)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Format for chart
    enrollment_chart = {"labels": [], "data": []}

    for item in enrollments_by_month:
        month_name = item["month"].strftime("%b %Y")
        enrollment_chart["labels"].append(month_name)
        enrollment_chart["data"].append(item["count"])

    # Chart 2: Top 5 Popular Courses (Pie Chart)
    popular_courses = (
        Enrollment.objects.filter(is_active=True)
        .values("course__id", "course__title")
        .annotate(enrollment_count=Count("id"))
        .order_by("-enrollment_count")[:5]
    )

    popular_courses_chart = {"labels": [], "data": [], "course_ids": []}

    for course in popular_courses:
        popular_courses_chart["labels"].append(course["course__title"])
        popular_courses_chart["data"].append(course["enrollment_count"])
        popular_courses_chart["course_ids"].append(str(course["course__id"]))

    # ========== BUILD RESPONSE ==========

    period_label = {
        "today": "today",
        "week": "this week",
        "2weeks": "last 2 weeks",
        "month": "this month",
        "3months": "last 3 months",
        "6months": "last 6 months",
        "year": "this year",
        "all": "all time",
    }.get(period, "this period")

    data = {
        "period": period,
        "period_label": period_label,
        "statistics": {
            "students": {
                "total": total_students,
                "new": new_students,
                "growth": student_growth,
                "growth_percentage": round(student_growth_percentage, 2),
                "label": f"+{new_students} new {period_label}",
            },
            "courses": {
                "total": total_courses,
                "new": new_courses,
                "growth": course_growth,
                "label": f"+{new_courses} new {period_label}",
            },
            "teachers": {
                "total": total_teachers,
                "new": new_teachers,
                "growth": teacher_growth,
                "label": f"+{new_teachers} new {period_label}",
            },
            "earnings": {
                "total": float(total_earnings),
                "period_earnings": float(period_earnings),
                "growth": float(earnings_growth),
                "growth_percentage": round(earnings_growth_percentage, 2),
                "label": f"+{round(earnings_growth_percentage, 1)}% {period_label}",
                "currency": "BDT",
            },
        },
        "charts": {
            "enrollment_overview": {
                "title": "Enrollment Overview - Last 12 Months",
                "type": "bar",
                "labels": enrollment_chart["labels"],
                "data": enrollment_chart["data"],
                "total_enrollments": sum(enrollment_chart["data"]),
            },
            "popular_courses": {
                "title": "Top 5 Popular Courses",
                "type": "pie",
                "labels": popular_courses_chart["labels"],
                "data": popular_courses_chart["data"],
                "course_ids": popular_courses_chart["course_ids"],
                "total_enrollments": sum(popular_courses_chart["data"]),
            },
        },
    }

    return api_response(True, f"Dashboard overview for {period_label} retrieved successfully", data)


@extend_schema(
    summary="Get detailed student statistics",
    description="""
    Get detailed breakdown of student data with trends and demographics.

    Includes:
    - Total active/inactive students
    - New registrations by day/week/month
    - Student growth trend
    - Geographic distribution (if available)
    """,
    parameters=[
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Time period filter",
            enum=["today", "week", "2weeks", "month", "3months", "6months", "year", "all"],
            default="month",
        )
    ],
    tags=["Dashboard"],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([IsAdmin])
def student_details(request):
    """Get detailed student statistics and trends."""

    period = request.query_params.get("period", "month")
    start_date = get_date_range(period)

    # Build filter
    date_filter = Q(date_joined__gte=start_date) if start_date else Q()

    # Basic stats
    total_students = CustomUser.objects.filter(role="student", is_enabled=True).count()
    inactive_students = CustomUser.objects.filter(role="student", is_enabled=False).count()
    new_students = CustomUser.objects.filter(role="student").filter(date_filter).count()

    # Students with enrollments
    enrolled_students = (
        CustomUser.objects.filter(role="student", is_enabled=True, enrollments__is_active=True).distinct().count()
    )

    # Daily registration trend (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_registrations = (
        CustomUser.objects.filter(role="student", date_joined__gte=thirty_days_ago)
        .annotate(date=TruncDate("date_joined"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    registration_trend = {"labels": [], "data": []}

    for item in daily_registrations:
        registration_trend["labels"].append(item["date"].strftime("%Y-%m-%d"))
        registration_trend["data"].append(item["count"])

    data = {
        "period": period,
        "summary": {
            "total_students": total_students,
            "active_students": total_students,
            "inactive_students": inactive_students,
            "new_students": new_students,
            "enrolled_students": enrolled_students,
            "unenrolled_students": total_students - enrolled_students,
        },
        "registration_trend": {
            "title": "Daily Registrations - Last 30 Days",
            "labels": registration_trend["labels"],
            "data": registration_trend["data"],
        },
    }

    return api_response(True, "Student details retrieved successfully", data)


@extend_schema(
    summary="Get detailed course statistics",
    description="Get detailed breakdown of course data with enrollment stats and revenue.",
    parameters=[
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Time period filter",
            enum=["today", "week", "2weeks", "month", "3months", "6months", "year", "all"],
            default="month",
        )
    ],
    tags=["Dashboard"],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([IsAdmin])
def course_details(request):
    """Get detailed course statistics."""

    period = request.query_params.get("period", "month")
    start_date = get_date_range(period)

    date_filter = Q(created_at__gte=start_date) if start_date else Q()

    # Course stats
    total_courses = Course.objects.filter(is_active=True).count()
    published_courses = Course.objects.filter(is_active=True, status="published").count()
    draft_courses = Course.objects.filter(is_active=True, status="draft").count()
    new_courses = Course.objects.filter(date_filter).count()

    # Enrollment stats per course
    course_enrollment_stats = (
        Course.objects.filter(is_active=True)
        .annotate(total_enrollments=Count("enrollments", filter=Q(enrollments__is_active=True)))
        .values("id", "title", "total_enrollments")
        .order_by("-total_enrollments")[:10]
    )

    data = {
        "period": period,
        "summary": {
            "total_courses": total_courses,
            "published_courses": published_courses,
            "draft_courses": draft_courses,
            "new_courses": new_courses,
        },
        "top_courses": list(course_enrollment_stats),
    }

    return api_response(True, "Course details retrieved successfully", data)


@extend_schema(
    summary="Get detailed earnings statistics",
    description="Get detailed breakdown of earnings with payment methods and trends.",
    parameters=[
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Time period filter",
            enum=["today", "week", "2weeks", "month", "3months", "6months", "year", "all"],
            default="month",
        )
    ],
    tags=["Dashboard"],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([IsAdmin])
def earnings_details(request):
    """Get detailed earnings statistics."""

    period = request.query_params.get("period", "month")
    start_date = get_date_range(period)

    date_filter = Q(created_at__gte=start_date) if start_date else Q()

    # Total earnings (Only completed orders)
    total_earnings = (
        Order.objects.filter(status="completed").aggregate(total=Sum("total_amount"))["total"]  # Only count completed orders
        or 0
    )

    # Period earnings (Only completed orders)
    period_earnings = (
        Order.objects.filter(status="completed")  # Only count completed orders
        .filter(date_filter)
        .aggregate(total=Sum("total_amount"))["total"]
        or 0
    )

    # Earnings by payment method (Only completed orders)
    earnings_by_method = (
        Order.objects.filter(status="completed")  # Only count completed orders
        .filter(date_filter)
        .values("payment_method")
        .annotate(total=Sum("total_amount"), count=Count("id"))
    )

    # Earnings by course (top 10, Only completed orders)
    earnings_by_course = (
        Order.objects.filter(status="completed")  # Only count completed orders
        .filter(date_filter)
        .values("items__course__id", "items__course__title")
        .annotate(total_revenue=Sum(F("items__price") - F("items__discount")), total_orders=Count("id", distinct=True))
        .order_by("-total_revenue")[:10]
    )

    # Monthly earnings trend (last 12 months, Only completed orders)
    twelve_months_ago = timezone.now() - timedelta(days=365)
    monthly_earnings = (
        Order.objects.filter(status="completed", created_at__gte=twelve_months_ago)  # Only count completed orders
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("total_amount"))
        .order_by("month")
    )

    earnings_trend = {"labels": [], "data": []}

    for item in monthly_earnings:
        earnings_trend["labels"].append(item["month"].strftime("%b %Y"))
        earnings_trend["data"].append(float(item["total"]))

    data = {
        "period": period,
        "summary": {"total_earnings": float(total_earnings), "period_earnings": float(period_earnings), "currency": "BDT"},
        "by_payment_method": [
            {"method": item["payment_method"], "total": float(item["total"]), "count": item["count"]}
            for item in earnings_by_method
        ],
        "top_earning_courses": [
            {
                "course_id": str(item["items__course__id"]) if item["items__course__id"] else None,
                "course_title": item["items__course__title"],
                "total_revenue": float(item["total_revenue"] or 0),
                "total_orders": item["total_orders"],
            }
            for item in earnings_by_course
        ],
        "earnings_trend": {
            "title": "Monthly Earnings - Last 12 Months",
            "labels": earnings_trend["labels"],
            "data": earnings_trend["data"],
        },
    }

    return api_response(True, "Earnings details retrieved successfully", data)
