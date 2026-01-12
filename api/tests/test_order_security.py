"""
Security tests for Order and Enrollment permissions.
Tests role-based access control and object-level permissions.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from api.models.models_course import Category, Course
from api.models.models_order import Enrollment, Order, OrderItem
from api.models.models_pricing import CoursePrice
from api.permissions import IsStaff, IsStudent
from api.views.views_order import EnrollmentViewSet, OrderViewSet

User = get_user_model()


class OrderSecurityTestCase(TestCase):
    """Test security features for Order and Enrollment models."""

    def setUp(self):
        # Users
        self.student = User.objects.create_user(
            email="student_security@example.com",
            password="testpass123",
            role="student",
            first_name="Test",
            last_name="Student",
            phone="01700000001",
        )

        self.student2 = User.objects.create_user(
            email="student2_security@example.com",
            password="testpass123",
            role="student",
            first_name="Test2",
            last_name="Student2",
            phone="01700000002",
        )

        self.staff = User.objects.create_user(
            email="staff_security@example.com",
            password="testpass123",
            role="staff",
            first_name="Test",
            last_name="Staff",
            phone="01700000003",
        )

        self.admin = User.objects.create_user(
            email="admin_security@example.com",
            password="testpass123",
            role="admin",
            first_name="Test",
            last_name="Admin",
            phone="01700000004",
        )

        # Course (course_prefix <= 8 chars)
        category = Category.objects.create(
            name="Security Test Category",
            slug="security-test-category",
        )

        self.course = Course.objects.create(
            title="Security Test Course",
            slug="security-test-course",
            course_prefix="SEC0001",
            category=category,
            short_description="Test course for security",
            status="published",
            is_active=True,
        )

        CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal("1000.00"),
            currency="BDT",
            is_active=True,
        )

        # Orders
        self.student_order = Order.objects.create(
            user=self.student,
            subtotal=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            currency="BDT",
            billing_email=self.student.email,
            billing_name=f"{self.student.first_name} {self.student.last_name}",
            status="pending",
        )

        OrderItem.objects.create(
            order=self.student_order,
            course=self.course,
            price=Decimal("1000.00"),
            currency="BDT",
        )

        self.student2_order = Order.objects.create(
            user=self.student2,
            subtotal=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            currency="BDT",
            billing_email=self.student2.email,
            billing_name=f"{self.student2.first_name} {self.student2.last_name}",
            status="pending",
        )

        OrderItem.objects.create(
            order=self.student2_order,
            course=self.course,
            price=Decimal("1000.00"),
            currency="BDT",
        )

        # Enrollments
        self.student_enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            order=self.student_order,
            progress_percentage=Decimal("50.00"),
        )

        self.student2_enrollment = Enrollment.objects.create(
            user=self.student2,
            course=self.course,
            order=self.student2_order,
            progress_percentage=Decimal("50.00"),
        )

        self.factory = APIRequestFactory()

    # ---------------------------------------------------
    # Role-Based Permission Tests
    # ---------------------------------------------------

    def test_is_student_permission_allows_student(self):
        request = self.factory.get("/")
        request.user = self.student
        self.assertTrue(IsStudent().has_permission(request, None))

    def test_is_student_permission_denies_staff(self):
        request = self.factory.get("/")
        request.user = self.staff
        self.assertFalse(IsStudent().has_permission(request, None))

    def test_is_staff_permission_denies_student(self):
        request = self.factory.get("/")
        request.user = self.student
        self.assertFalse(IsStaff().has_permission(request, None))

    def test_is_staff_permission_allows_staff(self):
        request = self.factory.get("/")
        request.user = self.staff
        self.assertTrue(IsStaff().has_permission(request, None))

    def test_is_staff_permission_allows_admin(self):
        request = self.factory.get("/")
        request.user = self.admin
        self.assertTrue(IsStaff().has_permission(request, None))

    # ---------------------------------------------------
    # Queryset Filtering Tests
    # ---------------------------------------------------

    def test_student_sees_only_own_orders(self):
        request = self.factory.get("/api/orders/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "list"

        qs = viewset.get_queryset()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.student_order)

    def test_staff_sees_all_orders(self):
        request = self.factory.get("/api/orders/")
        request.user = self.staff

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "list"

        self.assertEqual(viewset.get_queryset().count(), Order.objects.count())

    # ---------------------------------------------------
    # Object-Level Permission Tests
    # ---------------------------------------------------

    def test_student_cannot_access_other_student_order(self):
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.student2

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"

        with self.assertRaises(PermissionDenied):
            viewset.check_object_permissions(request, self.student_order)

    def test_student_can_access_own_order(self):
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"

        viewset.check_object_permissions(request, self.student_order)

    def test_staff_can_access_any_order(self):
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.staff

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"

        viewset.check_object_permissions(request, self.student_order)

    # ---------------------------------------------------
    # Cancel Order Permission Tests
    # ---------------------------------------------------

    def test_admin_can_cancel_orders(self):
        request = self.factory.post(f"/api/orders/{self.student_order.id}/cancel_order/")
        request.user = self.admin

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "cancel_order"

        permissions = viewset.get_permissions()
        self.assertTrue(any(p.has_permission(request, viewset) for p in permissions))
