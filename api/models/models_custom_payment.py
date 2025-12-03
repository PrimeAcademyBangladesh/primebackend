"""Custom Payment models for admin-initiated enrollments and event registrations.

This module handles:
1. CustomPayment - Admin enrolls student in course with custom amount (scholarships, free access)
2. EventRegistration - Event/workshop/training registrations with payment tracking
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


class EventRegistration(TimeStampedModel):
    """Track event/workshop/training registrations with payment."""
    
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
        ('free', 'Free'),
        ('other', 'Other'),
    ]
    
    EVENT_TYPE_CHOICES = [
        ('workshop', 'Workshop'),
        ('training', 'Training'),
        ('seminar', 'Seminar'),
        ('webinar', 'Webinar'),
        ('conference', 'Conference'),
        ('meetup', 'Meetup'),
        ('bootcamp', 'Bootcamp'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Unique registration number (EVT-YYYYMMDD-XXXXX)"
    )
    
    # Participant
    user = models.ForeignKey(
        'api.CustomUser',
        on_delete=models.CASCADE,
        related_name='event_registrations',
        help_text="User registering for event"
    )
    
    # Admin who created this (if admin-initiated)
    created_by = models.ForeignKey(
        'api.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_event_registrations',
        help_text="Admin who created this registration (optional)"
    )
    
    # Event Information
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='workshop',
        db_index=True,
        help_text="Type of event"
    )
    event_name = models.CharField(
        max_length=255,
        help_text="Name of the event"
    )
    event_date = models.DateTimeField(
        help_text="Date and time of the event"
    )
    event_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Event location (physical or virtual)"
    )
    event_description = models.TextField(
        blank=True,
        help_text="Event description and details"
    )
    
    # Ticket Information
    ticket_type = models.CharField(
        max_length=100,
        default='General Admission',
        help_text="Type of ticket (e.g., VIP, Early Bird, Student)"
    )
    number_of_tickets = models.PositiveIntegerField(
        default=1,
        help_text="Number of tickets purchased"
    )
    
    # Pricing
    price_per_ticket = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Price per ticket"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount (price × tickets)"
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
    
    # Attendance Tracking
    is_attended = models.BooleanField(
        default=False,
        help_text="Whether attendee showed up"
    )
    attended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When attendance was recorded"
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
        help_text="When registration was cancelled"
    )
    
    # Contact Information
    contact_name = models.CharField(
        max_length=200,
        help_text="Full name for registration"
    )
    contact_email = models.EmailField(
        help_text="Email for registration and updates"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
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
        help_text="Whether this registration is active"
    )
    
    class Meta(TimeStampedModel.Meta):
        verbose_name = "Event Registration"
        verbose_name_plural = "Event Registrations"
        ordering = ['-event_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['registration_number']),
            models.Index(fields=['event_type', 'event_date']),
            models.Index(fields=['event_date', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['created_by', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.registration_number:
            self.registration_number = self._generate_registration_number()
        
        # Auto-calculate total
        self.total_amount = self.price_per_ticket * self.number_of_tickets
        
        # Auto-set timestamps
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def _generate_registration_number(self):
        """Generate unique registration number in format EVT-YYYYMMDD-XXXXX."""
        import random
        import string
        
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        registration_number = f"EVT-{date_str}-{random_str}"
        
        while EventRegistration.objects.filter(registration_number=registration_number).exists():
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            registration_number = f"EVT-{date_str}-{random_str}"
        
        return registration_number
    
    def mark_as_completed(self):
        """Mark payment as completed."""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()
    
    def mark_attendance(self):
        """Mark user as attended."""
        if not self.is_attended:
            self.is_attended = True
            self.attended_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"{self.registration_number} - {self.event_name} ({self.number_of_tickets} ticket(s)) - {self.user.email}"
