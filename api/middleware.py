# api/middleware.py
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class RejectDisabledUserMiddleware(MiddlewareMixin):
    """
    Very lightweight middleware.
    - Runs AFTER AuthenticationMiddleware
    - Never parses JWT
    - Uses request.user only
    - Uses cache to avoid repeated checks
    """

    CACHE_KEY_PREFIX = "user:disabled:"
    CACHE_TTL = 5  # seconds

    def process_request(self, request):
        user = getattr(request, "user", None)

        # Let anonymous users pass
        if not user or not user.is_authenticated:
            # For JWT-authenticated requests, DRF authenticates during view
            # handling (after middleware). To block disabled/deleted accounts
            # earlier, attempt to parse a Bearer access token from the
            # Authorization header and validate the referenced user's state.
            auth = request.META.get("HTTP_AUTHORIZATION", "")
            if auth and auth.startswith("Bearer "):
                token_str = auth.split(" ", 1)[1].strip()
                try:
                    from rest_framework_simplejwt.tokens import AccessToken

                    at = AccessToken(token_str)
                    user_id = at.get(getattr(settings, "SIMPLE_JWT", {}).get("USER_ID_CLAIM", "user_id")) or at.get("user_id")
                    if user_id:
                        # Import locally to avoid heavier imports at module level
                        from django.contrib.auth import get_user_model

                        User = get_user_model()
                        try:
                            fresh = User.objects.get(pk=user_id)
                        except User.DoesNotExist:
                            return JsonResponse({"detail": "User not found."}, status=401)

                        if not fresh.is_active or not getattr(fresh, "is_enabled", True):
                            return JsonResponse({"detail": "Your account has been disabled."}, status=403)
                except Exception:
                    # If token invalid/expired or simplejwt not installed, let DRF handle it
                    return None

            return None

        cache_key = f"{self.CACHE_KEY_PREFIX}{user.pk}"

        # Fast cache hit
        if cache.get(cache_key) is True:
            request.session.flush()
            return JsonResponse({"detail": "Your account has been disabled."}, status=403)

        # Check user flags (NO DB query, user already loaded)
        if not user.is_active or not getattr(user, "is_enabled", True):
            cache.set(cache_key, True, timeout=self.CACHE_TTL)
            request.session.flush()
            return JsonResponse({"detail": "Your account has been disabled."}, status=403)

        return None


# To use the signal, add this to your User model's app ready() method:
# @receiver(post_save, sender=User)
# def user_saved_handler(sender, instance, **kwargs):
#     clear_user_cache_on_status_change(sender, instance, **kwargs)


# import time
# import warnings
# from collections import OrderedDict

# from django.conf import settings
# from django.contrib.auth import get_user_model
# from django.core.cache import CacheKeyWarning, caches
# from django.http import JsonResponse

# try:
#     from rest_framework_simplejwt.tokens import AccessToken
# except Exception:
#     AccessToken = None


# class _InMemoryLRUCache:
#     """A tiny thread-unsafe LRU cache fallback when Django cache isn't configured.

#     Stores mapping key -> (value, expiry_timestamp). Simple and sufficient
#     for short-lived per-process caching in development.
#     """

#     def __init__(self, maxsize=1024):
#         self.maxsize = maxsize
#         self.data = OrderedDict()

#     def get(self, key):
#         item = self.data.get(key)
#         if not item:
#             return None
#         value, expiry = item
#         if expiry is not None and expiry < time.time():
#             # expired
#             del self.data[key]
#             return None
#         # mark as recently used
#         self.data.move_to_end(key)
#         return value

#     def set(self, key, value, timeout=None):
#         if timeout is None or timeout <= 0:
#             expiry = None
#         else:
#             expiry = time.time() + timeout
#         if key in self.data:
#             del self.data[key]
#         self.data[key] = (value, expiry)
#         # evict if too large
#         while len(self.data) > self.maxsize:
#             self.data.popitem(last=False)


# class RejectDeletedOrDisabledUserMiddleware:
#     """Reject requests where the authenticated user no longer exists or is disabled.

#     This middleware runs after Django's AuthenticationMiddleware. For any
#     authenticated request it verifies (with a short cache) that the user still
#     exists and is active/enabled. The cache reduces DB hits for repeated
#     requests for the same user.
#     """

