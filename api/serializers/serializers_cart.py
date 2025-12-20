"""Cart and Wishlist Serializers"""

from rest_framework import serializers
from decimal import Decimal

from api.models.models_cart import Cart, CartItem, Wishlist
from api.models.models_course import Course


class CartItemCourseSerializer(serializers.ModelSerializer):
    """Nested course details for cart items"""

    price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    header_image = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "header_image",
            "price",
            "discounted_price",
            "has_discount",
        ]

    def get_price(self, obj):
        """Get original price"""
        if hasattr(obj, "pricing") and obj.pricing:
            return str(obj.pricing.base_price)
        return "0.00"

    def get_discounted_price(self, obj):
        """Get discounted price"""
        if hasattr(obj, "pricing") and obj.pricing:
            return str(obj.pricing.get_discounted_price())
        return "0.00"

    def get_has_discount(self, obj):
        """Check if course has active discount"""
        if hasattr(obj, "pricing") and obj.pricing:
            return obj.pricing.is_currently_discounted()
        return False

    def get_header_image(self, obj):
        """Get header image URL"""
        if obj.header_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.header_image.url)
            return obj.header_image.url
        return None


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items"""

    course = CartItemCourseSerializer(read_only=True)
    course_id = serializers.UUIDField(write_only=True)
    batch_info = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "course",
            "course_id",
            "batch",
            "batch_info",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "batch_info", "created_at", "updated_at"]

    def get_batch_info(self, obj):
        """Get batch information for this cart item including installment availability"""
        if obj.batch:
            # Determine if installment is available for this batch
            # Batch setting overrides course setting
            has_installment = False
            installment_preview = None

            if obj.batch.installment_available is not None:
                # Batch explicitly sets installment availability
                if obj.batch.installment_available and obj.batch.installment_count:
                    has_installment = True
                    # Calculate installment details for batch
                    if obj.batch.custom_price:
                        total_price = obj.batch.custom_price
                    elif hasattr(obj.course, "pricing") and obj.course.pricing:
                        total_price = obj.course.pricing.get_discounted_price()
                    else:
                        total_price = None

                    if total_price:
                        per_installment = total_price / obj.batch.installment_count
                        installment_preview = {
                            "available": True,
                            "count": obj.batch.installment_count,
                            "amount": float(per_installment),
                            "total": float(total_price),
                            "description": f"Pay in {obj.batch.installment_count} installments of ৳{per_installment:,.2f}",
                        }
            else:
                # Use course default setting
                if hasattr(obj.course, "pricing") and obj.course.pricing:
                    pricing = obj.course.pricing
                    if pricing.installment_available and pricing.installment_count:
                        has_installment = True
                        total_price = (
                            obj.batch.custom_price or pricing.get_discounted_price()
                        )
                        per_installment = total_price / pricing.installment_count
                        installment_preview = {
                            "available": True,
                            "count": pricing.installment_count,
                            "amount": float(per_installment),
                            "total": float(total_price),
                            "description": f"Pay in {pricing.installment_count} installments of ৳{per_installment:,.2f}",
                        }

            return {
                "id": str(obj.batch.id),
                "batch_number": obj.batch.batch_number,
                "batch_name": obj.batch.batch_name,
                "display_name": obj.batch.get_display_name(),
                "slug": obj.batch.slug,
                "start_date": obj.batch.start_date,
                "end_date": obj.batch.end_date,
                "has_installment": has_installment,
                "installment_preview": installment_preview,
            }
        return None

    def get_subtotal(self, obj):
        """Get subtotal for this item"""
        return str(obj.get_subtotal())


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart with payment method grouping"""

    items = CartItemSerializer(many=True, read_only=True)
    installment_preview = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    payment_summary = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total",
            "item_count",
            "installment_preview",
            "payment_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total(self, obj):
        """Get cart total"""
        return str(obj.get_total())

    def get_item_count(self, obj):
        """Get item count"""
        return obj.get_item_count()

    def get_payment_summary(self, obj):
        """Group cart items by payment method for checkout validation.

        Returns summary of installment vs full payment items to help frontend
        enforce single payment method per checkout.
        """
        items = obj.items.all()
        if not items.exists():
            return {
                "has_mixed_payment_methods": False,
                "installment_items": [],
                "full_payment_items": [],
                "can_checkout_together": True,
            }

        installment_items = []
        full_payment_items = []

        for item in items:
            item_data = {
                "item_id": str(item.id),
                "course_title": item.course.title,
                "batch_name": item.batch.get_display_name() if item.batch else None,
                "subtotal": float(item.get_subtotal()),
            }

            # Check if item has installment
            has_installment = False
            if item.batch:
                if item.batch.installment_available is not None:
                    has_installment = (
                        item.batch.installment_available
                        and item.batch.installment_count
                    )
                elif hasattr(item.course, "pricing") and item.course.pricing:
                    has_installment = (
                        item.course.pricing.installment_available
                        and item.course.pricing.installment_count
                    )

            if has_installment:
                installment_items.append(item_data)
            else:
                full_payment_items.append(item_data)

        has_mixed = len(installment_items) > 0 and len(full_payment_items) > 0

        return {
            "has_mixed_payment_methods": has_mixed,
            "installment_items_count": len(installment_items),
            "full_payment_items_count": len(full_payment_items),
            "installment_items": installment_items,
            "full_payment_items": full_payment_items,
            "can_checkout_together": not has_mixed,
            "message": (
                "Your cart has courses with different payment methods. Please checkout one payment type at a time."
                if has_mixed
                else "All items can be checked out together."
            ),
        }

    def get_installment_preview(self, obj):
        """Return backend-controlled installment plan from course pricing.

        Returns the single installment plan configured in the course's pricing,
        not multiple options. This ensures consistency across the entire system.
        """
        # For carts with multiple items, we'd need different logic
        # For now, assuming single-course cart (typical for course purchases)
        items = obj.items.all()
        if not items.exists():
            return None

        # Get first item's course pricing
        first_item = items.first()
        course = first_item.course

        if not hasattr(course, "pricing") or not course.pricing:
            return None

        pricing = course.pricing

        # Return backend-controlled installment plan
        if pricing.installment_available and pricing.installment_count:
            return {
                "available": True,
                "count": pricing.installment_count,
                "amount": float(pricing.get_installment_amount()),
                "total": float(pricing.get_discounted_price()),
                "description": f"Pay in {pricing.installment_count} installments of ৳{pricing.get_installment_amount():,.2f}",
            }

        return None


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for adding items to cart.

    Rules:
    - Either course_id OR batch_id is required
    - batch_id takes priority
    - course is auto-derived from batch
    """

    course_id = serializers.UUIDField(required=False)
    batch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        from api.models.models_course import Course, CourseBatch

        course_id = data.get("course_id")
        batch_id = data.get("batch_id")

        # ❌ Neither provided
        if not course_id and not batch_id:
            raise serializers.ValidationError(
                "Either course or batch must be provided."
            )

        # ✅ If batch is provided → derive course
        if batch_id:
            try:
                batch = CourseBatch.objects.get(id=batch_id, is_active=True)
            except CourseBatch.DoesNotExist:
                raise serializers.ValidationError(
                    {"batch_id": "Batch not found or is not available."}
                )

            data["batch"] = batch
            data["course"] = batch.course
            return data

        # ✅ Course-only flow
        try:
            course = Course.objects.get(id=course_id, is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError(
                {"course_id": "Course not found or is not available."}
            )

        data["course"] = course
        data["batch"] = None
        return data


class WishlistCourseSerializer(serializers.ModelSerializer):
    """Nested course details for wishlist"""

    price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    header_image = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "header_image",
            "price",
            "discounted_price",
            "has_discount",
        ]

    def get_price(self, obj):
        """Get original price"""
        if hasattr(obj, "pricing") and obj.pricing:
            return str(obj.pricing.base_price)
        return "0.00"

    def get_discounted_price(self, obj):
        """Get discounted price"""
        if hasattr(obj, "pricing") and obj.pricing:
            return str(obj.pricing.get_discounted_price())
        return "0.00"

    def get_has_discount(self, obj):
        """Check if course has active discount"""
        if hasattr(obj, "pricing") and obj.pricing:
            return obj.pricing.is_currently_discounted()
        return False

    def get_header_image(self, obj):
        """Get header image URL"""
        if obj.header_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.header_image.url)
            return obj.header_image.url
        return None


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for wishlist"""

    courses = WishlistCourseSerializer(many=True, read_only=True)
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ["id", "courses", "course_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_course_count(self, obj):
        """Get number of courses in wishlist"""
        return obj.courses.count()


class AddToWishlistSerializer(serializers.Serializer):
    """Serializer for adding/removing courses from wishlist"""

    course_id = serializers.UUIDField(required=True)

    def validate_course_id(self, value):
        """Validate that course exists and is active"""
        try:
            course = Course.objects.get(id=value, is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found or is not available.")
        return value


class MoveToCartResponseSerializer(serializers.Serializer):
    """Response serializer for moving course from wishlist to cart"""

    message = serializers.CharField()
    cart = CartSerializer()
    wishlist = WishlistSerializer()
