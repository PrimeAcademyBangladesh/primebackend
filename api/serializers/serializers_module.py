"""Serializers for course modules, live classes, assignments, and quizzes."""

from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from api.models.models_course import CourseModule
from api.models.models_module import (
    LiveClass,
    LiveClassAttendance,
    Assignment,
    AssignmentSubmission,
    Quiz,
    QuizQuestion,
    QuizQuestionOption,
    QuizAttempt,
    QuizAnswer,
    CourseResource,
    CourseResourceFile,
)

from api.serializers.serializers_helpers import HTMLFieldsMixin


# ========== Live Class Serializers ==========


class LiveClassSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for live classes within a module."""

    html_fields = ["description"]

    instructor_name = serializers.CharField(
        source="instructor.get_full_name", read_only=True, allow_null=True
    )
    instructor_email = serializers.EmailField(
        source="instructor.email", read_only=True, allow_null=True
    )

    # Helper fields
    is_upcoming = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()
    has_recording = serializers.SerializerMethodField()
    attendance_marked = (
        serializers.SerializerMethodField()
    )  # NEW: Student attendance status
    has_enrollment = (
        serializers.SerializerMethodField()
    )  # NEW: Check if student is enrolled
    batch_info = serializers.SerializerMethodField()  # NEW: Student's batch information

    class Meta:
        model = LiveClass
        fields = [
            "id",
            "title",
            "description",
            "scheduled_date",
            "duration_minutes",
            "meeting_url",
            "meeting_id",
            "meeting_password",
            "recording_url",
            "status",
            "order",
            "is_active",
            "instructor_name",
            "instructor_email",
            "is_upcoming",
            "is_past",
            "can_join",
            "has_recording",
            "attendance_marked",  # NEW
            "has_enrollment",  # NEW
            "batch_info",  # NEW
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_upcoming(self, obj):
        """Check if class is upcoming (scheduled in future)"""
        return obj.scheduled_date > timezone.now() and obj.status == "scheduled"

    def get_is_past(self, obj):
        """Check if class is in the past"""
        return obj.scheduled_date < timezone.now() or obj.status == "completed"

    def get_can_join(self, obj):
        """Check if student can join now (10 mins before start until class ends)"""
        now = timezone.now()
        start_time = obj.scheduled_date
        end_time = start_time + timezone.timedelta(minutes=obj.duration_minutes)
        grace_period = timezone.timedelta(minutes=10)

        return (start_time - grace_period) <= now <= end_time and obj.status in [
            "scheduled",
            "ongoing",
        ]

    def get_has_recording(self, obj):
        """Check if recording is available"""
        return bool(obj.recording_url)

    def get_attendance_marked(self, obj):
        """Check if current student has marked attendance"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        try:
            attendance = LiveClassAttendance.objects.filter(
                live_class=obj, student=request.user, attended=True
            ).exists()
            return attendance
        except Exception:
            return False

    def get_has_enrollment(self, obj):
        """Check if current student is enrolled in the course"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        try:
            from api.models.models_order import Enrollment

            return Enrollment.objects.filter(
                user=request.user, course=obj.module.course.course, is_active=True
            ).exists()
        except Exception:
            return False

    def get_batch_info(self, obj):
        """Get student's batch information for this course"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            from api.models.models_order import Enrollment

            enrollment = (
                Enrollment.objects.filter(
                    user=request.user, course=obj.module.course.course, is_active=True
                )
                .select_related("batch")
                .first()
            )

            if enrollment and enrollment.batch:
                return {
                    "id": str(enrollment.batch.id),
                    "batch_number": enrollment.batch.batch_number,
                    "batch_name": enrollment.batch.batch_name,
                    "display_name": enrollment.batch.display_name,
                    "start_date": enrollment.batch.start_date,
                    "end_date": enrollment.batch.end_date,
                }
            return None
        except Exception:
            return None


class LiveClassCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Teacher/Admin only
    Batch is mandatory
    """

    class Meta:
        model = LiveClass
        fields = [
            "module",
            "batch",
            "title",
            "description",
            "scheduled_date",
            "duration_minutes",
            "meeting_url",
            "meeting_id",
            "meeting_password",
            "recording_url",
            "status",
            "order",
            "is_active",
            "instructor",
        ]

    def validate_batch(self, value):
        if not value:
            raise serializers.ValidationError(
                "Batch is required to create a live class."
            )
        return value


class LiveClassAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for live class attendance tracking."""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_email = serializers.EmailField(source="student.email", read_only=True)
    class_title = serializers.CharField(source="live_class.title", read_only=True)

    class Meta:
        model = LiveClassAttendance
        fields = [
            "id",
            "live_class",
            "student",
            "student_name",
            "student_email",
            "class_title",
            "attended",
            "joined_at",
            "left_at",
            "duration_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ========== Assignment Serializers ==========
class AssignmentListSerializer(serializers.ModelSerializer):
    module_id = serializers.UUIDField(source="module.id", read_only=True)
    module_title = serializers.CharField(source="module.title", read_only=True)

    batch_id = serializers.UUIDField(source="batch.id", read_only=True)
    batch_name = serializers.CharField(source="batch.display_name", read_only=True)

    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "module_id",
            "module_title",
            "batch_id",
            "batch_name",
            "title",
            "assignment_type",
            "due_date",
            "total_marks",
            "order",
            "is_active",
            "is_overdue",
        ]

    def get_is_overdue(self, obj):
        return bool(obj.due_date and timezone.now() > obj.due_date)


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Teacher/Admin only
    Batch is REQUIRED at API level
    """

    class Meta:
        model = Assignment
        fields = [
            "module",
            "batch",
            "title",
            "description",
            "assignment_type",
            "attachment",
            "total_marks",
            "passing_marks",
            "due_date",
            "late_submission_allowed",
            "late_submission_penalty",
            "order",
            "is_active",
        ]

    def validate_batch(self, value):
        if not value:
            raise serializers.ValidationError(
                "Batch is required when creating an assignment."
            )
        return value


class AssignmentStudentSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    html_fields = ["description"]

    module_title = serializers.CharField(source="module.title", read_only=True)

    is_overdue = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    has_submitted = serializers.SerializerMethodField()
    submission_status = serializers.SerializerMethodField()
    submission_date = serializers.SerializerMethodField()
    obtained_marks = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "module_title",
            "title",
            "description",
            "assignment_type",
            "attachment_url",
            "total_marks",
            "passing_marks",
            "due_date",
            "late_submission_allowed",
            "late_submission_penalty",
            "order",
            "is_active",
            "is_overdue",
            "days_remaining",
            "has_submitted",
            "submission_status",
            "submission_date",
            "obtained_marks",
            "can_submit",
        ]

    # ---------- helpers ----------

    def _submission(self, obj):
        user = self.context["request"].user
        return obj.submissions.filter(student=user).first()

    def get_is_overdue(self, obj):
        return bool(obj.due_date and timezone.now() > obj.due_date)

    def get_days_remaining(self, obj):
        if not obj.due_date:
            return None
        return max(0, (obj.due_date - timezone.now()).days)

    def get_has_submitted(self, obj):
        return bool(self._submission(obj))

    def get_submission_status(self, obj):
        sub = self._submission(obj)
        return sub.status if sub else "pending"

    def get_submission_date(self, obj):
        sub = self._submission(obj)
        return sub.submitted_at if sub else None

    def get_obtained_marks(self, obj):
        sub = self._submission(obj)
        return (
            float(sub.marks_obtained)
            if sub and sub.marks_obtained is not None
            else None
        )

    def get_can_submit(self, obj):
        if not obj.due_date:
            return True
        if timezone.now() <= obj.due_date:
            return True
        return obj.late_submission_allowed

    def get_attachment_url(self, obj):
        request = self.context.get("request")
        if obj.attachment and request:
            return request.build_absolute_uri(obj.attachment.url)
        return None


class AssignmentSubmissionSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for student assignment submissions."""

    html_fields = ["submission_text", "feedback"]

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_email = serializers.EmailField(source="student.email", read_only=True)
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    graded_by_name = serializers.CharField(
        source="graded_by.get_full_name", read_only=True, allow_null=True
    )

    # Helper fields
    percentage = serializers.SerializerMethodField()
    is_passed = serializers.SerializerMethodField()
    can_view_feedback = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "student",
            "student_name",
            "student_email",
            "assignment_title",
            "submission_text",
            "submission_file",
            "submission_url",
            "submitted_at",
            "is_late",
            "status",
            "marks_obtained",
            "feedback",
            "graded_by_name",
            "graded_at",
            "percentage",
            "is_passed",
            "can_view_feedback",
            "updated_at",
        ]
        read_only_fields = ["id", "submitted_at", "updated_at", "is_late"]

    def get_percentage(self, obj):
        """Calculate percentage score"""
        if obj.marks_obtained is not None and obj.assignment.total_marks > 0:
            return round(
                (float(obj.marks_obtained) / obj.assignment.total_marks) * 100, 2
            )
        return None

    def get_is_passed(self, obj):
        """Check if student passed"""
        if obj.marks_obtained is not None:
            return obj.marks_obtained >= obj.assignment.passing_marks
        return False

    def get_can_view_feedback(self, obj):
        """Check if student can view feedback (only after graded)"""
        return obj.status == "graded"


class AssignmentSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for students to submit assignments."""

    class Meta:
        model = AssignmentSubmission
        fields = [
            "submission_text",
            "submission_file",
            "submission_url",
        ]


class AssignmentGradeSerializer(serializers.Serializer):
    """Serializer for teacher to grade assignment."""

    marks_obtained = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0")
    )
    feedback = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=["graded", "resubmit"], default="graded")


# ========== Quiz Serializers ==========


class QuizQuestionOptionSerializer(serializers.ModelSerializer):
    """
    Used for:
    - Teacher: full access
    - Student: is_correct hidden
    """

    class Meta:
        model = QuizQuestionOption
        fields = [
            "id",
            "option_text",
            "option_image",
            "is_correct",
            "order",
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            if getattr(request.user, "role", None) == "student":
                data.pop("is_correct", None)

        return data


class QuizQuestionSerializer(serializers.ModelSerializer):
    """
    Read-only question serializer
    Used when showing quiz details or starting quiz
    """

    options = QuizQuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = [
            "id",
            "question_text",
            "question_type",
            "marks",
            "order",
            "correct_answer_text",
            "explanation",
            "options",
            "is_active",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if getattr(request.user, "role", None) == "student":
                data.pop("correct_answer_text", None)
                data.pop("explanation", None)

        return data


class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, allow_null=True
    )
    module_id = serializers.UUIDField(source="module.id", read_only=True)
    module_title = serializers.CharField(source="module.title", read_only=True)

    batch_id = serializers.UUIDField(source="batch.id", read_only=True, allow_null=True)
    batch_name = serializers.CharField(
        source="batch.display_name", read_only=True, allow_null=True
    )

    question_count = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    attempts_used = serializers.SerializerMethodField()
    can_attempt = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "id",
            "module_id",
            "module_title",
            "batch_id",
            "batch_name",
            "title",
            "description",
            "total_marks",
            "passing_marks",
            "duration_minutes",
            "difficulty",
            "max_attempts",
            "show_correct_answers",
            "randomize_questions",
            "available_from",
            "available_until",
            "is_active",
            "created_by_name",
            "question_count",
            "is_available",
            "attempts_used",
            "can_attempt",
            "best_score",
            "is_completed",
            "questions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _student_attempts(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return QuizAttempt.objects.none()

        if not hasattr(self, "_attempt_cache"):
            self._attempt_cache = {}

        if obj.id not in self._attempt_cache:
            self._attempt_cache[obj.id] = obj.attempts.filter(student=request.user)

        return self._attempt_cache[obj.id]

    def get_question_count(self, obj):
        return obj.questions.filter(is_active=True).count()

    def get_is_available(self, obj):
        now = timezone.now()
        if obj.available_from and now < obj.available_from:
            return False
        if obj.available_until and now > obj.available_until:
            return False
        return obj.is_active

    def get_attempts_used(self, obj):
        return self._student_attempts(obj).filter(status="submitted").count()

    def get_can_attempt(self, obj):
        if not self.get_is_available(obj):
            return False
        if obj.max_attempts <= 0:
            return False
        return self.get_attempts_used(obj) < obj.max_attempts

    def get_best_score(self, obj):
        attempt = (
            self._student_attempts(obj)
            .filter(status="submitted")
            .order_by("-marks_obtained")
            .first()
        )
        return float(attempt.marks_obtained) if attempt else None

    def get_is_completed(self, obj):
        return self.get_attempts_used(obj) > 0


class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    module = serializers.PrimaryKeyRelatedField(queryset=CourseModule.objects.all())

    class Meta:
        model = Quiz
        fields = [
            "module",
            "batch",
            "title",
            "description",
            "total_marks",
            "passing_marks",
            "duration_minutes",
            "difficulty",
            "max_attempts",
            "show_correct_answers",
            "randomize_questions",
            "available_from",
            "available_until",
            "is_active",
        ]

    def validate_batch(self, value):
        if not value:
            raise serializers.ValidationError("Batch is required to create a quiz.")
        return value


class QuizQuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Used ONLY by teacher/admin
    Handles create & update of questions with options
    """

    options = QuizQuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = QuizQuestion
        fields = [
            "id",
            "quiz",
            "question_text",
            "question_type",
            "marks",
            "order",
            "correct_answer_text",
            "explanation",
            "is_active",
            "options",
        ]
        read_only_fields = ["id"]

    # -------------------------
    # CREATE
    # -------------------------
    def create(self, validated_data):
        options_data = validated_data.pop("options", [])
        question = QuizQuestion.objects.create(**validated_data)

        for option in options_data:
            QuizQuestionOption.objects.create(question=question, **option)

        return question

    # -------------------------
    # UPDATE
    # -------------------------
    def update(self, instance, validated_data):
        options_data = validated_data.pop("options", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if options_data is not None:
            instance.options.all().delete()
            for option in options_data:
                QuizQuestionOption.objects.create(question=instance, **option)

        return instance

    # -------------------------
    # VALIDATION
    # -------------------------
    def validate(self, data):
        """
        Validates correctness of options based on question_type.
        Works for both CREATE and UPDATE.
        """

        qtype = data.get("question_type", getattr(self.instance, "question_type", None))

        options = data.get("options", None)

        if options is not None:

            correct_count = sum(1 for o in options if o.get("is_correct"))

            if qtype in ["mcq", "true_false"]:
                if correct_count != 1:
                    raise serializers.ValidationError(
                        "MCQ / True-False questions must have exactly one correct option."
                    )

            elif qtype == "multiple":
                if correct_count < 1:
                    raise serializers.ValidationError(
                        "Multiple choice questions must have at least one correct option."
                    )

            if qtype == "true_false":
                if len(options) != 2:
                    raise serializers.ValidationError(
                        "True/False questions must have exactly two options."
                    )

        return data


class QuizAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "quiz_title",
            "student_name",
            "attempt_number",
            "started_at",
            "submitted_at",
            "status",
            "marks_obtained",
            "percentage",
            "passed",
            "updated_at",
        ]
        read_only_fields = ["id", "started_at", "updated_at"]


class QuizAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(
        source="question.question_text", read_only=True
    )
    correct_answer = serializers.SerializerMethodField()

    class Meta:
        model = QuizAnswer
        fields = [
            "id",
            "question",
            "question_text",
            "selected_options",
            "answer_text",
            "is_correct",
            "marks_awarded",
            "correct_answer",
            "answered_at",
        ]
        read_only_fields = ["id", "answered_at"]

    def get_correct_answer(self, obj):
        if not obj.attempt.quiz.show_correct_answers:
            return None

        if obj.question.question_type in ["mcq", "multiple", "true_false"]:
            return QuizQuestionOptionSerializer(
                obj.question.options.filter(is_correct=True),
                many=True,
                context=self.context,
            ).data

        return obj.question.correct_answer_text

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        if request and getattr(request.user, "role", None) == "student":
            data.pop("is_correct", None)

        return data


# ========== Course Resource Serializers ==========

from rest_framework import serializers
from api.models.models_module import CourseResourceFile


class CourseResourceFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = CourseResourceFile
        fields = [
            "id",
            "file",
            "file_url",
            "file_size",
            "file_size_display",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "file_size", "created_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_size_display(self, obj):
        if not obj.file_size:
            return "Unknown"

        size = float(obj.file_size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return "Unknown"


class CourseResourceSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    html_fields = ["description"]

    module_title = serializers.CharField(source="module.title", read_only=True)
    batch_name = serializers.CharField(source="batch.display_name", read_only=True)

    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    files = CourseResourceFileSerializer(many=True, read_only=True)

    can_download = serializers.SerializerMethodField()

    class Meta:
        model = CourseResource
        fields = [
            "id",
            "module",
            "module_title",
            "batch",
            "batch_name",
            "live_class",
            "title",
            "description",
            "resource_type",
            "file_url",
            "external_url",
            "file_size_display",
            "files",
            "download_count",
            "order",
            "is_active",
            "can_download",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "download_count",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_size_display(self, obj):
        return obj.get_file_size_display()

    def get_can_download(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated)


class CourseResourceCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseResource
        fields = [
            "module",
            "batch",
            "live_class",
            "title",
            "description",
            "resource_type",
            "file",
            "external_url",
            "order",
            "is_active",
        ]

    def validate(self, attrs):
        file = attrs.get("file")
        external_url = attrs.get("external_url")

        if not file and not external_url:
            return attrs

        return attrs


class CourseResourceFileCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseResourceFile
        fields = [
            "resource",
            "file",
            "order",
        ]


# ========== Module with Complete Content Serializer ==========


# ========== Module with Complete Content (STUDENT STUDY PLAN) ==========


class CourseModuleStudentStudyPlanSerializer(
    HTMLFieldsMixin, serializers.ModelSerializer
):
    """
    Student-facing Study Plan serializer

    Used ONLY for:
    GET /api/courses/{course_slug}/study-plan/{module_slug}/

    Provides everything needed to render:
    - Module accordion
    - Assignments
    - Quizzes
    - Live classes
    - Resources
    """

    html_fields = ["short_description"]

    # ---- Content blocks ----
    live_classes = LiveClassSerializer(many=True, read_only=True)
    assignments = AssignmentStudentSerializer(many=True, read_only=True)
    quizzes = QuizSerializer(many=True, read_only=True)
    resources = CourseResourceSerializer(
        many=True,
        read_only=True,
    )

    live_class_count = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()
    quiz_count = serializers.SerializerMethodField()
    resource_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "order",
            "is_active",
            # content
            "live_classes",
            "assignments",
            "quizzes",
            "resources",
            # counts
            "live_class_count",
            "assignment_count",
            "quiz_count",
            "resource_count",
        ]
        read_only_fields = ["id", "slug"]

    def get_live_class_count(self, obj):
        return obj.live_classes.filter(is_active=True).count()

    def get_assignment_count(self, obj):
        return obj.assignments.filter(is_active=True).count()

    def get_quiz_count(self, obj):
        from django.db.models import Count, Q

        return (
            obj.quizzes.filter(is_active=True)
            .annotate(
                active_question_count=Count(
                    "questions", filter=Q(questions__is_active=True)
                )
            )
            .filter(active_question_count__gt=0)
            .count()
        )

    def get_resource_count(self, obj):
        return obj.resources.filter(is_active=True).count()
