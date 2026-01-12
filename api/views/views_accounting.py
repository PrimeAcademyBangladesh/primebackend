from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Prefetch, Exists, OuterRef

from api.models.models_accounting import Income, IncomeUpdateRequest
from api.permissions import IsAdmin, IsAdminOrAccountant
from api.serializers.serializers_accounting import (
    IncomeReadSerializer,
    IncomeListSerializer,
    IncomeCreateSerializer,
    IncomeUpdateRequestSerializer,
    IncomeUpdateRequestReadSerializer,
    IncomeApprovalActionSerializer,
)
from api.utils.pagination import StandardResultsSetPagination


# ============================================================
# Income ViewSet
# ============================================================
@extend_schema(tags=['ACCOUNTING'])
class IncomeViewSet(ModelViewSet):
    """
    Income management with approval workflow.
    - Accountants: create + request updates
    - Admins: full control
    """
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        "status": ["exact"],
        "approval_status": ["exact"],
        "income_type": ["exact"],
        "payment_method": ["exact"],
        "date": ["gte", "lte", "exact"],
        "amount": ["gte", "lte"],
    }

    search_fields = [
        "transaction_id",
        "payer_name",
        "payer_email",
        "description",
        "payment_reference",
    ]

    ordering_fields = ["date", "amount", "created_at", "transaction_id"]
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        queryset = Income.objects.select_related(
            "income_type",
            "payment_method",
            "recorded_by",
            "approved_by",
        )

        if self.action in ["retrieve", "update", "partial_update"]:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "update_requests",
                    queryset=IncomeUpdateRequest.objects.select_related(
                        "requested_by", "reviewed_by"
                    ).filter(status="pending"),
                )
            )

        if self.action in ["update", "partial_update"]:
            queryset = queryset.annotate(
                has_pending_request=Exists(
                    IncomeUpdateRequest.objects.filter(
                        income=OuterRef("pk"),
                        status="pending",
                    )
                )
            )

        return queryset

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsAdminOrAccountant()]

    def get_serializer_class(self):
        if self.action == "list":
            return IncomeListSerializer
        if self.action == "retrieve":
            return IncomeReadSerializer
        return IncomeCreateSerializer

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    def update(self, request, *args, **kwargs):
        income = self.get_object()
        partial = kwargs.pop("partial", False)

        serializer = self.get_serializer(
            income, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)

        if getattr(income, "has_pending_request", False):
            return Response(
                {
                    "detail": "An update request is already pending approval.",
                    "code": "pending_request_exists",
                },
                status=status.HTTP_409_CONFLICT,
            )

        if request.user.is_accountant and not (
            request.user.is_admin or request.user.is_superuser
        ):
            update_request = IncomeUpdateRequest.objects.create(
                income=income,
                requested_by=request.user,
                requested_data=serializer.validated_data,
            )

            return Response(
                {
                    "detail": "Update request submitted for admin approval.",
                    "request_id": update_request.id,
                    "code": "request_submitted",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        self.perform_update(serializer)

        if getattr(income, "_prefetched_objects_cache", None):
            income._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(summary="Get pending approvals")
    @action(detail=False, methods=["get"], url_path="pending-approval")
    def pending_approval(self, request):
        self.permission_classes = [IsAdmin]
        self.check_permissions(request)

        queryset = self.filter_queryset(
            self.get_queryset().filter(approval_status="pending")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ============================================================
# Income Update Request ViewSet (Admin Only)
# ============================================================
@extend_schema(tags=['ACCOUNTING'])
class IncomeUpdateRequestViewSet(ModelViewSet):
    """
    Admin-only approval of income update requests.
    """

    permission_classes = [IsAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]

    filterset_fields = ["status", "income"]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return IncomeUpdateRequest.objects.select_related(
            "income",
            "income__income_type",
            "income__payment_method",
            "requested_by",
            "reviewed_by",
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return IncomeUpdateRequestReadSerializer
        return IncomeUpdateRequestSerializer

    @extend_schema(
        summary="Approve update request",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        update_request = self.get_object()

        if update_request.status != "pending":
            return Response(
                {
                    "detail": f"This request has already been {update_request.status}.",
                    "code": "already_processed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_request.approve(request.user)

        return Response(
            {
                "detail": "Update request approved successfully.",
                "income_id": str(update_request.income.id),
                "transaction_id": update_request.income.transaction_id,
            }
        )

    @extend_schema(
        summary="Reject update request",
        request=IncomeApprovalActionSerializer,
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        update_request = self.get_object()

        if update_request.status != "pending":
            return Response(
                {
                    "detail": f"This request has already been {update_request.status}.",
                    "code": "already_processed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IncomeApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_request.reject(
            request.user,
            serializer.validated_data.get("reason", ""),
        )

        return Response(
            {
                "detail": "Update request rejected successfully.",
                "rejection_reason": serializer.validated_data.get("reason", ""),
            }
        )

    @extend_schema(summary="Get pending requests")
    @action(detail=False, methods=["get"], url_path="pending")
    def pending_requests(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(status="pending")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)