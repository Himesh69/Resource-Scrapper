"""
Unit tests for the Input Validators.
"""
from __future__ import annotations

import pytest

from core.exceptions import DuplicateSubmissionError, InputValidationError, UnsupportedPlatformError
from utils.validators import validate_url, check_duplicate, validate_text_input


def test_validate_url_valid() -> None:
    """Test validation of supported platform URLs."""
    url = "https://instagram.com/reel/123/?si=abc"
    normalized = validate_url(url)
    assert normalized == "https://instagram.com/reel/123"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "not_a_url",
        "ftp://instagram.com/reel/123",
        "https://",
    ],
)
def test_validate_url_malformed(bad_url: str) -> None:
    """Test that malformed inputs raise InputValidationError."""
    with pytest.raises(InputValidationError):
        validate_url(bad_url)


def test_validate_url_unsupported_platform() -> None:
    """Test that unsupported domains raise UnsupportedPlatformError."""
    unsupported = "https://reddit.com/r/python"
    with pytest.raises(UnsupportedPlatformError):
        validate_url(unsupported)


def test_check_duplicate() -> None:
    """Test duplicate submission checking."""
    seen = {"https://instagram.com/reel/123"}
    
    # Non-duplicate should pass
    check_duplicate("https://instagram.com/reel/456", seen)
    
    # Duplicate (raw URL) should raise
    with pytest.raises(DuplicateSubmissionError):
        check_duplicate("https://instagram.com/reel/123", seen)
        
    # Duplicate (with tracking params) should also raise because check normalizes it
    with pytest.raises(DuplicateSubmissionError):
        check_duplicate("https://instagram.com/reel/123/?utm_source=copy", seen)


def test_validate_text_input() -> None:
    """Test plain text input validation requirements."""
    # Valid long text
    valid_text = "This is a long text post that contains useful information and satisfies the minimum length requirement."
    assert validate_text_input(valid_text) == valid_text
    
    # Invalid short text
    short_text = "Too short."
    with pytest.raises(InputValidationError):
        validate_text_input(short_text)
