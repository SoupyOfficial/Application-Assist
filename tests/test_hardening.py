"""Tests for new hardening fixes: validation, retry, DB path, error handling."""

from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import pytest
import sqlite3

from src.main import validate_profile, validate_answers
from src.tracker.db import DB_PATH, _get_connection, init_db


# ---------------------------------------------------------------------------
# Profile / answers validation
# ---------------------------------------------------------------------------

class TestValidateProfile:

    def test_valid_profile(self, profile):
        """Valid profile should not exit."""
        validate_profile(profile)  # No exception

    def test_missing_identity(self):
        """Missing 'identity' should exit."""
        with pytest.raises(SystemExit):
            validate_profile({"location": {}, "links": {}, "work_authorization": {}, "skills": []})

    def test_missing_skills(self):
        """Missing 'skills' should exit."""
        with pytest.raises(SystemExit):
            validate_profile({
                "identity": {"legal_first_name": "A", "legal_last_name": "B", "email": "a@b.com"},
                "location": {}, "links": {}, "work_authorization": {},
            })

    def test_missing_identity_email(self):
        """Missing 'email_primary' inside identity should exit."""
        with pytest.raises(SystemExit):
            validate_profile({
                "identity": {"legal_first_name": "A", "legal_last_name": "B"},
                "location": {}, "links": {}, "work_authorization": {}, "skills": [],
            })

    def test_missing_multiple_keys(self):
        """Multiple missing keys should exit."""
        with pytest.raises(SystemExit):
            validate_profile({})


class TestValidateAnswers:

    def test_valid_answers(self, answers):
        """Valid answers should not exit."""
        validate_answers(answers)  # No exception

    def test_missing_answers_key(self):
        """Missing 'answers' key should exit."""
        with pytest.raises(SystemExit):
            validate_answers({"entries": []})

    def test_answers_not_list(self):
        """'answers' not a list should exit."""
        with pytest.raises(SystemExit):
            validate_answers({"answers": "not a list"})

    def test_empty_dict(self):
        """Empty dict should exit."""
        with pytest.raises(SystemExit):
            validate_answers({})


# ---------------------------------------------------------------------------
# DB path is absolute
# ---------------------------------------------------------------------------

class TestDBPath:

    def test_db_path_is_absolute(self):
        """DB_PATH should be an absolute path."""
        assert Path(DB_PATH).is_absolute()

    def test_db_path_ends_with_applications_db(self):
        """DB_PATH should end with applications.db."""
        assert DB_PATH.endswith("applications.db")


# ---------------------------------------------------------------------------
# SQLite WAL + busy_timeout
# ---------------------------------------------------------------------------

class TestDBConnection:

    def test_wal_mode(self, tmp_path, monkeypatch):
        """Connection should use WAL journal mode."""
        monkeypatch.setattr("src.tracker.db.DB_PATH", str(tmp_path / "test.db"))
        init_db()
        conn = _get_connection()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_busy_timeout(self, tmp_path, monkeypatch):
        """Connection should have busy_timeout set."""
        monkeypatch.setattr("src.tracker.db.DB_PATH", str(tmp_path / "test.db"))
        conn = _get_connection()
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000
        conn.close()

    def test_date_index_created(self, tmp_path, monkeypatch):
        """init_db should create an index on the date column."""
        monkeypatch.setattr("src.tracker.db.DB_PATH", str(tmp_path / "test.db"))
        init_db()
        conn = _get_connection()
        indices = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_applications_date'"
        ).fetchall()
        assert len(indices) == 1
        conn.close()


