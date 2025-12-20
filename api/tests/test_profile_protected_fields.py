from django.urls import reverse

from rest_framework.test import APITestCase

from api.models.models_auth import CustomUser


class ProfileProtectedFieldsTests(APITestCase):
    def test_student_cannot_change_protected_flags_via_profile(self):
        # Create student with known flags
        student = CustomUser.objects.create_user(
            email="student-protected@example.com",
            password="pass12345",
            role=CustomUser.Role.STUDENT,
            is_active=True,
            is_enabled=True,
        )

        self.client.force_authenticate(user=student)
        url = reverse("my-profile")

        payload = {
            "first_name": "NewFirst",
            "is_enabled": False,
            "is_active": False,
        }

        resp = self.client.patch(url, payload, format="json")
        self.assertIn(resp.status_code, (200, 204))

        student.refresh_from_db()
        # is_enabled CAN be changed by students (this is now allowed)
        self.assertFalse(student.is_enabled)
        # is_active should remain protected (cannot be changed)
        self.assertTrue(student.is_active)
        # Writable field should update
        self.assertEqual(student.first_name, "NewFirst")

    def test_teacher_cannot_change_protected_flags_via_profile(self):
        teacher = CustomUser.objects.create_user(
            email="teacher-protected@example.com",
            password="pass12345",
            role=CustomUser.Role.TEACHER,
            is_active=True,
            is_enabled=True,
        )

        self.client.force_authenticate(user=teacher)
        url = reverse("my-profile")

        payload = {
            "last_name": "NewLast",
            "is_enabled": False,
            "is_active": False,
        }

        resp = self.client.patch(url, payload, format="json")
        self.assertIn(resp.status_code, (200, 204))

        teacher.refresh_from_db()
        # is_enabled CAN be changed by teachers (this is now allowed)
        self.assertFalse(teacher.is_enabled)
        # is_active should remain protected (cannot be changed)
        self.assertTrue(teacher.is_active)
        # Writable field should update
        self.assertEqual(teacher.last_name, "NewLast")
