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

        # Student batch isolation
        if getattr(user, "role", None) == "student":
            enrollment = (
                Enrollment.objects.filter(user=user, is_active=True)
                .select_related("batch")
                .first()
            )

            if not enrollment or not enrollment.batch:
                return queryset.none()

            queryset = queryset.filter(batch=enrollment.batch)

        # Optional module filter
        module_id = self.request.query_params.get("module_id")
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except ValueError:
                return queryset.none()

        return queryset


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


@extend_schema(
    tags=["Course - Quizzes"],
    summary="Manage quizzes (list, retrieve, create, update, delete)",
    description=(
        "List and retrieve quizzes. Use `QuizCreateUpdateSerializer` for "
        "create/update. Responses use `QuizSerializer` for reads and "
        "`QuizAttemptSerializer` for attempt-related responses."
    ),
    request=QuizCreateUpdateSerializer,
    responses={200: QuizSerializer, 201: QuizSerializer},
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


@extend_schema(
    tags=["Course - Quiz Attempts"],
    summary="View and submit quiz attempts",
    description=(
        "List and retrieve quiz attempts. Use `/answer/` to save an answer and `/submit/` to submit the quiz. "
        "`QuizAttemptSerializer` is used for responses."
    ),
    responses={200: QuizAttemptSerializer},
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


class CourseResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for course resources/materials.

    List/Retrieve: Available to enrolled students
    Create/Update/Delete: Teachers and admin only
    """

    queryset = CourseResource.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_class(self):
        """Use different serializers for read vs write operations"""

        if self.action in ["create", "update", "partial_update"]:
            return CourseResourceCreateUpdateSerializer
        return CourseResourceSerializer

    def get_permissions(self):
        """Different permissions for read vs write operations"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter resources based on query parameters and user enrollment"""

        queryset = (
            CourseResource.objects.filter(is_active=True)
            .select_related("module", "live_class", "uploaded_by")
            .order_by("order", "-created_at")
        )

        # Teachers/admin can see all resources
        if self.request.user.is_staff or hasattr(self.request.user, "is_teacher"):
            pass
        else:
            # Students can only see resources from modules they're enrolled in

            enrolled_courses = Enrollment.objects.filter(
                user=self.request.user, is_active=True
            ).values_list("course", flat=True)

            queryset = queryset.filter(module__course__course__in=enrolled_courses)

        # Filter by module_id if provided
        module_id = self.request.query_params.get("module_id")
        if module_id:
            queryset = queryset.filter(module_id=module_id)

        # Filter by live_class_id if provided
        live_class_id = self.request.query_params.get("live_class_id")
        if live_class_id:
            queryset = queryset.filter(live_class_id=live_class_id)

        # Filter by resource_type if provided
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        return queryset

    def list(self, request, *args, **kwargs):
        """List resources with graceful error handling"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)

            return api_response(
                success=True,
                message="Resources retrieved successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            # Return empty array instead of 500 error
            return api_response(
                success=True,
                message="No resources found",
                data=[],
                status_code=status.HTTP_200_OK,
            )

    def retrieve(self, request, *args, **kwargs):
        """Get resource details"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return api_response(
            success=True,
            message="Resource retrieved successfully",
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        """Upload new resource"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set uploaded_by to current user
        resource = serializer.save(uploaded_by=request.user)

        # Calculate file size if file was uploaded
        if resource.file:
            try:
                resource.file_size = resource.file.size
                resource.save(update_fields=["file_size"])
            except Exception:
                pass

        response_serializer = CourseResourceSerializer(
            resource, context={"request": request}
        )

        return api_response(
            success=True,
            message="Resource uploaded successfully",
            data=response_serializer.data,
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Update resource"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        resource = serializer.save()

        # Recalculate file size if new file was uploaded
        if "file" in request.data and resource.file:
            try:
                resource.file_size = resource.file.size
                resource.save(update_fields=["file_size"])
            except Exception:
                pass

        response_serializer = CourseResourceSerializer(
            resource, context={"request": request}
        )

        return api_response(
            success=True,
            message="Resource updated successfully",
            data=response_serializer.data,
            status_code=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """Delete resource"""
        instance = self.get_object()
        instance.delete()

        return api_response(
            success=True,
            message="Resource deleted successfully",
            data=None,
            status_code=status.HTTP_204_NO_CONTENT,
        )

    @extend_schema(
        tags=["Course - Resources"],
        summary="Download resource",
        description="Download resource and increment download count",
    )
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Track resource download

        Increments download count and returns file URL
        """
        resource = self.get_object()

        # Increment download count
        resource.increment_download_count()

        # Return file URL or external URL
        if resource.file:
            file_url = request.build_absolute_uri(resource.file.url)
            return api_response(
                success=True,
                message="Download initiated",
                data={
                    "url": file_url,
                    "title": resource.title,
                    "file_size": resource.get_file_size_display(),
                    "download_count": resource.download_count,
                },
                status_code=status.HTTP_200_OK,
            )
        elif resource.external_url:
            return api_response(
                success=True,
                message="External resource accessed",
                data={
                    "url": resource.external_url,
                    "title": resource.title,
                    "download_count": resource.download_count,
                },
                status_code=status.HTTP_200_OK,
            )
        else:
            return api_response(
                success=False,
                message="No file or URL available",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND,
            )
