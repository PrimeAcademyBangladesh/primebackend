from django.conf import settings
from django.test import TestCase

from api.models.models_seo import PageSEO


class PageSEOAboutTests(TestCase):
    def test_about_page_uses_aboutpage_and_includes_org(self):
        p = PageSEO(page_name='about', meta_title='About Prime', meta_description='About us')
        sd = p._generate_base_structured_data()
        self.assertEqual(sd.get('@type'), 'AboutPage')
        self.assertIn('mainEntity', sd)
        org = sd['mainEntity']
        self.assertEqual(org.get('@type'), 'Organization')
        # logo should be present from SEO_CONFIG
        self.assertIn('logo', org)
        self.assertIn('url', org)
