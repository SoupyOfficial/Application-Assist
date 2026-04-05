"""
confidence.py — Confidence scoring and fill decision logic.

Takes a match result from matcher.py and returns:
  - A numeric confidence score (0.0–1.0)
  - A fill decision: "auto_fill", "fill_and_flag", or "skip_and_ask"

Thresholds:
  >= 0.8  → auto_fill  (high confidence, safe to fill without review)
  0.5–0.8 → fill_and_flag  (medium confidence, fill but flag for review)
  < 0.5   → skip_and_ask  (low confidence, do not fill, ask user)
"""

# Confidence thresholds
AUTO_FILL_THRESHOLD = 0.8
FILL_FLAG_THRESHOLD = 0.5

# Numeric scores for string confidence labels from answers.json
CONFIDENCE_SCORE_MAP = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.3,
    "none": 0.0,
    "dynamic": 0.5,
}


def score_confidence(match_result: dict) -> float:
    """
    Convert a match result's confidence label to a numeric score (0.0–1.0).

    Incorporates multiple signals: base label, fuzzy match score,
    answer presence, review requirement, and edge-case notes.
    """
    base_confidence = match_result.get("confidence", "none")

    # Handle numeric confidence if already set
    if isinstance(base_confidence, (float, int)):
        score = float(base_confidence)
    else:
        score = CONFIDENCE_SCORE_MAP.get(base_confidence, 0.0)

    # Blend in fuzzy match score if available (70% label, 30% match score)
    match_score = match_result.get("match_score")
    if match_score is not None and isinstance(match_score, (float, int)):
        score = (score * 0.7) + (float(match_score) * 0.3)

    # If the answer is None, cap score
    if match_result.get("answer") is None and match_result.get("answer_long") is None:
        score = min(score, 0.3)

    # Cap confidence if requires_review is True — human should always approve
    if match_result.get("requires_review", False):
        score = min(score, 0.75)

    # If notes mention inverted phrasing, penalize
    notes = match_result.get("notes") or ""
    if "inverted" in notes.lower():
        score = min(score, 0.65)

    return round(score, 3)


def get_fill_decision(score: float, match_result: dict, profile: dict = None) -> str:
    """
    Return the fill decision for a given confidence score.

    Args:
        score:        Numeric confidence score from score_confidence().
        match_result: The full match result dict.
        profile:      Optional parsed profile.json for preference overrides.

    Returns:
        "auto_fill"     — fill without flagging for review
        "fill_and_flag" — fill but add to review queue
        "skip_and_ask"  — do not fill, prompt user for input
    """
    intent = match_result.get("intent", "")

    # Safety overrides from profile preferences
    if profile:
        prefs = profile.get("application_preferences", {})
        never_auto = prefs.get("never_auto_submit", [])
        always_review = prefs.get("always_review", [])
        if intent in never_auto or intent in always_review:
            return "fill_and_flag" if score >= FILL_FLAG_THRESHOLD else "skip_and_ask"

    # If requires_review, never auto_fill
    if match_result.get("requires_review", False):
        return "fill_and_flag" if score >= FILL_FLAG_THRESHOLD else "skip_and_ask"

    # Standard threshold logic
    if score >= AUTO_FILL_THRESHOLD:
        return "auto_fill"
    elif score >= FILL_FLAG_THRESHOLD:
        return "fill_and_flag"
    else:
        return "skip_and_ask"
