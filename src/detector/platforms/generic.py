"""
generic.py — Generic fallback ATS detection and form interaction.

Used when no specific platform is identified by URL or DOM markers.
Falls back to Playwright-based form discovery: find all visible input
fields, labels, and select elements, and attempt best-effort filling.

This is the catch-all for:
  - Custom in-house ATS builds
  - Niche platforms (SmartRecruiters, iCIMS, JazzHR, BambooHR, etc.)
  - Direct company career pages
"""

PLATFORM_NAME = "generic"


def matches_url(url: str) -> bool:
    """Generic never matches by URL — it is always the fallback."""
    return False


def detect_from_dom(page) -> bool:
    """
    Generic never positively matches by DOM — it is always the fallback.

    TODO (future enhancement): Could inspect the page for common ATS
    signatures not covered by the specific platform modules, and return
    a best-guess platform name with lower confidence.
    """
    return False


def discover_fields(page) -> list:
    """
    Discover all fillable form fields on the page using Playwright.

    Returns a list of field descriptor dicts:
      {
        "locator": <Playwright Locator>,
        "label": <string label text>,
        "field_type": <"text" | "select" | "radio" | "checkbox" | "file">,
        "name": <input name attribute>,
        "required": <bool>,
      }

    TODO: Implement generic field discovery:
      1. Find all <label> elements and map them to their associated inputs
         via `for` attribute or DOM proximity.
      2. Find all <input>, <select>, <textarea> elements.
      3. Attempt to extract visible label text for each field.
      4. Classify field type from input[type] attribute.
      5. Return the combined list for the fill engine to process.
    """
    # TODO: Implement generic form field discovery
    return []
