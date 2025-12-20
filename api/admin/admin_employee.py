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
    # Use autocomplete to provide a searchable dropdown for UUID PKs
    autocomplete_fields = ("department",)

    # Read-only system fields
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "employee_image_preview",
        "resume_preview",
    )

    # --------------------------
    # Fieldsets (Grouped UI)
    # --------------------------
    fieldsets = (
        (
            "Basic Identity",
            {
                "fields": (
                    "employee_id",
                    ("first_name", "middle_name", "last_name"),
                    ("gender", "date_of_birth"),
                    "nationality",
                    ("qualification", "experience_years"),
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "email",
                    "phone_number",
                    "address",
                    "blood_group",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Employment Details",
            {
                "fields": (
                    "job_title",
                    "department",
                    "employment_type",
                    ("joining_date", "salary"),
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Compliance & Personal Records",
            {
                "fields": (
                    "nid_no",
                    "marital_status",
                    "resume",
                    "resume_preview",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Emergency Contact",
            {
                "fields": (
                    "spouse_name",
                    "spouse_contact_phone",
                    "emergency_contact_name",
                    "alternative_contact_phone",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Photo",
            {
                "fields": ("employee_image", "employee_image_preview"),
            },
        ),
        (
            "System Flags",
            {
                "fields": (
                    "is_active",
                    "is_enabled",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
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
                return mark_safe(
                    """
                    <img src="{obj.employee_image.url}"
                         style="width:40px;height:40px;object-fit:cover;
                                border-radius:4px;border:1px solid #ddd;" />
                """
                )
            except Exception:
                return "-"
        return "-"

    employee_image_tag.short_description = "Photo"

    def employee_image_preview(self, obj):
        """Large preview for detail page."""
        if obj.employee_image:
            try:
                return mark_safe(
                    """
                    <img src="{obj.employee_image.url}"
                         style="width:150px;height:150px;object-fit:cover;
                                border-radius:6px;border:1px solid #ccc;margin-top:5px;" />
                """
                )
            except Exception:
                return "-"
        return "-"

    employee_image_preview.short_description = "Image Preview"

    def resume_preview(self, obj):
        """Show a compact file icon + filename with a click-to-open/download link."""
        if not obj or not obj.resume:
            return "-"
        try:
            url = obj.resume.url
            filename = obj.resume.name.split("/")[-1]
            icon_svg = '<svg viewBox="-4 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><g id="SVGRepo_bgCarrier" stroke-width="0"></g><g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round"></g><g id="SVGRepo_iconCarrier"> <path d="M25.6686 26.0962C25.1812 26.2401 24.4656 26.2563 23.6984 26.145C22.875 26.0256 22.0351 25.7739 21.2096 25.403C22.6817 25.1888 23.8237 25.2548 24.8005 25.6009C25.0319 25.6829 25.412 25.9021 25.6686 26.0962ZM17.4552 24.7459C17.3953 24.7622 17.3363 24.7776 17.2776 24.7939C16.8815 24.9017 16.4961 25.0069 16.1247 25.1005L15.6239 25.2275C14.6165 25.4824 13.5865 25.7428 12.5692 26.0529C12.9558 25.1206 13.315 24.178 13.6667 23.2564C13.9271 22.5742 14.193 21.8773 14.468 21.1894C14.6075 21.4198 14.7531 21.6503 14.9046 21.8814C15.5948 22.9326 16.4624 23.9045 17.4552 24.7459ZM14.8927 14.2326C14.958 15.383 14.7098 16.4897 14.3457 17.5514C13.8972 16.2386 13.6882 14.7889 14.2489 13.6185C14.3927 13.3185 14.5105 13.1581 14.5869 13.0744C14.7049 13.2566 14.8601 13.6642 14.8927 14.2326ZM9.63347 28.8054C9.38148 29.2562 9.12426 29.6782 8.86063 30.0767C8.22442 31.0355 7.18393 32.0621 6.64941 32.0621C6.59681 32.0621 6.53316 32.0536 6.44015 31.9554C6.38028 31.8926 6.37069 31.8476 6.37359 31.7862C6.39161 31.4337 6.85867 30.8059 7.53527 30.2238C8.14939 29.6957 8.84352 29.2262 9.63347 28.8054ZM27.3706 26.1461C27.2889 24.9719 25.3123 24.2186 25.2928 24.2116C24.5287 23.9407 23.6986 23.8091 22.7552 23.8091C21.7453 23.8091 20.6565 23.9552 19.2582 24.2819C18.014 23.3999 16.9392 22.2957 16.1362 21.0733C15.7816 20.5332 15.4628 19.9941 15.1849 19.4675C15.8633 17.8454 16.4742 16.1013 16.3632 14.1479C16.2737 12.5816 15.5674 11.5295 14.6069 11.5295C13.948 11.5295 13.3807 12.0175 12.9194 12.9813C12.0965 14.6987 12.3128 16.8962 13.562 19.5184C13.1121 20.5751 12.6941 21.6706 12.2895 22.7311C11.7861 24.0498 11.2674 25.4103 10.6828 26.7045C9.04334 27.3532 7.69648 28.1399 6.57402 29.1057C5.8387 29.7373 4.95223 30.7028 4.90163 31.7107C4.87693 32.1854 5.03969 32.6207 5.37044 32.9695C5.72183 33.3398 6.16329 33.5348 6.6487 33.5354C8.25189 33.5354 9.79489 31.3327 10.0876 30.8909C10.6767 30.0029 11.2281 29.0124 11.7684 27.8699C13.1292 27.3781 14.5794 27.011 15.985 26.6562L16.4884 26.5283C16.8668 26.4321 17.2601 26.3257 17.6635 26.2153C18.0904 26.0999 18.5296 25.9802 18.976 25.8665C20.4193 26.7844 21.9714 27.3831 23.4851 27.6028C24.7601 27.7883 25.8924 27.6807 26.6589 27.2811C27.3486 26.9219 27.3866 26.3676 27.3706 26.1461ZM30.4755 36.2428C30.4755 38.3932 28.5802 38.5258 28.1978 38.5301H3.74486C1.60224 38.5301 1.47322 36.6218 1.46913 36.2428L1.46884 3.75642C1.46884 1.6039 3.36763 1.4734 3.74457 1.46908H20.263L20.2718 1.4778V7.92396C20.2718 9.21763 21.0539 11.6669 24.0158 11.6669H30.4203L30.4753 11.7218L30.4755 36.2428ZM28.9572 10.1976H24.0169C21.8749 10.1976 21.7453 8.29969 21.7424 7.92417V2.95307L28.9572 10.1976ZM31.9447 36.2428V11.1157L21.7424 0.871022V0.823357H21.6936L20.8742 0H3.74491C2.44954 0 0 0.785336 0 3.75711V36.2435C0 37.5427 0.782956 40 3.74491 40H28.2001C29.4952 39.9997 31.9447 39.2143 31.9447 36.2428Z" fill="#EB5757"></path> </g></svg>'
            return mark_safe(
                f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                f'style="display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:#111;">'
                f'{icon_svg}<span style="font-size:13px">{filename}</span></a>'
            )
        except Exception:
            return "-"

    resume_preview.short_description = "Resume Preview"
