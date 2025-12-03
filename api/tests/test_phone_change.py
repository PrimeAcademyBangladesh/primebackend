from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


def digits_only(s: str) -> str:
    return "".join(filter(str.isdigit, s or ""))


class PhoneChangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = CustomUser.objects.create_user(
            email="phoneuser@example.com",
            password="testpass123",
            first_name="Phone",
            last_name="User",
            phone="+8801234567890",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )
        self.teacher = CustomUser.objects.create_user(
            email="teacher@example.com",
            password="teacherpass123",
            first_name="Teach",
            last_name="User",
            phone="+8801111111111",
            role=CustomUser.Role.TEACHER,
            is_active=True,
        )

        # login student and set credentials
        resp = self.client.post(reverse('student-login'), {'email': self.student.email, 'password': 'testpass123'}, format='json')
        access = None
        if resp.data:
            data_block = resp.data.get('data') or {}
            tokens = data_block.get('tokens') or {}
            access = tokens.get('access')
        if access:
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        self.url = reverse('update-phone')

    def tearDown(self):
        self.client.credentials()  # clear auth

    @patch('api.views.views_auth.send_system_email')
    def test_student_can_update_phone(self, mock_send):
        new_phone = "+8801999887766"
        resp = self.client.post(self.url, {'new_phone': new_phone}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.student.refresh_from_db()
        # Serializer strips non-digits; tests should compare normalized digits-only
        self.assertEqual(self.student.phone, digits_only(new_phone))

    def test_unauthenticated_cannot_update(self):
        self.client.credentials()  # remove auth
        resp = self.client.post(self.url, {'new_phone': '+8801222333444'}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_non_student_cannot_update(self):
        # login as teacher
        resp = self.client.post(reverse('teacher-login'), {'email': self.teacher.email, 'password': 'teacherpass123'}, format='json')
        access = None
        if resp.data:
            data_block = resp.data.get('data') or {}
            tokens = data_block.get('tokens') or {}
            access = tokens.get('access')
        if access:
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = self.client.post(self.url, {'new_phone': '+8801234000000'}, format='json')
        # the view returns a success envelope with success=False when unauthorized
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get('success', True))
