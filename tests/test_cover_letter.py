"""Tests for src/llm/cover_letter.py — cover letter generation and saving."""

import pytest
from unittest.mock import patch, MagicMock
from src.llm.cover_letter import generate_cover_letter, save_cover_letter


class TestGenerateCoverLetter:
    def test_no_api_key_returns_empty(self, minimal_profile):
        with patch.dict("os.environ", {}, clear=True):
            result = generate_cover_letter(minimal_profile, "Acme", "Engineer")
            assert result == ""

    @patch("src.llm.cover_letter.anthropic.Anthropic")
    def test_returns_generated_text(self, mock_cls, minimal_profile):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="This is a great cover letter.")]
        )
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = generate_cover_letter(minimal_profile, "Acme", "Engineer")
        assert result == "This is a great cover letter."
        mock_client.messages.create.assert_called_once()

    @patch("src.llm.cover_letter.anthropic.Anthropic")
    def test_includes_job_description_in_prompt(self, mock_cls, minimal_profile):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Letter")]
        )
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            generate_cover_letter(
                minimal_profile, "Acme", "Engineer",
                job_description="Build scalable APIs",
            )
        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Build scalable APIs" in user_msg


class TestSaveCoverLetter:
    def test_saves_file(self, tmp_path):
        with patch("src.llm.cover_letter.COVER_LETTERS_DIR", tmp_path):
            path = save_cover_letter("Hello world", "Acme Corp", "Backend Engineer")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Acme Corp" in content
        assert "Hello world" in content
        assert path.suffix == ".md"

    def test_avoids_overwrite(self, tmp_path):
        with patch("src.llm.cover_letter.COVER_LETTERS_DIR", tmp_path):
            p1 = save_cover_letter("First", "Acme", "Engineer")
            p2 = save_cover_letter("Second", "Acme", "Engineer")
        assert p1 != p2
        assert p1.exists()
        assert p2.exists()

    def test_sanitizes_filename(self, tmp_path):
        with patch("src.llm.cover_letter.COVER_LETTERS_DIR", tmp_path):
            path = save_cover_letter("Test", "Acme/Corp!", "Sr. Engineer@")
        assert "/" not in path.name
        assert "!" not in path.name
        assert "@" not in path.name
