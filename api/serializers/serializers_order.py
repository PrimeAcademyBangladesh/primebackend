"""Serializers for Order, OrderItem, and Enrollment models."""

from decimal import Decimal

from django.utils import timezone

from rest_framework import serializers

from api.models.models_course import Course
from api.models.models_order import Enrollment, Order, OrderInstallment, OrderItem
from api.models.models_pricing import Coupon

# ========== OrderInstallment Serializers ==========


class OrderInstallmentSerializer(serializers.ModelSerializer):
    """Serializer for order installments."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    can_accept_payment = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()

    class Meta:
        model = OrderInstallment
        fields = [
            "id",
            "order",
            "installment_number",
            "amount",
            "due_date",
            "status",
            "status_display",
            "paid_at",
            "payment_id",
            "payment_method",
            # Helper fields (new)
            "is_overdue",
            "remaining_amount",
            "days_until_due",
            "can_accept_payment",
            "is_paid",
            "notes",
            "extra_data",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status_display",
            "is_overdue",
            "remaining_amount",
            "days_until_due",
            "can_accept_payment",
            "is_paid",
            "created_at",
        ]

    def get_is_overdue(self, obj):
        return obj.is_overdue_now()

    def get_remaining_amount(self, obj):
        return obj.remaining_amount()

    def get_days_until_due(self, obj):
        return obj.days_until_due()

    def get_can_accept_payment(self, obj):
        return obj.can_accept_payment()

    def get_is_paid(self, obj):
        return obj.is_paid()

    # ========= Safe extra_data update ==========
    def update(self, instance, validated_data):
        extra_data = validated_data.pop("extra_data", None)
        instance = super().update(instance, validated_data)

        if extra_data:
            instance.update_extra_data(extra_data)

        return instance


class OrderInstallmentPaymentSerializer(serializers.Serializer):
    """Serializer for marking installment as paid."""

    payment_id = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.CharField(required=False, allow_blank=True)


# ========== OrderItem Serializers ==========


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""

    course_title = serializers.CharField(read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)
    batch_info = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "course",
            "batch",
            "batch_info",
            "course_title",
            "course_slug",
            "price",
            "discount",
            "currency",
            "total",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "batch_info",
            "course_title",
            "course_slug",
            "total",
            "created_at",
        ]

    def get_batch_info(self, obj):
        """Get batch information if available."""
        if obj.batch:
            return {
                "id": str(obj.batch.id),
                "batch_number": obj.batch.batch_number,
                "batch_name": obj.batch.batch_name,
                "display_name": obj.batch.get_display_name(),
            }
        return None

    def get_total(self, obj):
        """Calculate total for this item."""
        return obj.get_total()


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating order items."""

    class Meta:
        model = OrderItem
        fields = ["course", "batch", "price", "discount", "currency"]

    def validate(self, attrs):
        """Validate order item data."""
        course = attrs.get("course")

        # Check if course exists and is active
        if not course.is_active:
            raise serializers.ValidationError("This course is not available for purchase.")

        if course.status != "published":
            raise serializers.ValidationError("This course is not yet published.")

        # Validate price matches course pricing
        if hasattr(course, "pricing"):
            expected_price = course.pricing.get_discounted_price()
            provided_price = attrs.get("price")

            if abs(expected_price - provided_price) > Decimal("0.01"):
                raise serializers.ValidationError(f"Price mismatch. Expected {expected_price}, got {provided_price}")

        return attrs


