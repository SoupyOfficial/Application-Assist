"""
workday.py — Adapter for Workday ATS forms.

Workday is the most complex target in this project:
  - Multi-step wizard (each step is a separate page/section)
  - React/Angular SPA — no stable static DOM structure
  - Heavily uses data-automation-id attributes on form elements
  - Often requires account creation before applying
  - Resume upload in step 1 triggers auto-population across all steps
  - Custom question banks vary significantly by employer
  - File inputs may be hidden; triggered via button click

Known Workday data-automation-id patterns (research needed):
  - "createAccountLink" — create account CTA
  - "email" — email input
  - "legalNameSection_firstName" — first name
  - "legalNameSection_lastName" — last name
  - "phone-device-type" — phone type select
  - "phoneNumber" — phone number input
  - Varies by employer configuration

Steps (typical Workday application flow):
  1. Sign in or create account
  2. My Information (contact details, resume upload)
  3. My Experience (work history, education — often auto-populated from resume)
  4. Application Questions (custom per-job questions)
  5. Voluntary Disclosures (EEO / demographic section)
  6. Review and Submit
"""

from src.adapters.base import BaseAdapter


class WorkdayAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """
        Detect form fields on the current Workday step/page.

        TODO: Implement using Playwright locators.
        Approach:
          - Use data-automation-id attributes as primary selectors
            (more stable than class names in Workday's dynamic DOM)
          - Detect which step we are on (step indicator or heading text)
          - Extract visible fields for the current step only
          - Build a step-aware field list
          - Handle hidden/collapsed sections that may need expanding first

        Key challenge: Field IDs may vary between Workday tenant configurations.
        Build a flexible detection strategy, not a hardcoded ID list.
        """
        # TODO: Implement Workday field detection (step-aware)
        return []

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill a Workday application — multi-step orchestration.

        TODO: Implement multi-step fill orchestration.
        Approach:
          1. Detect current step (step 1 = My Information, etc.)
          2. Fill current step fields
          3. Click "Next" or "Save and Continue"
          4. Wait for next step to load (page.wait_for_load_state)
          5. Repeat until "Review" step is reached
          6. On resume upload (step 1): pause and wait for auto-population
             then re-detect all fields before continuing

        State machine sketch:
          STEP_ACCOUNT → STEP_MY_INFO → STEP_MY_EXPERIENCE →
          STEP_APP_QUESTIONS → STEP_VOLUNTARY → STEP_REVIEW
        """
        # TODO: Implement Workday multi-step form filling
        return []

    def submit(self, page) -> bool:
        """
        Submit the Workday application from the Review step.

        TODO: Implement submission.
        Approach:
          - Must be on the final Review step
          - Locate: page.locator('[data-automation-id="bottom-navigation-next-button"]')
            or the final "Submit" button variant
          - Click and wait for confirmation page
          - Workday confirmation typically shows an application number
          - Return True on success, False on error or timeout
        """
        # TODO: Implement Workday submit
        raise NotImplementedError("Workday submit not yet implemented")
