"""ViewSets for CustomPayment and EventRegistration."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.decorators import action

from api.models.models_custom_payment import CustomPayment, EventRegistration
from api.permissions import IsStaff
from api.serializers.serializers_custom_payment import (
    CustomPaymentSerializer, EventRegistrationSerializer)
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


@extend_schema_view(
    list=extend_schema(
        summary="List event registrations",
        description="Get list of event registrations. Users see only their own, staff see all.",
        tags=['Event Registration'],
    ),
    create=extend_schema(
        summary="Create event registration",
        description="Register for an event. Students can register themselves, staff can register anyone.",
        tags=['Event Registration'],
    ),
    retrieve=extend_schema(
        summary="Get event registration details",
        description="Get detailed information about a specific event registration.",
        tags=['Event Registration'],
    ),
    update=extend_schema(
        summary="Update event registration",
        description="Update event registration (staff only).",
        tags=['Event Registration'],
    ),
    partial_update=extend_schema(
        summary="Partially update event registration",
        description="Partially update event registration (staff only).",
        tags=['Event Registration'],
    ),
    destroy=extend_schema(
        summary="Delete event registration",
        description="Delete event registration (staff only).",
        tags=['Event Registration'],
    ),
)
class EventRegistrationViewSet(BaseAdminViewSet):
    """ViewSet for managing event registrations."""
    
    queryset = EventRegistration.objects.select_related('user', 'created_by').all()
    serializer_class = EventRegistrationSerializer
    permission_classes = [IsStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'event_type', 'payment_method', 'is_attended', 'user', 'created_by']
    search_fields = ['event_name', 'event_location', 'registration_number', 'user__email']
    ordering_fields = ['created_at', 'event_date', 'total_amount']
    ordering = ['-event_date', '-created_at']
    
    def get_permissions(self):
        """Students can create their own registrations and view their own, staff can do everything."""
        from api.permissions import IsStudent
        if self.action in ['create', 'list', 'retrieve']:
            return [(IsStudent | IsStaff)()]
        return [IsStaff()]
    
    def filter_public_queryset(self, queryset):
        """Users see their own registrations."""
        return queryset.filter(user=self.request.user)
    
    def get_queryset(self):
        """Get queryset - BaseAdminViewSet handles filtering."""
        return super().get_queryset()
    
    def check_object_permissions(self, request, obj):
        """Check if user can access this specific event registration."""
        super().check_object_permissions(request, obj)
        
        # Staff can access everything
        if self.is_staff_user(request.user):
            return
        
        # Users can only access their own registrations
        if obj.user != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to access this event registration.")
    
    @extend_schema(
        summary="Mark payment as completed",
        description="Mark event registration payment as completed (staff only).",
        request=None,
        responses={200: EventRegistrationSerializer},
        tags=['Event Registration'],
    )
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark payment as completed (admin only)."""
        registration = self.get_object()
        registration.mark_as_completed()
        serializer = self.get_serializer(registration)
        return api_response(
            True,
            "Event registration payment marked as completed successfully",
            serializer.data
        )
    
    @extend_schema(
        summary="Mark attendance",
        description="Mark user as attended the event (admin only).",
        request=None,
        responses={200: EventRegistrationSerializer},
        tags=['Event Registration'],
    )
    @action(detail=True, methods=['post'])
    def mark_attendance(self, request, pk=None):
        """Mark attendance for event (admin only)."""
        registration = self.get_object()
        registration.mark_attendance()
        serializer = self.get_serializer(registration)
        return api_response(
            True,
            "Attendance marked successfully",
            serializer.data
        )
