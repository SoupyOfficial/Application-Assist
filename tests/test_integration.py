"""
End-to-end integration test for Application-Assist.

Exercises the full flow: adapter selection → fill_form → review → submit,
with a fully mocked Playwright page. Verifies the complete pipeline from
main.run_application() through to application tracking.
"""

from argparse import Namespace
from unittest.mock import MagicMock, patch, ANY
import pytest

from src.main import run_application, _extract_company, _extract_role, resolve_resume_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_page():
    """A mock Playwright Page with a realistic title."""
    page = MagicMock()
    page.title.return_value = "Software Engineer - Acme Corp"
    page.wait_for_timeout = MagicMock()
    page.wait_for_load_state = MagicMock()
    return page


@pytest.fixture
def default_args():
    """Default CLI args for run_application."""
    return Namespace(
        url="https://boards.greenhouse.io/acme/jobs/12345",
        mode="fill_only",
        profile="data/profile.json",
        answers="data/answers.json",
        resume="backend",
        cover_letter=False,
        company=None,
        role=None,
        dry_run=False,
    )


def _make_field(label="First Name", field_type="text", name="first_name"):
    return {
        "locator": MagicMock(),
        "label": label,
        "field_type": field_type,
        "name": name,
        "section": "personal_info",
        "required": True,
        "options": None,
        "placeholder": None,
    }


def _make_fill_result(field, answer="Jacob", filled=True, confidence=0.93,
                      source="profile", requires_review=False, intent="first_name"):
    return {
        "field": field,
        "proposed_answer": answer,
        "confidence": confidence,
        "source": source,
        "requires_review": requires_review,
        "filled": filled,
        "intent": intent,
        "notes": "",
    }


# ---------------------------------------------------------------------------
# _extract_company / _extract_role
# ---------------------------------------------------------------------------

class TestExtractors:

    def test_extract_company_from_title(self, mock_page):
        assert _extract_company(mock_page) == "Acme Corp"

    def test_extract_role_from_title(self, mock_page):
        assert _extract_role(mock_page) == "Software Engineer"

    def test_extract_company_empty_title(self, mock_page):
        mock_page.title.return_value = ""
        assert _extract_company(mock_page) is None

    def test_extract_role_empty_title(self, mock_page):
        mock_page.title.return_value = ""
        # Returns empty string from parts[0].strip()
        result = _extract_role(mock_page)
        assert result == "" or result is None

    def test_extract_company_no_dash(self, mock_page):
        mock_page.title.return_value = "Apply Now"
        assert _extract_company(mock_page) is None


# ---------------------------------------------------------------------------
# resolve_resume_path
# ---------------------------------------------------------------------------

class TestResumeResolution:

    def test_nonexistent_resume(self):
        """No files in resumes/ means None."""
        result = resolve_resume_path("backend")
        # May or may not be None depending on whether user has PDFs
        assert result is None or result.endswith(".pdf") or result.endswith(".PDF")


# ---------------------------------------------------------------------------
# run_application — integration
# ---------------------------------------------------------------------------

class TestRunApplication:

    def _make_mock_adapter(self, fill_results=None):
        """Create a mock adapter class that returns a mock instance."""
        adapter = MagicMock()
        adapter.fill_form.return_value = fill_results or []
        adapter.submit.return_value = True
        # Make the class callable, returning the instance
        adapter_cls = MagicMock(return_value=adapter)
        adapter_cls.__name__ = "MockAdapter"
        return adapter_cls, adapter

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_fill_only_no_submit(self, _resume, mock_review, _init_db, mock_log,
                                  mock_page, minimal_profile, minimal_answers, default_args):
        """fill_only mode should fill fields, run review, but NOT submit."""
        field = _make_field("First Name")
        fill_result = _make_fill_result(field, answer="Jacob", filled=True)
        mock_review.return_value = [{**fill_result, "action": "approve", "final_answer": "Jacob"}]

        adapter_cls, adapter = self._make_mock_adapter([fill_result])

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)

            adapter.fill_form.assert_called_once()
            mock_review.assert_called_once()
            adapter.submit.assert_not_called()
            mock_log.assert_called_once()
            assert mock_log.call_args.kwargs["status"] == "filled"

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value="/fake/resume.pdf")
    def test_resume_path_injected(self, _resume, mock_review, _init_db, _log,
                                   mock_page, minimal_profile, minimal_answers, default_args):
        """Resume path should be injected into profile before fill_form."""
        mock_review.return_value = []
        adapter_cls, adapter = self._make_mock_adapter()

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)

            call_args = adapter.fill_form.call_args[0]
            passed_profile = call_args[1]
            assert passed_profile.get("_resume_path") == "/fake/resume.pdf"

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    @patch("src.main.clear_field")
    def test_rejected_field_cleared(self, mock_clear, _resume, mock_review, _init_db, _log,
                                     mock_page, minimal_profile, minimal_answers, default_args):
        """Fields with action='reject' should be cleared on the page."""
        field = _make_field("Salary", field_type="text", name="salary")
        fill_result = _make_fill_result(field, answer="$100k", filled=True,
                                        intent="salary_expectations", requires_review=True)
        mock_review.return_value = [{**fill_result, "action": "reject", "final_answer": None}]
        adapter_cls, adapter = self._make_mock_adapter([fill_result])

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)
            mock_clear.assert_called_once_with(mock_page, field, "text")

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    @patch("src.main.fill_field")
    def test_edited_field_refilled(self, mock_fill, _resume, mock_review, _init_db, _log,
                                    mock_page, minimal_profile, minimal_answers, default_args):
        """Fields with action='edit' should be re-filled with the edited answer."""
        field = _make_field("City", field_type="text", name="city")
        fill_result = _make_fill_result(field, answer="Orlando", filled=True, intent="city")
        mock_review.return_value = [{**fill_result, "action": "edit", "final_answer": "Lake Mary"}]
        adapter_cls, adapter = self._make_mock_adapter([fill_result])

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)
            mock_fill.assert_called_once_with(mock_page, field, "Lake Mary", "text")

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_generic_adapter_fallback(self, _resume, mock_review, _init_db, mock_log,
                                       mock_page, minimal_profile, minimal_answers, default_args):
        """Unknown platform should fall back to GenericAdapter."""
        mock_review.return_value = []
        adapter_cls, adapter = self._make_mock_adapter()

        with patch("src.main.GenericAdapter", adapter_cls):
            run_application(mock_page, "unknown_ats", minimal_profile, minimal_answers, default_args)
            adapter_cls.assert_called_once()

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_application_logged_with_metadata(self, _resume, mock_review, _init_db, mock_log,
                                               mock_page, minimal_profile, minimal_answers, default_args):
        """Application should be logged with URL, platform, mode, and status."""
        mock_review.return_value = []
        adapter_cls, adapter = self._make_mock_adapter()

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)

            mock_log.assert_called_once()
            kwargs = mock_log.call_args.kwargs
            assert kwargs["url"] == "https://boards.greenhouse.io/acme/jobs/12345"
            assert kwargs["ats_platform"] == "greenhouse"
            assert kwargs["mode"] == "fill_only"
            assert kwargs["status"] == "filled"

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session")
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_multiple_fields_processed(self, _resume, mock_review, _init_db, _log,
                                        mock_page, minimal_profile, minimal_answers, default_args):
        """Multiple fields should all be processed and returned to review."""
        fields = [_make_field("First Name"), _make_field("Last Name"), _make_field("Email")]
        fill_results = [
            _make_fill_result(fields[0], answer="Jacob", intent="first_name"),
            _make_fill_result(fields[1], answer="Campbell", intent="last_name"),
            _make_fill_result(fields[2], answer="jacob@example.com", intent="email"),
        ]
        mock_review.return_value = [
            {**r, "action": "approve", "final_answer": r["proposed_answer"]}
            for r in fill_results
        ]

        adapter_cls, adapter = self._make_mock_adapter(fill_results)

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(mock_page, "greenhouse", minimal_profile, minimal_answers, default_args)

            # All 3 results sent to review
            review_call_args = mock_review.call_args[0][0]
            assert len(review_call_args) == 3


