from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


class MiddlewareTokenRevocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse("student-login")
        self.profile_url = reverse("my-profile")

    def _create_and_login(self, email="mwtest@example.com"):
        password = "MwPass1!"
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            first_name="Mw",
            last_name="Test",
            phone="01700000123",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )

        resp = self.client.post(self.login_url, {"email": email, "password": password}, format="json")
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get("tokens") or resp.data.get("data", {}).get("tokens")
        access = tokens["access"]
        return user, access

    def test_access_blocked_after_user_delete(self):
        user, access = self._create_and_login(email="mwdel@example.com")

        # Should be able to access profile initially
        r = self.client.get(self.profile_url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(r.status_code, 200)

        # Delete user (this should trigger pre_delete signal which blacklists refresh tokens)
        user.delete()

        # Using same access token should now be rejected by middleware (user not found)
        r2 = self.client.get(self.profile_url, HTTP_AUTHORIZATION=f"Bearer {access}")
        # middleware returns 401 when user not found
        self.assertEqual(r2.status_code, 401)

    def test_access_blocked_after_user_disable(self):
        user, access = self._create_and_login(email="mwdisable@example.com")

        # Should be able to access profile initially
        r = self.client.get(self.profile_url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(r.status_code, 200)

        # Disable user without deleting
        user.is_active = False
        user.save(update_fields=["is_active"])

        # Using same access token should now be rejected by middleware (disabled)
        r2 = self.client.get(self.profile_url, HTTP_AUTHORIZATION=f"Bearer {access}")
        # middleware returns 403 for disabled
        self.assertEqual(r2.status_code, 403)
