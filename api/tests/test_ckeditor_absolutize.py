import re

from django.conf import settings
from django.test import SimpleTestCase

from api.utils.ckeditor_paths import absolutize_media_urls


class TestAbsolutizeHelper(SimpleTestCase):
    def test_absolutizes_media_url_without_request(self):
        html = '<p><img src="/media/uploads/ckeditor/example.png" alt="x"></p>'
        out = absolutize_media_urls(html, request=None)
        m = re.search(r'src=["\'](.*?)["\']', out)
        self.assertIsNotNone(m, "Expected a src attribute in transformed HTML")
        expected = settings.SITE_BASE_URL.rstrip("/") + "/media/uploads/ckeditor/example.png"
        self.assertEqual(m.group(1), expected)

    def test_leaves_already_absolute_url_unchanged(self):
        html = '<p><img src="https://cdn.example.com/media/x.png" /></p>'
        out = absolutize_media_urls(html, request=None)
        m = re.search(r'src=["\'](.*?)["\']', out)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "https://cdn.example.com/media/x.png")
