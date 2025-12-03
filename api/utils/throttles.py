"""Throttling utilities for the API.

Includes login throttles and other rate-limiting helpers.
"""

from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """
    Per-email + per-IP login throttling.
    Uses email as primary key; falls back to IP if email is missing.
    """
    scope = "login"

    def get_cache_key(self, request, view):
        """
        Returns a cache key for the login throttle.

        If the email is provided, it uses the email as the primary key.
        If the email is missing, it falls back to using the IP address.

        :param request: The request object
        :param view: The view object
        :return: A cache key string
        """
        email = request.data.get("email")
        if email:
            return f"login:{email.lower()}"
        # Fall back to IP address
        return self.get_ident(request)
