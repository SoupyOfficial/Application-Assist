"""
filler.py — Playwright form field filling.

Handles filling individual form fields using Playwright locators.
Supports: text inputs, select dropdowns, radio buttons, checkboxes,
          date inputs, file uploads, and textarea fields.

After any file upload (resume), the caller should re-scan fields
because many ATS platforms auto-populate fields from the parsed resume.
"""


def fill_field(page, field_locator, answer: str, field_type: str) -> bool:
    """
    Fill a single form field using Playwright.

    Args:
        page:          Playwright Page object.
        field_locator: Playwright Locator pointing to the field element.
        answer:        The string answer to fill in.
        field_type:    One of: "text", "select", "radio", "checkbox", "date", "file", "textarea".

    Returns:
        True if the field was filled successfully, False otherwise.

    TODO: Implement per-type filling logic:

      text / textarea:
        field_locator.fill(answer)

      select:
        Try exact option match first:
          field_locator.select_option(label=answer)
        If that fails, try case-insensitive prefix match:
          options = field_locator.locator('option').all_text_contents()
          best = find_best_option_match(answer, options)
          field_locator.select_option(label=best)

      radio:
        Find the radio input whose associated label matches `answer`:
          radios = page.locator(f'input[type="radio"][name="{field_name}"]').all()
          for radio in radios:
            label = get_label_for_input(page, radio)
            if label.lower() == answer.lower():
                radio.check()
                break

      checkbox:
        If answer is truthy ("yes", "true", "1"):
          field_locator.check()
        Else:
          field_locator.uncheck()

      date:
        Normalize answer to MM/DD/YYYY or YYYY-MM-DD depending on input format.
        field_locator.fill(formatted_date)

      file:
        Requires the path to the file on disk.
        page.set_input_files(field_locator, answer)  # answer = file path string
        After file upload, caller must call re-scan to detect auto-populated fields.
    """
    # TODO: Implement field filling
    raise NotImplementedError(f"fill_field not yet implemented for type: {field_type}")


def find_best_option_match(answer: str, options: list) -> str:
    """
    Find the best matching option text for a select dropdown.

    Args:
        answer:  The desired answer string.
        options: List of option text strings from the <select> element.

    Returns:
        The best matching option text string.

    TODO: Implement fuzzy matching:
      - Exact match (case-insensitive)
      - Prefix match
      - difflib.get_close_matches() for fuzzy fallback
      - If no good match, raise ValueError so the caller can flag for review
    """
    # TODO: Implement option matching
    answer_lower = answer.lower()
    for option in options:
        if option.lower() == answer_lower:
            return option
    # Fallback: return original answer and let Playwright handle/fail
    return answer


def get_label_for_input(page, input_locator) -> str:
    """
    Find the visible label text associated with a given input element.

    Args:
        page:           Playwright Page object.
        input_locator:  Playwright Locator for the input element.

    Returns:
        Label text string, or empty string if not found.

    TODO: Implement label discovery:
      1. Check input's id attribute, look for <label for="id">
      2. Check for wrapping <label> element (parent traversal)
      3. Check for aria-label attribute
      4. Check for aria-labelledby and follow the reference
      5. Fall back to nearest preceding text node
    """
    # TODO: Implement label discovery
    return ""
