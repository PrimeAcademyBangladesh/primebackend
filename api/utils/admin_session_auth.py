"""Custom authentication that allows SessionAuthentication only for admin requests."""

from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication


class AdminSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication that only applies to requests from Django admin.
    Checks if the request path starts with /admin/ or if the referer is from admin.
    """

    def authenticate(self, request):
        # Only apply session auth if request is from admin interface
        path = request.path
        referer = request.META.get("HTTP_REFERER", "")

        # Check if this is an admin request
        is_admin_request = (
            path.startswith("/admin/") or "/admin/" in referer or request.META.get("HTTP_X_REQUESTED_FROM") == "admin"
        )

        if is_admin_request:
            return super().authenticate(request)

        # Not an admin request, skip session auth
        return None


class CombinedAuthentication:
    """
    Authentication class that tries SessionAuth for admin requests,
    then falls back to JWT for API requests.
    """

    def authenticate(self, request):
        # Try admin session auth first
        admin_auth = AdminSessionAuthentication()
        result = admin_auth.authenticate(request)
        if result is not None:
            return result

        # Fall back to JWT
        jwt_auth = JWTAuthentication()
        return jwt_auth.authenticate(request)

    def authenticate_header(self, request):
        """Return WWW-Authenticate header for 401 responses"""
        return 'Bearer realm="api"'
