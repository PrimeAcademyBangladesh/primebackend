"""Order and Enrollment models for course purchases and student progress tracking.

This module handles order management, course enrollments, and student progress.
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from api.utils.helper_models import TimeStampedModel


class Order(TimeStampedModel):
    """Main order model for course purchases"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("bkash", "bKash"),
        ("nagad", "Nagad"),
        ("rocket", "Rocket"),
        ("card", "Credit/Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("ssl_commerce", "SSLCommerz"),
        ('amar_pay', 'Amar Pay'),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=100, 
        unique=True, 
        editable=False,
        db_index=True,
        help_text="Unique order number (auto-generated)"
    )
    user = models.ForeignKey(
        'api.CustomUser',  # Use string reference
        on_delete=models.CASCADE, 
        related_name="orders",
        help_text="User who placed this order"
    )

    # Pricing
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Subtotal before discounts and taxes"
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total discount applied"
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Tax amount (if applicable)"
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Final total amount to be paid"
    )
    currency = models.CharField(
        max_length=3, 
        default="BDT",
        help_text="Currency code (BDT, USD, etc.)"
    )

    # Coupon
    coupon = models.ForeignKey(
        'api.Coupon',  # Use string reference
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders',
        help_text="Coupon applied to this order"
    )
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Snapshot of coupon code at time of order"
    )

    # Status and payment
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default="pending",
        db_index=True,
        help_text="Current status of the order"
    )
    payment_method = models.CharField(
        max_length=50, 
        choices=PAYMENT_METHOD_CHOICES, 
        blank=True,
        help_text="Payment method used"
    )
    payment_id = models.CharField(
        max_length=255, 
        blank=True,
        help_text="External payment gateway transaction ID"
    )
    payment_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Payment gateway status response"
    )

    # Timestamps (created_at and updated_at inherited from TimeStampedModel)
    completed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the order was completed"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True, 
        help_text="When the order was cancelled"
    )

    # Billing info
    billing_email = models.EmailField(
        help_text="Email for billing and receipts"
    )
    billing_name = models.CharField(
        max_length=200,
        help_text="Full name for billing"
    )
    billing_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
    )
    billing_address = models.TextField(
        blank=True,
        help_text="Billing address (optional)"
    )
    billing_city = models.CharField(
        max_length=100,
        default="Dhaka",
        help_text="Billing city"
    )
    billing_country = models.CharField(
        max_length=100,
        default="Bangladesh",
        help_text="Billing country"
    )
    billing_postcode = models.CharField(
        max_length=20,
        default="1207",
        help_text="Billing postal/ZIP code"
    )
    
    # Installment payment tracking
    is_installment = models.BooleanField(
        default=False,
        help_text="Whether this order uses installment payment"
    )
    installment_plan = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total number of installments for this order"
    )
    installments_paid = models.PositiveIntegerField(
        default=0,
        help_text="Number of installments already paid"
    )
    next_installment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Due date for next installment payment"
    )
    
    # Custom payment option
    is_custom_payment = models.BooleanField(
        default=False,
        help_text="Whether this is a custom payment (not course-based)"
    )
    custom_payment_description = models.TextField(
        blank=True,
        help_text="Description of custom payment (e.g., 'Workshop fee', 'Consultation')"
    )
    
    # Admin notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes (visible to staff only)"
    )
    
    # Active status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this order is active"
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_method']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        
        # Auto-set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        # Auto-set cancelled_at when status changes to cancelled
        if self.status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def _generate_order_number(self):
        """Generate unique order number in format ORD-YYYYMMDD-XXXXX."""
        import random
        import string

        from django.utils import timezone
        
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        order_number = f"ORD-{date_str}-{random_str}"
        
        # Ensure uniqueness
        while Order.objects.filter(order_number=order_number).exists():
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            order_number = f"ORD-{date_str}-{random_str}"
        
        return order_number

    def get_total_items(self):
        """Get total number of items in order."""
        return self.items.count()
    
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in ['pending', 'processing']
    
    def mark_as_completed(self):
        """Mark order as completed and create enrollments."""
        # Ensure order is marked completed and completed_at is set
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()

        # Create enrollments for all courses in this order.
        # Even if the order was already marked completed previously, we may
        # not have created enrollments (e.g., earlier error). Ensure enrollments
        # exist for each OrderItem. Use get_or_create to avoid duplicates.
        for item in self.items.all():
            Enrollment.objects.get_or_create(
                user=self.user,
                course=item.course,
                batch=item.batch,
                defaults={'order': self}
            )
    
    def get_installment_amount(self):
        """Calculate amount per installment."""
        if self.is_installment and self.installment_plan and self.installment_plan > 0:
            return self.total_amount / self.installment_plan
        return self.total_amount
    
    def get_remaining_installments(self):
        """Get number of remaining installments."""
        if self.is_installment and self.installment_plan:
            return self.installment_plan - self.installments_paid
        return 0
    
    def get_paid_amount(self):
        """Calculate total amount paid through installments."""
        if self.is_installment:
            return self.get_installment_amount() * self.installments_paid
        return self.total_amount if self.status == 'completed' else Decimal('0.00')
    
    def get_remaining_amount(self):
        """Calculate remaining amount to be paid."""
        if self.is_installment:
            return self.total_amount - self.get_paid_amount()
        return Decimal('0.00') if self.status == 'completed' else self.total_amount
    
    def is_fully_paid(self):
        """Check if all installments are paid."""
        if self.is_installment:
            return self.installments_paid >= self.installment_plan
        return self.status == 'completed'
    
    def __str__(self):
        return f"Order {self.order_number} - {self.user.get_full_name or self.user.email}"


