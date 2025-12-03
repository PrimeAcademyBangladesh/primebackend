from django.contrib import admin

from api.models.models_employee import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    readonly_fields = ("is_active",)
    
    def has_module_permission(self, request):
        return False

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "employee_name",
        "job_title",
        "department",
        "employee_image",
        "phone_number",
        "email",
        "joining_date",
        "is_active",
    )
    search_fields = ("employee_name", "email", "employee_id")
    list_filter = ("department", "is_active")
    
