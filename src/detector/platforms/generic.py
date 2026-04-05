"""
generic.py — Generic fallback ATS detection and form field discovery.

Used when no specific platform is identified by URL or DOM markers.
Falls back to Playwright-based form discovery: find all visible input
fields, labels, and select elements, and attempt best-effort filling.
"""

from src.engine.filler import get_label_for_input

PLATFORM_NAME = "generic"


def matches_url(url: str) -> bool:
    """Generic never matches by URL — it is always the fallback."""
    return False


def detect_from_dom(page) -> bool:
    """Generic never positively matches by DOM — it is always the fallback."""
    return False


def _guess_section(label: str) -> str:
    """Guess the logical section from the label text."""
    label_lower = label.lower()
    if any(kw in label_lower for kw in ["name", "email", "phone", "address", "city", "zip", "linkedin", "github"]):
        return "personal_info"
    if any(kw in label_lower for kw in ["authorized", "sponsorship", "visa", "work permit", "citizen"]):
        return "work_auth"
    if any(kw in label_lower for kw in ["resume", "cv", "upload"]):
        return "resume"
    if any(kw in label_lower for kw in ["gender", "race", "ethnicity", "veteran", "disability", "demographic"]):
        return "demographics"
    if any(kw in label_lower for kw in ["salary", "compensation", "pay"]):
        return "compensation"
    return "custom"


def _categorize_input_type(input_el) -> str:
    """Categorize the input type from the HTML type attribute."""
    raw_type = (input_el.get_attribute("type") or "text").lower()
    type_map = {
        "text": "text", "email": "text", "tel": "text", "url": "text",
        "number": "text", "password": "text",
        "date": "date", "datetime-local": "date", "month": "date",
        "file": "file",
        "checkbox": "checkbox",
        "radio": "radio",
    }
    return type_map.get(raw_type, "text")


def discover_fields(page) -> list:
    """
    Discover all fillable form fields on the page using Playwright.

    Returns a list of field descriptor dicts with: locator, label, field_type,
    name, required, section, options, placeholder.
    """
    fields = []

    # --- Text-like inputs ---
    text_selector = (
        'input[type="text"], input[type="email"], input[type="tel"], '
        'input[type="url"], input[type="number"], input[type="date"], '
        'input:not([type])'
    )
    for input_el in page.locator(text_selector).all():
        try:
            if not input_el.is_visible():
                continue
        except Exception:
            continue
        label = get_label_for_input(page, input_el)
        fields.append({
            "locator":     input_el,
            "label":       label,
            "field_type":  _categorize_input_type(input_el),
            "name":        input_el.get_attribute("name") or input_el.get_attribute("id") or "",
            "required":    input_el.get_attribute("required") is not None or input_el.get_attribute("aria-required") == "true",
            "section":     _guess_section(label),
            "options":     None,
            "placeholder": input_el.get_attribute("placeholder"),
        })

    # --- Textareas ---
    for textarea in page.locator("textarea").all():
        try:
            if not textarea.is_visible():
                continue
        except Exception:
            continue
        label = get_label_for_input(page, textarea)
        fields.append({
            "locator":     textarea,
            "label":       label,
            "field_type":  "textarea",
            "name":        textarea.get_attribute("name") or textarea.get_attribute("id") or "",
            "required":    textarea.get_attribute("required") is not None,
            "section":     _guess_section(label),
            "options":     None,
            "placeholder": textarea.get_attribute("placeholder"),
        })

    # --- Select dropdowns ---
    for select in page.locator("select").all():
        try:
            if not select.is_visible():
                continue
        except Exception:
            continue
        label = get_label_for_input(page, select)
        options = select.locator("option").all_text_contents()
        fields.append({
            "locator":     select,
            "label":       label,
            "field_type":  "select",
            "name":        select.get_attribute("name") or select.get_attribute("id") or "",
            "required":    select.get_attribute("required") is not None,
            "section":     _guess_section(label),
            "options":     options,
            "placeholder": None,
        })

    # --- Radio groups (grouped by name to avoid duplicates) ---
    radio_names_seen = set()
    for radio in page.locator('input[type="radio"]').all():
        name = radio.get_attribute("name")
        if name in radio_names_seen:
            continue
        try:
            if not radio.is_visible():
                continue
        except Exception:
            continue
        radio_names_seen.add(name)
        label = get_label_for_input(page, radio)
        # Collect all option labels for this radio group
        group_radios = page.locator(f'input[type="radio"][name="{name}"]').all()
        options = [get_label_for_input(page, r) for r in group_radios]
        fields.append({
            "locator":     radio,
            "label":       label,
            "field_type":  "radio",
            "name":        name or "",
            "required":    radio.get_attribute("required") is not None,
            "section":     _guess_section(label),
            "options":     options,
            "placeholder": None,
        })

    # --- Checkboxes ---
    for checkbox in page.locator('input[type="checkbox"]').all():
        try:
            if not checkbox.is_visible():
                continue
        except Exception:
            continue
        label = get_label_for_input(page, checkbox)
        fields.append({
            "locator":     checkbox,
            "label":       label,
            "field_type":  "checkbox",
            "name":        checkbox.get_attribute("name") or "",
            "required":    checkbox.get_attribute("required") is not None,
            "section":     _guess_section(label),
            "options":     None,
            "placeholder": None,
        })

    # --- File inputs ---
    for file_input in page.locator('input[type="file"]').all():
        label = get_label_for_input(page, file_input)
        fields.append({
            "locator":     file_input,
            "label":       label or "Resume/Document Upload",
            "field_type":  "file",
            "name":        file_input.get_attribute("name") or "",
            "required":    file_input.get_attribute("required") is not None,
            "section":     "resume",
            "options":     None,
            "placeholder": None,
        })

    return fields
