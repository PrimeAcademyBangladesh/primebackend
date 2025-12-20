"""URL building helpers used by emails and API links.

Provides build_full_url which uses a request or SITE_BASE_URL to produce
absolute links for emails and redirects.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse


def build_full_url(path: str, query_params: dict = None) -> str:
    """
    Build a full frontend URL.

    :param path: Frontend path (e.g., 'verify-student')
    :param query_params: Optional dict of query parameters
    """
    site_base = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not site_base:
        raise ValueError("Cannot build full URL: FRONTEND_URL not defined in settings.")

    url = f"{site_base}/{path.lstrip('/')}"
    if query_params:
        url += f"?{urlencode(query_params)}"

    return url
