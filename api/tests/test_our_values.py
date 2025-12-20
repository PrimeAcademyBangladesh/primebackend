from django.core.exceptions import ValidationError
from django.test import TestCase

from rest_framework.test import APIClient

from api.models.models_our_values import ValueTab, ValueTabContent, ValueTabSection
from api.models.models_service import PageService
from api.serializers.serializers_our_values import (
    ValueTabContentCreateUpdateSerializer,
    ValueTabCreateUpdateSerializer,
    ValueTabSectionCreateUpdateSerializer,
)


class OurValuesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # create a page to attach sections to
        self.page = PageService.objects.create(name="About", slug="about", is_active=True)

    def test_value_tab_content_model_validation_requires_video_fields(self):
        # create section and tab
        section = ValueTabSection.objects.create(title="Our Values", slug="our-values", page=self.page)
        tab = ValueTab.objects.create(value_section=section, title="Be The Expert", slug="be-the-expert")

        # Create a ValueTabContent instance with media_type=video but missing thumbnail
        content = ValueTabContent(
            value_tab=tab,
            media_type="video",
            video_provider="youtube",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="Video Content",
            description="Desc",
        )

        with self.assertRaises(ValidationError):
            content.full_clean()

    def test_value_tab_content_serializer_rejects_missing_video_provider(self):
        # create section and tab
        section = ValueTabSection.objects.create(title="Our Values 2", slug="our-values-2", page=self.page)
        tab = ValueTab.objects.create(value_section=section, title="Be The Future", slug="be-the-future")

        payload = {
            "value_tab": str(tab.pk),
            "media_type": "video",
            "video_url": "https://vimeo.com/12345678",
            "video_thumbnail": None,
            "title": "Video",
            "description": "Video description",
        }

        serializer = ValueTabContentCreateUpdateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        # The serializer may attach the provider-related error to 'video_url'
        # with message 'Video provider must be specified.' depending on validation order
        self.assertTrue("video_provider" in serializer.errors or "video_url" in serializer.errors)

    def test_by_page_view_returns_sections(self):
        # create sections/tabs/contents
        section = ValueTabSection.objects.create(title="Our Values 3", slug="our-values-3", page=self.page, is_active=True)
        tab = ValueTab.objects.create(value_section=section, title="Be The Customer", slug="be-the-customer", is_active=True)
        # create a small in-memory image for the ImageField
        from django.core.files.uploadedfile import SimpleUploadedFile

        img = SimpleUploadedFile("test.jpg", b"\x47\x49\x46\x38\x39\x61", content_type="image/jpeg")
        content = ValueTabContent.objects.create(
            value_tab=tab, media_type="image", image=img, title="Image Content", description="Some description", is_active=True
        )

        url = f"/api/our-values/sections/by-page/{self.page.slug}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("data"), list)
        # Ensure at least one section returned
        self.assertGreaterEqual(len(data.get("data")), 1)
