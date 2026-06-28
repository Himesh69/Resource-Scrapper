"""
Unit tests for the URL Parser and Platform Detector.
"""
from __future__ import annotations

import pytest
from core.knowledge_graph import Platform, ContentType
from utils.url_parser import detect_platform, detect_content_type, normalize_url, parse_url


@pytest.mark.parametrize(
    "url,expected_platform",
    [
        ("https://www.instagram.com/reel/C567/", Platform.INSTAGRAM),
        ("https://instagram.com/p/abc", Platform.INSTAGRAM),
        ("https://youtube.com/watch?v=123456", Platform.YOUTUBE),
        ("https://youtu.be/123456", Platform.YOUTUBE),
        ("https://twitter.com/elonmusk/status/123", Platform.X),
        ("https://x.com/username/status/456", Platform.X),
        ("https://www.linkedin.com/posts/activity-123", Platform.LINKEDIN),
        ("https://google.com", Platform.UNKNOWN),
    ],
)
def test_detect_platform(url: str, expected_platform: Platform) -> None:
    """Test platform detection accuracy."""
    assert detect_platform(url) == expected_platform


@pytest.mark.parametrize(
    "url,expected_type",
    [
        ("https://www.instagram.com/reel/C567/", ContentType.REEL),
        ("https://www.instagram.com/reels/C567/", ContentType.REEL),
        ("https://instagram.com/p/abc", ContentType.POST),
        ("https://youtube.com/shorts/123", ContentType.SHORT),
        ("https://youtube.com/watch?v=123", ContentType.VIDEO),
        ("https://youtu.be/123", ContentType.VIDEO),
        ("https://x.com/username/status/456", ContentType.POST),
        ("https://google.com", ContentType.UNKNOWN),
    ],
)
def test_detect_content_type(url: str, expected_type: ContentType) -> None:
    """Test content type parsing from URL structure."""
    assert detect_content_type(url) == expected_type


@pytest.mark.parametrize(
    "url,expected_normalized",
    [
        ("https://instagram.com/reel/C567/?utm_source=ig_web_copy_link&si=123", "https://instagram.com/reel/C567"),
        ("https://www.youtube.com/watch?v=123&feature=shared&utm_campaign=xyz", "https://www.youtube.com/watch?v=123"),
        ("HTTP://X.COM/status/123/", "http://x.com/status/123"),
    ],
)
def test_normalize_url(url: str, expected_normalized: str) -> None:
    """Test that tracking params are stripped and format is normalized."""
    assert normalize_url(url) == expected_normalized
