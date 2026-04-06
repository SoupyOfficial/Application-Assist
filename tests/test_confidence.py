"""Tests for src/engine/confidence.py — confidence scoring and fill decisions."""

import pytest
from src.engine.confidence import score_confidence, get_fill_decision


# ── score_confidence ──────────────────────────────────────────────────────

class TestScoreConfidence:
    def test_high_confidence_exact_match(self):
        result = {
            "confidence": "high",
            "match_score": 1.0,
            "answer": "Yes",
            "requires_review": False,
        }
        score = score_confidence(result)
        assert score >= 0.8

    def test_none_confidence(self):
        result = {
            "confidence": "none",
            "match_score": 0.0,
            "answer": None,
            "requires_review": True,
        }
        score = score_confidence(result)
        assert score <= 0.3

    def test_medium_confidence(self):
        result = {
            "confidence": "medium",
            "match_score": 0.8,
            "answer": "Yes",
            "requires_review": False,
        }
        score = score_confidence(result)
        assert 0.4 < score < 0.9

    def test_no_answer_caps_score(self):
        result = {
            "confidence": "high",
            "match_score": 1.0,
            "answer": None,
            "answer_long": None,
            "requires_review": False,
        }
        score = score_confidence(result)
        assert score <= 0.3

    def test_requires_review_caps_score(self):
        result = {
            "confidence": "high",
            "match_score": 1.0,
            "answer": "Yes",
            "requires_review": True,
        }
        score = score_confidence(result)
        assert score <= 0.75

    def test_inverted_note_penalizes(self):
        result = {
            "confidence": "high",
            "match_score": 1.0,
            "answer": "Yes",
            "requires_review": False,
            "notes": "Inverted phrasing detected",
        }
        score = score_confidence(result)
        assert score <= 0.65

    def test_numeric_confidence_passthrough(self):
        result = {
            "confidence": 0.72,
            "match_score": 0.9,
            "answer": "Yes",
            "requires_review": False,
        }
        score = score_confidence(result)
        # 0.72 * 0.7 + 0.9 * 0.3 = 0.504 + 0.27 = 0.774
        assert 0.7 < score < 0.85


# ── get_fill_decision ─────────────────────────────────────────────────────

class TestGetFillDecision:
    def test_auto_fill_high_score(self):
        result = {"intent": "background_check_consent", "requires_review": False}
        assert get_fill_decision(0.95, result) == "auto_fill"

    def test_fill_and_flag_medium_score(self):
        result = {"intent": "willing_to_relocate", "requires_review": False}
        assert get_fill_decision(0.65, result) == "fill_and_flag"

    def test_skip_and_ask_low_score(self):
        result = {"intent": "unknown", "requires_review": False}
        assert get_fill_decision(0.2, result) == "skip_and_ask"

    def test_requires_review_prevents_auto_fill(self):
        result = {"intent": "salary_expectations", "requires_review": True}
        # Even at high score, requires_review -> fill_and_flag, not auto_fill
        assert get_fill_decision(0.9, result) == "fill_and_flag"

    def test_never_auto_submit_from_profile(self):
        result = {"intent": "salary_expectations", "requires_review": False}
        profile = {
            "application_preferences": {
                "never_auto_submit": ["salary_expectations"],
                "always_review": [],
            }
        }
        assert get_fill_decision(0.95, result, profile) == "fill_and_flag"

    def test_always_review_from_profile(self):
        result = {"intent": "work_authorization_us", "requires_review": False}
        profile = {
            "application_preferences": {
                "never_auto_submit": [],
                "always_review": ["work_authorization_us"],
            }
        }
        assert get_fill_decision(0.95, result, profile) == "fill_and_flag"

    def test_threshold_boundary_auto(self):
        result = {"intent": "test", "requires_review": False}
        assert get_fill_decision(0.8, result) == "auto_fill"

    def test_threshold_boundary_flag(self):
        result = {"intent": "test", "requires_review": False}
        assert get_fill_decision(0.5, result) == "fill_and_flag"

    def test_threshold_boundary_skip(self):
        result = {"intent": "test", "requires_review": False}
        assert get_fill_decision(0.49, result) == "skip_and_ask"
