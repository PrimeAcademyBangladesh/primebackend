from django.test import TestCase

from api.models.models_seo import PageSEO


class PageSEOMetaGenerationTests(TestCase):
    def test_unsaved_instance_generates_structured_data(self):
        p = PageSEO(page_name='landing', meta_title='Landing', meta_description='Welcome')
        meta = p.get_seo_meta()
        # structured_data should be synthesized even though instance not saved
        self.assertIn('structured_data', meta)
        sd = meta['structured_data']
        self.assertIsInstance(sd, dict)
        self.assertIn('@context', sd)
        self.assertIn('@type', sd)

    def test_saved_instance_has_structured_data_and_cached(self):
        p = PageSEO(page_name='saved-page', meta_title='Saved', meta_description='Saved desc')
        # before save structured_data may be None on model field, but get_seo_meta returns synthesized
        meta_before = p.get_seo_meta()
        self.assertIsInstance(meta_before.get('structured_data'), dict)

        p.save()
        meta_after = p.get_seo_meta()
        self.assertIsInstance(meta_after.get('structured_data'), dict)
        # basic sanity checks
        sd = meta_after['structured_data']
        self.assertEqual(sd.get('@type'), 'WebPage')
        self.assertIn('publisher', sd)
