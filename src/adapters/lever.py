"""
lever.py — Adapter for Lever ATS forms.

Lever application forms:
  - Single-page form with labeled inputs
  - Consistent structure across companies
  - Resume upload triggers field auto-population
  - Custom questions vary per job posting

Implementation approach:
  - Use Lever-specific class names and input patterns
  - Standard fields map from profile.identity directly
  - Resume upload + re-scan pattern applies
  - Submit button is typically the primary CTA button at the bottom
"""

from src.adapters.base import BaseAdapter


class LeverAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """
        Detect form fields on a Lever application page.

        TODO: Implement using Playwright locators.
        Approach:
          - Lever forms use consistent class names — research live form structure
          - Locate all visible input/textarea/select elements
          - Map each to a label using <label for="..."> or DOM proximity
          - Classify field type
          - Identify the resume upload input (input[type="file"])
          - Identify the cover letter input (often a textarea)
        """
        # TODO: Implement Lever field detection
        return []

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill a Lever application form.

        TODO: Implement form filling orchestration.
        Approach:
          1. Fill standard contact fields from profile.identity
          2. Upload resume from resumes/<variant>.pdf
          3. Re-scan fields after resume upload (auto-population)
          4. Fill work auth / sponsorship fields from answers.json
          5. Handle any custom questions with normalize → match → fill pipeline
          6. EEO/demographic section: use demographic_defaults
        """
        # TODO: Implement Lever form filling
        return []

    def submit(self, page) -> bool:
        """
        Submit the Lever application.

        TODO: Implement submission.
        Approach:
          - Locate the submit button (typically bottom of the single-page form)
          - Click and wait for confirmation/success state
          - Lever typically shows a "Your application has been submitted" confirmation
          - Return True on success, False on error
        """
        # TODO: Implement Lever submit
        raise NotImplementedError("Lever submit not yet implemented")
