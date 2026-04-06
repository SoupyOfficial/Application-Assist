"""Tests for BaseAdapter (src/adapters/base.py)."""

from unittest.mock import MagicMock, patch, call
import pytest

from src.adapters.base import BaseAdapter, MAX_PAGES, MIN_EXPECTED_FIELDS


# ---------------------------------------------------------------------------
# Concrete subclass for testing (BaseAdapter is abstract)
# ---------------------------------------------------------------------------

class StubAdapter(BaseAdapter):
    """Minimal concrete adapter for testing base class behavior."""

    def __init__(self, fields_per_call=None):
        """
        Args:
            fields_per_call: list of lists — each call to detect_fields
                             returns the next entry. If exhausted, returns [].
        """
        self._fields_per_call = fields_per_call or [[]]
        self._call_idx = 0

    def detect_fields(self, page) -> list:
        if self._call_idx < len(self._fields_per_call):
            fields = self._fields_per_call[self._call_idx]
            self._call_idx += 1
            return fields
        return []


def _make_field(label="First Name", field_type="text"):
    return {
        "locator": MagicMock(),
        "label": label,
        "field_type": field_type,
        "name": label.lower().replace(" ", "_"),
        "required": True,
        "section": "personal_info",
        "options": None,
        "placeholder": None,
    }


@pytest.fixture
def mock_page():
    page = MagicMock()
    return page


# ---------------------------------------------------------------------------
# fill_form — single page
# ---------------------------------------------------------------------------

class TestFillFormSinglePage:

    @patch("src.adapters.base.run_fill_pipeline")
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=False)
    def test_single_page_runs_pipeline_once(self, _mp, _cap, _login, _ready, _frame, mock_pipeline, mock_page):
        """Single-page form: detect_fields → pipeline → return."""
        fields = [_make_field("First Name"), _make_field("Last Name")]
        adapter = StubAdapter(fields_per_call=[fields])
        mock_pipeline.return_value = [{"field": f, "filled": True} for f in fields]

        results = adapter.fill_form(mock_page, {}, {}, "fill_and_pause")

        assert mock_pipeline.call_count == 1
        assert len(results) == 2

    @patch("src.adapters.base.run_fill_pipeline")
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=False)
    def test_no_fields_returns_empty(self, _mp, _cap, _login, _ready, _frame, mock_pipeline, mock_page):
        """If detect_fields returns nothing, pipeline is never called."""
        adapter = StubAdapter(fields_per_call=[[]])

        results = adapter.fill_form(mock_page, {}, {}, "fill_and_pause")

        mock_pipeline.assert_not_called()
        assert results == []


# ---------------------------------------------------------------------------
# fill_form — multi page
# ---------------------------------------------------------------------------

class TestFillFormMultiPage:

    @patch("src.adapters.base.run_fill_pipeline")
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=True)
    @patch("src.adapters.base.is_final_step", return_value=False)
    @patch("src.adapters.base.try_next_page", side_effect=[True, False])
    @patch("src.adapters.base.wait_for_navigation_settle")
    def test_multi_page_loops(self, _settle, _next, _final, _mp, _cap, _login, _ready, _frame, mock_pipeline, mock_page):
        """Multi-page form should call pipeline once per page."""
        page1_fields = [_make_field("First Name")]
        page2_fields = [_make_field("Email")]
        adapter = StubAdapter(fields_per_call=[page1_fields, page2_fields])
        mock_pipeline.side_effect = [
            [{"field": f, "filled": True} for f in page1_fields],
            [{"field": f, "filled": True} for f in page2_fields],
        ]

        results = adapter.fill_form(mock_page, {}, {}, "fill_and_pause")

        assert mock_pipeline.call_count == 2
        assert len(results) == 2

    @patch("src.adapters.base.run_fill_pipeline")
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=True)
    @patch("src.adapters.base.is_final_step", return_value=True)
    def test_stops_at_final_step(self, _final, _mp, _cap, _login, _ready, _frame, mock_pipeline, mock_page):
        """Should stop iterating when is_final_step returns True."""
        fields = [_make_field("Name")]
        adapter = StubAdapter(fields_per_call=[fields])
        mock_pipeline.return_value = [{"field": fields[0], "filled": True}]

        results = adapter.fill_form(mock_page, {}, {}, "fill_and_pause")

        assert mock_pipeline.call_count == 1
        assert len(results) == 1


