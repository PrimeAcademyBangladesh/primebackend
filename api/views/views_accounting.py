import calendar
from decimal import Decimal

from django.db.models import Prefetch, Exists, OuterRef
from django.db.models import Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from django.utils.timesince import timesince
from api.models import CustomUser
from api.models.models_accounting import Income, Expense
from api.models.models_accounting import IncomeUpdateRequest, ExpenseUpdateRequest, IncomeType, \
    PaymentMethod, ExpenseType, ExpensePaymentMethod
from api.permissions import IsAdmin, IsAccountant, IsAdminOrAccountant
from api.serializers.serializers_accounting import (
    IncomeReadSerializer,
    IncomeListSerializer,
    IncomeCreateSerializer,
    IncomeUpdateRequestCreateSerializer,
    IncomeUpdateRequestReadSerializer,
    IncomeApprovalActionSerializer, ExpenseListSerializer, ExpenseReadSerializer, ExpenseCreateSerializer,
    ExpenseUpdateRequestReadSerializer, ExpenseUpdateRequestCreateSerializer, ExpenseApprovalActionSerializer,
    IncomeTypeSerializer, PaymentMethodSerializer, ExpenseTypeSerializer, ExpensePaymentMethodSerializer
)
from api.utils.accounting_tranx_helper import resolve_date_range, export_transactions_pdf, export_transactions_csv
from api.utils.approval_utils import handle_update_with_approval
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response


