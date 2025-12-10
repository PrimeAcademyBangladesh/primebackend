"""
Views for Live Classes, Assignments, and Quizzes
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from django.db import models
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from api.models.models_module import (
    LiveClass,
    LiveClassAttendance,
    Assignment,
    AssignmentSubmission,
    Quiz,
    QuizAttempt,
    QuizAnswer,
    QuizQuestion,
    QuizQuestionOption,
)
from api.serializers.serializers_module import (
    LiveClassSerializer,
    LiveClassCreateUpdateSerializer,
    LiveClassAttendanceSerializer,
    AssignmentSerializer,
    AssignmentCreateUpdateSerializer,
    AssignmentSubmissionSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentGradeSerializer,
    QuizSerializer,
    QuizCreateUpdateSerializer,
    QuizAttemptSerializer,
    QuizAnswerSerializer,
)
from api.permissions import IsTeacherOrAdmin
from api.utils.response_utils import api_response


@extend_schema_view(
    list=extend_schema(
        tags=['Course - Live Classes'],
        summary='List live classes',
        description='Get list of all live classes. Can be filtered by module_id and status.',
        parameters=[
            OpenApiParameter(
                name='module_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by module ID',
                required=False
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status (scheduled, ongoing, completed, cancelled)',
                required=False,
                enum=['scheduled', 'ongoing', 'completed', 'cancelled']
            ),
        ],
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Live classes retrieved successfully',
                    'data': [
                        {
                            'id': '01e5b671-334c-48b3-b48e-c4da7b9289a9',
                            'title': 'Python Installation & Setup',
                            'description': 'Learn how to install Python and set up your development environment',
                            'scheduled_date': '2025-11-27T07:31:50.914021Z',
                            'duration_minutes': 90,
                            'status': 'scheduled',
                            'meeting_url': 'https://zoom.us/j/123456789',
                            'meeting_id': 'zoom-123456',
                            'instructor_name': 'John Doe',
                            'module_id': 'abc123',
                            'module_title': 'Introduction to Python',
                            'course_title': 'Python Programming Mastery',
                            'is_upcoming': True,
                            'is_past': False,
                            'can_join': False,
                            'has_recording': False
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Live Classes'],
        summary='Get live class detail',
        description='Get detailed information about a specific live class'
    ),
    create=extend_schema(
        tags=['Course - Live Classes'],
        summary='Create live class',
        description='Create a new live class (teachers/admin only)'
    ),
    update=extend_schema(
        tags=['Course - Live Classes'],
        summary='Update live class',
        description='Update live class details (teachers/admin only)'
    ),
    partial_update=extend_schema(
        tags=['Course - Live Classes'],
        summary='Partially update live class',
        description='Partially update live class details (teachers/admin only)'
    ),
    destroy=extend_schema(
        tags=['Course - Live Classes'],
        summary='Delete live class',
        description='Delete a live class (teachers/admin only)'
    )
)
class LiveClassViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Live Classes
    
    Endpoints:
    - GET /api/live-classes/ - List live classes
    - GET /api/live-classes/{id}/ - Get live class details
    - POST /api/live-classes/ - Create live class (teachers/admin only)
    - PUT /api/live-classes/{id}/ - Update live class (teachers/admin only)
    - DELETE /api/live-classes/{id}/ - Delete live class (teachers/admin only)
    - POST /api/live-classes/{id}/mark-attendance/ - Mark attendance
    - GET /api/live-classes/{id}/attendances/ - Get attendance list (teachers only)
    """
    queryset = LiveClass.objects.select_related(
        'module',
        'instructor'
    ).order_by('scheduled_date')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializers for read and write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return LiveClassCreateUpdateSerializer
        return LiveClassSerializer

    def get_permissions(self):
        """Teachers and admin can create/update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'attendances']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter by module_id if provided"""
        queryset = super().get_queryset()
        module_id = self.request.query_params.get('module_id')
        if module_id:
            # Validate UUID format
            try:
                import uuid
                uuid.UUID(str(module_id))
                queryset = queryset.filter(module_id=module_id)
            except (ValueError, AttributeError):
                # Return empty queryset for invalid UUID
                return queryset.none()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset

    def list(self, request, *args, **kwargs):
        """List live classes with wrapped response"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return api_response(
                success=True,
                message='Live classes retrieved successfully',
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            # Gracefully handle errors - return empty array
            return api_response(
                success=True,
                message='Live classes retrieved successfully',
                data=[],
                status_code=status.HTTP_200_OK
            )

    @extend_schema(
        tags=['Course - Live Classes'],
        summary='Record attendance on join',
        description='Record student attendance when they join the live class (frontend should call when opening the meeting URL)',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Attendance recorded successfully',
                    'data': {
                        'id': 'att-123',
                        'live_class_id': '01e5b671-334c-48b3-b48e-c4da7b9289a9',
                        'student_name': 'Jane Smith',
                        'joined_at': '2025-11-27T08:00:00Z'
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """
        Record attendance when student clicks to join the meeting.

        Frontend should call this endpoint when opening the meeting URL. This will
        create or update a LiveClassAttendance record and set `attended=True` and
        `joined_at` to now if not already set.
        """
        live_class = self.get_object()
        student = request.user

        now = timezone.now()

        attendance, created = LiveClassAttendance.objects.get_or_create(
            live_class=live_class,
            student=student,
            defaults={'attended': True, 'joined_at': now, 'duration_minutes': 0}
        )

        # If record existed but no joined_at, set it. Always mark attended=True
        if not attendance.joined_at:
            attendance.joined_at = now
        attendance.attended = True
        attendance.save()

        serializer = LiveClassAttendanceSerializer(attendance)
        return api_response(True, 'Attendance recorded successfully', serializer.data)

    @extend_schema(
        tags=['Course - Live Classes'],
        summary='Get my attendance',
        description='Get current student\'s attendance status for this live class'
    )
    @action(detail=True, methods=['get'], url_path='my-attendance')
    def my_attendance(self, request, pk=None):
        """Get current student's attendance for this live class"""
        live_class = self.get_object()
        student = request.user
        
        try:
            attendance = LiveClassAttendance.objects.get(
                live_class=live_class,
                student=student
            )
            serializer = LiveClassAttendanceSerializer(attendance)
            return api_response(
                True,
                'Attendance retrieved successfully',
                serializer.data
            )
        except LiveClassAttendance.DoesNotExist:
            return api_response(
                True,
                'No attendance record found',
                {
                    'attended': False,
                    'joined_at': None
                }
            )

    @extend_schema(
        tags=['Course - Live Classes'],
        summary='Get attendance list',
        description='Get attendance list for a live class (teachers only)'
    )
    @action(detail=True, methods=['get'])
    def attendances(self, request, pk=None):
        """Get attendance list for live class (teachers only)"""
        live_class = self.get_object()
        attendances = live_class.attendances.select_related('student').all()
        serializer = LiveClassAttendanceSerializer(attendances, many=True)
        return api_response(
            True,
            'Attendances retrieved successfully',
            {
                'attendances': serializer.data,
                'total_students': attendances.count()
            }
        )


