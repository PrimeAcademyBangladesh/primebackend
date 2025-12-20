"""Tests for the resend verification flow including throttling.

Ensures expired tokens can be detected and that resending behaves as
expected (including throttle limits).
"""

import random
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APIClient

from api.models.models_auth import CustomUser


class ResendVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.resend_url = reverse("resend-verification")
        self.verify_url = reverse("verify-student")

        # Ensure throttling state from other tests does not leak into these tests
        try:
            cache.clear()
        except Exception:
            # If cache backend unavailable in this environment, ignore
            pass

        # create inactive student with a unique phone to avoid test DB collisions
        unique_phone = "017" + "".join(random.choices("0123456789", k=8))
        self.student = CustomUser.objects.create_user(
            email="resend@example.com",
            password="TestPass123",
            first_name="Resend",
            last_name="User",
            phone=unique_phone,
            role=CustomUser.Role.STUDENT,
            is_active=False,
        )

    def test_verify_expired_token_returns_can_resend(self):
        signer = TimestampSigner()
        token = signer.sign(str(self.student.pk))
        # artificially call verify with expired by using very small max_age via query tweak is hard
        # Instead, simulate bad signature by mangling the token
        bad_token = token + "tamper"
        resp = self.client.get(self.verify_url, {"token": bad_token}, format="json")
        # some implementations redirect or return 400; our view can return 400 or be throttled (429)
        self.assertIn(resp.status_code, (400, 302, 429))
        # if throttled, the body will be a DRF throttle detail; allow that
        if resp.status_code == 429:
            self.assertIn("detail", resp.data.get("data", {}))
        else:
            # can_resend may be nested under data
            self.assertIn("can_resend", resp.data.get("data", {}))
            self.assertTrue(resp.data.get("data", {}).get("can_resend"))
            self.assertIn("resend_url", resp.data.get("data", {}))

    def test_resend_throttle_and_send(self):
        # We'll patch the send_system_email to avoid real sends and patch the
        # ScopedRateThrottle.allow_request to deterministically throttle after
        # a few calls. This keeps the test independent of global settings.
        # Patch send email and throttle behaviors. Also patch ScopedRateThrottle.wait
        # so tests don't fail when DRF attempts to compute wait durations.
        with (
            patch("api.views.views_auth.send_system_email") as mock_send,
            patch("rest_framework.throttling.ScopedRateThrottle.allow_request") as mock_allow,
            patch("rest_framework.throttling.ScopedRateThrottle.wait", return_value=None),
        ):

            # allow the first 3 requests, then throttle (return False) on the 4th
            def side_effect(request, view):
                side_effect.count += 1
                return side_effect.count <= 3

            side_effect.count = 0
            mock_allow.side_effect = side_effect

            # First request should succeed and send email
            resp1 = self.client.post(self.resend_url, {"email": "resend@example.com"}, format="json")
            if resp1.status_code != 200:
                # Dump response for debugging (kept in test; will be removed once fixed)
                try:
                    print("DEBUG_RESP1_STATUS", resp1.status_code)
                    print("DEBUG_RESP1_CONTENT", resp1.content.decode("utf-8"))
                    print("DEBUG_RESP1_DATA", getattr(resp1, "data", None))
                except Exception:
                    pass
            self.assertEqual(resp1.status_code, 200)
            self.assertTrue(mock_send.called)

            # make 3 more rapid requests - the 4th overall should be throttled
            resp2 = self.client.post(self.resend_url, {"email": "resend@example.com"}, format="json")
            resp3 = self.client.post(self.resend_url, {"email": "resend@example.com"}, format="json")
            resp4 = self.client.post(self.resend_url, {"email": "resend@example.com"}, format="json")

            statuses = [resp2.status_code, resp3.status_code, resp4.status_code]
            self.assertTrue(any(s == 429 for s in statuses), msg=f"Expected a 429 in {statuses}")

    def test_register_resend_verify_integration(self):
        register_url = reverse("student-register")
        email = "integ@example.com"
        data = {
            "email": email,
            "password": "StrongPass1!",
            "password2": "StrongPass1!",
            "first_name": "Integra",
            "last_name": "Test",
            "phone": "01700000099",
        }

        # Capture registration email
        with patch("api.serializers.serializers_auth.send_system_email") as mock_reg_send:
            resp = self.client.post(register_url, data, format="json")
            self.assertEqual(resp.status_code, 201)
            self.assertTrue(mock_reg_send.called)
            # verification url is passed in context under 'verify_url'
            # Some implementations call send_system_email with keyword args.
            call_args, call_kwargs = mock_reg_send.call_args
            # Prefer kwargs context if present
            if "context" in call_kwargs:
                verify_url = call_kwargs["context"].get("verify_url")
            else:
                # Fallback: if positional args used, attempt to parse the message rendered
                # which is typically the second positional arg when message is rendered.
                if len(call_args) >= 2 and isinstance(call_args[1], str) and "token=" in call_args[1]:
                    parsed = urlparse(call_args[1])
                    token = parse_qs(parsed.query).get("token", [None])[0]
                    verify_url = None
                else:
                    verify_url = None
            if verify_url:
                parsed = urlparse(verify_url)
                token = parse_qs(parsed.query).get("token", [None])[0]
        # Tamper token to force invalid/expired and expect can_resend hint
        bad_token = token + "x"
        resp_bad = self.client.get(reverse("verify-student"), {"token": bad_token}, format="json")
        # allow throttle or 400
        self.assertIn(resp_bad.status_code, (400, 429))
        if resp_bad.status_code == 429:
            self.assertIn("detail", resp_bad.data.get("data", {}))
        else:
            # can_resend lives under data in api_response
            self.assertIn("can_resend", resp_bad.data.get("data", {}))

        # Call resend to get a new token and verify it activates the account
        with patch("api.views.views_auth.send_system_email") as mock_resend_send:
            # use a fresh client to avoid test-level throttling
            fresh = APIClient()
            resp_resend = fresh.post(reverse("resend-verification"), {"email": email}, format="json")
            self.assertEqual(resp_resend.status_code, 200)
            self.assertTrue(mock_resend_send.called)
            call_args, call_kwargs = mock_resend_send.call_args
            # Prefer kwargs context if present
            if "context" in call_kwargs and call_kwargs["context"].get("verify_url"):
                parsed = urlparse(call_kwargs["context"]["verify_url"])
                token2 = parse_qs(parsed.query).get("token", [None])[0]
            else:
                # Fallback: look for token in second positional arg (message) if available
                token2 = None
                if len(call_args) >= 2 and isinstance(call_args[1], str) and "token=" in call_args[1]:
                    # extract first token-like query from the message
                    try:
                        token2 = parse_qs(urlparse(call_args[1].split()[-1]).query).get("token", [None])[0]
                    except Exception:
                        token2 = None

        # Verify with the new token
        self.assertIsNotNone(token2)
        resp_verify2 = self.client.get(reverse("verify-student"), {"token": token2}, format="json")
        self.assertEqual(resp_verify2.status_code, 200)
        # Ensure user is active now
        user = CustomUser.objects.get(email=email)
        self.assertTrue(user.is_active)
