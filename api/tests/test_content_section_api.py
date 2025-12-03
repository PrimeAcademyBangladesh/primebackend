from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.models.models_service import ContentSection, PageService


class ContentSectionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_by_page_type_and_position_happy_path(self):
        # Create page and content sections
        page = PageService.objects.create(name='Services', slug='services', is_active=True)

        image_file = SimpleUploadedFile('test.png', b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82', content_type='image/png')

        cs1 = ContentSection.objects.create(
            page=page,
            section_type='info',
            position_choice='top',
            title='Top Info',
            content='Top content',
            order=1,
            is_active=True,
            image=image_file,
        )

        # other sections that should not be returned
        ContentSection.objects.create(
            page=page,
            section_type='info',
            position_choice='middle',
            title='Middle Info',
            content='Middle content',
            order=2,
            is_active=True,
            image=image_file,
        )

        ContentSection.objects.create(
            page=page,
            section_type='icon',
            position_choice='top',
            title='Top Icon',
            content='Icon content',
            order=3,
            is_active=True,
            image=image_file,
        )

        # Call the new endpoint
        resp = self.client.get(f'/api/content-sections/by-page/{page.slug}/info/top/', format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get('success'))

        data = resp.data.get('data', {})
        self.assertEqual(data.get('section_type'), 'info')
        self.assertEqual(data.get('position'), 'top')

        sections = data.get('sections', [])
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].get('id'), str(cs1.id))

    def test_invalid_section_type_returns_400(self):
        page = PageService.objects.create(name='Services2', slug='services-2', is_active=True)
        resp = self.client.get(f'/api/content-sections/by-page/{page.slug}/badtype/top/', format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data.get('success'))

    def test_invalid_position_returns_400(self):
        page = PageService.objects.create(name='Services3', slug='services-3', is_active=True)
        resp = self.client.get(f'/api/content-sections/by-page/{page.slug}/info/left/', format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data.get('success'))
