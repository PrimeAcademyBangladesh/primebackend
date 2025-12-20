"""
Cache utilities with automatic invalidation.

Provides safe caching that:
- Only caches public/anonymous requests
- Automatically invalidates on model updates
- Includes cache hit/miss headers for debugging
"""

import hashlib
from functools import wraps

from django.core.cache import cache
from django.utils.encoding import force_str


def generate_cache_key(prefix, *args, **kwargs):
    """Generate a consistent cache key from arguments."""
    key_parts = [prefix]
    key_parts.extend([force_str(arg) for arg in args])
    key_parts.extend([f"{k}={force_str(v)}" for k, v in sorted(kwargs.items())])

    key_string = ":".join(key_parts)

    # Hash if key is too long
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    return key_string


def cache_response(timeout=300, key_prefix="view", cache_anonymous_only=True):
    """
    Cache decorator for DRF views with automatic invalidation.

    Args:
        timeout: Cache TTL in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key
        cache_anonymous_only: Only cache for anonymous users (default: True)

    Usage:
        @cache_response(timeout=600, key_prefix='course_list')
        def list(self, request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Check if we should skip caching
            should_skip_cache = False
            skip_reason = None

            # Don't cache for authenticated users if cache_anonymous_only=True
            if cache_anonymous_only and request.user.is_authenticated:
                should_skip_cache = True
                skip_reason = "SKIP-AUTH"

            # Don't cache for staff users (they might be testing/editing)
            if request.user.is_authenticated and hasattr(request.user, "is_staff") and request.user.is_staff:
                should_skip_cache = True
                skip_reason = "SKIP-STAFF"

            # If we should skip cache, just call the view and return
            if should_skip_cache:
                response = view_func(self, request, *args, **kwargs)
                if hasattr(response, "__setitem__"):  # Check if we can set headers
                    response["X-Cache"] = skip_reason
                return response

            # Generate cache key from request
            query_params = sorted(request.GET.items())
            cache_key = generate_cache_key(key_prefix, request.path, *[f"{k}={v}" for k, v in query_params])

            # Try to get from cache
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                # Return cached response
                from rest_framework import status

                from api.utils.response_utils import api_response

                response = api_response(
                    cached_data["success"],
                    cached_data["message"],
                    cached_data["data"],
                    cached_data.get("status_code", status.HTTP_200_OK),
                )
                response["X-Cache"] = "HIT"
                response["X-Cache-Key"] = cache_key[:50]  # Truncate for header
                return response

            # Call the actual view
            response = view_func(self, request, *args, **kwargs)

            # Cache successful responses only
            if hasattr(response, "data") and hasattr(response, "status_code") and response.status_code == 200:
                cache_data = {
                    "success": response.data.get("success", True),
                    "message": response.data.get("message", ""),
                    "data": response.data.get("data", {}),
                    "status_code": response.status_code,
                }
                cache.set(cache_key, cache_data, timeout)
                if hasattr(response, "__setitem__"):
                    response["X-Cache"] = "MISS"
                    response["X-Cache-Key"] = cache_key[:50]
            else:
                if hasattr(response, "__setitem__"):
                    response["X-Cache"] = "SKIP-ERROR"

            return response

        return wrapper

    return decorator


def invalidate_cache_pattern(pattern):
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: Cache key pattern (e.g., 'course_list:*')

    Note: Requires Redis backend for pattern matching.
    For other backends, this will silently fail.
    """
    try:
        from django.core.cache.backends.redis import RedisCache

        if isinstance(cache, RedisCache):
            # Redis supports pattern deletion
            keys = cache.keys(pattern)
            if keys:
                cache.delete_many(keys)
        else:
            # For other backends, we need to track keys manually
            # This is a fallback - not as efficient
            pass
    except Exception:
        # Silently fail - caching is not critical
        pass


def invalidate_cache_keys(*keys):
    """Delete specific cache keys."""
    cache.delete_many(keys)


# Cache key prefixes
CACHE_KEY_COURSE_LIST = "course_list"
CACHE_KEY_COURSE_DETAIL = "course_detail"
CACHE_KEY_COURSE_FEATURED = "course_featured"
CACHE_KEY_HOME_CATEGORIES = "home_categories"
CACHE_KEY_COURSE_PRICE = "course_price"
CACHE_KEY_CATEGORY_LIST = "category_list"
CACHE_KEY_BLOG_LIST = "blog_list"
CACHE_KEY_BLOG_DETAIL = "blog_detail"
CACHE_KEY_FAQ_LIST = "faq_list"
CACHE_KEY_ACADEMY_OVERVIEW = "academy_overview"
CACHE_KEY_MEGAMENU = "megamenu_nav"


def clear_course_caches():
    """Clear all course-related caches."""
    invalidate_cache_pattern(f"{CACHE_KEY_COURSE_LIST}:*")
    invalidate_cache_pattern(f"{CACHE_KEY_COURSE_DETAIL}:*")
    cache.delete(CACHE_KEY_COURSE_FEATURED)
    invalidate_cache_pattern(f"{CACHE_KEY_HOME_CATEGORIES}:*")
    cache.delete(CACHE_KEY_MEGAMENU)


def clear_course_detail_cache(slug):
    """Clear cache for specific course."""
    cache_key = generate_cache_key(CACHE_KEY_COURSE_DETAIL, slug)
    cache.delete(cache_key)


def clear_category_caches():
    """Clear all category-related caches."""
    invalidate_cache_pattern(f"{CACHE_KEY_CATEGORY_LIST}:*")
    cache.delete(CACHE_KEY_MEGAMENU)
    invalidate_cache_pattern(f"{CACHE_KEY_HOME_CATEGORIES}:*")


def clear_blog_caches():
    """Clear all blog-related caches."""
    invalidate_cache_pattern(f"{CACHE_KEY_BLOG_LIST}:*")
    invalidate_cache_pattern(f"{CACHE_KEY_BLOG_DETAIL}:*")


def clear_faq_caches():
    """Clear FAQ caches."""
    invalidate_cache_pattern(f"{CACHE_KEY_FAQ_LIST}:*")


def clear_academy_caches():
    """Clear academy overview caches."""
    invalidate_cache_pattern(f"{CACHE_KEY_ACADEMY_OVERVIEW}:*")
