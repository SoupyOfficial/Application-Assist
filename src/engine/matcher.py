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
from rapidfuzz import fuzz


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


def match_answer(intent: str, profile: dict, answers: dict, *, raw_label: str = "") -> dict:
    """
    Find the best answer for the given canonical intent.

    Args:
        intent:    Canonical intent string (from normalizer.normalize_question).
        profile:   Parsed profile.json dict.
        answers:   Parsed answers.json dict.
        raw_label: Original field label text (used for inverted phrasing detection).

    Returns:
        Match result dict with intent, answer, confidence, source, etc.
    """
    # Priority 1: Exact intent match in answers.json
    for entry in answers.get("answers", []):
        if entry.get("intent") == intent:
            answer = entry.get("answer")

            # Template entries with null answer — fall through to skill lookup
            if answer is None:
                break

            notes = entry.get("notes")
            requires_review = entry.get("requires_review", True)

            # Check for inverted phrasing
            if entry.get("answer_inverted") is not None:
                if _is_inverted_phrasing(raw_label, entry):
                    answer = entry["answer_inverted"]
                    inv_note = entry.get("answer_inverted_note", "Inverted phrasing detected")
                    notes = f"{notes}; {inv_note}" if notes else inv_note
                    requires_review = True

            return {
                "intent":          intent,
                "answer":          answer,
                "answer_long":     entry.get("answer_long"),
                "confidence":      entry.get("confidence", "low"),
                "source":          "answers_bank",
                "requires_review": requires_review,
                "answer_entry":    entry,
                "notes":           notes,
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

    # Priority 2b: Skill-aware lookup — "Do you have experience with X?" / "Years of X experience"
    skill_result = _try_skill_lookup(intent, profile, raw_label)
    if skill_result is not None:
        return skill_result

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
            score = fuzz.ratio(intent_cleaned, phrase_cleaned) / 100.0
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


# ---------------------------------------------------------------------------
# Skill-aware lookup
# ---------------------------------------------------------------------------

_EXPERIENCE_YEARS_PATTERN = re.compile(
    r"(?:(.+?)\s+experience\s*\(?years?\)?)"
    r"|(?:years?\s+(?:of\s+)?experience\s+(?:with|in|using)\s+(.+?))\s*$"
    r"|(?:years?\s+(?:of\s+)?(.+?)\s+experience)"
    r"|(?:years?\s+(?:of\s+)?(?:exp\s+)?(?:with|in|using)\s+(.+?))\s*$",
    re.IGNORECASE,
)

_SKILL_BOOLEAN_PATTERN = re.compile(
    r"(?:do you have (?:experience|proficiency|familiarity) (?:with|in)\s+(.+?))\s*$"
    r"|(?:have you (?:worked|used|programmed) (?:with|in)\s+(.+?))\s*$"
    r"|(?:are you (?:proficient|experienced|familiar) (?:with|in)\s+(.+?))\s*$",
    re.IGNORECASE,
)


def _try_skill_lookup(intent: str, profile: dict, raw_label: str) -> dict | None:
    """
    Check if the question is asking about a specific skill and resolve
    from profile.skills[].

    Handles two patterns:
      - "Years of X experience" → returns the years number
      - "Do you have experience with X?" → returns Yes/No
    """
    skills = profile.get("skills", [])
    if not skills:
        return None

    label = raw_label or intent

    # Build a quick name→skill map (case insensitive)
    skill_map = {s["name"].lower(): s for s in skills if s.get("name")}

    # Try years-of-experience pattern
    m = _EXPERIENCE_YEARS_PATTERN.search(label)
    if m:
        skill_name = next((g for g in m.groups() if g), "").strip().rstrip("?").strip()
        if skill_name:
            skill = _find_skill(skill_name, skill_map)
            if skill:
                return {
                    "intent":          intent,
                    "answer":          str(skill.get("years", "")),
                    "answer_long":     None,
                    "confidence":      "high",
                    "source":          "profile",
                    "requires_review": False,
                    "answer_entry":    None,
                    "notes":           f"Skill match: {skill['name']} ({skill.get('years')} yrs)",
                    "match_score":     1.0,
                }

    # Try boolean skill-experience pattern
    m = _SKILL_BOOLEAN_PATTERN.search(label)
    if m:
        skill_name = (m.group(1) or m.group(2) or m.group(3) or "").strip().rstrip("?").strip()
        if skill_name:
            skill = _find_skill(skill_name, skill_map)
            return {
                "intent":          intent,
                "answer":          "Yes" if skill else None,
                "answer_long":     None,
                "confidence":      "high" if skill else "none",
                "source":          "profile" if skill else "none",
                "requires_review": skill is None,
                "answer_entry":    None,
                "notes":           f"Skill match: {skill['name']}" if skill else f"Skill '{skill_name}' not in profile",
                "match_score":     1.0 if skill else 0.0,
            }

    return None


def _find_skill(name: str, skill_map: dict) -> dict | None:
    """Find a skill by exact or fuzzy name match."""
    name_lower = name.lower().strip()
    # Exact match
    if name_lower in skill_map:
        return skill_map[name_lower]
    # Fuzzy match
    best_score = 0.0
    best_skill = None
    for key, skill in skill_map.items():
        score = fuzz.ratio(name_lower, key) / 100.0
        if score > best_score:
            best_score = score
            best_skill = skill
    if best_score >= 0.8:
        return best_skill
    return None


# ---------------------------------------------------------------------------
# Inverted phrasing detection
# ---------------------------------------------------------------------------

# Common patterns where the question asks the *opposite* of the stored intent.
# e.g., intent = "requires_sponsorship" (answer: "No") but the label says
# "Are you authorized to work ... without sponsorship?" (inverted → "Yes")
_INVERSION_PATTERNS = [
    (r"without\s+sponsorship", "sponsorship"),
    (r"do\s+not\s+require\s+sponsorship", "sponsorship"),
    (r"authorized\s+to\s+work.*without", "sponsorship"),
    (r"will\s+not\s+require", "sponsorship"),
    (r"not\s+require.*visa", "sponsorship"),
]


def _is_inverted_phrasing(raw_label: str, entry: dict) -> bool:
    """
    Detect whether the raw field label uses inverted phrasing relative
    to the stored answer entry.

    Uses entry-level ``inverted_phrasing`` patterns if provided, falling
    back to hardcoded inversion heuristics.
    """
    if not raw_label:
        return False

    label_lower = raw_label.lower()

    # Entry-specific patterns (from answers.json)
    entry_patterns = entry.get("inverted_phrasing") or []
    for pat in entry_patterns:
        if pat.lower() in label_lower:
            return True

    # Hardcoded heuristics
    for pattern, _category in _INVERSION_PATTERNS:
        if re.search(pattern, label_lower):
            return True

    return False
