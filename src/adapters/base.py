"""
base.py — Abstract base class for ATS platform adapters.

All platform-specific adapters must subclass BaseAdapter and implement
the three core methods: detect_fields, fill_form, and submit.
"""

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """
    Abstract adapter interface for a single ATS platform.

    Each adapter is responsible for:
      1. Detecting/extracting fields from the live Playwright page.
      2. Orchestrating the fill process (calling the fill engine per field).
      3. Submitting the form when authorized by the mode and review UI.
    """

    @abstractmethod
    def detect_fields(self, page) -> list:
        """
        Scan the current page and return a list of field descriptors.

        Args:
            page: Playwright Page object (already navigated to the job URL).

        Returns:
            List of field descriptor dicts, each containing at minimum:
              {
                "locator":    <Playwright Locator>,
                "label":      <string — visible label text>,
                "field_type": <"text" | "select" | "radio" | "checkbox" | "file" | "date">,
                "name":       <input name or id attribute>,
                "required":   <bool>,
                "section":    <string — logical section name, e.g. "personal_info">,
              }

        TODO: Each platform adapter implements this differently:
          - Greenhouse: Use known CSS selectors for its standard form structure.
          - Lever: Similar — known class names and input patterns.
          - Workday: Use data-automation-id attributes; handle multi-step pagination.
          - Generic: Use proximity-based label-to-input mapping.
        """
        raise NotImplementedError

    @abstractmethod
    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """
        Fill the form using the fill engine, returning a list of fill results.

        Args:
            page:    Playwright Page object.
            profile: Parsed profile.json dict.
            answers: Parsed answers.json dict.
            mode:    Submission mode string.

        Returns:
            List of fill result dicts — one per field — containing:
              {
                "field":          <field descriptor from detect_fields>,
                "proposed_answer": <string>,
                "confidence":     <float 0.0–1.0>,
                "source":         <"profile" | "answers" | "llm" | "manual">,
                "requires_review": <bool>,
                "filled":         <bool>,
              }

        TODO: Orchestration flow per adapter:
          1. Call detect_fields() to get field list.
          2. For each field, call engine.normalizer.normalize_question(label).
          3. Call engine.matcher.match_answer(intent, profile, answers).
          4. Call engine.confidence.score_confidence(match_result).
          5. If confidence >= threshold, call engine.filler.fill_field(page, ...).
          6. After any file upload, re-call detect_fields() to catch auto-populated fields.
          7. Return the results list for the review UI.
        """
        raise NotImplementedError

    @abstractmethod
    def submit(self, page) -> bool:
        """
        Submit the completed form.

        Args:
            page: Playwright Page object.

        Returns:
            True if submission appeared successful, False otherwise.

        TODO: Each platform has a different submit mechanism:
          - Greenhouse/Lever: Click the final "Submit Application" button.
          - Workday: Multi-step — must navigate through all steps before final submit.
          - Generic: Find and click the primary form submit button.

        Safety: This method should NEVER be called unless the calling code
        has already confirmed that mode != "fill_only" and the review UI
        has approved the submission.
        """
        raise NotImplementedError
