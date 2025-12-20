"""Regression tests for password reset token one-time-use semantics.

Ensures that requesting a password reset twice produces two distinct tokens
where the second token (newly generated) remains usable even after the
first reset has updated `last_password_reset`.
"""

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password_reset_url = reverse("password-reset")
        self.password_reset_confirm_url = reverse("password-reset-confirm")
        self.login_url = reverse("student-login")

    def test_consecutive_resets_produce_usable_tokens(self):
        # Create active student
        student = CustomUser.objects.create_user(
            email="regress_student@example.com",
            password="StartPass1",
            first_name="Reg",
            last_name="Student",
            phone="01700000099",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )

        # Request first reset and capture token from email outbox
        resp = self.client.post(self.password_reset_url, {"email": student.email}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(mail.outbox) >= 1)
        body = mail.outbox[-1].body
        idx = body.find("?token=")
        self.assertNotEqual(idx, -1, msg="token not found in email body")
        token_a = body[idx + len("?token=") :].split()[0].strip()

        # Use token A to reset password
        resp_a = self.client.post(
            self.password_reset_confirm_url + f"?token={token_a}",
            {"new_password": "NewPassA1!", "new_password2": "NewPassA1!"},
            format="json",
        )
        self.assertEqual(resp_a.status_code, 200)

        # Ensure student can login with new password A
        login_a = self.client.post(self.login_url, {"email": student.email, "password": "NewPassA1!"}, format="json")
        self.assertEqual(login_a.status_code, 200)

        # Request second reset (new token B) and capture token from email outbox
        resp2 = self.client.post(self.password_reset_url, {"email": student.email}, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(len(mail.outbox) >= 2)
        body_b = mail.outbox[-1].body
        idxb = body_b.find("?token=")
        self.assertNotEqual(idxb, -1, msg="token not found in second email body")
        token_b = body_b[idxb + len("?token=") :].split()[0].strip()

        # Use token B to reset password again
        resp_b = self.client.post(
            self.password_reset_confirm_url + f"?token={token_b}",
            {"new_password": "NewPassB1!", "new_password2": "NewPassB1!"},
            format="json",
        )
        self.assertEqual(resp_b.status_code, 200)

        # Ensure student can login with new password B
        login_b = self.client.post(self.login_url, {"email": student.email, "password": "NewPassB1!"}, format="json")
        self.assertEqual(login_b.status_code, 200)