# ========== Order Serializers ==========


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for listing orders."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "user_email",
            "user_name",
            "status",
            "status_display",
            "total_amount",
            "currency",
            "payment_method",
            "payment_method_display",
            "items_count",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "user_email",
            "user_name",
            "status_display",
            "payment_method_display",
            "items_count",
            "created_at",
            "completed_at",
        ]

    def get_items_count(self, obj):
        """Get total number of items."""
        return obj.get_total_items()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for orders with all items."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    coupon_code_display = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    # Installment fields
    installment_amount = serializers.SerializerMethodField()
    remaining_installments = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    is_fully_paid = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "user",
            "user_email",
            "user_name",
            "status",
            "status_display",
            "subtotal",
            "discount_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "coupon",
            "coupon_code",
            "coupon_code_display",
            "payment_method",
            "payment_method_display",
            "payment_id",
            "payment_status",
            "billing_name",
            "billing_email",
            "billing_phone",
            "billing_address",
            "is_installment",
            "installment_plan",
            "installments_paid",
            "next_installment_date",
            "installment_amount",
            "remaining_installments",
            "paid_amount",
            "remaining_amount",
            "is_fully_paid",
            "is_custom_payment",
            "custom_payment_description",
            "items",
            "can_cancel",
            "created_at",
            "updated_at",
            "completed_at",
            "cancelled_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "user_email",
            "user_name",
            "status_display",
            "payment_method_display",
            "coupon_code_display",
            "installments_paid",
            "installment_amount",
            "remaining_installments",
            "paid_amount",
            "remaining_amount",
            "is_fully_paid",
            "can_cancel",
            "created_at",
            "updated_at",
            "completed_at",
            "cancelled_at",
        ]

    def get_coupon_code_display(self, obj):
        """Display coupon code."""
        return obj.coupon_code if obj.coupon_code else (obj.coupon.code if obj.coupon else None)

    def get_can_cancel(self, obj):
        """Check if order can be cancelled."""
        return obj.can_be_cancelled()

    def get_installment_amount(self, obj):
        """Get amount per installment."""
        return obj.get_installment_amount()

    def get_remaining_installments(self, obj):
        """Get number of remaining installments."""
        return obj.get_remaining_installments()

    def get_paid_amount(self, obj):
        """Get total amount paid."""
        return obj.get_paid_amount()

    def get_remaining_amount(self, obj):
        """Get remaining amount to be paid."""
        return obj.get_remaining_amount()

    def get_is_fully_paid(self, obj):
        """Check if order is fully paid."""
        return obj.is_fully_paid()


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders."""

    items = OrderItemCreateSerializer(many=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True, required=False)  # Auto-set in view

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "subtotal",
            "discount_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "coupon",
            "billing_name",
            "billing_email",
            "billing_phone",
            "billing_address",
            "billing_city",
            "billing_country",
            "billing_postcode",
            "is_installment",
            "installment_plan",
            "is_custom_payment",
            "custom_payment_description",
            "items",
        ]
        extra_kwargs = {
            "user": {"required": False},
        }

    def validate(self, attrs):
        """Validate order data."""
        items = attrs.get("items", [])
        is_custom_payment = attrs.get("is_custom_payment", False)

        # Custom payment validation
        if is_custom_payment:
            # For custom payments, description is required
            if not attrs.get("custom_payment_description"):
                raise serializers.ValidationError(
                    {"custom_payment_description": "Description is required for custom payments."}
                )

            # Custom payments can have:
            # 1. No items (pure custom payment like workshop fee)
            # 2. Course items with custom pricing (manual enrollment with discount/scholarship)
            if not items:
                # Pure custom payment without enrollment
                attrs["items"] = []
            else:
                # Custom payment WITH course enrollment
                # Validate that courses exist and are active
                for item in items:
                    course = item.get("course")
                    if course and not course.is_active:
                        raise serializers.ValidationError({"items": f"Course '{course.title}' is not active."})

                # For custom payments with items, allow flexible pricing
                # Admin can set any price (scholarship, discount, free enrollment, etc.)
                # Subtotal should match sum of item prices
                if items:
                    calculated_subtotal = sum(item.get("price", 0) for item in items)
                    provided_subtotal = attrs.get("subtotal", 0)

                    if abs(calculated_subtotal - provided_subtotal) > Decimal("0.01"):
                        raise serializers.ValidationError(
                            f"Subtotal mismatch. Calculated {calculated_subtotal}, provided {provided_subtotal}"
                        )

            # Skip regular coupon validation for custom payments
            # Total calculation for custom payments
            expected_total = attrs.get("subtotal", 0) - attrs.get("discount_amount", 0) + attrs.get("tax_amount", 0)
            provided_total = attrs.get("total_amount")

            if abs(expected_total - provided_total) > Decimal("0.01"):
                raise serializers.ValidationError(f"Total mismatch. Calculated {expected_total}, provided {provided_total}")

            return attrs

        # Regular course order validation
        if not items:
            raise serializers.ValidationError("Order must have at least one item.")

        # Validate subtotal calculation for regular orders
        calculated_subtotal = sum(item["price"] for item in items)
        provided_subtotal = attrs.get("subtotal")

        if abs(calculated_subtotal - provided_subtotal) > Decimal("0.01"):
            raise serializers.ValidationError(
                f"Subtotal mismatch. Calculated {calculated_subtotal}, provided {provided_subtotal}"
            )

        # Validate total calculation
        expected_total = attrs.get("subtotal", 0) - attrs.get("discount_amount", 0) + attrs.get("tax_amount", 0)
        provided_total = attrs.get("total_amount")

        if abs(expected_total - provided_total) > Decimal("0.01"):
            raise serializers.ValidationError(f"Total mismatch. Calculated {expected_total}, provided {provided_total}")

        # Validate coupon if provided
        coupon = attrs.get("coupon")
        if coupon:
            is_valid, message = coupon.is_valid()
            if not is_valid:
                raise serializers.ValidationError(f"Coupon error: {message}")

            # Check if coupon applies to all courses in order
            for item in items:
                course = item["course"]
                if not coupon.can_apply_to_course(course):
                    raise serializers.ValidationError(f"Coupon '{coupon.code}' cannot be applied to course '{course.title}'")

        # Validate installment settings
        is_installment = attrs.get("is_installment", False)
        installment_plan = attrs.get("installment_plan")

        if is_installment:
            if not installment_plan or installment_plan < 2:
                raise serializers.ValidationError({"installment_plan": "Installment plan must be at least 2 installments."})

            # Validate minimum amount per installment
            installment_amount = attrs.get("total_amount") / installment_plan
            if installment_amount < Decimal("500.00"):  # Minimum 500 BDT per installment
                raise serializers.ValidationError(
                    {"installment_plan": f"Each installment must be at least 500 BDT. Current: {installment_amount:.2f} BDT"}
                )

        return attrs

    def create(self, validated_data):
        """Create order with items."""
        items_data = validated_data.pop("items")
        coupon = validated_data.get("coupon")

        # Capture coupon code
        if coupon:
            validated_data["coupon_code"] = coupon.code

        # Create order
        order = Order.objects.create(**validated_data)

        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        # If installment plan selected, create OrderInstallment records
        if order.is_installment and order.installment_plan and order.installment_plan > 1:
            from datetime import timedelta

            total = order.total_amount
            plan = int(order.installment_plan)

            base_amount = (total / plan).quantize(Decimal("0.01"))
            amounts = [base_amount for _ in range(plan)]
            if sum(amounts) != total:
                amounts[-1] = (total - sum(amounts[:-1])).quantize(Decimal("0.01"))

            now = timezone.now()
            first_due = now + timedelta(days=30)

            for idx in range(plan):
                due_date = first_due + timedelta(days=30 * idx)
                OrderInstallment.objects.create(
                    order=order,
                    installment_number=idx + 1,
                    amount=amounts[idx],
                    due_date=due_date,
                )

            # ✅ FIX: DO NOT set next_installment_date yet
            order.installments_paid = 0
            order.next_installment_date = None
            order.save(update_fields=["installments_paid", "next_installment_date"])

        # Increment coupon usage if applicable
        if coupon:
            coupon.increment_usage()

        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating order status and payment info."""

    class Meta:
        model = Order
        fields = [
            "status",
            "payment_method",
            "payment_id",
            "payment_status",
            "notes",
        ]

    def validate_status(self, value):
        """Validate status transitions."""
        if self.instance:
            current_status = self.instance.status

            # Don't allow changing from completed
            if current_status == "completed" and value != "completed":
                raise serializers.ValidationError("Cannot change status of a completed order.")

            # Don't allow changing from refunded
            if current_status == "refunded" and value != "refunded":
                raise serializers.ValidationError("Cannot change status of a refunded order.")

        return value


