"""Order, OrderItem, and Enrollment API views."""

from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.models.models_order import Enrollment, Order, OrderItem
from api.permissions import IsAdmin, IsStaff, IsStudent
from api.serializers.serializers_order import (
    EnrollmentCreateSerializer,
    EnrollmentDetailSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderListSerializer,
    OrderUpdateSerializer,
)
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet

# ========== Order ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List orders",
        description="Staff see all orders. Users see only their own orders.",
        responses={200: OrderListSerializer},
        tags=["Course - Orders"],
    ),
    retrieve=extend_schema(
        summary="Retrieve order by ID",
        description="Get detailed order information with all items.",
        responses={200: OrderDetailSerializer},
        tags=["Course - Orders"],
    ),
    create=extend_schema(
        summary="Create an order",
        description="Create a new order with items. This will be the checkout endpoint.",
        responses={201: OrderCreateSerializer},
        tags=["Course - Orders"],
    ),
    update=extend_schema(
        summary="Update order",
        description="Update order status and payment information (staff only).",
        responses={200: OrderUpdateSerializer},
        tags=["Course - Orders"],
    ),
    partial_update=extend_schema(
        summary="Partially update order",
        responses={200: OrderUpdateSerializer},
        tags=["Course - Orders"],
    ),
    destroy=extend_schema(
        summary="Delete order",
        description="Delete order (staff only).",
        responses={204: None},
        tags=["Course - Orders"],
    ),
)
class OrderViewSet(BaseAdminViewSet):
    """
    Order CRUD with role-based access.
    - Staff: can see and manage all orders
    - Users: can create orders and view their own
    - Public: no access
    """

    queryset = Order.objects.select_related("user", "coupon").prefetch_related("items__course").all()

    serializer_class = OrderListSerializer
    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "payment_method", "currency", "user"]
    search_fields = ["order_number", "billing_email", "billing_name", "user__email"]
    ordering_fields = ["created_at", "total_amount", "completed_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """
        Students can list/retrieve/my_orders (their own only).
        Staff can view all orders.
        Students can create orders (via frontend enroll/buy button) for themselves.
        Staff can also create orders.
        Only Admin can perform destructive mutations by default (update/delete).
        """
        from api.permissions import IsStudent

        if self.action in ["list", "retrieve", "my_orders"]:
            # Students can view their own, staff/admin can view all
            return [(IsStudent | IsStaff)()]

        # Allow students and staff to create orders (frontend enroll/buy button)
        if self.action == "create":
            return [(IsStudent | IsStaff)()]

        # All other mutations require Admin only (updates/deletes)
        return [IsAdmin()]

    def filter_public_queryset(self, queryset):
        """
        Students see only their own orders.
        This is called by BaseAdminViewSet.get_queryset() for non-staff users
        during list/retrieve actions.
        """
        return queryset.filter(user=self.request.user)

    def get_queryset(self):
        """Get queryset - BaseAdminViewSet handles filtering."""
        return super().get_queryset()

    def check_object_permissions(self, request, obj):
        """Check if user can access this specific order."""
        super().check_object_permissions(request, obj)

        # Staff can access everything
        if self.is_staff_user(request.user):
            return

        # Students can only access their own orders
        if obj.user != request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You don't have permission to access this order.")

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        if self.action == "retrieve":
            return OrderDetailSerializer
        elif self.action == "create":
            return OrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return OrderUpdateSerializer
        return OrderListSerializer

    def perform_create(self, serializer):
        """Auto-set user to current user on order creation."""
        # Only admin can create orders for anyone, others only for themselves
        user_role = self.request.user.role if hasattr(self.request.user, "role") else None

        if "user" in serializer.validated_data and serializer.validated_data["user"] != self.request.user:
            # Only admin can create orders for others
            if user_role != "admin":
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("You can only create orders for yourself.")

        # If user is not specified or non-admin creating order, use request.user
        if "user" not in serializer.validated_data or user_role != "admin":
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @extend_schema(
        summary="Get my orders",
        description="Get all orders for the current authenticated user.",
        responses={200: OrderListSerializer},
        tags=["Course - Orders"],
    )
    @action(detail=False, methods=["get"], permission_classes=[IsStudent | IsStaff])
    def my_orders(self, request):
        """Get all orders for current user."""
        queryset = self.get_queryset().filter(user=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                True,
                "Your orders retrieved successfully",
                self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(True, "Your orders retrieved successfully", serializer.data)

    @extend_schema(
        summary="Cancel order",
        description="Cancel a pending or processing order.",
        responses={200: OrderDetailSerializer},
        tags=["Course - Orders"],
    )
    @action(detail=True, methods=["post"], permission_classes=[IsStaff])
    def cancel_order(self, request, pk=None):
        """Cancel an order (staff only)."""
        order = self.get_object()

        if not order.can_be_cancelled():
            return api_response(
                False,
                f"Order cannot be cancelled. Current status: {order.get_status_display()}",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        order.status = "cancelled"
        order.cancelled_at = timezone.now()
        order.save()

        serializer = OrderDetailSerializer(order)
        return api_response(True, f"Order {order.order_number} cancelled successfully", serializer.data)

    @extend_schema(
        summary="Complete order",
        description="Mark order as completed and create enrollments.",
        responses={200: OrderDetailSerializer},
        tags=["Course - Orders"],
    )
    @action(detail=True, methods=["post"], permission_classes=[IsStaff])
    def complete_order(self, request, pk=None):
        """Complete an order and create enrollments (staff only)."""
        order = self.get_object()

        if order.status == "completed":
            return api_response(False, "Order is already completed", {}, status.HTTP_400_BAD_REQUEST)

        # Mark as completed (this also creates enrollments)
        order.mark_as_completed()

        serializer = OrderDetailSerializer(order)
        return api_response(
            True,
            f"Order {order.order_number} completed successfully. Enrollments created.",
            serializer.data,
        )

    @extend_schema(
        summary="Get order statistics",
        description="Get order statistics for staff (total orders, revenue, etc.).",
        responses={200: dict},
        tags=["Course - Orders"],
    )
    @action(detail=False, methods=["get"], permission_classes=[IsStaff])
    def statistics(self, request):
        """Get order statistics (staff only)."""
        from django.db.models import Avg, Count, Sum

        queryset = self.get_queryset()

        stats = {
            "total_orders": queryset.count(),
            "completed_orders": queryset.filter(status="completed").count(),
            "pending_orders": queryset.filter(status="pending").count(),
            "total_revenue": queryset.filter(status="completed").aggregate(total=Sum("total_amount"))["total"] or 0,
            "average_order_value": queryset.filter(status="completed").aggregate(avg=Avg("total_amount"))["avg"] or 0,
            "orders_by_status": {
                status_choice[0]: queryset.filter(status=status_choice[0]).count() for status_choice in Order.STATUS_CHOICES
            },
        }

        return api_response(True, "Order statistics retrieved successfully", stats)


# ========== OrderItem ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List order items",
        description="Staff only - view all order items.",
        responses={200: OrderItemSerializer},
        tags=["Course - Orders"],
    ),
    retrieve=extend_schema(
        summary="Retrieve order item",
        responses={200: OrderItemSerializer},
        tags=["Course - Orders"],
    ),
    create=extend_schema(exclude=True),
    update=extend_schema(exclude=True),
    partial_update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class OrderItemViewSet(BaseAdminViewSet):
    """
    OrderItem ViewSet - Staff only.
    Note: Order items are typically created as part of Order creation,
    not as standalone entities. This viewset is mainly for admin viewing.
    """

    queryset = OrderItem.objects.select_related("order", "course").all()

    serializer_class = OrderItemSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["order", "course", "currency"]
    search_fields = ["order__order_number", "course__title", "course_title"]
    ordering_fields = ["created_at", "price"]
    ordering = ["-created_at"]

    # Disable create/update/delete since items are managed through Order
    def create(self, request, *args, **kwargs):
        return api_response(
            False,
            "Order items cannot be created directly. Create an Order instead.",
            {},
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return api_response(
            False,
            "Order items cannot be updated directly.",
            {},
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return api_response(
            False,
            "Order items cannot be deleted directly.",
            {},
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ========== Enrollment ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List enrollments",
        description="Staff see all enrollments. Users see only their own enrollments.",
        responses={200: EnrollmentSerializer},
        tags=["Course - Enrollments"],
    ),
    retrieve=extend_schema(
        summary="Retrieve enrollment",
        responses={200: EnrollmentDetailSerializer},
        tags=["Course - Enrollments"],
    ),
    create=extend_schema(
        summary="Create enrollment",
        description="Create a new enrollment (staff only or via order completion).",
        responses={201: EnrollmentCreateSerializer},
        tags=["Course - Enrollments"],
    ),
    update=extend_schema(
        summary="Update enrollment",
        description="Update enrollment progress and status.",
        responses={200: EnrollmentUpdateSerializer},
        tags=["Course - Enrollments"],
    ),
    partial_update=extend_schema(
        summary="Partially update enrollment",
        responses={200: EnrollmentUpdateSerializer},
        tags=["Course - Enrollments"],
    ),
    destroy=extend_schema(exclude=True),
)
class EnrollmentViewSet(BaseAdminViewSet):
    """
    Enrollment CRUD with role-based access.
    - Staff: can see and manage all enrollments
    - Users: can view their own enrollments and update progress
    - Note: Enrollments are typically auto-created when orders are completed
    """

    queryset = Enrollment.objects.select_related("user", "course", "order").all()

    serializer_class = EnrollmentSerializer
    permission_classes = [IsStudent | IsStaff]  # Students and staff can access
    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "certificate_issued", "course"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "course__title",
    ]
    ordering_fields = ["created_at", "progress_percentage", "last_accessed"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """
        Custom permissions:
        - list, retrieve, my_enrollments, access_course: students can view their enrollments
        - create, destroy: staff only
        - update, complete: students can update their own progress
        - statistics: staff only
        """
        if self.action in [
            "list",
            "retrieve",
            "my_enrollments",
            "access_course",
            "complete",
        ]:
            return [permission() for permission in self.permission_classes]
        elif self.action in ["create", "destroy", "statistics"]:
            return [IsStaff()]
        elif self.action in ["update", "partial_update"]:
            return [permission() for permission in self.permission_classes]  # Students can update their own
        return super().get_permissions()

    def filter_public_queryset(self, queryset):
        """
        For enrollments, students see their own enrollments.
        Don't apply is_active filtering automatically - handled by user filtering.
        """
        # Students see their own enrollments - the base get_queryset handles the user filtering
        return queryset

    def get_queryset(self):
        """
        Filter queryset based on user role:
        - Staff: see all enrollments
        - Regular users: see only their own enrollments
        """
        queryset = super().get_queryset()

        # Staff can see everything
        if self.is_staff_user(self.request.user):
            return queryset

        # Regular users see only their own enrollments
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        if self.action in ["retrieve", "my_enrollments"]:
            return EnrollmentDetailSerializer
        elif self.action == "create":
            return EnrollmentCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return EnrollmentUpdateSerializer
        return EnrollmentSerializer

    def perform_update(self, serializer):
        """Check ownership before allowing update."""
        enrollment = self.get_object()

        # Students can only update their own enrollments
        if not self.is_staff_user(self.request.user) and enrollment.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You don't have permission to update this enrollment.")

        serializer.save()

    def perform_destroy(self, instance):
        """Staff only can destroy enrollments."""
        if not self.is_staff_user(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only staff can delete enrollments.")

        instance.delete()

    @extend_schema(
        summary="Get my enrollments",
        description="Get all enrollments for the current authenticated user. Use ?status=ongoing or ?status=completed to filter.",
        responses={200: EnrollmentSerializer},
        tags=["Course - Enrollments"],
    )
    @action(detail=False, methods=["get"], permission_classes=[IsStudent | IsStaff])
    def my_enrollments(self, request):
        """Get all enrollments for current user."""
        queryset = self.get_queryset().filter(user=request.user, is_active=True)

        # Filter by status (ongoing or completed)
        status_filter = request.query_params.get("status", None)
        if status_filter == "ongoing":
            # Ongoing means not 100% complete
            queryset = queryset.filter(progress_percentage__lt=100)
        elif status_filter == "completed":
            # Completed means 100% progress
            queryset = queryset.filter(progress_percentage=100)
        # If status_filter is 'all' or None, return all enrollments

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                True,
                "Your enrollments retrieved successfully",
                self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(True, "Your enrollments retrieved successfully", serializer.data)

    @extend_schema(
        summary="Access course",
        description="Update last accessed timestamp when user accesses a course.",
        responses={200: EnrollmentSerializer},
        tags=["Course - Enrollments"],
    )
    @action(detail=True, methods=["post"], permission_classes=[IsStudent | IsStaff])
    def access_course(self, request, pk=None):
        """Update last accessed timestamp."""
        enrollment = self.get_object()

        # Check if user owns this enrollment
        if enrollment.user != request.user and not self.is_staff_user(request.user):
            return api_response(
                False,
                "You don't have permission to access this enrollment",
                {},
                status.HTTP_403_FORBIDDEN,
            )

        enrollment.update_last_accessed()

        serializer = self.get_serializer(enrollment)
        return api_response(True, "Course accessed successfully", serializer.data)

    @extend_schema(
        summary="Complete enrollment",
        description="Mark enrollment as 100% complete.",
        responses={200: EnrollmentSerializer},
        tags=["Course - Enrollments"],
    )
    @action(detail=True, methods=["post"], permission_classes=[IsStudent | IsStaff])
    def complete(self, request, pk=None):
        """Mark enrollment as completed."""
        enrollment = self.get_object()

        # Check if user owns this enrollment
        if enrollment.user != request.user and not self.is_staff_user(request.user):
            return api_response(
                False,
                "You don't have permission to modify this enrollment",
                {},
                status.HTTP_403_FORBIDDEN,
            )

        if enrollment.is_completed():
            return api_response(
                False,
                "Enrollment is already completed",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        enrollment.mark_as_completed()

        serializer = self.get_serializer(enrollment)
        return api_response(True, "Enrollment completed successfully", serializer.data)

    @extend_schema(
        summary="Get enrollment statistics",
        description="Get enrollment statistics (staff only).",
        responses={200: dict},
        tags=["Course - Enrollments"],
    )
    @action(detail=False, methods=["get"], permission_classes=[IsStaff])
    def statistics(self, request):
        """Get enrollment statistics (staff only)."""
        from django.db.models import Avg, Count

        queryset = self.get_queryset()

        stats = {
            "total_enrollments": queryset.count(),
            "active_enrollments": queryset.filter(is_active=True).count(),
            "completed_enrollments": queryset.filter(progress_percentage=100).count(),
            "certificates_issued": queryset.filter(certificate_issued=True).count(),
            "average_progress": queryset.aggregate(avg=Avg("progress_percentage"))["avg"] or 0,
            "enrollments_by_course": queryset.values("course__title").annotate(count=Count("id")).order_by("-count")[:10],
        }

        return api_response(True, "Enrollment statistics retrieved successfully", stats)
