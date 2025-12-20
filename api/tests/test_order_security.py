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
        """Create test data."""
        # Create users
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

        # Create course
        category = Category.objects.create(name="Security Test Category", slug="security-test-category")

        self.course = Course.objects.create(
            title="Security Test Course",
            slug="security-test-course",
            category=category,
            short_description="Test course for security",
            status="published",
            is_active=True,
        )

        CoursePrice.objects.create(course=self.course, base_price=Decimal("1000.00"), currency="BDT", is_active=True)

        # Create orders
        self.student_order = Order.objects.create(
            user=self.student,
            subtotal=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            currency="BDT",
            billing_email=self.student.email,
            billing_name=f"{self.student.first_name} {self.student.last_name}",
            status="pending",
        )

        OrderItem.objects.create(order=self.student_order, course=self.course, price=Decimal("1000.00"), currency="BDT")

        self.student2_order = Order.objects.create(
            user=self.student2,
            subtotal=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            currency="BDT",
            billing_email=self.student2.email,
            billing_name=f"{self.student2.first_name} {self.student2.last_name}",
            status="pending",
        )

        OrderItem.objects.create(order=self.student2_order, course=self.course, price=Decimal("1000.00"), currency="BDT")

        # Create enrollments
        self.student_enrollment = Enrollment.objects.create(
            user=self.student, course=self.course, order=self.student_order, progress_percentage=Decimal("50.00")
        )

        self.student2_enrollment = Enrollment.objects.create(
            user=self.student2, course=self.course, order=self.student2_order, progress_percentage=Decimal("50.00")
        )

        self.factory = APIRequestFactory()

    # Role-Based Permission Tests

    def test_is_student_permission_allows_student(self):
        """IsStudent permission should allow student role."""
        request = self.factory.get("/")
        request.user = self.student

        permission = IsStudent()
        self.assertTrue(permission.has_permission(request, None))

    def test_is_student_permission_denies_staff(self):
        """IsStudent permission should deny staff role."""
        request = self.factory.get("/")
        request.user = self.staff

        permission = IsStudent()
        self.assertFalse(permission.has_permission(request, None))

    def test_is_staff_permission_denies_student(self):
        """IsStaff permission should deny student role."""
        request = self.factory.get("/")
        request.user = self.student

        permission = IsStaff()
        self.assertFalse(permission.has_permission(request, None))

    def test_is_staff_permission_allows_staff(self):
        """IsStaff permission should allow staff role."""
        request = self.factory.get("/")
        request.user = self.staff

        permission = IsStaff()
        self.assertTrue(permission.has_permission(request, None))

    def test_is_staff_permission_allows_admin(self):
        """IsStaff permission should allow admin role."""
        request = self.factory.get("/")
        request.user = self.admin

        permission = IsStaff()
        self.assertTrue(permission.has_permission(request, None))

    # Order Queryset Filtering Tests

    def test_student_sees_only_own_orders(self):
        """Students should only see their own orders in queryset."""
        request = self.factory.get("/api/orders/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first(), self.student_order)

    def test_student_cannot_see_other_student_orders(self):
        """Students should not see other students' orders in queryset."""
        request = self.factory.get("/api/orders/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        self.assertFalse(queryset.filter(user=self.student2).exists())

    def test_staff_sees_all_orders(self):
        """Staff should see all orders in queryset."""
        request = self.factory.get("/api/orders/")
        request.user = self.staff

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        self.assertEqual(queryset.count(), Order.objects.count())

    # Enrollment Queryset Filtering Tests

    def test_student_sees_only_own_enrollments(self):
        """Students should only see their own enrollments in queryset."""
        request = self.factory.get("/api/enrollments/")
        request.user = self.student

        viewset = EnrollmentViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first(), self.student_enrollment)

    def test_staff_sees_all_enrollments(self):
        """Staff should see all enrollments in queryset."""
        request = self.factory.get("/api/enrollments/")
        request.user = self.staff

        viewset = EnrollmentViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        self.assertEqual(queryset.count(), Enrollment.objects.count())

    # Order Object-Level Permission Tests

    def test_student_cannot_access_other_student_order(self):
        """Students should not be able to access other students' orders."""
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.student2

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"
        viewset.kwargs = {"pk": self.student_order.id}

        with self.assertRaises(PermissionDenied):
            viewset.check_object_permissions(request, self.student_order)

    def test_student_can_access_own_order(self):
        """Students should be able to access their own orders."""
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"
        viewset.kwargs = {"pk": self.student_order.id}

        # Should not raise PermissionDenied
        try:
            viewset.check_object_permissions(request, self.student_order)
        except PermissionDenied:
            self.fail("Student should be able to access their own order")

    def test_staff_can_access_any_order(self):
        """Staff should be able to access any order."""
        request = self.factory.get(f"/api/orders/{self.student_order.id}/")
        request.user = self.staff

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "retrieve"
        viewset.kwargs = {"pk": self.student_order.id}

        # Should not raise PermissionDenied
        try:
            viewset.check_object_permissions(request, self.student_order)
        except PermissionDenied:
            self.fail("Staff should be able to access any order")

    # Order Action Permission Tests

    def test_student_cannot_cancel_orders(self):
        """Students should not have permission to cancel orders."""
        request = self.factory.post(f"/api/orders/{self.student_order.id}/cancel_order/")
        request.user = self.student

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "cancel_order"

        permissions = viewset.get_permissions()
        has_permission = any(perm.has_permission(request, viewset) for perm in permissions)

        self.assertFalse(has_permission)

    def test_staff_cannot_cancel_orders(self):
        """Staff should NOT have permission to cancel orders - admin only."""
        request = self.factory.post(f"/api/orders/{self.student_order.id}/cancel_order/")
        request.user = self.staff

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "cancel_order"

        permissions = viewset.get_permissions()
        has_permission = any(perm.has_permission(request, viewset) for perm in permissions)

        self.assertFalse(has_permission)

    def test_admin_can_cancel_orders(self):
        """Admin should have permission to cancel orders."""
        request = self.factory.post(f"/api/orders/{self.student_order.id}/cancel_order/")
        request.user = self.admin

        viewset = OrderViewSet()
        viewset.request = request
        viewset.action = "cancel_order"

        permissions = viewset.get_permissions()
        has_permission = any(perm.has_permission(request, viewset) for perm in permissions)

        self.assertTrue(has_permission)

    # Enrollment Update Permission Tests

    def test_student_cannot_update_other_enrollment(self):
        """Students should not be able to update other students' enrollments."""
        request = self.factory.patch(f"/api/enrollments/{self.student_enrollment.id}/")
        request.user = self.student2

        viewset = EnrollmentViewSet()
        viewset.request = request
        viewset.action = "update"
        viewset.kwargs = {"pk": self.student_enrollment.id}
        viewset.get_object = lambda: self.student_enrollment

        class MockSerializer:
            validated_data = {"progress_percentage": Decimal("75.00")}

            def save(self):
                pass

        with self.assertRaises(PermissionDenied):
            viewset.perform_update(MockSerializer())

    def test_student_can_update_own_enrollment(self):
        """Students should be able to update their own enrollments."""
        request = self.factory.patch(f"/api/enrollments/{self.student_enrollment.id}/")
        request.user = self.student

        viewset = EnrollmentViewSet()
        viewset.request = request
        viewset.action = "update"
        viewset.kwargs = {"pk": self.student_enrollment.id}
        viewset.get_object = lambda: self.student_enrollment

        class MockSerializer:
            validated_data = {"progress_percentage": Decimal("75.00")}

            def save(self):
                pass

        # Should not raise PermissionDenied
        try:
            viewset.perform_update(MockSerializer())
        except PermissionDenied:
            self.fail("Student should be able to update their own enrollment")

    def test_staff_can_update_any_enrollment(self):
        """Staff should be able to update any enrollment."""
        request = self.factory.patch(f"/api/enrollments/{self.student_enrollment.id}/")
        request.user = self.staff

        viewset = EnrollmentViewSet()
        viewset.request = request
        viewset.action = "update"
        viewset.kwargs = {"pk": self.student_enrollment.id}
        viewset.get_object = lambda: self.student_enrollment

        class MockSerializer:
            validated_data = {"progress_percentage": Decimal("75.00")}

            def save(self):
                pass

        # Should not raise PermissionDenied
        try:
            viewset.perform_update(MockSerializer())
        except PermissionDenied:
            self.fail("Staff should be able to update any enrollment")