# ============================================================
# Income Type ViewSet
# ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Read-only Income Types (Master Data). Used in dropdowns. Add by SuperAdmin only.",
)
class IncomeTypeViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Read-only Income Types (Master Data)

    - Used in dropdowns (Income Create / Update forms)
    - Only active income types are returned
    - No create / update / delete via API
    """

    queryset = IncomeType.objects.filter(is_active=True)
    serializer_class = IncomeTypeSerializer
    permission_classes = [IsAdminOrAccountant]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return api_response(
            success=True,
            message="Income types retrieved successfully",
            data=serializer.data,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_response(
            success=True,
            message="Income type retrieved successfully",
            data=serializer.data,
        )


# ============================================================
# Payment Method ViewSet
# ============================================================

@extend_schema(
    tags=["ACCOUNTING"],
    summary='Read-only Payment Methods (Master Data) Used in dropdowns. Add by SuperAdmin only.',
)
class PaymentMethodViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Read-only Payment Methods (Master Data)
    - Used in dropdowns (Payment Method Create / Update forms)
    - Only active Payment Method are returned
    - No create / update / delete via API
    """

    queryset = PaymentMethod.objects.filter(is_active=True)
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAdminOrAccountant]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return api_response(
            success=True,
            message="Payment methods retrieved successfully",
            data=serializer.data,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return api_response(
            success=True,
            message="Payment method retrieved successfully",
            data=serializer.data,
        )


@extend_schema(
    tags=["ACCOUNTING"],
    summary='Income management with approval workflow.',
)
class IncomeViewSet(ModelViewSet):
    """
    Income management with approval workflow.

    Accountant:
        • Create income
        • Request updates (admin approval required)

    Admin / SuperAdmin:
        • Approve or reject update requests
        • Update or delete income directly (if no pending request)

    Filters:
        • status, income_type, payment_method
        • date__gte, date__lte
        • amount__gte, amount__lte

    Search:
        • transaction_id, payer_name, payer_email, description

    Ordering:
        • date, amount, created_at
    """

    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        "status": ["exact"],
        "income_type": ["exact"],
        "payment_method": ["exact"],
        "date": ["gte", "lte"],
        "amount": ["gte", "lte"],
    }

    search_fields = [
        "transaction_id",
        "payer_name",
        "payer_email",
        "description",
    ]

    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date", "-created_at"]

    # --------------------------------------------------------
    # Permissions (CLEAN WAY)
    # --------------------------------------------------------
    def get_permissions(self):
        if self.action in ["destroy", "pending_approval"]:
            return [IsAdmin()]
        return [IsAdminOrAccountant()]

    # --------------------------------------------------------
    # Queryset
    # --------------------------------------------------------

    def get_queryset(self):
        queryset = Income.objects.select_related(
            "income_type",
            "payment_method",
            "recorded_by",
            "approved_by",
        ).annotate(
            has_pending_updates=Exists(
                IncomeUpdateRequest.objects.filter(
                    income=OuterRef("pk"),
                    status="pending",
                )
            )
        )

        # keep your existing conditional prefetch logic
        if self.action in ["retrieve", "update", "partial_update"]:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "update_requests",
                    queryset=IncomeUpdateRequest.objects.filter(status="pending"),
                )
            )

        return queryset

    # --------------------------------------------------------
    # Serializers
    # --------------------------------------------------------
    def get_serializer_class(self):
        if self.action == "list":
            return IncomeListSerializer

        if self.action == "retrieve":
            return IncomeReadSerializer

        if self.action in ["update", "partial_update"]:
            return IncomeCreateSerializer

        if self.action == "create":
            return IncomeCreateSerializer

        return IncomeReadSerializer

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    @extend_schema(summary="Accountant: Create income")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        income = serializer.save(recorded_by=request.user)

        return api_response(
            success=True,
            message="Income created successfully",
            data=IncomeReadSerializer(income).data,
            status_code=status.HTTP_201_CREATED,
        )

    # --------------------------------------------------------
    # UPDATE (Approval Workflow)
    # --------------------------------------------------------
    @extend_schema(
        summary="Accountant: Update request income only. Admin: direct update"
    )
    def update(self, request, *args, **kwargs):
        income = self.get_object()
        partial = kwargs.pop("partial", False)

        serializer = self.get_serializer(income, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # 🔒 No-op protection
        if not serializer.validated_data:
            return api_response(
                success=False,
                message="No changes detected",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 👇 Accountant vs Admin handled here
        if request.user.role == "accountant":
            return handle_update_with_approval(
                request=request,
                instance=income,
                serializer=serializer,
                update_request_model=IncomeUpdateRequest,
                success_message="Income updated successfully",
            )

        # 🛡 Admin → direct update + auto approval
        income = serializer.save(
            approval_status="approved",
            approved_by=request.user,
            approved_at=timezone.now(),
        )

        return api_response(
            success=True,
            message="Income updated successfully",
            data=IncomeReadSerializer(income).data,
        )

    @extend_schema(summary="Accountant: Partial update request income only. Admin: direct partial update.")
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # --------------------------------------------------------
    # DELETE (Admin Only)
    # --------------------------------------------------------
    @extend_schema(summary="Admin: Delete income")
    def destroy(self, request, *args, **kwargs):
        income = self.get_object()

        if getattr(income, "has_pending_updates", False):
            return api_response(
                success=False,
                message="Cannot delete record with pending update requests",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        transaction_id = income.transaction_id
        income.delete()

        return api_response(
            success=True,
            message="Income deleted successfully",
            data={"transaction_id": transaction_id},
        )

    # --------------------------------------------------------
    # ADMIN: Incomes with pending update requests
    # --------------------------------------------------------
    @extend_schema(summary="Admin: incomes with pending update requests")
    @action(detail=False, methods=["get"], url_path="pending-approval")
    def pending_approval(self, request):
        queryset = self.filter_queryset(
            self.get_queryset()
            .filter(update_requests__status="pending")
            .distinct()
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = IncomeListSerializer(page, many=True)
            return api_response(
                success=True,
                message="Pending approvals fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = IncomeListSerializer(queryset, many=True)
        return api_response(
            success=True,
            message="Pending approvals fetched successfully",
            data=serializer.data,
        )


# ============================================================
# Income Update Request ViewSet
# ============================================================
@extend_schema(tags=["ACCOUNTING"])
class IncomeUpdateRequestViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Approval workflow for income updates.

    Accountant:
        • View own update requests

    Admin / SuperAdmin:
        • View pending update requests
        • Approve or reject update requests

    Endpoints:
        • List and retrieve update requests
        • Admin: list pending requests
        • Accountant: list own requests
    """

    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status", "income"]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    # --------------------------------------------------------
    # Permissions (CLEAN & CENTRALIZED)
    # --------------------------------------------------------
    def get_permissions(self):
        if self.action in ["approve", "reject", "pending_requests"]:
            return [IsAdmin()]
        if self.action == "my_requests":
            return [IsAccountant()]
        return [IsAdminOrAccountant()]

    # --------------------------------------------------------
    # Queryset
    # --------------------------------------------------------
    def get_queryset(self):
        return IncomeUpdateRequest.objects.select_related(
            "income",
            "requested_by",
            "reviewed_by",
        )

    # --------------------------------------------------------
    # Serializers
    # --------------------------------------------------------
    def get_serializer_class(self):
        if self.action == "retrieve":
            return IncomeUpdateRequestReadSerializer

        if self.action in ["pending_requests", "my_requests", "list"]:
            return IncomeUpdateRequestReadSerializer

        return IncomeUpdateRequestCreateSerializer

    # --------------------------------------------------------
    # ADMIN: List pending requests
    # --------------------------------------------------------
    @extend_schema(summary="Admin: pending update requests")
    @action(detail=False, methods=["get"], url_path="pending")
    def pending_requests(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(status="pending")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                success=True,
                message="Pending update requests fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            success=True,
            message="Pending update requests fetched successfully",
            data=serializer.data,
        )

    # --------------------------------------------------------
    # ACCOUNTANT: My update requests
    # --------------------------------------------------------
    @extend_schema(summary="Accountant: my update requests")
    @action(detail=False, methods=["get"], url_path="my-requests")
    def my_requests(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(requested_by=request.user)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                success=True,
                message="Your update requests fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            success=True,
            message="Your update requests fetched successfully",
            data=serializer.data,
        )

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------
    @extend_schema(summary="Admin: approve update request")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        update_request = self.get_object()

        if update_request.status != "pending":
            return api_response(
                success=False,
                message=f"Request already {update_request.status}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IncomeApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_request.approve(request.user)

        return api_response(
            success=True,
            message="Update request approved successfully",
            data={
                "income_id": str(update_request.income.id),
                "transaction_id": update_request.income.transaction_id,
            },
        )

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------
    @extend_schema(
        summary="Admin: reject update request",
        request=IncomeApprovalActionSerializer,
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        update_request = self.get_object()

        if update_request.status != "pending":
            return api_response(
                success=False,
                message=f"Request already {update_request.status}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IncomeApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_request.reject(
            request.user,
            serializer.validated_data.get("reason", ""),
        )

        return api_response(
            success=True,
            message="Update request rejected successfully",
            data={"reason": serializer.validated_data.get("reason")},
        )


# ============================================================
# Expense Type ViewSet
# ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Read-only Expense Types (Master Data). Used in dropdowns. Add by SuperAdmin only.",
)
class ExpenseTypeViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Read-only Expense Types (Master Data)

    - Used in dropdowns (Expense Create / Update forms)
    - Only active income types are returned
    - No create / update / delete via API
    """

    queryset = ExpenseType.objects.filter(is_active=True)
    serializer_class = ExpenseTypeSerializer
    permission_classes = [IsAdminOrAccountant]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return api_response(
            success=True,
            message="Income types retrieved successfully",
            data=serializer.data,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_response(
            success=True,
            message="Income type retrieved successfully",
            data=serializer.data,
        )


# ============================================================
# Expense Payment Method ViewSet
# ============================================================

@extend_schema(
    tags=["ACCOUNTING"],
    summary='Read-only Expense Payment Methods (Master Data) Used in dropdowns. Add by SuperAdmin only.',
)
class ExpensePaymentMethodViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Read-only Payment Methods (Master Data)
    - Used in dropdowns (Expense Payment Method Create / Update forms)
    - Only active Payment Method are returned
    - No create / update / delete via API
    """

    queryset = ExpensePaymentMethod.objects.filter(is_active=True)
    serializer_class = ExpensePaymentMethodSerializer
    permission_classes = [IsAdminOrAccountant]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return api_response(
            success=True,
            message="Payment methods retrieved successfully",
            data=serializer.data,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return api_response(
            success=True,
            message="Payment method retrieved successfully",
            data=serializer.data,
        )


# ============================================================
# Expense ViewSet
# ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Expense management with accountant updates and admin approval"
)
class ExpenseViewSet(ModelViewSet):
    """
    Expense management with approval workflow.

    Roles:
    - Accountant:
        • Create expense records
        • Request updates (admin approval required)
    - Admin / SuperAdmin:
        • Approve or reject update requests
        • Directly update expenses when no pending request exists
        • Delete expenses

    Filters:
    - status
    - expense_type
    - payment_method
    - date (gte, lte, exact)
    - amount (gte, lte)

    Search:
    - reference_id
    - vendor_name
    - vendor_email
    - description
    """

    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = {
        "status": ["exact"],
        "expense_type": ["exact"],
        "payment_method": ["exact"],
        "date": ["gte", "lte", "exact"],
        "amount": ["gte", "lte"],
    }

    search_fields = [
        "reference_id",
        "vendor_name",
        "vendor_email",
        "description",
    ]

    ordering_fields = ["date", "amount", "created_at", "reference_id"]
    ordering = ["-date", "-created_at"]

    # --------------------------------------------------------
    # Queryset
    # --------------------------------------------------------
    def get_queryset(self):
        queryset = Expense.objects.select_related(
            "expense_type",
            "payment_method",
            "recorded_by",
        ).annotate(
            has_pending_updates=Exists(
                ExpenseUpdateRequest.objects.filter(
                    expense=OuterRef("pk"),
                    status="pending",
                )
            )
        )

        if self.action in ["retrieve", "update", "partial_update"]:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "update_requests",
                    queryset=ExpenseUpdateRequest.objects.filter(status="pending"),
                )
            )

        return queryset

    # --------------------------------------------------------
    # Permissions
    # --------------------------------------------------------
    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsAdminOrAccountant()]

    # --------------------------------------------------------
    # Serializers
    # --------------------------------------------------------
    def get_serializer_class(self):
        if self.action == "list":
            return ExpenseListSerializer
        if self.action == "retrieve":
            return ExpenseReadSerializer
        return ExpenseCreateSerializer

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                success=True,
                message="Expenses fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            success=True,
            message="Expenses fetched successfully",
            data=serializer.data,
        )

    # --------------------------------------------------------
    # RETRIEVE
    # --------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return api_response(
            success=True,
            message="Expense fetched successfully",
            data=serializer.data,
        )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = serializer.save(recorded_by=request.user)

        return api_response(
            success=True,
            message="Expense created successfully",
            data=ExpenseReadSerializer(expense).data,
            status_code=status.HTTP_201_CREATED,
        )

    # --------------------------------------------------------
    # UPDATE (Approval Workflow)
    # --------------------------------------------------------
    def update(self, request, *args, **kwargs):
        expense = self.get_object()
        partial = kwargs.pop("partial", False)

        serializer = self.get_serializer(expense, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if not serializer.validated_data:
            return api_response(
                success=False,
                message="No changes detected",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ SINGLE RETURN — SAME AS IncomeViewSet
        return handle_update_with_approval(
            request=request,
            instance=expense,
            serializer=serializer,
            update_request_model=ExpenseUpdateRequest,
            success_message="Expense updated successfully",
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        expense = self.get_object()

        if getattr(expense, "has_pending_updates", False):
            return api_response(
                success=False,
                message="Cannot delete record with pending update requests",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        ref = expense.reference_id
        self.perform_destroy(expense)

        return api_response(
            success=True,
            message="Expense deleted successfully",
            data={"reference_id": ref},
        )


# ============================================================
# Expense Update Request ViewSet (Admin Only)
# ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Admin: review, approve, or reject expense update requests"
)
class ExpenseUpdateRequestViewSet(ModelViewSet):
    """
    Approval workflow for expense update requests.

    Roles:
    - Accountant:
        • View own update requests
    - Admin / SuperAdmin:
        • View all update requests
        • Approve or reject pending requests

    Filters:
    - status
    - expense

    Ordering:
    - created_at
    - reviewed_at
    """

    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]

    filterset_fields = ["status", "expense"]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["approve", "reject"]:
            return [IsAdmin()]
        if self.action == "my_requests":
            return [IsAccountant()]
        return [IsAdminOrAccountant()]

    def get_queryset(self):
        qs = ExpenseUpdateRequest.objects.select_related(
            "expense",
            "expense__expense_type",
            "expense__payment_method",
            "requested_by",
            "reviewed_by",
        )

        if self.request.user.role == "accountant":
            qs = qs.filter(requested_by=self.request.user)

        return qs

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "my_requests"]:
            return ExpenseUpdateRequestReadSerializer
        return ExpenseUpdateRequestCreateSerializer

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                success=True,
                message="Expense update requests fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            success=True,
            message="Expense update requests fetched successfully",
            data=serializer.data,
        )

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------
    @extend_schema(summary="Admin: approve expense update request")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        req = self.get_object()

        if req.status != "pending":
            return api_response(
                success=False,
                message=f"This request has already been {req.status}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        req.approve(request.user)

        return api_response(
            success=True,
            message="Expense update approved successfully",
            data={"reference_id": req.expense.reference_id},
        )

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------
    @extend_schema(
        summary="Admin: reject expense update request",
        request=ExpenseApprovalActionSerializer
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = self.get_object()
        serializer = ExpenseApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if req.status != "pending":
            return api_response(
                success=False,
                message=f"This request has already been {req.status}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        reason = serializer.validated_data.get("reason", "")
        req.reject(request.user, reason)

        return api_response(
            success=True,
            message="Expense update rejected successfully",
            data={"rejection_reason": reason},
        )

    # --------------------------------------------------------
    # Accountant → View Own Requests
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="my-requests")
    def my_requests(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(requested_by=request.user)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                success=True,
                message="Your expense update requests fetched successfully",
                data=self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            success=True,
            message="Your expense update requests fetched successfully",
            data=serializer.data,
        )


# ============================================================
# Accounting Dashboard API View
# ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Accounting Dashboard Data",
    parameters=[
        OpenApiParameter(
            name="year",
            type=int,
            description="Year for which to fetch the dashboard data. Defaults to current year.",
            required=False,
        ),
    ],
)
class AccountingDashboardAPIView(APIView):
    permission_classes = [IsAdminOrAccountant]

    def get(self, request):
        year = int(request.query_params.get("year", timezone.now().year))

        return api_response(
            success=True,
            message="Accounting dashboard data fetched successfully",
            data={
                "summary": self.get_summary(year),
                "chart": self.get_revenue_vs_expense_chart(year),
                "recent_transactions": self.get_recent_transactions(),
                "quick_stats": self.get_quick_stats(year),
                "recent_activity": self.get_recent_activity(),
            },
        )

    def get_summary(self, year):
        revenue = (
                Income.objects.filter(
                    date__year=year,
                    status="completed",
                    approval_status="approved",
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
        )

        expenses = (
                Expense.objects.filter(
                    date__year=year,
                    status="paid",
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
        )

        net_income = revenue - expenses

        balance = (
                          Income.objects.filter(
                              status="completed",
                              approval_status="approved",
                          ).aggregate(total=Sum("amount"))["total"]
                          or Decimal("0.00")
                  ) - (
                          Expense.objects.filter(status="paid")
                          .aggregate(total=Sum("amount"))["total"]
                          or Decimal("0.00")
                  )

        return {
            "total_revenue": float(revenue),
            "total_expenses": float(expenses),
            "net_income": float(net_income),
            "balance": float(balance),
        }

    def get_revenue_vs_expense_chart(self, year):
        months = []

        for month in range(1, 13):
            revenue = (
                    Income.objects.filter(
                        date__year=year,
                        date__month=month,
                        status="completed",
                        approval_status="approved",
                    ).aggregate(total=Sum("amount"))["total"]
                    or Decimal("0.00")
            )

            expense = (
                    Expense.objects.filter(
                        date__year=year,
                        date__month=month,
                        status="paid",
                    ).aggregate(total=Sum("amount"))["total"]
                    or Decimal("0.00")
            )

            months.append({
                "month": calendar.month_abbr[month],
                "revenue": float(revenue),
                "expenses": float(expense),
            })

        return {
            "year": year,
            "data": months,
        }

    def get_recent_transactions(self):
        incomes = Income.objects.filter(
            status="completed",
            approval_status="approved",
        ).values(
            "transaction_id",
            "description",
            "amount",
            "date",
        )

        expenses = Expense.objects.filter(
            status="paid"
        ).values(
            "reference_id",
            "description",
            "amount",
            "date",
        )

        data = []

        for i in incomes:
            data.append({
                "id": i["transaction_id"],
                "type": "income",
                "description": i["description"],
                "amount": float(i["amount"]),
                "date": i["date"],
            })

        for e in expenses:
            data.append({
                "id": e["reference_id"],
                "type": "expense",
                "description": e["description"],
                "amount": float(e["amount"]),
                "date": e["date"],
            })

        data.sort(key=lambda x: x["date"], reverse=True)

        return data[:10]

    def get_quick_stats(self, year):
        active_students = CustomUser.objects.filter(
            role="student",
            is_active=True,
        ).count()

        active_teachers = CustomUser.objects.filter(
            role="teacher",
            is_active=True,
        ).count()

        avg_monthly_revenue = (
                Income.objects.filter(
                    date__year=year,
                    status="completed",
                    approval_status="approved",
                ).aggregate(avg=Sum("amount") / 12)["avg"]
                or Decimal("0.00")
        )

        pending_incomes = Income.objects.filter(
            approval_status="pending"
        ).count()

        pending_expenses = Expense.objects.filter(
            status="pending"
        ).count()

        return {
            "active_students": active_students,
            "active_teachers": active_teachers,
            "avg_monthly_revenue": float(avg_monthly_revenue),
            "pending_income_approvals": pending_incomes,
            "pending_expenses": pending_expenses,
        }

    def get_recent_activity(self):
        activities = []

        # -------------------------
        # Income created
        # -------------------------
        incomes = Income.objects.select_related(
            "recorded_by"
        ).order_by("-created_at")[:5]

        for inc in incomes:
            activities.append({
                "type": "income_created",
                "message": f"Income {inc.transaction_id} recorded",
                "time": f"{timesince(inc.created_at)} ago",
                "created_at": inc.created_at,
            })

        # -------------------------
        # Income update requests
        # -------------------------
        income_requests = IncomeUpdateRequest.objects.select_related(
            "income",
            "requested_by",
        ).order_by("-created_at")[:5]

        for req in income_requests:
            activities.append({
                "type": "income_update_request",
                "message": f"Update requested for {req.income.transaction_id}",
                "time": f"{timesince(req.created_at)} ago",
                "created_at": req.created_at,
            })

        # -------------------------
        # Expense update requests
        # -------------------------
        expense_requests = ExpenseUpdateRequest.objects.select_related(
            "expense",
            "requested_by",
        ).order_by("-created_at")[:5]

        for req in expense_requests:
            activities.append({
                "type": "expense_update_request",
                "message": f"Update requested for expense {req.expense.reference_id}",
                "time": f"{timesince(req.created_at)} ago",
                "created_at": req.created_at,
            })

        # -------------------------
        # Expense created
        # -------------------------
        expenses = Expense.objects.select_related(
            "recorded_by"
        ).order_by("-created_at")[:5]

        for exp in expenses:
            activities.append({
                "type": "expense_created",
                "message": f"Expense {exp.reference_id} recorded",
                "time": f"{timesince(exp.created_at)} ago",
                "created_at": exp.created_at,
            })

        # -------------------------
        # SORT & LIMIT
        # -------------------------
        activities.sort(key=lambda x: x["created_at"], reverse=True)

        return activities[:8]


# # ============================================================
# Transactions API View
# # ============================================================
@extend_schema(
    tags=["ACCOUNTING"],
    summary="Fetch all transactions (incomes and expenses) with filters, pagination, and export options",
    parameters=[
        OpenApiParameter(
            name="search",
            type=str,
            description="Search by transaction ID, description, payer/vendor name",
            required=False,
        ),
        OpenApiParameter(
            name="type",
            type=str,
            description="Filter by transaction type: income or expense",
            required=False,
            enum=["income", "expense"],
        ),
        OpenApiParameter(
            name="status",
            type=str,
            description="Filter by transaction status",
            required=False,
        ),
        OpenApiParameter(
            name="range",
            type=str,
            description="Predefined date range filter (e.g., this_month, last_month)",
            required=False,
        ),
        OpenApiParameter(
            name="date_from",
            type=str,
            description="Start date for custom date range filter (YYYY-MM-DD)",
            required=False,
        ),
        OpenApiParameter(
            name="date_to",
            type=str,
            description="End date for custom date range filter (YYYY-MM-DD)",
            required=False,
        ),
        OpenApiParameter(
            name="export",
            type=str,
            description="Export format: csv or pdf",
            required=False,
            enum=["csv", "pdf"],
        ),
        OpenApiParameter(
            name="page",
            type=int,
            description="Page number for pagination",
            required=False,
        ),
        OpenApiParameter(
            name="page_size",
            type=int,
            description="Number of records per page for pagination",
            required=False,
        ),
    ],
)
class TransactionsAPIView(APIView):
    permission_classes = [IsAdminOrAccountant]

    def get(self, request):
        search = request.query_params.get("search")
        tx_type = request.query_params.get("type")
        status = request.query_params.get("status")
        range_key = request.query_params.get("range")
        export = request.query_params.get("export")

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        start, end = resolve_date_range(range_key)

        incomes = Income.objects.select_related(
            "income_type"
        )

        expenses = Expense.objects.select_related(
            "expense_type"
        )

        # --------------------
        # Filters
        # --------------------
        if status:
            incomes = incomes.filter(status=status)
            expenses = expenses.filter(status=status)

        if start and end:
            incomes = incomes.filter(date__range=(start, end))
            expenses = expenses.filter(date__range=(start, end))

        if date_from and date_to:
            incomes = incomes.filter(date__range=(date_from, date_to))
            expenses = expenses.filter(date__range=(date_from, date_to))

        if search:
            incomes = incomes.filter(
                Q(transaction_id__icontains=search) |
                Q(description__icontains=search) |
                Q(payer_name__icontains=search)
            )
            expenses = expenses.filter(
                Q(reference_id__icontains=search) |
                Q(description__icontains=search) |
                Q(vendor_name__icontains=search)
            )

        rows = []

        if tx_type in (None, "income"):
            for i in incomes:
                rows.append({
                    "id": i.transaction_id,
                    "description": i.description,
                    "category": i.income_type.name,
                    "reference": i.payer_name,
                    "date": i.date,
                    "type": "Income",
                    "status": i.status,
                    "amount": float(i.amount),
                })

        if tx_type in (None, "expense"):
            for e in expenses:
                rows.append({
                    "id": e.reference_id,
                    "description": e.description,
                    "category": e.expense_type.name,
                    "reference": e.vendor_name,
                    "date": e.date,
                    "type": "Expense",
                    "status": e.status,
                    "amount": -float(e.amount),
                })

        rows.sort(key=lambda x: x["date"], reverse=True)

        # --------------------
        # EXPORTS
        # --------------------
        if export == "csv":
            return export_transactions_csv(rows)

        if export == "pdf":
            return export_transactions_pdf(rows)

        # --------------------
        # PAGINATION
        # --------------------
        page = int(request.query_params.get("page", 1))
        size = int(request.query_params.get("page_size", 20))

        start_idx = (page - 1) * size
        end_idx = start_idx + size

        return api_response(
            success=True,
            message="Transactions fetched successfully",
            data={
                "count": len(rows),
                "page": page,
                "page_size": size,
                "results": rows[start_idx:end_idx],
            },
        )
