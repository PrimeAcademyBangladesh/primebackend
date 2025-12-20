from django.core.exceptions import ValidationError
from django.test import TestCase

from api.models.models_seo import PageSEO


class StructuredDataValidationTests(TestCase):
    def test_valid_structured_data_allowed(self):
        sd = {"@context": "https://schema.org", "@type": "WebPage", "name": "Test"}
        p = PageSEO(page_name="valid", structured_data=sd)
        # should not raise
        p.full_clean()  # calls clean()

    def test_non_dict_structured_data_rejected(self):
        p = PageSEO(page_name="bad1", structured_data="not-a-dict")
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_missing_keys_structured_data_rejected(self):
        sd = {"name": "No context/type"}
        p = PageSEO(page_name="bad2", structured_data=sd)
        with self.assertRaises(ValidationError):
            p.full_clean()
