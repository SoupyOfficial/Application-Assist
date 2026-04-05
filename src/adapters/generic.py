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

from src.adapters.base import BaseAdapter
from src.detector.platforms.generic import discover_fields


class GenericAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """
        Discover form fields using the generic Playwright-based scanner.

        Delegates to src.detector.platforms.generic.discover_fields().

        TODO: Wire in the discover_fields() implementation once it is built.
        The generic discovery uses label proximity mapping and input[type]
        classification to build the field descriptor list.
        """
        # TODO: Return discover_fields(page) once implemented
        return discover_fields(page)

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill a generic form using the full normalize → match → fill pipeline.

        TODO: Implement generic fill orchestration.
        Approach:
          1. detect_fields() to get raw field list
          2. For each field: normalize label → match intent → score confidence
          3. Only fill fields with confidence >= 0.5; flag the rest for review
          4. No submit automation — always leave submit for the user
          5. Return all fill results for the review UI
        """
        # TODO: Implement generic form filling
        return []

    def submit(self, page) -> bool:
        """
        Submit via generic submit button detection.

        TODO: Implement generic submit.
        Approach:
          - Search for a button with text matching submit/apply/send
          - Confirm with user before clicking (extra caution on generic forms)
          - Return True on apparent success
        """
        # TODO: Implement generic submit
        raise NotImplementedError("Generic submit not yet implemented")
