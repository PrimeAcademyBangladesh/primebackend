from rest_framework import serializers
from django.utils import timezone

from api.models.models_accounting import (
    IncomeType,
    PaymentMethod,
    Income,
    IncomeUpdateRequest, ExpenseType, ExpensePaymentMethod, Expense, ExpenseUpdateRequest
)


class IncomeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeType
        fields = "__all__"


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = "__all__"


class IncomeCreateSerializer(serializers.ModelSerializer):
    transaction_id = serializers.ReadOnlyField()

    class Meta:
        model = Income
        exclude = ["approved_by", "approved_at", "approval_status"]

    def validate_amount(self, value):
        """Ensure amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_date(self, value):
        """Ensure date is not in the future"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Income date cannot be in the future.")
        return value

    def validate(self, attrs):
        """
        Cross-field validation
        """
        # Ensure income_type and payment_method are active
        income_type = attrs.get('income_type')
        payment_method = attrs.get('payment_method')

        if income_type and not income_type.is_active:
            raise serializers.ValidationError({
                "income_type": "Selected income type is not active."
            })

        if payment_method and not payment_method.is_active:
            raise serializers.ValidationError({
                "payment_method": "Selected payment method is not active."
            })

        return attrs

    def validate_income_type(self, value):
        if not value:
            raise serializers.ValidationError("Income type is required.")
        return value

    def validate_payment_method(self, value):
        if not value:
            raise serializers.ValidationError("Payment method is required.")
        return value


class IncomeReadSerializer(serializers.ModelSerializer):
    """
    Serializer for reading Income records with nested relationships.
    Optimized to work with select_related() queryset.
    """
    # Nested relationship fields
    income_type_name = serializers.CharField(source="income_type.name", read_only=True)
    income_type_code = serializers.CharField(source="income_type.code", read_only=True)

    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)

    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True, default=None,
                                               allow_null=True, required=False)

    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, default=None)
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True, default=None,
                                               allow_null=True, required=False)

    # Computed fields
    has_pending_updates = serializers.SerializerMethodField()

    class Meta:
        model = Income
        fields = "__all__"

    def get_has_pending_updates(self, obj):
        """Check if there are pending update requests"""
        # This will use prefetch_related if available, otherwise single query
        return obj.update_requests.filter(status="pending").exists()


class IncomeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing incomes.
    Only includes essential fields for performance.
    """
    income_type_name = serializers.CharField(source="income_type.name", read_only=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Income
        fields = [
            'id', 'transaction_id', 'income_type_name', 'payment_method_name',
            'amount', 'date', 'payer_name', 'status', 'approval_status',
            'recorded_by_name', 'created_at'
        ]


class IncomeUpdateRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for income update requests.
    Includes validation to ensure only allowed fields are in requested_data.
    """
    income_transaction_id = serializers.CharField(source="income.transaction_id", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = IncomeUpdateRequest
        fields = "__all__"
        read_only_fields = [
            "status", "reviewed_by", "reviewed_at", "rejection_reason"
        ]

    def validate_requested_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("requested_data must be a dictionary.")

        invalid_fields = set(value.keys()) - IncomeUpdateRequest.ALLOWED_UPDATE_FIELDS
        if invalid_fields:
            raise serializers.ValidationError(
                f"The following fields cannot be updated: {', '.join(invalid_fields)}"
            )

        return value


class IncomeUpdateRequestReadSerializer(serializers.ModelSerializer):
    """
    Detailed read serializer for update requests with full context.
    """
    income = IncomeReadSerializer(read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)

    class Meta:
        model = IncomeUpdateRequest
        fields = "__all__"


class IncomeApprovalActionSerializer(serializers.Serializer):
    """Serializer for approval/rejection actions"""
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


# ============================================================
# Expense Type Serializer
# ============================================================
class ExpenseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseType
        fields = "__all__"


# ============================================================
# Expense Payment Method Serializer
# ============================================================
class ExpensePaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpensePaymentMethod
        fields = "__all__"


# ============================================================
# Expense Create / Update Serializer
# ============================================================
class ExpenseCreateSerializer(serializers.ModelSerializer):
    reference_id = serializers.ReadOnlyField()

    class Meta:
        model = Expense
        exclude = ["recorded_by"]

    # ----------------------------
    # Field Validations
    # ----------------------------
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Expense date cannot be in the future.")
        return value

    # ----------------------------
    # Cross-field Validation
    # ----------------------------
    def validate(self, attrs):
        expense_type = attrs.get("expense_type")
        payment_method = attrs.get("payment_method")

        if expense_type and not expense_type.is_active:
            raise serializers.ValidationError(
                {"expense_type": "Selected expense type is not active."}
            )

        if payment_method and not payment_method.is_active:
            raise serializers.ValidationError(
                {"payment_method": "Selected payment method is not active."}
            )

        return attrs


# ============================================================
# Expense Read Serializer (DETAIL VIEW)
# ============================================================
class ExpenseReadSerializer(serializers.ModelSerializer):
    expense_type_name = serializers.CharField(
        source="expense_type.name", read_only=True
    )
    expense_type_code = serializers.CharField(
        source="expense_type.code", read_only=True
    )

    payment_method_name = serializers.CharField(
        source="payment_method.name", read_only=True
    )
    payment_method_code = serializers.CharField(
        source="payment_method.code", read_only=True
    )

    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True, default=None
    )
    recorded_by_email = serializers.EmailField(
        source="recorded_by.email", read_only=True, default=None, allow_null=True, required=False
    )

    has_pending_updates = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = "__all__"

    def get_has_pending_updates(self, obj):
        return obj.update_requests.filter(status="pending").exists()


# ============================================================
# Expense List Serializer (LIGHTWEIGHT)
# ============================================================
class ExpenseListSerializer(serializers.ModelSerializer):
    expense_type_name = serializers.CharField(
        source="expense_type.name", read_only=True
    )
    payment_method_name = serializers.CharField(
        source="payment_method.name", read_only=True
    )
    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "reference_id",
            "expense_type_name",
            "payment_method_name",
            "amount",
            "date",
            "vendor_name",
            "status",
            "recorded_by_name",
            "created_at",
        ]


# ============================================================
# Expense Update Request Serializer (CREATE / LIST)
# ============================================================
class ExpenseUpdateRequestSerializer(serializers.ModelSerializer):
    expense_reference_id = serializers.CharField(
        source="expense.reference_id", read_only=True
    )
    requested_by_name = serializers.CharField(
        source="requested_by.get_full_name", read_only=True
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = ExpenseUpdateRequest
        fields = "__all__"
        read_only_fields = [
            "status",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        ]

    def validate_requested_data(self, value):
        """
        Validate requested update data.
        Ensures only allowed fields are included.
        Final validation occurs during approval.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("requested_data must be a dictionary.")

        invalid_fields = set(value.keys()) - ExpenseUpdateRequest.ALLOWED_UPDATE_FIELDS
        if invalid_fields:
            raise serializers.ValidationError(
                f"Invalid fields for update: {', '.join(invalid_fields)}"
            )

        return value


# ============================================================
# Expense Update Request Read Serializer (DETAIL)
# ============================================================
class ExpenseUpdateRequestReadSerializer(serializers.ModelSerializer):
    expense = ExpenseReadSerializer(read_only=True)

    requested_by_name = serializers.CharField(
        source="requested_by.get_full_name", read_only=True
    )
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True
    )

    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name", read_only=True, default=None
    )
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )

    class Meta:
        model = ExpenseUpdateRequest
        fields = "__all__"


# ============================================================
# Approval / Rejection Action Serializer
# ============================================================
class ExpenseApprovalActionSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
