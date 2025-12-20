from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from PIL import Image
from rest_framework.test import APITestCase

from api.models.models_auth import CustomUser
from api.models.models_service import ContentSection, PageService


class ContentSectionAdminTests(APITestCase):
    def setUp(self):
        # create admin user
        self.admin = CustomUser.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            role=CustomUser.Role.ADMIN,
            is_active=True,
            is_enabled=True,
            first_name="Admin",
            last_name="User",
            phone="+8801000000001",
        )
        # create non-admin user
        self.user = CustomUser.objects.create_user(
            email="user@example.com",
            password="userpass",
            role=CustomUser.Role.STUDENT,
            is_active=True,
            is_enabled=True,
            first_name="Normal",
            last_name="User",
            phone="+8801000000002",
        )
        self.page = PageService.objects.create(name="Services", slug="services", is_active=True)
        self.url_list = reverse("contentsection-list")

    def test_admin_can_create_update_delete_content_section(self):
        self.client.force_authenticate(user=self.admin)
        # generate a small valid PNG in-memory
        buf = BytesIO()
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
        img.save(buf, format="PNG")
        buf.seek(0)
        image_file = SimpleUploadedFile("test.png", buf.read(), content_type="image/png")

        payload = {
            "page": self.page.name,
            "section_type": "info",
            "position_choice": "top",
            "media_type": "image",
            "title": "Admin Created",
            "content": "Some content",
            "order": 1,
            "is_active": True,
            "image": image_file,
        }
        # create
        resp = self.client.post(self.url_list, payload, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data.get("success"))
        data = resp.data.get("data")
        created_id = data.get("id")

        # update
        url_detail = reverse("contentsection-detail", kwargs={"pk": created_id})
        resp2 = self.client.patch(url_detail, {"title": "Updated Title"}, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.data.get("success"))
        self.assertEqual(resp2.data.get("data").get("title"), "Updated Title")

        # delete
        resp3 = self.client.delete(url_detail)
        self.assertEqual(resp3.status_code, 204)
        self.assertTrue(resp3.data.get("success"))

    def test_non_admin_cannot_create(self):
        self.client.force_authenticate(user=self.user)
        # generate a small valid JPEG
        buf2 = BytesIO()
        img2 = Image.new("RGB", (8, 8), (0, 255, 0))
        img2.save(buf2, format="JPEG")
        buf2.seek(0)
        image_file = SimpleUploadedFile("test.jpg", buf2.read(), content_type="image/jpeg")
        payload = {
            "page": self.page.name,
            "section_type": "info",
            "position_choice": "top",
            "media_type": "image",
            "title": "User Created",
            "content": "Some content",
            "order": 1,
            "is_active": True,
            "image": image_file,
        }
        resp = self.client.post(self.url_list, payload, format="multipart")
        # Should be forbidden (403)
        self.assertIn(resp.status_code, (403, 401))

    def test_list_is_public(self):
        # create a section (attach a small valid PNG so model validation passes)
        # generate a small valid PNG for public section
        buf3 = BytesIO()
        img3 = Image.new("RGBA", (6, 6), (0, 0, 255, 0))
        img3.save(buf3, format="PNG")
        buf3.seek(0)
        image_file = SimpleUploadedFile("public.png", buf3.read(), content_type="image/png")

        cs = ContentSection.objects.create(
            page=self.page,
            section_type="info",
            position_choice="top",
            media_type="image",
            title="Public",
            content="Public content",
            order=1,
            is_active=True,
            image=image_file,
        )
        resp = self.client.get(self.url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("success"))
        # ensure the public list contains our section
        data = resp.data.get("data")
        # when not paginated, data should be list
        if isinstance(data, list):
            items = data
        else:
            items = data.get("results", [])
        # check presence
        self.assertTrue(any(item.get("id") == str(cs.id) for item in items))
