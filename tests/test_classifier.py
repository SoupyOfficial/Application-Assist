"""Tests for src/llm/classifier.py — caching behavior."""

import pytest
from unittest.mock import patch, MagicMock
from src.llm.classifier import classify_field, _classify_cached


class TestClassifierCache:
    """Verify LRU caching prevents repeated API calls."""

    def setup_method(self):
        """Clear the cache before each test."""
        _classify_cached.cache_clear()

    def test_no_api_key_returns_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            result = classify_field("First Name", "", {})
            assert result["intent"] == "unknown"
            assert "ANTHROPIC_API_KEY" in result["reasoning"]

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_caching_avoids_duplicate_calls(self, mock_anthropic_cls):
        """Same (label, context) should only hit the API once."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"intent": "first_name", "confidence": 0.95, "reasoning": "test"}')]
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            r1 = classify_field("First Name", "personal info", {})
            r2 = classify_field("First Name", "personal info", {})

        assert r1["intent"] == "first_name"
        assert r2["intent"] == "first_name"
        # API should be called only once due to caching
        assert mock_client.messages.create.call_count == 1

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_different_labels_not_cached(self, mock_anthropic_cls):
        """Different labels should hit the API separately."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"intent": "email", "confidence": 0.9, "reasoning": "test"}')]
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            classify_field("Email", "", {})
            classify_field("Phone", "", {})

        assert mock_client.messages.create.call_count == 2
