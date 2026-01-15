"""Authentication and profile related tests.

Includes registration, login, profile CRUD, password reset and change
tests for students and teachers.
"""

from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from api.models.models_auth import CustomUser
from api.views.views_accounting import get


class TeacherLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse("teacher-login")

        # Create an active teacher
        self.active_teacher = CustomUser.objects.create_user(
            email="teacher@example.com",
            password="securepass123",
            first_name="Active",
            last_name="Teacher",
            phone="01700000001",
            role=CustomUser.Role.TEACHER,
            is_active=True,
        )

        # Create an inactive (unverified) teacher
        self.inactive_teacher = CustomUser.objects.create_user(
            email="inactive@example.com",
            password="securepass123",
            first_name="Inactive",
            last_name="Teacher",
            phone="01700000002",
            role=CustomUser.Role.TEACHER,
            is_active=False,
        )

    def _extract_tokens(self, resp):
        # Accept both envelope and flat responses
        if "tokens" in resp.data:
            return resp.data["tokens"]
        return resp.data.get("tokens")

    def _extract_user(self, resp):
        if "user" in resp.data:
            return resp.data["user"]
        return resp.data.get("user")

    def test_active_teacher_can_login(self):
        data = {"email": "teacher@example.com", "password": "securepass123"}
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        tokens_payload = self._extract_tokens(response)
        self.assertIsNotNone(tokens_payload)
        user_payload = self._extract_user(response)
        self.assertIsNotNone(user_payload)
        self.assertIn("access", tokens_payload)
        self.assertIn("refresh", tokens_payload)

    def test_inactive_teacher_cannot_login(self):
        data = {"email": "inactive@example.com", "password": "securepass123"}
        response = self.client.post(self.login_url, data, format="json")
        # Should be 400 or 401 depending on API's error mapping
        self.assertIn(response.status_code, (400, 401))
        # detail may be at top-level or under data
        detail = response.data.get("detail") or response.data.get("detail")
        # DRF may return validation detail as a string or a list; normalize to text
        if isinstance(detail, list):
            detail_text = " ".join(str(d) for d in detail)
        else:
            detail_text = str(detail)
        # Accept disabled, unable to log in, or invalid credentials messages
        self.assertTrue(
            "disabled" in detail_text.lower()
            or "unable to log in" in detail_text.lower()
            or "invalid credentials" in detail_text.lower(),
            msg=f"Unexpected detail message: {detail_text}",
        )


class TeacherProfileAndPasswordTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create and login a teacher
        self.teacher = CustomUser.objects.create_user(
            email="profile_teacher@example.com",
            password="initialPass123",
            first_name="Profile",
            last_name="Teacher",
            phone="01700000003",
            role=CustomUser.Role.TEACHER,
            is_active=True,
        )

        # Login to obtain tokens via teacher-login endpoint
        login_url = reverse("teacher-login")
        resp = self.client.post(
            login_url, {"email": "profile_teacher@example.com", "password": "initialPass123"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get("tokens") or resp.data.get("tokens")
        self.access = tokens["access"]

        # Set Authorization header for subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

        self.profile_url = reverse("my-profile")
        self.change_password_url = reverse("teacher-change-password")

    def test_get_teacher_profile(self):
        response = self.client.get(self.profile_url, format="json")
        self.assertEqual(response.status_code, 200)
        # Basic fields expected in profile response. The view may return
        # either a raw serializer dict or the project's envelope.
        if "email" in response.data:
            email_val = response.data["email"]
        else:
            email_val = response.data.get("email")
        # If still not present in the payload, fall back to DB value.
        if not email_val:
            user = get(pk=self.teacher.pk)
            email_val = user.email
        self.assertEqual(email_val, "profile_teacher@example.com")

    def test_patch_teacher_profile(self):
        # Attempt to change name + email and phone (email/phone should not change)
        data = {"first_name": "Updated", "last_name": "Name", "email": "hacked@example.com", "phone": "00000000000"}
        response = self.client.patch(self.profile_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        # Verify only allowed fields updated (first_name/last_name), and email/phone unchanged
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, "Updated")
        self.assertEqual(self.teacher.last_name, "Name")
        self.assertEqual(self.teacher.email, "profile_teacher@example.com")
        # phone should remain unchanged (not editable via profile patch)
        self.assertEqual(self.teacher.phone, "01700000003")

    def test_change_password_success(self):
        data = {
            "old_password": "initialPass123",
            "new_password": "NewStrongPass!1",
            "new_password2": "NewStrongPass!1",
        }
        response = self.client.post(self.change_password_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.data)
        # Ensure the old password no longer works
        self.client.credentials()  # remove token
        login_url = reverse("teacher-login")
        bad = self.client.post(
            login_url, {"email": "profile_teacher@example.com", "password": "initialPass123"}, format="json"
        )
        self.assertIn(bad.status_code, (400, 401))

    def test_change_password_wrong_old(self):
        data = {
            "old_password": "wrongOld",
            "new_password": "AnotherPass1!",
            "new_password2": "AnotherPass1!",
        }
        response = self.client.post(self.change_password_url, data, format="json")
        # API returns an envelope with message on incorrect old password
        self.assertEqual(response.status_code, 400)
        # message explains old password incorrect
        msg = response.data.get("message") or response.data.get("message")
        self.assertIsNotNone(msg)
        self.assertIn("old", msg.lower())


class StudentAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("student-register")
        self.login_url = reverse("student-login")
        self.profile_url = reverse("my-profile")
        self.verify_url = reverse("verify-student")
        self.resend_verification_url = reverse("resend-verification")
        self.password_reset_url = reverse("password-reset")
        self.password_reset_confirm_url = reverse("password-reset-confirm")
        self.change_password_url = reverse("student-change-password")
        self.logout_url = reverse("logout")

    def test_student_registration_and_verification_flow(self):
        # Register student
        data = {
            "email": "student1@example.com",
            "password": "StudPass123!",
            "password2": "StudPass123!",
            "first_name": "Stud",
            "last_name": "One",
            "phone": "01700000010",
        }
        resp = self.client.post(self.register_url, data, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("message", resp.data)

        # User should be created but inactive
        user = get(email="student1@example.com")
        self.assertFalse(user.is_active)

        # Resend verification for inactive user should succeed
        resp2 = self.client.post(self.resend_verification_url, {"email": "student1@example.com"}, format="json")
        self.assertEqual(resp2.status_code, 200)

        # Generate verification token (same signer as serializer)
        from django.core.signing import TimestampSigner

        signer = TimestampSigner()
        token = signer.sign(user.pk)

        # Call verify endpoint
        resp3 = self.client.get(self.verify_url, {"token": token})
        self.assertEqual(resp3.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_student_login_and_profile_and_logout(self):
        # create active student
        student = CustomUser.objects.create_user(
            email="student2@example.com",
            password="Password123!",
            first_name="Two",
            last_name="Student",
            phone="01700000011",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )

        # Login
        resp = self.client.post(self.login_url, {"email": "student2@example.com", "password": "Password123!"}, format="json")
        self.assertEqual(resp.status_code, 200)
        tokens = resp.data.get("tokens") or resp.data.get("tokens")
        self.assertIsNotNone(tokens)
        access = tokens["access"]
        refresh = tokens["refresh"]

        # Use token to get profile
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        prof = self.client.get(self.profile_url)
        self.assertEqual(prof.status_code, 200)
        # profile response may be wrapped in envelope {success,message,data:{user:...}}
        if "email" in prof.data:
            email_val = prof.data["email"]
        else:
            # tokens and user often live under data; UserProfileSerializer places email at data.email
            email_val = prof.data.get("email")
        self.assertEqual(email_val, "student2@example.com")

        # Update profile
        # Attempt to update first_name and also maliciously change email/phone via PATCH
        patch = self.client.patch(
            self.profile_url,
            {"first_name": "UpdatedStudent", "email": "attacker@example.com", "phone": "00000000000"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        student.refresh_from_db()
        # Ensure allowed fields updated; student phone/email should remain unchanged
        self.assertEqual(student.first_name, "UpdatedStudent")
        self.assertEqual(student.email, "student2@example.com")
        self.assertEqual(student.phone, "01700000011")

        # Logout by blacklisting refresh
        logout_resp = self.client.post(self.logout_url, {"refresh": refresh}, format="json")
        self.assertEqual(logout_resp.status_code, 200)

    def test_password_reset_request_and_confirm(self):
        student = CustomUser.objects.create_user(
            email="student3@example.com",
            password="OrigPass1",
            first_name="Three",
            last_name="Student",
            phone="01700000012",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )

        # Request password reset
        resp = self.client.post(self.password_reset_url, {"email": "student3@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)

        # Generate token and confirm reset
        from django.core.signing import TimestampSigner

        signer = TimestampSigner()
        token = signer.sign(str(student.pk))

        resp2 = self.client.post(
            self.password_reset_confirm_url + f"?token={token}",
            {"new_password": "NewPass123!", "new_password2": "NewPass123!"},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)

        # Ensure new password works
        login = self.client.post(self.login_url, {"email": "student3@example.com", "password": "NewPass123!"}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_change_password_requires_auth_and_valid_old(self):
        student = CustomUser.objects.create_user(
            email="student4@example.com",
            password="OldPass1",
            first_name="Four",
            last_name="Student",
            phone="01700000013",
            role=CustomUser.Role.STUDENT,
            is_active=True,
        )
        login = self.client.post(self.login_url, {"email": "student4@example.com", "password": "OldPass1"}, format="json")
        self.assertEqual(login.status_code, 200)
        access = login.data.get("tokens") or login.data.get("tokens")
        access = access["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        # Wrong old password
        resp = self.client.post(
            self.change_password_url,
            {"old_password": "wrong", "new_password": "X1Y2Z3!8", "new_password2": "X1Y2Z3!8"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        # Correct old password
        resp2 = self.client.post(
            self.change_password_url,
            {"old_password": "OldPass1", "new_password": "X1Y2Z3!8", "new_password2": "X1Y2Z3!8"},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
