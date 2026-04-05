"""
greenhouse.py — Greenhouse ATS detection logic.

URL patterns:
  - boards.greenhouse.io/<company>/jobs/<id>
  - job-boards.greenhouse.io/<company>/jobs/<id>
  - <company>.greenhouse.io/...
  - Custom domains with /jobs/ path + Greenhouse meta tags

API: Available — https://developers.greenhouse.io/job-board.html
     Can use the Job Board API to fetch job details without browser automation.

DOM markers: TBD — inspect a live Greenhouse form to identify reliable selectors.
  Candidates to research:
    - <div id="application"> or similar wrapper
    - data-* attributes specific to Greenhouse
    - form action URLs containing greenhouse.io
    - <meta name="application-name" content="Greenhouse"> or similar
"""

import re

PLATFORM_NAME = "greenhouse"

# Known Greenhouse URL patterns
URL_PATTERNS = [
    re.compile(r"boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"job-boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"greenhouse\.io/", re.IGNORECASE),
]


def matches_url(url: str) -> bool:
    """Return True if the URL matches a known Greenhouse pattern."""
    return any(pattern.search(url) for pattern in URL_PATTERNS)


def detect_from_dom(page) -> bool:
    """Return True if the live page DOM confirms this is a Greenhouse form."""
    try:
        # Check for Greenhouse-specific form action
        if page.locator('form[action*="greenhouse.io"]').count() > 0:
            return True
        # Check for Greenhouse data attribute
        if page.locator('[data-source="greenhouse"]').count() > 0:
            return True
        # Check for #application wrapper common in Greenhouse embeds
        if page.locator('#application').count() > 0:
            # Confirm it's Greenhouse by checking for typical field structure
            if page.locator('#application .field').count() > 0:
                return True
        # Check meta tags
        meta = page.locator('meta[name="application-name"]')
        if meta.count() > 0 and "greenhouse" in (meta.get_attribute("content") or "").lower():
            return True
        # Check for Greenhouse script tags
        if page.locator('script[src*="greenhouse.io"]').count() > 0:
            return True
    except Exception:
        pass
    return False
