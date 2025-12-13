from django.contrib import admin
from django.utils.html import mark_safe

from api.models.models_employee import Department, Employee


# ------------------------------------------------------------
# Department Admin
# ------------------------------------------------------------
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    readonly_fields = ("id",)

    def has_module_permission(self, request):
        return True


# ------------------------------------------------------------
# Employee Admin
# ------------------------------------------------------------
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Professional admin configuration for the Employee model."""

    # What shows in list view
    list_display = (
        "employee_image_tag",
        "employee_id",
        "full_name",
        "job_title",
        "department",
        "employment_type",
        "phone_number",
        "email",
        "joining_date",
        "is_active",
    )

    # Searchable fields
    search_fields = (
        "employee_id",
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "phone_number",
        "nid_no",
    )

    # Filters on right side
    list_filter = (
        "department",
        "employment_type",
        "marital_status",
        "is_active",
        "is_enabled",
    )

    # Optimization
    list_select_related = ("department",)
    raw_id_fields = ("department",)

    # Read-only system fields
    readonly_fields = ("id", "created_at", "updated_at", "employee_image_preview")

    # --------------------------
    # Fieldsets (Grouped UI)
    # --------------------------
    fieldsets = (
        ("Basic Identity", {
            "fields": (
                "employee_id",
                ("first_name", "middle_name", "last_name"),
                ("gender", "date_of_birth"),
                "nationality",
                ("qualification", "experience_years"),
            ),
            "classes": ("wide",),
        }),

        ("Contact Information", {
            "fields": (
                "email",
                "phone_number",
                "address",
                "blood_group",
            ),
            "classes": ("wide",),
        }),

        ("Employment Details", {
            "fields": (
                "job_title",
                "department",
                "employment_type",
                ("joining_date", "salary"),
            ),
            "classes": ("wide",),
        }),

        ("Compliance & Personal Records", {
            "fields": (
                "nid_no",
                "marital_status",
                "resume",
            ),
            "classes": ("wide",),
        }),

        ("Emergency Contact", {
            "fields": (
                "spouse_name",
                "spouse_contact_phone",
                "emergency_contact_name",
                "alternative_contact_phone",
            ),
            "classes": ("wide",),
        }),

        ("Photo", {
            "fields": ("employee_image", "employee_image_preview"),
        }),

        ("System Flags", {
            "fields": (
                "is_active",
                "is_enabled",
                "created_at",
                "updated_at",
            ),
        }),
    )

    # ------------------------------------------------------------
    # Custom display helpers
    # ------------------------------------------------------------

    def full_name(self, obj):
        """Display full name dynamically."""
        return " ".join(filter(None, [obj.first_name, obj.middle_name, obj.last_name]))
    full_name.short_description = "Full Name"

    def employee_image_tag(self, obj):
        """Thumbnail for list view."""
        if obj.employee_image:
            try:
                return mark_safe(f"""
                    <img src="{obj.employee_image.url}" 
                         style="width:40px;height:40px;object-fit:cover;
                                border-radius:4px;border:1px solid #ddd;" />
                """)
            except Exception:
                return "-"
        return "-"
    employee_image_tag.short_description = "Photo"

    def employee_image_preview(self, obj):
        """Large preview for detail page."""
        if obj.employee_image:
            try:
                return mark_safe(f"""
                    <img src="{obj.employee_image.url}" 
                         style="width:150px;height:150px;object-fit:cover;
                                border-radius:6px;border:1px solid #ccc;margin-top:5px;" />
                """)
            except Exception:
                return "-"
        return "-"
    employee_image_preview.short_description = "Image Preview"

