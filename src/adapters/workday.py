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
from src.engine.normalizer import normalize_question
from src.engine.matcher import match_answer
from src.engine.confidence import score_confidence, get_fill_decision
from src.engine.filler import fill_field, get_label_for_input
from src.llm.drafter import draft_answer


class WorkdayAdapter(BaseAdapter):

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

            fields = self.detect_fields(page)
            if not fields:
                print("[info] Workday: no fields on current step, checking for next")
                if not self._try_next_step(page):
                    break
                continue

            step_results = self._fill_step(page, fields, profile, answers, mode)
            all_results.extend(step_results)

            # Check if we're on the review/submit step
            if self._is_review_step(page):
                print("[info] Workday: reached review step")
                break

            # Try to advance to next step
            if not self._try_next_step(page):
                break

        return all_results

    def _fill_step(self, page, fields, profile, answers, mode) -> list:
        """Fill fields on a single Workday step."""
        results = []

        for field in fields:
            label = field.get("label", "")
            field_type = field.get("field_type", "text")
            context = field.get("section", "")

            if field_type == "file":
                resume_path = profile.get("_resume_path")
                if resume_path:
                    filled = fill_field(page, field, resume_path, "file")
                    results.append({
                        "field": field, "proposed_answer": resume_path,
                        "confidence": 1.0, "source": "profile",
                        "requires_review": False, "filled": filled,
                    })
                    if filled:
                        page.wait_for_timeout(3000)
                continue

            intent = normalize_question(label, profile, context)
            match_result = match_answer(intent, profile, answers)
            answer = match_result.get("answer") or match_result.get("answer_long")
            source = match_result.get("source", "none")

            if not answer and field_type in ("textarea",):
                answer = draft_answer(label, profile, context)
                if answer:
                    source = "llm"
                    match_result["confidence"] = "medium"
                    match_result["requires_review"] = True

            score = score_confidence(match_result)
            decision = get_fill_decision(score, match_result, profile)

            filled = False
            if answer and decision in ("auto_fill", "fill_and_flag"):
                filled = fill_field(page, field, str(answer), field_type)

            results.append({
                "field": field, "proposed_answer": answer,
                "confidence": score, "source": source,
                "requires_review": match_result.get("requires_review", False) or decision == "fill_and_flag",
                "filled": filled, "intent": intent,
                "notes": match_result.get("notes", ""),
            })

        return results

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
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)
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
