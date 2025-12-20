import pytest

from api.utils.video_utils import extract_video_id, validate_video_url


def test_validate_youtube_urls():
    urls = [
        "https://www.youtube.com/watch?v=ABCDEFGHIJK",
        "https://youtu.be/ABCDEFGHIJK",
        "https://www.youtube.com/embed/ABCDEFGHIJK",
    ]
    for u in urls:
        assert validate_video_url("youtube", u) is True
        assert extract_video_id("youtube", u) == "ABCDEFGHIJK"


def test_validate_vimeo_urls():
    urls = [
        "https://vimeo.com/123456789",
        "https://player.vimeo.com/video/123456789",
    ]
    for u in urls:
        assert validate_video_url("vimeo", u) is True
        assert extract_video_id("vimeo", u) == "123456789"


def test_invalid_or_empty():
    assert validate_video_url("youtube", None) is False
    assert validate_video_url(None, "https://youtu.be/ABCDEFGHIJK") is False
    assert extract_video_id("youtube", "https://example.com/watch?v=bad") is None
    assert extract_video_id("vimeo", "https://example.com/123") is None


def test_case_insensitivity_and_whitespace():
    assert validate_video_url("YouTube", "  https://youtu.be/ABCDEFGHIJK  ".strip()) is True
    assert extract_video_id("YouTube", "https://youtu.be/ABCDEFGHIJK") == "ABCDEFGHIJK"