# ---------------------------------------------------------------------------
# LLM retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:

    @patch("src.llm.retry.time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep):
        """Should retry on RateLimitError and eventually succeed."""
        import anthropic
        from src.llm.retry import call_with_retry

        client = MagicMock()
        client.messages.create.side_effect = [
            anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            MagicMock(content=[MagicMock(text="OK")]),
        ]

        result = call_with_retry(client, model="test", max_tokens=10, messages=[])
        assert result.content[0].text == "OK"
        assert client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    def test_raises_auth_error_immediately(self):
        """Should not retry on AuthenticationError."""
        import anthropic
        from src.llm.retry import call_with_retry

        client = MagicMock()
        client.messages.create.side_effect = anthropic.AuthenticationError(
            message="invalid key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )

        with pytest.raises(anthropic.AuthenticationError):
            call_with_retry(client, model="test", max_tokens=10, messages=[])

        assert client.messages.create.call_count == 1

    @patch("src.llm.retry.time.sleep")
    def test_exhausts_retries(self, mock_sleep):
        """Should raise after MAX_RETRIES rate limit failures."""
        import anthropic
        from src.llm.retry import call_with_retry, MAX_RETRIES

        client = MagicMock()
        client.messages.create.side_effect = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )

        with pytest.raises(anthropic.RateLimitError):
            call_with_retry(client, model="test", max_tokens=10, messages=[])

        assert client.messages.create.call_count == MAX_RETRIES


# ---------------------------------------------------------------------------
# Filler radio CSS escape
# ---------------------------------------------------------------------------

class TestRadioCSS:

    def test_radio_empty_name_skipped(self):
        """Radio with empty name should return False."""
        from src.engine.filler import fill_field
        page = MagicMock()
        field = {"locator": MagicMock(), "name": "", "label": "Gender"}
        assert fill_field(page, field, "Male", "radio") is False

    def test_radio_special_chars_in_name(self):
        """Radio with special chars in name should not crash."""
        from src.engine.filler import fill_field
        page = MagicMock()
        page.locator.return_value.all.return_value = []
        field = {"locator": MagicMock(), "name": 'answer["q1"]', "label": "Option"}
        # Should not crash, just return False (no matching radios)
        assert fill_field(page, field, "Yes", "radio") is False


# ---------------------------------------------------------------------------
# Error handling in run_application
# ---------------------------------------------------------------------------

class TestRunApplicationErrors:

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session", return_value=[])
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_fill_form_crash_logs_error(self, _resume, _review, _init_db, mock_log,
                                         minimal_profile, minimal_answers):
        """If fill_form crashes, should log as 'error' status."""
        from argparse import Namespace
        from src.main import run_application

        args = Namespace(
            url="https://example.com/apply", mode="fill_only",
            resume="backend", cover_letter=False, company=None, role=None, dry_run=False,
        )
        page = MagicMock()
        page.title.return_value = "Job - Company"

        adapter_cls = MagicMock(__name__="CrashAdapter")
        adapter = adapter_cls.return_value
        adapter.fill_form.side_effect = RuntimeError("browser crashed")

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(page, "greenhouse", minimal_profile, minimal_answers, args)

        assert mock_log.call_args.kwargs["status"] == "error"

    @patch("src.main.log_application")
    @patch("src.main.init_db")
    @patch("src.main.review_session", return_value=[])
    @patch("src.main.resolve_resume_path", return_value=None)
    def test_fill_form_crash_still_shows_review(self, _resume, mock_review, _init_db, _log,
                                                  minimal_profile, minimal_answers):
        """If fill_form crashes, should still call review_session with partial results."""
        from argparse import Namespace
        from src.main import run_application

        args = Namespace(
            url="https://example.com/apply", mode="fill_only",
            resume="backend", cover_letter=False, company=None, role=None, dry_run=False,
        )
        page = MagicMock()
        page.title.return_value = "Job - Company"

        adapter_cls = MagicMock(__name__="CrashAdapter")
        adapter = adapter_cls.return_value
        adapter.fill_form.side_effect = RuntimeError("timeout")

        with patch.dict("src.main.ADAPTER_MAP", {"greenhouse": adapter_cls}):
            run_application(page, "greenhouse", minimal_profile, minimal_answers, args)

        mock_review.assert_called_once_with([])
