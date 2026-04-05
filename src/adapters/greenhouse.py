"""
greenhouse.py — Adapter for Greenhouse ATS forms.

Greenhouse forms are relatively clean and consistent:
  - Standard HTML form with labeled inputs
  - Known CSS structure from the Greenhouse Job Board embeds
  - Fields are typically inside a <div class="field"> wrapper with a <label>
  - Resume upload is a file input; after upload, check for auto-populated fields
  - Submit button is typically: <input type="submit" value="Submit Application">
"""

import sys

from src.adapters.base import BaseAdapter
from src.engine.normalizer import normalize_question
from src.engine.matcher import match_answer
from src.engine.confidence import score_confidence, get_fill_decision
from src.engine.filler import fill_field, get_label_for_input
from src.llm.drafter import draft_answer


class GreenhouseAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """Detect form fields on a Greenhouse application page."""
        fields = []
        field_wrappers = page.locator("#application .field, #application_form .field").all()

        for wrapper in field_wrappers:
            try:
                if not wrapper.is_visible():
                    continue
            except Exception:
                continue

            # Find label
            label_el = wrapper.locator("label").first
            label = label_el.text_content().strip() if label_el.count() > 0 else ""

            # Find the input element
            input_el = None
            field_type = "text"
            options = None

            select = wrapper.locator("select")
            if select.count() > 0:
                input_el = select.first
                field_type = "select"
                options = input_el.locator("option").all_text_contents()
            else:
                textarea = wrapper.locator("textarea")
                if textarea.count() > 0:
                    input_el = textarea.first
                    field_type = "textarea"
                else:
                    file_input = wrapper.locator('input[type="file"]')
                    if file_input.count() > 0:
                        input_el = file_input.first
                        field_type = "file"
                    else:
                        inp = wrapper.locator("input").first
                        if inp.count() > 0:
                            input_el = inp
                            raw_type = (inp.get_attribute("type") or "text").lower()
                            if raw_type == "checkbox":
                                field_type = "checkbox"
                            elif raw_type == "radio":
                                field_type = "radio"
                            elif raw_type == "date":
                                field_type = "date"

            if input_el is None:
                continue

            name = input_el.get_attribute("name") or input_el.get_attribute("id") or ""
            required = wrapper.locator(".required").count() > 0 or input_el.get_attribute("required") is not None

            fields.append({
                "locator": input_el,
                "label": label,
                "field_type": field_type,
                "name": name,
                "required": required,
                "section": _guess_gh_section(label, name),
                "options": options,
                "placeholder": input_el.get_attribute("placeholder") if field_type != "select" else None,
            })

        return fields

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """Fill a Greenhouse application form."""
        fields = self.detect_fields(page)
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
                        page.wait_for_timeout(2000)
                        # Re-detect after upload
                        fields = self.detect_fields(page)
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

    def submit(self, page) -> bool:
        """Submit the Greenhouse application."""
        selectors = [
            'input[type="submit"][value*="Submit"]',
            'button:has-text("Submit Application")',
            'button:has-text("Submit")',
            '#submit_app',
        ]
        for sel in selectors:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle")
                return True
        print("[warn] Greenhouse: could not find submit button.", file=sys.stderr)
        return False


def _guess_gh_section(label: str, name: str) -> str:
    """Guess the section from Greenhouse field label/name."""
    combined = (label + " " + name).lower()
    if any(kw in combined for kw in ["name", "email", "phone", "linkedin", "github", "website"]):
        return "personal_info"
    if any(kw in combined for kw in ["resume", "cv", "file"]):
        return "resume"
    if any(kw in combined for kw in ["cover", "letter"]):
        return "cover_letter"
    if any(kw in combined for kw in ["gender", "race", "veteran", "disability"]):
        return "demographics"
    return "custom"
