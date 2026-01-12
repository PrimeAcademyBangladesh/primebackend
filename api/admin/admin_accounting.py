from django.contrib import admin
from django.utils.html import format_html

from api.models.models_accounting import (
    IncomeType,
    PaymentMethod,
    Income,
    IncomeUpdateRequest,
)

# =====================================
# Income Type (MASTER DATA)
# =====================================
@admin.register(IncomeType)
class IncomeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "prefix", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


# =====================================
# Payment Method (MASTER DATA)
# =====================================
@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]


# =====================================
# Income (TRANSACTION)
# =====================================
@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "income_type",
        "amount",
        "date",
        "payer_name",
        "approval_status",
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

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        # Accountants cannot directly modify approved income
        if obj and obj.approval_status == "approved":
            return request.user.role in ["admin", "superadmin"]
        return True


# =====================================
# Income Update Request (APPROVAL WORKFLOW)
# =====================================
@admin.register(IncomeUpdateRequest)
class IncomeUpdateRequestAdmin(admin.ModelAdmin):
    list_display = (
        "income_link",
        "requested_by",
        "status",
        "created_at",
        "reviewed_by",
    )

    list_filter = ("status", "created_at")
    search_fields = ("income__transaction_id", "requested_by__email")

    readonly_fields = (
        "income",
        "requested_by",
        "requested_data",
        "created_at",
        "reviewed_by",
        "reviewed_at",
    )

    actions = ["approve_requests", "reject_requests"]

    def income_link(self, obj):
        return format_html(
            '<a href="/admin/api/income/{}/change/">{}</a>',
            obj.income.id,
            obj.income.transaction_id,
        )
    income_link.short_description = "Income"



    @admin.action(description="Approve selected update requests")
    def approve_requests(self, request, queryset):
        for req in queryset.filter(status="pending"):
            req.approve(request.user)

    @admin.action(description="Reject selected update requests")
    def reject_requests(self, request, queryset):
        for req in queryset.filter(status="pending"):
            req.reject(request.user, reason="Rejected from admin panel")

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]

    def has_change_permission(self, request, obj=None):
        return request.user.role in ["admin", "superadmin"]
