"""Tests for src/engine/filler.py — non-Playwright utility functions."""

import pytest
from src.engine.filler import find_best_option_match, _find_best_label_index


# ── find_best_option_match ────────────────────────────────────────────────

class TestFindBestOptionMatch:
    def test_exact_case_insensitive(self):
        options = ["Yes", "No", "Not sure"]
        assert find_best_option_match("yes", options) == "Yes"

    def test_prefix_match(self):
        options = ["United States of America", "United Kingdom", "Canada"]
        assert find_best_option_match("United States", options) == "United States of America"

    def test_fuzzy_match(self):
        options = ["Decline to self-identify", "Male", "Female", "Non-binary"]
        result = find_best_option_match("Decline to self identify", options)
        assert result == "Decline to self-identify"

    def test_no_match_returns_none(self):
        options = ["Apple", "Banana", "Cherry"]
        assert find_best_option_match("Zucchini", options) is None

    def test_empty_options(self):
        assert find_best_option_match("Yes", []) is None


# ── _find_best_label_index ────────────────────────────────────────────────

class TestFindBestLabelIndex:
    def test_exact_match(self):
        labels = ["Yes", "No", "Maybe"]
        assert _find_best_label_index("Yes", labels) == 0

    def test_close_match(self):
        labels = ["I do not require sponsorship", "I require sponsorship"]
        idx = _find_best_label_index("I do not require visa sponsorship", labels)
        assert idx == 0

    def test_no_match_returns_none(self):
        labels = ["Apple", "Banana"]
        assert _find_best_label_index("Zucchini smoothie recipe", labels) is None

    def test_empty_labels(self):
        assert _find_best_label_index("Yes", []) is None
