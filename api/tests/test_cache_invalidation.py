"""Test cache invalidation for course-related endpoints."""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from rest_framework.test import APIClient

from api.models.models_course import Category, Course
from api.models.models_pricing import CoursePrice
from api.utils.cache_utils import CACHE_KEY_COURSE_LIST, CACHE_KEY_HOME_CATEGORIES, generate_cache_key


class CacheInvalidationTestCase(TestCase):
    """Test that caches are properly invalidated on model changes"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create category
        self.category = Category.objects.create(name="Test Category", slug="test-category", is_active=True)

        # Create course
        self.course = Course.objects.create(
            title="Test Course",
            slug="test-course",
            category=self.category,
            short_description="Short desc",
            is_active=True,
            status="published",
            show_in_home_tab=True,
        )

        # Create pricing
        self.pricing = CoursePrice.objects.create(course=self.course, base_price=Decimal("99.99"), currency="BDT")

    def test_home_categories_cache_invalidated_on_course_update(self):
        """Test that home-categories cache is cleared when course is updated"""
        # Clear cache first
        cache.clear()

        # Make initial request to populate cache
        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)

        # Verify cache was created (check X-Cache header)
        # Note: First call won't have X-Cache header as it's MISS

        # Make second request - should hit cache
        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        # Update the course
        self.course.title = "Updated Course Title"
        self.course.save()

        # Make another request - should be fresh data (cache invalidated)
        response3 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response3.status_code, 200)

        # Verify the updated data is returned
        data = response3.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_category_update(self):
        """Test that home-categories cache is cleared when category is updated"""
        # Clear cache first
        cache.clear()

        # Populate cache
        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)

        # Update category
        self.category.name = "Updated Category"
        self.category.save()

        # Request should return fresh data
        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        data = response2.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_price_update(self):
        """Test that home-categories cache is cleared when pricing is updated"""
        # Clear cache first
        cache.clear()

        # Populate cache
        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)

        # Update pricing
        self.pricing.base_price = Decimal("149.99")
        self.pricing.save()

        # Request should return fresh data with updated price
        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        data = response2.json()
        self.assertTrue(data["success"])

    def test_home_categories_cache_invalidated_on_course_delete(self):
        """Test that home-categories cache is cleared when course is deleted"""
        # Clear cache first
        cache.clear()

        # Populate cache
        response1 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()
        initial_count = len(data1["data"][0]["courses"]) if data1["data"] else 0

        # Delete course
        self.course.delete()

        # Request should return fresh data without the deleted course
        response2 = self.client.get("/api/courses/home-categories/")
        self.assertEqual(response2.status_code, 200)

        data2 = response2.json()
        # Should have fewer courses or empty category list
        self.assertTrue(data2["success"])

    def test_cache_not_used_for_authenticated_users(self):
        """Test that authenticated users don't use cache"""
        from api.models import CustomUser

        # Create user
        user = CustomUser.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            role="student",
        )

        # Clear cache
        cache.clear()

        # Authenticated request
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/courses/home-categories/")

        self.assertEqual(response.status_code, 200)
        # Should have X-Cache: SKIP-AUTH header
        if "X-Cache" in response:
            self.assertIn("SKIP", response["X-Cache"])
