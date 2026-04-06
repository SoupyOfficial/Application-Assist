"""
classifier.py — LLM-based field intent classification.

Used when fuzzy matching in the normalizer fails to identify a field's
canonical intent with sufficient confidence. Calls Claude via the
Anthropic Python SDK to classify the field intent.

Only called as a fallback — the majority of fields should be resolved
through the faster fuzzy matching path in normalizer.py.
"""

import os
import json
import sys
from functools import lru_cache

import anthropic

_SYSTEM_PROMPT = (
    "You are a job application form classifier. Given a form field label "
    "and optional page context, return ONLY a JSON object with three keys:\n"
    '  "intent" (snake_case canonical intent string),\n'
    '  "confidence" (float 0.0–1.0),\n'
    '  "reasoning" (one-sentence explanation).\n\n'
    "Common intents: work_authorization_us, requires_sponsorship, "
    "salary_expectations, years_experience_total, first_name, last_name, "
    "email, phone, linkedin_url, github_url, willing_to_relocate, "
    "work_arrangement, citizenship_status, gender, race_ethnicity, "
    "veteran_status, disability_status, start_date, cover_letter, "
    "how_did_you_hear, referral_source, additional_info."
)

_FALLBACK = {"intent": "unknown", "confidence": 0.0, "reasoning": "classification failed"}


def classify_field(label: str, context: str, profile: dict) -> dict:
    """
    Use Claude to classify a form field's canonical intent.

    Results are cached per (label, context) pair for the session lifetime
    to avoid repeated API calls for identical fields across pages.

    Args:
        label:   The raw form field label text.
        context: Surrounding page context (section heading, nearby text).
        profile: Parsed profile.json dict. Not sent to the API.

    Returns:
        {"intent": str, "confidence": float, "reasoning": str}
    """
    return _classify_cached(label, context)


@lru_cache(maxsize=256)
def _classify_cached(label: str, context: str) -> dict:
    """Cached inner implementation — keyed on (label, context)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {**_FALLBACK, "reasoning": "ANTHROPIC_API_KEY not set"}

    user_message = f"Field label: {label}"
    if context:
        user_message += f"\nPage context: {context}"

    try:
        from src.llm.retry import call_with_retry
        client = anthropic.Anthropic(api_key=api_key)
        response = call_with_retry(
            client,
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        result = json.loads(raw.strip())
        return {
            "intent":     str(result.get("intent", "unknown")),
            "confidence": float(result.get("confidence", 0.0)),
            "reasoning":  str(result.get("reasoning", "")),
        }
    except anthropic.AuthenticationError as e:
        print(f"[error] Invalid ANTHROPIC_API_KEY: {e}", file=sys.stderr)
        return {**_FALLBACK, "reasoning": "invalid API key"}
    except (anthropic.APIError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[warn] LLM classify_field failed: {e}", file=sys.stderr)
        return {**_FALLBACK, "reasoning": f"API error: {type(e).__name__}"}
