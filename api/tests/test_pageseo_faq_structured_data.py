from django.test import TestCase

from api.models.models_faq import FAQ, FAQItem
from api.models.models_seo import PageSEO


class PageSEOFaqTests(TestCase):
    def test_pageseo_includes_faq_main_entity_when_matching(self):
        # Create FAQItem that corresponds to page_name 'help'
        item = FAQItem.objects.create(title='General', faq_nav='help')
        faq1 = FAQ.objects.create(item=item, question='<p>Q1?</p>', answer='<p>A1</p>')
        faq2 = FAQ.objects.create(item=item, question='Q2', answer='A2')

        page = PageSEO(page_name='help', meta_title='Help', meta_description='Help page')
        sd = page._generate_base_structured_data()
        # Ensure mainEntity FAQPage is present
        self.assertIn('mainEntity', sd)
        faqpage = sd['mainEntity']
        self.assertEqual(faqpage.get('@type'), 'FAQPage')
        self.assertIn('mainEntity', faqpage)
        questions = faqpage['mainEntity']
        self.assertTrue(any(q.get('name').startswith('Q1') or q.get('name').startswith('Q2') for q in questions))
