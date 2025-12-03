"""Tests for admin viewsets and permissions.

Verifies that admin endpoints are protected and that CRUD operations
work as expected for student and teacher management.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


class AdminViewSetTests(TestCase):
    def setUp(self):
        """
        Sets up the test environment for the admin viewset tests.

        Creates an admin user and a non-admin user, then logs in the admin
        user to obtain tokens for subsequent requests.

        Also creates three students to be managed by the admin user.
        """
        self.client = APIClient()
        # create an admin user
        self.admin = CustomUser.objects.create_user(
            email='admin@example.com', password='AdminPass1', first_name='Admin', last_name='User', phone='01700000020', role=CustomUser.Role.ADMIN, is_active=True
        )

        # create a non-admin user
        self.teacher = CustomUser.objects.create_user(
            email='teacher_admin_test@example.com', password='TeachPass1', first_name='T', last_name='User', phone='01700000021', role=CustomUser.Role.TEACHER, is_active=True
        )

        # create some students to manage
        for i in range(3):
            CustomUser.objects.create_user(
                email=f'student_admin_{i}@example.com', password='S1234567', first_name='S', last_name=str(i), phone=f'0170000002{i+2}', role=CustomUser.Role.STUDENT, is_active=True
            )

        # login admin to get tokens
        resp = self.client.post(reverse('admin-login'), {'email': 'admin@example.com', 'password': 'AdminPass1'}, format='json')
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get('tokens') or resp.data.get('data', {}).get('tokens')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_admin_can_list_students(self):
        resp = self.client.get('/api/admin/students/')
        self.assertEqual(resp.status_code, 200)
        # results live under data for the project's envelope
        results = resp.data.get('data', {}).get('results') or resp.data.get('results')
        self.assertIsNotNone(results)

    def test_admin_can_create_student(self):
        data = {'email': 'newstudent@example.com', 'password': 'NewStud1!', 'password2': 'NewStud1!', 'first_name': 'New', 'last_name': 'Stud', 'phone': '01700000099'}
        resp = self.client.post('/api/admin/students/', data, format='json')
        # serializer returns 201 on success
        self.assertIn(resp.status_code, (200, 201))
        user = CustomUser.objects.filter(email='newstudent@example.com').first()
        self.assertIsNotNone(user)

    def test_admin_can_retrieve_update_delete_student(self):
        student = CustomUser.objects.filter(role=CustomUser.Role.STUDENT).first()
        url = f'/api/admin/students/{student.pk}/'
        get = self.client.get(url)
        self.assertEqual(get.status_code, 200)

        patch = self.client.patch(url, {'first_name': 'Patched'}, format='json')
        self.assertEqual(patch.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.first_name, 'Patched')

        delete = self.client.delete(url)
        self.assertIn(delete.status_code, (204, 200))

    def test_admin_teacher_crud(self):
        # create a teacher via admin endpoint
        data = {'email': 'managed_teacher@example.com', 'password': 'TeachNew1', 'first_name': 'Managed', 'last_name': 'Teacher', 'phone': '01700000999'}
        resp = self.client.post('/api/admin/teachers/', data, format='json')
        self.assertIn(resp.status_code, (200, 201))
        teacher = CustomUser.objects.filter(email='managed_teacher@example.com').first()
        self.assertIsNotNone(teacher)
        # retrieve
        url = f'/api/admin/teachers/{teacher.pk}/'
        get = self.client.get(url)
        self.assertEqual(get.status_code, 200)
        # ensure admin retrieve includes nested profile
        data = get.data.get('data', {}) or get.data
        self.assertIn('profile', data)

        # update
        patch = self.client.patch(url, {'first_name': 'ManagedUpdated'}, format='json')
        self.assertEqual(patch.status_code, 200)
        teacher.refresh_from_db()
        self.assertEqual(teacher.first_name, 'ManagedUpdated')

        # delete
        delete = self.client.delete(url)
        self.assertIn(delete.status_code, (204, 200))


class AdminPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # create a teacher user who is not admin
        self.teacher = CustomUser.objects.create_user(
            email='plain_teacher@example.com', password='TeachPass2', first_name='T2', last_name='User', phone='01700000022', role=CustomUser.Role.TEACHER, is_active=True
        )

    def test_non_admin_cannot_access_admin_endpoints(self):
        # login as teacher
        resp = self.client.post(reverse('teacher-login'), {'email': 'plain_teacher@example.com', 'password': 'TeachPass2'}, format='json')
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get('tokens') or resp.data.get('data', {}).get('tokens')
        access = tokens['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        resp2 = self.client.get('/api/admin/students/')
        self.assertEqual(resp2.status_code, 403)

    def test_admin_can_list_teachers_includes_profile(self):
        # login as admin already done in previous tests? create and login here to be explicit
        admin = CustomUser.objects.create_user(
            email='list_admin@example.com', password='AdminList1', first_name='LA', last_name='Admin', phone='01700000123', role=CustomUser.Role.ADMIN, is_active=True
        )
        # create some teachers
        for i in range(2):
            CustomUser.objects.create_user(
                email=f'teach_list_{i}@example.com', password='TeachList1', first_name='TL', last_name=str(i), phone=f'0170000023{i}', role=CustomUser.Role.TEACHER, is_active=True
            )
        resp = self.client.post(reverse('admin-login'), {'email': 'list_admin@example.com', 'password': 'AdminList1'}, format='json')
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get('tokens') or resp.data.get('data', {}).get('tokens')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp2 = self.client.get('/api/admin/teachers/')
        self.assertEqual(resp2.status_code, 200)
        results = resp2.data.get('data', {}).get('results') or resp2.data.get('results')
        self.assertIsNotNone(results)
        # ensure each returned teacher has a profile nested object
        for item in results:
            self.assertIn('profile', item)
