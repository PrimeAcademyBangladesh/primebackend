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
            'header_image', 'price', 'discounted_price', 'has_discount', 'batch'
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
    subtotal = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'course', 'course_id', 'subtotal', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
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
        """Return candidate installment plans and per-installment amounts.

        Respects the minimum per-installment amount rule used by order validation
        (minimum 500.00 BDT per installment).
        """
        total = obj.get_total()
        # Candidate plans to display in cart UI
        candidate_plans = [2, 3, 4, 6]
        min_per_installment = Decimal('500.00')

        preview = []
        for plan in candidate_plans:
            per = (total / Decimal(plan)).quantize(Decimal('0.01'))
            allowed = per >= min_per_installment
            preview.append({
                'plan': plan,
                'per_installment': str(per),
                'allowed': allowed,
            })

        return preview


class AddToCartSerializer(serializers.Serializer):
    """Serializer for adding items to cart"""
    course_id = serializers.UUIDField(required=True)
    
    def validate_course_id(self, value):
        """Validate that course exists and is active"""
        try:
            course = Course.objects.get(id=value, is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found or is not available.")
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
            'header_image', 'price', 'discounted_price', 'has_discount', 'batch'
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
