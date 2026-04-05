"""
matcher.py — Answer matching from the answer bank.

Given a canonical intent string and the loaded profile/answers data,
finds the best answer from answers.json and returns a structured result.

Match priority:
  1. Exact intent match in answers.json
  2. Fuzzy phrase match across all match_phrases in all answers
  3. Profile field lookup by intent (e.g., identity.email, location.city)
  4. No match → returns result with confidence "none" and requires_review=True
"""


def match_answer(intent: str, profile: dict, answers: dict) -> dict:
    """
    Find the best answer for the given canonical intent.

    Args:
        intent:  Canonical intent string (from normalizer.normalize_question).
        profile: Parsed profile.json dict.
        answers: Parsed answers.json dict.

    Returns:
        Match result dict:
          {
            "intent":          <str — the matched intent>,
            "answer":          <str | None — the answer to fill>,
            "answer_long":     <str | None — longer form answer if available>,
            "confidence":      <"high" | "medium" | "low" | "none">,
            "source":          <"answers_bank" | "profile" | "none">,
            "requires_review": <bool>,
            "answer_entry":    <dict | None — the full answers.json entry if matched>,
            "notes":           <str | None — notes from the answer entry>,
          }

    TODO: Implement matching logic:

      Step 1 — Exact intent match in answers.json:
        for entry in answers["answers"]:
            if entry["intent"] == intent:
                return build_result(entry, source="answers_bank")

      Step 2 — Fuzzy match across match_phrases:
        Use difflib.get_close_matches or rapidfuzz to compare `intent`
        against all match_phrases in all entries. Return the entry with
        the highest match score if above threshold.

      Step 3 — Profile field lookup:
        Some intents map directly to profile fields:
          "first_name"    → profile["identity"]["legal_first_name"]
          "last_name"     → profile["identity"]["legal_last_name"]
          "email"         → profile["identity"]["email_primary"]
          "phone"         → profile["identity"]["phone_formatted"]
          "linkedin_url"  → profile["links"]["linkedin"]
          "github_url"    → profile["links"]["github"]
          "city"          → profile["location"]["city"]
          "state"         → profile["location"]["state"]
          "zip"           → profile["location"]["zip"]
          etc.
        Build a PROFILE_FIELD_MAP dict for this lookup.

      Step 4 — No match:
        Return a result with confidence="none", requires_review=True,
        answer=None, source="none".
    """
    # TODO: Implement matching
    # Placeholder: scan answers for exact intent match
    for entry in answers.get("answers", []):
        if entry.get("intent") == intent:
            return {
                "intent": intent,
                "answer": entry.get("answer"),
                "answer_long": entry.get("answer_long"),
                "confidence": entry.get("confidence", "low"),
                "source": "answers_bank",
                "requires_review": entry.get("requires_review", True),
                "answer_entry": entry,
                "notes": entry.get("notes"),
            }

    # No match found
    return {
        "intent": intent,
        "answer": None,
        "answer_long": None,
        "confidence": "none",
        "source": "none",
        "requires_review": True,
        "answer_entry": None,
        "notes": "No match found in answers bank or profile.",
    }
