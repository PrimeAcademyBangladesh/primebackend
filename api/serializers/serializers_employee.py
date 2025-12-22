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

    department_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), source="department", write_only=True)
    employee_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_name",
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
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate(self, attrs):
        # Support legacy `employee_name` by splitting into first and last name.
        name = self.initial_data.get("employee_name") if hasattr(self, "initial_data") else None
        if name and (not attrs.get("first_name") or not attrs.get("last_name")):
            parts = name.strip().split(None, 1)
            attrs.setdefault("first_name", parts[0] if parts else "")
            attrs.setdefault("last_name", parts[1] if len(parts) > 1 else "")
        return super().validate(attrs)

    def create(self, validated_data):
        # Remove write-only alias field before creating model instance
        validated_data.pop("employee_name", None)
        return super().create(validated_data)
