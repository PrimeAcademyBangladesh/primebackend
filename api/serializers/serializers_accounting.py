from rest_framework import serializers
from django.utils import timezone

from api.models.models_accounting import (
    IncomeType,
    PaymentMethod,
    Income,
    IncomeUpdateRequest,
    ExpenseType,
    ExpensePaymentMethod,
    Expense,
    ExpenseUpdateRequest,
)

# ============================================================
# BASE UPDATE REQUEST SERIALIZER (REUSABLE CORE)
# ============================================================

class BaseUpdateRequestSerializer(serializers.ModelSerializer):
    """
    Base serializer for update requests (Income / Expense).

    Subclasses MUST define:
    - Meta.model
    - ALLOWED_FIELDS (set of allowed field names)
    """

    ALLOWED_FIELDS = set()

    def validate_requested_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("requested_data must be a dictionary.")

        invalid_fields = set(value.keys()) - self.ALLOWED_FIELDS
        if invalid_fields:
            raise serializers.ValidationError(
                f"Invalid fields for update: {', '.join(sorted(invalid_fields))}"
            )

        return value

    def create(self, validated_data):
        request = self.context["request"]
        return self.Meta.model.objects.create(
            requested_by=request.user,
            status="pending",
            **validated_data,
        )


# ============================================================
# INCOME SERIALIZERS
# ============================================================

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
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Income date cannot be in the future.")
        return value

    def validate(self, attrs):
        income_type = attrs.get("income_type")
        payment_method = attrs.get("payment_method")

        if income_type and not income_type.is_active:
            raise serializers.ValidationError({"income_type": "Selected income type is not active."})

        if payment_method and not payment_method.is_active:
            raise serializers.ValidationError({"payment_method": "Selected payment method is not active."})

        return attrs


class IncomeReadSerializer(serializers.ModelSerializer):
    income_type_name = serializers.CharField(source="income_type.name", read_only=True)
    income_type_code = serializers.CharField(source="income_type.code", read_only=True)

    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)

    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True, allow_null=True)

    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, default=None)
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True, allow_null=True)

    has_pending_updates = serializers.SerializerMethodField()

    class Meta:
        model = Income
        fields = "__all__"

    def get_has_pending_updates(self, obj):
        return obj.update_requests.filter(status="pending").exists()


class IncomeListSerializer(serializers.ModelSerializer):
    income_type_name = serializers.CharField(source="income_type.name", read_only=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Income
        fields = [
            "id",
            "transaction_id",
            "income_type_name",
            "payment_method_name",
            "amount",
            "date",
            "payer_name",
            "status",
            "approval_status",
            "recorded_by_name",
            "created_at",
        ]


class IncomeUpdateRequestCreateSerializer(BaseUpdateRequestSerializer):
    ALLOWED_FIELDS = IncomeUpdateRequest.ALLOWED_UPDATE_FIELDS

    class Meta:
        model = IncomeUpdateRequest
        fields = ["income", "requested_data"]


class IncomeUpdateRequestReadSerializer(serializers.ModelSerializer):
    income = IncomeReadSerializer(read_only=True)

    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)

    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)

    class Meta:
        model = IncomeUpdateRequest
        fields = "__all__"


class IncomeApprovalActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


# ============================================================
# EXPENSE SERIALIZERS (IDENTICAL PATTERN, SAFE & CLEAN)
# ============================================================

class ExpenseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseType
        fields = "__all__"


class ExpensePaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpensePaymentMethod
        fields = "__all__"


class ExpenseCreateSerializer(serializers.ModelSerializer):
    reference_id = serializers.ReadOnlyField()

    class Meta:
        model = Expense
        exclude = ["recorded_by"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Expense date cannot be in the future.")
        return value

    def validate(self, attrs):
        expense_type = attrs.get("expense_type")
        payment_method = attrs.get("payment_method")

        if expense_type and not expense_type.is_active:
            raise serializers.ValidationError({"expense_type": "Selected expense type is not active."})

        if payment_method and not payment_method.is_active:
            raise serializers.ValidationError({"payment_method": "Selected payment method is not active."})

        return attrs


class ExpenseReadSerializer(serializers.ModelSerializer):
    expense_type_name = serializers.CharField(source="expense_type.name", read_only=True)
    expense_type_code = serializers.CharField(source="expense_type.code", read_only=True)

    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)

    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True, allow_null=True)

    has_pending_updates = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = "__all__"

    def get_has_pending_updates(self, obj):
        return obj.update_requests.filter(status="pending").exists()


class ExpenseListSerializer(serializers.ModelSerializer):
    expense_type_name = serializers.CharField(source="expense_type.name", read_only=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)

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


class ExpenseUpdateRequestCreateSerializer(BaseUpdateRequestSerializer):
    ALLOWED_FIELDS = ExpenseUpdateRequest.ALLOWED_UPDATE_FIELDS

    class Meta:
        model = ExpenseUpdateRequest
        fields = ["expense", "requested_data"]


class ExpenseUpdateRequestReadSerializer(serializers.ModelSerializer):
    expense = ExpenseReadSerializer(read_only=True)

    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)

    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)

    class Meta:
        model = ExpenseUpdateRequest
        fields = "__all__"


class ExpenseApprovalActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
