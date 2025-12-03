"""Admin interfaces for course progress tracking models."""

import nested_admin
from django.contrib import admin
from django.utils.html import format_html

from api.admin.base_admin import BaseAdmin
from api.models.models_progress import (
    CourseProgress,
    ModuleAssignment,
    ModuleQuiz,
    StudentAssignmentSubmission,
    StudentModuleProgress,
    StudentQuizAttempt,
)


# ========== Inline Admins for Module Content ==========

class ModuleQuizInline(nested_admin.NestedStackedInline):
    """Inline admin for quizzes within a module."""
    model = ModuleQuiz
    extra = 0
    max_num = 1  # Typically 0-1 quiz per module
    fields = [
        'title',
        'description',
        'passing_score',
        'max_attempts',
        'time_limit_minutes',
        'is_active',
        'order',
    ]
    verbose_name = "Module Quiz"
    verbose_name_plural = "Module Quizzes (0-1 recommended)"


class ModuleAssignmentInline(nested_admin.NestedStackedInline):
    """Inline admin for assignments within a module."""
    model = ModuleAssignment
    extra = 0
    max_num = 2  # Typically 0-2 assignments per module (remove max_num for unlimited)
    fields = [
        'title',
        'description',
        'attachment_file',
        'due_date',
        'max_score',
        'passing_score',
        'allow_late_submission',
        'is_active',
        'order',
    ]
    verbose_name = "Module Assignment"
    verbose_name_plural = "Module Assignments (0-2 recommended)"


# ========== Main Model Admins ==========

