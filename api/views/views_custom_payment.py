"""ViewSets for CustomPayment."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.decorators import action

from api.models.models_custom_payment import CustomPayment
from api.permissions import IsStaff
from api.serializers.serializers_custom_payment import CustomPaymentSerializer
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List custom payments",
        description="Get list of custom payments. Students see only their own, staff see all.",
        tags=['Custom Payment'],
    ),
    create=extend_schema(
        summary="Create custom payment",
        description="Admin creates custom payment to enroll student with flexible pricing (staff only).",
        tags=['Custom Payment'],
    ),
    retrieve=extend_schema(
        summary="Get custom payment details",
        description="Get detailed information about a specific custom payment.",
        tags=['Custom Payment'],
    ),
    update=extend_schema(
        summary="Update custom payment",
        description="Update custom payment (staff only).",
        tags=['Custom Payment'],
    ),
    partial_update=extend_schema(
        summary="Partially update custom payment",
        description="Partially update custom payment (staff only).",
        tags=['Custom Payment'],
    ),
    destroy=extend_schema(
        summary="Delete custom payment",
        description="Delete custom payment (staff only).",
        tags=['Custom Payment'],
    ),
)
class CustomPaymentViewSet(BaseAdminViewSet):
    """ViewSet for managing custom payments (admin enrolls student with custom amount)."""

    queryset = CustomPayment.objects.select_related(
        'student', 'course', 'created_by', 'enrollment'
    ).all()
    serializer_class = CustomPaymentSerializer
    permission_classes = [IsStaff]  # Base permission, overridden in get_permissions
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'student', 'course', 'created_by']
    search_fields = ['title', 'description', 'payment_number', 'student__email']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def get_permissions(self):
        """Students can list/retrieve their own, staff can do everything."""
        from api.permissions import IsStudent
        if self.action in ['list', 'retrieve']:
            return [(IsStudent | IsStaff)()]
        return [IsStaff()]

    def filter_public_queryset(self, queryset):
        """Students see their own payments."""
        return queryset.filter(student=self.request.user)

    def get_queryset(self):
        """Get queryset - BaseAdminViewSet handles filtering."""
        return super().get_queryset()

    def check_object_permissions(self, request, obj):
        """Check if user can access this specific custom payment."""
        super().check_object_permissions(request, obj)

        # Staff can access everything
        if self.is_staff_user(request.user):
            return

        # Students can only access their own payments
        if obj.student != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to access this custom payment.")

    def perform_create(self, serializer):
        """Set created_by to current admin user."""
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary="Mark payment as completed",
        description="Mark custom payment as completed and create enrollment (staff only).",
        request=None,
        responses={200: CustomPaymentSerializer},
        tags=['Custom Payment'],
    )
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark payment as completed (admin only)."""
        payment = self.get_object()
        payment.mark_as_completed()
        serializer = self.get_serializer(payment)
        return api_response(
            True,
            "Payment marked as completed successfully",
            serializer.data
        )

