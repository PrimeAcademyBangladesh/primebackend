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
            'id', 'title', 'slug', 'short_description',
            'header_image', 'price', 'discounted_price', 'has_discount'
        ]
    
    def get_price(self, obj):
        """Get original price"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return str(obj.pricing.base_price)
        return "0.00"
    
    def get_discounted_price(self, obj):
        """Get discounted price"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return str(obj.pricing.get_discounted_price())
        return "0.00"
    
    def get_has_discount(self, obj):
        """Check if course has active discount"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return obj.pricing.is_currently_discounted()
        return False
    
    def get_header_image(self, obj):
        """Get header image URL"""
        if obj.header_image:
            request = self.context.get('request')
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
            'id', 'course', 'course_id', 'batch', 'batch_info', 'subtotal', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'batch_info', 'created_at', 'updated_at']
    
    def get_batch_info(self, obj):
        """Get batch information for this cart item"""
        if obj.batch:
            return {
                'id': str(obj.batch.id),
                'batch_number': obj.batch.batch_number,
                'batch_name': obj.batch.batch_name,
                'display_name': obj.batch.get_display_name(),
                'slug': obj.batch.slug,
                'start_date': obj.batch.start_date,
                'end_date': obj.batch.end_date,
            }
        return None
    
    def get_subtotal(self, obj):
        """Get subtotal for this item"""
        return str(obj.get_subtotal())


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart"""
    items = CartItemSerializer(many=True, read_only=True)
    installment_preview = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'items', 'total', 'item_count', 'installment_preview',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_total(self, obj):
        """Get cart total"""
        return str(obj.get_total())
    
    def get_item_count(self, obj):
        """Get item count"""
        return obj.get_item_count()

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
        
        if not hasattr(course, 'pricing') or not course.pricing:
            return None
        
        pricing = course.pricing
        
        # Return backend-controlled installment plan
        if pricing.installment_available and pricing.installment_count:
            return {
                'available': True,
                'count': pricing.installment_count,
                'amount': float(pricing.get_installment_amount()),
                'total': float(pricing.get_discounted_price()),
                'description': f"Pay in {pricing.installment_count} installments of ৳{pricing.get_installment_amount():,.2f}"
            }
        
        return None


class AddToCartSerializer(serializers.Serializer):
    """Serializer for adding items to cart"""
    course_id = serializers.UUIDField(required=True)
    batch_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate_course_id(self, value):
        """Validate that course exists and is active"""
        try:
            course = Course.objects.get(id=value, is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found or is not available.")
        return value
    
    def validate_batch_id(self, value):
        """Validate that batch exists and is active"""
        if value:
            from api.models.models_course import CourseBatch
            try:
                batch = CourseBatch.objects.get(id=value, is_active=True)
            except CourseBatch.DoesNotExist:
                raise serializers.ValidationError("Batch not found or is not available.")
        return value


class WishlistCourseSerializer(serializers.ModelSerializer):
    """Nested course details for wishlist"""
    price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    header_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description',
            'header_image', 'price', 'discounted_price', 'has_discount'
        ]
    
    def get_price(self, obj):
        """Get original price"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return str(obj.pricing.base_price)
        return "0.00"
    
    def get_discounted_price(self, obj):
        """Get discounted price"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return str(obj.pricing.get_discounted_price())
        return "0.00"
    
    def get_has_discount(self, obj):
        """Check if course has active discount"""
        if hasattr(obj, 'pricing') and obj.pricing:
            return obj.pricing.is_currently_discounted()
        return False
    
    def get_header_image(self, obj):
        """Get header image URL"""
        if obj.header_image:
            request = self.context.get('request')
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
        fields = [
            'id', 'courses', 'course_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
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
