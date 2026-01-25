"""
Admin interfaces for Live Classes, Assignments, and Quizzes (NEW SYSTEM)

This module provides comprehensive admin interfaces for managing:
- Live Classes (with attendance tracking)
- Assignments (with submissions and grading)
- Quizzes (with questions, options, attempts, and answers)

Uses nested_admin for complex hierarchical structures.
"""

import nested_admin
from django import forms
from django.contrib import admin
from django.db.models import Avg
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from api.admin.base_admin import BaseModelAdmin
from api.models.models_course import Course, CourseModule
from api.models.models_module import (
    Assignment,
    AssignmentSubmission,
    LiveClass,
    QuizQuestion,
    QuizQuestionOption, QuizAttempt, QuizAnswer, Quiz,
)


# ========== Live Class Admin ==========


@admin.register(LiveClass)
class LiveClassAdmin(BaseModelAdmin):
    """Admin for managing live classes."""

    def get_queryset(self, request):
        """Optimize queryset to eliminate N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "module",  # For course_name(), course_display()
            "module__course",  # Load Course
            "instructor",  # For instructor field in list_display
        ).prefetch_related(
            "attendances",  # For attendance_count()
        )

    class LiveClassAdminForm(forms.ModelForm):
        course = forms.ModelChoiceField(
            queryset=Course.objects.filter(is_active=True),
            required=False,
            label="Course",
            to_field_name="slug",
        )

        class Meta:
            model = LiveClass
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Set initial course from instance.module if editing
            if self.instance and getattr(self.instance, "module", None):
                module = self.instance.module
                if getattr(module, "course", None):
                    self.fields["course"].initial = module.course.slug

            # Limit module queryset to active modules; modules will be loaded via AJAX when course selected
            self.fields["module"].queryset = CourseModule.objects.filter(is_active=True).select_related("course")


        def clean(self):
            cleaned = super().clean()
            course = cleaned.get("course")
            module = cleaned.get("module")
            batch = cleaned.get("batch")

            if course and module:
                if module.course.slug != course.slug:
                    raise forms.ValidationError("Selected module does not belong to the chosen course.")

            if module and batch:
                if batch.course_id != module.course_id:
                    raise forms.ValidationError("Selected batch does not belong to the chosen module's course.")

            return cleaned

    form = LiveClassAdminForm
    list_display = [
        "title",
        "course_name",
        "module",
        "scheduled_date_display",
        "duration_minutes",
        "status_display",
        "attendance_count",
        "has_recording",
        "instructor",
        "is_active",
    ]
    list_filter = [
        "status",
        "is_active",
        "scheduled_date",
        "module__course",
        "instructor",
    ]
    search_fields = [
        "title",
        "description",
        "module__title",
        "module__course__title",
    ]
    readonly_fields = [
        "id",
        "course_display",
        "created_at",
        "updated_at",
        "get_statistics",
    ]
    filter_horizontal = []
    date_hierarchy = "scheduled_date"

    fieldsets = (
        (
            "📚 Course, Module & Batch",
            {
                "fields": ("course", "module", "batch"),
                "description": "Select course → module → batch",
            },
        ),
        (
            "Live Class Information",
            {"fields": ("title", "description", "order", "is_active")},
        ),
        ("Schedule", {"fields": ("scheduled_date", "duration_minutes", "instructor")}),
        (
            "Meeting Details",
            {
                "fields": ("meeting_url", "meeting_id", "meeting_password"),
                "classes": ("collapse",),
            },
        ),
        (
            "Recording",
            {
                "fields": ("status", "recording_url"),
                "description": "Add recording URL after class is completed",
            },
        ),
        ("Statistics", {"fields": ("get_statistics",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = []

    class Media:
        js = (
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/jquery.init.js",
            "admin/js/core.js",
            "admin/js/course_module_filter.js",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Show only active modules in dropdown."""
        if db_field.name == "module":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_active=True).select_related("course")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def course_name(self, obj):
        """Display course name."""
        return obj.module.course.title if obj.module and obj.module.course else "-"

    course_name.short_description = "Course"
    course_name.admin_order_field = "module__course__title"

    def course_display(self, obj):
        """Display course name in form (read-only)."""
        if obj.module and obj.module.course:
            course = obj.module.course
            return format_html(
                '<div style="padding: 10px; background: #e3f2fd; border-left: 4px solid #1976d2; font-size: 14px;">'
                '<strong style="color: #1976d2;">📚 {}</strong><br>'
                '<small style="color: #666;">Category: {} | Status: {}</small>'
                "</div>",
                course.title,
                course.category.name if course.category else "No category",
                course.get_status_display(),
            )
        return mark_safe('<em style="color: #999;">No course selected yet</em>')

    course_display.short_description = "Course (Read-only)"

    def scheduled_date_display(self, obj):
        """Display scheduled date with relative time."""
        now = timezone.now()
        delta = obj.scheduled_date - now

        if delta.days < 0:
            date_str = obj.scheduled_date.strftime("%Y-%m-%d %H:%M")
            days_ago = abs(delta.days)
            return format_html(
                '<span style="color: #999;">{}<br><small>{} days ago</small></span>',
                date_str,
                days_ago,
            )
        elif delta.days == 0:
            time_str = obj.scheduled_date.strftime("%H:%M")
            return format_html(
                '<span style="color: #ff9800; font-weight: bold;">{}<br><small>Today!</small></span>',
                time_str,
            )
        else:
            date_str = obj.scheduled_date.strftime("%Y-%m-%d %H:%M")
            days_left = delta.days
            return format_html("<span>{}<br><small>in {} days</small></span>", date_str, days_left)

    scheduled_date_display.short_description = "Scheduled"
    scheduled_date_display.admin_order_field = "scheduled_date"

    def status_display(self, obj):
        """Display status with color."""
        colors = {
            "scheduled": "#1976d2",
            "ongoing": "#ff9800",
            "completed": "#2e7d32",
            "cancelled": "#d32f2f",
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, "#666"),
            obj.get_status_display(),
        )

    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    def attendance_count(self, obj):
        """Display attendance count using prefetched cache."""
        if obj.pk:
            attendances = list(obj.attendances.all())
            total = len(attendances)
            attended = sum(1 for a in attendances if a.attended)

            if total > 0:
                percentage = (attended / total) * 100
                percentage_str = "{:.0f}%".format(float(percentage))
                return format_html("<span>{} / {} ({})</span>", attended, total, percentage_str)
            return "No attendees"
        return "-"

    attendance_count.short_description = "Attendance"

    def has_recording(self, obj):
        """Check if recording exists."""
        if obj.recording_url:
            return format_html('<span style="color: green;">✓ Yes</span>')
        return format_html('<span style="color: #999;">No</span>')

    has_recording.short_description = "Recording"
    has_recording.admin_order_field = "recording_url"

    def get_statistics(self, obj):
        """Display live class statistics using prefetched cache."""
        if obj.pk:
            attendances = list(obj.attendances.all())
            total_students = len(attendances)

            attended_list = [a for a in attendances if a.attended]
            attended = len(attended_list)

            attendance_rate = (attended / total_students * 100) if total_students > 0 else 0

            if attended_list:
                avg_duration = sum(a.duration_minutes for a in attended_list if a.duration_minutes) / len(attended_list)
            else:
                avg_duration = 0

            attendance_rate_fmt = f"{attendance_rate:.1f}%"
            avg_duration_fmt = f"{avg_duration:.0f}"

            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
                "<h3>Live Class Statistics</h3>"
                "<p><strong>Total Enrolled:</strong> {}</p>"
                "<p><strong>Attended:</strong> {} ({})</p>"
                "<p><strong>Avg Duration:</strong> {} minutes</p>"
                "<p><strong>Status:</strong> {}</p>"
                "<p><strong>Has Recording:</strong> {}</p>"
                "</div>",
                total_students,
                attended,
                attendance_rate_fmt,
                avg_duration_fmt,
                obj.get_status_display(),
                "Yes" if obj.recording_url else "No",
            )
        return "Save to see statistics"

    get_statistics.short_description = "Statistics"

    actions = ["mark_as_completed", "mark_as_cancelled"]

    def mark_as_completed(self, request, queryset):
        """Mark classes as completed."""
        updated = queryset.update(status="completed")
        self.message_user(request, f"{updated} classes marked as completed.")

    mark_as_completed.short_description = "Mark as completed"

    def mark_as_cancelled(self, request, queryset):
        """Mark classes as cancelled."""
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} classes marked as cancelled.")

    mark_as_cancelled.short_description = "Mark as cancelled"


