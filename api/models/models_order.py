"""Order and Enrollment models for course purchases and student progress tracking.

This module handles order management, course enrollments, and student progress.
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import F
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
        'api.CustomUser',
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

    coupon = models.ForeignKey(
        'api.Coupon',
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
    
    is_custom_payment = models.BooleanField(
        default=False,
        help_text="Whether this is a custom payment (not course-based)"
    )
    custom_payment_description = models.TextField(
        blank=True,
        help_text="Description of custom payment (e.g., 'Workshop fee', 'Consultation')"
    )
    
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
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()

        # Create enrollments for all courses in this order.
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




class PaymentTransaction(models.Model):
    """Idempotent payment log - prevents duplicate charges"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('settled', 'Settled'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('duplicate', 'Duplicate'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installment = models.ForeignKey(
        'OrderInstallment',
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    gateway_transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    internal_payment_id = models.CharField(max_length=255, unique=True, db_index=True)
    payment_method = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BDT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    request_id = models.CharField(max_length=255, blank=True, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        ordering = ['-created_at']
        unique_together = [('installment', 'gateway_transaction_id')]
        indexes = [
            models.Index(fields=['gateway_transaction_id']),
            models.Index(fields=['internal_payment_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['installment', 'status']),
            models.Index(fields=['request_id']),
        ]
    
    def __str__(self):
        return f"{self.internal_payment_id} - {self.status}"




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
    
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Any Extra info metadata (session keys, etc.)"
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
    
    @transaction.atomic
    def mark_as_paid(self, payment_id='', payment_method='', gateway_transaction_id=''):
        """Mark installment as paid with duplicate control."""
        
        # Validate inputs
        if not payment_id or not isinstance(payment_id, str):
            raise ValueError("payment_id must be non-empty string")
        
        payment_id = payment_id.strip()
        if not payment_id or len(payment_id) > 255:
            raise ValueError("Invalid payment_id")
        
        if not gateway_transaction_id:
            raise ValueError("gateway_transaction_id is required")
        
        # Check duplicate
        if OrderInstallment.objects.filter(
            payment_id=payment_id
        ).exclude(id=self.id).exists():
            raise ValueError(f"Duplicate payment_id: {payment_id}")
        
        # Update installment
        if self.status != 'paid':
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.payment_id = payment_id
            self.payment_method = payment_method
            self.save(update_fields=['status', 'paid_at', 'payment_id', 'payment_method'])
            
            # Atomic increment
            Order.objects.filter(id=self.order.id).update(
                installments_paid=F('installments_paid') + 1
            )
            
            # Refresh and check if fully paid
            self.order.refresh_from_db(fields=['installments_paid'])
            
            if self.order.is_fully_paid():
                self.order.mark_as_completed()
            else:
                self._update_next_installment_date()    
        
    # @transaction.atomic
    # def mark_as_paid(self, payment_id='', payment_method=''):
    #     """Mark this installment as paid and update order."""
        
    #     # Validate payment_id is not empty if updating
    #     if not payment_id:
    #         raise ValueError("payment_id cannot be empty")
        
    #     # Check for duplicate payment IDs (security: prevent double-charging)
    #     if OrderInstallment.objects.filter(
    #         payment_id=payment_id
    #     ).exclude(id=self.id).exists():
    #         raise ValueError(f"Duplicate payment_id: {payment_id}")
        
    #     if self.status != 'paid':
    #         self.status = 'paid'
    #         self.paid_at = timezone.now()
    #         self.payment_id = payment_id
    #         self.payment_method = payment_method
    #         self.save()
            
    #         # Update order's installments_paid count
    #         # self.order.installments_paid += 1 # Wrong way
    #         self.order.installments_paid = F('installments_paid') + 1
    #         self.order.save(update_fields=['installments_paid'])
            
    #         # Refresh to get actual value for subsequent checks
    #         self.order.refresh_from_db(fields=['installments_paid'])
            
    #         # Check if this was the last installment
    #         if self.order.is_fully_paid():
    #             self.order.mark_as_completed()
    #         else:
    #             # Update next installment date
    #             try:
    #                 next_installment = OrderInstallment.objects.filter(
    #                     order=self.order,
    #                     status='pending'
    #                 ).order_by('installment_number').first()
                    
    #                 if next_installment:
    #                     self.order.next_installment_date = next_installment.due_date
    #             except OrderInstallment.DoesNotExist:
    #                 self.order.next_installment_date = None
                
    #             self.order.save()
    
    def check_overdue(self):
        """Check if installment is overdue and update status."""
        if self.status == 'pending' and timezone.now() > self.due_date:
            self.status = 'overdue'
            self.save()
            return True
        return False
    
    # ========== PAYMENT HELPER METHODS ==========
    
    def can_accept_payment(self):
        """Check if this installment can accept payment."""
        return self.status in ['pending', 'overdue'] and self.is_active
    
    def remaining_amount(self):
        """Get remaining amount to be paid."""
        return self.amount if self.status != 'paid' else Decimal('0.00')
    
    def is_overdue_now(self):
        """Check if installment is currently overdue (without saving)."""
        return self.status in ['pending', 'overdue'] and timezone.now() > self.due_date
    
    def days_until_due(self):
        """Calculate days until due date (negative if overdue)."""
        delta = self.due_date - timezone.now()
        return delta.days
    
    def is_paid(self):
        """Check if installment is paid."""
        return self.status == 'paid'
    
    
    # ========== EXTRA_DATA HELPER METHODS ==========
    
    def get_extra_data(self, key, default=None):
        """Safely get value from extra_data."""
        if not self.extra_data:
            return default
        return self.extra_data.get(key, default)
    
    def set_extra_data(self, key, value, save=True):
        """Safely set value in extra_data."""
        if not self.extra_data:
            self.extra_data = {}
        self.extra_data[key] = value
        if save:
            self.save(update_fields=['extra_data'])
    
    def update_extra_data(self, data_dict, save=True):
        """Update multiple extra_data keys at once."""
        if not self.extra_data:
            self.extra_data = {}
        self.extra_data.update(data_dict)
        if save:
            self.save(update_fields=['extra_data'])
    
    
    def _update_next_installment_date(self):
        """Update next installment date efficiently."""
        next_due = OrderInstallment.objects.filter(
            order=self.order,
            status='pending'
        ).order_by('installment_number').values_list('due_date', flat=True).first()
        
        Order.objects.filter(id=self.order.id).update(
            next_installment_date=next_due
        )
    
    @classmethod
    @transaction.atomic
    def create_payment_transaction(
        cls,
        installment,
        gateway_transaction_id,
        payment_method,
        amount,
        gateway_response=None,
        request_id=None
    ):
        """Create or get payment transaction (idempotent)."""
        
        try:
            payment = PaymentTransaction.objects.get(
                gateway_transaction_id=gateway_transaction_id
            )
            return (payment, False)  # Already exists
        
        except PaymentTransaction.DoesNotExist:
            internal_id = f"PAY-{installment.order.order_number}-{installment.installment_number}-{uuid.uuid4().hex[:8]}"
            
            try:
                payment = PaymentTransaction.objects.create(
                    installment=installment,
                    gateway_transaction_id=gateway_transaction_id,
                    internal_payment_id=internal_id,
                    payment_method=payment_method,
                    amount=amount,
                    currency='BDT',
                    gateway_response=gateway_response or {},
                    request_id=request_id,
                    status='pending'
                )
                return (payment, True)  # New payment created
            
            except IntegrityError:
                payment = PaymentTransaction.objects.get(
                    gateway_transaction_id=gateway_transaction_id
                )
                return (payment, False)
        
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
        'api.CourseBatch',
        on_delete=models.CASCADE,
        related_name="enrollments",
        null=True,
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
        unique_together = [("user", "batch")]
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



