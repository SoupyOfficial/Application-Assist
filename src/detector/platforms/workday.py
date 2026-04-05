"""
workday.py — Workday ATS detection logic.

URL patterns:
  - <company>.myworkdayjobs.com/...
  - wd5.myworkdayjobs.com/<company>/...
  - <company>.wd1.myworkdayjobs.com/...  (various wd1–wd5 subdomains)
  - <company>.workday.com/...

API: No public application API available.
     Full browser automation is required. Workday forms are:
     - Multi-step (account creation, resume upload, question pages)
     - Heavily dynamic (React / Angular SPA, no standard static DOM)
     - Often behind a login wall
     - The most complex target in this project.

Notes:
  - Workday often requires creating an account before applying.
  - Resume parsing may auto-populate fields — must re-scan after upload.
  - Some steps involve custom question banks unique to each employer.
  - Expect significant Playwright wait/timing complexity.
"""

import re

PLATFORM_NAME = "workday"

URL_PATTERNS = [
    re.compile(r"myworkdayjobs\.com", re.IGNORECASE),
    re.compile(r"workday\.com", re.IGNORECASE),
]


def matches_url(url: str) -> bool:
    """Return True if the URL matches a known Workday pattern."""
    return any(pattern.search(url) for pattern in URL_PATTERNS)


def detect_from_dom(page) -> bool:
    """
    Return True if the live page DOM confirms this is a Workday form.

    TODO: Implement DOM marker detection using Playwright.
    Candidates:
      - page.locator('[data-automation-id]').count() > 0
        (Workday uses data-automation-id extensively on form elements)
      - Check for Workday-specific CSS class prefixes (wd-*)
      - Check window.workdayConfig or similar JS globals
      - Check <title> or <meta> tags for "Workday"
    """
    # TODO: Implement DOM-based detection
    return False
