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
    QuizAnswer
)
from api.models.models_course import CourseModule
from api.serializers.serializers_helpers import HTMLFieldsMixin


# ========== Live Class Serializers ==========

class LiveClassSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for live classes within a module."""
    html_fields = ['description']
    
    instructor_name = serializers.CharField(
        source='instructor.get_full_name',
        read_only=True,
        allow_null=True
    )
    instructor_email = serializers.EmailField(
        source='instructor.email',
        read_only=True,
        allow_null=True
    )
    
    # Helper fields
    is_upcoming = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()
    has_recording = serializers.SerializerMethodField()
    attendance_marked = serializers.SerializerMethodField()  # NEW: Student attendance status
    
    class Meta:
        model = LiveClass
        fields = [
            'id',
            'title',
            'description',
            'scheduled_date',
            'duration_minutes',
            'meeting_url',
            'meeting_id',
            'meeting_password',
            'recording_url',
            'status',
            'order',
            'is_active',
            'instructor_name',
            'instructor_email',
            'is_upcoming',
            'is_past',
            'can_join',
            'has_recording',
            'attendance_marked',  # NEW
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_is_upcoming(self, obj):
        """Check if class is upcoming (scheduled in future)"""
        return obj.scheduled_date > timezone.now() and obj.status == 'scheduled'
    
    def get_is_past(self, obj):
        """Check if class is in the past"""
        return obj.scheduled_date < timezone.now() or obj.status == 'completed'
    
    def get_can_join(self, obj):
        """Check if student can join now (10 mins before start until class ends)"""
        now = timezone.now()
        start_time = obj.scheduled_date
        end_time = start_time + timezone.timedelta(minutes=obj.duration_minutes)
        grace_period = timezone.timedelta(minutes=10)
        
        return (start_time - grace_period) <= now <= end_time and obj.status in ['scheduled', 'ongoing']
    
    def get_has_recording(self, obj):
        """Check if recording is available"""
        return bool(obj.recording_url)
    
    def get_attendance_marked(self, obj):
        """Check if current student has marked attendance"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        try:
            attendance = LiveClassAttendance.objects.filter(
                live_class=obj,
                student=request.user,
                attended=True
            ).exists()
            return attendance
        except Exception:
            return False


class LiveClassCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating live classes (admin/teacher use)."""
    
    class Meta:
        model = LiveClass
        fields = [
            'module',
            'title',
            'description',
            'scheduled_date',
            'duration_minutes',
            'meeting_url',
            'meeting_id',
            'meeting_password',
            'recording_url',
            'status',
            'order',
            'is_active',
            'instructor',
        ]


class LiveClassAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for live class attendance tracking."""
    
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    class_title = serializers.CharField(source='live_class.title', read_only=True)
    
    class Meta:
        model = LiveClassAttendance
        fields = [
            'id',
            'live_class',
            'student',
            'student_name',
            'student_email',
            'class_title',
            'attended',
            'joined_at',
            'left_at',
            'duration_minutes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ========== Assignment Serializers ==========

class AssignmentSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for assignments within a module."""
    html_fields = ['description']
    
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Helper fields
    is_overdue = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    has_submitted = serializers.SerializerMethodField()  # NEW: Student submission status
    submission_status = serializers.SerializerMethodField()  # NEW: pending|submitted|graded
    submission_date = serializers.SerializerMethodField()  # NEW: When submitted
    obtained_marks = serializers.SerializerMethodField()  # NEW: Grade received
    can_submit = serializers.SerializerMethodField()  # NEW: Check deadline
    attachment_url = serializers.SerializerMethodField()  # NEW: Assignment file URL
    
    class Meta:
        model = Assignment
        fields = [
            'id',
            'title',
            'description',
            'assignment_type',
            'attachment',
            'total_marks',
            'passing_marks',
            'due_date',
            'late_submission_allowed',
            'late_submission_penalty',
            'order',
            'is_active',
            'created_by_name',
            'is_overdue',
            'days_remaining',
            'submission_count',
            'has_submitted',  # NEW
            'submission_status',  # NEW
            'submission_date',  # NEW
            'obtained_marks',  # NEW
            'can_submit',  # NEW
            'attachment_url',  # NEW
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
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
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        try:
            return obj.submissions.filter(student=request.user).exists()
        except Exception:
            return False
    
    def get_submission_status(self, obj):
        """Get submission status for current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.status if submission else None
        except Exception:
            return None
    
    def get_submission_date(self, obj):
        """Get submission date for current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.submitted_at if submission else None
        except Exception:
            return None
    
    def get_obtained_marks(self, obj):
        """Get marks obtained by current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            submission = obj.submissions.filter(student=request.user).first()
            return float(submission.marks_obtained) if submission and submission.marks_obtained is not None else None
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
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating assignments (admin/teacher use)."""
    
    class Meta:
        model = Assignment
        fields = [
            'module',
            'title',
            'description',
            'assignment_type',
            'attachment',
            'total_marks',
            'passing_marks',
            'due_date',
            'late_submission_allowed',
            'late_submission_penalty',
            'order',
            'is_active',
        ]


class AssignmentSubmissionSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for student assignment submissions."""
    html_fields = ['submission_text', 'feedback']
    
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    graded_by_name = serializers.CharField(
        source='graded_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Helper fields
    percentage = serializers.SerializerMethodField()
    is_passed = serializers.SerializerMethodField()
    can_view_feedback = serializers.SerializerMethodField()
    
    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'student',
            'student_name',
            'student_email',
            'assignment_title',
            'submission_text',
            'submission_file',
            'submission_url',
            'submitted_at',
            'is_late',
            'status',
            'marks_obtained',
            'feedback',
            'graded_by_name',
            'graded_at',
            'percentage',
            'is_passed',
            'can_view_feedback',
            'updated_at',
        ]
        read_only_fields = ['id', 'submitted_at', 'updated_at', 'is_late']
    
    def get_percentage(self, obj):
        """Calculate percentage score"""
        if obj.marks_obtained is not None and obj.assignment.total_marks > 0:
            return round((float(obj.marks_obtained) / obj.assignment.total_marks) * 100, 2)
        return None
    
    def get_is_passed(self, obj):
        """Check if student passed"""
        if obj.marks_obtained is not None:
            return obj.marks_obtained >= obj.assignment.passing_marks
        return False
    
    def get_can_view_feedback(self, obj):
        """Check if student can view feedback (only after graded)"""
        return obj.status == 'graded'


class AssignmentSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for students to submit assignments."""
    
    class Meta:
        model = AssignmentSubmission
        fields = [
            'submission_text',
            'submission_file',
            'submission_url',
        ]


class AssignmentGradeSerializer(serializers.Serializer):
    """Serializer for teacher to grade assignment."""
    
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    feedback = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=['graded', 'resubmit'],
        default='graded'
    )


# ========== Quiz Serializers ==========

class QuizQuestionOptionSerializer(serializers.ModelSerializer):
    """Serializer for quiz question options."""
    
    class Meta:
        model = QuizQuestionOption
        fields = [
            'id',
            'option_text',
            'option_image',
            'is_correct',  # Only shown to teachers or after submission
            'order',
        ]
        read_only_fields = ['id']


class QuizQuestionSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for quiz questions."""
    html_fields = ['question_text', 'explanation']
    
    options = QuizQuestionOptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuizQuestion
        fields = [
            'id',
            'question_text',
            'question_type',
            'question_image',
            'marks',
            'order',
            'correct_answer_text',  # For short answer
            'explanation',
            'options',
            'is_active',
        ]
        read_only_fields = ['id']


class QuizSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for quizzes within a module."""
    html_fields = ['description']
    
    questions = QuizQuestionSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Helper fields
    question_count = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    attempts_used = serializers.SerializerMethodField()  # NEW: Student's attempts
    can_attempt = serializers.SerializerMethodField()  # NEW: Can take quiz
    best_score = serializers.SerializerMethodField()  # NEW: Highest score
    last_attempt_date = serializers.SerializerMethodField()  # NEW: Last attempt
    is_completed = serializers.SerializerMethodField()  # NEW: Progress tracking
    
    class Meta:
        model = Quiz
        fields = [
            'id',
            'title',
            'description',
            'total_marks',
            'passing_marks',
            'duration_minutes',
            'difficulty',
            'max_attempts',
            'show_correct_answers',
            'randomize_questions',
            'available_from',
            'available_until',
            'is_active',
            'created_by_name',
            'question_count',
            'is_available',
            'attempt_count',
            'attempts_used',  # NEW
            'can_attempt',  # NEW
            'best_score',  # NEW
            'last_attempt_date',  # NEW
            'is_completed',  # NEW
            'questions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_question_count(self, obj):
        """Get number of questions"""
        return obj.questions.filter(is_active=True).count()
    
    def get_is_available(self, obj):
        """Check if quiz is currently available"""
        now = timezone.now()
        if obj.available_from and now < obj.available_from:
            return False
        if obj.available_until and now > obj.available_until:
            return False
        return obj.is_active
    
    def get_attempt_count(self, obj):
        """Get total number of attempts"""
        return obj.attempts.count()
    
    def get_attempts_used(self, obj):
        """Get number of attempts used by current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        
        try:
            return obj.attempts.filter(student=request.user, status='submitted').count()
        except Exception:
            return 0
    
    def get_can_attempt(self, obj):
        """Check if student can attempt quiz"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Check if quiz is available
        if not self.get_is_available(obj):
            return False
        
        # Check attempt limit
        attempts_used = self.get_attempts_used(obj)
        if obj.max_attempts and attempts_used >= obj.max_attempts:
            return False
        
        return True
    
    def get_best_score(self, obj):
        """Get highest score achieved by current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            best_attempt = obj.attempts.filter(
                student=request.user,
                status='submitted',
                marks_obtained__isnull=False
            ).order_by('-marks_obtained').first()
            
            return float(best_attempt.marks_obtained) if best_attempt else None
        except Exception:
            return None
    
    def get_last_attempt_date(self, obj):
        """Get date of last attempt by current student"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            last_attempt = obj.attempts.filter(
                student=request.user
            ).order_by('-started_at').first()
            
            return last_attempt.submitted_at if last_attempt and last_attempt.submitted_at else None
        except Exception:
            return None
    
    def get_is_completed(self, obj):
        """Check if student has completed quiz (has at least one submission)"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        try:
            # Simply check if student has submitted at least once
            attempts_used = self.get_attempts_used(obj)
            return attempts_used > 0
        except Exception:
            return False


# Serializer for create/update operations on Quiz (writable)
class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    module = serializers.PrimaryKeyRelatedField(queryset=CourseModule.objects.all())

    class Meta:
        model = Quiz
        fields = [
            'module',
            'title',
            'description',
            'total_marks',
            'passing_marks',
            'duration_minutes',
            'difficulty',
            'max_attempts',
            'show_correct_answers',
            'randomize_questions',
            'available_from',
            'available_until',
            'is_active',
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer for quiz attempts."""
    
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz',
            'student',
            'student_name',
            'student_email',
            'quiz_title',
            'attempt_number',
            'started_at',
            'submitted_at',
            'status',
            'marks_obtained',
            'percentage',
            'passed',
            'updated_at',
        ]
        read_only_fields = ['id', 'started_at', 'updated_at']


class QuizAnswerSerializer(serializers.ModelSerializer):
    """Serializer for quiz answers."""
    
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    correct_answer = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAnswer
        fields = [
            'id',
            'question',
            'question_text',
            'selected_options',
            'answer_text',
            'is_correct',
            'marks_awarded',
            'correct_answer',
            'answered_at',
        ]
        read_only_fields = ['id', 'answered_at']
    
    def get_correct_answer(self, obj):
        """Get correct answer (only shown if quiz allows it)"""
        request = self.context.get('request')
        # Only show if quiz allows showing correct answers
        if obj.attempt.quiz.show_correct_answers:
            if obj.question.question_type in ['mcq', 'multiple', 'true_false']:
                correct_options = obj.question.options.filter(is_correct=True)
                return QuizQuestionOptionSerializer(correct_options, many=True).data
            else:
                return obj.question.correct_answer_text
        return None


# ========== Module with Complete Content Serializer ==========

class CourseModuleDetailSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Complete serializer for course module with all content (live classes, assignments, quizzes)."""
    html_fields = ['short_description']
    
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
            'id',
            'title',
            'short_description',
            'order',
            'is_active',
            'live_classes',
            'assignments',
            'quizzes',
            'live_class_count',
            'assignment_count',
            'quiz_count',
        ]
        read_only_fields = ['id']
    
    def get_live_class_count(self, obj):
        """Count active live classes"""
        return obj.live_classes.filter(is_active=True).count()
    
    def get_assignment_count(self, obj):
        """Count active assignments with proper content"""
        from django.db.models import Q
        return obj.assignments.filter(is_active=True).exclude(
            Q(title__isnull=True) | Q(title='') |
            Q(description__isnull=True) | Q(description='')
        ).count()
    
    def get_quiz_count(self, obj):
        """Count active quizzes with at least one active question"""
        from django.db.models import Count, Q
        return obj.quizzes.filter(is_active=True).annotate(
            active_question_count=Count('questions', filter=Q(questions__is_active=True))
        ).filter(active_question_count__gt=0).count()
