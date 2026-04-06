"""
lever.py — Adapter for Lever ATS forms.

Lever application forms:
  - Single-page form with labeled inputs
  - Consistent structure across companies
  - Resume upload triggers field auto-population
  - Custom questions vary per job posting
"""

import sys

from src.adapters.base import BaseAdapter


class LeverAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """Detect form fields on a Lever application page."""
        fields = []

        # Lever wraps fields in .application-question or similar containers
        for container_sel in [".application-question", ".application-field", ".lever-application-form .field"]:
            containers = page.locator(container_sel).all()
            for container in containers:
                try:
                    if not container.is_visible():
                        continue
                except Exception:
                    continue

                label_el = container.locator("label, .question-label, .field-label").first
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

        # Fall back to generic discovery if no Lever-specific fields found
        if not fields:
            from src.detector.platforms.generic import discover_fields
            fields = discover_fields(page)

        return fields

    # fill_form() inherited from BaseAdapter (multi-page aware, shared pipeline)

    def submit(self, page) -> bool:
        """Submit the Lever application."""
        selectors = [
            'button:has-text("Submit application")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            '.postings-btn-submit',
        ]
        for sel in selectors:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle")
                return True
        print("[warn] Lever: could not find submit button.", file=sys.stderr)
        return False
