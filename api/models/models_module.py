import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from django_ckeditor_5.fields import CKEditor5Field

from api.models.models_course import CourseBatch, CourseModule
from api.utils.helper_models import TimeStampedModel


# Live Classes within a module
class LiveClass(models.Model):
    """Live classes scheduled for a course module."""

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    module = models.ForeignKey(
        "CourseModule",
        related_name="live_classes",
        on_delete=models.CASCADE,
    )

    batch = models.ForeignKey(
        "CourseBatch",
        related_name="live_classes",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        help_text="Batch this live class belongs to (required)",
    )

    title = models.CharField(max_length=200)

    description = CKEditor5Field(
        blank=True,
        null=True,
        help_text="Description of what will be covered",
    )

    scheduled_date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)

    meeting_url = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=100, blank=True)
    meeting_password = models.CharField(max_length=50, blank=True)

    recording_url = models.URLField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )

    order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_classes",
        limit_choices_to={"role__in": ["teacher", "admin", "superadmin"]},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Live Class"
        verbose_name_plural = "15. Live Classes"
        ordering = ["module", "order"]
        unique_together = ["module", "batch", "order"]

    def __str__(self):
        return f"{self.module.title} | {self.batch.get_display_name} | {self.title}"


# Attendance tracking for live classes
class LiveClassAttendance(TimeStampedModel):
    """Track student attendance for live classes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_class = models.ForeignKey(LiveClass, related_name="attendances", on_delete=models.CASCADE)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="class_attendances",
        limit_choices_to={"role": "student"},
    )
    attended = models.BooleanField(default=False)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0, help_text="How long the student attended (in minutes)")

    class Meta:
        verbose_name = "Live Class Attendance"
        verbose_name_plural = "16. Live Class Attendances"
        unique_together = ["live_class", "student"]

    def __str__(self):
        return f"{self.student.get_full_name} - {self.live_class.title}"


# Assignments within a module
class Assignment(TimeStampedModel):
    """Assignments for students within a course module."""

    TYPE_CHOICES = [
        ("written", "Written Assignment"),
        ("coding", "Coding Assignment"),
        ("project", "Project"),
        ("quiz", "Quiz"),
        ("presentation", "Presentation"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey("CourseModule", related_name="module_assignments", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = CKEditor5Field(help_text="Detailed assignment instructions and requirements")
    assignment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="written")

    # Files and resources
    attachment = models.FileField(
        upload_to="assignments/attachments/",
        blank=True,
        null=True,
        help_text="Reference materials or assignment file",
    )

    # Grading
    total_marks = models.PositiveIntegerField(default=100, help_text="Maximum marks for this assignment")
    passing_marks = models.PositiveIntegerField(default=40, help_text="Minimum marks required to pass")

    # Deadlines
    due_date = models.DateTimeField(help_text="Submission deadline")
    late_submission_allowed = models.BooleanField(default=True, help_text="Allow submissions after due date")
    late_submission_penalty = models.PositiveIntegerField(default=10, help_text="Percentage penalty for late submission")

    order = models.PositiveIntegerField(help_text="Order of this assignment within the module")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_assignments",
        limit_choices_to={"role__in": ["teacher", "admin", "superadmin"]},
    )

    batch = models.ForeignKey(
        "CourseBatch",
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text="Specific batch this assignment is for (optional - leave blank for all batches)",
    )

    class Meta:
        verbose_name = "Assignment"
        verbose_name_plural = "17. Assignments"
        ordering = ["module", "order"]
        unique_together = [
            "module",
            "batch",
            "order",
        ]  # Allow same order for different batches

    def __str__(self):
        return f"{self.module.title} - {self.title}"


# Student assignment submissions
class AssignmentSubmission(TimeStampedModel):
    """Student submissions for assignments."""

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("submitted", "Submitted"),
        ("graded", "Graded"),
        ("resubmit", "Needs Resubmission"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, related_name="submissions", on_delete=models.CASCADE)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="module_assignment_submissions",
        limit_choices_to={"role": "student"},
    )

    # Submission
    submission_text = CKEditor5Field(blank=True, null=True, help_text="Text answer or description")
    submission_file = models.FileField(
        upload_to="assignments/submissions/",
        blank=True,
        null=True,
        help_text="Uploaded assignment file",
    )
    submission_url = models.URLField(blank=True, help_text="URL for online submissions (GitHub, Google Drive, etc.)")

    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False, help_text="Whether this submission was after the deadline")

    # Grading
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Marks awarded by instructor",
    )
    feedback = CKEditor5Field(blank=True, null=True, help_text="Instructor's feedback")
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="module_graded_assignments",
        limit_choices_to={"role__in": ["teacher", "admin", "superadmin"]},
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assignment Submission"
        verbose_name_plural = "Assignment Submissions"
        unique_together = ["assignment", "student"]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student.get_full_name} - {self.assignment.title}"

#===========================================
# Quiz/Test within a module
#===========================================


class Quiz(TimeStampedModel):
    """Quiz or test for a course module."""

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey("CourseModule", related_name="module_quizzes", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = CKEditor5Field(blank=True, null=True, help_text="Instructions and overview for the quiz")

    # Quiz settings
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=40)
    duration_minutes = models.PositiveIntegerField(default=30, help_text="Time limit for the quiz in minutes")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="medium")

    # Attempt settings
    max_attempts = models.PositiveIntegerField(default=1, help_text="Maximum number of attempts allowed")
    show_correct_answers = models.BooleanField(default=True, help_text="Show correct answers after submission")
    randomize_questions = models.BooleanField(default=False, help_text="Randomize question order for each attempt")

    # Availability
    available_from = models.DateTimeField(null=True, blank=True, help_text="When the quiz becomes available")
    available_until = models.DateTimeField(null=True, blank=True, help_text="When the quiz closes")

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_quizzes",
        limit_choices_to={"role__in": ["teacher", "admin", "superadmin"]},
    )

    batch = models.ForeignKey(
        "CourseBatch",
        on_delete=models.CASCADE,
        related_name="quizzes",
        help_text="Specific batch this quiz is for (optional - leave blank for all batches)",
    )

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "18. Course Quizzes"
        ordering = ["module", "title"]

    def __str__(self):
        return f"{self.module.title} - {self.title}"


# Quiz questions
class QuizQuestion(TimeStampedModel):
    """Individual questions within a quiz."""

    QUESTION_TYPE_CHOICES = [
        ("mcq", "Multiple Choice (Single Answer)"),
        ("multiple", "Multiple Choice (Multiple Answers)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, related_name="questions", on_delete=models.CASCADE)
    question_text = CKEditor5Field(help_text="The question text (supports rich formatting)")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default="mcq")

    marks = models.PositiveIntegerField(default=1, help_text="Points for this question")
    order = models.PositiveIntegerField(help_text="Display order of the question")

    explanation = CKEditor5Field(blank=True, null=True, help_text="Explanation shown after answering")

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Quiz Question"
        verbose_name_plural = "20. Quiz Questions"
        ordering = ["quiz", "order"]
        unique_together = ["quiz", "order"]

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"


# Quiz question options (for MCQ)
class QuizQuestionOption(TimeStampedModel):
    """Answer options for multiple choice questions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(QuizQuestion, related_name="options", on_delete=models.CASCADE)
    option_text = models.TextField(help_text="The answer option text")
    is_correct = models.BooleanField(default=False, help_text="Check if this is a correct answer")
    order = models.PositiveIntegerField(help_text="Display order of the option")

    class Meta:
        verbose_name = "Quiz Question Option"
        verbose_name_plural = "21. Quiz Question Options"
        ordering = ["question", "order"]

    def __str__(self):
        return f"{self.question.question_text[:30]} - Option {self.order}"


