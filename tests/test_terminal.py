"""Tests for the terminal review UI (src/review/terminal.py)."""

from unittest.mock import patch, MagicMock
import pytest

from src.review.terminal import (
    review_session,
    _render_summary_table,
    _review_single_field,
    _render_decision_summary,
    AUTO_APPROVE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fill_result(label="First Name", answer="Jacob", confidence=0.9,
                      source="profile", requires_review=False, filled=True):
    return {
        "field": {"label": label, "field_type": "text", "name": label.lower()},
        "proposed_answer": answer,
        "confidence": confidence,
        "source": source,
        "requires_review": requires_review,
        "filled": filled,
        "intent": label.lower().replace(" ", "_"),
        "notes": "",
    }


# ---------------------------------------------------------------------------
# review_session
# ---------------------------------------------------------------------------

class TestReviewSession:

    def test_empty_fields_returns_empty(self):
        """Empty input should return empty list."""
        result = review_session([])
        assert result == []

    @patch("src.review.terminal.Prompt.ask", return_value="y")
    def test_batch_approve_high_confidence(self, mock_ask):
        """High-confidence non-review fields should be batch-approved when user says 'y'."""
        fields = [
            _make_fill_result("First Name", "Jacob", 0.93, requires_review=False),
            _make_fill_result("Email", "jacob@example.com", 0.93, requires_review=False),
        ]
        result = review_session(fields)
        assert len(result) == 2
        assert all(f["action"] == "accept" for f in result)
        assert all(f["final_answer"] is not None for f in result)

    @patch("src.review.terminal.Prompt.ask")
    def test_batch_decline_sends_to_manual(self, mock_ask):
        """Declining batch approve should send fields to individual review."""
        # First call: batch approve prompt -> 'n'; subsequent calls: individual review -> 'a'
        mock_ask.side_effect = ["n", "a", "a"]
        fields = [
            _make_fill_result("First Name", "Jacob", 0.93, requires_review=False),
            _make_fill_result("Email", "jacob@example.com", 0.93, requires_review=False),
        ]
        result = review_session(fields)
        assert len(result) == 2
        assert all(f["action"] == "accept" for f in result)

    @patch("src.review.terminal.Prompt.ask", return_value="a")
    def test_review_flagged_fields_shown_individually(self, mock_ask):
        """Fields with requires_review=True must go to individual review."""
        fields = [
            _make_fill_result("Salary", "$100k", 0.7, requires_review=True),
        ]
        result = review_session(fields)
        # Should be individually reviewed, not batch-approved
        assert len(result) == 1
        assert result[0]["action"] == "accept"

    @patch("src.review.terminal.Prompt.ask", return_value="r")
    def test_reject_sets_action_and_null_answer(self, mock_ask):
        """Rejecting a field should set action='reject' and final_answer=None."""
        fields = [
            _make_fill_result("Salary", "$100k", 0.3, requires_review=True),
        ]
        result = review_session(fields)
        assert result[0]["action"] == "reject"
        assert result[0]["final_answer"] is None

    @patch("src.review.terminal.Prompt.ask")
    def test_edit_sets_custom_answer(self, mock_ask):
        """Editing a field should set action='edit' and custom final_answer."""
        # First call: action choice -> 'e'; second call: custom answer text
        mock_ask.side_effect = ["e", "My custom answer"]
        fields = [
            _make_fill_result("Why this company?", "", 0.2, requires_review=True),
        ]
        result = review_session(fields)
        assert result[0]["action"] == "edit"
        assert result[0]["final_answer"] == "My custom answer"

    @patch("src.review.terminal.Prompt.ask", return_value="a")
    def test_low_confidence_no_answer_goes_to_review(self, mock_ask):
        """Fields with None answer should always go to individual review."""
        fields = [
            _make_fill_result("Unknown field", None, 0.0, requires_review=True, filled=False),
        ]
        result = review_session(fields)
        assert len(result) == 1
        assert result[0]["action"] == "accept"

    @patch("src.review.terminal.Prompt.ask", return_value="y")
    def test_mixed_fields_partition_correctly(self, mock_ask):
        """Mix of high-confidence and review-flagged fields should partition correctly."""
        fields = [
            _make_fill_result("First Name", "Jacob", 0.93, requires_review=False),
            _make_fill_result("Salary", "$100k", 0.7, requires_review=True),
        ]
        # 'y' for batch approve, then 'a' for the review field
        mock_ask.side_effect = ["y", "a"]
        result = review_session(fields)
        assert len(result) == 2
        auto_approved = [f for f in result if f["field"]["label"] == "First Name"]
        reviewed = [f for f in result if f["field"]["label"] == "Salary"]
        assert auto_approved[0]["action"] == "accept"
        assert reviewed[0]["action"] == "accept"


# ---------------------------------------------------------------------------
# _review_single_field
# ---------------------------------------------------------------------------

class TestReviewSingleField:

    @patch("src.review.terminal.Prompt.ask", return_value="a")
    def test_accept(self, mock_ask):
        field = _make_fill_result("Name", "Jacob")
        _review_single_field(field)
        assert field["action"] == "accept"
        assert field["final_answer"] == "Jacob"

    @patch("src.review.terminal.Prompt.ask", return_value="r")
    def test_reject(self, mock_ask):
        field = _make_fill_result("Name", "Jacob")
        _review_single_field(field)
        assert field["action"] == "reject"
        assert field["final_answer"] is None

    @patch("src.review.terminal.Prompt.ask")
    def test_edit(self, mock_ask):
        mock_ask.side_effect = ["e", "Jake"]
        field = _make_fill_result("Name", "Jacob")
        _review_single_field(field)
        assert field["action"] == "edit"
        assert field["final_answer"] == "Jake"


# ---------------------------------------------------------------------------
# _render_decision_summary (smoke test — just make sure it doesn't crash)
# ---------------------------------------------------------------------------

class TestRenderDecisionSummary:

    def test_renders_without_error(self):
        fields = [
            {**_make_fill_result(), "action": "accept"},
            {**_make_fill_result(), "action": "reject"},
            {**_make_fill_result(), "action": "edit"},
        ]
        _render_decision_summary(fields)  # Should not raise


# ---------------------------------------------------------------------------
# _render_summary_table (smoke test)
# ---------------------------------------------------------------------------

class TestRenderSummaryTable:

    def test_renders_without_error(self):
        fields = [
            _make_fill_result("First Name", "Jacob", 0.9),
            _make_fill_result("Salary", "$100k", 0.5),
            _make_fill_result("Unknown", None, 0.1),
        ]
        _render_summary_table(fields)  # Should not raise

    def test_long_answer_truncated(self):
        """Long answers shouldn't crash the table renderer."""
        fields = [_make_fill_result("Essay", "x" * 200, 0.5)]
        _render_summary_table(fields)  # Should not raise


# ---------------------------------------------------------------------------
# AUTO_APPROVE_THRESHOLD
# ---------------------------------------------------------------------------

class TestThreshold:

    def test_threshold_value(self):
        """Threshold should be 0.8 to match pipeline confidence."""
        assert AUTO_APPROVE_THRESHOLD == 0.8
