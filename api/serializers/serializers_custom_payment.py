"""Serializers for CustomPayment."""

from decimal import Decimal

from rest_framework import serializers

from api.models.models_custom_payment import CustomPayment


class CustomPaymentSerializer(serializers.ModelSerializer):
    """Serializer for custom payment (admin enrolls student with custom amount)."""

    student_email = serializers.EmailField(source="student.email", read_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, allow_null=True)
    enrollment_id = serializers.UUIDField(source="enrollment.id", read_only=True, allow_null=True)

    class Meta:
        model = CustomPayment
        fields = [
            "id",
            "payment_number",
            "student",
            "student_email",
            "student_name",
            "course",
            "course_title",
            "created_by",
            "created_by_name",
            "title",
            "description",
            "amount",
            "original_price",
            "currency",
            "status",
            "payment_method",
            "payment_id",
            "enrollment",
            "enrollment_id",
            "completed_at",
            "cancelled_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "payment_number",
            "created_by",
            "enrollment",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        """Ensure amount is not negative."""
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Amount cannot be negative.")
        return value

    def validate(self, attrs):
        """Validate student and course."""
        student = attrs.get("student")
        course = attrs.get("course")

        # Check if student exists and is a student
        if student and not student.is_student:
            raise serializers.ValidationError({"student": "User must have student role."})

        # If course is provided, check if student is already enrolled
        if course:
            from api.models.models_order import Enrollment

            existing_enrollment = Enrollment.objects.filter(
                user=student, course=course, status__in=["active", "completed"]
            ).first()

            if existing_enrollment:
                raise serializers.ValidationError(
                    {"course": f"Student is already enrolled in this course (Enrollment ID: {existing_enrollment.id})"}
                )

        return attrs

    def create(self, validated_data):
        """Create custom payment with admin as creator."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["created_by"] = request.user
        return super().create(validated_data)
