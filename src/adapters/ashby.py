"""
ashby.py — Adapter for Ashby ATS forms.

Ashby is a modern ATS with a clean React-based UI:
  - Growing adoption among newer/modern tech startups
  - Form structure is relatively clean compared to Workday
  - Uses React components — may need careful locator strategies
"""

import sys

from src.adapters.base import BaseAdapter
from src.engine.normalizer import normalize_question
from src.engine.matcher import match_answer
from src.engine.confidence import score_confidence, get_fill_decision
from src.engine.filler import fill_field, get_label_for_input
from src.llm.drafter import draft_answer


class AshbyAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """Detect form fields on an Ashby application page."""
        fields = []

        # Ashby uses form groups with labels
        for container_sel in [".ashby-application-form-field-entry", "[data-ashby] .field", "form .form-field"]:
            containers = page.locator(container_sel).all()
            for container in containers:
                try:
                    if not container.is_visible():
                        continue
                except Exception:
                    continue

                label_el = container.locator("label").first
                label = label_el.text_content().strip() if label_el.count() > 0 else ""

                input_el = None
                field_type = "text"
                options = None

                select = container.locator("select")
                if select.count() > 0:
                    input_el = select.first
                    field_type = "select"
                    options = input_el.locator("option").all_text_contents()
                else:
                    textarea = container.locator("textarea")
                    if textarea.count() > 0:
                        input_el = textarea.first
                        field_type = "textarea"
                    else:
                        file_input = container.locator('input[type="file"]')
                        if file_input.count() > 0:
                            input_el = file_input.first
                            field_type = "file"
                        else:
                            inp = container.locator("input").first
                            if inp.count() > 0:
                                input_el = inp
                                raw_type = (inp.get_attribute("type") or "text").lower()
                                type_map = {"checkbox": "checkbox", "radio": "radio", "date": "date"}
                                field_type = type_map.get(raw_type, "text")

                if input_el is None:
                    continue

                name = input_el.get_attribute("name") or input_el.get_attribute("id") or ""

                fields.append({
                    "locator": input_el,
                    "label": label,
                    "field_type": field_type,
                    "name": name,
                    "required": input_el.get_attribute("required") is not None,
                    "section": "custom",
                    "options": options,
                    "placeholder": input_el.get_attribute("placeholder") if field_type not in ("select", "file") else None,
                })

        # Fall back to generic discovery if Ashby-specific selectors missed
        if not fields:
            from src.detector.platforms.generic import discover_fields
            fields = discover_fields(page)

        return fields

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """Fill an Ashby application form."""
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
        """Submit the Ashby application."""
        selectors = [
            'button:has-text("Submit")',
            'button:has-text("Submit Application")',
            'button[type="submit"]',
        ]
        for sel in selectors:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle")
                return True
        print("[warn] Ashby: could not find submit button.", file=sys.stderr)
        return False
