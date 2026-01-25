from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

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
# MASTER DATA
# ============================================================

@admin.register(IncomeType)
class IncomeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "prefix", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


@admin.register(ExpenseType)
class ExpenseTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


@admin.register(ExpensePaymentMethod)
class ExpensePaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


# ============================================================
# INCOME (TRANSACTION)
# ============================================================

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "income_type",
        "amount",
        "date",
        "payer_name",
        "approval_status_badge",
        "recorded_by",
    )

    list_filter = (
        "income_type",
        "payment_method",
        "approval_status",
        "date",
    )

    search_fields = (
        "transaction_id",
        "payer_name",
        "payer_email",
    )

    readonly_fields = (
        "transaction_id",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Transaction Info", {
            "fields": ("transaction_id", "income_type", "payment_method", "date")
        }),
        ("Payment Details", {
            "fields": ("amount", "payment_reference")
        }),
        ("Payer Information", {
            "fields": ("payer_name", "payer_email", "payer_phone")
        }),
        ("Approval", {
            "fields": ("approval_status", "approved_by", "approved_at")
        }),
        ("Meta", {
            "fields": ("recorded_by", "created_at", "updated_at")
        }),
    )

    def approval_status_badge(self, obj):
        color = {
            "pending": "orange",
            "approved": "green",
            "rejected": "red",
        }.get(obj.approval_status, "gray")

        return format_html(
            '<strong style="color:{}">{}</strong>',
            color,
            obj.approval_status.upper(),
        )

    approval_status_badge.short_description = "Approval Status"

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        if obj and obj.approval_status == "approved":
            return request.user.role in ["admin", "superadmin"]
        return True


# ============================================================
# INCOME UPDATE REQUEST (APPROVAL WORKFLOW)
# ============================================================

@admin.register(IncomeUpdateRequest)
class IncomeUpdateRequestAdmin(admin.ModelAdmin):
    list_display = (
        "income_link",
        "requested_by",
        "status_badge",
        "created_at",
        "reviewed_by",
    )

    list_filter = ("status", "created_at")
    search_fields = ("income__transaction_id", "requested_by__email")

    readonly_fields = (
        "income",
        "requested_by",
        "requested_data",
        "status",
        "reviewed_by",
        "reviewed_at",
        "rejection_reason",
        "created_at",
    )

    actions = ["approve_requests", "reject_requests"]

    def income_link(self, obj):
        url = reverse("admin:api_income_change", args=[obj.income.id])
        return format_html('<a href="{}">{}</a>', url, obj.income.transaction_id)

    income_link.short_description = "Income"

    def status_badge(self, obj):
        color = "orange" if obj.status == "pending" else "green"
        return format_html(
            '<strong style="color:{}">{}</strong>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    @admin.action(description="Approve selected update requests")
    def approve_requests(self, request, queryset):
        for req in queryset:
            if req.status == "pending":
                req.approve(request.user)

    @admin.action(description="Reject selected update requests")
    def reject_requests(self, request, queryset):
        for req in queryset:
            if req.status == "pending":
                req.reject(request.user, reason="Rejected from admin panel")

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


# ============================================================
# EXPENSE (TRANSACTION)
# ============================================================

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "reference_id",
        "expense_type",
        "amount",
        "date",
        "vendor_name",
        "status",
        "recorded_by",
    )

    list_filter = (
        "expense_type",
        "payment_method",
        "status",
        "date",
    )

    search_fields = (
        "reference_id",
        "vendor_name",
        "vendor_email",
        "description",
    )

    readonly_fields = (
        "reference_id",
        "recorded_by",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Expense Info", {
            "fields": (
                "reference_id",
                "expense_type",
                "payment_method",
                "date",
                "status",
            )
        }),
        ("Amount & Description", {
            "fields": ("amount", "description")
        }),
        ("Vendor Information", {
            "fields": ("vendor_name", "vendor_email")
        }),
        ("Meta", {
            "fields": ("recorded_by", "created_at", "updated_at")
        }),
    )

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        if obj and obj.update_requests.filter(status="pending").exists():
            return request.user.role in ["admin", "superadmin"]
        return True


# ============================================================
# EXPENSE UPDATE REQUEST (APPROVAL WORKFLOW)
# ============================================================

@admin.register(ExpenseUpdateRequest)
class ExpenseUpdateRequestAdmin(admin.ModelAdmin):
    list_display = (
        "expense_link",
        "requested_by",
        "status_badge",
        "created_at",
        "reviewed_by",
    )

    list_filter = ("status", "created_at")
    search_fields = ("expense__reference_id", "requested_by__email")

    readonly_fields = (
        "expense",
        "requested_by",
        "requested_data",
        "status",
        "reviewed_by",
        "reviewed_at",
        "rejection_reason",
        "created_at",
    )

    actions = ["approve_requests", "reject_requests"]

    def expense_link(self, obj):
        url = reverse("admin:api_expense_change", args=[obj.expense.id])
        return format_html('<a href="{}">{}</a>', url, obj.expense.reference_id)

    expense_link.short_description = "Expense"

    def status_badge(self, obj):
        color = "orange" if obj.status == "pending" else "green"
        return format_html(
            '<strong style="color:{}">{}</strong>',
            color,
            obj.status.upper(),
        )

    status_badge.short_description = "Status"

    @admin.action(description="Approve selected update requests")
    def approve_requests(self, request, queryset):
        for req in queryset:
            if req.status == "pending":
                req.approve(request.user)

    @admin.action(description="Reject selected update requests")
    def reject_requests(self, request, queryset):
        for req in queryset:
            if req.status == "pending":
                req.reject(request.user, reason="Rejected from admin panel")

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]