# ========== Enrollment Serializers ==========


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollments."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    progress_display = serializers.SerializerMethodField()
    is_completed_status = serializers.SerializerMethodField()
    days_enrolled = serializers.SerializerMethodField()
    batch_info = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "course",
            "course_title",
            "course_slug",
            "batch",
            "batch_info",
            "order",
            "order_number",
            "progress_percentage",
            "progress_display",
            "is_active",
            "is_completed_status",
            "certificate_issued",
            "last_accessed",
            "completed_at",
            "created_at",
            "days_enrolled",
        ]
        read_only_fields = [
            "id",
            "user_email",
            "user_name",
            "course_title",
            "course_slug",
            "batch_info",
            "order_number",
            "progress_display",
            "is_completed_status",
            "created_at",
            "days_enrolled",
        ]

    def get_progress_display(self, obj):
        """Format progress percentage."""
        return f"{float(obj.progress_percentage):.1f}%"

    def get_is_completed_status(self, obj):
        """Check if enrollment is completed."""
        return obj.is_completed()

    def get_days_enrolled(self, obj):
        """Calculate days since enrollment."""
        delta = timezone.now() - obj.created_at
        return delta.days

    def get_batch_info(self, obj):
        """Get batch information for this enrollment."""
        if obj.batch:
            return {
                "id": str(obj.batch.id),
                "batch_number": obj.batch.batch_number,
                "batch_name": obj.batch.batch_name,
                "display_name": obj.batch.get_display_name(),
                "slug": obj.batch.slug,
                "start_date": obj.batch.start_date,
                "end_date": obj.batch.end_date,
            }
        return None


