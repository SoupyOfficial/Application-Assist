"""
filler.py — Playwright form field filling.

Handles filling individual form fields using Playwright locators.
Supports: text inputs, select dropdowns, radio buttons, checkboxes,
          date inputs, file uploads, and textarea fields.

After any file upload (resume), the caller should re-scan fields
because many ATS platforms auto-populate fields from the parsed resume.
"""

from rapidfuzz import fuzz, process
import sys


def fill_field(page, field_descriptor: dict, answer: str, field_type: str) -> bool:
    """
    Fill a single form field using Playwright.

    Args:
        page:             Playwright Page object.
        field_descriptor: Field descriptor dict containing 'locator', 'name', 'label', etc.
        answer:           The string answer to fill in.
        field_type:       One of: "text", "select", "radio", "checkbox", "date", "file", "textarea".

    Returns:
        True if the field was filled successfully, False otherwise.
    """
    locator = field_descriptor["locator"]

    try:
        if field_type in ("text", "textarea"):
            locator.clear()
            locator.fill(answer)
            return True

        elif field_type == "select":
            # Try exact label match first
            try:
                locator.select_option(label=answer)
                return True
            except Exception:
                pass
            # Fuzzy: get all options, find closest match
            options = locator.locator("option").all_text_contents()
            best = find_best_option_match(answer, options)
            if best:
                locator.select_option(label=best)
                return True
            return False

        elif field_type == "radio":
            name = field_descriptor.get("name", "")
            if not name:
                print(f"[warn] Radio field '{field_descriptor.get('label', '?')}' has no name attribute — skipping", file=sys.stderr)
                return False
            # Escape CSS special chars in name attribute
            escaped_name = name.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")
            radios = page.locator(f'input[type="radio"][name="{escaped_name}"]').all()
            # Exact label match pass
            for radio in radios:
                label = get_label_for_input(page, radio)
                if label.lower().strip() == answer.lower().strip():
                    radio.check()
                    return True
            # Fuzzy label match pass
            labels = [get_label_for_input(page, r) for r in radios]
            best_idx = _find_best_label_index(answer, labels)
            if best_idx is not None:
                radios[best_idx].check()
                return True
            return False

        elif field_type == "checkbox":
            truthy = answer.lower() in ("yes", "true", "1", "checked")
            if truthy:
                locator.check()
            else:
                locator.uncheck()
            return True

        elif field_type == "date":
            locator.fill(answer)
            return True

        elif field_type == "file":
            locator.set_input_files(answer)
            return True

        else:
            # Unknown type — best effort
            locator.fill(answer)
            return True

    except Exception as e:
        print(f"[warn] Failed to fill field '{field_descriptor.get('label', '?')}': {e}", file=sys.stderr)
        return False


def clear_field(page, field_descriptor: dict, field_type: str):
    """Clear a previously filled field (used when user rejects an answer)."""
    locator = field_descriptor["locator"]
    try:
        if field_type in ("text", "textarea", "date"):
            locator.clear()
        elif field_type == "select":
            locator.select_option(index=0)
        elif field_type == "checkbox":
            locator.uncheck()
        elif field_type == "file":
            locator.set_input_files([])
        # radio: can't be unchecked in standard HTML; skip
    except Exception as e:
        print(f"[warn] Failed to clear field '{field_descriptor.get('label', '?')}': {e}", file=sys.stderr)


def find_best_option_match(answer: str, options: list) -> str | None:
    """
    Find the best matching option text for a select dropdown.

    Returns the best matching option text, or None if no match is good enough.
    """
    if not options:
        return None

    answer_lower = answer.lower().strip()

    # Exact case-insensitive match
    for option in options:
        if option.lower().strip() == answer_lower:
            return option

    # Prefix match
    for option in options:
        if option.lower().strip().startswith(answer_lower):
            return option

    # Fuzzy match
    result = process.extractOne(answer, options, score_cutoff=60)
    if result:
        return result[0]

    return None


def get_label_for_input(page, input_locator) -> str:
    """
    Find the visible label text associated with a given input element.
    Tries multiple strategies: for attribute, wrapping label, aria-label,
    aria-labelledby, and placeholder.
    """
    try:
        # 1. Check for <label for="id">
        input_id = input_locator.get_attribute("id")
        if input_id:
            label_el = page.locator(f'label[for="{input_id}"]')
            if label_el.count() > 0:
                return label_el.first.text_content().strip()

        # 2. Check for wrapping <label>
        parent_label = input_locator.locator("xpath=ancestor::label")
        if parent_label.count() > 0:
            return parent_label.first.text_content().strip()

        # 3. Check aria-label
        aria = input_locator.get_attribute("aria-label")
        if aria:
            return aria.strip()

        # 4. Check aria-labelledby
        labelledby = input_locator.get_attribute("aria-labelledby")
        if labelledby:
            label_el = page.locator(f"#{labelledby}")
            if label_el.count() > 0:
                return label_el.first.text_content().strip()

        # 5. Placeholder fallback
        placeholder = input_locator.get_attribute("placeholder")
        if placeholder:
            return placeholder.strip()
    except Exception:
        pass

    return ""


def _find_best_label_index(answer: str, labels: list) -> int | None:
    """Find the index of the best fuzzy-matching label."""
    answer_lower = answer.lower().strip()
    best_score = 0.0
    best_idx = None
    for i, label in enumerate(labels):
        if not label:
            continue
        score = fuzz.ratio(answer_lower, label.lower().strip()) / 100.0
        if score > best_score:
            best_score = score
            best_idx = i
    if best_score >= 0.6 and best_idx is not None:
        return best_idx
    return None
