from django.test import TestCase

from api.models.models_blog import Blog, BlogCategory


class BlogStructuredDataSavedTests(TestCase):
    def test_structured_data_saved_on_save_when_missing(self):
        cat = BlogCategory.objects.create(name="News2")
        b = Blog.objects.create(category=cat, title="Saved Blog", excerpt="Saved summary", status="published")
        # structured_data field should be populated on save
        self.assertIsNotNone(b.structured_data)
        self.assertIsInstance(b.structured_data, dict)
        self.assertEqual(b.structured_data.get("@type"), "BlogPosting")
