"""Custom Payment models for admin-initiated enrollments.

This module provides the `CustomPayment` model used for admin-created payments
and enrollments (scholarships, manual payments, etc.).
"""

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from api.utils.helper_models import TimeStampedModel


class CustomPayment(TimeStampedModel):
    """Admin-initiated custom payment to enroll student in course with flexible pricing."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('ssl_commerce', 'SSLCommerz'),
        ('amar_pay', 'Amar Pay'),
        ('cash', 'Cash'),
        ('free', 'Free/Scholarship'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Unique payment reference number (CPAY-YYYYMMDD-XXXXX)"
    )
    
    # Student being enrolled
    student = models.ForeignKey(
        'api.CustomUser',
        on_delete=models.CASCADE,
        related_name='custom_payments',
        help_text="Student being enrolled"
    )
    
    # Course enrollment (optional - can be pure custom payment)
    course = models.ForeignKey(
        'api.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custom_payments',
        help_text="Course for enrollment (optional)"
    )
    
    # Admin who initiated this
    created_by = models.ForeignKey(
        'api.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_custom_payments',
        help_text="Admin who created this payment"
    )
    
    # Payment Details
    title = models.CharField(
        max_length=255,
        help_text="Payment title (e.g., 'Scholarship Enrollment', 'Staff Training')"
    )
    description = models.TextField(
        blank=True,
        help_text="Reason for custom payment (scholarship, discount, etc.)"
    )
    
    # Pricing
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Custom payment amount (can be 0 for free enrollment)"
    )
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original course price (for reference)"
    )
    currency = models.CharField(
        max_length=3,
        default='BDT',
        help_text="Currency code"
    )
    
    # Status and Payment
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Payment status"
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
    
    # Enrollment tracking
    enrollment = models.OneToOneField(
        'api.Enrollment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custom_payment',
        help_text="Associated enrollment record"
    )
    
    # Timestamps
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was completed"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was cancelled"
    )
    
    # Admin notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes (staff only)"
    )
    
    # Active status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this payment record is active"
    )
    
    class Meta(TimeStampedModel.Meta):
        verbose_name = "Custom Payment"
        verbose_name_plural = "Custom Payments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['payment_number']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self._generate_payment_number()
        
        # Auto-set timestamps
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def _generate_payment_number(self):
        """Generate unique payment number in format CPAY-YYYYMMDD-XXXXX."""
        import random
        import string
        
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        payment_number = f"CPAY-{date_str}-{random_str}"
        
        while CustomPayment.objects.filter(payment_number=payment_number).exists():
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            payment_number = f"CPAY-{date_str}-{random_str}"
        
        return payment_number
    
    def create_enrollment(self):
        """Create enrollment for student in course."""
        from api.models.models_order import Enrollment
        
        if self.course and not self.enrollment:
            enrollment = Enrollment.objects.create(
                user=self.student,
                course=self.course,
                is_active=True
            )
            self.enrollment = enrollment
            self.save()
            return enrollment
        return self.enrollment
    
    def mark_as_completed(self):
        """Mark payment as completed and create enrollment."""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()
            
            # Auto-create enrollment if course is set
            if self.course:
                self.create_enrollment()
    
    def __str__(self):
        course_info = f" - {self.course.title}" if self.course else ""
        return f"{self.payment_number} - {self.student.email}{course_info} ({self.amount} {self.currency})"

