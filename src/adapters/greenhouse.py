"""
greenhouse.py — Adapter for Greenhouse ATS forms.

Greenhouse forms are relatively clean and consistent:
  - Standard HTML form with labeled inputs
  - Known CSS structure from the Greenhouse Job Board embeds
  - Public API available: https://developers.greenhouse.io/job-board.html

Implementation approach:
  - Use Greenhouse-specific CSS selectors to locate fields reliably
  - Fields are typically inside a <div class="field"> wrapper with a <label>
  - Resume upload is a file input; after upload, check for auto-populated fields
  - Submit button is typically: <input type="submit" value="Submit Application">
"""

from src.adapters.base import BaseAdapter


class GreenhouseAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """
        Detect form fields on a Greenhouse application page.

        TODO: Implement using Playwright locators.
        Approach:
          - Locate all .field divs: page.locator('.field')
          - For each .field, extract the <label> text and the associated input
          - Classify input type from input[type] attribute
          - Map to field descriptor format expected by fill engine
          - Handle special cases: resume upload, cover letter, custom questions
        """
        # TODO: Implement Greenhouse field detection
        return []

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill a Greenhouse application form.

        TODO: Implement form filling orchestration.
        Approach:
          1. Call self.detect_fields(page) to get field list
          2. Standard fields (name, email, phone, LinkedIn, GitHub) map directly
             from profile.identity — these can be filled without LLM
          3. Work auth, sponsorship questions → answers.json lookup
          4. Resume upload: locate file input, set file path from resume_variants
          5. After upload: re-detect fields to catch any auto-populated values
          6. Custom questions: normalize → match → confidence score → fill or flag
          7. Demographic EEO section: use demographic_defaults from answers.json
        """
        # TODO: Implement Greenhouse form filling
        return []

    def submit(self, page) -> bool:
        """
        Submit the Greenhouse application.

        TODO: Implement submission.
        Approach:
          - Locate: page.locator('input[type="submit"][value*="Submit"]')
            or: page.locator('button:has-text("Submit Application")')
          - Click and wait for navigation or success confirmation
          - Check for confirmation page or success message
          - Return True if confirmation detected, False if error or timeout
        """
        # TODO: Implement Greenhouse submit
        raise NotImplementedError("Greenhouse submit not yet implemented")
