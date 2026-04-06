"""Tests for the shared fill pipeline (src/adapters/pipeline.py)."""

from unittest.mock import MagicMock, patch
import pytest

from src.adapters.pipeline import run_fill_pipeline, _try_demographic_default, _handle_file_upload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_page():
    """A mock Playwright Page that records fill operations."""
    page = MagicMock()
    page.wait_for_timeout = MagicMock()
    return page


def _make_field(label="First Name", field_type="text", name="first_name",
                section="personal_info", options=None):
    """Helper to build a field descriptor dict."""
    return {
        "locator": MagicMock(),
        "label": label,
        "field_type": field_type,
        "name": name,
        "section": section,
        "required": True,
        "options": options,
        "placeholder": None,
    }


# ---------------------------------------------------------------------------
# run_fill_pipeline — integration tests
# ---------------------------------------------------------------------------

class TestRunFillPipeline:

    def test_returns_list_of_results(self, mock_page, minimal_profile, minimal_answers):
        """Pipeline should return one result dict per field."""
        fields = [_make_field("First Name"), _make_field("Last Name")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert len(results) == 2

    def test_result_keys_present(self, mock_page, minimal_profile, minimal_answers):
        """Each result should have all required keys for the review UI."""
        fields = [_make_field("First Name")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        result = results[0]
        required_keys = {"field", "proposed_answer", "confidence", "source",
                         "requires_review", "filled", "intent", "notes"}
        assert required_keys.issubset(result.keys())

    def test_profile_field_resolved(self, mock_page, minimal_profile, minimal_answers):
        """A 'First Name' field should resolve from profile identity data."""
        fields = [_make_field("First Name")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["proposed_answer"] == "Jacob"
        assert results[0]["source"] == "profile"

    def test_answers_bank_match(self, mock_page, minimal_profile, minimal_answers):
        """An answer-bank question should match and return the stored answer."""
        fields = [_make_field("What are your salary expectations?")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["proposed_answer"] is not None
        assert "$110,000" in str(results[0]["proposed_answer"])

    def test_no_match_field(self, mock_page, minimal_profile, minimal_answers):
        """An unrecognized field should produce a result with no answer filled."""
        fields = [_make_field("What is your favorite dinosaur?")]
        with patch("src.adapters.pipeline.fill_field", return_value=False):
            with patch("src.adapters.pipeline.draft_answer", return_value=None):
                results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["proposed_answer"] is None
        assert results[0]["filled"] is False
        assert results[0]["requires_review"] is True

    def test_file_upload_field_with_resume(self, mock_page, minimal_profile, minimal_answers):
        """File fields should use the _resume_path from profile."""
        minimal_profile["_resume_path"] = "/fake/resume.pdf"
        fields = [_make_field("Resume", field_type="file")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["source"] == "profile"
        assert results[0]["proposed_answer"] == "/fake/resume.pdf"
        assert results[0]["confidence"] == 1.0

    def test_file_upload_field_no_resume(self, mock_page, minimal_profile, minimal_answers):
        """File fields with no resume should flag for review."""
        fields = [_make_field("Resume", field_type="file")]
        with patch("src.adapters.pipeline.fill_field", return_value=False):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["requires_review"] is True
        assert results[0]["filled"] is False

    def test_empty_fields_list(self, mock_page, minimal_profile, minimal_answers):
        """Empty fields list should return empty results."""
        results = run_fill_pipeline(mock_page, [], minimal_profile, minimal_answers, "fill_and_pause")
        assert results == []

    def test_confidence_is_numeric(self, mock_page, minimal_profile, minimal_answers):
        """Confidence should always be a float, not a string label."""
        fields = [_make_field("Email")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert isinstance(results[0]["confidence"], float)

    def test_cover_letter_shortcut(self, mock_page, minimal_profile, minimal_answers):
        """Pre-generated cover letter text should be used for cover_letter intent."""
        minimal_profile["_cover_letter_text"] = "My tailored cover letter."
        fields = [_make_field("Cover Letter", field_type="textarea")]
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            results = run_fill_pipeline(mock_page, fields, minimal_profile, minimal_answers, "fill_and_pause")
        assert results[0]["proposed_answer"] == "My tailored cover letter."
        assert results[0]["source"] == "llm"


# ---------------------------------------------------------------------------
# _try_demographic_default
# ---------------------------------------------------------------------------

class TestDemographicDefault:

    def test_gender_decline(self):
        """Should find a 'decline' option for gender fields."""
        field = _make_field("Gender", field_type="select",
                            options=["Male", "Female", "Prefer not to say", "Other"])
        answers = {
            "demographic_defaults": {
                "common_select_values": {
                    "gender_decline": ["Prefer not to say", "Decline to self-identify"],
                }
            }
        }
        result = _try_demographic_default("demographic_gender", field, answers)
        assert result == "Prefer not to say"

    def test_non_demographic_intent(self):
        """Non-demographic intents should return None."""
        field = _make_field("Salary", field_type="select", options=["100k", "120k"])
        answers = {"demographic_defaults": {"common_select_values": {}}}
        result = _try_demographic_default("salary_expectations", field, answers)
        assert result is None

    def test_no_matching_option(self):
        """Should return None if no decline option is in the select."""
        field = _make_field("Gender", field_type="select", options=["Male", "Female"])
        answers = {
            "demographic_defaults": {
                "common_select_values": {
                    "gender_decline": ["Prefer not to say"],
                }
            }
        }
        result = _try_demographic_default("demographic_gender", field, answers)
        assert result is None

    def test_empty_options(self):
        """Should return None for empty options."""
        field = _make_field("Gender", field_type="select", options=[])
        answers = {"demographic_defaults": {"common_select_values": {"gender_decline": ["Decline"]}}}
        result = _try_demographic_default("demographic_gender", field, answers)
        assert result is None


# ---------------------------------------------------------------------------
# _handle_file_upload
# ---------------------------------------------------------------------------

class TestHandleFileUpload:

    def test_with_resume_path(self):
        """Should fill and return high-confidence result."""
        page = MagicMock()
        field = _make_field("Resume", field_type="file")
        profile = {"_resume_path": "/path/to/resume.pdf"}
        with patch("src.adapters.pipeline.fill_field", return_value=True):
            result = _handle_file_upload(page, field, profile, 2000, None)
        assert result["filled"] is True
        assert result["confidence"] == 1.0
        assert result["intent"] == "resume"

    def test_without_resume_path(self):
        """Should return unfilled result flagged for review."""
        page = MagicMock()
        field = _make_field("Resume", field_type="file")
        profile = {}
        result = _handle_file_upload(page, field, profile, 2000, None)
        assert result["filled"] is False
        assert result["requires_review"] is True
        assert "No resume" in result["notes"]
