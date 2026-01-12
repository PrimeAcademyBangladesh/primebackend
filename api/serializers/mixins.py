# In api/serializers/mixins.py (create this file if it doesn't exist)

class CoursePurchaseCheckMixin:
    """
    Mixin to add is_purchased checking logic to course serializers.
    Reusable across CourseListSerializer and CourseDetailedSerializer.
    """

    def get_is_purchased(self, obj):
        """
        Return True if current request user is already enrolled in ANY batch of this course.
        Optimized to use annotated queryset value when available.
        """
        # Prefer annotated value when available (avoids per-object queries)
        if hasattr(obj, "is_purchased"):
            return bool(getattr(obj, "is_purchased"))

        # Fallback to database query
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False

        try:
            from api.models.models_order import Enrollment
            return Enrollment.objects.filter(
                user=request.user,
                course=obj,
                is_active=True
            ).exists()
        except Exception:
            return False