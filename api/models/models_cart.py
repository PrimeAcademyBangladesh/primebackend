"""Shopping Cart and Wishlist Models"""
import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone

from api.models.models_auth import CustomUser
from api.models.models_course import Course
from api.utils.helper_models import TimeStampedModel


class Cart(TimeStampedModel):
    """Shopping cart for users (supports both authenticated and guest users)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='cart',
        null=True,
        blank=True,
        help_text="User who owns this cart (null for guest carts)"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Session key for guest users"
    )
    
    class Meta(TimeStampedModel.Meta):
        verbose_name = "Shopping Cart"
        verbose_name_plural = "Shopping Carts"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
        ]
    
    def get_total(self):
        """Calculate total cart amount with discounts"""
        total = sum(item.get_subtotal() for item in self.items.all())
        return Decimal(str(total))
    
    def get_item_count(self):
        """Get total number of items"""
        return self.items.count()
    
    def clear(self):
        """Remove all items from cart"""
        self.items.all().delete()
    
    def __str__(self):
        if self.user:
            return f"Cart for {self.user.email}"
        return f"Guest Cart ({self.session_key[:8]}...)"


class CartItem(TimeStampedModel):
    """Individual courses in shopping cart"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        Cart, 
        related_name='items', 
        on_delete=models.CASCADE
    )
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE,
        help_text="Course added to cart"
    )
    
    class Meta(TimeStampedModel.Meta):
        unique_together = ('cart', 'course')
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        ordering = ['-created_at']
    
    def get_subtotal(self):
        """Get price for this course (with discount if applicable)"""
        if hasattr(self.course, 'pricing') and self.course.pricing:
            return Decimal(str(self.course.pricing.get_discounted_price()))
        return Decimal('0.00')
    
    def __str__(self):
        cart_owner = self.cart.user.email if self.cart.user else f"Guest {self.cart.session_key[:8]}"
        return f"{self.course.title} in {cart_owner}'s cart"


class Wishlist(TimeStampedModel):
    """User's wishlist for courses they're interested in"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='wishlist'
    )
    courses = models.ManyToManyField(
        Course, 
        related_name='wishlisted_by',
        blank=True,
        help_text="Courses saved for later"
    )
    
    class Meta(TimeStampedModel.Meta):
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
    
    def __str__(self):
        return f"{self.user.email}'s wishlist ({self.courses.count()} items)"
