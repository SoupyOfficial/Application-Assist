"""
confidence.py — Confidence scoring and fill decision logic.

Takes a match result from matcher.py and returns:
  - A numeric confidence score (0.0–1.0)
  - A fill decision: "auto_fill", "fill_and_flag", or "skip_and_ask"

Thresholds:
  >= 0.8  → auto_fill  (high confidence, safe to fill without review)
  0.5–0.8 → fill_and_flag  (medium confidence, fill but flag for review)
  < 0.5   → skip_and_ask  (low confidence, do not fill, ask user)

These thresholds can be tuned per field type or intent category.
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
    "dynamic": 0.5,  # dynamic entries require runtime evaluation
}


def score_confidence(match_result: dict) -> float:
    """
    Convert a match result's confidence label to a numeric score (0.0–1.0).

    Args:
        match_result: Dict returned by matcher.match_answer().

    Returns:
        Float confidence score between 0.0 and 1.0.

    TODO: Extend this function to incorporate additional signals:
      - Fuzzy match score from the matching step (if available in match_result)
      - Whether the answer entry has a notes field warning of edge cases
      - Whether requires_review is explicitly True (cap score at 0.75 if so)
      - Whether the answer is None (score = 0.0)
    """
    base_confidence = match_result.get("confidence", "none")

    # Handle numeric confidence if already set
    if isinstance(base_confidence, float):
        score = base_confidence
    else:
        score = CONFIDENCE_SCORE_MAP.get(base_confidence, 0.0)

    # If the answer is None, confidence is zero regardless of label
    if match_result.get("answer") is None and match_result.get("answer_long") is None:
        score = min(score, 0.3)

    # Cap confidence if requires_review is True — human should always approve
    if match_result.get("requires_review", False):
        score = min(score, 0.75)

    return round(score, 3)


def get_fill_decision(score: float, match_result: dict) -> str:
    """
    Return the fill decision for a given confidence score.

    Args:
        score:        Numeric confidence score from score_confidence().
        match_result: The full match result dict (for additional context).

    Returns:
        "auto_fill"     — fill without flagging for review
        "fill_and_flag" — fill but add to review queue
        "skip_and_ask"  — do not fill, prompt user for input

    TODO: Add per-intent overrides:
      - Intents in profile["application_preferences"]["never_auto_submit"]
        should always return "fill_and_flag" or "skip_and_ask", regardless of score.
      - Intents in profile["application_preferences"]["always_review"]
        should always return "fill_and_flag".
    """
    if match_result.get("requires_review", False):
        # Always flag for review even if confidence is high
        if score >= AUTO_FILL_THRESHOLD:
            return "fill_and_flag"

    if score >= AUTO_FILL_THRESHOLD:
        return "auto_fill"
    elif score >= FILL_FLAG_THRESHOLD:
        return "fill_and_flag"
    else:
        return "skip_and_ask"
