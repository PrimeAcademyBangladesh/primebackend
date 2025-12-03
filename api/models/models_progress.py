"""Course Progress Tracking Models

This module handles student progress tracking including:
- Module quizzes and quiz attempts
- Module assignments and submissions
- Student module completion tracking
- Overall course progress calculation
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from api.utils.helper_models import TimeStampedModel


# OLD Models Removed (ModuleQuiz, StudentQuizAttempt, ModuleAssignment, StudentAssignmentSubmission)
# Use NEW models in models_module.py instead:
# - Quiz, QuizQuestion, QuizAttempt, QuizAnswer
# - Assignment, AssignmentSubmission
# - LiveClass, LiveClassAttendance

class StudentModuleProgress(TimeStampedModel):
    """Tracks student progress through individual course modules.
    
    Teachers mark modules as completed after reviewing quizzes and assignments.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'api.CustomUser',
        related_name='module_progress',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        help_text='Student whose progress is tracked'
    )
    module = models.ForeignKey(
        'api.CourseModule',
        related_name='student_progress',
        on_delete=models.CASCADE,
        help_text='Module being tracked'
    )
    is_completed = models.BooleanField(
        default=False,
        help_text='Whether student completed this module'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When module was marked complete'
    )
    marked_by = models.ForeignKey(
        'api.CustomUser',
        null=True,
        blank=True,
        related_name='marked_module_completions',
        on_delete=models.SET_NULL,
        limit_choices_to={'role': 'teacher'},
        help_text='Teacher who marked module as complete'
    )
    notes = models.TextField(
        blank=True,
        help_text='Teacher notes on student progress'
    )
    
    class Meta:
        verbose_name = 'Student Module Progress'
        verbose_name_plural = 'Student Module Progress'
        ordering = ['module__order']
        unique_together = ['student', 'module']
        indexes = [
            models.Index(fields=['student', 'module']),
            models.Index(fields=['module', 'is_completed']),
            models.Index(fields=['student', 'is_completed']),
        ]
    
    def __str__(self):
        status = "✓ Complete" if self.is_completed else "⏳ In Progress"
        return f"{self.student.email} - {self.module.title} ({status})"
    
    def save(self, *args, **kwargs):
        """Auto-set completed_at timestamp"""
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.is_completed:
            self.completed_at = None
        
        super().save(*args, **kwargs)
    
    def check_auto_complete(self):
        """Check if module can be auto-completed based on quiz/assignment completion"""
        # Get all active quizzes and assignments for this module
        active_quizzes = self.module.quizzes.filter(is_active=True)
        active_assignments = self.module.assignments.filter(is_active=True)
        
        # Check if student passed all quizzes
        for quiz in active_quizzes:
            if not quiz.attempts.filter(student=self.student, is_passed=True).exists():
                return False
        
        # Check if student completed all assignments
        for assignment in active_assignments:
            if not assignment.submissions.filter(
                student=self.student,
                status='approved'
            ).exists():
                return False
        
        # All requirements met
        return True


class CourseProgress(TimeStampedModel):
    """Tracks overall student progress through a course.
    
    Calculates completion percentage based on modules, quizzes, and assignments.
    Auto-updates when student completes requirements.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'api.CustomUser',
        related_name='course_progress',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},
        help_text='Student whose progress is tracked'
    )
    course = models.ForeignKey(
        'api.Course',
        related_name='student_progress',
        on_delete=models.CASCADE,
        help_text='Course being tracked'
    )
    enrollment = models.OneToOneField(
        'api.Enrollment',
        null=True,
        blank=True,
        related_name='progress',
        on_delete=models.CASCADE,
        help_text='Related enrollment record'
    )
    completion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Overall completion percentage (0-100%)'
    )
    modules_completed = models.PositiveIntegerField(
        default=0,
        help_text='Number of modules completed'
    )
    modules_total = models.PositiveIntegerField(
        default=0,
        help_text='Total number of active modules'
    )
    quizzes_passed = models.PositiveIntegerField(
        default=0,
        help_text='Number of quizzes passed'
    )
    quizzes_total = models.PositiveIntegerField(
        default=0,
        help_text='Total number of active quizzes'
    )
    assignments_completed = models.PositiveIntegerField(
        default=0,
        help_text='Number of assignments approved'
    )
    assignments_total = models.PositiveIntegerField(
        default=0,
        help_text='Total number of active assignments'
    )
    is_completed = models.BooleanField(
        default=False,
        help_text='Whether student completed 100% of course'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When course was completed'
    )
    certificate_issued = models.BooleanField(
        default=False,
        help_text='Whether completion certificate was issued'
    )
    certificate_issued_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When certificate was issued'
    )
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text='Last time progress was updated'
    )
    
    class Meta:
        verbose_name = 'Course Progress'
        verbose_name_plural = 'Course Progress Records'
        ordering = ['-last_activity_at']
        unique_together = ['student', 'course']
        indexes = [
            models.Index(fields=['student', 'course']),
            models.Index(fields=['course', 'is_completed']),
            models.Index(fields=['student', 'is_completed']),
            models.Index(fields=['-last_activity_at']),
        ]
    
    def __str__(self):
        return f"{self.student.email} - {self.course.title} ({self.completion_percentage}%)"
    
    def calculate_completion(self):
        """
        Calculate course completion based on module completion only.
        
        ⚠️ OLD quiz/assignment tracking removed.
        Use NEW system for quiz/assignment progress:
        - Quiz model from models_module.py
        - Assignment model from models_module.py
        - QuizAttempt and AssignmentSubmission for progress
        """
        total_items = 0
        completed_items = 0
        
        # Get course modules through CourseDetail
        try:
            course_detail = self.course.detail
            modules = course_detail.modules.filter(is_active=True)
        except:
            modules = []
        
        # 1. Module completion (teacher marks as done)
        self.modules_total = modules.count()
        self.modules_completed = StudentModuleProgress.objects.filter(
            student=self.student,
            module__in=modules,
            is_completed=True
        ).count()
        total_items += self.modules_total
        completed_items += self.modules_completed
        
        # OLD quiz/assignment progress removed - use NEW system
        self.quizzes_total = 0
        self.quizzes_passed = 0
        self.assignments_total = 0
        self.assignments_completed = 0
        
        # Calculate percentage
        if total_items == 0:
            self.completion_percentage = Decimal('0.00')
        else:
            percentage = (completed_items / total_items) * 100
            self.completion_percentage = Decimal(str(round(percentage, 2)))
        
        # Check if course is completed
        was_completed = self.is_completed
        self.is_completed = self.completion_percentage == Decimal('100.00')
        
        # Set completion timestamp if just completed
        if self.is_completed and not was_completed:
            self.completed_at = timezone.now()
        elif not self.is_completed:
            self.completed_at = None
        
        self.save()
        
        return self.completion_percentage
    
    def get_next_incomplete_module(self):
        """Get the next incomplete module for this student"""
        try:
            course_detail = self.course.detail
            modules = course_detail.modules.filter(is_active=True).order_by('order')
        except:
            return None
        
        for module in modules:
            progress, _ = StudentModuleProgress.objects.get_or_create(
                student=self.student,
                module=module
            )
            if not progress.is_completed:
                return module
        
        return None
    
    # REMOVED: get_pending_quizzes() used old ModuleQuiz model
    def get_pending_quizzes(self):
        """DEPRECATED: Use NEW Quiz model."""
        return []
    # REMOVED: get_pending_assignments() used old ModuleAssignment model
    def get_pending_assignments(self):
        """DEPRECATED: Use NEW Assignment model."""
        return []
