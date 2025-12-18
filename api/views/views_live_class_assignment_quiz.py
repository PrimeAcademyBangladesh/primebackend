"""
Views for Live Classes, Assignments, and Quizzes
"""

import uuid
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
)
from django.db.models import Prefetch
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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
from api.serializers.serializers_module import (
    LiveClassSerializer,
    LiveClassCreateUpdateSerializer,
    LiveClassAttendanceSerializer,
    AssignmentListSerializer,
    AssignmentStudentSerializer,
    AssignmentCreateUpdateSerializer,
    AssignmentSubmissionSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentGradeSerializer,
    QuizSerializer,
    QuizCreateUpdateSerializer,
    QuizQuestionSerializer,
    QuizQuestionCreateUpdateSerializer,
    QuizAttemptSerializer,
    QuizAnswerSerializer,
)
from api.permissions import IsTeacherOrAdmin
from api.utils.response_utils import api_response
from api.models.models_module import CourseResource
from api.serializers.serializers_module import (
    CourseResourceSerializer,
    CourseResourceCreateUpdateSerializer,
)
from api.models.models_order import Enrollment
from api.permissions import IsTeacherOrAdmin


@extend_schema_view(
    list=extend_schema(summary="List live classes", tags=["Course - Live Classes"]),
    retrieve=extend_schema(
        summary="Get live class details", tags=["Course - Live Classes"]
    ),
    create=extend_schema(
        summary="Create live class (Admin)", tags=["Course - Live Classes"]
    ),
    update=extend_schema(
        summary="Update live class (Admin)", tags=["Course - Live Classes"]
    ),
    partial_update=extend_schema(
        summary="Partial update live class (Admin)", tags=["Course - Live Classes"]
    ),
    destroy=extend_schema(
        summary="Delete live class (Admin)", tags=["Course - Live Classes"]
    ),
)
class LiveClassViewSet(viewsets.ModelViewSet):
    """
    Live Classes API

    Students → batch-isolated
    Teachers/Admin → full access
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = LiveClass.objects.select_related(
        "module", "batch", "instructor"
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
        ]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if getattr(user, "role", None) == "student":
            enrollment = (
                Enrollment.objects.filter(user=user, is_active=True)
                .select_related("batch")
                .first()
            )

            if not enrollment or not enrollment.batch:
                return queryset.none()

            queryset = queryset.filter(batch=enrollment.batch)

        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        return queryset


@extend_schema_view(
    list=extend_schema(summary="List assignments", tags=["Course - Assignments"]),
    retrieve=extend_schema(
        summary="Get assignment details", tags=["Course - Assignments"]
    ),
    create=extend_schema(
        summary="Create assignment (Admin)", tags=["Course - Assignments"]
    ),
    update=extend_schema(
        summary="Update assignment (Admin)", tags=["Course - Assignments"]
    ),
    partial_update=extend_schema(
        summary="Partial update assignment (Admin)", tags=["Course - Assignments"]
    ),
    destroy=extend_schema(
        summary="Delete assignment (Admin)", tags=["Course - Assignments"]
    ),
    submit=extend_schema(
        summary="Submit assignment (Student)", tags=["Course - Assignments"]
    ),
    my_submission=extend_schema(
        summary="Get my submission (Student)", tags=["Course - Assignments"]
    ),
)
class AssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    queryset = Assignment.objects.select_related("module", "batch").order_by("due_date")

    # ---------------- SERIALIZER SWITCH ----------------

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AssignmentCreateUpdateSerializer

        if self.action == "retrieve":
            return AssignmentStudentSerializer

        return AssignmentListSerializer

    # ---------------- PERMISSIONS ----------------

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # ---------------- QUERYSET ----------------

    def get_queryset(self):
        user = self.request.user

        # Teacher/Admin → see all
        if hasattr(user, "is_teacher") and user.is_teacher:
            return self.queryset

        # Student → only their batch + course
        enrollment = (
            Enrollment.objects.filter(user=user, is_active=True)
            .select_related("batch", "course")
            .first()
        )

        if not enrollment:
            return Assignment.objects.none()

        return self.queryset.filter(
            batch=enrollment.batch, module__course=enrollment.course
        )

    # ---------------- ACTIONS ----------------

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        assignment = self.get_object()
        student = request.user

        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            student=student,
            defaults={"status": "pending"},
        )

        serializer = AssignmentSubmissionCreateSerializer(
            submission,
            data=request.data,
            context={"request": request},
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return api_response(
            True,
            "Assignment submitted successfully",
            {"assignment_id": str(assignment.id)},
            status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="my-submission")
    def my_submission(self, request, pk=None):
        assignment = self.get_object()
        submission = assignment.submissions.filter(student=request.user).first()

        if not submission:
            return api_response(
                False, "No submission found", None, status.HTTP_404_NOT_FOUND
            )

        return api_response(
            True,
            "Submission retrieved",
            AssignmentSubmissionSerializer(submission).data,
        )


@extend_schema_view(
    list=extend_schema(
        summary="List assignment submissions", tags=["Course - Assignments"]
    ),
    retrieve=extend_schema(
        summary="Get submission details", tags=["Course - Assignments"]
    ),
)
class AssignmentSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Assignment Submissions (Read-Only)

    Students submit via /api/assignments/{id}/submit/

    Endpoints:
    - GET /api/assignment-submissions/ - List submissions
    - GET /api/assignment-submissions/{id}/ - Get submission details
    - POST /api/assignment-submissions/{id}/grade/ - Grade submission (teachers only)
    """

    queryset = AssignmentSubmission.objects.select_related(
        "assignment", "student", "graded_by"
    ).order_by("-submitted_at")
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Students see only their submissions, teachers see all"""
        queryset = super().get_queryset()
        if not (
            hasattr(self.request.user, "is_teacher") and self.request.user.is_teacher
        ):
            queryset = queryset.filter(student=self.request.user)
        return queryset

    @extend_schema(
        tags=["Course - Assignments"],
        summary="Grade submission",
        description="Grade an assignment submission (teachers only)",
        examples=[
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "message": "Assignment graded successfully",
                    "data": {
                        "id": "sub-123",
                        "assignment_title": "Python Basics Exercise",
                        "student_name": "Jane Smith",
                        "score": 85,
                        "graded": True,
                        "feedback": "Great work!",
                        "graded_at": "2025-11-28T15:00:00Z",
                        "graded_by_name": "John Teacher",
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        """
        Grade assignment submission (teachers only)

        Body: {
            "marks_obtained": 85,
            "feedback": "<p>Good work!</p>",
            "status": "graded"
        }
        """
        submission = self.get_object()

        # Check permission
        if not (hasattr(request.user, "is_teacher") and request.user.is_teacher):
            return Response(
                api_response(False, "Only teachers can grade assignments", None),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AssignmentGradeSerializer(
            submission, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save(graded_by=request.user, graded_at=timezone.now())
            return Response(
                api_response(
                    True,
                    "Assignment graded successfully",
                    AssignmentSubmissionSerializer(submission).data,
                )
            )

        return Response(
            api_response(False, "Validation failed", serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )


@extend_schema_view(
    list=extend_schema(summary="List quizzes", tags=["Course - Quizzes"]),
    retrieve=extend_schema(
        summary="Get quiz with questions", tags=["Course - Quizzes"]
    ),
    create=extend_schema(summary="Create quiz (Admin)", tags=["Course - Quizzes"]),
    update=extend_schema(summary="Update quiz (Admin)", tags=["Course - Quizzes"]),
    partial_update=extend_schema(
        summary="Partial update quiz (Admin)", tags=["Course - Quizzes"]
    ),
    destroy=extend_schema(summary="Delete quiz (Admin)", tags=["Course - Quizzes"]),
)
class QuizViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Quizzes

    Student + Teacher access

    Endpoints:
    - GET /api/quizzes/ - List quizzes
    - GET /api/quizzes/{id}/ - Get quiz details with questions
    - POST /api/quizzes/ - Create quiz (teachers/admin only)
    - PUT /api/quizzes/{id}/ - Update quiz (teachers/admin only)
    - DELETE /api/quizzes/{id}/ - Delete quiz (teachers/admin only)
    - POST /api/quizzes/{id}/start/ - Start quiz attempt
    - GET /api/quizzes/{id}/my-attempts/ - Get student's attempts
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = (
        Quiz.objects.select_related("created_by")
        .prefetch_related(
            "questions",
            "questions__options",
            "attempts",
        )
        .order_by("title")
    )

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return QuizCreateUpdateSerializer
        return QuizSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()

        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        queryset = queryset.annotate(
            active_question_count=Count(
                "questions", filter=Q(questions__is_active=True)
            )
        ).filter(active_question_count__gt=0)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return api_response(
            True,
            "Quizzes retrieved successfully",
            serializer.data,
            status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save(created_by=request.user)

        return api_response(
            True,
            "Quiz created successfully",
            QuizSerializer(quiz, context={"request": request}).data,
            status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Course - Quizzes"],
        summary="Start quiz attempt",
        description="Start a quiz attempt; no request body required. Returns attempt metadata and questions.",
        request=None,
        responses={201: QuizAttemptSerializer},
    )
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        quiz = self.get_object()
        student = request.user
        now = timezone.now()

        if quiz.available_from and now < quiz.available_from:
            return api_response(
                False, "Quiz not yet available", None, status.HTTP_400_BAD_REQUEST
            )

        if quiz.available_until and now > quiz.available_until:
            return api_response(
                False, "Quiz is no longer available", None, status.HTTP_400_BAD_REQUEST
            )

        attempt_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()
        if quiz.max_attempts and attempt_count >= quiz.max_attempts:
            return api_response(
                False, "Maximum attempts reached", None, status.HTTP_400_BAD_REQUEST
            )

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            attempt_number=attempt_count + 1,
            started_at=now,
        )

        questions = quiz.questions.filter(is_active=True)

        if quiz.randomize_questions:
            questions = questions.order_by("?")
        else:
            questions = questions.order_by("order")

        total_questions = questions.count()
        marks_per_question = (
            quiz.total_marks / total_questions if total_questions else 0
        )

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
                    {"id": str(o.id), "option_text": o.option_text}
                    for o in q.options.all().order_by("order")
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
    description=(
        "Endpoints to create, update and delete quiz questions. "
        "Use `QuizQuestionCreateUpdateSerializer` for writes and `QuizQuestionSerializer` for reads."
    ),
    request=QuizQuestionCreateUpdateSerializer,
    responses={200: QuizQuestionSerializer, 201: QuizQuestionSerializer},
)
class QuizQuestionViewSet(viewsets.ModelViewSet):
    """
    Teacher/Admin only
    Create / Update / Delete quiz questions
    """

    permission_classes = [IsTeacherOrAdmin]
    serializer_class = QuizQuestionCreateUpdateSerializer

    queryset = QuizQuestion.objects.prefetch_related("options").order_by("order")


@extend_schema_view(
    list=extend_schema(
        summary="List student's quiz attempts", tags=["Course - Quizzes"]
    ),
    retrieve=extend_schema(summary="Get attempt details", tags=["Course - Quizzes"]),
    answer=extend_schema(
        summary="Submit answer for question", tags=["Course - Quizzes"]
    ),
    submit=extend_schema(summary="Submit entire quiz", tags=["Course - Quizzes"]),
    results=extend_schema(
        summary="Get results with correct answers", tags=["Course - Quizzes"]
    ),
)
class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Quiz Attempts

    Endpoints:
    - GET /api/quiz-attempts/ - List student's attempts
    - GET /api/quiz-attempts/{id}/ - Get attempt details
    - POST /api/quiz-attempts/{id}/answer/ - Submit answer for question
    - POST /api/quiz-attempts/{id}/submit/ - Submit entire quiz
    - GET /api/quiz-attempts/{id}/results/ - Get results with correct answers
    """

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

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self.request.user, "role", None) == "student":
            qs = qs.filter(student=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        attempt = self.get_object()

        if attempt.submitted_at:
            return api_response(
                False, "Quiz already submitted", None, status.HTTP_400_BAD_REQUEST
            )

        question = get_object_or_404(
            QuizQuestion, id=request.data.get("question_id"), quiz=attempt.quiz
        )

        answer, _ = QuizAnswer.objects.get_or_create(attempt=attempt, question=question)

        answer.answer_text = request.data.get("answer_text", "")
        answer.selected_options.set(request.data.get("selected_options", []))
        answer.save()

        return api_response(
            True,
            "Answer saved",
            QuizAnswerSerializer(answer, context={"request": request}).data,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def submit(self, request, pk=None):
        attempt = self.get_object()

        if attempt.submitted_at:
            return api_response(
                False, "Quiz already submitted", None, status.HTTP_400_BAD_REQUEST
            )

        answers_data = request.data.get("answers", [])

        if not answers_data:
            return api_response(
                False,
                "No answers submitted",
                None,
                status.HTTP_400_BAD_REQUEST,
            )

        total_questions = attempt.quiz.questions.filter(is_active=True).count()
        marks_per_question = (
            attempt.quiz.total_marks / total_questions if total_questions else 0
        )

        options_map = {
            str(o.id): o
            for o in QuizQuestionOption.objects.filter(question__quiz=attempt.quiz)
        }

        total_marks = 0

        for item in answers_data:
            question = QuizQuestion.objects.filter(
                id=item.get("question_id"), quiz=attempt.quiz
            ).first()
            if not question:
                continue

            quiz_answer, _ = QuizAnswer.objects.get_or_create(
                attempt=attempt, question=question
            )

            if question.question_type in ["mcq", "multiple", "true_false"]:
                selected_ids = item.get("answer", [])
                if not isinstance(selected_ids, list):
                    selected_ids = [selected_ids]

                quiz_answer.selected_options.clear()
                for opt_id in selected_ids:
                    option = options_map.get(str(opt_id))
                    if option:
                        quiz_answer.selected_options.add(option)

                correct_ids = set(
                    question.options.filter(is_correct=True).values_list(
                        "id", flat=True
                    )
                )
                chosen_ids = set(
                    quiz_answer.selected_options.values_list("id", flat=True)
                )

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
        attempt.percentage = (
            (total_marks / attempt.quiz.total_marks) * 100
            if attempt.quiz.total_marks > 0
            else 0
        )
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
            return api_response(
                False, "Quiz not yet submitted", None, status.HTTP_400_BAD_REQUEST
            )

        serializer = QuizAttemptSerializer(attempt, context={"request": request})

        return api_response(
            True,
            "Results retrieved successfully",
            serializer.data,
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
class CourseResourceViewSet(viewsets.ModelViewSet):
    """
    Course Resources API

    Students:
    - Download resources
    - Batch-isolated access

    Teachers/Admin:
    - Full CRUD access
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    queryset = (
        CourseResource.objects.select_related(
            "module", "batch", "live_class", "uploaded_by"
        )
        .prefetch_related("files")
        .filter(is_active=True)
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

        # ---- Students: batch isolation ----
        if getattr(user, "role", None) == "student":
            enrollment = (
                Enrollment.objects.filter(user=user, is_active=True)
                .select_related("batch", "course")
                .first()
            )

            if not enrollment:
                return queryset.none()

            queryset = queryset.filter(
                batch=enrollment.batch,
                module__course=enrollment.course,
            )

        # ---- Filters ----
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

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Download resource and increment count
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
