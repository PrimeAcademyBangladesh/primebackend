"""
Views for Assignments and Assignment Submissions

Implements secure, maintainable assignment management with proper
enrollment filtering, late submission handling, and grading logic.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

# Local app imports
from api.models.models_module import (
    Assignment,
    AssignmentSubmission,
    CourseResource,
    LiveClass,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    QuizQuestionOption,
)
from api.permissions import IsTeacherOrAdmin
from api.serializers.serializers_module import (
    AssignmentCreateUpdateSerializer,
    AssignmentGradeSerializer,
    AssignmentListSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentSubmissionSerializer,
    CourseResourceCreateUpdateSerializer,
    LiveClassAttendanceSerializer,
    LiveClassCreateUpdateSerializer,
    QuizAnswerSerializer,
    QuizAttemptSerializer,
    QuizCreateUpdateSerializer,
    QuizQuestionCreateUpdateSerializer,
)
from api.utils.enrollment_filters import filter_queryset_for_student
from api.utils.grading_utils import apply_late_penalty
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
    # Join class and AUto mark attendance
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
        summary="Attendance live class",
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



# ============================================================================
# ASSIGNMENT VIEW SET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List assignments",
        tags=["Course - Assignments"],
        description="List all assignments accessible to the user based on enrollment."
    ),
    retrieve=extend_schema(
        summary="Get assignment details",
        tags=["Course - Assignments"],
        description="Retrieve detailed information about a specific assignment."
    ),
    create=extend_schema(
        summary="Create assignment (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Create a new assignment for a course module and batch."
    ),
    update=extend_schema(
        summary="Update assignment (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Update all fields of an existing assignment."
    ),
    partial_update=extend_schema(
        summary="Partial update assignment (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Update specific fields of an existing assignment."
    ),
    destroy=extend_schema(
        summary="Delete assignment (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Delete an assignment and all its submissions."
    ),
)
class AssignmentViewSet(BaseAdminViewSet):
    """
    Assignment Management API

    Access Control:
    ---------------
    Students:
        - View assignments only for enrolled courses and batches
        - Submit assignments
        - View their own submissions
        - Cannot see inactive assignments

    Teachers/Admin:
        - Full CRUD access to all assignments
        - Can grade submissions
        - View all submissions for their assignments

    Features:
    ---------
    - Enrollment-based access control
    - Late submission tracking and penalties
    - Deadline validation
    - Submission status management
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = Assignment.objects.select_related(
        'module',
        'module__course',
        'batch',
        'created_by'
    ).prefetch_related(
        'submissions'
    ).order_by('-created_at')

    # ========================================================================
    # SERIALIZER CONFIGURATION
    # ========================================================================

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action and user role.

        Returns:
            - AssignmentCreateUpdateSerializer: For create/update actions
            - AssignmentStudentSerializer: For students (limited fields)
            - AssignmentListSerializer: For teachers/admin (full details)
        """
        if self.action in ['create', 'update', 'partial_update']:
            return AssignmentCreateUpdateSerializer

        if self.request.user.role == 'student':
            return AssignmentStudentSerializer

        return AssignmentListSerializer

    # ========================================================================
    # PERMISSION CONFIGURATION
    # ========================================================================

    def get_permissions(self):
        """
        Set permissions based on action.

        - Create/Update/Delete: Teacher or Admin only
        - View/Submit: Any authenticated user (with enrollment filtering)
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    # ========================================================================
    # QUERYSET FILTERING
    # ========================================================================

    def get_queryset(self):
        """
        Filter queryset based on user role and enrollment.

        Logic:
        ------
        1. Admin/Superadmin/Teacher: Access to all assignments
        2. Student: Only assignments for:
           - Batches they are enrolled in
           - Courses they are enrolled in
           - Active assignments only

        Returns:
            QuerySet: Filtered assignment queryset
        """
        user = self.request.user
        queryset = super().get_queryset()

        # Admin/Teacher: Full access
        if user.role in ['admin', 'superadmin', 'teacher']:
            return self._apply_optional_filters(queryset)

        # Student: Enrollment-scoped and active only
        queryset = filter_queryset_for_student(
            queryset,
            user,
            batch_field='batch_id',
            course_field='module__course_id'
        ).filter(is_active=True)

        return self._apply_optional_filters(queryset)

    def _apply_optional_filters(self, queryset):
        """
        Apply optional query parameter filters.

        Supported Filters:
        - module_id: Filter by course module
        - batch_id: Filter by batch
        - status: Filter by assignment status
        """
        # Module filter
        module_id = self.request.query_params.get('module_id')
        if module_id:
            try:
                uuid.UUID(module_id)
                queryset = queryset.filter(module_id=module_id)
            except (ValueError, AttributeError):
                return queryset.none()

        # Batch filter
        batch_id = self.request.query_params.get('batch_id')
        if batch_id:
            try:
                uuid.UUID(batch_id)
                queryset = queryset.filter(batch_id=batch_id)
            except (ValueError, AttributeError):
                return queryset.none()

        return queryset

    # ========================================================================
    # LIST OVERRIDE
    # ========================================================================

    def list(self, request, *args, **kwargs):
        """
        Override list to provide friendly message for students with no assignments.
        """
        queryset = self.filter_queryset(self.get_queryset())

        if request.user.role == 'student' and not queryset.exists():
            return api_response(
                success=True,
                message='No assignments found for your enrolled courses.',
                data=[],
            )

        return super().list(request, *args, **kwargs)

    # ========================================================================
    # CUSTOM ACTIONS
    # ========================================================================

    @extend_schema(
        summary="Submit assignment (Student)",
        tags=["Course - Assignments"],
        description="""
        Submit an assignment or update existing submission.

        Business Rules:
        - Students can only submit assignments for enrolled courses
        - Validates deadline and late submission policy
        - Marks submission as late if past due date
        - Cannot update graded submissions
        - Applies late penalty percentage upon grading

        Request Body:
        - submission_text: Text content of submission
        - file: File upload (optional)
        - attachments: Multiple file uploads (optional)
        """
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        """
        Submit assignment with comprehensive validation.

        Workflow:
        1. Verify student has access to assignment
        2. Check assignment is active
        3. Calculate if submission is late
        4. Validate late submission policy
        5. Create or update submission
        6. Prevent updates to graded submissions

        Args:
            request: HTTP request with submission data
            pk: Assignment ID

        Returns:
            Response with submission details and late penalty info
        """
        assignment = self.get_object()
        student = request.user
        now = timezone.now()

        # ====================================================================
        # STEP 1: Verify Access
        # ====================================================================
        if not self.get_queryset().filter(id=assignment.id).exists():
            return api_response(
                success=False,
                message="You don't have permission to submit this assignment.",
                data=None,
            )

        # ====================================================================
        # STEP 2: Check Assignment Status
        # ====================================================================
        if not assignment.is_active:
            return api_response(
                success=False,
                message="This assignment is no longer accepting submissions.",
                data=None,
            )

        # ====================================================================
        # STEP 3: Calculate Late Status
        # ====================================================================
        is_late = bool(assignment.due_date and now > assignment.due_date)

        # ====================================================================
        # STEP 4: Validate Late Submission Policy
        # ====================================================================
        if is_late and not assignment.late_submission_allowed:
            time_diff = now - assignment.due_date
            hours_late = int(time_diff.total_seconds() / 3600)

            return api_response(
                success=False,
                message=(
                    f"Submission deadline passed {hours_late} hours ago. "
                    "Late submissions are not allowed for this assignment."
                ),
                data={
                    'due_date': assignment.due_date,
                    'current_time': now,
                    'hours_late': hours_late
                },
            )

        # ====================================================================
        # STEP 5: Get or Create Submission
        # ====================================================================
        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            student=student,
            defaults={
                'status': 'submitted',
                'is_late': is_late,
                'submitted_at': now
            }
        )

        # ====================================================================
        # STEP 6: Prevent Updates to Graded Submissions
        # ====================================================================
        if not created and submission.status == 'graded':
            return api_response(
                success=False,
                message=(
                    "Cannot update a graded submission. "
                    "Please contact your instructor if you need to make changes."
                ),
                data={
                    'submission_id': str(submission.id),
                    'graded_at': submission.graded_at,
                    'graded_by': submission.graded_by.get_full_name() if submission.graded_by else None,
                    'marks_obtained': float(submission.marks_obtained) if submission.marks_obtained else None
                },
            )

        # ====================================================================
        # STEP 7: Validate and Save Submission
        # ====================================================================
        serializer = AssignmentSubmissionCreateSerializer(
            submission,
            data=request.data,
            partial=not created,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        serializer.save(
            is_late=is_late,
            status='submitted'
        )

        # ====================================================================
        # STEP 8: Prepare Response Message
        # ====================================================================
        message = (
            "Assignment submitted successfully."
            if created
            else "Submission updated successfully."
        )

        if is_late and assignment.late_submission_penalty > 0:
            message += (
                f" Note: A {assignment.late_submission_penalty}% late penalty "
                "will be applied upon grading."
            )

        # ====================================================================
        # STEP 9: Return Success Response
        # ====================================================================
        return api_response(
            success=True,
            message=message,
            data={
                'submission_id': str(submission.id),
                'assignment_id': str(assignment.id),
                'assignment_title': assignment.title,
                'is_late': is_late,
                'late_penalty_percentage': assignment.late_submission_penalty if is_late else 0,
                'submitted_at': submission.submitted_at,
                'status': submission.status,
                'can_resubmit': submission.status != 'graded'
            },
        )

    @extend_schema(
        summary="Get my submission (Student)",
        tags=["Course - Assignments"],
        description="Retrieve the authenticated student's submission for this assignment."
    )
    @action(detail=True, methods=['get'], url_path='my-submission')
    def my_submission(self, request, pk=None):
        """
        Get authenticated user's submission for this assignment.

        Args:
            request: HTTP request
            pk: Assignment ID

        Returns:
            Response with submission details including grades and feedback
        """
        assignment = self.get_object()

        # Verify student has access
        if not self.get_queryset().filter(id=assignment.id).exists():
            return api_response(
                success=False,
                message="You don't have permission to view this assignment.",
                data=None,
            )

        submission = assignment.submissions.filter(student=request.user).first()

        if not submission:
            return api_response(
                success=False,
                message="No submission found for this assignment.",
                data={
                    'assignment_id': str(assignment.id),
                    'assignment_title': assignment.title,
                    'due_date': assignment.due_date,
                    'can_submit': assignment.is_active
                },
            )

        serializer = AssignmentSubmissionSerializer(
            submission,
            context={'request': request}
        )

        return api_response(
            success=True,
            message='Submission retrieved successfully.',
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Get all submissions for assignment (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Retrieve all student submissions for this assignment."
    )
    @action(
        detail=True,
        methods=['get'],
        permission_classes=[IsTeacherOrAdmin],
        url_path='submissions'
    )
    def submissions(self, request, pk=None):
        """
        Get all submissions for this assignment (Teacher/Admin only).

        Includes:
        - Student information
        - Submission status
        - Grading information
        - Late submission status

        Args:
            request: HTTP request
            pk: Assignment ID

        Returns:
            Response with list of all submissions
        """
        assignment = self.get_object()

        submissions = assignment.submissions.select_related(
            'student',
            'graded_by'
        ).order_by('-submitted_at')

        # Optional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            submissions = submissions.filter(status=status_filter)

        late_filter = request.query_params.get('is_late')
        if late_filter is not None:
            is_late_bool = late_filter.lower() == 'true'
            submissions = submissions.filter(is_late=is_late_bool)

        serializer = AssignmentSubmissionSerializer(
            submissions,
            many=True,
            context={'request': request}
        )

        # Calculate statistics
        total_submissions = submissions.count()
        graded_count = submissions.filter(status='graded').count()
        late_count = submissions.filter(is_late=True).count()

        return api_response(
            success=True,
            message='Submissions retrieved successfully.',
            data={
                'submissions': serializer.data,
                'statistics': {
                    'total_submissions': total_submissions,
                    'graded': graded_count,
                    'pending': total_submissions - graded_count,
                    'late_submissions': late_count
                }
            },
            status_code=status.HTTP_200_OK
        )


# ============================================================================
# ASSIGNMENT SUBMISSION VIEW SET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="List assignment submissions",
        tags=["Course - Assignments"],
        description="List all submissions (filtered by role)."
    ),
    retrieve=extend_schema(
        summary="Get submission details",
        tags=["Course - Assignments"],
        description="Retrieve detailed information about a specific submission."
    ),
    update=extend_schema(
        summary="Update submission (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Update submission details (teachers can update feedback/marks)."
    ),
    partial_update=extend_schema(
        summary="Partially update submission (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Update specific fields of a submission."
    ),
    destroy=extend_schema(
        summary="Delete submission (Admin)",
        tags=["Course - Assignments"],
        description="Delete a submission (admin only)."
    ),
)
class AssignmentSubmissionViewSet(BaseAdminViewSet):
    """
    Assignment Submission Management API

    Access Control:
    ---------------
    Students:
        - View only their own submissions
        - Cannot directly create/update via this endpoint (use Assignment.submit)

    Teachers:
        - View submissions for their courses
        - Grade submissions
        - Provide feedback

    Admin:
        - Full access to all submissions
        - Can delete submissions

    Features:
    ---------
    - Automated late penalty calculation
    - Grade validation
    - Feedback management
    - Submission status tracking
    """

    permission_classes = [permissions.IsAuthenticated]

    queryset = AssignmentSubmission.objects.select_related(
        'assignment',
        'assignment__module',
        'assignment__module__course',
        'assignment__batch',
        'student',
        'graded_by'
    ).order_by('-submitted_at')

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'grade':
            return AssignmentGradeSerializer
        return AssignmentSubmissionSerializer

    def get_queryset(self):
        """
        Filter submissions based on user role.

        Logic:
        - Students: Only their own submissions
        - Teachers: Submissions for their courses
        - Admin: All submissions
        """
        queryset = super().get_queryset()
        user = self.request.user

        # Student: Only own submissions
        if user.role == 'student':
            return queryset.filter(student=user)

        # Teacher: Submissions for their assigned courses
        if user.role == 'teacher':
            return queryset.filter(
                assignment__batch__in=Enrollment.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('batch_id', flat=True)
            )

        # Admin: All submissions
        return queryset

    # ========================================================================
    # GRADING ACTION
    # ========================================================================

    @extend_schema(
        summary="Grade assignment submission (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="""
        Grade a student's assignment submission.

        Business Rules:
        - Automatically calculates and applies late submission penalty
        - Validates marks don't exceed assignment total
        - Ensures marks never go below zero
        - Records grader and timestamp
        - Cannot grade pending (unsubmitted) submissions

        Request Body:
        - marks_obtained: Raw marks before penalty (required)
        - feedback: Grading feedback (optional)
        - status: Submission status, defaults to 'graded'

        Response includes:
        - Original marks (before penalty)
        - Final marks (after penalty)
        - Late penalty percentage applied
        - Grader information
        """
    )
    @action(detail=True, methods=['post'], permission_classes=[IsTeacherOrAdmin])
    @transaction.atomic
    def grade(self, request, pk=None):
        submission = self.get_object()
        assignment = submission.assignment

        if submission.status == 'pending' or not submission.submitted_at:
            return api_response(
                success=False,
                message="Cannot grade a submission that hasn't been submitted yet.",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = AssignmentGradeSerializer(
            submission,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        marks_obtained = serializer.validated_data.get('marks_obtained')
        status_value = serializer.validated_data.get('status', 'graded')
        feedback = serializer.validated_data.get('feedback', submission.feedback or '')

        if marks_obtained is not None:
            if marks_obtained < 0 or marks_obtained > assignment.total_marks:
                return api_response(
                    success=False,
                    message=f"Marks must be between 0 and {assignment.total_marks}.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

        original_marks = marks_obtained
        final_marks = marks_obtained
        penalty_applied = False
        penalty_percentage = Decimal('0')
        penalty_amount = Decimal('0')

        if (
                marks_obtained is not None
                and submission.is_late
                and assignment.late_submission_allowed
                and assignment.late_submission_penalty > 0
        ):
            penalty_percentage = Decimal(str(assignment.late_submission_penalty))
            final_marks = apply_late_penalty(marks_obtained, penalty_percentage)
            penalty_amount = (marks_obtained - final_marks).quantize(Decimal('0.01'))
            penalty_applied = True

        submission.marks_obtained = final_marks
        submission.status = status_value
        submission.feedback = feedback
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save(update_fields=[
            'marks_obtained',
            'status',
            'feedback',
            'graded_by',
            'graded_at'
        ])

        message = "Assignment graded successfully"
        if penalty_applied:
            message += f" (late penalty of {penalty_percentage}% applied)"

        return api_response(
            success=True,
            message=message,
            data={
                'submission_id': str(submission.id),
                'assignment_id': str(assignment.id),
                'student_id': str(submission.student.id),
                'grading': {
                    'original_marks': float(original_marks) if original_marks is not None else None,
                    'final_marks': float(final_marks) if final_marks is not None else None,
                    'penalty_amount': float(penalty_amount),
                    'penalty_percentage': float(penalty_percentage),
                },
                'status': submission.status,
                'graded_at': submission.graded_at,
            },
            status_code=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Bulk grade submissions (Teacher/Admin)",
        tags=["Course - Assignments"],
        description="Grade multiple submissions at once."
    )
    @action(detail=False, methods=['post'], permission_classes=[IsTeacherOrAdmin])
    @transaction.atomic
    def bulk_grade(self, request):
        submissions_data = request.data.get('submissions', [])

        if not submissions_data:
            return api_response(
                success=False,
                message="No submissions provided for grading.",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        results = []

        for item in submissions_data:
            try:
                submission = self.get_queryset().get(id=item['submission_id'])
                assignment = submission.assignment

                if submission.status == 'pending' or not submission.submitted_at:
                    raise ValueError("Submission has not been submitted yet.")

                marks = Decimal(str(item.get('marks_obtained')))
                if marks < 0 or marks > assignment.total_marks:
                    raise ValueError(f"Marks must be between 0 and {assignment.total_marks}.")

                final_marks = marks

                if (
                        submission.is_late
                        and assignment.late_submission_allowed
                        and assignment.late_submission_penalty > 0
                ):
                    final_marks = apply_late_penalty(
                        marks,
                        assignment.late_submission_penalty
                    )

                submission.marks_obtained = final_marks
                submission.feedback = item.get('feedback', '')
                submission.status = 'graded'
                submission.graded_by = request.user
                submission.graded_at = timezone.now()
                submission.save(update_fields=[
                    'marks_obtained',
                    'feedback',
                    'status',
                    'graded_by',
                    'graded_at'
                ])

                results.append({
                    'submission_id': str(submission.id),
                    'status': 'success',
                    'final_marks': float(final_marks),
                })

            except Exception as e:
                results.append({
                    'submission_id': item.get('submission_id'),
                    'status': 'error',
                    'message': str(e),
                })

        return api_response(
            success=True,
            message="Bulk grading completed.",
            data={'results': results},
            status_code=status.HTTP_200_OK
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


# ==============================================================
# STUDENT CONTENT VIEWSETS (MINIMAL + SAFE)
# ==============================================================

from django.db.models import Prefetch
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse

from api.permissions import IsStudent

from api.models.models_order import Enrollment
from api.models.models_course import CourseModule
from api.models.models_module import (
    Assignment,
    Quiz,
    LiveClass,
    CourseResource,
    LiveClassAttendance,
)

from api.serializers.serializers_module import (
    AssignmentStudentSerializer,
    QuizSerializer,
    LiveClassSerializer,
    CourseResourceSerializer,
)


# ==============================================================
# BASE VIEW SET (STUDENT + ENROLLMENT)
# ==============================================================

class StudentBaseViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated, IsStudent]

    def get_batch_ids(self):
        return Enrollment.objects.filter(
            user=self.request.user,
            is_active=True
        ).values_list("batch_id", flat=True)


# ==============================================================
# ASSIGNMENTS
# ==============================================================

class StudentAssignmentViewSet(StudentBaseViewSet):

    @extend_schema(
        summary="Student assignments",
        description="Assignments grouped by module (batch-wise).",
        responses={200: OpenApiResponse(description="Assignments grouped by module")},
        tags=["Student DashBoard"]
    )
    def list(self, request):
        batch_ids = self.get_batch_ids()
        if not batch_ids.exists():
            return api_response(True, "No enrollments found.", [])

        qs = Assignment.objects.filter(
            is_active=True,
            batch_id__in=batch_ids
        ).select_related("module")

        modules = (
            CourseModule.objects
            .filter(module_assignments__in=qs, is_active=True)
            .distinct()
            .order_by("order")
            .prefetch_related(
                Prefetch("module_assignments", queryset=qs.order_by("order"))
            )
        )

        data = [{
            "module_id": m.id,
            "module_title": m.title,
            "module_slug": m.slug,
            "assignments": AssignmentStudentSerializer(
                m.module_assignments.all(),
                many=True,
                context={"request": request},
            ).data,
        } for m in modules]

        return api_response(True, "Assignments retrieved.", data)


# ==============================================================
# QUIZZES
# ==============================================================

class StudentQuizViewSet(StudentBaseViewSet):

    @extend_schema(
        summary="Student quizzes",
        description="Quizzes grouped by module (batch-wise).",
        responses={200: OpenApiResponse(description="Quizzes grouped by module")},
        tags=["Student DashBoard"]
    )
    def list(self, request):
        batch_ids = self.get_batch_ids()
        if not batch_ids.exists():
            return api_response(True, "No enrollments found.", [])

        qs = Quiz.objects.filter(
            is_active=True,
            batch_id__in=batch_ids,
            questions__is_active=True,
        ).distinct()

        modules = (
            CourseModule.objects
            .filter(module_quizzes__in=qs)
            .distinct()
            .order_by("order")
            .prefetch_related(
                Prefetch("module_quizzes", queryset=qs)
            )
        )

        data = [{
            "module_id": m.id,
            "module_title": m.title,
            "module_slug": m.slug,
            "quizzes": QuizSerializer(
                m.module_quizzes.all(),
                many=True,
                context={"request": request},
            ).data,
        } for m in modules]

        return api_response(True, "Quizzes retrieved.", data)


# ==============================================================
# LIVE CLASSES / RECORDINGS
# ==============================================================

class StudentLiveClassViewSet(StudentBaseViewSet):

    @extend_schema(
        summary="Student live classes",
        description="Live classes and recordings grouped by module.",
        responses={200: OpenApiResponse(description="Live classes grouped by module")},
        tags=["Student DashBoard"]
    )
    def list(self, request):
        batch_ids = self.get_batch_ids()
        if not batch_ids.exists():
            return api_response(True, "No enrollments found.", [])

        qs = LiveClass.objects.filter(
            is_active=True,
            batch_id__in=batch_ids
        )

        modules = (
            CourseModule.objects
            .filter(live_classes__in=qs)
            .distinct()
            .order_by("order")
            .prefetch_related(
                Prefetch("live_classes", queryset=qs)
            )
        )

        data = [{
            "module_id": m.id,
            "module_title": m.title,
            "module_slug": m.slug,
            "live_classes": LiveClassSerializer(
                m.live_classes.all(),
                many=True,
                context={"request": request},
            ).data,
        } for m in modules]

        return api_response(True, "Live classes retrieved.", data)


# ==============================================================
# RESOURCES
# ==============================================================

class StudentResourceViewSet(StudentBaseViewSet):

    @extend_schema(
        summary="Student resources",
        description="Resources grouped by module (batch-wise).",
        responses={200: OpenApiResponse(description="Resources grouped by module")},
        tags=["Student DashBoard"]
    )
    def list(self, request):
        batch_ids = self.get_batch_ids()
        if not batch_ids.exists():
            return api_response(True, "No enrollments found.", [])

        qs = CourseResource.objects.filter(
            is_active=True,
            batch_id__in=batch_ids
        )

        modules = (
            CourseModule.objects
            .filter(resources__in=qs)
            .distinct()
            .order_by("order")
            .prefetch_related(
                Prefetch("resources", queryset=qs)
            )
        )

        data = [{
            "module_id": m.id,
            "module_title": m.title,
            "module_slug": m.slug,
            "resources": CourseResourceSerializer(
                m.resources.all(),
                many=True,
                context={"request": request},
            ).data,
        } for m in modules]

        return api_response(True, "Resources retrieved.", data)


# ==============================================================
# ATTENDANCE
# ==============================================================

class StudentAttendanceViewSet(StudentBaseViewSet):

    @extend_schema(
        summary="Student attendance",
        description="Attendance across live classes (batch-wise).",
        responses={200: OpenApiResponse(description="Attendance list")},
        tags=["Student DashBoard"]
    )
    def list(self, request):
        batch_ids = self.get_batch_ids()
        if not batch_ids.exists():
            return api_response(True, "No enrollments found.", [])

        attendance = LiveClassAttendance.objects.filter(
            student=request.user,
            live_class__batch_id__in=batch_ids
        ).select_related("live_class", "live_class__module")

        data = [{
            "module_title": a.live_class.module.title,
            "live_class_title": a.live_class.title,
            "attended": a.attended,
            "joined_at": a.joined_at,
            "left_at": a.left_at,
            "duration_minutes": a.duration_minutes,
        } for a in attendance]

        return api_response(True, "Attendance retrieved.", data)