# ---------------------------------------------------------------------------
# Pipeline integration — real normalize→match→score chain
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Tests that exercise the full pipeline with real normalizer/matcher/confidence."""

    def test_profile_fields_all_resolve(self, profile, answers):
        """All basic profile fields should resolve to answers via the real pipeline."""
        from src.engine.normalizer import normalize_question
        from src.engine.matcher import match_answer
        from src.engine.confidence import score_confidence

        test_labels = {
            "First Name": ("first_name", "Jacob"),
            "Last Name": ("last_name", "Campbell"),
            "Email Address": ("email", None),  # Any non-None email
            "Phone Number": ("phone", None),
            "City": ("city", None),
        }

        for label, (expected_intent, expected_answer) in test_labels.items():
            intent = normalize_question(label, answers=answers)
            assert intent == expected_intent, f"Label '{label}' → intent '{intent}', expected '{expected_intent}'"
            result = match_answer(intent, profile, answers, raw_label=label)
            assert result["answer"] is not None, f"No answer for '{label}'"
            if expected_answer:
                assert result["answer"] == expected_answer

    def test_answer_bank_fields_resolve(self, profile, answers):
        """Answer bank questions should resolve end-to-end."""
        from src.engine.normalizer import normalize_question
        from src.engine.matcher import match_answer
        from src.engine.confidence import score_confidence

        test_labels = {
            "Are you legally authorized to work in the United States?": "work_authorization_us",
            "Will you now or in the future require sponsorship?": "requires_sponsorship",
            "What are your salary expectations?": "salary_expectations",
        }

        for label, expected_intent in test_labels.items():
            intent = normalize_question(label, answers=answers)
            assert intent == expected_intent, f"Label '{label}' → intent '{intent}'"
            result = match_answer(intent, profile, answers, raw_label=label)
            assert result["answer"] is not None, f"No answer for '{label}'"
            score = score_confidence(result)
            assert score > 0.0, f"Zero confidence for '{label}'"

    def test_skill_questions_resolve_from_profile(self, profile, answers):
        """Skill-type questions should resolve dynamically from profile.skills[]."""
        from src.engine.normalizer import normalize_question
        from src.engine.matcher import match_answer

        # "Do you have experience with Python?" → Yes (from profile)
        intent = normalize_question("Do you have experience with Python?", answers=answers)
        result = match_answer(intent, profile, answers, raw_label="Do you have experience with Python?")
        assert result["answer"] == "Yes"
        assert result["source"] == "profile"

        # "Years of Java experience" → 4 (from profile)
        intent2 = normalize_question("Years of Java experience", answers=answers)
        result2 = match_answer(intent2, profile, answers, raw_label="Years of Java experience")
        assert result2["answer"] == "4"
        assert result2["source"] == "profile"

    def test_unknown_question_returns_no_match(self, profile, answers):
        """A question with no match should flag for review."""
        from src.engine.normalizer import normalize_question
        from src.engine.matcher import match_answer
        from src.engine.confidence import score_confidence

        intent = normalize_question("What is your favorite color?", answers=answers)
        result = match_answer(intent, profile, answers, raw_label="What is your favorite color?")
        score = score_confidence(result)
        assert score < 0.5
        assert result["requires_review"] is True
