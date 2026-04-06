"""
pipeline.py — Shared fill pipeline used by all adapters.

Eliminates the duplicated normalize→match→score→fill loop from every
adapter.  Each adapter calls ``run_fill_pipeline()`` per page/step and
gets back a list of fill result dicts ready for the review UI.
"""

from src.engine.normalizer import normalize_question
from src.engine.matcher import match_answer
from src.engine.confidence import score_confidence, get_fill_decision
from src.engine.filler import fill_field
from src.llm.drafter import draft_answer


def run_fill_pipeline(
    page,
    fields: list,
    profile: dict,
    answers: dict,
    mode: str,
    *,
    resume_wait_ms: int = 2000,
    redetect_after_upload=None,
) -> list:
    """
    Run the standard fill pipeline for a list of field descriptors.

    Args:
        page:                  Playwright Page/Frame object.
        fields:                List of field descriptor dicts.
        profile:               Parsed profile.json dict.
        answers:               Parsed answers.json dict.
        mode:                  Submission mode string.
        resume_wait_ms:        How long to wait after a file upload (ms).
        redetect_after_upload: Optional callable(page) -> list[fields] to
                               re-detect fields after a resume upload causes
                               auto-population.  If provided, fill_form is
                               NOT responsible for processing the fresh fields
                               — it just returns the re-detected list so the
                               caller can decide.

    Returns:
        List of fill result dicts — one per processed field.
    """
    results = []

    for field in fields:
        label = field.get("label", "")
        field_type = field.get("field_type", "text")
        context = field.get("section", "")

        # ---- File upload (resume) — special path ----------------------------
        if field_type == "file":
            result = _handle_file_upload(page, field, profile, resume_wait_ms, redetect_after_upload)
            results.append(result)
            continue

        # ---- Standard pipeline: normalize → match → score → fill -----------
        intent = normalize_question(label, answers=answers)
        match_result = match_answer(intent, profile, answers, raw_label=label)

        answer = match_result.get("answer") or match_result.get("answer_long")
        source = match_result.get("source", "none")

        # ---- Pre-generated cover letter shortcut ----------------------------
        if not answer and intent == "cover_letter" and profile.get("_cover_letter_text"):
            answer = profile["_cover_letter_text"]
            source = "llm"
            match_result["confidence"] = "high"
            match_result["requires_review"] = True

        # ---- LLM draft fallback for long-text fields -------------------------
        if not answer and field_type in ("textarea",):
            answer = draft_answer(label, profile, context)
            if answer:
                source = "llm"
                match_result["confidence"] = "medium"
                match_result["requires_review"] = True

        # ---- Demographic defaults fallback -----------------------------------
        if not answer and field_type == "select":
            answer = _try_demographic_default(intent, field, answers)
            if answer:
                source = "answers"
                match_result["confidence"] = "high"

        score = score_confidence(match_result)
        decision = get_fill_decision(score, match_result, profile)

        filled = False
        if answer and decision in ("auto_fill", "fill_and_flag"):
            filled = fill_field(page, field, str(answer), field_type)

        results.append({
            "field":           field,
            "proposed_answer": answer,
            "confidence":      score,
            "source":          source,
            "requires_review": match_result.get("requires_review", False) or decision == "fill_and_flag",
            "filled":          filled,
            "intent":          intent,
            "notes":           match_result.get("notes", ""),
        })

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_file_upload(page, field, profile, wait_ms, redetect_fn) -> dict:
    """Handle a file input — upload resume if available."""
    resume_path = profile.get("_resume_path")
    if resume_path:
        filled = fill_field(page, field, resume_path, "file")
        if filled and wait_ms > 0:
            page.wait_for_timeout(wait_ms)
        return {
            "field": field,
            "proposed_answer": resume_path,
            "confidence": 1.0,
            "source": "profile",
            "requires_review": False,
            "filled": filled,
            "intent": "resume",
            "notes": "",
        }
    return {
        "field": field,
        "proposed_answer": None,
        "confidence": 0.0,
        "source": "none",
        "requires_review": True,
        "filled": False,
        "intent": "resume",
        "notes": "No resume file found",
    }


_DEMOGRAPHIC_INTENTS = {
    "gender", "race", "ethnicity", "veteran_status",
    "disability_status", "demographic_gender",
    "demographic_race", "demographic_veteran",
    "demographic_disability",
}


def _try_demographic_default(intent: str, field: dict, answers: dict) -> str | None:
    """
    If the field looks like a demographic EEO question, check whether
    answers.json has a common_select_values mapping for it and try to
    match one of the provided options.
    """
    if not any(kw in intent.lower() for kw in ("gender", "race", "ethnic", "veteran", "disab")):
        return None

    defaults = answers.get("demographic_defaults", {})
    select_values = defaults.get("common_select_values", {})

    options = field.get("options") or []
    options_lower = [o.lower().strip() for o in options]

    # For each demographic category, check if any of the preferred
    # decline values appear in the select options.
    for _category, preferred_values in select_values.items():
        for pv in preferred_values:
            pv_lower = pv.lower().strip()
            for i, opt_lower in enumerate(options_lower):
                if pv_lower in opt_lower or opt_lower in pv_lower:
                    return options[i]

    return None
