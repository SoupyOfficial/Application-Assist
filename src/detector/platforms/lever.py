"""
lever.py — Lever ATS detection logic.

URL patterns:
  - jobs.lever.co/<company>/<job-id>
  - lever.co/apply/...
  - Custom domains with Lever embed

API: Available — Lever Postings API provides public job listings.
     https://hire.lever.co/developer/postings

DOM markers: TBD — inspect a live Lever form to identify reliable selectors.
  Candidates to research:
    - <div class="application-page"> or similar wrapper
    - form action URLs containing lever.co
    - <script src="...lever.co..."> tags
    - Lever-specific data attributes or CSS class prefixes
"""

import re

PLATFORM_NAME = "lever"

URL_PATTERNS = [
    re.compile(r"jobs\.lever\.co", re.IGNORECASE),
    re.compile(r"lever\.co/apply", re.IGNORECASE),
]


def matches_url(url: str) -> bool:
    """Return True if the URL matches a known Lever pattern."""
    return any(pattern.search(url) for pattern in URL_PATTERNS)


def detect_from_dom(page) -> bool:
    """Return True if the live page DOM confirms this is a Lever form."""
    try:
        if page.locator('.lever-application-form').count() > 0:
            return True
        if page.locator('[data-lever-source]').count() > 0:
            return True
        if page.locator('form[action*="lever.co"]').count() > 0:
            return True
        if page.locator('script[src*="lever.co"]').count() > 0:
            return True
        if page.locator('.application-page .posting-page').count() > 0:
            return True
    except Exception:
        pass
    return False
