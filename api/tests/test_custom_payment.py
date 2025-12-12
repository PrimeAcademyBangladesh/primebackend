"""
Security and integration tests for CustomPayment.
Tests role-based access control, object-level permissions, and business logic.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from api.models.models_course import Category, Course
from api.models.models_custom_payment import CustomPayment
from api.models.models_order import Enrollment
from api.models.models_pricing import CoursePrice
from api.permissions import IsStaff, IsStudent
from api.views.views_custom_payment import (CustomPaymentViewSet,)

User = get_user_model()


class CustomPaymentSecurityTestCase(TestCase):
    """Test security features for CustomPayment model."""
    
    def setUp(self):
        """Create test data."""
        # Create users
        self.student1 = User.objects.create_user(
            email='student1_cp@example.com',
            password='testpass123',
            role='student',
            first_name='Student',
            last_name='One',
            phone='01700000001'
        )
        
        self.student2 = User.objects.create_user(
            email='student2_cp@example.com',
            password='testpass123',
            role='student',
            first_name='Student',
            last_name='Two',
            phone='01700000002'
        )
        
        self.staff = User.objects.create_user(
            email='staff_cp@example.com',
            password='testpass123',
            role='staff',
            first_name='Staff',
            last_name='User',
            phone='01700000003'
        )
        
        self.admin = User.objects.create_user(
            email='admin_cp@example.com',
            password='testpass123',
            role='admin',
            first_name='Admin',
            last_name='User',
            phone='01700000004'
        )
        
        # Create course
        category = Category.objects.create(
            name='Custom Payment Test Category',
            slug='cp-test-category'
        )
        
        self.course = Course.objects.create(
            title='Custom Payment Test Course',
            slug='cp-test-course',
            category=category,
            short_description='Test course',
            status='published',
            is_active=True
        )
        
        CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal('5000.00'),
            currency='BDT',
            is_active=True
        )
        
        # Create custom payments
        self.payment1 = CustomPayment.objects.create(
            student=self.student1,
            course=self.course,
            created_by=self.admin,
            title='Scholarship - 100%',
            description='Full scholarship for excellent performance',
            amount=Decimal('0.00'),
            original_price=Decimal('5000.00'),
            status='pending',
            payment_method='free'
        )
        
        self.payment2 = CustomPayment.objects.create(
            student=self.student2,
            course=self.course,
            created_by=self.staff,
            title='Discount - 50%',
            description='Half price special offer',
            amount=Decimal('2500.00'),
            original_price=Decimal('5000.00'),
            status='completed',
            payment_method='cash'
        )
        
        self.factory = APIRequestFactory()
    
    # Permission Tests
    
    def test_only_staff_can_create_custom_payment(self):
        """Only staff should be able to create custom payments."""
        # Student cannot create
        request = self.factory.post('/api/custom-payments/')
        request.user = self.student1
        
        viewset = CustomPaymentViewSet()
        viewset.request = request
        viewset.action = 'create'
        
        permissions = viewset.get_permissions()
        has_permission = all(perm.has_permission(request, viewset) for perm in permissions)
        self.assertFalse(has_permission)
        
        # Staff can create
        request.user = self.staff
        has_permission = all(perm.has_permission(request, viewset) for perm in permissions)
        self.assertTrue(has_permission)
    
    def test_student_sees_only_own_custom_payments(self):
        """Students should only see their own custom payments."""
        request = self.factory.get('/api/custom-payments/')
        request.user = self.student1
        
        viewset = CustomPaymentViewSet()
        viewset.request = request
        viewset.action = 'list'
        queryset = viewset.get_queryset()
        
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first(), self.payment1)
        self.assertNotIn(self.payment2, queryset)
    
    def test_staff_sees_all_custom_payments(self):
        """Staff should see all custom payments."""
        request = self.factory.get('/api/custom-payments/')
        request.user = self.staff
        
        viewset = CustomPaymentViewSet()
        viewset.request = request
        viewset.action = 'list'
        viewset.format_kwarg = None  # Add this
        queryset = viewset.get_queryset()
        
        self.assertGreaterEqual(queryset.count(), 2)  # At least the 2 we created
        payment_ids = [p.id for p in queryset]
        self.assertIn(self.payment1.id, payment_ids)
        self.assertIn(self.payment2.id, payment_ids)
    
    def test_only_staff_can_update_custom_payment(self):
        """Only staff should be able to update custom payments."""
        request = self.factory.patch(f'/api/custom-payments/{self.payment1.id}/')
        request.user = self.student1
        
        viewset = CustomPaymentViewSet()
        viewset.request = request
        viewset.action = 'update'
        
        permissions = viewset.get_permissions()
        has_permission = all(perm.has_permission(request, viewset) for perm in permissions)
        self.assertFalse(has_permission)
        
        # Staff can update
        request.user = self.staff
        has_permission = all(perm.has_permission(request, viewset) for perm in permissions)
        self.assertTrue(has_permission)
    
    # Business Logic Tests
    
    def test_payment_number_auto_generated(self):
        """Payment number should be auto-generated in CPAY format."""
        payment = CustomPayment.objects.create(
            student=self.student1,
            created_by=self.admin,
            title='Test Payment',
            amount=Decimal('1000.00')
        )
        
        self.assertTrue(payment.payment_number.startswith('CPAY-'))
        self.assertEqual(len(payment.payment_number), 19)  # CPAY-YYYYMMDD-XXXXX
    
    def test_payment_number_is_unique(self):
        """Each payment should have a unique payment number."""
        payment1 = CustomPayment.objects.create(
            student=self.student1,
            created_by=self.admin,
            title='Payment 1',
            amount=Decimal('1000.00')
        )
        
        payment2 = CustomPayment.objects.create(
            student=self.student1,
            created_by=self.admin,
            title='Payment 2',
            amount=Decimal('2000.00')
        )
        
        self.assertNotEqual(payment1.payment_number, payment2.payment_number)
    
    def test_mark_as_completed_creates_enrollment(self):
        """Marking payment as completed should create enrollment if course is set."""
        self.assertIsNone(self.payment1.enrollment)
        
        self.payment1.mark_as_completed()
        self.payment1.refresh_from_db()
        
        self.assertEqual(self.payment1.status, 'completed')
        self.assertIsNotNone(self.payment1.completed_at)
        self.assertIsNotNone(self.payment1.enrollment)
        self.assertEqual(self.payment1.enrollment.user, self.student1)
        self.assertEqual(self.payment1.enrollment.course, self.course)
    
    def test_mark_as_completed_without_course(self):
        """Payment without course should not create enrollment."""
        payment = CustomPayment.objects.create(
            student=self.student1,
            created_by=self.admin,
            title='Workshop Fee',
            amount=Decimal('500.00'),
            status='pending'
        )
        
        payment.mark_as_completed()
        payment.refresh_from_db()
        
        self.assertEqual(payment.status, 'completed')
        self.assertIsNone(payment.enrollment)
    
    def test_created_by_tracks_admin(self):
        """CustomPayment should track which admin created it."""
        self.assertEqual(self.payment1.created_by, self.admin)
        self.assertEqual(self.payment2.created_by, self.staff)
    
    def test_zero_amount_allowed(self):
        """CustomPayment should allow 0 amount for free enrollments."""
        payment = CustomPayment.objects.create(
            student=self.student1,
            course=self.course,
            created_by=self.admin,
            title='Free Access',
            amount=Decimal('0.00'),
            payment_method='free'
        )
        
        self.assertEqual(payment.amount, Decimal('0.00'))
    
    def test_completed_at_auto_set(self):
        """completed_at should be auto-set when status becomes completed."""
        self.assertIsNone(self.payment1.completed_at)
        
        self.payment1.status = 'completed'
        self.payment1.save()
        
        self.assertIsNotNone(self.payment1.completed_at)
    
    def test_cancelled_at_auto_set(self):
        """cancelled_at should be auto-set when status becomes cancelled."""
        self.assertIsNone(self.payment1.cancelled_at)
        
        self.payment1.status = 'cancelled'
        self.payment1.save()
        
        self.assertIsNotNone(self.payment1.cancelled_at)



class CustomPaymentIntegrationTestCase(TestCase):
    """Integration tests for CustomPayment workflows."""
    
    def setUp(self):
        """Create test data."""
        self.admin = User.objects.create_user(
            email='admin_int@example.com',
            password='testpass123',
            role='admin',
            first_name='Admin',
            last_name='User',
            phone='01700000020'
        )
        
        self.student = User.objects.create_user(
            email='student_int@example.com',
            password='testpass123',
            role='student',
            first_name='Student',
            last_name='User',
            phone='01700000021'
        )
        
        category = Category.objects.create(
            name='Integration Test',
            slug='int-test'
        )
        
        self.course = Course.objects.create(
            title='Integration Test Course',
            slug='int-test-course',
            category=category,
            short_description='Test',
            status='published',
            is_active=True
        )
        
        CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal('10000.00'),
            currency='BDT',
            is_active=True
        )
    
    def test_full_scholarship_workflow(self):
        """Test complete scholarship enrollment workflow."""
        # Admin creates scholarship payment
        payment = CustomPayment.objects.create(
            student=self.student,
            course=self.course,
            created_by=self.admin,
            title='Full Scholarship',
            description='100% scholarship for excellent performance',
            amount=Decimal('0.00'),
            original_price=Decimal('10000.00'),
            payment_method='free',
            status='pending'
        )
        
        # Verify initial state
        self.assertEqual(payment.status, 'pending')
        self.assertIsNone(payment.enrollment)
        self.assertEqual(payment.amount, Decimal('0.00'))
        
        # Admin marks as completed
        payment.mark_as_completed()
        payment.refresh_from_db()
        
        # Verify enrollment created
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.enrollment)
        self.assertEqual(payment.enrollment.user, self.student)
        self.assertEqual(payment.enrollment.course, self.course)
        self.assertTrue(payment.enrollment.is_active)
    
    def test_partial_scholarship_workflow(self):
        """Test 50% discount enrollment workflow."""
        payment = CustomPayment.objects.create(
            student=self.student,
            course=self.course,
            created_by=self.admin,
            title='50% Discount',
            description='Half price special offer',
            amount=Decimal('5000.00'),
            original_price=Decimal('10000.00'),
            payment_method='bkash',
            status='pending'
        )
        
        # Payment collected
        payment.payment_id = 'BKASH123456'
        payment.mark_as_completed()
        payment.refresh_from_db()
        
        # Verify
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.enrollment)
        self.assertEqual(payment.amount, Decimal('5000.00'))
    
    def test_custom_payment_without_course(self):
        """Test custom payment for non-course items."""
        payment = CustomPayment.objects.create(
            student=self.student,
            created_by=self.admin,
            title='Consultation Fee',
            description='One-on-one career counseling session',
            amount=Decimal('2000.00'),
            payment_method='cash',
            status='pending'
        )
        
        # Mark as completed
        payment.mark_as_completed()
        payment.refresh_from_db()
        
        # Should not create enrollment
        self.assertEqual(payment.status, 'completed')
        self.assertIsNone(payment.enrollment)
        self.assertIsNone(payment.course)
