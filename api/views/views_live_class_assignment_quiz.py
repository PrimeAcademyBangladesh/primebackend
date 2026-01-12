"""
Views for Live Classes, Assignments, and Quizzes
"""

import uuid

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models.models_module import (
    Assignment,
    AssignmentSubmission,
    CourseResource,
    LiveClass,
    LiveClassAttendance,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    QuizQuestionOption,
)
from api.models.models_order import Enrollment
from api.permissions import IsTeacherOrAdmin
from api.serializers.serializers_module import (
    AssignmentCreateUpdateSerializer,
    AssignmentGradeSerializer,
    AssignmentListSerializer,
    AssignmentStudentSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentSubmissionSerializer,
    CourseResourceCreateUpdateSerializer,
    CourseResourceSerializer,
    LiveClassAttendanceSerializer,
    LiveClassCreateUpdateSerializer,
    LiveClassSerializer,
    QuizAnswerSerializer,
    QuizAttemptSerializer,
    QuizCreateUpdateSerializer,
    QuizQuestionCreateUpdateSerializer,
    QuizQuestionSerializer,
    QuizSerializer,
)
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet


@extend_schema_view(
    list=extend_schema(summary="List live classes", tags=["Course - Live Classes"]),
    retrieve=extend_schema(summary="Get live class details", tags=["Course - Live Classes"]),
    create=extend_schema(summary="Create live class (Admin)", tags=["Course - Live Classes"]),
    update=extend_schema(summary="Update live class (Admin)", tags=["Course - Live Classes"]),
    partial_update=extend_schema(summary="Partial update live class (Admin)", tags=["Course - Live Classes"]),
    destroy=extend_schema(summary="Delete live class (Admin)", tags=["Course - Live Classes"]),
)
class LiveClassViewSet(viewsets.ModelViewSet):
    """
    Live Classes API

    Students → enrolled batches only
    Teachers/Admin → full access
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = LiveClass.objects.select_related(
        "module",
        "module__course",
        "batch",
        "instructor",
    ).order_by("scheduled_date")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LiveClassCreateUpdateSerializer
        return LiveClassSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "attendances",
            "mark_attendance",
        ]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # =========================
    # QUERYSET FILTERING
    # =========================
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Admin / Teacher → all
        if user.role in ["admin", "superadmin", "teacher"]:
            return queryset

        # Student → enrolled batches only
        enrollments = Enrollment.objects.filter(user=user, is_active=True).values_list("batch_id", flat=True)

        if not enrollments:
            return queryset.none()

        queryset = queryset.filter(batch_id__in=enrollments)

        # Optional module filter
        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        return queryset

    @extend_schema(
        summary="Join live class",
        tags=["Live Classes"],
    )
    # Join class and AUto mark attendace
    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        live_class = self.get_object()
        user = request.user

        attendance, created = LiveClassAttendance.objects.get_or_create(
            live_class=live_class,
            student=user,
            defaults={"joined_at": timezone.now()},
        )

        if not created and not attendance.joined_at:
            attendance.joined_at = timezone.now()
            attendance.save(update_fields=["joined_at"])

        serializer = LiveClassAttendanceSerializer(attendance)

        return api_response(
            True,
            "Attendance recorded successfully",
            serializer.data,
        )

    @extend_schema(
        summary="Attendacne live class",
        tags=["Live Classes"],  # Same tag as ViewSet
    )
    @action(detail=True, methods=["get"], url_path="my-attendance")
    def my_attendance(self, request, pk=None):
        live_class = self.get_object()
        user = request.user

        attendance = LiveClassAttendance.objects.filter(
            live_class=live_class,
            student=user,
        ).first()

        if not attendance:
            return api_response(
                True,
                "No attendance found",
                None,
            )

        serializer = LiveClassAttendanceSerializer(attendance)
        return api_response(True, "Attendance fetched", serializer.data)

    @extend_schema(
        summary="Join live class",
        tags=["Live Classes"],
    )
    @action(detail=True, methods=["get"])
    def attendances(self, request, pk=None):
        live_class = self.get_object()

        attendances = LiveClassAttendance.objects.filter(live_class=live_class).select_related("student")

        serializer = LiveClassAttendanceSerializer(attendances, many=True)
        return api_response(True, "Attendance list", serializer.data)

    @extend_schema(
        summary="Join live class",
        tags=["Live Classes"],  # Same tag as ViewSet
    )
    @action(detail=True, methods=["post"], url_path="mark-attendance")
    def mark_attendance(self, request, pk=None):
        live_class = self.get_object()
        student_id = request.data.get("student_id")

        if not student_id:
            return api_response(False, "student_id is required", None)

        attendance, _ = LiveClassAttendance.objects.get_or_create(
            live_class=live_class,
            student_id=student_id,
        )

        attendance.joined_at = timezone.now()
        attendance.save()

        serializer = LiveClassAttendanceSerializer(attendance)
        return api_response(True, "Attendance marked", serializer.data)


@extend_schema_view(
    list=extend_schema(summary="List assignments", tags=["Course - Assignments"]),
    retrieve=extend_schema(summary="Get assignment details", tags=["Course - Assignments"]),
    create=extend_schema(summary="Create assignment (Admin)", tags=["Course - Assignments"]),
    update=extend_schema(summary="Update assignment (Admin)", tags=["Course - Assignments"]),
    partial_update=extend_schema(summary="Partial update assignment (Admin)", tags=["Course - Assignments"]),
    destroy=extend_schema(summary="Delete assignment (Admin)", tags=["Course - Assignments"]),
    submit=extend_schema(summary="Submit assignment (Student)", tags=["Course - Assignments"]),
    my_submission=extend_schema(summary="Get my submission (Student)", tags=["Course - Assignments"]),
)
class AssignmentViewSet(BaseAdminViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Assignment.objects.select_related(
        "module",
        "module__course",
        "batch",
    ).order_by("due_date")
    serializer_class = AssignmentListSerializer

    # ---------------- SERIALIZER SWITCH ----------------

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AssignmentCreateUpdateSerializer

        # For student-facing endpoints, ensure list and retrieve use the
        # student serializer so the response fields stay consistent.
        if self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "student":
            if self.action in ["list", "retrieve"]:
                return AssignmentStudentSerializer

        if self.action == "retrieve":
            return AssignmentStudentSerializer

        return AssignmentListSerializer

    # ---------------- PERMISSIONS ----------------

    def get_permissions(self):
        """Override to handle assignment-specific permissions"""

        if not self.request.user.is_authenticated:
            return [permissions.IsAuthenticated()]

        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]

        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]

        if self.action in ["submit", "my_submission"]:
            return [permissions.IsAuthenticated()]

        return super().get_permissions()

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        user = self.request.user
        base_queryset = self.queryset

        if user.role in ["admin", "superadmin", "teacher"]:
            return base_queryset

        enrollment = Enrollment.objects.filter(user=user, is_active=True).select_related("batch", "course")

        if not enrollment.exists():
            return base_queryset.none()

        batch_ids = enrollment.values_list("batch_id", flat=True)
        course_ids = enrollment.values_list("course_id", flat=True)

        return base_queryset.filter(
            batch__id__in=batch_ids,
            module__course__id__in=course_ids,
        )

    def list(self, request, *args, **kwargs):
        """Custom list to handle student enrollment case"""
        queryset = self.filter_queryset(self.get_queryset())

        if (
            request.user.role == "student"
            and not queryset.exists()
            and not Enrollment.objects.filter(user=request.user, is_active=True).exists()
        ):

            return api_response(
                False,
                "No active enrollment found. Please enroll in a course first.",
                None,
                status.HTTP_404_NOT_FOUND,
            )

        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Student submits assignment"""
        assignment = self.get_object()
        student = request.user

        if not self.get_queryset().filter(id=assignment.id).exists():
            return api_response(
                False,
                "You don't have permission to submit to this assignment",
                None,
                status.HTTP_403_FORBIDDEN,
            )

        if assignment.due_date and timezone.now() > assignment.due_date:
            if not assignment.late_submission_allowed:
                return api_response(
                    False,
                    "Submission deadline has passed",
                    None,
                    status.HTTP_400_BAD_REQUEST,
                )

        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            student=student,
            defaults={"status": "pending"},
        )

        serializer = AssignmentSubmissionCreateSerializer(
            submission,
            data=request.data,
            context={"request": request},
            partial=not created,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        message = "Assignment submitted successfully" if created else "Submission updated"
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

        return api_response(
            True,
            message,
            {
                "submission_id": str(submission.id),
                "assignment_id": str(assignment.id),
                "created": created,
            },
            status_code,
        )

    @action(detail=True, methods=["get"], url_path="my-submission")
    def my_submission(self, request, pk=None):
        """Get student's submission for this assignment"""
        assignment = self.get_object()

        if not self.get_queryset().filter(id=assignment.id).exists():
            return api_response(
                False,
                "You don't have permission to view this assignment",
                None,
                status.HTTP_403_FORBIDDEN,
            )

        submission = assignment.submissions.filter(student=request.user).first()

        if not submission:
            return api_response(
                False,
                "No submission found",
                None,
                status.HTTP_404_NOT_FOUND,
            )

        return api_response(
            True,
            "Submission retrieved successfully",
            AssignmentSubmissionSerializer(submission, context={"request": request}).data,
        )


@extend_schema_view(
    list=extend_schema(
        summary="List assignment submissions",
        tags=["Course - Assignments"],
    ),
    retrieve=extend_schema(
        summary="Get submission details",
        tags=["Course - Assignments"],
    ),
    create=extend_schema(
        summary="Create assignment submission",
        tags=["Course - Assignments"],
    ),
    update=extend_schema(
        summary="Update assignment submission",
        tags=["Course - Assignments"],
    ),
    partial_update=extend_schema(
        summary="Partially update assignment submission",
        tags=["Course - Assignments"],
    ),
    destroy=extend_schema(
        summary="Delete assignment submission",
        tags=["Course - Assignments"],
    ),
    grade=extend_schema(
        summary="Grade assignment submission (Teacher/Admin)",
        tags=["Course - Assignments"],
    ),
)
class AssignmentSubmissionViewSet(BaseAdminViewSet):
    """
    Assignment Submissions (Read-only for students)

    Students:
    - View only their submissions

    Teachers/Admin:
    - View all submissions
    - Grade submissions
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssignmentSubmissionSerializer

    queryset = AssignmentSubmission.objects.select_related(
        "assignment",
        "assignment__module",
        "assignment__module__course",
        "student",
        "graded_by",
    ).order_by("-submitted_at")

    # ---------------- PERMISSIONS ----------------

    def get_permissions(self):
        if self.action == "grade":
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        # Use base queryset to avoid public filtering in BaseAdminViewSet
        queryset = self.get_base_queryset()
        user = self.request.user

        # 🔒 Student → only their submissions
        role = getattr(user, "role", None)
        if role == "student":
            queryset = queryset.filter(student=user)

        return queryset

    # ---------------- ACTIONS ----------------

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        """
        Grade assignment submission (Teacher/Admin only)

        Body:
        {
            "marks_obtained": 85,
            "feedback": "<p>Good work!</p>",
            "status": "graded"
        }
        """
        submission = self.get_object()

        serializer = AssignmentGradeSerializer(
            submission,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(
            graded_by=request.user,
            graded_at=timezone.now(),
        )

        return api_response(
            True,
            "Assignment graded successfully",
            AssignmentSubmissionSerializer(submission, context={"request": request}).data,
        )


@extend_schema_view(
    list=extend_schema(summary="List quizzes", tags=["Course - Quizzes"]),
    retrieve=extend_schema(summary="Get quiz details", tags=["Course - Quizzes"]),
    create=extend_schema(summary="Create quiz (Admin)", tags=["Course - Quizzes"]),
    update=extend_schema(summary="Update quiz (Admin)", tags=["Course - Quizzes"]),
    partial_update=extend_schema(summary="Partial update quiz (Admin)", tags=["Course - Quizzes"]),
    destroy=extend_schema(summary="Delete quiz (Admin)", tags=["Course - Quizzes"]),
    start=extend_schema(summary="Start quiz attempt", tags=["Course - Quizzes"]),
)
class QuizViewSet(BaseAdminViewSet):
    """
    Quiz API

    Students → enrollment scoped (multi-course + multi-batch)
    Teachers/Admin → full access
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = (
        Quiz.objects.select_related(
            "module",
            "module__course",
            "batch",
            "created_by",
        )
        .prefetch_related(
            "questions",
            "questions__options",
            "attempts",
        )
        .order_by("title")
    )

    # ---------------- SERIALIZER ----------------

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return QuizCreateUpdateSerializer
        return QuizSerializer

    # ---------------- PERMISSIONS ----------------

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Admin / Teacher → full access
        if user.role in ["admin", "superadmin", "teacher"]:
            return queryset

        # Student → enrollment scoped
        enrollments = Enrollment.objects.filter(
            user=user,
            is_active=True,
        ).select_related("batch", "course")

        if not enrollments.exists():
            return queryset.none()

        batch_ids = enrollments.values_list("batch_id", flat=True)
        course_ids = enrollments.values_list("course_id", flat=True)

        queryset = queryset.filter(
            batch_id__in=batch_ids,
            module__course_id__in=course_ids,
        )

        # Optional module filter
        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        # Only quizzes with active questions
        queryset = queryset.annotate(
            active_question_count=Count(
                "questions",
                filter=Q(questions__is_active=True),
            )
        ).filter(active_question_count__gt=0)

        return queryset

    # ---------------- START QUIZ ----------------

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        quiz = self.get_object()
        student = request.user
        now = timezone.now()

        # 🔒 Enrollment guard (same rule as Assignment / LiveClass)
        if not self.get_queryset().filter(id=quiz.id).exists():
            return api_response(
                False,
                "You don't have permission to start this quiz",
                None,
                status.HTTP_403_FORBIDDEN,
            )

        if quiz.available_from and now < quiz.available_from:
            return api_response(False, "Quiz not yet available", None, status.HTTP_400_BAD_REQUEST)

        if quiz.available_until and now > quiz.available_until:
            return api_response(False, "Quiz is no longer available", None, status.HTTP_400_BAD_REQUEST)

        attempt_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()

        if quiz.max_attempts and attempt_count >= quiz.max_attempts:
            return api_response(False, "Maximum attempts reached", None, status.HTTP_400_BAD_REQUEST)

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            attempt_number=attempt_count + 1,
            started_at=now,
        )

        questions = quiz.questions.filter(is_active=True)
        questions = questions.order_by("?") if quiz.randomize_questions else questions.order_by("order")

        total_questions = questions.count()
        marks_per_question = quiz.total_marks / total_questions if total_questions else 0

        questions_data = []
        for q in questions:
            q_data = {
                "id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "points": round(marks_per_question, 2),
                "options": None,
            }

            if q.question_type in ["mcq", "multiple", "true_false"]:
                q_data["options"] = [
                    {"id": str(o.id), "option_text": o.option_text} for o in q.options.all().order_by("order")
                ]

            questions_data.append(q_data)

        return api_response(
            True,
            "Quiz attempt started successfully",
            {
                "attempt_id": str(attempt.id),
                "quiz_id": str(quiz.id),
                "attempt_number": attempt.attempt_number,
                "started_at": attempt.started_at,
                "time_limit_minutes": quiz.duration_minutes,
                "questions": questions_data,
            },
            status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Course - Quiz Questions"],
    summary="Create/update/delete quiz questions (teachers/admin)",
)
class QuizQuestionViewSet(BaseAdminViewSet):
    """
    Teacher/Admin only
    Create / Update / Delete quiz questions
    """

    permission_classes = [IsTeacherOrAdmin]
    serializer_class = QuizQuestionCreateUpdateSerializer

    queryset = QuizQuestion.objects.prefetch_related("options").order_by("order")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Admin / Superadmin → full access
        if user.role in ["admin", "superadmin"]:
            return qs

        # Teacher → only quizzes they created
        return qs.filter(quiz__created_by=user)


