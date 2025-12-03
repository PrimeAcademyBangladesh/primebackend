from rest_framework import serializers

from api.models.models_employee import Department, Employee


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "is_active"]
        read_only_fields = ["id", "is_active"]


class EmployeeSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source="department", write_only=True
    )
    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "job_title",
            "department_id",
            "department",
            "employee_image",
            "phone_number",
            "email",
            "joining_date",
            "is_active",
        ]
        read_only_fields = ["id", "department"]
