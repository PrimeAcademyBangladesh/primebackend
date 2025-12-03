"""Integration tests for authentication flows.

These tests use Django's test email backend (outbox) to capture sent
emails and extract the signed tokens to drive the password reset confirm
endpoint end-to-end.
"""

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password_reset_url = reverse('password-reset')
        self.password_reset_confirm_url = reverse('password-reset-confirm')
        self.login_url = reverse('student-login')
        self.change_password_url = reverse('student-change-password')

    def _extract_token_from_last_email(self):
        # Very small helper: search the last email body for '?token=' and return the value
        if not mail.outbox:
            return None
        body = mail.outbox[-1].body
        idx = body.find('?token=')
        if idx == -1:
            return None
        token = body[idx+len('?token='):].split()[0].strip()
        return token

    def test_password_reset_email_flow(self):
        # Create user
        user = CustomUser.objects.create_user(
            email='int_user@example.com', password='StartPass1!', first_name='Int', last_name='User', phone='01700000200', role=CustomUser.Role.STUDENT, is_active=True
        )

        # Request password reset - should send email
        resp = self.client.post(self.password_reset_url, {'email': user.email}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(mail.outbox) >= 1)

        token = self._extract_token_from_last_email()
        self.assertIsNotNone(token)

        # Confirm reset using token
        resp2 = self.client.post(self.password_reset_confirm_url + f'?token={token}', {'new_password': 'NewStrong1!', 'new_password2': 'NewStrong1!'}, format='json')
        self.assertEqual(resp2.status_code, 200)

        # Login with new password
        login = self.client.post(self.login_url, {'email': user.email, 'password': 'NewStrong1!'}, format='json')
        self.assertEqual(login.status_code, 200)

    def test_change_password_flow(self):
        user = CustomUser.objects.create_user(
            email='int_user2@example.com', password='StartPass1!', first_name='Int2', last_name='User2', phone='01700000201', role=CustomUser.Role.STUDENT, is_active=True
        )

        # Login to get access token
        resp = self.client.post(self.login_url, {'email': user.email, 'password': 'StartPass1!'}, format='json')
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get('tokens') or resp.data.get('data', {}).get('tokens')
        access = tokens['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        # Change password
        resp2 = self.client.post(self.change_password_url, {'old_password': 'StartPass1!', 'new_password': 'Another1!', 'new_password2': 'Another1!'}, format='json')
        self.assertEqual(resp2.status_code, 200)

        # Ensure old password no longer works
        self.client.credentials()  # clear token
        login_old = self.client.post(self.login_url, {'email': user.email, 'password': 'StartPass1!'}, format='json')
        self.assertIn(login_old.status_code, (400, 401))

        # Ensure new password works
        login_new = self.client.post(self.login_url, {'email': user.email, 'password': 'Another1!'}, format='json')
        self.assertEqual(login_new.status_code, 200)
