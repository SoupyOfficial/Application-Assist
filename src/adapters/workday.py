"""
workday.py — Adapter for Workday ATS forms.

Workday is the most complex target in this project:
  - Multi-step wizard (each step is a separate page/section)
  - React/Angular SPA — no stable static DOM structure
  - Heavily uses data-automation-id attributes on form elements
  - Resume upload in step 1 triggers auto-population across all steps

Known data-automation-id patterns:
  - "legalNameSection_firstName", "legalNameSection_lastName"
  - "email", "phone-device-type", "phoneNumber"
  - "bottom-navigation-next-button" (Next/Continue)
"""

import sys

from src.adapters.base import BaseAdapter
from src.adapters.pipeline import run_fill_pipeline
from src.engine.filler import fill_field, get_label_for_input
from src.browser.helpers import wait_for_navigation_settle


class WorkdayAdapter(BaseAdapter):

    # Workday is always multi-step
    multi_page = True

    def detect_fields(self, page) -> list:
        """Detect form fields on the current Workday step/page using data-automation-id."""
        fields = []

        # Primary strategy: data-automation-id inputs
        auto_inputs = page.locator("[data-automation-id] input, [data-automation-id] select, [data-automation-id] textarea").all()
        seen_names = set()

        for el in auto_inputs:
            try:
                if not el.is_visible():
                    continue
            except Exception:
                continue

            name = el.get_attribute("data-automation-id") or el.get_attribute("name") or el.get_attribute("id") or ""
            if name in seen_names:
                continue
            seen_names.add(name)

            tag = el.evaluate("el => el.tagName.toLowerCase()")
            label = get_label_for_input(page, el)

            field_type = "text"
            options = None
            if tag == "select":
                field_type = "select"
                options = el.locator("option").all_text_contents()
            elif tag == "textarea":
                field_type = "textarea"
            else:
                raw_type = (el.get_attribute("type") or "text").lower()
                type_map = {"checkbox": "checkbox", "radio": "radio", "date": "date", "file": "file"}
                field_type = type_map.get(raw_type, "text")

            fields.append({
                "locator": el,
                "label": label,
                "field_type": field_type,
                "name": name,
                "required": el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true",
                "section": _guess_wd_step(page),
                "options": options,
                "placeholder": el.get_attribute("placeholder"),
            })

        # Also scan for file inputs (often hidden in Workday)
        file_inputs = page.locator('input[type="file"]').all()
        for fi in file_inputs:
            name = fi.get_attribute("data-automation-id") or fi.get_attribute("name") or "file_upload"
            if name not in seen_names:
                fields.append({
                    "locator": fi,
                    "label": "Resume/Document Upload",
                    "field_type": "file",
                    "name": name,
                    "required": False,
                    "section": "resume",
                    "options": None,
                    "placeholder": None,
                })

        # Fall back to generic if data-automation-id strategy yields nothing
        if not fields:
            from src.detector.platforms.generic import discover_fields
            fields = discover_fields(page)

        return fields

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """Fill a Workday application — multi-step orchestration."""
        all_results = []

        # Process up to 10 steps (safety limit)
        for step_num in range(10):
            print(f"[info] Workday: processing step {step_num + 1}")

            try:
                fields = self.detect_fields(page)
            except Exception as e:
                print(f"[warn] Workday: detect_fields failed on step {step_num + 1}: {e}")
                break

            if not fields:
                print("[info] Workday: no fields on current step, checking for next")
                if not self._try_next_step(page):
                    break
                continue

            try:
                step_results = self._fill_step(page, fields, profile, answers, mode)
                all_results.extend(step_results)
            except Exception as e:
                print(f"[warn] Workday: fill failed on step {step_num + 1}: {e}")
                break

            # Check if we're on the review/submit step
            if self._is_review_step(page):
                print("[info] Workday: reached review step")
                break

            # Try to advance to next step
            if not self._try_next_step(page):
                break

        return all_results

    def _fill_step(self, page, fields, profile, answers, mode) -> list:
        """Fill fields on a single Workday step using the shared pipeline."""
        return run_fill_pipeline(
            page, fields, profile, answers, mode,
            resume_wait_ms=3000,
            redetect_after_upload=lambda p: self.detect_fields(p),
        )

    def _try_next_step(self, page) -> bool:
        """Click the Next/Continue button to advance to the next Workday step."""
        selectors = [
            '[data-automation-id="bottom-navigation-next-button"]',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Save and Continue")',
        ]
        for sel in selectors:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                wait_for_navigation_settle(page)
                return True
        return False

    def _is_review_step(self, page) -> bool:
        """Check if the current step is the final review/submit step."""
        heading = page.locator("h2, h3, [data-automation-id*='review'], [data-automation-id*='summary']")
        for el in heading.all():
            text = (el.text_content() or "").lower()
            if any(kw in text for kw in ["review", "summary", "submit"]):
                return True
        return False

    def submit(self, page) -> bool:
        """Submit the Workday application from the Review step."""
        selectors = [
            '[data-automation-id="bottom-navigation-next-button"]',
            'button:has-text("Submit")',
            'button:has-text("Submit Application")',
        ]
        for sel in selectors:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle")
                return True
        print("[warn] Workday: could not find submit button.", file=sys.stderr)
        return False


def _guess_wd_step(page) -> str:
    """Guess the current Workday step from headings."""
    headings = page.locator("h2, h3").all()
    for h in headings:
        text = (h.text_content() or "").lower()
        if "information" in text or "contact" in text:
            return "personal_info"
        if "experience" in text:
            return "experience"
        if "question" in text:
            return "custom"
        if "voluntary" in text or "disclosure" in text:
            return "demographics"
    return "custom"