@extend_schema_view(
    list=extend_schema(summary="List student's quiz attempts", tags=["Course - Quizzes"]),
    retrieve=extend_schema(summary="Get attempt details", tags=["Course - Quizzes"]),
    answer=extend_schema(summary="Submit answer", tags=["Course - Quizzes"]),
    submit=extend_schema(summary="Submit quiz", tags=["Course - Quizzes"]),
    results=extend_schema(summary="Get results", tags=["Course - Quizzes"]),
)
class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = QuizAttemptSerializer

    queryset = (
        QuizAttempt.objects.select_related("quiz", "student")
        .prefetch_related(
            "answers",
            "answers__question",
            "answers__selected_options",
        )
        .order_by("-started_at")
    )

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Student → only own attempts
        if user.role == "student":
            return qs.filter(student=user)

        # Teacher → only quizzes they created
        if user.role == "teacher":
            return qs.filter(quiz__created_by=user)

        # Admin / Superadmin → all
        return qs

    # ---------------- ACTIONS ----------------

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        attempt = self.get_object()

        # 🔒 Ownership check
        if attempt.student != request.user:
            return api_response(
                False,
                "You don't have permission to answer this quiz",
                None,
                status.HTTP_403_FORBIDDEN,
            )

        if attempt.submitted_at:
            return api_response(False, "Quiz already submitted", None, status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(QuizQuestion, id=request.data.get("question_id"), quiz=attempt.quiz)

        answer, _ = QuizAnswer.objects.get_or_create(attempt=attempt, question=question)

        answer.answer_text = request.data.get("answer_text", "")
        answer.selected_options.set(request.data.get("selected_options", []))
        answer.save()

        return api_response(
            True,
            "Answer saved successfully",
            QuizAnswerSerializer(answer).data,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def submit(self, request, pk=None):
        attempt = self.get_object()

        # 🔒 Ownership check
        if attempt.student != request.user:
            return api_response(
                False,
                "You don't have permission to submit this quiz",
                None,
                status.HTTP_403_FORBIDDEN,
            )

        if attempt.submitted_at:
            return api_response(False, "Quiz already submitted", None, status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get("answers", [])
        if not answers_data:
            return api_response(False, "No answers submitted", None, status.HTTP_400_BAD_REQUEST)

        total_questions = attempt.quiz.questions.filter(is_active=True).count()
        marks_per_question = attempt.quiz.total_marks / total_questions if total_questions else 0

        options_map = {str(o.id): o for o in QuizQuestionOption.objects.filter(question__quiz=attempt.quiz)}

        total_marks = 0

        for item in answers_data:
            question = QuizQuestion.objects.filter(id=item.get("question_id"), quiz=attempt.quiz).first()
            if not question:
                continue

            quiz_answer, _ = QuizAnswer.objects.get_or_create(attempt=attempt, question=question)

            if question.question_type in ["mcq", "multiple", "true_false"]:
                selected_ids = item.get("answer", [])
                if not isinstance(selected_ids, list):
                    selected_ids = [selected_ids]

                quiz_answer.selected_options.clear()
                for opt_id in selected_ids:
                    option = options_map.get(str(opt_id))
                    if option:
                        quiz_answer.selected_options.add(option)

                correct_ids = set(question.options.filter(is_correct=True).values_list("id", flat=True))
                chosen_ids = set(quiz_answer.selected_options.values_list("id", flat=True))

                if correct_ids == chosen_ids:
                    quiz_answer.marks_awarded = marks_per_question
                    quiz_answer.is_correct = True
                    total_marks += marks_per_question
                else:
                    quiz_answer.marks_awarded = 0
                    quiz_answer.is_correct = False
            else:
                quiz_answer.answer_text = item.get("answer", "")
                quiz_answer.marks_awarded = 0

            quiz_answer.save()

        attempt.submitted_at = timezone.now()
        attempt.marks_obtained = total_marks
        attempt.percentage = (total_marks / attempt.quiz.total_marks) * 100 if attempt.quiz.total_marks > 0 else 0
        attempt.passed = total_marks >= attempt.quiz.passing_marks
        attempt.status = "submitted"
        attempt.save()

        return api_response(
            True,
            "Quiz submitted successfully",
            QuizAttemptSerializer(attempt).data,
        )

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        attempt = self.get_object()

        if not attempt.submitted_at:
            return api_response(False, "Quiz not yet submitted", None, status.HTTP_400_BAD_REQUEST)

        return api_response(
            True,
            "Results retrieved successfully",
            QuizAttemptSerializer(attempt).data,
        )


# ========== Course Resources ViewSet ==========


@extend_schema_view(
    list=extend_schema(tags=["Course - Resources"]),
    retrieve=extend_schema(tags=["Course - Resources"]),
    create=extend_schema(tags=["Course - Resources"]),
    update=extend_schema(tags=["Course - Resources"]),
    partial_update=extend_schema(tags=["Course - Resources"]),
    destroy=extend_schema(tags=["Course - Resources"]),
)
class CourseResourceViewSet(BaseAdminViewSet):
    """
    Course Resources API

    Students:
    - View / download resources
    - Access limited to enrolled batches & courses

    Teachers/Admin:
    - Full CRUD access
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    queryset = (
        CourseResource.objects.select_related(
            "module",
            "module__course",
            "batch",
            "live_class",
            "uploaded_by",
        )
        .prefetch_related("files")
        .order_by("order", "-created_at")
    )

    # ---------------- SERIALIZERS ----------------

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseResourceCreateUpdateSerializer
        return CourseResourceSerializer

    # ---------------- PERMISSIONS ----------------

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated and user.role == "student":
            enrollments = Enrollment.objects.filter(
                user=user,
                is_active=True,
            ).select_related("batch", "course")

            if not enrollments.exists():
                return queryset.none()

            batch_ids = enrollments.values_list("batch_id", flat=True)
            course_ids = enrollments.values_list("course_id", flat=True)

            queryset = queryset.filter(
                batch_id__in=batch_ids,
                module__course_id__in=course_ids,
                is_active=True,
            )

        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        live_class_id = self.request.query_params.get("live_class_id")
        if live_class_id:
            queryset = queryset.filter(live_class_id=live_class_id)

        return queryset

    # ---------------- ACTIONS ----------------
    @extend_schema(summary="Download resource and return URL", tags=["Course - Resources"])
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Download resource and increment download count
        """
        resource = self.get_object()
        resource.increment_download_count()

        if resource.file:
            return api_response(
                True,
                "Download initiated",
                {
                    "url": request.build_absolute_uri(resource.file.url),
                    "title": resource.title,
                    "download_count": resource.download_count,
                },
            )

        if resource.external_url:
            return api_response(
                True,
                "External resource accessed",
                {
                    "url": resource.external_url,
                    "download_count": resource.download_count,
                },
            )

        return api_response(
            False,
            "No downloadable content",
            None,
            status.HTTP_404_NOT_FOUND,
        )
