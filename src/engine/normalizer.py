"""
normalizer.py — Field label normalization.

Takes a raw form field label string (e.g., "Are you legally authorized
to work in the United States?") and returns a canonical intent string
(e.g., "work_authorization_us") that can be matched against answers.json.

Normalization pipeline:
  1. Lowercase and strip punctuation from the raw label
  2. Check profile field map for simple identity fields
  3. Exact match against canonical questions in answers.json
  4. Fuzzy match against all match_phrases in answers.json
  5. If no confident match, fall back to LLM classification
  6. Return the intent string, or "unknown" if all methods fail
"""

import re
import difflib


# Threshold for fuzzy match acceptance
FUZZY_THRESHOLD = 0.80

# Map common label text patterns to profile field intents
LABEL_TO_PROFILE_INTENT = {
    "first name":       "first_name",
    "last name":        "last_name",
    "full name":        "full_name",
    "name":             "full_name",
    "legal name":       "full_name",
    "preferred name":   "preferred_name",
    "email":            "email",
    "email address":    "email",
    "phone":            "phone",
    "phone number":     "phone",
    "mobile phone":     "phone",
    "cell phone":       "phone",
    "linkedin":         "linkedin_url",
    "linkedin url":     "linkedin_url",
    "linkedin profile": "linkedin_url",
    "linkedin profile url": "linkedin_url",
    "github":           "github_url",
    "github url":       "github_url",
    "github profile":   "github_url",
    "website":          "portfolio_url",
    "portfolio":        "portfolio_url",
    "portfolio url":    "portfolio_url",
    "personal website": "portfolio_url",
    "city":             "city",
    "state":            "state",
    "state province":   "state",
    "zip":              "zip",
    "zip code":         "zip",
    "postal code":      "zip",
    "country":          "country",
    "address":          "address_line_1",
    "street address":   "address_line_1",
    "current company":  "current_company",
    "current employer": "current_company",
    "current title":    "current_title",
    "job title":        "current_title",
    "current job title":"current_title",
    "school":           "university",
    "university":       "university",
    "college":          "university",
    "degree":           "degree",
    "cover letter":     "cover_letter",
    "resume":           "resume",
    "cv":               "resume",
}


def _clean(text: str) -> str:
    """Lowercase, strip punctuation and excessive whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _match_profile_field_label(cleaned_label: str) -> str | None:
    """Check if a cleaned label maps directly to a profile field intent."""
    if cleaned_label in LABEL_TO_PROFILE_INTENT:
        return LABEL_TO_PROFILE_INTENT[cleaned_label]
    matches = difflib.get_close_matches(
        cleaned_label, LABEL_TO_PROFILE_INTENT.keys(), n=1, cutoff=0.85
    )
    if matches:
        return LABEL_TO_PROFILE_INTENT[matches[0]]
    return None


def normalize_question(label_text: str, answers: dict = None, threshold: float = FUZZY_THRESHOLD) -> str:
    """
    Normalize a raw form field label to a canonical intent string.

    Args:
        label_text: Raw label text from the form field.
        answers:    Parsed answers.json dict. If provided, fuzzy matching is used.
        threshold:  Minimum fuzzy match score (0.0–1.0) to accept a match.

    Returns:
        Canonical intent string (e.g., "work_authorization_us"), or "unknown".
    """
    if not label_text or not label_text.strip():
        return "unknown"

    cleaned = _clean(label_text)
    if not cleaned:
        return "unknown"

    # Step 1: Profile field map (simple identity fields)
    profile_intent = _match_profile_field_label(cleaned)
    if profile_intent:
        return profile_intent

    # Skip further matching if no answers data
    if not answers or "answers" not in answers:
        return cleaned

    # Step 2: Exact match against canonical_question
    for entry in answers["answers"]:
        canonical_cleaned = _clean(entry.get("canonical_question", ""))
        if cleaned == canonical_cleaned:
            return entry["intent"]

    # Step 3: Fuzzy match against all match_phrases
    best_score = 0.0
    best_intent = None
    for entry in answers["answers"]:
        phrases = [entry.get("canonical_question", "")] + entry.get("match_phrases", [])
        for phrase in phrases:
            phrase_cleaned = _clean(phrase)
            if not phrase_cleaned:
                continue
            score = difflib.SequenceMatcher(None, cleaned, phrase_cleaned).ratio()
            if score > best_score:
                best_score = score
                best_intent = entry["intent"]

    if best_score >= threshold and best_intent:
        return best_intent

    # Step 4: LLM fallback
    try:
        from src.llm.classifier import classify_field
        result = classify_field(label_text, context="", profile={})
        if result.get("intent", "unknown") != "unknown" and result.get("confidence", 0.0) >= 0.6:
            return result["intent"]
    except Exception:
        pass

    return "unknown"
