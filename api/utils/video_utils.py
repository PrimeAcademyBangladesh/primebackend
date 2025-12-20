"""Video URL helpers shared across models.

Provides validate_video_url(provider, url) -> bool and
extract_video_id(provider, url) -> Optional[str].
"""

from __future__ import annotations

import re
from typing import Optional


def validate_video_url(video_provider: str | None, video_url: str | None) -> bool:
    """Return True if the given URL is valid for the provider.

    Supported providers: 'youtube', 'vimeo'.
    """
    if not video_url or not video_provider:
        return False

    provider = video_provider.lower()

    if provider == "youtube":
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            if re.search(pattern, video_url):
                return True
        return False

    if provider == "vimeo":
        patterns = [
            r"vimeo\.com\/(\d+)",
            r"player\.vimeo\.com\/video\/(\d+)",
        ]
        for pattern in patterns:
            if re.search(pattern, video_url):
                return True
        return False

    return False


def extract_video_id(video_provider: str | None, video_url: str | None) -> Optional[str]:
    """Extract the provider-specific video id from URL, or None if not found."""
    if not video_provider or not video_url:
        return None

    provider = video_provider.lower()

    if provider == "youtube":
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        return None

    if provider == "vimeo":
        patterns = [
            r"vimeo\.com\/(\d+)",
            r"player\.vimeo\.com\/video\/(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        return None

    return None