@admin.register(ModuleQuiz)
class ModuleQuizAdmin(BaseAdmin):
    """Admin interface for module quizzes."""
    list_display = [
        'title',
        'module',
        'passing_score',
        'max_attempts',
        'get_pass_count_display',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'passing_score', 'created_at', 'module__course']
    search_fields = ['title', 'description', 'module__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'get_statistics']
    fieldsets = (
        ('Quiz Information', {
            'fields': ('module', 'title', 'description', 'order')
        }),
        ('Settings', {
            'fields': ('passing_score', 'max_attempts', 'time_limit_minutes', 'is_active')
        }),
        ('Questions', {
            'fields': ('questions',),
            'description': 'Quiz questions in JSON format. Use API or custom interface to manage questions.'
        }),
        ('Statistics', {
            'fields': ('get_statistics',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_pass_count_display(self, obj):
        """Display number of students who passed."""
        count = obj.get_pass_count()
        total = obj.get_attempt_count()
        return f"{count} passed / {total} attempts"
    get_pass_count_display.short_description = 'Pass Rate'
    
    def get_statistics(self, obj):
        """Display quiz statistics."""
        if obj.pk:
            pass_count = obj.get_pass_count()
            total_attempts = obj.get_attempt_count()
            pass_rate = (pass_count / total_attempts * 100) if total_attempts > 0 else 0
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
                '<h3>Quiz Statistics</h3>'
                '<p><strong>Total Attempts:</strong> {}</p>'
                '<p><strong>Students Passed:</strong> {}</p>'
                '<p><strong>Pass Rate:</strong> {:.1f}%</p>'
                '<p><strong>Passing Score:</strong> {}%</p>'
                '</div>',
                total_attempts,
                pass_count,
                pass_rate,
                obj.passing_score
            )
        return "Save quiz to see statistics"
    get_statistics.short_description = 'Statistics'


@admin.register(ModuleAssignment)
class ModuleAssignmentAdmin(BaseAdmin):
    """Admin interface for module assignments."""
    list_display = [
        'title',
        'module',
        'due_date',
        'max_score',
        'get_submission_stats',
        'is_overdue_display',
        'is_active',
    ]
    list_filter = ['is_active', 'due_date', 'allow_late_submission', 'created_at', 'module__course']
    search_fields = ['title', 'description', 'module__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'get_statistics']
    fieldsets = (
        ('Assignment Information', {
            'fields': ('module', 'title', 'description', 'attachment_file', 'order')
        }),
        ('Grading', {
            'fields': ('max_score', 'passing_score')
        }),
        ('Deadline', {
            'fields': ('due_date', 'allow_late_submission')
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('get_statistics',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_submission_stats(self, obj):
        """Display submission statistics."""
        approved = obj.get_approved_count()
        total = obj.get_submission_count()
        return f"{approved} approved / {total} submissions"
    get_submission_stats.short_description = 'Submissions'
    
    def is_overdue_display(self, obj):
        """Display if assignment is overdue."""
        if obj.is_overdue():
            return format_html('<span style="color: red;">⚠️ Overdue</span>')
        return format_html('<span style="color: green;">✓ Open</span>')
    is_overdue_display.short_description = 'Status'
    
    def get_statistics(self, obj):
        """Display assignment statistics."""
        if obj.pk:
            total_submissions = obj.get_submission_count()
            approved = obj.get_approved_count()
            approval_rate = (approved / total_submissions * 100) if total_submissions > 0 else 0
            
            status = "Overdue" if obj.is_overdue() else "Open"
            status_color = "red" if obj.is_overdue() else "green"
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
                '<h3>Assignment Statistics</h3>'
                '<p><strong>Status:</strong> <span style="color: {};">{}</span></p>'
                '<p><strong>Total Submissions:</strong> {}</p>'
                '<p><strong>Approved:</strong> {}</p>'
                '<p><strong>Approval Rate:</strong> {:.1f}%</p>'
                '<p><strong>Max Score:</strong> {}</p>'
                '</div>',
                status_color,
                status,
                total_submissions,
                approved,
                approval_rate,
                obj.max_score
            )
        return "Save assignment to see statistics"
    get_statistics.short_description = 'Statistics'


@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(BaseAdmin):
    """Admin interface for student quiz attempts."""
    list_display = [
        'student',
        'quiz',
        'attempt_number',
        'score',
        'is_passed_display',
        'completed_at',
        'graded_by',
    ]
    list_filter = [
        'is_passed',
        'started_at',
        'completed_at',
        'quiz__module__course',
        'graded_by',
    ]
    search_fields = [
        'student__email',
        'student__first_name',
        'student__last_name',
        'quiz__title',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'started_at',
        'get_time_taken_display',
    ]
    fieldsets = (
        ('Attempt Information', {
            'fields': ('student', 'quiz', 'attempt_number')
        }),
        ('Answers & Score', {
            'fields': ('answers', 'score', 'is_passed')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'get_time_taken_display')
        }),
        ('Grading', {
            'fields': ('graded_by', 'graded_at', 'feedback'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_passed_display(self, obj):
        """Display pass/fail with color."""
        if obj.is_passed:
            return format_html('<span style="color: green; font-weight: bold;">✓ PASSED</span>')
        return format_html('<span style="color: red;">✗ Failed</span>')
    is_passed_display.short_description = 'Result'
    
    def get_time_taken_display(self, obj):
        """Display time taken for quiz."""
        time_taken = obj.get_time_taken()
        if time_taken:
            return f"{time_taken:.1f} minutes"
        return "Not completed"
    get_time_taken_display.short_description = 'Time Taken'


@admin.register(StudentAssignmentSubmission)
class StudentAssignmentSubmissionAdmin(BaseAdmin):
    """Admin interface for student assignment submissions."""
    list_display = [
        'student',
        'assignment',
        'status_display',
        'score',
        'is_late_display',
        'submitted_at',
        'graded_by',
    ]
    list_filter = [
        'status',
        'is_late',
        'submitted_at',
        'graded_at',
        'assignment__module__course',
        'graded_by',
    ]
    search_fields = [
        'student__email',
        'student__first_name',
        'student__last_name',
        'assignment__title',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'submitted_at',
        'is_late',
        'resubmission_count',
    ]
    fieldsets = (
        ('Submission Information', {
            'fields': ('student', 'assignment', 'submitted_at', 'is_late', 'resubmission_count')
        }),
        ('Submission Content', {
            'fields': ('submission_file', 'submission_text', 'submission_url')
        }),
        ('Grading', {
            'fields': ('status', 'score', 'feedback', 'graded_by', 'graded_at')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['approve_submissions', 'reject_submissions', 'mark_for_resubmission']
    
    def status_display(self, obj):
        """Display status with color."""
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'resubmit': 'blue',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def is_late_display(self, obj):
        """Display late status."""
        if obj.is_late:
            return format_html('<span style="color: red;">⚠️ Late</span>')
        return format_html('<span style="color: green;">✓ On Time</span>')
    is_late_display.short_description = 'Timing'
    
    def approve_submissions(self, request, queryset):
        """Bulk approve submissions."""
        updated = queryset.filter(status='pending').update(
            status='approved',
            graded_by=request.user,
        )
        self.message_user(request, f"{updated} submissions approved.")
    approve_submissions.short_description = "Approve selected submissions"
    
    def reject_submissions(self, request, queryset):
        """Bulk reject submissions."""
        updated = queryset.filter(status='pending').update(
            status='rejected',
            graded_by=request.user,
        )
        self.message_user(request, f"{updated} submissions rejected.")
    reject_submissions.short_description = "Reject selected submissions"
    
    def mark_for_resubmission(self, request, queryset):
        """Mark submissions for resubmission."""
        updated = queryset.update(
            status='resubmit',
            graded_by=request.user,
        )
        self.message_user(request, f"{updated} submissions marked for resubmission.")
    mark_for_resubmission.short_description = "Mark for resubmission"


@admin.register(StudentModuleProgress)
class StudentModuleProgressAdmin(BaseAdmin):
    """Admin interface for student module progress."""
    list_display = [
        'student',
        'module',
        'is_completed_display',
        'completed_at',
        'marked_by',
    ]
    list_filter = [
        'is_completed',
        'completed_at',
        'module__course',
        'marked_by',
    ]
    search_fields = [
        'student__email',
        'student__first_name',
        'student__last_name',
        'module__title',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    fieldsets = (
        ('Progress Information', {
            'fields': ('student', 'module', 'is_completed', 'completed_at')
        }),
        ('Teacher Notes', {
            'fields': ('marked_by', 'notes')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_as_completed', 'mark_as_incomplete']
    
    def is_completed_display(self, obj):
        """Display completion status with icon."""
        if obj.is_completed:
            return format_html('<span style="color: green; font-size: 16px;">✓ Complete</span>')
        return format_html('<span style="color: orange;">⏳ In Progress</span>')
    is_completed_display.short_description = 'Status'
    
    def mark_as_completed(self, request, queryset):
        """Bulk mark modules as completed."""
        for progress in queryset:
            progress.is_completed = True
            progress.marked_by = request.user
            progress.save()
        self.message_user(request, f"{queryset.count()} modules marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_incomplete(self, request, queryset):
        """Bulk mark modules as incomplete."""
        updated = queryset.update(is_completed=False, completed_at=None)
        self.message_user(request, f"{updated} modules marked as incomplete.")
    mark_as_incomplete.short_description = "Mark as incomplete"


@admin.register(CourseProgress)
class CourseProgressAdmin(BaseAdmin):
    """Admin interface for overall course progress."""
    list_display = [
        'student',
        'course',
        'completion_percentage_display',
        'is_completed_display',
        'certificate_issued_display',
        'last_activity_at',
    ]
    list_filter = [
        'is_completed',
        'certificate_issued',
        'completed_at',
        'course',
        'last_activity_at',
    ]
    search_fields = [
        'student__email',
        'student__first_name',
        'student__last_name',
        'course__title',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'last_activity_at',
        'completed_at',
        'get_progress_breakdown',
    ]
    fieldsets = (
        ('Progress Information', {
            'fields': ('student', 'course', 'enrollment')
        }),
        ('Completion Details', {
            'fields': (
                'completion_percentage',
                'is_completed',
                'completed_at',
                'get_progress_breakdown',
            )
        }),
        ('Certificate', {
            'fields': ('certificate_issued', 'certificate_issued_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'last_activity_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['recalculate_progress', 'issue_certificates']
    
    def completion_percentage_display(self, obj):
        """Display completion percentage with progress bar."""
        percentage = float(obj.completion_percentage)
        color = 'green' if percentage == 100 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 5px;">'
            '<div style="width: {}%; background: {}; color: white; text-align: center; '
            'border-radius: 5px; padding: 2px;">{:.1f}%</div>'
            '</div>',
            percentage,
            color,
            percentage
        )
    completion_percentage_display.short_description = 'Progress'
    
    def is_completed_display(self, obj):
        """Display completion status."""
        if obj.is_completed:
            return format_html('<span style="color: green; font-weight: bold;">✓ COMPLETED</span>')
        return format_html('<span style="color: orange;">⏳ In Progress</span>')
    is_completed_display.short_description = 'Status'
    
    def certificate_issued_display(self, obj):
        """Display certificate status."""
        if obj.certificate_issued:
            return format_html('<span style="color: green;">✓ Issued</span>')
        return format_html('<span style="color: gray;">Not Issued</span>')
    certificate_issued_display.short_description = 'Certificate'
    
    def get_progress_breakdown(self, obj):
        """Display detailed progress breakdown."""
        if obj.pk:
            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
                '<h3>Progress Breakdown</h3>'
                '<p><strong>Modules:</strong> {} / {} completed ({:.1f}%)</p>'
                '<p><strong>Quizzes:</strong> {} / {} passed ({:.1f}%)</p>'
                '<p><strong>Assignments:</strong> {} / {} approved ({:.1f}%)</p>'
                '<hr>'
                '<p><strong>Overall:</strong> {:.1f}%</p>'
                '</div>',
                obj.modules_completed,
                obj.modules_total,
                (obj.modules_completed / obj.modules_total * 100) if obj.modules_total > 0 else 0,
                obj.quizzes_passed,
                obj.quizzes_total,
                (obj.quizzes_passed / obj.quizzes_total * 100) if obj.quizzes_total > 0 else 0,
                obj.assignments_completed,
                obj.assignments_total,
                (obj.assignments_completed / obj.assignments_total * 100) if obj.assignments_total > 0 else 0,
                obj.completion_percentage
            )
        return "Save to see progress breakdown"
    get_progress_breakdown.short_description = 'Breakdown'
    
    def recalculate_progress(self, request, queryset):
        """Recalculate progress for selected courses."""
        for progress in queryset:
            progress.calculate_completion()
        self.message_user(request, f"Progress recalculated for {queryset.count()} students.")
    recalculate_progress.short_description = "Recalculate progress"
    
    def issue_certificates(self, request, queryset):
        """Issue certificates for completed courses."""
        from django.utils import timezone
        updated = queryset.filter(
            is_completed=True,
            certificate_issued=False
        ).update(
            certificate_issued=True,
            certificate_issued_at=timezone.now()
        )
        self.message_user(request, f"{updated} certificates issued.")
    issue_certificates.short_description = "Issue certificates"
