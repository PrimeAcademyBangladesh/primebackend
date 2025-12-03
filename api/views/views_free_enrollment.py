from rest_framework.decorators import api_view, permission_classes
from api.permissions import IsStudent
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from api.models.models_order import Enrollment
from api.models.models_course import Course

@extend_schema(
    summary="Enroll in a free course",
    description="Enrolls the students in a free course if the course price is zero.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'course_id': {'type': 'integer', 'description': 'ID of the free course'}
            },
            'required': ['course_id']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'enrollment_id': {'type': 'integer', 'nullable': True},
                'error': {'type': 'string', 'nullable': True}
            }
        }
    },
    tags=['Course - Enrollment']
)
@api_view(['POST'])
@permission_classes([IsStudent])
def enroll_free_course(request):
    course_id = request.data.get('course_id')
    user = request.user
    # Only allow students (not staff/admin)
    if hasattr(user, 'role') and user.role != 'student':
        return Response({'success': False, 'error': 'Only students can enroll in free courses', 'enrollment_id': None})
    try:
        course = Course.objects.get(id=course_id)

        if hasattr(course, 'price') and course.price == 0 and user.role == 'student':
            enrollment, created = Enrollment.objects.get_or_create(user=user, course=course)
            return Response({'success': True, 'enrollment_id': enrollment.id})
        else:
            return Response({'success': False, 'error': 'Course is not free', 'enrollment_id': None})
    except Course.DoesNotExist:
        return Response({'success': False, 'error': 'Course not found', 'enrollment_id': None})