class OrderInstallment(TimeStampedModel):
    """Track individual installment payments for orders."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='installment_payments',
        help_text="Order this installment belongs to"
    )
    installment_number = models.PositiveIntegerField(
        help_text="Installment sequence number (1, 2, 3...)"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount for this installment"
    )
    due_date = models.DateTimeField(
        help_text="When this installment is due"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Payment status of this installment"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this installment was paid"
    )
    payment_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External payment transaction ID for this installment"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment method used for this installment"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this installment"
    )
    
    # Active status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this installment is active"
    )
    
    class Meta(TimeStampedModel.Meta):
        verbose_name = "Order Installment"
        verbose_name_plural = "Order Installments"
        ordering = ['order', 'installment_number']
        unique_together = [('order', 'installment_number')]
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['status']),
        ]
    
    def mark_as_paid(self, payment_id='', payment_method=''):
        """Mark this installment as paid and update order."""
        if self.status != 'paid':
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.payment_id = payment_id
            self.payment_method = payment_method
            self.save()
            
            # Update order's installments_paid count
            self.order.installments_paid += 1
            
            # Check if this was the last installment
            if self.order.is_fully_paid():
                self.order.mark_as_completed()
            else:
                # Update next installment date
                try:
                    next_installment = OrderInstallment.objects.filter(
                        order=self.order,
                        status='pending'
                    ).order_by('installment_number').first()
                    
                    if next_installment:
                        self.order.next_installment_date = next_installment.due_date
                except OrderInstallment.DoesNotExist:
                    self.order.next_installment_date = None
                
                self.order.save()
    
    def check_overdue(self):
        """Check if installment is overdue and update status."""
        if self.status == 'pending' and timezone.now() > self.due_date:
            self.status = 'overdue'
            self.save()
            return True
        return False
    
    def __str__(self):
        return f"Installment {self.installment_number}/{self.order.installment_plan} - {self.order.order_number}"


class OrderItem(TimeStampedModel):
    """Individual courses in an order."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, 
        related_name="items", 
        on_delete=models.CASCADE,
        help_text="Order this item belongs to"
    )
    course = models.ForeignKey(
        'api.Course',  # Use string reference
        on_delete=models.CASCADE,
        help_text="Course being purchased"
    )
    batch = models.ForeignKey(
        'api.CourseBatch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Specific batch for enrollment (optional)"
    )
    course_title = models.CharField(
        max_length=255,
        help_text="Snapshot of course title at time of purchase"
    )

    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Course price at time of purchase"
    )
    discount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Discount applied to this item"
    )
    currency = models.CharField(
        max_length=3,
        default="BDT",
        help_text="Currency for this item"
    )
    
    # Active status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this order item is active"
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', 'course']),
        ]
    
    def save(self, *args, **kwargs):
        """Capture course title snapshot on first save."""
        if not self.course_title and self.course:
            self.course_title = self.course.title
        super().save(*args, **kwargs)
    
    def get_total(self):
        """Calculate total for this item."""
        price = self.price if self.price is not None else Decimal('0.00')
        discount = self.discount if self.discount is not None else Decimal('0.00')
        return price - discount
    
    def __str__(self):
        return f"{self.course_title or self.course.title} - Order {self.order.order_number}"


