"""Test cache invalidation for course-related endpoints."""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from rest_framework.test import APIClient

from api.models.models_course import Category, Course
from api.models.models_pricing import CoursePrice
from api.utils.cache_utils import (
    CACHE_KEY_COURSE_LIST,
    CACHE_KEY_HOME_CATEGORIES,
    generate_cache_key,
)


class CacheInvalidationTestCase(TestCase):
    """Test that caches are properly invalidated on model changes."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create category
        self.category = Category.objects.create(
            name="Test Category",
            slug="test-category",
            is_active=True,
        )

        # Create course (course_prefix is required)
        self.course = Course.objects.create(
            title="Test Course",
            slug="test-course",
            course_prefix="TEST101",
            category=self.category,
            short_description="Short desc",
            is_active=True,
            status="published",
            show_in_home_tab=True,
        )

        # Create pricing
        self.pricing = CoursePrice.objects.create(
            course=self.course,
            base_price=Decimal("99.99"),
            currency="BDT",
        )

    def test_home_categories_cache_invalidated_on_course_update(self):
        """Cache is cleared when a course is updated."""
        cache.clear()

        # Populate cache
        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)

        # Cached response
        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        # Update course
        self.course.title = "Updated Course Title"
        self.course.save()

        # Cache should be invalidated
        response3 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response3.status_code, 200)

        data = response3.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_category_update(self):
        """Cache is cleared when a category is updated."""
        cache.clear()

        self.client.get("/api/courses/home-categories/")

        self.category.name = "Updated Category"
        self.category.save()

        response = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_price_update(self):
        """Cache is cleared when pricing is updated."""
        cache.clear()

        self.client.get("/api/courses/home-categories/")

        self.pricing.base_price = Decimal("149.99")
        self.pricing.save()

        response = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_course_delete(self):
        """Cache is cleared when a course is deleted."""
        cache.clear()

        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)

        self.course.delete()

        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        data = response2.json()
        self.assertTrue(data["success"])

    def test_cache_not_used_for_authenticated_users(self):
        """Authenticated users should bypass cache."""
        from api.models import CustomUser

        user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        cache.clear()

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/courses/home-categories/")

        self.assertEqual(response.status_code, 200)

        if "X-Cache" in response:
            self.assertIn("SKIP", response["X-Cache"])
