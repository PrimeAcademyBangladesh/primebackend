from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


class CurrentUserProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student_login = reverse('student-login')
        self.teacher_login = reverse('teacher-login')
        self.my_profile = reverse('my-profile')

        # Create users
        self.student = CustomUser.objects.create_user(
            email='cur_student@example.com', password='StudPass321', first_name='Cur', last_name='Student', phone='01700000021', role=CustomUser.Role.STUDENT, is_active=True
        )

        self.teacher = CustomUser.objects.create_user(
            email='cur_teacher@example.com', password='TeachPass321', first_name='Cur', last_name='Teacher', phone='01700000022', role=CustomUser.Role.TEACHER, is_active=True
        )

    def _login_and_get_access(self, login_url, email, password):
        resp = self.client.post(login_url, {'email': email, 'password': password}, format='json')
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get('tokens') or resp.data.get('data', {}).get('tokens')
        return tokens['access']

    def test_student_can_get_and_patch_my_profile(self):
        access = self._login_and_get_access(self.student_login, 'cur_student@example.com', 'StudPass321')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        r = self.client.get(self.my_profile)
        self.assertEqual(r.status_code, 200)
        # ensure returned email matches
        if 'email' in r.data:
            email = r.data['email']
        else:
            email = r.data.get('data', {}).get('email')
        self.assertEqual(email, 'cur_student@example.com')

        # patch first name
        patch = self.client.patch(self.my_profile, {'first_name': 'StudentUpdated'}, format='json')
        self.assertEqual(patch.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'StudentUpdated')

    def test_teacher_can_get_and_patch_my_profile(self):
        access = self._login_and_get_access(self.teacher_login, 'cur_teacher@example.com', 'TeachPass321')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        r = self.client.get(self.my_profile)
        self.assertEqual(r.status_code, 200)
        if 'email' in r.data:
            email = r.data['email']
        else:
            email = r.data.get('data', {}).get('email')
        self.assertEqual(email, 'cur_teacher@example.com')

        # patch last name
        patch = self.client.patch(self.my_profile, {'last_name': 'TeacherUpdated'}, format='json')
        self.assertEqual(patch.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.last_name, 'TeacherUpdated')