class Enrollment(TimeStampedModel):
    """Track user's purchased courses and progress.
    
    IMPORTANT: Students enroll in CourseBatch (not Course directly).
    The 'course' field is maintained for backward compatibility and quick lookups,
    but 'batch' is the primary enrollment reference.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'api.CustomUser',  # Use string reference
        on_delete=models.CASCADE, 
        related_name="enrollments",
        help_text="Student enrolled in the course"
    )
    
    # NEW: Primary enrollment reference (batch-based enrollment)
    batch = models.ForeignKey(
        'api.CourseBatch',  # Use string reference
        on_delete=models.CASCADE,
        related_name="enrollments",
        null=True,  # Nullable for backward compatibility with existing enrollments
        blank=True,
        help_text="Course batch the student is enrolled in (primary reference)"
    )
    
    # LEGACY: Kept for backward compatibility and quick lookups
    course = models.ForeignKey(
        'api.Course',  # Use string reference
        on_delete=models.CASCADE,
        related_name="enrollments",
        help_text="Course the student is enrolled in (auto-set from batch)"
    )
    
    order = models.ForeignKey(
        Order, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="enrollments",
        help_text="Order that created this enrollment (if applicable)"
    )

    # enrolled_at inherited from created_at in TimeStampedModel
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether enrollment is currently active"
    )
    completed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the student completed the course"
    )
    certificate_issued = models.BooleanField(
        default=False,
        help_text="Whether certificate has been issued"
    )
    last_accessed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time student accessed this course"
    )

    # Progress tracking
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"
        # Updated: User can enroll in multiple batches of the same course
        unique_together = [("user", "batch")]  # One enrollment per user per batch
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['course', 'is_active']),
            models.Index(fields=['batch', 'is_active']),
            models.Index(fields=['is_active', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-set course from batch if batch is provided."""
        if self.batch and not self.course_id:
            self.course = self.batch.course
        super().save(*args, **kwargs)
        
        # Update batch enrolled count after save (in a separate transaction)
        if self.batch_id:
            from api.models.models_course import CourseBatch
            try:
                batch = CourseBatch.objects.get(pk=self.batch_id)
                batch.update_enrolled_count()
            except CourseBatch.DoesNotExist:
                pass

    def update_last_accessed(self):
        """Update last accessed timestamp."""
        self.last_accessed = timezone.now()
        self.save(update_fields=['last_accessed'])
    
    def mark_as_completed(self):
        """Mark enrollment as completed."""
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.progress_percentage = Decimal('100.00')
            self.save(update_fields=['completed_at', 'progress_percentage'])
    
    def is_completed(self):
        """Check if course is completed."""
        return self.progress_percentage == Decimal('100.00') or self.completed_at is not None
    
    @property
    def enrolled_at(self):
        """Alias for created_at for backward compatibility."""
        return self.created_at
    
    def __str__(self):
        if self.batch:
            return f"{self.user.get_full_name or self.user.email} enrolled in {self.batch.get_display_name()}"
        return f"{self.user.get_full_name or self.user.email} enrolled in {self.course.title}"
