"""
generic.py — Generic fallback adapter for unknown ATS platforms.

Used when the detector cannot identify a specific platform.
Uses Playwright-based form discovery: scan all visible inputs, labels,
and selects, then attempt best-effort filling via the full engine pipeline.

This adapter is intentionally conservative:
  - It discovers fields but does not make assumptions about structure
  - Confidence thresholds are enforced strictly
  - Nearly all fields will be flagged for review
  - Submit is always gated behind review, regardless of mode
"""

import sys

from src.adapters.base import BaseAdapter
from src.detector.platforms.generic import discover_fields


class GenericAdapter(BaseAdapter):
    """Fallback adapter — uses generic field discovery + base class fill logic."""

    def detect_fields(self, page) -> list:
        """Discover form fields using the generic Playwright-based scanner."""
        return discover_fields(page)

    # fill_form() inherited from BaseAdapter (multi-page aware, shared pipeline)

    def submit(self, page) -> bool:
        """Submit via generic submit button detection."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send")',
        ]
        for selector in submit_selectors:
            btn = page.locator(selector)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle")
                return True
        print("[warn] Could not find a submit button.", file=sys.stderr)
        return False
