
import os
from datetime import datetime


def ckeditor_upload_path_by_model(instance, filename):
    """
    Organize CKEditor uploads by model name.
    Path like: ckeditor/faq/2025/10/20251025_143022_filename.png
    """
    today = datetime.now()
    
    # Get model name from instance
    model_name = instance.__class__.__name__.lower()
    
    # Create unique filename with timestamp
    timestamp = today.strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    
    # Build path: ckeditor/model_name/YYYY/MM/filename
    base_dir = f"ckeditor/{model_name}/{today.year}/{today.month:02d}"
    
    return os.path.join(base_dir, unique_filename)


def absolutize_media_urls(html: str, request=None) -> str:
    """Rewrite src/href attributes that point to MEDIA files into absolute URLs.

    This variant will use the configured SITE_BASE_URL from Django settings
    as the authoritative base for generated absolute URLs. It's useful for
    scripts, tests, and development where the request host may be absent or
    invalid (e.g. 'testserver').

    Leaves already-absolute URLs (http(s):// or //) untouched.
    """
    if not html or not isinstance(html, str):
        return html

    import re

    from django.conf import settings

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    media_url = media_url if media_url.endswith("/") else media_url + "/"

    # Prefer SITE_BASE_URL from settings. Fall back to a safe default.
    site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if not site_base:
        site_base = "http://127.0.0.1:8000"

    def _replace(match):
        attr = match.group(1)
        quote = match.group(2)
        url = match.group(3)

        # Already absolute -> ignore
        if url.startswith("http://") or url.startswith("https://") or url.startswith("//"):
            return match.group(0)

        # Consider media-like URLs only
        if url.startswith(media_url) or url.startswith("/" + media_url.lstrip("/")) or url.startswith(media_url.lstrip("/")) or url.startswith("/media/"):
            # Ensure path begins with '/'
            if not url.startswith('/'):
                url_path = '/' + url
            else:
                url_path = url

            # Always construct full URL from SITE_BASE_URL
            full = f"{site_base}{url_path}"
            return f"{attr}={quote}{full}{quote}"

        return match.group(0)

    pattern = re.compile(r"(src|href)=([\'\"])(.*?)\2", flags=re.IGNORECASE)
    return pattern.sub(_replace, html)
