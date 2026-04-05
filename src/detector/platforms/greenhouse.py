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
    """
    Return True if the live page DOM confirms this is a Greenhouse form.

    TODO: Implement DOM marker detection using Playwright.
    Candidates:
      - page.locator('[data-source="greenhouse"]').count() > 0
      - page.locator('form[action*="greenhouse.io"]').count() > 0
      - Check meta tags: page.locator('meta[name="application-name"]').get_attribute("content")
      - Check for Greenhouse-specific CSS classes or JS globals (window.Greenhouse)
    """
    # TODO: Implement DOM-based detection
    return False
