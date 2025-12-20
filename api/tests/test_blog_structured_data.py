from django.conf import settings
from django.test import TestCase

from api.models.models_blog import Blog, BlogCategory


class BlogStructuredDataTests(TestCase):
    def test_blog_structured_data_contains_expected_keys(self):
        cat = BlogCategory.objects.create(name="News")
        b = Blog.objects.create(category=cat, title="Test Blog", excerpt="Summary here", status="published")
        sd = b.get_structured_data()
        self.assertIsInstance(sd, dict)
        self.assertEqual(sd.get("@type"), "BlogPosting")
        self.assertEqual(sd.get("headline"), "Test Blog")
        self.assertIn("publisher", sd)
        # url should start with FRONTEND_URL
        self.assertTrue(sd.get("url").startswith(settings.FRONTEND_URL))