class EnrollmentDetailSerializer(EnrollmentSerializer):
    """Detailed enrollment serializer with course info."""

    course_info = serializers.SerializerMethodField()
    course_status = serializers.SerializerMethodField()
    module_count = serializers.SerializerMethodField()

    class Meta(EnrollmentSerializer.Meta):
        fields = EnrollmentSerializer.Meta.fields + [
            "course_info",
            "course_status",
            "module_count",
        ]

    def get_course_info(self, obj):
        """Get basic course information."""
        request = self.context.get("request")

        if obj.course.header_image:
            # Use actual course image from media
            header_image_url = obj.course.header_image.url
        else:
            # Use default placeholder image from static files
            from django.conf import settings
            from django.templatetags.static import static

            header_image_url = static("default_images/default_course.webp")

        # Build absolute URI
        if request:
            header_image = request.build_absolute_uri(header_image_url)
        else:
            header_image = header_image_url

        batch_info = None
        if obj.batch:
            batch_info = {
                "id": str(obj.batch.id),
                "batch_number": obj.batch.batch_number,
                "batch_name": obj.batch.batch_name,
                "slug": obj.batch.slug,
            }

        return {
            "title": obj.course.title,
            "slug": obj.course.slug,
            "short_description": obj.course.short_description,
            "header_image": header_image,
            "batch": batch_info,
        }

    def get_course_status(self, obj):
        """Get course status: 'ongoing' or 'completed'."""
        if obj.is_completed():
            return "completed"
        return "ongoing"

    def get_module_count(self, obj):
        """Get number of active modules in the course."""
        if hasattr(obj.course, "modules"):
            return obj.course.modules.filter(is_active=True).count()
        return 0


class EnrollmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating enrollments."""

    class Meta:
        model = Enrollment
        fields = ["user", "course", "order"]

    def validate(self, attrs):
        """Validate enrollment creation."""
        user = attrs.get("user")
        course = attrs.get("course")

        # Check if already enrolled
        if Enrollment.objects.filter(user=user, course=course).exists():
            raise serializers.ValidationError(f"User is already enrolled in '{course.title}'")

        # Check if course is active
        if not course.is_active or course.status != "published":
            raise serializers.ValidationError("This course is not available for enrollment.")

        return attrs


class EnrollmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating enrollment progress."""

    class Meta:
        model = Enrollment
        fields = [
            "progress_percentage",
            "is_active",
            "certificate_issued",
            "completed_at",
        ]

    def validate_progress_percentage(self, value):
        """Validate progress percentage."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Progress percentage must be between 0 and 100.")
        return value

    def update(self, instance, validated_data):
        """Update enrollment and auto-complete if 100%."""
        progress = validated_data.get("progress_percentage", instance.progress_percentage)

        # Auto-set completed_at if reaching 100%
        if progress == 100 and not instance.completed_at:
            validated_data["completed_at"] = timezone.now()

        return super().update(instance, validated_data)


# ========== Coupon Validation Serializer (for cart/checkout) ==========


class CouponApplicationSerializer(serializers.Serializer):
    """Serializer for applying coupon to cart/order."""

    coupon_code = serializers.CharField(max_length=50)
    course_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        help_text="List of course IDs to apply coupon to",
    )

    def validate_coupon_code(self, value):
        """Validate coupon code exists."""
        try:
            coupon = Coupon.objects.get(code=value.upper())
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code.")

        # Check if coupon is valid
        is_valid, message = coupon.is_valid()
        if not is_valid:
            raise serializers.ValidationError(message)

        return value

    def validate_course_ids(self, value):
        """Validate courses exist."""
        if not value:
            raise serializers.ValidationError("At least one course ID is required.")

        courses = Course.objects.filter(id__in=value, is_active=True, status="published")
        if courses.count() != len(value):
            raise serializers.ValidationError("One or more invalid course IDs.")

        return value

    def validate(self, attrs):
        """Validate coupon can be applied to courses."""
        coupon_code = attrs.get("coupon_code")
        course_ids = attrs.get("course_ids")

        coupon = Coupon.objects.get(code=coupon_code.upper())
        courses = Course.objects.filter(id__in=course_ids)

        # Check if coupon applies to all courses
        for course in courses:
            if not coupon.can_apply_to_course(course):
                raise serializers.ValidationError(f"Coupon '{coupon.code}' cannot be applied to course '{course.title}'")

        attrs["coupon"] = coupon
        attrs["courses"] = courses

        return attrs


class CouponApplicationResultSerializer(serializers.Serializer):
    """Serializer for coupon application result."""

    coupon_code = serializers.CharField()
    discount_type = serializers.CharField()
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    courses_count = serializers.IntegerField()
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    message = serializers.CharField()
