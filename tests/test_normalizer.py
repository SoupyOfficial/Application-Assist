"""Tests for src/engine/normalizer.py — field label normalization."""

import pytest
from src.engine.normalizer import normalize_question, _clean, _match_profile_field_label


# ── _clean ────────────────────────────────────────────────────────────────

class TestClean:
    def test_lowercase_and_strip(self):
        assert _clean("  First Name  ") == "first name"

    def test_removes_punctuation(self):
        assert _clean("What is your email?") == "what is your email"

    def test_collapses_whitespace(self):
        assert _clean("First   Name") == "first name"

    def test_empty_string(self):
        assert _clean("") == ""

    def test_punctuation_only(self):
        assert _clean("???") == ""


# ── _match_profile_field_label ────────────────────────────────────────────

class TestProfileFieldLabel:
    def test_exact_match(self):
        assert _match_profile_field_label("first name") == "first_name"

    def test_exact_match_email(self):
        assert _match_profile_field_label("email address") == "email"

    def test_fuzzy_close_match(self):
        # "linkedin profile url" is an exact entry; a slight variation should still match
        result = _match_profile_field_label("linkedin profile")
        assert result == "linkedin_url"

    def test_no_match_returns_none(self):
        assert _match_profile_field_label("banana smoothie recipe") is None


# ── normalize_question ────────────────────────────────────────────────────

class TestNormalizeQuestion:
    def test_empty_label(self):
        assert normalize_question("") == "unknown"

    def test_whitespace_only(self):
        assert normalize_question("   ") == "unknown"

    def test_profile_field_exact(self):
        assert normalize_question("First Name") == "first_name"

    def test_profile_field_email(self):
        assert normalize_question("Email Address") == "email"

    def test_profile_field_linkedin(self):
        assert normalize_question("LinkedIn URL") == "linkedin_url"

    def test_canonical_question_exact(self, minimal_answers):
        result = normalize_question(
            "Are you legally authorized to work in the United States?",
            answers=minimal_answers,
        )
        assert result == "work_authorization_us"

    def test_fuzzy_match_from_phrases(self, minimal_answers):
        result = normalize_question(
            "Are you authorized to work in the US?",
            answers=minimal_answers,
        )
        assert result == "work_authorization_us"

    def test_no_answers_returns_cleaned(self):
        result = normalize_question("Some weird custom question")
        assert result == "some weird custom question"

    def test_no_match_returns_unknown_or_cleaned(self, minimal_answers):
        result = normalize_question(
            "Completely unrelated banana field xyz123",
            answers=minimal_answers,
        )
        # Should be "unknown" (no match) or the cleaned text (no LLM available)
        assert result in ("unknown", "completely unrelated banana field xyz123")

    def test_with_real_data_salary(self, answers):
        result = normalize_question("What are your salary expectations?", answers=answers)
        assert result == "salary_expectations"

    def test_with_real_data_sponsorship(self, answers):
        result = normalize_question(
            "Will you now or in the future require visa sponsorship?",
            answers=answers,
        )
        assert result == "requires_sponsorship"