# ========== Assignment Admin ==========


class AssignmentSubmissionInline(admin.TabularInline):
    """Inline for viewing assignment submissions."""

    model = AssignmentSubmission
    extra = 0
    fields = ["student", "status", "marks_obtained", "submitted_at", "is_late"]
    readonly_fields = ["student", "submitted_at", "is_late"]
    can_delete = False
    verbose_name = "Submission"
    verbose_name_plural = "Student Submissions"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Assignment)
class AssignmentAdmin(BaseModelAdmin):
    """Admin for managing assignments."""

    def get_queryset(self, request):
        """Optimize queryset to eliminate N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "module",
            "module__course",
            "created_by",
        ).prefetch_related(
            "submissions",
        )

    list_display = [
        "title",
        "course_name",
        "module",
        "assignment_type_display",
        "due_date_display",
        "submission_stats",
        "max_marks_display",
        "is_active",
    ]
    list_filter = [
        "assignment_type",
        "is_active",
        "due_date",
        "module__course",
        "late_submission_allowed",
    ]
    search_fields = [
        "title",
        "description",
        "module__title",
        "module__course__title",
    ]
    readonly_fields = [
        "id",
        "course_display",
        "created_at",
        "updated_at",
        "get_statistics",
    ]
    date_hierarchy = "due_date"

    fieldsets = (
        (
            "📚 Module & Batch",
            {
                "fields": ("module", "batch"),
                "description": "Assignment is batch-specific",
            },
        ),
        (
            "Assignment Information",
            {
                "fields": (
                    "title",
                    "description",
                    "assignment_type",
                    "order",
                    "is_active",
                )
            },
        ),
        (
            "Files & Resources",
            {
                "fields": ("attachment",),
                "description": "Upload reference materials or assignment file for students",
            },
        ),
        ("Grading", {"fields": ("total_marks", "passing_marks")}),
        (
            "Deadline & Submission",
            {
                "fields": (
                    "due_date",
                    "late_submission_allowed",
                    "late_submission_penalty",
                )
            },
        ),
        ("Statistics", {"fields": ("get_statistics",), "classes": ("collapse",)}),
        (
            "Metadata",
            {
                "fields": ("id", "created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [AssignmentSubmissionInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Show only active modules in dropdown."""
        if db_field.name == "module":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_active=True).select_related("course")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def course_name(self, obj):
        """Display course name."""
        return obj.module.course.title if obj.module and obj.module.course else "-"

    course_name.short_description = "Course"
    course_name.admin_order_field = "module__course__title"

    def course_display(self, obj):
        """Display course name in form (read-only)."""
        if obj.module and obj.module.course:
            course = obj.module.course
            return format_html(
                '<div style="padding: 10px; background: #e3f2fd; border-left: 4px solid #1976d2; font-size: 14px;">'
                '<strong style="color: #1976d2;">📚 {}</strong><br>'
                '<small style="color: #666;">Category: {} | Status: {}</small>'
                "</div>",
                course.title,
                course.category.name if course.category else "No category",
                course.get_status_display(),
            )
        return format_html('<em style="color: #999;">No course selected yet</em>')

    course_display.short_description = "Course (Read-only)"

    def assignment_type_display(self, obj):
        """Display assignment type with icon."""
        icons = {
            "written": "📝",
            "coding": "💻",
            "project": "🚀",
            "quiz": "❓",
            "presentation": "🎤",
        }
        icon = icons.get(obj.assignment_type, "📄")
        type_display = obj.get_assignment_type_display()
        return format_html("<span>{} {}</span>", icon, type_display)

    assignment_type_display.short_description = "Type"
    assignment_type_display.admin_order_field = "assignment_type"

    def due_date_display(self, obj):
        """Display due date with status."""
        now = timezone.now()
        delta = obj.due_date - now

        if delta.days < 0:
            date_str = obj.due_date.strftime("%Y-%m-%d %H:%M")
            return format_html(
                '<span style="color: #d32f2f; font-weight: bold;">{}<br><small>⚠️ Overdue</small></span>',
                date_str,
            )
        elif delta.days == 0:
            time_str = obj.due_date.strftime("%H:%M")
            return format_html(
                '<span style="color: #ff9800; font-weight: bold;">{}<br><small>⏰ Due today!</small></span>',
                time_str,
            )
        else:
            date_str = obj.due_date.strftime("%Y-%m-%d %H:%M")
            days_left = delta.days
            return format_html("<span>{}<br><small>{} days left</small></span>", date_str, days_left)

    due_date_display.short_description = "Due Date"
    due_date_display.admin_order_field = "due_date"

    def submission_stats(self, obj):
        """Display submission statistics using prefetched cache."""
        if obj.pk:
            submissions = list(obj.submissions.all())
            total = len(submissions)
            graded = sum(1 for s in submissions if s.status == "graded")
            pending = sum(1 for s in submissions if s.status == "pending")

            return format_html(
                '<div style="line-height: 1.4;">'
                '<span style="color: #2e7d32;">✓ {}</span> graded<br>'
                '<span style="color: #ff9800;">⏳ {}</span> pending<br>'
                "<strong>{}</strong> total"
                "</div>",
                graded,
                pending,
                total,
            )
        return "-"

    submission_stats.short_description = "Submissions"

    def max_marks_display(self, obj):
        """Display marks with passing score."""
        return format_html(
            "<strong>{}</strong> total<br><small>{} to pass</small>",
            obj.total_marks,
            obj.passing_marks,
        )

    max_marks_display.short_description = "Marks"

    def get_statistics(self, obj):
        """Display assignment statistics."""
        if obj.pk:
            total_submissions = obj.submissions.count()
            graded = obj.submissions.filter(status="graded").count()
            pending = obj.submissions.filter(status="pending").count()
            passed = obj.submissions.filter(status="graded", marks_obtained__gte=obj.passing_marks).count()

            avg_marks = obj.submissions.filter(status="graded").aggregate(avg=Avg("marks_obtained"))["avg"] or 0

            pass_rate = (passed / graded * 100) if graded > 0 else 0

            # PRE-FORMATTED VALUES
            pass_rate_fmt = f"{pass_rate:.1f}%"
            avg_marks_fmt = f"{avg_marks:.1f}"

            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
                "<h3>Assignment Statistics</h3>"
                "<p><strong>Total Submissions:</strong> {}</p>"
                "<p><strong>Graded:</strong> {} | <strong>Pending:</strong> {}</p>"
                "<p><strong>Passed:</strong> {} ({})</p>"
                "<p><strong>Average Marks:</strong> {} / {}</p>"
                "<p><strong>Passing Marks:</strong> {}</p>"
                "</div>",
                total_submissions,
                graded,
                pending,
                passed,
                pass_rate_fmt,
                avg_marks_fmt,
                obj.total_marks,
                obj.passing_marks,
            )
        return "Save to see statistics"

    get_statistics.short_description = "Statistics"

    def save_model(self, request, obj, form, change):
        """Set created_by on first save."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(BaseModelAdmin):
    """Admin for assignment submissions."""

    list_display = [
        "student_name",
        "assignment",
        "status_display",
        "marks_display",
        "late_status",
        "submitted_at",
        "graded_by",
    ]
    list_filter = [
        "status",
        "is_late",
        "submitted_at",
        "graded_at",
        "assignment__module__course",
    ]
    search_fields = [
        "student__email",
        "student__first_name",
        "student__last_name",
        "assignment__title",
    ]
    readonly_fields = ["id", "submitted_at", "is_late", "updated_at"]
    date_hierarchy = "submitted_at"

    fieldsets = (
        (
            "Submission Information",
            {"fields": ("assignment", "student", "submitted_at", "is_late")},
        ),
        (
            "Submission Content",
            {"fields": ("submission_text", "submission_file", "submission_url")},
        ),
        (
            "Grading",
            {
                "fields": (
                    "status",
                    "marks_obtained",
                    "feedback",
                    "graded_by",
                    "graded_at",
                )
            },
        ),
        ("Metadata", {"fields": ("id", "updated_at"), "classes": ("collapse",)}),
    )

    actions = ["grade_as_pending", "grade_as_graded", "mark_for_resubmission"]

    def student_name(self, obj):
        """Display student name."""
        return obj.student.get_full_name

    student_name.short_description = "Student"
    student_name.admin_order_field = "student__first_name"

    def status_display(self, obj):
        """Display status with color."""
        colors = {
            "pending": "#ff9800",
            "submitted": "#1976d2",
            "graded": "#2e7d32",
            "resubmit": "#d32f2f",
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, "#666"),
            obj.get_status_display(),
        )

    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    def marks_display(self, obj):
        """Display marks obtained."""
        if obj.marks_obtained is not None:
            percentage = (obj.marks_obtained / obj.assignment.total_marks) * 100
            passed = obj.marks_obtained >= obj.assignment.passing_marks
            color = "#2e7d32" if passed else "#d32f2f"

            # PRE-FORMAT percentage
            percentage_fmt = f"{percentage:.0f}%"

            return format_html(
                '<span style="color: {}; font-weight: bold;">{} / {} ({})</span>',
                color,
                obj.marks_obtained,
                obj.assignment.total_marks,
                percentage_fmt,
            )

        return format_html('<span style="color: #999;">Not graded</span>')

    marks_display.short_description = "Marks"

    def late_status(self, obj):
        """Display late submission status."""
        if obj.is_late:
            return format_html('<span style="color: #d32f2f;">⚠️ Late</span>')
        return format_html('<span style="color: #2e7d32;">✓ On Time</span>')

    late_status.short_description = "Timing"
    late_status.admin_order_field = "is_late"

    def grade_as_pending(self, request, queryset):
        """Mark as pending review."""
        updated = queryset.update(status="pending")
        self.message_user(request, f"{updated} submissions marked as pending.")

    grade_as_pending.short_description = "Mark as pending"

    def grade_as_graded(self, request, queryset):
        """Mark as graded."""
        updated = queryset.update(status="graded", graded_by=request.user, graded_at=timezone.now())
        self.message_user(request, f"{updated} submissions marked as graded.")

    grade_as_graded.short_description = "Mark as graded"

    def mark_for_resubmission(self, request, queryset):
        """Mark for resubmission."""
        updated = queryset.update(status="resubmit", graded_by=request.user, graded_at=timezone.now())
        self.message_user(request, f"{updated} submissions marked for resubmission.")

    mark_for_resubmission.short_description = "Mark for resubmission"

    def has_module_permission(self, request):
        return False



# ============================================================
# QUIZ ADMIN – FIXED & PRODUCTION SAFE
# ============================================================

class QuizQuestionOptionInline(nested_admin.NestedTabularInline):
    model = QuizQuestionOption
    extra = 4
    max_num = 10
    fields = ["order", "option_text", "is_correct"]
    ordering = ["order"]

    verbose_name = "Answer Option"
    verbose_name_plural = "Answer Options (tick correct ones)"



# ------------------------------------------------------------
# INLINE: Questions
# ------------------------------------------------------------

class QuizQuestionInline(nested_admin.NestedStackedInline):
    model = QuizQuestion
    extra = 0
    ordering = ("order",)
    inlines = [QuizQuestionOptionInline]


# ------------------------------------------------------------
# INLINE: Attempts (READ ONLY)
# ------------------------------------------------------------

class QuizAttemptInline(nested_admin.NestedTabularInline):
    model = QuizAttempt
    extra = 0
    can_delete = False
    show_change_link = True

    readonly_fields = (
        "student",
        "attempt_number",
        "marks_obtained",
        "percentage",
        "passed",
        "status",
        "started_at",
        "submitted_at",
    )

    fields = readonly_fields


# ------------------------------------------------------------
# MAIN ADMIN: QUIZ
# ------------------------------------------------------------

@admin.register(Quiz)
class QuizAdmin(nested_admin.NestedModelAdmin, BaseModelAdmin):

    inlines = [
        QuizQuestionInline,
        QuizAttemptInline,
    ]

    fieldsets = (
        (
            "📚 Module & Batch",
            {
                "fields": ("module", "batch"),
                "description": "Quiz is batch-specific",
            },
        ),
        (
            "Quiz Information",
            {
                "fields": (
                    "title",
                    "description",
                    "difficulty",
                    "total_marks",
                    "passing_marks",
                    "duration_minutes",
                    "max_attempts",
                    "is_active",
                )
            },
        ),
        (
            "Availability",
            {
                "fields": ("available_from", "available_until"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    list_display = (
        "title",
        "module",
        "batch",
        "difficulty",
        "total_marks",
        "max_attempts",
        "is_active",
    )

    list_filter = ("difficulty", "is_active", "module__course", "batch")
    search_fields = ("title", "module__title", "module__course__title")

    readonly_fields = ("created_at", "updated_at")


# ------------------------------------------------------------
# HIDE FROM SIDEBAR (INLINE-ONLY MODELS)
# ------------------------------------------------------------

@admin.register(QuizAttempt)
class QuizAttemptAdmin(BaseModelAdmin):
    def has_module_permission(self, request):
        return False


@admin.register(QuizAnswer)
class QuizAnswerAdmin(BaseModelAdmin):
    def has_module_permission(self, request):
        return False


