"""Admin configuration for Cart and Wishlist models"""
from django.contrib import admin
from django.utils.html import format_html

from api.models.models_cart import Cart, CartItem, Wishlist


class CartItemInline(admin.TabularInline):
    """Inline admin for cart items"""
    model = CartItem
    extra = 0
    readonly_fields = ['course', 'subtotal_display', 'created_at']
    fields = ['course', 'subtotal_display', 'created_at']
    can_delete = True
    
    def subtotal_display(self, obj):
        """Display formatted subtotal"""
        if obj.id:
            return f"${obj.get_subtotal()}"
        return "-"
    subtotal_display.short_description = "Subtotal"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin interface for Cart model"""
    list_display = [
        'id', 'user_display', 'session_key_display', 
        'item_count', 'total_display', 'created_at', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'session_key']
    readonly_fields = ['id', 'item_count', 'total_display', 'created_at', 'updated_at']
    inlines = [CartItemInline]
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('id', 'user', 'session_key')
        }),
        ('Statistics', {
            'fields': ('item_count', 'total_display')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_display(self, obj):
        """Display user email or guest indicator"""
        if obj.user:
            return obj.user.email
        return format_html('<span style="color: #999;">Guest</span>')
    user_display.short_description = "User"
    
    def session_key_display(self, obj):
        """Display truncated session key"""
        if obj.session_key:
            return f"{obj.session_key[:8]}..."
        return "-"
    session_key_display.short_description = "Session"
    
    def item_count(self, obj):
        """Display item count"""
        return obj.get_item_count()
    item_count.short_description = "Items"
    
    def total_display(self, obj):
        """Display formatted total"""
        return f"${obj.get_total()}"
    total_display.short_description = "Total"
    
    def has_add_permission(self, request):
        """Disable manual cart creation"""
        return False


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """Admin interface for CartItem model"""
    list_display = [
        'id', 'cart_owner', 'course', 
        'subtotal_display', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = [
        'cart__user__email', 'cart__user__first_name', 
        'cart__user__last_name', 'course__title'
    ]
    readonly_fields = ['id', 'subtotal_display', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Item Information', {
            'fields': ('id', 'cart', 'course')
        }),
        ('Pricing', {
            'fields': ('subtotal_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def cart_owner(self, obj):
        """Display cart owner"""
        if obj.cart.user:
            return obj.cart.user.email
        return format_html('<span style="color: #999;">Guest ({0}...)</span>', 
                         obj.cart.session_key[:8] if obj.cart.session_key else 'N/A')
    cart_owner.short_description = "Cart Owner"
    
    def subtotal_display(self, obj):
        """Display formatted subtotal"""
        return f"${obj.get_subtotal()}"
    subtotal_display.short_description = "Subtotal"


class WishlistCourseInline(admin.TabularInline):
    """Inline admin for wishlist courses"""
    model = Wishlist.courses.through
    extra = 0
    verbose_name = "Wishlist Course"
    verbose_name_plural = "Wishlist Courses"


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Admin interface for Wishlist model"""
    list_display = [
        'id', 'user_email', 'course_count', 
        'created_at', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'course_count', 'created_at', 'updated_at']
    filter_horizontal = ['courses']
    
    fieldsets = (
        ('Wishlist Information', {
            'fields': ('id', 'user', 'course_count')
        }),
        ('Courses', {
            'fields': ('courses',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = "User"
    
    def course_count(self, obj):
        """Display course count"""
        return obj.courses.count()
    course_count.short_description = "Courses"
    
    def has_add_permission(self, request):
        """Disable manual wishlist creation"""
        return False
