from rest_framework import permissions
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema

from api.models.models_course import Course, CourseModule
from api.models.models_module import LiveClass, Assignment, Quiz, CourseResource
from api.models.models_order import Enrollment
from api.permissions import IsStudent
from api.serializers.serializers_module import CourseModuleStudentStudyPlanSerializer
from api.utils.response_utils import api_response


@extend_schema(
    tags=["Course - Modules"],
    summary="Get module study plan (Student)",
    description="""
    Retrieve the **complete study plan** for a specific course module.

    This endpoint is **student-only** and returns **batch-specific content** 
    based on the student's active enrollment.

    ### What this API provides
    For the requested module, the response includes:
    - 📺 **Live Classes** (upcoming, completed, recordings if available)
    - 📝 **Assignments** (submission status, deadlines, marks)
    - 🧠 **Quizzes** (attempt status, availability, best score)
    - 📂 **Study Resources** (notes, recordings, files, links)

    ### Important behavior
    - Only content belonging to the **student’s enrolled batch** is returned
    - Content created for other batches is **automatically hidden**
    - No batch or course ID is required from the frontend
    - The backend guarantees **security, correctness, and isolation**

    ### Typical use case (UI)
    This endpoint powers the **Study Plan / Module Details page**, where students:
    - Expand a module to see all learning activities
    - Track what is completed or pending
    - Open live classes, submit assignments, or start quizzes

    ### Access rules
    - 🔒 Student must be enrolled in the course
    - 🔒 Module must belong to the given course
    - 🔒 Only active content is returned
    """,
)
class CourseModuleStudyPlanView(APIView):
    """
    GET /api/courses/{course_slug}/study-plan/{module_slug}/
    Student-only, batch-safe, production-ready
    """

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, course_slug, module_slug):
        user = request.user

        course = get_object_or_404(
            Course,
            slug=course_slug,
            is_active=True,
        )

        enrollment = get_object_or_404(
            Enrollment,
            user=user,
            course=course,
            is_active=True,
        )

        student_batch = enrollment.batch

        module = get_object_or_404(
            CourseModule.objects.filter(
                course=course,
                slug=module_slug,
                is_active=True,
            ).prefetch_related(
                Prefetch(
                    "live_classes",
                    queryset=LiveClass.objects.filter(
                        batch=student_batch,
                        is_active=True,
                    ).order_by("order"),
                ),
                Prefetch(
                    "assignments",
                    queryset=Assignment.objects.filter(
                        batch=student_batch,
                        is_active=True,
                    ).order_by("order"),
                ),
                Prefetch(
                    "quizzes",
                    queryset=Quiz.objects.filter(
                        batch=student_batch,
                        is_active=True,
                    ).order_by("order"),
                ),
                Prefetch(
                    "resources",
                    queryset=CourseResource.objects.filter(
                        batch=student_batch,
                        is_active=True,
                    ).order_by("order"),
                ),
            )
        )

        serializer = CourseModuleStudentStudyPlanSerializer(
            module,
            context={"request": request},
        )

        return api_response(
            True,
            "Study plan loaded successfully",
            serializer.data,
        )
