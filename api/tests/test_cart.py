"""
Tests for Cart and Wishlist functionality
"""

import uuid
from decimal import Decimal

from django.test import TestCase
from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import RequestFactory

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.models.models_auth import CustomUser
from api.models.models_cart import Cart, CartItem, Wishlist
from api.models.models_course import Category, Course
from api.models.models_pricing import CoursePrice


def create_course(*, category, title, slug, prefix, is_active=True, full_description=None):
    """Helper to create valid Course objects for tests."""
    return Course.objects.create(
        title=title,
        slug=slug,
        course_prefix=prefix,
        category=category,
        short_description="Short desc",
        full_description=full_description or "",
        is_active=is_active,
    )


class CartModelTestCase(TestCase):
    """Test Cart model functionality"""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = create_course(
            category=self.category,
            title="Test Course",
            slug="test-course",
            prefix="CART-001",
            full_description="Full description",
        )

        self.pricing = CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal("99.99"),
            currency="USD",
        )

    def test_create_user_cart(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.get_item_count(), 0)
        self.assertEqual(cart.get_total(), Decimal("0.00"))

    def test_create_guest_cart(self):
        cart = Cart.objects.create(session_key="guest-session")
        self.assertIsNone(cart.user)

    def test_cart_add_item(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, course=self.course)
        self.assertEqual(cart.get_item_count(), 1)

    def test_cart_total_calculation(self):
        cart = Cart.objects.create(user=self.user)

        course2 = create_course(
            category=self.category,
            title="Test Course 2",
            slug="test-course-2",
            prefix="CART-002",
        )

        CoursePrice.objects.create(course=course2, base_price=Decimal("149.99"), currency="USD")

        CartItem.objects.create(cart=cart, course=self.course)
        CartItem.objects.create(cart=cart, course=course2)

        self.assertEqual(cart.get_total(), Decimal("249.98"))

    def test_cart_clear(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, course=self.course)
        cart.clear()
        self.assertEqual(cart.get_item_count(), 0)


class WishlistModelTestCase(TestCase):
    """Test Wishlist model functionality"""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = create_course(
            category=self.category,
            title="Wishlist Course",
            slug="wishlist-course",
            prefix="WISH-001",
        )

    def test_add_remove_wishlist(self):
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)
        self.assertEqual(wishlist.courses.count(), 1)
        wishlist.courses.remove(self.course)
        self.assertEqual(wishlist.courses.count(), 0)


class CartAPITestCase(APITestCase):
    """Test Cart API endpoints"""

    def setUp(self):
        self.client = APIClient()

        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = create_course(
            category=self.category,
            title="API Course",
            slug="api-course",
            prefix="API-001",
        )

        CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="USD")

    def test_add_duplicate_to_cart(self):
        self.client.force_authenticate(user=self.user)

        r1 = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["cart"]["item_count"], 1)


class WishlistAPITestCase(APITestCase):
    """Test Wishlist API endpoints"""

    def setUp(self):
        self.client = APIClient()

        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = create_course(
            category=self.category,
            title="Wishlist API Course",
            slug="wishlist-api-course",
            prefix="WAPI-001",
        )

        CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="USD")

    def test_add_duplicate_to_wishlist(self):
        self.client.force_authenticate(user=self.user)

        self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")
        response = self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["wishlist"]["course_count"], 1)


class CartWithDiscountTestCase(APITestCase):
    """Test cart calculations with discounts"""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.client = APIClient()

        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = create_course(
            category=self.category,
            title="Discount Course",
            slug="discount-course",
            prefix="DISC-001",
        )

        CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal("99.99"),
            discount_percentage=20,
            discount_start_date=timezone.now() - timedelta(days=1),
            discount_end_date=timezone.now() + timedelta(days=30),
            currency="USD",
        )

    def test_cart_total_with_discount(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        total = float(response.data["cart"]["total"])
        self.assertAlmostEqual(total, 79.99, places=1)