@extend_schema_view(
    list=extend_schema(
        tags=['Course - Assignments'],
        summary='List assignments',
        description='Get list of all assignments. Can be filtered by module_id.',
        parameters=[
            OpenApiParameter(
                name='module_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by module ID',
                required=False
            ),
        ],
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Assignments retrieved successfully',
                    'data': [
                        {
                            'id': '87d2b110-004e-4624-b1c9-f829a4c6c595',
                            'title': 'Python Basics Exercise',
                            'description': 'Complete the Python basics exercises',
                            'assignment_type': 'homework',
                            'due_date': '2025-11-30T21:31:50.914021Z',
                            'total_marks': 100,
                            'passing_marks': 40,
                            'late_submission_allowed': True,
                            'late_submission_penalty': 10,
                            'module_id': 'abc123',
                            'module_title': 'Introduction to Python',
                            'course_title': 'Python Programming Mastery',
                            'submission_count': 0,
                            'is_overdue': False,
                            'days_remaining': 4
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Assignments'],
        summary='Get assignment detail',
        description='Get detailed information about a specific assignment'
    ),
    create=extend_schema(
        tags=['Course - Assignments'],
        summary='Create assignment',
        description='Create a new assignment (teachers/admin only)'
    ),
    update=extend_schema(
        tags=['Course - Assignments'],
        summary='Update assignment',
        description='Update assignment details (teachers/admin only)'
    ),
    partial_update=extend_schema(
        tags=['Course - Assignments'],
        summary='Partially update assignment',
        description='Partially update assignment details (teachers/admin only)'
    ),
    destroy=extend_schema(
        tags=['Course - Assignments'],
        summary='Delete assignment',
        description='Delete an assignment (teachers/admin only)'
    )
)
class AssignmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Assignments
    
    Endpoints:
    - GET /api/assignments/ - List assignments
    - GET /api/assignments/{id}/ - Get assignment details
    - POST /api/assignments/ - Create assignment (teachers/admin only)
    - PUT /api/assignments/{id}/ - Update assignment (teachers/admin only)
    - DELETE /api/assignments/{id}/ - Delete assignment (teachers/admin only)
    - POST /api/assignments/{id}/submit/ - Submit assignment
    - GET /api/assignments/{id}/my-submission/ - Get student's submission
    - GET /api/assignments/{id}/submissions/ - Get all submissions (teachers only)
    """
    queryset = Assignment.objects.select_related('module').annotate(
        submission_count=Count('submissions')
    ).order_by('title')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action in ['create', 'update', 'partial_update']:
            return AssignmentCreateUpdateSerializer
        return AssignmentSerializer

    def get_permissions(self):
        """Teachers and admin can create/update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'submissions']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter by module_id if provided and exclude assignments with empty content"""
        queryset = super().get_queryset()
        module_id = self.request.query_params.get('module_id')
        if module_id:
            # Validate UUID format
            try:
                import uuid
                uuid.UUID(str(module_id))
                queryset = queryset.filter(module_id=module_id)
            except (ValueError, AttributeError):
                # Return empty queryset for invalid UUID
                return queryset.none()
        
        # Filter out assignments with empty title or description
        queryset = queryset.exclude(
            Q(title__isnull=True) | Q(title='') |
            Q(description__isnull=True) | Q(description='')
        )
        
        return queryset

    def list(self, request, *args, **kwargs):
        """List assignments with wrapped response"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return api_response(
                success=True,
                message='Assignments retrieved successfully',
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            # Gracefully handle errors - return empty array
            return api_response(
                success=True,
                message='Assignments retrieved successfully',
                data=[],
                status_code=status.HTTP_200_OK
            )

    @extend_schema(
        tags=['Course - Assignments'],
        summary='Submit assignment',
        description='Submit assignment solution (students)',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Assignment submitted successfully',
                    'data': {
                        'id': 'sub-123',
                        'assignment_id': '87d2b110-004e-4624-b1c9-f829a4c6c595',
                        'assignment_title': 'Python Basics Exercise',
                        'student_name': 'Jane Smith',
                        'submission_text': 'Here is my solution...',
                        'status': 'pending',
                        'submitted_at': '2025-11-27T10:00:00Z',
                        'graded': False,
                        'score': None
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit assignment
        
        Body (multipart/form-data or JSON): {
            "submission_text": "My answer text",
            "submission_file": <file>,
            "submission_url": "https://github.com/..."
        }
        
        At least one of submission_text, submission_file, or submission_url must be provided.
        """
        try:
            assignment = self.get_object()
            student = request.user
            
            # Check if already submitted
            existing_submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            
            if existing_submission and existing_submission.status != 'resubmit':
                return api_response(
                    False, 
                    'You have already submitted this assignment', 
                    None,
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Create or update submission
            serializer = AssignmentSubmissionCreateSerializer(
                existing_submission,
                data=request.data,
                context={'request': request}
            )
            
            if serializer.is_valid():
                submission = serializer.save(
                    assignment=assignment,
                    student=student,
                    status='pending'
                )
                
                # Return simplified response without full serialization
                response_data = {
                    'id': str(submission.id),
                    'assignment': str(submission.assignment.id),
                    'assignment_title': submission.assignment.title,
                    'submission_text': submission.submission_text or '',
                    'submission_file': request.build_absolute_uri(submission.submission_file.url) if submission.submission_file else None,
                    'submission_url': submission.submission_url or '',
                    'submitted_at': submission.submitted_at.isoformat(),
                    'status': submission.status,
                    'is_late': submission.is_late
                }
                
                return api_response(
                    True,
                    'Assignment submitted successfully',
                    response_data,
                    status.HTTP_201_CREATED
                )
            
            return api_response(
                False, 
                'Validation failed', 
                serializer.errors,
                status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return api_response(
                False,
                f'Server error: {str(e)}',
                {'error': str(e), 'type': type(e).__name__},
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        tags=['Course - Assignments'],
        summary='Get my submission',
        description='Get current student\'s submission for this assignment'
    )
    @action(detail=True, methods=['get'], url_path='my-submission')
    def my_submission(self, request, pk=None):
        """Get current student's submission for this assignment"""
        assignment = self.get_object()
        student = request.user
        
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student
        ).first()
        
        if not submission:
            return Response(
                api_response(False, 'No submission found', None),
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AssignmentSubmissionSerializer(submission)
        return Response(api_response(True, 'Submission retrieved successfully', serializer.data))

    @extend_schema(
        tags=['Course - Assignments'],
        summary='Get all submissions',
        description='Get all submissions for this assignment (teachers only)'
    )
    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Get all submissions for assignment (teachers only)"""
        assignment = self.get_object()
        submissions = assignment.submissions.select_related('student').all()
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            submissions = submissions.filter(status=status_filter)
        
        serializer = AssignmentSubmissionSerializer(submissions, many=True)
        return Response(api_response(
            True,
            'Submissions retrieved successfully',
            {
                'submissions': serializer.data,
                'total_submissions': submissions.count()
            }
        ))


@extend_schema_view(
    list=extend_schema(
        tags=['Course - Assignments'],
        summary='List assignment submissions',
        description='Get list of assignment submissions. Students see only their own, teachers see all.',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Submissions retrieved successfully',
                    'data': [
                        {
                            'id': 'sub-123',
                            'assignment_id': '87d2b110-004e-4624-b1c9-f829a4c6c595',
                            'assignment_title': 'Python Basics Exercise',
                            'student_name': 'Jane Smith',
                            'student_email': 'jane@example.com',
                            'submission_text': 'My solution...',
                            'submission_file': 'http://example.com/files/submission.pdf',
                            'status': 'graded',
                            'submitted_at': '2025-11-27T10:00:00Z',
                            'graded': True,
                            'score': 85,
                            'feedback': 'Great work!',
                            'graded_at': '2025-11-28T15:00:00Z'
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Assignments'],
        summary='Get submission detail',
        description='Get detailed information about a specific submission'
    ),
    create=extend_schema(exclude=True),
    update=extend_schema(exclude=True),
    partial_update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True)
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
        'assignment',
        'student',
        'graded_by'
    ).order_by('-submitted_at')
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Students see only their submissions, teachers see all"""
        queryset = super().get_queryset()
        if not (hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher):
            queryset = queryset.filter(student=self.request.user)
        return queryset

    @extend_schema(
        tags=['Course - Assignments'],
        summary='Grade submission',
        description='Grade an assignment submission (teachers only)',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Assignment graded successfully',
                    'data': {
                        'id': 'sub-123',
                        'assignment_title': 'Python Basics Exercise',
                        'student_name': 'Jane Smith',
                        'score': 85,
                        'graded': True,
                        'feedback': 'Great work!',
                        'graded_at': '2025-11-28T15:00:00Z',
                        'graded_by_name': 'John Teacher'
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
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
        if not (hasattr(request.user, 'is_teacher') and request.user.is_teacher):
            return Response(
                api_response(False, 'Only teachers can grade assignments', None),
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AssignmentGradeSerializer(
            submission,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save(graded_by=request.user, graded_at=timezone.now())
            return Response(api_response(
                True,
                'Assignment graded successfully',
                AssignmentSubmissionSerializer(submission).data
            ))
        
        return Response(
            api_response(False, 'Validation failed', serializer.errors),
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema_view(
    list=extend_schema(
        tags=['Course - Quizzes'],
        summary='List quizzes',
        description='Get list of all quizzes. Can be filtered by module_id.',
        parameters=[
            OpenApiParameter(
                name='module_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by module ID',
                required=False
            ),
        ],
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Quizzes retrieved successfully',
                    'data': [
                        {
                            'id': '802c67e6-94e0-4f50-b05d-0e40ec9e9780',
                            'title': 'Python Data Structures Quiz',
                            'description': 'Test your knowledge of Python data structures',
                            'total_marks': 100,
                            'passing_marks': 75,
                            'duration_minutes': 25,
                            'difficulty': 'intermediate',
                            'max_attempts': 2,
                            'show_correct_answers': True,
                            'randomize_questions': False,
                            'module_id': 'abc123',
                            'module_title': 'Introduction to Python',
                            'course_title': 'Python Programming Mastery',
                            'question_count': 10,
                            'attempt_count': 0,
                            'is_available': True
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Quizzes'],
        summary='Get quiz detail',
        description='Get detailed information about a quiz including all questions'
    ),
    create=extend_schema(
        tags=['Course - Quizzes'],
        summary='Create quiz',
        description='Create a new quiz (teachers/admin only)'
    ),
    update=extend_schema(
        tags=['Course - Quizzes'],
        summary='Update quiz',
        description='Update quiz details (teachers/admin only)'
    ),
    partial_update=extend_schema(
        tags=['Course - Quizzes'],
        summary='Partially update quiz',
        description='Partially update quiz details (teachers/admin only)'
    ),
    destroy=extend_schema(
        tags=['Course - Quizzes'],
        summary='Delete quiz',
        description='Delete a quiz (teachers/admin only)'
    )
)
class QuizViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Quizzes
    
    Endpoints:
    - GET /api/quizzes/ - List quizzes
    - GET /api/quizzes/{id}/ - Get quiz details with questions
    - POST /api/quizzes/ - Create quiz (teachers/admin only)
    - PUT /api/quizzes/{id}/ - Update quiz (teachers/admin only)
    - DELETE /api/quizzes/{id}/ - Delete quiz (teachers/admin only)
    - POST /api/quizzes/{id}/start/ - Start quiz attempt
    - GET /api/quizzes/{id}/my-attempts/ - Get student's attempts
    """
    queryset = Quiz.objects.prefetch_related(
        'questions',
        'questions__options'
    ).order_by('title')
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializer for create/update operations."""
        if self.action in ['create', 'update', 'partial_update']:
            return QuizCreateUpdateSerializer
        return QuizSerializer

    def get_permissions(self):
        """Teachers and admin can create/update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter by module_id if provided and exclude quizzes with no questions"""
        queryset = super().get_queryset()
        module_id = self.request.query_params.get('module_id')
        if module_id:
            # Validate UUID format
            try:
                import uuid
                uuid.UUID(str(module_id))
                queryset = queryset.filter(module_id=module_id)
            except (ValueError, AttributeError):
                # Return empty queryset for invalid UUID
                return queryset.none()
        
        # Filter out quizzes with no active questions
        queryset = queryset.annotate(
            active_question_count=Count('questions', filter=Q(questions__is_active=True))
        ).filter(active_question_count__gt=0)
        
        return queryset

    def list(self, request, *args, **kwargs):
        """List quizzes with wrapped response"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return api_response(
                success=True,
                message='Quizzes retrieved successfully',
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            # Gracefully handle errors - return empty array
            return api_response(
                success=True,
                message='Quizzes retrieved successfully',
                data=[],
                status_code=status.HTTP_200_OK
            )

    def create(self, request, *args, **kwargs):
        """Create quiz and return created object with serialized data (includes `id`)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return api_response(
            True,
            'Quiz created successfully',
            serializer.data,
            status_code=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=['Course - Quizzes'],
        summary='Start quiz attempt',
        description='Start a new quiz attempt. Returns quiz with questions.',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Quiz attempt started successfully',
                    'data': {
                        'attempt_id': 'attempt-123',
                        'quiz_id': '802c67e6-94e0-4f50-b05d-0e40ec9e9780',
                        'quiz_title': 'Python Data Structures Quiz',
                        'duration_minutes': 25,
                        'attempt_number': 1,
                        'started_at': '2025-11-27T10:00:00Z',
                        'questions': [
                            {
                                'id': 'q1',
                                'question_text': 'What is a list in Python?',
                                'question_type': 'multiple_choice',
                                'points': 10,
                                'options': [
                                    {'id': 'opt1', 'option_text': 'A mutable sequence', 'order': 1},
                                    {'id': 'opt2', 'option_text': 'An immutable sequence', 'order': 2}
                                ]
                            }
                        ]
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Start a new quiz attempt
        
        Creates QuizAttempt and returns quiz with questions (without correct answers)
        """
        quiz = self.get_object()
        student = request.user
        
        # Check if quiz is available
        now = timezone.now()
        if quiz.available_from and now < quiz.available_from:
            return api_response(
                success=False,
                message='Quiz not yet available',
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if quiz.available_until and now > quiz.available_until:
            return api_response(
                success=False,
                message='Quiz is no longer available',
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check max attempts
        attempt_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()
        if quiz.max_attempts and attempt_count >= quiz.max_attempts:
            return api_response(
                success=False,
                message=f'Maximum attempts ({quiz.max_attempts}) reached',
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create attempt
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            attempt_number=attempt_count + 1,
            started_at=now
        )
        
        # Get quiz questions
        questions_data = []
        
        # Calculate marks per question dynamically (total_marks / question_count)
        active_questions = quiz.questions.filter(is_active=True).order_by('order')
        total_questions = active_questions.count()
        marks_per_question = float(quiz.total_marks) / total_questions if total_questions > 0 else 0
        
        # Map backend question types to frontend format
        type_mapping = {
            'mcq': 'single_choice',
            'true_false': 'single_choice',
            'multiple': 'multiple_choice',
            'short_answer': 'text',
            'essay': 'text'
        }
        
        for question in active_questions:
            # Map question type to frontend format
            frontend_type = type_mapping.get(question.question_type, question.question_type)
            
            q_data = {
                'id': str(question.id),
                'question_text': question.question_text,
                'question_type': frontend_type,
                'points': round(marks_per_question, 2),  # Dynamic marks per question
                'options': None
            }
            
            # Add options for MCQ questions
            if question.question_type in ['mcq', 'multiple', 'true_false']:
                options = []
                for opt in question.options.all().order_by('order'):
                    options.append({
                        'id': str(opt.id),
                        'option_text': opt.option_text
                    })
                q_data['options'] = options
            
            questions_data.append(q_data)
        
        return api_response(
            success=True,
            message='Quiz attempt started successfully',
            data={
                'id': str(attempt.id),
                'quiz_id': str(quiz.id),
                'student_id': str(student.id),
                'attempt_number': attempt.attempt_number,
                'started_at': attempt.started_at,
                'time_limit_minutes': quiz.duration_minutes,
                'questions': questions_data
            },
            status_code=status.HTTP_201_CREATED
        )

    @extend_schema(
        tags=['Course - Quizzes'],
        summary='Get my quiz attempts',
        description='Get all attempts by current student for this quiz'
    )
    @action(detail=True, methods=['get'], url_path='my-attempts')
    def my_attempts(self, request, pk=None):
        """Get all attempts by current student for this quiz"""
        quiz = self.get_object()
        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            student=request.user
        ).order_by('-started_at')
        
        serializer = QuizAttemptSerializer(attempts, many=True)
        return api_response(
            success=True,
            message='Attempts retrieved successfully',
            data={
                'attempts': serializer.data,
                'total_attempts': attempts.count(),
                'max_attempts': quiz.max_attempts
            },
            status_code=status.HTTP_200_OK
        )


@extend_schema_view(
    list=extend_schema(
        tags=['Course - Quizzes'],
        summary='List quiz attempts',
        description='Get list of quiz attempts. Students see only their own attempts.',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Quiz attempts retrieved successfully',
                    'data': [
                        {
                            'id': 'attempt-123',
                            'quiz_id': '802c67e6-94e0-4f50-b05d-0e40ec9e9780',
                            'quiz_title': 'Python Data Structures Quiz',
                            'student_name': 'Jane Smith',
                            'attempt_number': 1,
                            'started_at': '2025-11-27T10:00:00Z',
                            'submitted_at': '2025-11-27T10:23:00Z',
                            'score': 85,
                            'passed': True,
                            'time_taken_minutes': 23
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Quizzes'],
        summary='Get quiz attempt detail',
        description='Get detailed information about a quiz attempt'
    )
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
    queryset = QuizAttempt.objects.select_related(
        'quiz',
        'student'
    ).prefetch_related(
        'answers',
        'answers__question',
        'answers__selected_options'
    ).order_by('-started_at')
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Students see only their attempts"""
        queryset = super().get_queryset()
        if not (hasattr(self.request.user, 'is_teacher') and self.request.user.is_teacher):
            queryset = queryset.filter(student=self.request.user)
        return queryset

    @extend_schema(
        tags=['Course - Quizzes'],
        summary='Submit quiz answer',
        description='Submit answer for a specific question in the quiz attempt',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Answer saved',
                    'data': {
                        'id': 'answer-123',
                        'question_id': 'q1',
                        'selected_options': ['opt1'],
                        'answer_text': 'My answer text'
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def answer(self, request, pk=None):
        """
        Submit answer for a question in quiz attempt
        
        Body: {
            "question_id": "uuid",
            "selected_options": ["option_id1", "option_id2"],  // For MCQ
            "answer_text": "My answer"  // For short answer
        }
        """
        attempt = self.get_object()
        
        # Check if already submitted
        if attempt.submitted_at:
            return Response(
                api_response(False, 'Quiz already submitted', None),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question_id = request.data.get('question_id')
        question = get_object_or_404(QuizQuestion, id=question_id, quiz=attempt.quiz)
        
        # Create or update answer
        answer, created = QuizAnswer.objects.get_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'answer_text': request.data.get('answer_text', '')
            }
        )
        
        if not created:
            answer.answer_text = request.data.get('answer_text', '')
            answer.selected_options.clear()
        
        # Add selected options for MCQ
        selected_options = request.data.get('selected_options', [])
        if selected_options:
            answer.selected_options.set(selected_options)
        
        answer.save()
        
        serializer = QuizAnswerSerializer(answer)
        return Response(api_response(True, 'Answer saved', serializer.data))

    @extend_schema(
        tags=['Course - Quizzes'],
        summary='Submit quiz',
        description='Submit the entire quiz attempt and get auto-graded results',
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'success': True,
                    'message': 'Quiz submitted successfully',
                    'data': {
                        'attempt_id': 'attempt-123',
                        'score': 85,
                        'passed': True,
                        'total_marks': 100,
                        'marks_obtained': 85,
                        'submitted_at': '2025-11-27T10:23:00Z',
                        'time_taken_minutes': 23
                    }
                },
                response_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit quiz and calculate results
        
        Body: {
            "answers": [
                {"question_id": "uuid", "answer": "option-uuid" or ["opt1", "opt2"] or "text"},
                ...
            ]
        }
        """
        attempt = self.get_object()
        
        # Check if already submitted
        if attempt.submitted_at:
            return api_response(
                success=False,
                message='Quiz already submitted',
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Process answers from request
        answers_data = request.data.get('answers', [])
        
        # Get total questions and calculate marks per question dynamically
        total_questions = attempt.quiz.questions.filter(is_active=True).count()
        quiz_total_marks = float(attempt.quiz.total_marks)
        marks_per_question = quiz_total_marks / total_questions if total_questions > 0 else 0
        
        total_marks = 0
        correct_count = 0
        
        for answer_data in answers_data:
            question_id = answer_data.get('question_id')
            answer_value = answer_data.get('answer')
            
            try:
                question = QuizQuestion.objects.get(id=question_id, quiz=attempt.quiz)
            except QuizQuestion.DoesNotExist:
                continue
            
            # Create or update answer
            quiz_answer, created = QuizAnswer.objects.get_or_create(
                attempt=attempt,
                question=question
            )
            
            # Process based on question type
            if question.question_type in ['mcq', 'multiple', 'true_false']:
                # MCQ - auto-grade
                if isinstance(answer_value, list):
                    selected_ids = answer_value
                else:
                    selected_ids = [answer_value]
                
                # Clear existing and add new selections
                quiz_answer.selected_options.clear()
                for opt_id in selected_ids:
                    try:
                        option = QuizQuestionOption.objects.get(id=opt_id)
                        quiz_answer.selected_options.add(option)
                    except QuizQuestionOption.DoesNotExist:
                        pass
                
                # Check correctness
                correct_options = set(
                    question.options.filter(is_correct=True).values_list('id', flat=True)
                )
                selected_options = set(quiz_answer.selected_options.values_list('id', flat=True))
                
                if correct_options == selected_options:
                    # Award dynamic marks per question (total_marks / question_count)
                    quiz_answer.marks_awarded = marks_per_question
                    quiz_answer.is_correct = True
                    total_marks += marks_per_question
                    correct_count += 1
                else:
                    quiz_answer.marks_awarded = 0
                    quiz_answer.is_correct = False
            else:
                # Text answer - save but don't auto-grade
                quiz_answer.answer_text = answer_value
                quiz_answer.marks_awarded = 0  # Requires manual grading
            
            quiz_answer.answered_at = timezone.now()
            quiz_answer.save()
        
        # Update attempt
        attempt.submitted_at = timezone.now()
        attempt.marks_obtained = total_marks
        attempt.passed = total_marks >= attempt.quiz.passing_marks
        attempt.status = 'submitted'
        attempt.save()
        
        time_taken = (attempt.submitted_at - attempt.started_at).total_seconds() / 60
        
        return api_response(
            success=True,
            message='Quiz submitted successfully',
            data={
                'attempt_id': str(attempt.id),
                'score': float(total_marks),
                'total_marks': float(attempt.quiz.total_marks),
                'passing_marks': float(attempt.quiz.passing_marks),
                'passed': attempt.passed,
                'submitted_at': attempt.submitted_at,
                'time_taken_minutes': int(time_taken),
                'correct_answers': correct_count,
                'total_questions': len(answers_data),
                'feedback': 'Great job! You passed the quiz.' if attempt.passed else 'Keep practicing!'
            },
            status_code=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['Course - Quizzes'],
        summary='Get quiz results',
        description='Get detailed quiz results with correct answers (only after submission)'
    )
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """
        Get quiz results with correct answers
        
        Only available after submission
        """
        attempt = self.get_object()
        
        if not attempt.submitted_at:
            return api_response(
                success=False,
                message='Quiz not yet submitted',
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = QuizAttemptSerializer(attempt, context={'show_correct_answers': True})
        return api_response(
            success=True,
            message='Results retrieved successfully',
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )


# ========== Course Resources ViewSet ==========

@extend_schema_view(
    list=extend_schema(
        tags=['Course - Resources'],
        summary='List course resources',
        description='Get list of course resources/materials. Filter by module_id or live_class_id.',
        parameters=[
            OpenApiParameter(
                name='module_id',
                type=OpenApiTypes.UUID,
                required=False,
                description='Filter resources by module'
            ),
            OpenApiParameter(
                name='live_class_id',
                type=OpenApiTypes.UUID,
                required=False,
                description='Filter resources by live class'
            ),
            OpenApiParameter(
                name='resource_type',
                type=OpenApiTypes.STR,
                required=False,
                description='Filter by resource type (pdf, video, slide, code, document, link, other)'
            ),
        ]
    ),
    retrieve=extend_schema(
        tags=['Course - Resources'],
        summary='Get resource details',
        description='Get detailed information about a specific resource'
    ),
    create=extend_schema(
        tags=['Course - Resources'],
        summary='Upload course resource',
        description='Upload a new course resource (teachers/admin only)'
    ),
    update=extend_schema(
        tags=['Course - Resources'],
        summary='Update course resource',
        description='Update an existing resource (teachers/admin only)'
    ),
    partial_update=extend_schema(
        tags=['Course - Resources'],
        summary='Partially update resource',
        description='Partially update a resource (teachers/admin only)'
    ),
    destroy=extend_schema(
        tags=['Course - Resources'],
        summary='Delete course resource',
        description='Delete a resource (teachers/admin only)'
    ),
)
class CourseResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for course resources/materials.
    
    List/Retrieve: Available to enrolled students
    Create/Update/Delete: Teachers and admin only
    """
    from api.models.models_module import CourseResource
    queryset = CourseResource.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Use different serializers for read vs write operations"""
        from api.serializers.serializers_module import (
            CourseResourceSerializer,
            CourseResourceCreateUpdateSerializer
        )
        if self.action in ['create', 'update', 'partial_update']:
            return CourseResourceCreateUpdateSerializer
        return CourseResourceSerializer
    
    def get_permissions(self):
        """Different permissions for read vs write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """Filter resources based on query parameters and user enrollment"""
        from api.models.models_module import CourseResource
        queryset = CourseResource.objects.filter(is_active=True).select_related(
            'module',
            'live_class',
            'uploaded_by'
        ).order_by('order', '-created_at')
        
        # Teachers/admin can see all resources
        if self.request.user.is_staff or hasattr(self.request.user, 'is_teacher'):
            pass
        else:
            # Students can only see resources from modules they're enrolled in
            from api.models.models_order import Enrollment
            enrolled_courses = Enrollment.objects.filter(
                user=self.request.user,
                is_active=True
            ).values_list('course', flat=True)
            
            queryset = queryset.filter(
                module__course__course__in=enrolled_courses
            )
        
        # Filter by module_id if provided
        module_id = self.request.query_params.get('module_id')
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        
        # Filter by live_class_id if provided
        live_class_id = self.request.query_params.get('live_class_id')
        if live_class_id:
            queryset = queryset.filter(live_class_id=live_class_id)
        
        # Filter by resource_type if provided
        resource_type = self.request.query_params.get('resource_type')
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
                message='Resources retrieved successfully',
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            # Return empty array instead of 500 error
            return api_response(
                success=True,
                message='No resources found',
                data=[],
                status_code=status.HTTP_200_OK
            )
    
    def retrieve(self, request, *args, **kwargs):
        """Get resource details"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            success=True,
            message='Resource retrieved successfully',
            data=serializer.data,
            status_code=status.HTTP_200_OK
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
                resource.save(update_fields=['file_size'])
            except Exception:
                pass
        
        # Return full serialized response
        from api.serializers.serializers_module import CourseResourceSerializer
        response_serializer = CourseResourceSerializer(resource, context={'request': request})
        
        return api_response(
            success=True,
            message='Resource uploaded successfully',
            data=response_serializer.data,
            status_code=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update resource"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        resource = serializer.save()
        
        # Recalculate file size if new file was uploaded
        if 'file' in request.data and resource.file:
            try:
                resource.file_size = resource.file.size
                resource.save(update_fields=['file_size'])
            except Exception:
                pass
        
        # Return full serialized response
        from api.serializers.serializers_module import CourseResourceSerializer
        response_serializer = CourseResourceSerializer(resource, context={'request': request})
        
        return api_response(
            success=True,
            message='Resource updated successfully',
            data=response_serializer.data,
            status_code=status.HTTP_200_OK
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete resource"""
        instance = self.get_object()
        instance.delete()
        
        return api_response(
            success=True,
            message='Resource deleted successfully',
            data=None,
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    @extend_schema(
        tags=['Course - Resources'],
        summary='Download resource',
        description='Download resource and increment download count'
    )
    @action(detail=True, methods=['get'])
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
                message='Download initiated',
                data={
                    'url': file_url,
                    'title': resource.title,
                    'file_size': resource.get_file_size_display(),
                    'download_count': resource.download_count
                },
                status_code=status.HTTP_200_OK
            )
        elif resource.external_url:
            return api_response(
                success=True,
                message='External resource accessed',
                data={
                    'url': resource.external_url,
                    'title': resource.title,
                    'download_count': resource.download_count
                },
                status_code=status.HTTP_200_OK
            )
        else:
            return api_response(
                success=False,
                message='No file or URL available',
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
