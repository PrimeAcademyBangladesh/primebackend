"""Serializers for course modules, live classes, assignments, and quizzes."""

from rest_framework import serializers
from django.utils import timezone

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
)
from api.models.models_course import CourseModule
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
    """Serializer for creating/updating live classes (admin/teacher use)."""

    class Meta:
        model = LiveClass
        fields = [
            "module",
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


class AssignmentSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for assignments within a module."""

    html_fields = ["description"]

    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, allow_null=True
    )

    # Helper fields
    is_overdue = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    has_submitted = (
        serializers.SerializerMethodField()
    )  # NEW: Student submission status
    submission_status = (
        serializers.SerializerMethodField()
    )  # NEW: pending|submitted|graded
    submission_date = serializers.SerializerMethodField()  # NEW: When submitted
    obtained_marks = serializers.SerializerMethodField()  # NEW: Grade received
    can_submit = serializers.SerializerMethodField()  # NEW: Check deadline
    attachment_url = serializers.SerializerMethodField()  # NEW: Assignment file URL
    has_enrollment = (
        serializers.SerializerMethodField()
    )  # NEW: Check if student is enrolled
    batch_info = serializers.SerializerMethodField()  # NEW: Student's batch information

    class Meta:
        model = Assignment
        fields = [
            "id",
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
            "created_by_name",
            "is_overdue",
            "days_remaining",
            "submission_count",
            "has_submitted",  # NEW
            "submission_status",  # NEW
            "submission_date",  # NEW
            "obtained_marks",  # NEW
            "can_submit",  # NEW
            "attachment_url",  # NEW
            "has_enrollment",  # NEW
            "batch_info",  # NEW
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_overdue(self, obj):
        """Check if assignment is past due date"""
        if obj.due_date:
            return timezone.now() > obj.due_date
        return False

    def get_days_remaining(self, obj):
        """Calculate days remaining until due date"""
        if obj.due_date:
            delta = obj.due_date - timezone.now()
            return max(0, delta.days)
        return None

    def get_submission_count(self, obj):
        """Get number of submissions"""
        return obj.submissions.count()

    def get_has_submitted(self, obj):
        """Check if current student has submitted"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        try:
            return obj.submissions.filter(student=request.user).exists()
        except Exception:
            return False

    def get_submission_status(self, obj):
        """Get submission status for current student"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.status if submission else None
        except Exception:
            return None

    def get_submission_date(self, obj):
        """Get submission date for current student"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.submitted_at if submission else None
        except Exception:
            return None

    def get_obtained_marks(self, obj):
        """Get marks obtained by current student"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            submission = obj.submissions.filter(student=request.user).first()
            return (
                float(submission.marks_obtained)
                if submission and submission.marks_obtained is not None
                else None
            )
        except Exception:
            return None

    def get_can_submit(self, obj):
        """Check if student can still submit"""
        if not obj.due_date:
            return True

        now = timezone.now()
        if now <= obj.due_date:
            return True

        # Check if late submission is allowed
        return obj.late_submission_allowed

    def get_attachment_url(self, obj):
        """Get full URL for attachment file"""
        if obj.attachment:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None

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


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating assignments (admin/teacher use)."""

    class Meta:
        model = Assignment
        fields = [
            "module",
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
        max_digits=6, decimal_places=2, min_value=0
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
            "question_image",
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
            QuizQuestionOption.objects.create(
                question=question,
                **option
            )

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
                QuizQuestionOption.objects.create(
                    question=instance,
                    **option
                )

        return instance

    # -------------------------
    # VALIDATION
    # -------------------------
    def validate(self, data):
        """
        Validates correctness of options based on question_type.
        Works for both CREATE and UPDATE.
        """

        qtype = data.get(
            "question_type",
            getattr(self.instance, "question_type", None)
        )

        options = data.get("options", None)

        if options is not None:

            correct_count = sum(
                1 for o in options if o.get("is_correct")
            )

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


# ========== Module with Complete Content Serializer ==========


class CourseModuleDetailSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Complete serializer for course module with all content (live classes, assignments, quizzes)."""

    html_fields = ["short_description"]

    live_classes = LiveClassSerializer(many=True, read_only=True)
    assignments = AssignmentSerializer(many=True, read_only=True)
    quizzes = QuizSerializer(many=True, read_only=True)

    # Summary fields
    live_class_count = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()
    quiz_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "title",
            "short_description",
            "order",
            "is_active",
            "live_classes",
            "assignments",
            "quizzes",
            "live_class_count",
            "assignment_count",
            "quiz_count",
        ]
        read_only_fields = ["id"]

    def get_live_class_count(self, obj):
        """Count active live classes"""
        return obj.live_classes.filter(is_active=True).count()

    def get_assignment_count(self, obj):
        """Count active assignments with proper content"""
        from django.db.models import Q

        return (
            obj.assignments.filter(is_active=True)
            .exclude(
                Q(title__isnull=True)
                | Q(title="")
                | Q(description__isnull=True)
                | Q(description="")
            )
            .count()
        )

    def get_quiz_count(self, obj):
        """Count active quizzes with at least one active question"""
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


# ========== Course Resource Serializers ==========


class CourseResourceSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for course resources/materials."""

    html_fields = ["description"]

    uploaded_by_name = serializers.CharField(
        source="uploaded_by.get_full_name", read_only=True, allow_null=True
    )
    live_class_title = serializers.CharField(
        source="live_class.title", read_only=True, allow_null=True
    )
    module_title = serializers.CharField(source="module.title", read_only=True)
    resource_type_display = serializers.CharField(
        source="get_resource_type_display", read_only=True
    )
    file_size_display = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    can_download = serializers.SerializerMethodField()

    class Meta:
        from api.models.models_module import CourseResource

        model = CourseResource
        fields = [
            "id",
            "module",
            "module_title",
            "live_class",
            "live_class_title",
            "title",
            "description",
            "resource_type",
            "resource_type_display",
            "file",
            "file_url",
            "external_url",
            "file_size",
            "file_size_display",
            "download_count",
            "order",
            "is_active",
            "uploaded_by_name",
            "can_download",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "download_count", "created_at", "updated_at"]

    def get_file_size_display(self, obj):
        """Get human-readable file size"""
        return obj.get_file_size_display()

    def get_file_url(self, obj):
        """Get full URL for file"""
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_can_download(self, obj):
        """Check if user can download this resource"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        # Check if student is enrolled in the course
        try:
            from api.models.models_order import Enrollment

            is_enrolled = Enrollment.objects.filter(
                user=request.user, course=obj.module.course.course, is_active=True
            ).exists()
            return is_enrolled
        except Exception:
            return False


class CourseResourceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating course resources (teachers/admin)."""

    class Meta:
        from api.models.models_module import CourseResource

        model = CourseResource
        fields = [
            "module",
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
        """Ensure either file or external_url is provided"""
        file_provided = attrs.get("file") or (self.instance and self.instance.file)
        url_provided = attrs.get("external_url")

        if not file_provided and not url_provided:
            raise serializers.ValidationError(
                "Either 'file' or 'external_url' must be provided"
            )

        return attrs

    def create(self, validated_data):
        """Create resource and calculate file size"""
        resource = super().create(validated_data)

        if resource.file:
            try:
                resource.file_size = resource.file.size
                resource.save(update_fields=["file_size"])
            except Exception:
                pass

        return resource
