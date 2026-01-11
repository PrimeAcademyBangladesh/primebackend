"""
Pricing and Coupon models for course monetization.
This module handles all pricing-related functionality including discounts, coupons, and installments.
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from api.utils.helper_models import TimeStampedModel


class CoursePrice(TimeStampedModel):
    """Advanced pricing management with discounts and currency support."""

    CURRENCY_CHOICES = [
        ("BDT", "Bangladeshi Taka"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.OneToOneField(
        "api.Course", related_name="pricing", on_delete=models.CASCADE  # Use string reference to avoid circular import
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Base price of the course in selected currency",
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="BDT", help_text="Currency for pricing")
    is_active = models.BooleanField(default=True, help_text="Whether this pricing is currently active")
    is_free = models.BooleanField(default=False, help_text="Mark as free course (overrides all pricing)")

    # Advanced Discount Fields
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage discount (0-100%)",
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Fixed amount discount",
    )
    discount_start_date = models.DateTimeField(null=True, blank=True, help_text="When discount becomes active")
    discount_end_date = models.DateTimeField(null=True, blank=True, help_text="When discount expires")

    # Installment Options
    installment_available = models.BooleanField(default=False, help_text="Whether installment payment is available")
    installment_count = models.PositiveIntegerField(null=True, blank=True, help_text="Number of installments allowed")

    def clean(self):
        """Validate model data integrity."""
        from django.core.exceptions import ValidationError

        # Validate discount logic
        if self.discount_start_date and self.discount_end_date:
            if self.discount_start_date >= self.discount_end_date:
                raise ValidationError("Discount start date must be before end date")

        # Validate percentage discount range
        if self.discount_percentage > 100:
            raise ValidationError("Discount percentage cannot exceed 100%")

        # Validate installment logic
        if self.installment_available and not self.installment_count:
            raise ValidationError("Installment count is required when installments are available")

        if self.installment_count and self.installment_count < 2:
            raise ValidationError("Installment count must be at least 2")

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Course Price"
        verbose_name_plural = "03. Course Prices"
        indexes = [
            models.Index(fields=["course", "is_active"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["is_free"]),
        ]

    def get_discounted_price(self):
        """Calculate price after applying time-based discounts."""
        from django.utils import timezone

        if self.is_free:
            return Decimal("0.00")

        # Return base_price if not yet saved or base_price is None
        if not self.base_price:
            return Decimal("0.00")

        # Check if discount is currently valid
        now = timezone.now()
        discount_valid = True

        if self.discount_start_date and now < self.discount_start_date:
            discount_valid = False
        if self.discount_end_date and now > self.discount_end_date:
            discount_valid = False

        if not discount_valid:
            return self.base_price

        # Apply percentage discount first
        price = self.base_price
        if self.discount_percentage and self.discount_percentage > 0:
            price = price - (price * (self.discount_percentage / 100))

        # Then apply fixed amount discount
        if self.discount_amount and self.discount_amount > 0:
            price = price - self.discount_amount

        # Ensure price doesn't go below 0
        return max(price, Decimal("0.00"))

    def get_savings(self):
        """Calculate total savings from discounts."""
        if not self.base_price:
            return Decimal("0.00")
        return self.base_price - self.get_discounted_price()

    def get_installment_amount(self):
        """Calculate per-installment amount if installments are available."""
        if not self.installment_available or not self.installment_count:
            return None

        total_price = self.get_discounted_price()
        if total_price == 0:
            return Decimal("0.00")

        # Round to 2 decimal places to avoid floating point issues
        return round(total_price / self.installment_count, 2)

    def is_currently_discounted(self):
        """Check if course has active discount."""
        from django.utils import timezone

        now = timezone.now()

        has_time_discount = False
        if self.discount_start_date and self.discount_end_date:
            has_time_discount = self.discount_start_date <= now <= self.discount_end_date
        elif not self.discount_start_date and not self.discount_end_date:
            has_time_discount = True
        elif self.discount_start_date and not self.discount_end_date:
            has_time_discount = now >= self.discount_start_date
        elif not self.discount_start_date and self.discount_end_date:
            has_time_discount = now <= self.discount_end_date

        has_discount = (self.discount_percentage and self.discount_percentage > 0) or (
            self.discount_amount and self.discount_amount > 0
        )

        return has_time_discount and has_discount

    @property
    def effective_price(self):
        """Returns the current effective price (discounted if available, otherwise base)."""
        return self.get_discounted_price()

    def __str__(self):
        if self.is_free:
            return f"Free - {self.course.title}"
        return f"{self.base_price} {self.currency} - {self.course.title}"


class Coupon(TimeStampedModel):
    """Advanced coupon and promo code management system."""

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage Discount"),
        ("fixed", "Fixed Amount Discount"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50, unique=True, db_index=True, help_text="Unique coupon code (e.g., SAVE20, NEWSTUDENT)"
    )
    discount_type = models.CharField(
        max_length=20, choices=DISCOUNT_TYPE_CHOICES, help_text="Type of discount this coupon provides"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Discount value (percentage or fixed amount)",
    )

    # Course Applicability
    courses = models.ManyToManyField(
        "api.Course",  # Use string reference to avoid circular import
        blank=True,
        related_name="coupons",
        help_text="Specific courses this coupon applies to (leave empty for all courses)",
    )
    apply_to_all = models.BooleanField(default=False, help_text="Apply to all courses (overrides specific course selection)")

    # Usage Limitations
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum total uses (leave empty for unlimited)")
    used_count = models.PositiveIntegerField(default=0, help_text="Number of times this coupon has been used")
    max_uses_per_user = models.PositiveIntegerField(default=1, help_text="Maximum uses per user")

    # Validity Period
    is_active = models.BooleanField(default=True, help_text="Whether this coupon is currently active")
    valid_from = models.DateTimeField(help_text="When this coupon becomes valid")
    valid_until = models.DateTimeField(help_text="When this coupon expires")

    def clean(self):
        """Validate coupon data integrity."""
        from django.core.exceptions import ValidationError

        # Validate date range
        if self.valid_from >= self.valid_until:
            raise ValidationError("Valid from date must be before valid until date")

        # Validate discount value based on type
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValidationError("Percentage discount cannot exceed 100%")

        # Validate usage limits
        if self.max_uses and self.used_count > self.max_uses:
            raise ValidationError("Used count cannot exceed max uses")

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Course Coupon"
        verbose_name_plural = "25. Course Coupons"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "valid_from", "valid_until"]),
            models.Index(fields=["discount_type"]),
        ]

    def get_remaining_uses(self):
        """Get remaining number of uses for this coupon."""
        if self.max_uses is None:
            return None  # Unlimited
        return max(0, self.max_uses - self.used_count)

    def is_valid(self):
        """Check if coupon is currently valid for use."""
        from django.utils import timezone

        now = timezone.now()

        if not self.is_active:
            return False, "Coupon is not active"
        if now < self.valid_from:
            return False, "Coupon is not yet valid"
        if now > self.valid_until:
            return False, "Coupon has expired"
        if self.max_uses and self.used_count >= self.max_uses:
            return False, "Coupon usage limit reached"

        return True, "Coupon is valid"

    def can_apply_to_course(self, course):
        """Check if this coupon can be applied to a specific course."""
        if self.apply_to_all:
            return True
        return self.courses.filter(id=course.id).exists()

    def calculate_discount(self, price):
        """Calculate discount amount for given price."""
        if not isinstance(price, Decimal):
            price = Decimal(str(price))

        if self.discount_type == "percentage":
            discount = price * (self.discount_value / 100)
        else:  # fixed amount
            discount = self.discount_value

        # Ensure discount doesn't exceed the price
        return min(discount, price)

    def increment_usage(self):
        """Safely increment usage count."""
        from django.db import transaction

        with transaction.atomic():
            # Refresh from database to get latest used_count
            latest = Coupon.objects.select_for_update().get(id=self.id)
            latest.used_count += 1
            latest.save(update_fields=["used_count"])
            self.used_count = latest.used_count

    def __str__(self):
        return f"{self.code} ({self.discount_value}{'%' if self.discount_type == 'percentage' else ' BDT'})"
