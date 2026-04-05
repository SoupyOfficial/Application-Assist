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
from src.engine.normalizer import normalize_question
from src.engine.matcher import match_answer
from src.engine.confidence import score_confidence, get_fill_decision
from src.engine.filler import fill_field
from src.llm.drafter import draft_answer


class GenericAdapter(BaseAdapter):

    def detect_fields(self, page) -> list:
        """Discover form fields using the generic Playwright-based scanner."""
        return discover_fields(page)

    def fill_form(self, page, profile: dict, answers: dict, mode: str) -> list:
        """Fill a generic form using the full normalize → match → fill pipeline."""
        fields = self.detect_fields(page)
        results = []

        for field in fields:
            label = field.get("label", "")
            field_type = field.get("field_type", "text")
            context = field.get("section", "")

            # Handle file upload separately
            if field_type == "file":
                resume_path = profile.get("_resume_path")
                if resume_path:
                    filled = fill_field(page, field, resume_path, "file")
                    results.append({
                        "field": field,
                        "proposed_answer": resume_path,
                        "confidence": 1.0,
                        "source": "profile",
                        "requires_review": False,
                        "filled": filled,
                    })
                    if filled:
                        # Re-detect after resume upload for auto-populated fields
                        page.wait_for_timeout(2000)
                else:
                    results.append({
                        "field": field,
                        "proposed_answer": None,
                        "confidence": 0.0,
                        "source": "none",
                        "requires_review": True,
                        "filled": False,
                        "notes": "No resume file found",
                    })
                continue

            # Normalize → Match → Score → Fill
            intent = normalize_question(label, profile, context)
            match_result = match_answer(intent, profile, answers)

            # If no match, try LLM drafting for textarea/long-text fields
            answer = match_result.get("answer") or match_result.get("answer_long")
            source = match_result.get("source", "none")

            if not answer and field_type in ("textarea",):
                answer = draft_answer(label, profile, context)
                if answer:
                    source = "llm"
                    match_result["confidence"] = "medium"
                    match_result["requires_review"] = True

            score = score_confidence(match_result)
            decision = get_fill_decision(score, match_result, profile)

            filled = False
            if answer and decision in ("auto_fill", "fill_and_flag"):
                filled = fill_field(page, field, str(answer), field_type)

            results.append({
                "field": field,
                "proposed_answer": answer,
                "confidence": score,
                "source": source,
                "requires_review": match_result.get("requires_review", False) or decision == "fill_and_flag",
                "filled": filled,
                "intent": intent,
                "notes": match_result.get("notes", ""),
            })

        return results

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
