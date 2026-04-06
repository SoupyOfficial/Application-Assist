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
from src.engine.filler import get_label_for_input


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

    # fill_form() inherited from BaseAdapter (multi-page aware, shared pipeline)

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
