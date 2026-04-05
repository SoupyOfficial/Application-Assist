"""
matcher.py — Answer matching from the answer bank.

Given a canonical intent string and the loaded profile/answers data,
finds the best answer from answers.json and returns a structured result.

Match priority:
  1. Exact intent match in answers.json
  2. Profile field lookup by intent (e.g., identity.email, location.city)
  3. Fuzzy phrase match across all match_phrases in all answers
  4. No match → returns result with confidence "none" and requires_review=True
"""

import re
import difflib


# Map intent strings to dotpaths into profile.json
PROFILE_FIELD_MAP = {
    "first_name":       ("identity.legal_first_name",      "text"),
    "last_name":        ("identity.legal_last_name",        "text"),
    "full_name":        ("identity.full_name",              "text"),
    "preferred_name":   ("identity.preferred_name",         "text"),
    "email":            ("identity.email_primary",          "text"),
    "phone":            ("identity.phone_formatted",        "text"),
    "linkedin_url":     ("links.linkedin",                  "text"),
    "github_url":       ("links.github",                    "text"),
    "portfolio_url":    ("links.portfolio",                 "text"),
    "city":             ("location.city",                   "text"),
    "state":            ("location.state",                  "text"),
    "zip":              ("location.zip",                    "text"),
    "address_line_1":   ("location.full_address_line",      "text"),
    "country":          ("location.country",                "text"),
    "current_company":  ("work_history[0].company",         "text"),
    "current_title":    ("work_history[0].title",           "text"),
    "university":       ("education[0].institution",        "text"),
    "degree":           ("education[0].degree_type",        "text"),
}


def _resolve_dotpath(obj: dict, dotpath: str):
    """Navigate a dict using a dot-separated path. Supports array indices like 'work_history[0].company'."""
    parts = dotpath.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        match = re.match(r'(\w+)\[(\d+)\]', part)
        if match:
            key, idx = match.group(1), int(match.group(2))
            lst = current.get(key, []) if isinstance(current, dict) else []
            current = lst[idx] if idx < len(lst) else None
        else:
            current = current.get(part) if isinstance(current, dict) else None
    return current


def _clean(text: str) -> str:
    """Lowercase, strip punctuation and whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def match_answer(intent: str, profile: dict, answers: dict) -> dict:
    """
    Find the best answer for the given canonical intent.

    Args:
        intent:  Canonical intent string (from normalizer.normalize_question).
        profile: Parsed profile.json dict.
        answers: Parsed answers.json dict.

    Returns:
        Match result dict with intent, answer, confidence, source, etc.
    """
    # Priority 1: Exact intent match in answers.json
    for entry in answers.get("answers", []):
        if entry.get("intent") == intent:
            return {
                "intent":          intent,
                "answer":          entry.get("answer"),
                "answer_long":     entry.get("answer_long"),
                "confidence":      entry.get("confidence", "low"),
                "source":          "answers_bank",
                "requires_review": entry.get("requires_review", True),
                "answer_entry":    entry,
                "notes":           entry.get("notes"),
                "match_score":     1.0,
            }

    # Priority 2: Profile field lookup
    if intent in PROFILE_FIELD_MAP:
        dotpath, _field_type = PROFILE_FIELD_MAP[intent]
        value = _resolve_dotpath(profile, dotpath)
        if value is not None:
            return {
                "intent":          intent,
                "answer":          str(value),
                "answer_long":     None,
                "confidence":      "high",
                "source":          "profile",
                "requires_review": False,
                "answer_entry":    None,
                "notes":           f"From profile: {dotpath}",
                "match_score":     1.0,
            }

    # Priority 3: Fuzzy cross-match against match_phrases
    best_score = 0.0
    best_entry = None
    intent_cleaned = _clean(intent)
    for entry in answers.get("answers", []):
        phrases = [entry.get("intent", "")] + entry.get("match_phrases", [])
        for phrase in phrases:
            phrase_cleaned = _clean(phrase)
            if not phrase_cleaned:
                continue
            score = difflib.SequenceMatcher(None, intent_cleaned, phrase_cleaned).ratio()
            if score > best_score:
                best_score = score
                best_entry = entry
    if best_score >= 0.75 and best_entry:
        return {
            "intent":          intent,
            "answer":          best_entry.get("answer"),
            "answer_long":     best_entry.get("answer_long"),
            "confidence":      "medium",
            "source":          "answers_bank",
            "requires_review": True,
            "answer_entry":    best_entry,
            "notes":           f"Fuzzy match (score={best_score:.2f})",
            "match_score":     best_score,
        }

    # Priority 4: No match
    return {
        "intent":          intent,
        "answer":          None,
        "answer_long":     None,
        "confidence":      "none",
        "source":          "none",
        "requires_review": True,
        "answer_entry":    None,
        "notes":           "No match found in answers bank or profile.",
        "match_score":     0.0,
    }
