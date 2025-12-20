from rest_framework import serializers

from api.models.models_employee import Department, Employee


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "is_active"]
        read_only_fields = ["id", "is_active"]


class EmployeeSerializer(serializers.ModelSerializer):
    # Nested read-only department details
    department = DepartmentSerializer(read_only=True)

    # Write-only FK for department assignment
    department_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), source="department", write_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "nationality",
            "qualification",
            "experience_years",
            "blood_group",
            "marital_status",
            "email",
            "phone_number",
            "address",
            "job_title",
            "employment_type",
            "department_id",
            "department",
            "joining_date",
            "salary",
            "nid_no",
            "spouse_name",
            "spouse_contact_phone",
            "emergency_contact_name",
            "alternative_contact_phone",
            "employee_image",
            "resume",
            "is_active",
            "is_enabled",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "department",
            "created_at",
            "updated_at",
        ]
