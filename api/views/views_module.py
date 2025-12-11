"""Course Module Management API for Teachers and Students."""

from django.db import models
from django.db.models import Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view, OpenApiExample
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.models.models_course import Course, CourseDetail, CourseModule
from api.permissions import IsCourseManager, IsStudentOwner, IsTeacherOrAdmin
from api.serializers.serializers_course import CourseModuleSerializer
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from rest_framework.parsers import FormParser, MultiPartParser

# ========== Teacher Module Management ViewSet ==========

@extend_schema_view(
    list=extend_schema(
        summary="List all modules",
        description="Get paginated list of all modules with search and ordering.",
        parameters=[
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by title or description'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: order, created_at, -order, -created_at'),
        ],
        tags=["Modules - Teacher"]
    ),
    retrieve=extend_schema(
        summary="Get module details",
        description="Retrieve a specific module by ID.",
        tags=["Modules - Teacher"]
    ),
    create=extend_schema(
        summary="Create module",
        description="Create a new course module. Order is auto-assigned if not provided.",
        examples=[
            OpenApiExample(
                'Create Module',
                value={
                    'course': 'uuid-here',
                    'title': 'Introduction to Python',
                    'short_description': '<p>Learn Python basics</p>',
                    'is_active': True
                }
            )
        ],
        tags=["Modules - Teacher"]
    ),
    update=extend_schema(
        summary="Update module",
        description="Full update of module fields.",
        tags=["Modules - Teacher"]
    ),
    partial_update=extend_schema(
        summary="Partial update",
        description="Update specific module fields only.",
        tags=["Modules - Teacher"]
    ),
    destroy=extend_schema(
        summary="Delete module",
        description="Delete module and associated content.",
        tags=["Modules - Teacher"]
    )
)
class TeacherModuleViewSet(viewsets.ModelViewSet):
    """
    Teacher Module Management.
    
    Teachers can create, read, update, and delete course modules.
    Modules are the main building blocks of a course curriculum.
    """
    
    serializer_class = CourseModuleSerializer
    permission_classes = [IsCourseManager]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    parser_classes = (MultiPartParser, FormParser)
    search_fields = ['title', 'short_description']
    ordering_fields = ['order', 'created_at']
    ordering = ['order']
    
    def get_queryset(self):
        """Get all modules with course information."""
        return CourseModule.objects.select_related(
            'course__course'
        ).filter(is_active=True)
    
    def perform_create(self, serializer):
        """Auto-assign order if not provided."""
        course_detail = serializer.validated_data.get('course')
        if 'order' not in serializer.validated_data:
            # Get the highest order for this course and increment
            max_order = CourseModule.objects.filter(
                course=course_detail
            ).aggregate(max_order=models.Max('order'))['max_order'] or 0
            serializer.save(order=max_order + 1)
        else:
            serializer.save()
    
    @extend_schema(
        summary="Filter modules by course",
        description="Get all modules for a specific course with pagination.",
        parameters=[
            OpenApiParameter('course_id', OpenApiTypes.UUID, OpenApiParameter.QUERY, 
                           description='Course UUID', required=True)
        ],
        responses={200: CourseModuleSerializer(many=True)},
        tags=["Modules - Teacher"]
    )
    @action(detail=False, methods=['get'], url_path='by-course')
    def by_course(self, request):
        """Get all modules for a specific course."""
        course_id = request.query_params.get('course_id')
        
        if not course_id:
            return Response(
                api_response(False, "course_id parameter is required", None),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify course exists and get its detail
        try:
            course = Course.objects.get(id=course_id, is_active=True)
            course_detail = course.detail
        except Course.DoesNotExist:
            return Response(
                api_response(False, "Course not found", None),
                status=status.HTTP_404_NOT_FOUND
            )
        except CourseDetail.DoesNotExist:
            return Response(
                api_response(False, "Course detail not found", None),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get modules for this course
        modules = self.get_queryset().filter(course=course_detail)
        
        # Paginate
        page = self.paginate_queryset(modules)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(modules, many=True)
        return Response(
            api_response(True, "Modules retrieved successfully", serializer.data),
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Reorder modules",
        description="Update module order by providing sorted array of module IDs.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'module_ids': {
                        'type': 'array',
                        'items': {'type': 'string', 'format': 'uuid'},
                        'example': ['uuid1', 'uuid2', 'uuid3']
                    }
                },
                'required': ['module_ids']
            }
        },
        responses={200: OpenApiTypes.OBJECT},
        tags=["Modules - Teacher"]
    )
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder_modules(self, request):
        """Reorder modules by updating their order field."""
        module_ids = request.data.get('module_ids', [])
        
        if not module_ids:
            return Response(
                api_response(False, "module_ids array is required", None),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update order for each module
        updated_count = 0
        for index, module_id in enumerate(module_ids, start=1):
            try:
                module = CourseModule.objects.get(id=module_id)
                module.order = index
                module.save(update_fields=['order'])
                updated_count += 1
            except CourseModule.DoesNotExist:
                continue
        
        return Response(
            api_response(
                True,
                f"Successfully reordered {updated_count} modules",
                {'updated_count': updated_count}
            ),
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Get module with content",
        description="Retrieve module with associated quizzes, assignments, and counts.",
        responses={200: OpenApiTypes.OBJECT},
        tags=["Modules - Teacher"]
    )
    @action(detail=True, methods=['get'], url_path='with-content')
    def with_content(self, request, pk=None):
        """Get module with all associated content.
        
        ⚠️ Note: This endpoint no longer includes quizzes and assignments.
        Use the NEW system instead:
        - GET /api/live-classes/?module_id={module_id}
        - GET /api/assignments/?module_id={module_id}
        - GET /api/quizzes/?module_id={module_id}
        """
        module = self.get_object()
        
        # Serialize module
        module_data = self.get_serializer(module).data
        
        # Note about new system
        module_data['note'] = 'Use /api/live-classes/, /api/assignments/, /api/quizzes/ endpoints for module content'
        
        return Response(
            api_response(True, "Module retrieved successfully", module_data),
            status=status.HTTP_200_OK
        )


# ========== Student Module ViewSet ==========

@extend_schema_view(
    list=extend_schema(
        summary="List enrolled modules",
        description="View modules from your enrolled courses only.",
        parameters=[
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by title'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: order, created_at'),
        ],
        tags=["Modules - Student"]
    ),
    retrieve=extend_schema(
        summary="Get module details",
        description="Retrieve module from an enrolled course.",
        tags=["Modules - Student"]
    )
)
class StudentModuleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Student Module Access.
    
    Students can view modules from courses they are enrolled in.
    Read-only access - students cannot create or modify modules.
    """
    
    serializer_class = CourseModuleSerializer
    permission_classes = [IsStudentOwner]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title']
    ordering = ['order']
    
    def get_queryset(self):
        """Get modules from enrolled courses only."""
        user = self.request.user
        
        # Get courses the student is enrolled in
        enrolled_courses = user.enrollments.filter(
            is_active=True
        ).values_list('course_id', flat=True)
        
        # Get course details for those courses
        course_details = CourseDetail.objects.filter(
            course_id__in=enrolled_courses
        ).values_list('id', flat=True)
        
        # Get modules for those course details
        return CourseModule.objects.select_related(
            'course__course'
        ).filter(
            course_id__in=course_details,
            is_active=True
        )
    
    @extend_schema(
        summary="Filter by enrolled course",
        description="Get all modules for a specific enrolled course.",
        parameters=[
            OpenApiParameter('course_id', OpenApiTypes.UUID, OpenApiParameter.QUERY,
                           description='Course UUID', required=True)
        ],
        responses={
            200: CourseModuleSerializer(many=True),
            403: OpenApiTypes.OBJECT
        },
        tags=["Modules - Student"]
    )
    @action(detail=False, methods=['get'], url_path='by-course')
    def by_course(self, request):
        """Get all modules for a specific enrolled course."""
        course_id = request.query_params.get('course_id')
        
        if not course_id:
            return Response(
                api_response(False, "course_id parameter is required", None),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify student is enrolled in this course
        is_enrolled = request.user.enrollments.filter(
            course_id=course_id,
            is_active=True
        ).exists()
        
        if not is_enrolled:
            return Response(
                api_response(False, "You are not enrolled in this course", None),
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get course detail
        try:
            course = Course.objects.get(id=course_id, is_active=True)
            course_detail = course.detail
        except (Course.DoesNotExist, CourseDetail.DoesNotExist):
            return Response(
                api_response(False, "Course not found", None),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get modules
        modules = self.get_queryset().filter(course=course_detail)
        
        # Paginate
        page = self.paginate_queryset(modules)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(modules, many=True)
        return Response(
            api_response(True, "Modules retrieved successfully", serializer.data),
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Get module with progress",
        description="Retrieve module with your personal progress, quiz attempts, and assignment submissions.",
        responses={200: OpenApiTypes.OBJECT},
        tags=["Modules - Student"]
    )
    @action(detail=True, methods=['get'], url_path='with-progress')
    def with_progress(self, request, pk=None):
        """Get module with student progress.
        
        ⚠️ Note: Progress tracking moved to NEW system.
        Use these endpoints instead:
        - GET /api/live-classes/?module_id={module_id} (with attendance)
        - GET /api/assignments/?module_id={module_id} (with submissions)
        - GET /api/quizzes/?module_id={module_id} (with attempts)
        """
        module = self.get_object()
        user = request.user
        
        # Serialize module
        module_data = self.get_serializer(module).data
        
        # Note about new system
        module_data['note'] = 'Use /api/live-classes/, /api/assignments/, /api/quizzes/ endpoints for progress tracking'
        module_data['module_id'] = str(module.id)
        
        return Response(
            api_response(True, "Module retrieved successfully. Use new endpoints for progress.", module_data),
            status=status.HTTP_200_OK
        )
