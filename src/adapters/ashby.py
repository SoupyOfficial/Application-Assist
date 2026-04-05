"""
ashby.py — Adapter for Ashby ATS forms.

Ashby is a modern ATS with a clean React-based UI:
  - Growing adoption among newer/modern tech startups
  - API availability is TBD — may allow fetching job details
  - Form structure is relatively clean compared to Workday

Implementation approach:
  - Research live Ashby forms to identify React component structure
  - Standard contact fields should map from profile.identity
  - Resume upload + re-scan pattern likely applies
  - EEO section may follow similar pattern to Greenhouse/Lever
"""

from src.adapters.base import BaseAdapter


class AshbyAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """
        Detect form fields on an Ashby application page.

        TODO: Implement using Playwright locators.
        Approach:
          - Inspect a live Ashby form to map out the DOM structure
          - Identify React component wrappers and their input children
          - Extract label text and associate with inputs
          - Handle any custom question types specific to Ashby
          - Map to standard field descriptor format
        """
        # TODO: Implement Ashby field detection
        return []

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill an Ashby application form.

        TODO: Implement form filling orchestration.
        Approach:
          1. Fill standard contact fields from profile.identity
          2. Upload resume
          3. Re-scan after upload
          4. Fill work auth / sponsorship fields
          5. Handle custom questions
          6. EEO/demographic section
        """
        # TODO: Implement Ashby form filling
        return []

    def submit(self, page) -> bool:
        """
        Submit the Ashby application.

        TODO: Implement submission.
        Approach:
          - Locate and click the primary submit button
          - Wait for confirmation state
          - Return True on success
        """
        # TODO: Implement Ashby submit
        raise NotImplementedError("Ashby submit not yet implemented")