# ---------------------------------------------------------------------------
# fill_form — blocker detection
# ---------------------------------------------------------------------------

class TestFillFormBlockers:

    @patch("src.adapters.base.run_fill_pipeline", return_value=[])
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=True)
    @patch("src.adapters.base.wait_for_user_to_clear_blocker")
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=False)
    def test_login_wall_triggers_wait(self, _mp, _cap, mock_wait, _login, _ready, _frame, _pipeline, mock_page):
        """Login wall should trigger wait_for_user_to_clear_blocker."""
        adapter = StubAdapter(fields_per_call=[[_make_field()]])
        adapter.fill_form(mock_page, {}, {}, "fill_and_pause")
        mock_wait.assert_called_once()

    @patch("src.adapters.base.run_fill_pipeline", return_value=[])
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=True)
    @patch("src.adapters.base.wait_for_user_to_clear_blocker")
    @patch("src.adapters.base.detect_multi_page", return_value=False)
    def test_captcha_triggers_wait(self, _mp, mock_wait, _cap, _login, _ready, _frame, _pipeline, mock_page):
        """CAPTCHA should trigger wait_for_user_to_clear_blocker."""
        adapter = StubAdapter(fields_per_call=[[_make_field()]])
        adapter.fill_form(mock_page, {}, {}, "fill_and_pause")
        mock_wait.assert_called_once()


# ---------------------------------------------------------------------------
# fill_form — shadow DOM fallback
# ---------------------------------------------------------------------------

class TestShadowDomFallback:

    @patch("src.adapters.base.run_fill_pipeline")
    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.wait_for_page_ready")
    @patch("src.adapters.base.detect_login_wall", return_value=False)
    @patch("src.adapters.base.detect_captcha", return_value=False)
    @patch("src.adapters.base.detect_multi_page", return_value=False)
    @patch("src.adapters.base.discover_fields_with_shadow_dom")
    def test_shadow_dom_used_when_few_fields(self, mock_shadow, _mp, _cap, _login, _ready, _frame, mock_pipeline, mock_page):
        """If detect_fields returns < MIN_EXPECTED_FIELDS and shadow finds more, use shadow results."""
        one_field = [_make_field("Name")]
        shadow_fields = [_make_field("Name"), _make_field("Email"), _make_field("Phone")]
        mock_shadow.return_value = shadow_fields

        adapter = StubAdapter(fields_per_call=[one_field])
        mock_pipeline.return_value = [{"field": f, "filled": True} for f in shadow_fields]

        results = adapter.fill_form(mock_page, {}, {}, "fill_and_pause")

        # Pipeline should receive the shadow fields (3), not original (1)
        pipeline_call_fields = mock_pipeline.call_args[0][1]
        assert len(pipeline_call_fields) == 3


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------

class TestSubmit:

    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.find_and_click_submit", return_value=True)
    def test_submit_delegates_to_helper(self, mock_submit, _frame, mock_page):
        adapter = StubAdapter()
        result = adapter.submit(mock_page)
        assert result is True
        mock_submit.assert_called_once()

    @patch("src.adapters.base.get_form_frame", side_effect=lambda p: p)
    @patch("src.adapters.base.find_and_click_submit", return_value=False)
    def test_submit_returns_false_when_no_button(self, mock_submit, _frame, mock_page):
        adapter = StubAdapter()
        result = adapter.submit(mock_page)
        assert result is False
