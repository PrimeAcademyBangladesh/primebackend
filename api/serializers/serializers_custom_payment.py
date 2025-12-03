"""Serializers for CustomPayment and EventRegistration."""

from decimal import Decimal

from rest_framework import serializers

from api.models.models_custom_payment import CustomPayment, EventRegistration


class CustomPaymentSerializer(serializers.ModelSerializer):
    """Serializer for custom payment (admin enrolls student with custom amount)."""
    
    student_email = serializers.EmailField(source='student.email', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    enrollment_id = serializers.UUIDField(source='enrollment.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CustomPayment
        fields = [
            'id',
            'payment_number',
            'student',
            'student_email',
            'student_name',
            'course',
            'course_title',
            'created_by',
            'created_by_name',
            'title',
            'description',
            'amount',
            'original_price',
            'currency',
            'status',
            'payment_method',
            'payment_id',
            'enrollment',
            'enrollment_id',
            'completed_at',
            'cancelled_at',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'payment_number',
            'created_by',
            'enrollment',
            'completed_at',
            'cancelled_at',
            'created_at',
            'updated_at',
        ]
    
    def validate_amount(self, value):
        """Ensure amount is not negative."""
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Amount cannot be negative.")
        return value
    
    def validate(self, attrs):
        """Validate student and course."""
        student = attrs.get('student')
        course = attrs.get('course')
        
        # Check if student exists and is a student
        if student and not student.is_student:
            raise serializers.ValidationError({"student": "User must have student role."})
        
        # If course is provided, check if student is already enrolled
        if course:
            from api.models.models_order import Enrollment
            existing_enrollment = Enrollment.objects.filter(
                user=student,
                course=course,
                status__in=['active', 'completed']
            ).first()
            
            if existing_enrollment:
                raise serializers.ValidationError({
                    "course": f"Student is already enrolled in this course (Enrollment ID: {existing_enrollment.id})"
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create custom payment with admin as creator."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class EventRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for event registration."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = EventRegistration
        fields = [
            'id',
            'registration_number',
            'user',
            'user_email',
            'user_name',
            'created_by',
            'created_by_name',
            'event_type',
            'event_name',
            'event_date',
            'event_location',
            'event_description',
            'ticket_type',
            'number_of_tickets',
            'price_per_ticket',
            'total_amount',
            'currency',
            'status',
            'payment_method',
            'payment_id',
            'is_attended',
            'attended_at',
            'completed_at',
            'cancelled_at',
            'contact_name',
            'contact_email',
            'contact_phone',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'registration_number',
            'created_by',
            'total_amount',
            'is_attended',
            'attended_at',
            'completed_at',
            'cancelled_at',
            'created_at',
            'updated_at',
        ]
    
    def validate_price_per_ticket(self, value):
        """Ensure price is not negative."""
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Price per ticket cannot be negative.")
        return value
    
    def validate_number_of_tickets(self, value):
        """Ensure at least 1 ticket."""
        if value < 1:
            raise serializers.ValidationError("Must register for at least 1 ticket.")
        return value
    
    def create(self, validated_data):
        """Create event registration with creator tracking."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # If admin creates this, set created_by
            if request.user.role in ['staff', 'admin']:
                validated_data['created_by'] = request.user
            # If student creates this, set user to themselves
            if not validated_data.get('user'):
                validated_data['user'] = request.user
        return super().create(validated_data)