# Student quiz attempts
class QuizAttempt(TimeStampedModel):
    """Record of a student's quiz attempt."""

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("submitted", "Submitted"),
        ("graded", "Graded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, related_name="attempts", on_delete=models.CASCADE)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="module_quiz_attempts",
        limit_choices_to={"role": "student"},
    )

    attempt_number = models.PositiveIntegerField(default=1, help_text="Which attempt this is (1, 2, 3...)")

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")

    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    passed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Quiz Attempt"
        verbose_name_plural = "22. Quiz Attempts"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student.get_full_name} - {self.quiz.title} (Attempt {self.attempt_number})"


# Student answers for quiz questions
class QuizAnswer(TimeStampedModel):
    """Individual answers within a quiz attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(QuizAttempt, related_name="answers", on_delete=models.CASCADE)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)

    selected_options = models.ManyToManyField(QuizQuestionOption, blank=True, help_text="Selected answer options (for MCQ)")

    is_correct = models.BooleanField(default=False, help_text="Whether the answer is correct (auto-graded for MCQ)")
    marks_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Marks given for this answer",
    )

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz Answer"
        verbose_name_plural = "23. Quiz Answers"
        unique_together = ["attempt", "question"]

    def __str__(self):
        return f"{self.attempt.student.get_full_name} - Q{self.question.order}"


# ========== Course Resources/Materials ==========


class CourseResource(TimeStampedModel):
    """
    Study materials / resources for a module or live class.
    Batch-isolated, student-safe, and production-ready.
    """

    RESOURCE_TYPE_CHOICES = [
        ("pd", "PDF Document"),
        ("video", "Video"),
        ("slide", "Presentation Slides"),
        ("code", "Code / Project Files"),
        ("document", "Document"),
        ("link", "External Link"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ---------- Relationships ----------
    module = models.ForeignKey(
        CourseModule,
        related_name="resources",
        on_delete=models.CASCADE,
        help_text="Module this resource belongs to",
    )

    batch = models.ForeignKey(
        CourseBatch,
        related_name="resources",
        on_delete=models.CASCADE,
        help_text="Batch this resource belongs to",
    )

    live_class = models.ForeignKey(
        LiveClass,
        related_name="resources",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional: Link to a specific live class",
    )

    # ---------- Resource details ----------
    title = models.CharField(max_length=200)
    description = CKEditor5Field(blank=True, null=True)

    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPE_CHOICES,
        default="document",
    )

    # ---------- File or URL ----------
    file = models.FileField(
        upload_to="course_resources/",
        blank=True,
        null=True,
        help_text="Optional single file upload",
    )
    external_url = models.URLField(
        blank=True,
        null=True,
        help_text="External link (Drive, YouTube, etc.)",
    )

    # ---------- Metadata ----------
    file_size = models.BigIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)

    # ---------- Display ----------
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # ---------- Tracking ----------
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_resources",
        limit_choices_to={"role__in": ["teacher", "admin", "superadmin"]},
    )

    class Meta:
        verbose_name = "Course Resource"
        verbose_name_plural = "20. Course Resources"
        ordering = ["order", "-created_at"]

        # Prevent duplicate ordering per batch
        unique_together = ["module", "batch", "order"]

        # ✅ Performance indexes
        indexes = [
            models.Index(fields=["module", "batch", "is_active"]),
            models.Index(fields=["module", "batch", "order"]),
            models.Index(fields=["live_class"]),
        ]

    def __str__(self):
        return f"{self.module.title} | {self.title}"

    # ---------- Validation ----------
    def clean(self):
        """
        Enforce that at least one content source exists:
        - file
        - external_url
        - attached files
        """
        has_attached_files = self.pk and self.files.exists()

        if not self.file and not self.external_url and not has_attached_files:
            raise ValidationError("A resource must have a file, external URL, or attached files.")

    # ---------- Helpers ----------
    def increment_download_count(self):
        self.download_count += 1
        self.save(update_fields=["download_count"])

    def get_file_size_display(self):
        if not self.file_size:
            return "Unknown"

        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return "Unknown"


class CourseResourceFile(models.Model):
    """
    Individual files attached to a CourseResource.
    Enables multi-file uploads per resource.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    resource = models.ForeignKey(
        CourseResource,
        related_name="files",
        on_delete=models.CASCADE,
    )

    file = models.FileField(
        upload_to="course_resources/files/",
        help_text="Attached resource file",
    )

    file_size = models.BigIntegerField(null=True, blank=True)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Course Resource File"
        verbose_name_plural = "Course Resource Files"
        ordering = ["order", "created_at"]

        indexes = [
            models.Index(fields=["resource", "order"]),
        ]

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.resource.title} - {self.file.name}"