#     CACHE_KEY_PREFIX = "middleware:user_status:"

#     def __init__(self, get_response):
#         self.get_response = get_response
#         # TTL in seconds for cached user status. Default 5 seconds.
#         self.ttl = getattr(settings, 'API_MIDDLEWARE_USER_CACHE_TTL_SECONDS', 5)

#         # Try to get the default cache. If cache configured, use it. If not,
#         # fall back to a tiny in-memory LRU cache.
#         try:
#             with warnings.catch_warnings():
#                 warnings.simplefilter('ignore', CacheKeyWarning)
#                 self.cache = caches['default']
#                 # Quick check to ensure cache backend is usable (some backends
#                 # raise on set/get if misconfigured)
#                 try:
#                     test_key = self.CACHE_KEY_PREFIX + 'probe'
#                     self.cache.set(test_key, '1', timeout=1)
#                 except Exception:
#                     self.cache = _InMemoryLRUCache()
#         except Exception:
#             self.cache = _InMemoryLRUCache()

#     def _cache_key(self, user_id):
#         return f"{self.CACHE_KEY_PREFIX}{user_id}"

#     def _get_cached_status(self, user_id):
#         key = self._cache_key(user_id)
#         try:
#             return self.cache.get(key)
#         except Exception:
#             # If cache backend fails, treat as miss
#             return None

#     def _set_cached_status(self, user_id, status):
#         key = self._cache_key(user_id)
#         try:
#             # cache.set may accept timeout kwarg; our fallback accepts positional
#             if hasattr(self.cache, 'set'):
#                 try:
#                     # Django cache API
#                     self.cache.set(key, status, timeout=self.ttl)
#                 except TypeError:
#                     # fallback in-memory cache signature
#                     self.cache.set(key, status, self.ttl)
#         except Exception:
#             # ignore cache set errors
#             pass

#     def _check_user_status(self, user_id):
#         """Return (ok: bool, reason: Optional[str]).

#         ok == True means user exists and is active/enabled.
#         """
#         # Try cached first (only negative results will be cached)
#         cached = self._get_cached_status(user_id)
#         if cached is not None:
#             return cached

#         User = get_user_model()
#         try:
#             fresh = User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             result = (False, 'not_found')
#             self._set_cached_status(user_id, result)
#             return result

#         if not getattr(fresh, 'is_active', True) or not getattr(fresh, 'is_enabled', True):
#             result = (False, 'disabled')
#             # cache negative (disabled) result so repeated requests are fast
#             self._set_cached_status(user_id, result)
#             return result

#         # Positive (ok) results are not cached to avoid allowing a recently
#         # disabled account to remain accessible until TTL expiry.
#         return (True, None)

#     def __call__(self, request):
#         user = getattr(request, 'user', None)
#         # If Django's authentication middleware already set request.user, use it.
#         if user and getattr(user, 'is_authenticated', False):
#             ok, reason = self._check_user_status(user.pk)
#             if not ok:
#                 if reason == 'not_found':
#                     return JsonResponse({'detail': 'User not found.'}, status=401)
#                 return JsonResponse({'detail': 'User account disabled.'}, status=403)
#         else:
#             # For JWT auth, DRF authenticates during view handling (after middleware).
#             # To block access tokens immediately, attempt to decode the Authorization
#             # header's Bearer access token to extract the user id and validate
#             # account state here. If token is invalid/expired we leave it to DRF.
#             auth = request.META.get('HTTP_AUTHORIZATION', '')
#             if auth and auth.startswith('Bearer '):
#                 token_str = auth.split(' ', 1)[1].strip()
#                 if AccessToken is not None:
#                     try:
#                         at = AccessToken(token_str)
#                         user_id = at.get(settings.SIMPLE_JWT.get('USER_ID_CLAIM', 'user_id')) or at.get('user_id')
#                         if user_id:
#                             ok, reason = self._check_user_status(user_id)
#                             if not ok:
#                                 if reason == 'not_found':
#                                     return JsonResponse({'detail': 'User not found.'}, status=401)
#                                 return JsonResponse({'detail': 'User account disabled.'}, status=403)
#                     except Exception:
#                         # invalid/expired token -> allow DRF auth to handle
#                         pass

#         return self.get_response(request)
