"""Reusable helper functions used by RejectDeletedOrDisabledUserMiddleware and other code.

Functions:
- get_user_status(user_id, ttl=None) -> (ok: bool, reason: Optional[str])
- decode_access_token(token_str) -> user_id | None
- check_token_user_status(token_str, ttl=None) -> (ok, reason)
- is_user_disabled(user) -> bool

These wrap the logic from the middleware so other parts of the app can reuse it.
"""

from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import caches

try:
    from rest_framework_simplejwt.tokens import AccessToken
except Exception:
    AccessToken = None

CACHE_KEY_PREFIX = "middleware:user_status:"


def _cache_key(user_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}{user_id}"


def get_user_status(user_id: str, ttl: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """Return (ok, reason) for a user id.

    ok == True means user exists and is active and enabled.
    reason is 'not_found' or 'disabled' for negative results.

    This function uses the Django cache (default) to cache negative results for ttl seconds.
    """
    if ttl is None:
        ttl = getattr(settings, "API_MIDDLEWARE_USER_CACHE_TTL_SECONDS", 5)

    cache = None
    try:
        cache = caches["default"]
    except Exception:
        cache = None

    key = _cache_key(user_id)
    if cache is not None:
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
        except Exception:
            pass

    User = get_user_model()
    try:
        fresh = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        result = (False, "not_found")
        if cache is not None:
            try:
                cache.set(key, result, timeout=ttl)
            except Exception:
                pass
        return result

    if not getattr(fresh, "is_active", True) or not getattr(fresh, "is_enabled", True):
        result = (False, "disabled")
        if cache is not None:
            try:
                cache.set(key, result, timeout=ttl)
            except Exception:
                pass
        return result

    return (True, None)


def decode_access_token(token_str: str) -> Optional[str]:
    """Extract the user id from a JWT access token string. Returns None if token invalid or missing."""
    if AccessToken is None:
        return None
    try:
        at = AccessToken(token_str)
        # SIMPLE_JWT may set USER_ID_CLAIM
        claim = settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
        return at.get(claim) or at.get("user_id")
    except Exception:
        return None


def check_token_user_status(token_str: str, ttl: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """Decode token and return user status (ok, reason).

    Returns (False, 'invalid_token') if token can't be decoded.
    """
    user_id = decode_access_token(token_str)
    if not user_id:
        return (False, "invalid_token")
    return get_user_status(user_id, ttl=ttl)


def is_user_disabled(user) -> bool:
    """Return True if user is considered disabled (inactive or admin-disabled)."""
    if user is None:
        return True
    return not (getattr(user, "is_active", True) and getattr(user, "is_enabled", True))
