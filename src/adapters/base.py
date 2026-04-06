"""
base.py — Abstract base class for ATS platform adapters.

All platform-specific adapters must subclass BaseAdapter and implement
the core methods.  Provides a default multi-page fill orchestration that
works for common cases; platform adapters can override for custom logic.
"""

from abc import ABC, abstractmethod

from src.adapters.pipeline import run_fill_pipeline
from src.browser.helpers import (
    wait_for_page_ready,
    wait_for_navigation_settle,
    detect_login_wall,
    detect_captcha,
    wait_for_user_to_clear_blocker,
    get_form_frame,
    discover_fields_with_shadow_dom,
    detect_multi_page,
    try_next_page,
    is_final_step,
    find_and_click_submit,
)


# Maximum number of pages/steps to iterate through before giving up
MAX_PAGES = 15

# Minimum number of fields we expect; below this we try shadow DOM
MIN_EXPECTED_FIELDS = 2


class BaseAdapter(ABC):
    """
    Abstract adapter interface for a single ATS platform.

    Each adapter is responsible for:
      1. Detecting/extracting fields from the live Playwright page.
      2. Orchestrating the fill process (calling the fill engine per field).
      3. Submitting the form when authorized by the mode and review UI.

    The base class provides a default multi-page ``fill_form()`` that:
      - detects iframes and switches context automatically
      - detects login walls / CAPTCHAs and pauses for the user
      - loops through pages calling detect_fields → pipeline → next
      - can be overridden completely by platform adapters
    """

    # Subclasses can set this to True if the platform is always multi-page
    multi_page: bool = False

    @abstractmethod
    def detect_fields(self, page) -> list:
        """
        Scan the current page/frame and return a list of field descriptors.

        Args:
            page: Playwright Page or Frame object.

        Returns:
            List of field descriptor dicts, each containing at minimum:
              {
                "locator":    <Playwright Locator>,
                "label":      <string — visible label text>,
                "field_type": <"text" | "select" | "radio" | "checkbox" | "file" | "date">,
                "name":       <input name or id attribute>,
                "required":   <bool>,
                "section":    <string — logical section name>,
              }
        """
        raise NotImplementedError

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Default multi-page-aware fill orchestration.

        1. Resolve iframe context
        2. Check for login wall / CAPTCHA
        3. Loop: detect → fill → next page  (single-page forms exit after 1 iteration)
        4. Return aggregated results for review UI

        Platform adapters may override this entirely (e.g. Workday).
        """
        # --- resolve iframe context -----------------------------------------
        frame = get_form_frame(page)

        # --- blocker detection -----------------------------------------------
        if detect_login_wall(frame):
            wait_for_user_to_clear_blocker(frame, "login wall")
        if detect_captcha(frame):
            wait_for_user_to_clear_blocker(frame, "CAPTCHA")

        wait_for_page_ready(frame)

        # --- determine if multi-page ----------------------------------------
        is_multi = self.multi_page or detect_multi_page(frame)
        all_results: list = []

        for step_num in range(MAX_PAGES):
            fields = self.detect_fields(frame)

            # Shadow DOM fallback if we found suspiciously few fields
            if len(fields) < MIN_EXPECTED_FIELDS:
                shadow_fields = discover_fields_with_shadow_dom(frame)
                if len(shadow_fields) > len(fields):
                    fields = shadow_fields

            if not fields and is_multi:
                # Possibly a blank interstitial; try advancing
                if try_next_page(frame):
                    wait_for_navigation_settle(frame)
                    continue
                break

            if not fields:
                break

            step_results = run_fill_pipeline(
                frame, fields, profile, answers, mode,
                redetect_after_upload=lambda p: self.detect_fields(p),
            )
            all_results.extend(step_results)

            # If single-page, we're done after one pass
            if not is_multi:
                break

            # If multi-page, check for final step or try to advance
            if is_final_step(frame):
                print("[info] Reached final review/submit step.")
                break

            if not try_next_page(frame):
                break

            wait_for_navigation_settle(frame)

        return all_results

    def submit(self, page) -> bool:
        """
        Default submit implementation using the shared button finder.

        Platform adapters should override this with their specific selectors.
        """
        frame = get_form_frame(page)
        return find_and_click_submit(frame)
