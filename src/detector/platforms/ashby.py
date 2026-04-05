"""
ashby.py — Ashby ATS detection logic.

URL patterns:
  - jobs.ashbyhq.com/<company>/<job-id>
  - ashbyhq.com/...
  - Custom domains with Ashby embed

API: TBD — Ashby API availability unclear. Research needed.
  - Check https://developers.ashbyhq.com (if it exists)
  - Ashby may expose a public job listings endpoint
  - May require browser automation for full form interaction

DOM markers: TBD — inspect a live Ashby form to identify reliable selectors.
  Candidates to research:
    - Ashby-specific React component class names or data attributes
    - Script tags pointing to ashbyhq.com CDN
    - Form action URLs
"""

import re

PLATFORM_NAME = "ashby"

URL_PATTERNS = [
    re.compile(r"jobs\.ashbyhq\.com", re.IGNORECASE),
    re.compile(r"ashbyhq\.com", re.IGNORECASE),
]


def matches_url(url: str) -> bool:
    """Return True if the URL matches a known Ashby pattern."""
    return any(pattern.search(url) for pattern in URL_PATTERNS)


def detect_from_dom(page) -> bool:
    """
    Return True if the live page DOM confirms this is an Ashby form.

    TODO: Implement DOM marker detection using Playwright.
    Candidates:
      - Look for Ashby-specific React root or component names
      - Check for script/link tags pointing to ashbyhq.com
      - Check window.__ASHBY__ or similar JS globals
    """
    # TODO: Implement DOM-based detection
    return False
