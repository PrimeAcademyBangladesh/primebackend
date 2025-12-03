from django.conf import settings
from django.test import TestCase

from api.models.models_seo import PageSEO


class CanonicalURLNormalizationTests(TestCase):
    def test_relative_path_normalizes(self):
        p = PageSEO(page_name='r', canonical_url='contact')
        p.clean()
        expected = settings.FRONTEND_URL.rstrip('/') + '/contact'
        self.assertEqual(p.canonical_url, expected)

    def test_leading_slash_normalizes(self):
        p = PageSEO(page_name='s', canonical_url='/pricing')
        p.clean()
        expected = settings.FRONTEND_URL.rstrip('/') + '/pricing'
        self.assertEqual(p.canonical_url, expected)

    def test_absolute_url_unchanged(self):
        p = PageSEO(page_name='a', canonical_url='https://example.com/page')
        p.clean()
        self.assertEqual(p.canonical_url, 'https://example.com/page')
