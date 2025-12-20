"""
Tests for Cart and Wishlist functionality
"""

import uuid
from decimal import Decimal

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test.client import RequestFactory

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.models.models_auth import CustomUser
from api.models.models_cart import Cart, CartItem, Wishlist
from api.models.models_course import Category, Course
from api.models.models_pricing import CoursePrice


class CartModelTestCase(TestCase):
    """Test Cart model functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        # Create category and course
        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = Course.objects.create(
            title="Test Course",
            slug="test-course",
            category=self.category,
            short_description="Short desc",
            full_description="Full description",
            is_active=True,
        )

        # Create course pricing
        self.pricing = CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="USD")

    def test_create_user_cart(self):
        """Test creating cart for authenticated user"""
        cart = Cart.objects.create(user=self.user)

        self.assertEqual(cart.user, self.user)
        self.assertIsNone(cart.session_key)
        self.assertEqual(cart.get_item_count(), 0)
        self.assertEqual(cart.get_total(), Decimal("0.00"))

    def test_create_guest_cart(self):
        """Test creating cart for guest user"""
        cart = Cart.objects.create(session_key="test_session_123")

        self.assertIsNone(cart.user)
        self.assertEqual(cart.session_key, "test_session_123")

    def test_cart_add_item(self):
        """Test adding item to cart"""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, course=self.course)

        self.assertEqual(cart.get_item_count(), 1)
        self.assertEqual(cart_item.get_subtotal(), Decimal("99.99"))

    def test_cart_total_calculation(self):
        """Test cart total with multiple items"""
        cart = Cart.objects.create(user=self.user)

        # Create another course
        course2 = Course.objects.create(
            title="Test Course 2",
            slug="test-course-2",
            category=self.category,
            short_description="Short desc 2",
            is_active=True,
        )
        CoursePrice.objects.create(course=course2, base_price=Decimal("149.99"), currency="USD")

        CartItem.objects.create(cart=cart, course=self.course)
        CartItem.objects.create(cart=cart, course=course2)

        self.assertEqual(cart.get_item_count(), 2)
        self.assertEqual(cart.get_total(), Decimal("249.98"))

    def test_cart_clear(self):
        """Test clearing cart"""
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, course=self.course)

        self.assertEqual(cart.get_item_count(), 1)

        cart.clear()

        self.assertEqual(cart.get_item_count(), 0)

    def test_cart_item_unique_constraint(self):
        """Test that same course+batch cannot be added twice, but different batches can"""
        from datetime import date, timedelta

        from django.db import IntegrityError

        from api.models.models_course import CourseBatch

        # Create batches for the course
        batch1 = CourseBatch.objects.create(
            course=self.course,
            batch_number=1,
            batch_name="Batch 1",
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=120),
            max_students=30,
        )
        batch2 = CourseBatch.objects.create(
            course=self.course,
            batch_number=2,
            batch_name="Batch 2",
            start_date=date.today() + timedelta(days=150),
            end_date=date.today() + timedelta(days=240),
            max_students=30,
        )

        cart = Cart.objects.create(user=self.user)

        # Add course with batch1 - should work
        CartItem.objects.create(cart=cart, course=self.course, batch=batch1)

        # Add same course with batch2 - should work (different batch)
        CartItem.objects.create(cart=cart, course=self.course, batch=batch2)

        # Try to add same course+batch1 again - should raise error
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(cart=cart, course=self.course, batch=batch1)

    def test_cart_string_representation(self):
        """Test cart __str__ method"""
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(str(cart), f"Cart for {self.user.email}")

        guest_cart = Cart.objects.create(session_key="abc123def")
        self.assertIn("Guest Cart", str(guest_cart))


class WishlistModelTestCase(TestCase):
    """Test Wishlist model functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course = Course.objects.create(
            title="Test Course", slug="test-course", category=self.category, short_description="Short desc", is_active=True
        )

    def test_create_wishlist(self):
        """Test creating wishlist"""
        wishlist = Wishlist.objects.create(user=self.user)

        self.assertEqual(wishlist.user, self.user)
        self.assertEqual(wishlist.courses.count(), 0)

    def test_add_course_to_wishlist(self):
        """Test adding course to wishlist"""
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)

        self.assertEqual(wishlist.courses.count(), 1)
        self.assertIn(self.course, wishlist.courses.all())

    def test_remove_course_from_wishlist(self):
        """Test removing course from wishlist"""
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)

        self.assertEqual(wishlist.courses.count(), 1)

        wishlist.courses.remove(self.course)

        self.assertEqual(wishlist.courses.count(), 0)

    def test_wishlist_string_representation(self):
        """Test wishlist __str__ method"""
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)

        self.assertIn(self.user.email, str(wishlist))
        self.assertIn("1 items", str(wishlist))


