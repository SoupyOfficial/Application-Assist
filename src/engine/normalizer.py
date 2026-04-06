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
from rapidfuzz import fuzz, process


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
    # Answer bank intents — common form label phrasings
    "salary expectations":          "salary_expectations",
    "desired salary":               "salary_expectations",
    "expected compensation":        "salary_expectations",
    "compensation expectations":    "salary_expectations",
    "start date":                   "earliest_start_date",
    "earliest start date":          "earliest_start_date",
    "available start date":         "earliest_start_date",
    "when can you start":           "earliest_start_date",
    "notice period":                "notice_period",
    "how much notice":              "notice_period",
    "willing to relocate":          "willing_to_relocate",
    "open to relocation":           "willing_to_relocate",
    "relocation":                   "willing_to_relocate",
    "willing to travel":            "willing_to_travel",
    "travel requirements":          "willing_to_travel",
    "work arrangement":             "work_arrangement",
    "preferred work arrangement":   "work_arrangement",
    "remote hybrid onsite":         "work_arrangement",
    "background check":             "background_check_consent",
    "background check consent":     "background_check_consent",
    "drug screening":               "drug_screening_consent",
    "drug test":                    "drug_screening_consent",
    "noncompete":                   "noncompete_agreement",
    "non compete":                  "noncompete_agreement",
    "noncompete agreement":         "noncompete_agreement",
    "how did you hear about us":    "how_did_you_hear",
    "how did you hear":             "how_did_you_hear",
    "referral source":              "how_did_you_hear",
    "source":                       "how_did_you_hear",
    "previously employed":          "previous_employee",
    "previous employee":            "previous_employee",
    "have you worked here before":  "previous_employee",
    "security clearance":           "security_clearance",
    "clearance level":              "security_clearance",
    "criminal history":             "criminal_history",
    "felony":                       "criminal_history",
    "convicted":                    "criminal_history",
    "age verification":             "age_verification",
    "are you 18":                   "age_verification",
    "are you at least 18":          "age_verification",
    "education level":              "highest_education_level",
    "highest education":            "highest_education_level",
    "highest degree":               "highest_education_level",
    "gpa":                          "gpa",
    "grade point average":          "gpa",
    "graduation year":              "graduation_year",
    "year of graduation":           "graduation_year",
    "certifications":               "certifications",
    "professional certifications":  "certifications",
    "languages":                    "languages_spoken",
    "languages spoken":             "languages_spoken",
    "referral":                     "referral_name",
    "referral name":                "referral_name",
    "who referred you":             "referral_name",
    "conflict of interest":         "conflict_of_interest",
    "accommodation":                "disability_accommodation",
    "disability accommodation":     "disability_accommodation",
    "reasonable accommodation":     "disability_accommodation",
    "terms and conditions":         "terms_and_conditions",
    "eeo":                          "eeo_acknowledgment",
    "equal employment":             "eeo_acknowledgment",
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
    # Only fuzzy match short labels (long questions should go through answers matching)
    if len(cleaned_label.split()) <= 5:
        matches = process.extractOne(
            cleaned_label, LABEL_TO_PROFILE_INTENT.keys(), score_cutoff=85
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
            score = fuzz.ratio(cleaned, phrase_cleaned) / 100.0
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
