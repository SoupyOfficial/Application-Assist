"""
normalizer.py — Field label normalization.

Takes a raw form field label string (e.g., "Are you legally authorized
to work in the United States?") and returns a canonical intent string
(e.g., "work_authorization_us") that can be matched against answers.json.

Normalization pipeline:
  1. Lowercase and strip punctuation from the raw label
  2. Fuzzy match against known canonical questions in answers.json
  3. If fuzzy match score >= threshold, return the matched intent
  4. If no confident match, fall back to LLM classification (llm/classifier.py)
  5. Return the intent string, or "unknown" if all methods fail
"""


def normalize_question(label_text: str, answers: dict = None, threshold: float = 0.8) -> str:
    """
    Normalize a raw form field label to a canonical intent string.

    Args:
        label_text: Raw label text from the form field (e.g., from a <label> element).
        answers:    Parsed answers.json dict. If provided, fuzzy matching is used.
                    If None, only simple cleaning is done.
        threshold:  Minimum fuzzy match score (0.0–1.0) to accept a match.

    Returns:
        Canonical intent string (e.g., "work_authorization_us"), or "unknown".

    TODO: Implement the normalization pipeline:
      1. Clean the input:
           clean = label_text.lower().strip()
           clean = re.sub(r'[^\w\s]', '', clean)  # strip punctuation

      2. Exact match: check if clean matches any `canonical_question` in answers.json
         exactly (after the same cleaning pass on the canonical questions).

      3. Fuzzy match: use difflib.SequenceMatcher or rapidfuzz to compare
         `clean` against all `match_phrases` in answers.json. Return the
         intent of the best match if score >= threshold.

      4. LLM fallback: if no fuzzy match found, call:
           from src.llm.classifier import classify_field
           result = classify_field(label_text, context="", profile=profile)
           return result.get("intent", "unknown")

      5. Return "unknown" if everything fails.
    """
    # TODO: Implement normalization
    # Placeholder: return a lowercased, stripped version for now
    cleaned = label_text.lower().strip()
    return cleaned