class CartAPITestCase(APITestCase):
    """Test Cart API endpoints"""

    def setUp(self):
        """Set up test data"""
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

        self.course = Course.objects.create(
            title="Test Course", slug="test-course", category=self.category, short_description="Short desc", is_active=True
        )

        self.pricing = CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="USD")

    def test_get_cart_guest(self):
        """Test getting cart as guest user"""
        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["item_count"], 0)
        self.assertEqual(response.data["total"], "0")

    def test_get_cart_authenticated(self):
        """Test getting cart as authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["item_count"], 0)

    def test_add_to_cart_guest(self):
        """Test adding course to cart as guest"""
        response = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["cart"]["item_count"], 1)

    def test_add_to_cart_authenticated(self):
        """Test adding course to cart as authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["cart"]["item_count"], 1)

    def test_add_duplicate_to_cart(self):
        """Test adding same course twice returns 200"""
        self.client.force_authenticate(user=self.user)

        # Add first time
        response1 = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Add second time
        response2 = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIn("already in your cart", response2.data["message"])
        self.assertEqual(response2.data["cart"]["item_count"], 1)

    def test_add_invalid_course_to_cart(self):
        """Test adding non-existent course"""
        invalid_uuid = str(uuid.uuid4())
        response = self.client.post("/api/cart/add/", {"course_id": invalid_uuid}, format="json")

        # Returns 400 because serializer validates course_id
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_inactive_course_to_cart(self):
        """Test adding inactive course"""
        inactive_course = Course.objects.create(
            title="Inactive Course",
            slug="inactive-course",
            category=self.category,
            short_description="Short desc",
            is_active=False,
        )

        response = self.client.post("/api/cart/add/", {"course_id": str(inactive_course.id)}, format="json")

        # Returns 400 because serializer validates course must be active
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_from_cart(self):
        """Test removing item from cart"""
        self.client.force_authenticate(user=self.user)

        # Add course
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, course=self.course)

        # Remove course
        response = self.client.delete(f"/api/cart/remove/{cart_item.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("removed from cart", response.data["message"])
        self.assertEqual(response.data["cart"]["item_count"], 0)

    def test_remove_nonexistent_item(self):
        """Test removing non-existent item"""
        self.client.force_authenticate(user=self.user)
        invalid_uuid = uuid.uuid4()

        response = self.client.delete(f"/api/cart/remove/{invalid_uuid}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_clear_cart(self):
        """Test clearing cart"""
        self.client.force_authenticate(user=self.user)

        # Add courses
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, course=self.course)

        # Clear cart
        response = self.client.post("/api/cart/clear/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cleared", response.data["message"])
        self.assertEqual(response.data["cart"]["item_count"], 0)

    # Note: Course.batch field removed - batches are now separate model
    # Cart items no longer include batch field in course data
    # Batch selection happens during enrollment, not cart phase


class WishlistAPITestCase(APITestCase):
    """Test Wishlist API endpoints"""

    def setUp(self):
        """Set up test data"""
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

        self.course = Course.objects.create(
            title="Test Course", slug="test-course", category=self.category, short_description="Short desc", is_active=True
        )

        self.pricing = CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="USD")

    def test_get_wishlist_unauthenticated(self):
        """Test getting wishlist without authentication"""
        response = self.client.get("/api/wishlist/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_wishlist_authenticated(self):
        """Test getting wishlist as authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/wishlist/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["course_count"], 0)

    def test_add_to_wishlist(self):
        """Test adding course to wishlist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("added to wishlist", response.data["message"])
        self.assertEqual(response.data["wishlist"]["course_count"], 1)

    def test_add_to_wishlist_unauthenticated(self):
        """Test adding to wishlist without authentication"""
        response = self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_add_duplicate_to_wishlist(self):
        """Test adding same course twice to wishlist"""
        self.client.force_authenticate(user=self.user)

        # Add first time
        response1 = self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Add second time
        response2 = self.client.post("/api/wishlist/add/", {"course_id": str(self.course.id)}, format="json")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIn("already in your wishlist", response2.data["message"])
        self.assertEqual(response2.data["wishlist"]["course_count"], 1)

    def test_remove_from_wishlist(self):
        """Test removing course from wishlist"""
        self.client.force_authenticate(user=self.user)

        # Add course to wishlist
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)

        # Remove course
        response = self.client.delete(f"/api/wishlist/remove/{self.course.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("removed from wishlist", response.data["message"])
        self.assertEqual(response.data["wishlist"]["course_count"], 0)

    def test_remove_nonexistent_from_wishlist(self):
        """Test removing course not in wishlist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/wishlist/remove/{self.course.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("was not in your wishlist", response.data["message"])

    def test_move_to_cart(self):
        """Test moving course from wishlist to cart"""
        self.client.force_authenticate(user=self.user)

        # Add to wishlist
        wishlist = Wishlist.objects.create(user=self.user)
        wishlist.courses.add(self.course)

        # Move to cart
        response = self.client.post(f"/api/wishlist/move-to-cart/{self.course.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("moved to cart", response.data["message"])
        self.assertEqual(response.data["cart"]["item_count"], 1)
        self.assertEqual(response.data["wishlist"]["course_count"], 0)

    def test_move_to_cart_unauthenticated(self):
        """Test moving to cart without authentication"""
        response = self.client.post(f"/api/wishlist/move-to-cart/{self.course.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # Note: Course.batch field removed - batches are now separate model
    # Wishlist items no longer include batch field in course data
    # Batch selection happens during enrollment, not wishlist phase


class CartMergeOnLoginTestCase(APITestCase):
    """Test cart merge functionality when guest logs in"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create user
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        # Create category and courses
        self.category = Category.objects.create(name="Test Category", slug="test-category")

        self.course1 = Course.objects.create(
            title="Course 1", slug="course-1", category=self.category, short_description="Short desc", is_active=True
        )

        self.course2 = Course.objects.create(
            title="Course 2", slug="course-2", category=self.category, short_description="Short desc", is_active=True
        )

        CoursePrice.objects.create(course=self.course1, base_price=Decimal("99.99"), currency="BDT")

        CoursePrice.objects.create(course=self.course2, base_price=Decimal("149.99"), currency="BDT")

    def test_guest_cart_merged_on_login(self):
        """Test that guest cart items are merged to user cart on login (single course only)"""
        # Add items to cart as guest
        self.client.post("/api/cart/add/", {"course_id": str(self.course1.id)}, format="json")

        # Note: Due to single course restriction, only first course will be added
        # Second course add will fail with error
        response2 = self.client.post("/api/cart/add/", {"course_id": str(self.course2.id)}, format="json")

        # Second add should fail due to single course restriction
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify guest cart has only 1 item (single course restriction)
        response = self.client.get("/api/cart/")
        self.assertEqual(response.data["item_count"], 1)

        # Login
        login_response = self.client.post(
            "/api/students/login/", {"email": "test@example.com", "password": "testpass123"}, format="json"
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        # Check if cart merge info is in response
        if "data" in login_response.data:
            data = login_response.data["data"]
            # Cart merge info may be present
            if "cart_merged" in data:
                self.assertTrue(data["cart_merged"])
                # Only 1 item merged due to single course restriction
                self.assertEqual(data["cart_items_merged"], 1)

        # Get cart as authenticated user
        token = login_response.data["data"]["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        cart_response = self.client.get("/api/cart/")

        # Verify user cart now has only 1 item (single course restriction)
        self.assertEqual(cart_response.data["item_count"], 1)

    def test_no_merge_when_no_guest_cart(self):
        """Test login without guest cart works normally"""
        # Login without adding anything to cart
        login_response = self.client.post(
            "/api/students/login/", {"email": "test@example.com", "password": "testpass123"}, format="json"
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        # Cart merge info should not be present
        if "data" in login_response.data:
            data = login_response.data["data"]
            self.assertNotIn("cart_merged", data)


class CartWithDiscountTestCase(APITestCase):
    """Test cart calculations with discounts"""

    def setUp(self):
        """Set up test data with discount"""
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

        self.course = Course.objects.create(
            title="Test Course", slug="test-course", category=self.category, short_description="Short desc", is_active=True
        )

        # Create pricing with discount
        from datetime import timedelta

        from django.utils import timezone

        self.pricing = CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal("99.99"),
            discount_percentage=20,
            discount_start_date=timezone.now() - timedelta(days=1),
            discount_end_date=timezone.now() + timedelta(days=30),
            currency="USD",
        )

    def test_cart_total_with_discount(self):
        """Test cart total calculation with discount"""
        self.client.force_authenticate(user=self.user)

        # Add course with discount
        response = self.client.post("/api/cart/add/", {"course_id": str(self.course.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check discounted price (99.99 - 20% = 79.992, rounded to 79.99 in display)
        cart_data = response.data["cart"]
        # The calculation may have more decimal places, so check it's within range
        total = float(cart_data["total"])
        self.assertAlmostEqual(total, 79.99, places=1)

        # Check item details
        item = cart_data["items"][0]
        self.assertEqual(item["course"]["price"], "99.99")
        # Discount calculation may have extra decimal places
        discounted = float(item["course"]["discounted_price"])
        self.assertAlmostEqual(discounted, 79.99, places=1)
        self.assertTrue(item["course"]["has_discount"])
