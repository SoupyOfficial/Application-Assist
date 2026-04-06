# Application-Assist — Full Architecture & Design Document

**Created:** 2026-04-05  
**Last updated:** 2026-04-05  
**Status:** Fully implemented — all modules coded and syntax-verified. Pseudo-code sections below now have real implementations in source.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Flow — End to End](#2-data-flow--end-to-end)
3. [Component Architecture](#3-component-architecture)
4. [Data Model Contracts](#4-data-model-contracts)
5. [Module-by-Module Pseudo-Code](#5-module-by-module-pseudo-code)
6. [Platform Adapter Strategy](#6-platform-adapter-strategy)
7. [LLM Integration Design](#7-llm-integration-design)
8. [Error Handling & Safety Model](#8-error-handling--safety-model)
9. [Testing Strategy](#9-testing-strategy)
10. [Design Decisions & Tradeoffs](#10-design-decisions--tradeoffs)
11. [Implementation Order](#11-implementation-order)
12. [Open Questions](#12-open-questions)

---

## 1. System Overview

Application-Assist is a **local, semi-automatic job application engine**. It uses browser automation (Playwright) to fill ATS (Applicant Tracking System) forms using a structured personal profile and answer bank. The human remains in the loop for all judgment calls.

### Core Pipeline

```
URL → Detect ATS → Launch Browser → Extract Fields → Normalize → Match → Score → Fill → Review → Submit/Pause
```

### Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                          CLI (main.py)                               │
│  Parses args, loads dotenv, orchestrates pipeline, Playwright lifecycle │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────┐     ┌─────────────────────────────────────┐
│   Detector            │     │  Data Layer                         │
│   detector.py         │     │  profile.json + answers.json        │
│   platforms/*.py      │     │  (loaded once at startup)           │
│                       │     └──────────────┬──────────────────────┘
│  URL patterns → DOM   │                    │
│  fallback → generic   │                    │
└───────────┬───────────┘                    │
            │ platform_name                  │
            ▼                                │
┌───────────────────────┐                    │
│   Browser Layer       │                    │
│   browser/helpers.py  │                    │
│   Iframe detection    │                    │
│   Login wall/CAPTCHA  │                    │
│   Shadow DOM pierce   │                    │
│   Multi-page nav      │                    │
│   SPA readiness wait  │                    │
└───────────┬───────────┘                    │
            │ page/frame                     │
            ▼                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Platform Adapter                             │
│   greenhouse.py | lever.py | ashby.py | workday.py | generic.py  │
│                                                                   │
│   BaseAdapter provides default multi-page fill_form():            │
│     1. get_form_frame(page) → resolve iframe context              │
│     2. detect blockers (login wall, CAPTCHA) → pause if found     │
│     3. Loop: detect_fields → shared pipeline → next page          │
│                                                                   │
│   Shared Fill Pipeline (adapters/pipeline.py):                    │
│     For each field:                                               │
│      ├── normalizer.normalize_question(label)  → intent           │
│      ├── matcher.match_answer(intent, raw_label=...)  → result    │
│      │   └── (inverted phrasing detection + answer swap)          │
│      ├── _try_demographic_default(intent, field, answers)         │
│      ├── confidence.score_confidence(result)   → score            │
│      ├── confidence.get_fill_decision(score)   → decision         │
│      └── filler.fill_field(page, locator, ...) → filled           │
│                                                                   │
│   Adapters only implement: detect_fields() + submit()             │
│   (Workday overrides fill_form() for multi-step wizard logic)     │
└───────────┬───────────────────────────────────────────────────────┘
            │                                    ▲
            │                          ┌─────────┴─────────┐
            │                          │   LLM Layer       │
            │                          │   classifier.py   │
            │                          │   drafter.py      │
            │                          │   (Anthropic API) │
            │                          └───────────────────┘
            │ fill_results[]
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Review UI (terminal.py)                      │
│                                                                   │
│   1. Render summary table of all fields                           │
│   2. Batch-approve high-confidence, non-review fields             │
│   3. Individual review for flagged/low-confidence fields          │
│   4. Return approved_results[] with final_answer + action         │
└───────────┬───────────────────────────────────────────────────────┘
            │ approved_results[]
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Submission Gate (adapter.submit)                │
│                                                                   │
│   Mode-dependent:                                                 │
│     fill_only           → do nothing, leave browser open          │
│     fill_and_pause      → prompt "Submit? (y/n)"                  │
│     fill_review_submit  → auto-submit if no flags remain          │
└───────────┬───────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Tracker (db.py)                                 │
│                                                                   │
│   Log: date, company, role, URL, platform, mode, status,          │
│         time_saved, notes → applications.db (SQLite)              │
└───────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow — End to End

This section traces a single application from CLI invocation to completion.

### Phase A: Initialization

```
1. User runs: python src/main.py --url <URL> --mode fill_and_pause --resume backend
2. main.py parses args
3. Load profile.json → profile dict
4. Load answers.json → answers dict
5. Resolve resume path: resumes/{label}.pdf → verify file exists
6. Initialize tracker DB (CREATE TABLE IF NOT EXISTS)
7. Record start_time for time-savings estimation
```

### Phase B: Detection

```
8. Call detector.detect(url) → platform_name
   a. Iterate PLATFORMS list: greenhouse, lever, ashby, workday
   b. For each, call platform_module.matches_url(url)
   c. If match → return platform_name (fast path, no browser needed)
   d. If no URL match → proceed to DOM detection (requires browser)
```

### Phase C: Browser Launch

```
9. Launch Playwright Chromium (headless=False — user sees the browser)
10. Navigate to URL: page.goto(url, wait_until="networkidle")
11. If platform still unknown, call detector.detect(url, page) for DOM detection
    a. For each platform_module, call detect_from_dom(page)
    b. Check DOM markers, meta tags, form structure
    c. If match → platform_name; else → "generic"
12. Instantiate adapter: adapter = get_adapter(platform_name)
```

### Phase D: Field Extraction

```
13. adapter.detect_fields(page) → raw_fields[]
    Each field = {locator, label, field_type, name, required, section}
14. Log: "[info] Detected {len(raw_fields)} fields on {platform_name}"
```

### Phase E: Fill Pipeline (per field)

```
For each field in raw_fields:

15. NORMALIZE: intent = normalizer.normalize_question(field.label, answers)
    a. Clean: lowercase, strip punctuation
    b. Exact match against answers[].canonical_question → intent
    c. Fuzzy match against answers[].match_phrases → intent (if score ≥ 0.8)
    d. Profile field map lookup (first_name, email, etc.) → intent
    e. LLM fallback: classifier.classify_field(label, context) → intent
    f. If all fail → intent = "unknown"

16. MATCH: match_result = matcher.match_answer(intent, profile, answers)
    a. Exact intent match in answers.json → build result
    b. Profile field lookup (PROFILE_FIELD_MAP) → build result
    c. No match → {answer: None, confidence: "none", requires_review: True}

17. SCORE: score = confidence.score_confidence(match_result)
           decision = confidence.get_fill_decision(score, match_result)

18. APPLY SAFETY RULES:
    a. If intent in never_auto_submit → decision = "fill_and_flag" at most
    b. If intent in always_review → decision = "fill_and_flag"
    c. If requires_review is True → decision = max("fill_and_flag", decision)

19. FILL OR SKIP:
    a. If decision == "auto_fill" or "fill_and_flag":
       filler.fill_field(page, field.locator, answer, field.field_type) → success
    b. If decision == "skip_and_ask":
       Leave field empty, flag for manual input in review UI

20. BUILD FILL RESULT:
    fill_result = {
       field, proposed_answer, confidence_score, source,
       requires_review, decision, filled, intent, notes
    }
```

### Phase F: Resume Upload Handling

```
21. If any field.field_type == "file" and was filled with a resume:
    a. Wait for upload to complete: page.wait_for_load_state("networkidle")
    b. Wait additional 2-3 seconds for ATS auto-population (platform-specific)
    c. Re-run adapter.detect_fields(page) to get updated field list
    d. Diff the old and new field lists:
       - Newly populated fields → mark as "auto_populated", high confidence
       - Changed fields → update fill_results with new values
       - Preserve user-filled fields that were not overwritten
```

### Phase G: LLM Drafting (if needed)

```
22. For any fill_result where:
    - decision == "skip_and_ask" AND field_type in ("text", "textarea")
    - OR intent matches a behavioral/open-ended pattern
    Call: drafter.draft_answer(question, profile, context) → draft text
    Set fill_result.proposed_answer = draft text
    Set fill_result.source = "llm"
    Set fill_result.requires_review = True  (ALWAYS for LLM drafts)
```

### Phase H: Review UI

```
23. review.terminal.review_session(fill_results[]) → approved_results[]
    a. Render summary table
    b. Batch-approve prompt for auto_fill fields
    c. Individual review for flagged/low-confidence/requires_review fields
    d. Rejected fields → clear from form (filler.clear_field)
    e. Edited fields → re-fill with user's edited answer
    f. Return approved_results with final_answer and action
```

### Phase I: Submission

```
24. Apply re-fills: for any field where action == "edit":
    filler.fill_field(page, field.locator, final_answer, field_type)

25. Submission gate (mode-dependent):
    a. fill_only → print "[info] Fill complete. Browser left open." → done
    b. fill_and_pause → prompt "Submit application? (y/n)"
       If yes: adapter.submit(page) → success/failure
       If no: print "[info] Application not submitted." → done
    c. fill_review_submit_if_safe:
       If no requires_review fields remain with action != "accept":
         adapter.submit(page) → success/failure
       Else:
         prompt "Some fields were flagged. Submit anyway? (y/n)"
```

### Phase J: Tracking

```
26. Calculate time_saved = elapsed_time * MANUAL_MULTIPLIER (rough estimate)
27. tracker.log_application(
       url, company, role, platform, mode, status, time_saved, notes
    )
28. Print summary and exit
```

---

## 3. Component Architecture

### 3.1 CLI Entry Point — `main.py`

**Responsibility:** Parse args, load data, orchestrate the full pipeline, manage Playwright lifecycle.

**Owns:**
- Argument validation
- Data file loading
- Playwright browser/page lifecycle (context manager)
- Timer for time-saved estimation
- Calling detector → adapter → review → submit → tracker in sequence
- Top-level error handling and graceful exit

**Does NOT own:**
- Field detection logic (adapter)
- Fill logic (engine)
- Review presentation (review UI)
- Database schema (tracker)

### 3.2 Detector — `detector/`

**Responsibility:** Identify the ATS platform from a URL and/or live DOM.

**Architecture:**
- `detector.py`: Orchestrator — iterates platform modules in priority order
- `platforms/*.py`: One module per ATS — each exports `PLATFORM_NAME`, `matches_url()`, optional `detect_from_dom()`

**Detection Priority:**
1. URL regex match (fast, no browser)  
2. DOM marker inspection (meta tags, data attributes, form actions)  
3. Fallback → "generic"

**Extension Model:** Adding a new ATS = create a new `platforms/newats.py` with `PLATFORM_NAME` and `matches_url()`, then add it to the `PLATFORMS` list in `detector.py`.

### 3.3 Platform Adapters — `adapters/`

**Responsibility:** ATS-specific form interaction — field detection, fill orchestration, submission.

**Architecture:**
- `base.py`: `BaseAdapter` — provides default multi-page `fill_form()` with iframe resolution, login wall/CAPTCHA detection, shadow DOM fallback, and per-page field loop
- `pipeline.py`: Shared fill pipeline — the normalize→match→score→fill loop used by all adapters, including demographic default handling and inverted phrasing detection
- One concrete adapter per platform: `greenhouse.py`, `lever.py`, `ashby.py`, `workday.py`, `generic.py`

**Contract:**
```
detect_fields(page) → list[FieldDescriptor]    # REQUIRED — each adapter implements
fill_form(page, profile, answers, mode) → list[FillResult]  # DEFAULT in BaseAdapter; Workday overrides
submit(page) → bool                             # DEFAULT in BaseAdapter; each adapter can override
```

**Key architectural change from original design:** Adapters no longer duplicate the fill loop. `BaseAdapter.fill_form()` handles the complete multi-page lifecycle:
1. Resolve iframe context via `get_form_frame()`
2. Detect login walls and CAPTCHAs, pausing for user
3. Loop: `detect_fields()` → `run_fill_pipeline()` → `try_next_page()`
4. Shadow DOM fallback if field count is suspiciously low

Adapters only implement `detect_fields()` (platform-specific CSS selectors) and optionally `submit()` (platform-specific button selectors). Workday overrides `fill_form()` entirely for its custom multi-step wizard.

### 3.4 Browser Layer — `browser/`

**Responsibility:** Handle real-world browser concerns that span all platforms.

**Module:**
- `helpers.py` — Stateless utilities for page readiness, iframe handling, blocker detection, shadow DOM, multi-page navigation

**Capabilities:**
- `wait_for_page_ready()` — SPA-aware readiness (networkidle + DOM stability)
- `wait_for_navigation_settle()` — Post-navigation loader/spinner detection
- `detect_login_wall()` / `detect_captcha()` — Pattern-based blocker detection
- `wait_for_user_to_clear_blocker()` — Pause automation for manual user intervention
- `get_form_frame()` — Automatic iframe detection and context switching (Greenhouse embed, iCIMS, BambooHR, Jobvite, etc.)
- `discover_fields_with_shadow_dom()` — Piercing shadow DOM scan as fallback
- `detect_multi_page()` / `try_next_page()` / `is_final_step()` — Multi-page form navigation
- `find_and_click_submit()` — Platform-agnostic submit button finder

### 3.4 Fill Engine — `engine/`

**Responsibility:** Platform-agnostic field normalization, answer matching, confidence scoring, and Playwright field filling.

**Modules:**
- `normalizer.py` — raw label → canonical intent string
- `matcher.py` — intent → best answer from answers.json or profile.json
- `confidence.py` — match result → numeric score + fill decision
- `filler.py` — Playwright locator + answer → filled field

**These are pure functions (except filler, which interacts with Playwright).** They take inputs and return outputs. No state, no side effects beyond filler's DOM interaction.

### 3.5 LLM Layer — `llm/`

**Responsibility:** Fallback classification of ambiguous fields + drafting open-ended answers.

**Modules:**
- `classifier.py` — label → intent (when fuzzy matching fails)
- `drafter.py` — question + profile → drafted answer text

**Design constraints:**
- Both are fallback paths — the majority of fields should be resolved without LLM calls
- All LLM outputs require review (never auto-submitted)
- Errors are swallowed (return empty/unknown) — LLM is non-critical
- API calls should be minimized (no per-field calls for known intents)

### 3.6 Review UI — `review/`

**Responsibility:** Present filled fields to the user for approval before submission.

**Module:**
- `terminal.py` — Rich-based terminal UI

**Flow:**
1. Summary table (all fields at a glance)
2. Batch-approve prompt (high-confidence, non-review fields)
3. Per-field review (flagged/low-confidence fields)
4. Return decisions: accept / reject / edit with final answers

### 3.7 Tracker — `tracker/`

**Responsibility:** Persist application history to local SQLite.

**Module:**
- `db.py` — init, log, query, stats

---

## 4. Data Model Contracts

### 4.1 FieldDescriptor (returned by adapter.detect_fields)

```python
FieldDescriptor = {
    "locator":    Locator,      # Playwright Locator for the input element
    "label":      str,          # Visible label text (cleaned)
    "field_type": str,          # "text" | "select" | "radio" | "checkbox" | "file" | "date" | "textarea"
    "name":       str,          # HTML name or id attribute
    "required":   bool,         # Whether the field is marked required
    "section":    str,          # Logical section: "personal_info" | "work_auth" | "custom" | "demographics" | "resume"
    "options":    list | None,  # For select/radio: list of option text strings
    "placeholder": str | None,  # Placeholder text if present
}
```

### 4.2 MatchResult (returned by matcher.match_answer)

```python
MatchResult = {
    "intent":          str,            # Canonical intent string
    "answer":          str | None,     # Short answer to fill
    "answer_long":     str | None,     # Long-form answer (for textareas)
    "confidence":      str,            # "high" | "medium" | "low" | "none"
    "source":          str,            # "answers_bank" | "profile" | "llm" | "none"
    "requires_review": bool,           # Whether human must approve
    "answer_entry":    dict | None,    # Full answers.json entry if from answer bank
    "notes":           str | None,     # Edge-case notes
    "match_score":     float | None,   # Fuzzy match score (0.0–1.0) if applicable
}
```

### 4.3 FillResult (returned by adapter.fill_form, consumed by review UI)

```python
FillResult = {
    "field":            FieldDescriptor,  # Original field descriptor
    "intent":           str,              # Resolved intent
    "proposed_answer":  str | None,       # The answer proposed for this field
    "confidence_score": float,            # Numeric confidence (0.0–1.0)
    "source":           str,              # "answers_bank" | "profile" | "llm" | "manual"
    "requires_review":  bool,             # Whether review is required
    "decision":         str,              # "auto_fill" | "fill_and_flag" | "skip_and_ask"
    "filled":           bool,             # Whether filler successfully filled the field
    "notes":            str | None,       # Notes for the reviewer
}
```

### 4.4 ApprovedResult (returned by review UI, consumed by submission gate)

```python
ApprovedResult = {
    **FillResult,                       # All FillResult fields, plus:
    "final_answer":  str | None,        # The answer to actually use
    "action":        str,               # "accept" | "reject" | "edit"
}
```

### 4.5 Profile Field Map (used by matcher.py)

```python
PROFILE_FIELD_MAP = {
    # Intent string → (dotpath into profile.json, field_type)
    "first_name":          ("identity.legal_first_name",      "text"),
    "last_name":           ("identity.legal_last_name",       "text"),
    "full_name":           ("identity.full_name",             "text"),
    "preferred_name":      ("identity.preferred_first_name",  "text"),
    "email":               ("identity.email_primary",         "text"),
    "phone":               ("identity.phone_formatted",       "text"),
    "linkedin_url":        ("links.linkedin",                 "text"),
    "github_url":          ("links.github",                   "text"),
    "portfolio_url":       ("links.portfolio",                "text"),
    "city":                ("location.city",                  "text"),
    "state":               ("location.state",                 "text"),
    "zip":                 ("location.zip",                   "text"),
    "address_line_1":      ("location.address_line_1",        "text"),
    "country":             ("location.country",               "text"),
    "current_company":     ("work_history[0].company",        "text"),
    "current_title":       ("work_history[0].title",          "text"),
    "university":          ("education[0].institution",       "text"),
    "degree":              ("education[0].degree",            "text"),
    "graduation_year":     ("education[0].graduation_year",   "text"),
    "gpa":                 ("education[0].gpa",               "text"),
}
```

### 4.6 Answer Bank Schema (answers.json structure)

```python
# Top level
{
    "answers": [
        {
            "intent":              str,         # Canonical intent (primary key)
            "canonical_question":  str,         # The "standard" phrasing of this question
            "match_phrases":       list[str],   # Alternative phrasings for fuzzy matching
            "field_type":          str,         # Expected field type hint
            "answer":              str | None,  # Short answer
            "answer_long":         str | None,  # Long-form answer for textareas
            "confidence":          str,         # "high" | "medium" | "low" | "dynamic"
            "requires_review":     bool,        # Must human approve?
            "auto_submit":         bool,        # Safe to auto-submit?
            "notes":               str | None,  # Edge case notes
            "inverted_phrasing":   str | None,  # Opposite phrasing to detect & flip
        },
    ],
    "behavioral_stories": [...],
    "demographic_defaults": {...},
}
```

---

## 5. Module-by-Module Pseudo-Code

### 5.1 main.py — Orchestrator

```
function main():
    args = parse_args()                          # --url, --mode, --profile, --answers, --resume
    profile = load_json(args.profile)
    answers = load_json(args.answers)
    resume_path = resolve_resume(args.resume)    # "resumes/{label}.pdf", verify exists

    tracker.init_db()
    start_time = now()

    # --- Detection (Phase 1: URL-only, no browser needed) ---
    platform = detector.detect(args.url)

    # --- Browser launch ---
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.url, wait_until="networkidle")

        # --- Detection (Phase 2: DOM-based, if URL didn't match) ---
        if platform == "generic":
            platform = detector.detect(args.url, page)

        # --- Get adapter ---
        adapter = get_adapter(platform)

        # --- Fill pipeline ---
        fill_results = adapter.fill_form(page, profile, answers, args.mode)

        # --- Review ---
        if args.mode != "fill_only":
            approved = review.terminal.review_session(fill_results)
        else:
            approved = auto_accept_all(fill_results)

        # --- Re-fill edited fields ---
        apply_edits(page, approved)

        # --- Submission gate ---
        status = handle_submission(page, adapter, approved, args.mode)

        # --- Track ---
        elapsed = now() - start_time
        tracker.log_application(
            url=args.url, company=extract_company(page),
            role=extract_role(page), ats_platform=platform,
            mode=args.mode, status=status,
            time_saved_seconds=estimate_time_saved(elapsed),
        )

        # --- Keep browser open for fill_only mode ---
        if args.mode == "fill_only":
            input("Press Enter to close the browser...")

        browser.close()


function get_adapter(platform_name) -> BaseAdapter:
    ADAPTER_MAP = {
        "greenhouse": GreenhouseAdapter(),
        "lever":      LeverAdapter(),
        "ashby":      AshbyAdapter(),
        "workday":    WorkdayAdapter(),
        "generic":    GenericAdapter(),
    }
    return ADAPTER_MAP.get(platform_name, GenericAdapter())


function handle_submission(page, adapter, approved, mode) -> str:
    if mode == "fill_only":
        return "filled"

    if mode == "fill_and_pause":
        confirm = prompt("Submit this application? (y/n)")
        if confirm == "y":
            success = adapter.submit(page)
            return "submitted" if success else "error"
        return "filled"

    if mode == "fill_review_submit_if_safe":
        has_flags = any(r["requires_review"] and r["action"] != "accept" for r in approved)
        if not has_flags:
            success = adapter.submit(page)
            return "submitted" if success else "error"
        else:
            confirm = prompt("Flagged fields remain. Submit anyway? (y/n)")
            if confirm == "y":
                success = adapter.submit(page)
                return "submitted" if success else "error"
            return "filled"
```

### 5.2 detector.py — Platform Detection

```
PLATFORMS = [greenhouse, lever, ashby, workday]  # ordered by prevalence

function detect(url, page=None) -> str:
    # Pass 1: URL regex (fast, no browser)
    for platform_module in PLATFORMS:
        if platform_module.matches_url(url):
            return platform_module.PLATFORM_NAME

    # Pass 2: DOM markers (requires Playwright page)
    if page is not None:
        for platform_module in PLATFORMS:
            if platform_module.detect_from_dom(page):
                return platform_module.PLATFORM_NAME

    return "generic"
```

### 5.3 normalizer.py — Field Label → Intent

```
import re
import difflib

# Threshold for fuzzy match acceptance
FUZZY_THRESHOLD = 0.80

function normalize_question(label_text, answers, profile=None, threshold=FUZZY_THRESHOLD) -> str:
    # Step 1: Clean the input
    cleaned = label_text.lower().strip()
    cleaned = re.sub(r'[^\w\s]', '', cleaned)        # strip punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned)            # collapse whitespace

    if not cleaned:
        return "unknown"

    # Step 2: Check profile field map for simple identity fields
    # (e.g., "first name" → "first_name", "email" → "email")
    profile_intent = match_profile_field_label(cleaned)
    if profile_intent:
        return profile_intent

    # Step 3: Exact match against canonical_question in answers.json
    for entry in answers.get("answers", []):
        canonical_cleaned = clean(entry["canonical_question"])
        if cleaned == canonical_cleaned:
            return entry["intent"]

    # Step 4: Fuzzy match against all match_phrases
    best_score = 0.0
    best_intent = None
    for entry in answers.get("answers", []):
        phrases = [entry["canonical_question"]] + entry.get("match_phrases", [])
        for phrase in phrases:
            score = difflib.SequenceMatcher(None, cleaned, clean(phrase)).ratio()
            if score > best_score:
                best_score = score
                best_intent = entry["intent"]

    if best_score >= threshold and best_intent:
        return best_intent

    # Step 5: LLM fallback
    from src.llm.classifier import classify_field
    result = classify_field(label_text, context="", profile=profile or {})
    if result["intent"] != "unknown" and result["confidence"] >= 0.6:
        return result["intent"]

    return "unknown"


# Map common label text patterns to profile field intents
LABEL_TO_PROFILE_INTENT = {
    "first name":     "first_name",
    "last name":      "last_name",
    "full name":      "full_name",
    "name":           "full_name",
    "email":          "email",
    "email address":  "email",
    "phone":          "phone",
    "phone number":   "phone",
    "linkedin":       "linkedin_url",
    "linkedin url":   "linkedin_url",
    "github":         "github_url",
    "github url":     "github_url",
    "website":        "portfolio_url",
    "portfolio":      "portfolio_url",
    "city":           "city",
    "state":          "state",
    "zip":            "zip",
    "zip code":       "zip",
    "postal code":    "zip",
    "country":        "country",
    "address":        "address_line_1",
    "street address": "address_line_1",
    "current company":"current_company",
    "current title":  "current_title",
    "school":         "university",
    "university":     "university",
    "degree":         "degree",
}

function match_profile_field_label(cleaned_label) -> str | None:
    # Exact match
    if cleaned_label in LABEL_TO_PROFILE_INTENT:
        return LABEL_TO_PROFILE_INTENT[cleaned_label]
    # Fuzzy match against profile labels (for minor variations)
    matches = difflib.get_close_matches(cleaned_label, LABEL_TO_PROFILE_INTENT.keys(), n=1, cutoff=0.85)
    if matches:
        return LABEL_TO_PROFILE_INTENT[matches[0]]
    return None
```

### 5.4 matcher.py — Intent → Best Answer

```
function match_answer(intent, profile, answers) -> MatchResult:
    # Priority 1: Exact intent match in answers.json
    for entry in answers.get("answers", []):
        if entry["intent"] == intent:
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
        dotpath, field_type = PROFILE_FIELD_MAP[intent]
        value = resolve_dotpath(profile, dotpath)
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

    # Priority 3: Fuzzy cross-match (intent doesn't match exactly, but
    # maybe the raw intent string is close to a match_phrase in another entry)
    best_score = 0.0
    best_entry = None
    for entry in answers.get("answers", []):
        phrases = [entry["intent"]] + entry.get("match_phrases", [])
        for phrase in phrases:
            score = fuzzy_score(intent, clean(phrase))
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
            "requires_review": True,       # fuzzy → always flag
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
        "notes":           "No match found.",
        "match_score":     0.0,
    }


function resolve_dotpath(obj, dotpath) -> any:
    """Navigate a dict/list using a dot-separated path like 'identity.email_primary'
    or 'work_history[0].company'."""
    parts = dotpath.split(".")
    current = obj
    for part in parts:
        # Handle array index: "work_history[0]"
        match = re.match(r'(\w+)\[(\d+)\]', part)
        if match:
            key, idx = match.group(1), int(match.group(2))
            current = current.get(key, [])[idx] if len(current.get(key, [])) > idx else None
        else:
            current = current.get(part) if isinstance(current, dict) else None
        if current is None:
            return None
    return current
```

### 5.5 confidence.py — Scoring & Fill Decision

```
AUTO_FILL_THRESHOLD = 0.8
FILL_FLAG_THRESHOLD = 0.5

CONFIDENCE_SCORE_MAP = {
    "high": 0.9, "medium": 0.6, "low": 0.3, "none": 0.0, "dynamic": 0.5,
}

function score_confidence(match_result) -> float:
    base = match_result.get("confidence", "none")

    # Convert string label to numeric
    if isinstance(base, float):
        score = base
    else:
        score = CONFIDENCE_SCORE_MAP.get(base, 0.0)

    # Boost/penalize based on match score from fuzzy matching
    match_score = match_result.get("match_score")
    if match_score is not None and isinstance(match_score, float):
        # Blend: 70% label-based, 30% match-score-based
        score = (score * 0.7) + (match_score * 0.3)

    # If answer is None → cap at 0.3
    if match_result.get("answer") is None and match_result.get("answer_long") is None:
        score = min(score, 0.3)

    # If requires_review → cap at 0.75 (never auto_fill)
    if match_result.get("requires_review", False):
        score = min(score, 0.75)

    # If notes mention "inverted" → penalize slightly
    notes = match_result.get("notes") or ""
    if "inverted" in notes.lower():
        score = min(score, 0.65)

    return round(score, 3)


function get_fill_decision(score, match_result, profile=None) -> str:
    intent = match_result.get("intent", "")

    # Safety overrides from profile preferences
    if profile:
        prefs = profile.get("application_preferences", {})
        if intent in prefs.get("never_auto_submit", []):
            return "fill_and_flag" if score >= FILL_FLAG_THRESHOLD else "skip_and_ask"
        if intent in prefs.get("always_review", []):
            return "fill_and_flag" if score >= FILL_FLAG_THRESHOLD else "skip_and_ask"

    # Standard threshold logic
    if match_result.get("requires_review", False):
        return "fill_and_flag" if score >= FILL_FLAG_THRESHOLD else "skip_and_ask"

    if score >= AUTO_FILL_THRESHOLD:
        return "auto_fill"
    elif score >= FILL_FLAG_THRESHOLD:
        return "fill_and_flag"
    else:
        return "skip_and_ask"
```

### 5.6 filler.py — Playwright Field Filling

```
function fill_field(page, field_descriptor, answer, field_type) -> bool:
    locator = field_descriptor["locator"]

    try:
        match field_type:
            case "text":
                locator.clear()
                locator.fill(answer)
                return True

            case "textarea":
                locator.clear()
                locator.fill(answer)
                return True

            case "select":
                # Try exact label match first
                try:
                    locator.select_option(label=answer)
                    return True
                except:
                    pass
                # Fuzzy: get all options, find closest match
                options = locator.locator("option").all_text_contents()
                best = find_best_option_match(answer, options)
                if best:
                    locator.select_option(label=best)
                    return True
                return False

            case "radio":
                # Find the radio group, match answer to option label
                name = field_descriptor.get("name", "")
                radios = page.locator(f'input[type="radio"][name="{name}"]').all()
                for radio in radios:
                    label = get_label_for_input(page, radio)
                    if label.lower().strip() == answer.lower().strip():
                        radio.check()
                        return True
                # Fuzzy fallback: find closest label match
                labels = [get_label_for_input(page, r) for r in radios]
                best_idx = find_best_label_index(answer, labels)
                if best_idx is not None:
                    radios[best_idx].check()
                    return True
                return False

            case "checkbox":
                truthy = answer.lower() in ("yes", "true", "1", "checked")
                if truthy:
                    locator.check()
                else:
                    locator.uncheck()
                return True

            case "date":
                formatted = normalize_date(answer)
                locator.fill(formatted)
                return True

            case "file":
                locator.set_input_files(answer)   # answer = file path string
                return True

            case _:
                # Unknown field type, try fill() as best effort
                locator.fill(answer)
                return True

    except Exception as e:
        log_warning(f"Failed to fill field '{field_descriptor.get('label')}': {e}")
        return False


function clear_field(page, field_descriptor, field_type):
    """Clear a previously filled field (used when user rejects an answer)."""
    locator = field_descriptor["locator"]
    match field_type:
        case "text" | "textarea" | "date":
            locator.clear()
        case "select":
            locator.select_option(index=0)          # reset to first option
        case "checkbox":
            locator.uncheck()
        case "radio":
            pass                                     # radios can't be unchecked; skip
        case "file":
            locator.set_input_files([])              # clear file input


function get_label_for_input(page, input_locator) -> str:
    """Find the visible label for an input element."""
    # 1. Check for explicit <label for="id">
    input_id = input_locator.get_attribute("id")
    if input_id:
        label_el = page.locator(f'label[for="{input_id}"]')
        if label_el.count() > 0:
            return label_el.first.text_content().strip()

    # 2. Check for wrapping <label>
    parent_label = input_locator.locator("xpath=ancestor::label")
    if parent_label.count() > 0:
        return parent_label.first.text_content().strip()

    # 3. Check aria-label
    aria = input_locator.get_attribute("aria-label")
    if aria:
        return aria.strip()

    # 4. Check aria-labelledby
    labelledby = input_locator.get_attribute("aria-labelledby")
    if labelledby:
        label_el = page.locator(f"#{labelledby}")
        if label_el.count() > 0:
            return label_el.first.text_content().strip()

    # 5. Placeholder fallback
    placeholder = input_locator.get_attribute("placeholder")
    if placeholder:
        return placeholder.strip()

    return ""
```

### 5.7 classifier.py — LLM Intent Classification

```
import anthropic, os, json

function classify_field(label, context, profile) -> ClassificationResult:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"intent": "unknown", "confidence": 0.0, "reasoning": "No API key"}

    # Build the known intents list from the profile/answers for grounding
    known_intents = [
        "work_authorization_us", "requires_sponsorship", "citizenship_status",
        "salary_expectations", "willing_to_relocate", "work_arrangement",
        "years_experience_total", "years_experience_java", "years_experience_python",
        "years_experience_javascript", "first_name", "last_name", "email", "phone",
        "linkedin_url", "github_url", "city", "state", "zip", "country",
        "current_company", "current_title", "university", "degree",
        "start_date", "willing_background_check", "willing_drug_screening",
        "gender_identity", "race_ethnicity", "veteran_status", "disability_status",
        "why_this_company", "why_this_role", "greatest_strength",
        "greatest_weakness", "five_year_goal",
    ]

    system_prompt = f"""You are a job application form field classifier.
Given a form field label and optional context, identify the canonical intent.
Return a JSON object with: intent (snake_case string), confidence (0.0-1.0), reasoning (brief string).

Known intents: {json.dumps(known_intents)}
If the field doesn't match any known intent, use a descriptive snake_case intent name.
If truly unclassifiable, return intent="unknown"."""

    user_message = f"Field label: {label}"
    if context:
        user_message += f"\nPage context: {context}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",       # fast, cheap — classification only
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        result = json.loads(response.content[0].text)
        return {
            "intent":     result.get("intent", "unknown"),
            "confidence": float(result.get("confidence", 0.0)),
            "reasoning":  result.get("reasoning", ""),
        }
    except Exception as e:
        return {"intent": "unknown", "confidence": 0.0, "reasoning": f"Error: {e}"}
```

### 5.8 drafter.py — LLM Answer Drafting

```
import anthropic, os

function draft_answer(question, profile, context="") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    profile_summary = build_profile_summary(profile)

    system_prompt = """You are drafting a job application answer for a software engineer.
Rules:
- Write in first person
- Be concise and authentic
- Ground everything in the provided background — do not fabricate experience
- Keep under 200 words unless the question clearly requires more
- Do not use filler phrases like "I am writing to express my interest"
- Be specific about technical skills and project experience"""

    user_message = f"Question: {question}\n"
    if context:
        user_message += f"Company/Role: {context}\n"
    user_message += f"\nBackground:\n{profile_summary}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",             # quality model for user-facing drafts
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()
    except Exception:
        return ""


function build_profile_summary(profile) -> str:
    """Build a concise text summary for LLM prompts. No unnecessary PII."""
    parts = []

    identity = profile.get("identity", {})
    summary = profile.get("professional_summary", {})
    parts.append(f"{identity.get('full_name', '')} — {summary.get('headline', '')}")

    # Work history
    for job in profile.get("work_history", []):
        parts.append(f"- {job['title']} at {job['company']} ({job.get('start_date', '')}–{job.get('end_date', 'present')})")
        if job.get("technologies"):
            parts.append(f"  Tech: {', '.join(job['technologies'][:8])}")

    # Education
    for edu in profile.get("education", []):
        parts.append(f"- {edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('institution', '')} ({edu.get('graduation_year', '')})")

    # Top skills
    top_skills = [s["name"] for s in profile.get("skills", []) if s.get("include")][:10]
    if top_skills:
        parts.append(f"Top skills: {', '.join(top_skills)}")

    # Key projects
    for proj in profile.get("projects", [])[:3]:
        parts.append(f"- Project: {proj['name']} — {proj.get('one_liner', '')}")

    return "\n".join(parts)
```

### 5.9 terminal.py — Review UI

```
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

console = Console()

function review_session(fill_results) -> list[ApprovedResult]:
    console.print(Panel.fit("[bold cyan]Application-Assist — Review Session[/bold cyan]"))

    if not fill_results:
        console.print("[yellow]No fields to review.[/yellow]")
        return []

    # --- Summary table ---
    render_summary_table(fill_results)

    # --- Partition fields ---
    auto_approvable = [f for f in fill_results
                       if f["decision"] == "auto_fill" and not f["requires_review"]]
    needs_review = [f for f in fill_results if f not in auto_approvable]

    # --- Batch approve ---
    if auto_approvable:
        console.print(f"\n[green]{len(auto_approvable)} fields are high-confidence and safe to auto-approve.[/green]")
        batch_choice = Prompt.ask("Batch approve these?", choices=["y", "n"], default="y")
        if batch_choice == "y":
            for f in auto_approvable:
                f["final_answer"] = f["proposed_answer"]
                f["action"] = "accept"
        else:
            # Move them all to manual review
            needs_review = fill_results
            auto_approvable = []

    # --- Individual review ---
    for field in needs_review:
        review_single_field(field)

    all_results = auto_approvable + needs_review
    render_decision_summary(all_results)
    return all_results


function review_single_field(field) -> None:
    """Show a panel for one field and prompt for action."""
    label = field.get("field", {}).get("label", "Unknown")
    proposed = field.get("proposed_answer") or "[no answer]"
    conf = field.get("confidence_score", 0.0)
    source = field.get("source", "none")
    notes = field.get("notes") or ""

    # Color confidence
    if conf >= 0.8:
        conf_display = f"[green]{conf:.2f}[/green]"
    elif conf >= 0.5:
        conf_display = f"[yellow]{conf:.2f}[/yellow]"
    else:
        conf_display = f"[red]{conf:.2f}[/red]"

    console.print(Panel(
        f"[bold]Question:[/bold]   {label}\n"
        f"[bold]Proposed:[/bold]   {proposed}\n"
        f"[bold]Confidence:[/bold] {conf_display}\n"
        f"[bold]Source:[/bold]     {source}\n"
        + (f"[bold]Notes:[/bold]      [dim]{notes}[/dim]\n" if notes else ""),
        title="[cyan]Review Field[/cyan]",
        border_style="blue",
    ))

    choice = Prompt.ask(
        "[bold](a)[/bold]ccept  [bold](r)[/bold]eject  [bold](e)[/bold]dit",
        choices=["a", "r", "e"],
        default="a",
    )

    if choice == "a":
        field["final_answer"] = field["proposed_answer"]
        field["action"] = "accept"
    elif choice == "r":
        field["final_answer"] = None
        field["action"] = "reject"
    elif choice == "e":
        custom = Prompt.ask("[cyan]Enter your answer[/cyan]")
        field["final_answer"] = custom
        field["action"] = "edit"


function render_decision_summary(results):
    """Print a quick summary of all decisions made."""
    accepted = sum(1 for r in results if r.get("action") == "accept")
    rejected = sum(1 for r in results if r.get("action") == "reject")
    edited = sum(1 for r in results if r.get("action") == "edit")
    console.print(f"\n[bold]Summary:[/bold] {accepted} accepted, {edited} edited, {rejected} rejected")
```

### 5.10 Adapter.fill_form — Shared Orchestration Logic

**Each adapter's `fill_form()` follows the same core pattern.** The only difference is platform-specific sequencing (single-page vs. multi-step).

```
function fill_form(self, page, profile, answers, mode) -> list[FillResult]:
    """Core fill orchestration — same pattern used by all adapters."""
    from src.engine import normalizer, matcher, confidence, filler

    raw_fields = self.detect_fields(page)
    fill_results = []
    resume_uploaded = False

    for field_desc in raw_fields:
        # --- Resume upload: handle specially ---
        if field_desc["field_type"] == "file" and field_desc["section"] == "resume":
            resume_path = resolve_resume_path(profile, mode)
            if resume_path:
                success = filler.fill_field(page, field_desc, resume_path, "file")
                fill_results.append(build_file_result(field_desc, resume_path, success))
                resume_uploaded = True
            continue

        # --- Standard field pipeline ---
        # 1. Normalize
        intent = normalizer.normalize_question(
            field_desc["label"], answers, profile
        )

        # 2. Match
        match_result = matcher.match_answer(intent, profile, answers)

        # 3. Handle answer selection (short vs long based on field type)
        if field_desc["field_type"] in ("textarea",) and match_result.get("answer_long"):
            chosen_answer = match_result["answer_long"]
        else:
            chosen_answer = match_result.get("answer")

        # 4. Score confidence
        score = confidence.score_confidence(match_result)
        decision = confidence.get_fill_decision(score, match_result, profile)

        # 5. Fill or skip
        filled = False
        if chosen_answer and decision in ("auto_fill", "fill_and_flag"):
            filled = filler.fill_field(page, field_desc, chosen_answer, field_desc["field_type"])

        # 6. Build result
        fill_results.append({
            "field":            field_desc,
            "intent":           intent,
            "proposed_answer":  chosen_answer,
            "confidence_score": score,
            "source":           match_result["source"],
            "requires_review":  match_result["requires_review"] or decision != "auto_fill",
            "decision":         decision,
            "filled":           filled,
            "notes":            match_result.get("notes"),
        })

    # --- Post-resume-upload re-scan ---
    if resume_uploaded:
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)  # platform-specific delay for parsing
        updated_fields = self.detect_fields(page)
        fill_results = reconcile_after_upload(fill_results, updated_fields)

    # --- LLM drafting for unanswered open-ended fields ---
    for result in fill_results:
        if (result["decision"] == "skip_and_ask"
            and result["field"]["field_type"] in ("text", "textarea")
            and result["proposed_answer"] is None):
            from src.llm.drafter import draft_answer
            context = extract_page_context(page)
            draft = draft_answer(result["field"]["label"], profile, context)
            if draft:
                result["proposed_answer"] = draft
                result["source"] = "llm"
                result["requires_review"] = True  # always review LLM output
                result["decision"] = "fill_and_flag"

    return fill_results
```

### 5.11 Generic Field Discovery — `detector/platforms/generic.py`

```
function discover_fields(page) -> list[FieldDescriptor]:
    """Scan a page for all visible form fields using generic heuristics."""
    fields = []

    # --- Text inputs ---
    for input_el in page.locator('input[type="text"], input[type="email"], input[type="tel"], input[type="url"], input[type="number"], input:not([type])').all():
        if not input_el.is_visible():
            continue
        label = get_label_for_input(page, input_el)
        fields.append({
            "locator":     input_el,
            "label":       label,
            "field_type":  categorize_input_type(input_el),
            "name":        input_el.get_attribute("name") or input_el.get_attribute("id") or "",
            "required":    input_el.get_attribute("required") is not None or input_el.get_attribute("aria-required") == "true",
            "section":     guess_section(label),
            "options":     None,
            "placeholder": input_el.get_attribute("placeholder"),
        })

    # --- Textareas ---
    for textarea in page.locator("textarea").all():
        if not textarea.is_visible():
            continue
        label = get_label_for_input(page, textarea)
        fields.append({
            "locator":     textarea,
            "label":       label,
            "field_type":  "textarea",
            "name":        textarea.get_attribute("name") or "",
            "required":    textarea.get_attribute("required") is not None,
            "section":     guess_section(label),
            "options":     None,
            "placeholder": textarea.get_attribute("placeholder"),
        })

    # --- Select dropdowns ---
    for select in page.locator("select").all():
        if not select.is_visible():
            continue
        label = get_label_for_input(page, select)
        options = select.locator("option").all_text_contents()
        fields.append({
            "locator":     select,
            "label":       label,
            "field_type":  "select",
            "name":        select.get_attribute("name") or "",
            "required":    select.get_attribute("required") is not None,
            "section":     guess_section(label),
            "options":     options,
            "placeholder": None,
        })

    # --- Radio groups ---
    # Group by name attribute to avoid duplicates
    radio_names_seen = set()
    for radio in page.locator('input[type="radio"]').all():
        name = radio.get_attribute("name")
        if name in radio_names_seen or not radio.is_visible():
            continue
        radio_names_seen.add(name)
        label = get_label_for_radio_group(page, name)
        options = get_radio_group_options(page, name)
        fields.append({
            "locator":     radio,           # points to first radio in group
            "label":       label,
            "field_type":  "radio",
            "name":        name,
            "required":    radio.get_attribute("required") is not None,
            "section":     guess_section(label),
            "options":     options,
            "placeholder": None,
        })

    # --- Checkboxes ---
    for checkbox in page.locator('input[type="checkbox"]').all():
        if not checkbox.is_visible():
            continue
        label = get_label_for_input(page, checkbox)
        fields.append({
            "locator":     checkbox,
            "label":       label,
            "field_type":  "checkbox",
            "name":        checkbox.get_attribute("name") or "",
            "required":    checkbox.get_attribute("required") is not None,
            "section":     guess_section(label),
            "options":     None,
            "placeholder": None,
        })

    # --- File inputs ---
    for file_input in page.locator('input[type="file"]').all():
        label = get_label_for_input(page, file_input)
        fields.append({
            "locator":     file_input,
            "label":       label or "Resume/Document Upload",
            "field_type":  "file",
            "name":        file_input.get_attribute("name") or "",
            "required":    file_input.get_attribute("required") is not None,
            "section":     "resume",
            "options":     None,
            "placeholder": None,
        })

    return fields


function guess_section(label) -> str:
    """Guess the logical section from the label text."""
    label_lower = label.lower()
    if any(kw in label_lower for kw in ["name", "email", "phone", "address", "city", "zip", "linkedin", "github"]):
        return "personal_info"
    if any(kw in label_lower for kw in ["authorized", "sponsorship", "visa", "work permit", "citizen"]):
        return "work_auth"
    if any(kw in label_lower for kw in ["resume", "cv", "upload"]):
        return "resume"
    if any(kw in label_lower for kw in ["gender", "race", "ethnicity", "veteran", "disability", "demographic"]):
        return "demographics"
    if any(kw in label_lower for kw in ["salary", "compensation", "pay"]):
        return "compensation"
    return "custom"
```

---

## 6. Platform Adapter Strategy

### 6.1 Architecture Pattern

All adapters inherit from `BaseAdapter` and implement the same 3-method contract. The fill pipeline is shared via engine modules. Platform differences exist only in:

| Aspect | Greenhouse | Lever | Ashby | Workday | Generic |
|---|---|---|---|---|---|
| **Form structure** | Single page | Single page | Single page | Multi-step wizard | Variable |
| **Field selectors** | `.field` CSS class | Class-based | TBD | `data-automation-id` | Generic scan |
| **Submit button** | `input[type=submit]` | Button w/ text | TBD | Step nav button | Best-effort search |
| **Resume upload** | Standard file input | Standard file input | TBD | Button-triggered | Standard file input |
| **Post-upload behavior** | Some auto-populate | Minimal | TBD | Heavy auto-populate | Varies |
| **Account required** | No | No | Sometimes | Usually | Varies |
| **Complexity** | Low | Low | Medium | High | Medium |

### 6.2 Workday Multi-Step State Machine

Workday is the most complex adapter because the application is spread across multiple wizard steps.

```
                ┌──────────────┐
                │   SIGN IN    │ (may require account creation)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ MY INFORMATION│ (contact details, resume upload)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ MY EXPERIENCE │ (work history, education — often auto-pop from resume)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ APP QUESTIONS │ (custom per-job questions)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │  VOLUNTARY   │ (EEO / demographics)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   REVIEW     │ (final review + submit)
                └──────────────┘
```

**Workday fill_form() pseudo-code:**

```
function fill_form(self, page, profile, answers, mode) -> list:
    all_results = []
    current_step = detect_current_step(page)

    while current_step != "REVIEW":
        fields = self.detect_fields(page)      # detect fields for current step
        step_results = fill_step(page, fields, profile, answers)
        all_results.extend(step_results)

        # Special: after resume upload on step MY_INFORMATION
        if current_step == "MY_INFORMATION" and has_resume_upload(fields):
            wait_for_auto_population(page)
            post_upload_fields = self.detect_fields(page)
            all_results = reconcile_after_upload(all_results, post_upload_fields)

        # Navigate to next step
        click_next(page)
        page.wait_for_load_state("networkidle")
        current_step = detect_current_step(page)

    return all_results
```

### 6.3 Greenhouse Adapter Field Detection

```
function detect_fields(self, page) -> list:
    fields = []

    # Greenhouse wraps each field in a .field div
    field_wrappers = page.locator("#application .field").all()

    for wrapper in field_wrappers:
        label_el = wrapper.locator("label").first
        label_text = label_el.text_content().strip() if label_el.count() > 0 else ""

        # Determine input type
        if wrapper.locator("input[type='file']").count() > 0:
            input_el = wrapper.locator("input[type='file']").first
            field_type = "file"
        elif wrapper.locator("select").count() > 0:
            input_el = wrapper.locator("select").first
            field_type = "select"
        elif wrapper.locator("textarea").count() > 0:
            input_el = wrapper.locator("textarea").first
            field_type = "textarea"
        elif wrapper.locator("input[type='checkbox']").count() > 0:
            input_el = wrapper.locator("input[type='checkbox']").first
            field_type = "checkbox"
        elif wrapper.locator("input[type='radio']").count() > 0:
            input_el = wrapper.locator("input[type='radio']").first
            field_type = "radio"
        else:
            input_el = wrapper.locator("input").first
            field_type = "text"

        required = wrapper.locator(".required").count() > 0 or label_text.endswith("*")

        fields.append({
            "locator":     input_el,
            "label":       label_text.rstrip("*").strip(),
            "field_type":  field_type,
            "name":        input_el.get_attribute("name") or input_el.get_attribute("id") or "",
            "required":    required,
            "section":     guess_section(label_text),
            "options":     get_options(wrapper, field_type) if field_type in ("select", "radio") else None,
            "placeholder": input_el.get_attribute("placeholder"),
        })

    return fields
```

### 6.4 When to Use the Greenhouse Job Board API

The Greenhouse Job Board API can supplement (not replace) browser automation:

```
Use API for:
  - Fetching job metadata (title, company, location) before navigating
  - Validating that a URL is a real Greenhouse job posting
  - Extracting required vs. optional fields before form interaction

Do NOT use API for:
  - Actually submitting the application (API submission is different from web form submission
    and may not be available for all job boards)
  - Replacing field detection (the live DOM is the source of truth)
```

---

## 7. LLM Integration Design

### 7.1 When LLM Is Called

The LLM is used in exactly two scenarios:

| Scenario | Module | Model | Trigger |
|---|---|---|---|
| **Field classification** | `classifier.py` | Claude Haiku (fast, cheap) | Normalizer fuzzy match fails (score < threshold) |
| **Answer drafting** | `drafter.py` | Claude Sonnet (quality) | Open-ended field with no answer bank match |

### 7.2 LLM Is Never Called For

- Fields that exactly match an answers.json intent
- Fields that fuzzy match above threshold
- Profile field lookups (name, email, phone, etc.)
- Demographic fields (always use defaults from answers.json)
- Boolean/checkbox fields with clear intent

### 7.3 LLM Cost Analysis

```
Estimated LLM calls per application:
  - Classifier: 0–3 calls (most fields match via fuzzy; only unknowns hit LLM)
  - Drafter: 0–2 calls (only for custom "why this company" or free-response)
  - Total: ~2–5 calls typical, mostly Haiku (cheap)

Estimated cost per application: < $0.01
```

### 7.4 Caching Strategy

```
LLM responses should be cached to avoid redundant API calls:

1. Classifier cache: Map (cleaned_label_text) → (intent, confidence)
   - In-memory dict, persisted across fields within one application run
   - NOT persisted across runs (field labels change between ATS platforms)

2. Drafter cache: Not cached (every question is contextual to the company/role)

3. Future: If the same question appears often, consider adding it to answers.json
   with match phrases derived from the LLM classification.
```

### 7.5 Privacy Model

```
What is sent to the LLM API:
  - Field label text (e.g., "Are you authorized to work in the US?")
  - Page context snippet (section heading, nearby text — no PII)
  - Profile summary (name, headline, work history, skills — intentionally included
    because the drafter needs it to write authentic answers)

What is NEVER sent:
  - Full raw profile.json
  - Social security numbers, financial data
  - Passwords or credentials
  - Other applicants' data (not applicable — single-user tool)

The user should review all LLM-generated content in the review UI before submission.
```

---

## 8. Error Handling & Safety Model

### 8.1 Error Categories and Responses

| Error | Category | Response |
|---|---|---|
| Profile/answers file missing | Startup | Exit with clear error message |
| Resume file missing | Startup | Warn; proceed without resume upload |
| URL unreachable | Browser | Exit with error + suggest checking URL |
| Page load timeout | Browser | Retry once; then exit with error |
| Field detection finds 0 fields | Adapter | Warn; prompt user to check if page loaded correctly |
| Normalizer returns "unknown" | Engine | Set decision = "skip_and_ask"; flag for review |
| Matcher returns no answer | Engine | Set decision = "skip_and_ask"; flag for review |
| Filler.fill_field() fails | Engine | Log warning; set filled=False; continue to next field |
| LLM API call fails | LLM | Return fallback (unknown/empty); do not block pipeline |
| LLM returns invalid JSON | LLM | Return fallback; log for debugging |
| Submit button not found | Adapter | Return False from submit(); inform user |
| Submit appears to fail | Adapter | Return False; leave browser open for manual check |
| SQLite write fails | Tracker | Log error; continue (tracking is non-critical) |
| Playwright crash | Browser | Log error; exit gracefully |

### 8.2 Safety Rules

These are enforced regardless of mode, confidence, or automation level:

```
1. NEVER auto-submit fields marked requires_review: true in answers.json
2. NEVER auto-submit intents in profile.application_preferences.never_auto_submit
3. ALWAYS flag intents in profile.application_preferences.always_review
4. NEVER submit in fill_only mode
5. NEVER fill a field with confidence < 0.5 without flagging it
6. ALWAYS show fill source and confidence in the review UI
7. ALL LLM-drafted answers require explicit review approval
8. If 0 fields detected → do not proceed to fill; warn the user
9. On any error during submission → leave browser open, do not retry
10. Inverted phrasing detection: if an answer entry has inverted_phrasing notes,
    cap confidence at 0.65 and always flag for review
```

### 8.3 Graceful Degradation

```
The system should degrade gracefully at each layer:

Detection fails    → fall back to "generic" (never block)
Normalizer fails   → intent = "unknown" → skip_and_ask
Matcher fails      → no answer → skip_and_ask
Confidence unclear → fill_and_flag (never auto_fill when uncertain)
Filler fails       → filled = False → field stays empty → user fills manually
LLM fails          → empty draft → user writes manually
Submit fails       → browser stays open → user submits manually
Tracker fails      → log warning → doesn't block the user
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Module | What to Test | Approach |
|---|---|---|
| `normalizer.py` | Label cleaning, exact match, fuzzy match, profile field map, LLM fallback | Pure function tests with mock answers.json |
| `matcher.py` | Exact intent match, profile lookup, fuzzy cross-match, no-match case | Mock profile.json + answers.json |
| `confidence.py` | Score calculation, threshold logic, safety overrides, fill decisions | Pure function tests |
| `filler.py` | `find_best_option_match`, `get_label_for_input` | Unit tests on the helper functions |
| `classifier.py` | Response parsing, error handling, fallback on API failure | Mock Anthropic client |
| `drafter.py` | `build_profile_summary`, error handling, fallback on API failure | Mock Anthropic client |
| `detector.py` | URL matching for each platform, fallback to generic | Pure tests on URL strings |
| `db.py` | init_db, log_application, get_history, get_stats | In-memory SQLite |

### 9.2 Integration Tests (with Playwright)

```
Approach: Create local HTML test fixtures that mimic real ATS form structures.
Place fixtures in tests/fixtures/*.html and serve them with a local HTTP server.

Test fixtures needed:
  - tests/fixtures/greenhouse_form.html  (single-page Greenhouse layout)
  - tests/fixtures/lever_form.html       (single-page Lever layout)
  - tests/fixtures/workday_step1.html    (Workday My Information step)
  - tests/fixtures/generic_form.html     (generic form with mixed field types)
  - tests/fixtures/tricky_fields.html    (edge cases: shadow DOM, dynamic, hidden)

Each fixture contains:
  - Named <label> elements with associated inputs
  - All field types: text, select, radio, checkbox, textarea, file
  - Required vs optional markers
  - Known answers that should fuzzy-match to answers.json entries

Tests verify:
  1. detect_fields() returns the correct field count and types
  2. Fill pipeline produces correct proposed_answers for known fields
  3. Filler actually populates the DOM correctly
  4. Review UI renders without errors
```

### 9.3 Test Data

```
tests/
├── fixtures/
│   ├── greenhouse_form.html
│   ├── lever_form.html
│   ├── workday_step1.html
│   ├── generic_form.html
│   └── tricky_fields.html
├── test_normalizer.py
├── test_matcher.py
├── test_confidence.py
├── test_filler.py         (Playwright-based)
├── test_detector.py
├── test_tracker.py
├── test_classifier.py     (mocked API)
├── test_drafter.py        (mocked API)
├── test_greenhouse_adapter.py  (Playwright + fixtures)
├── test_generic_adapter.py     (Playwright + fixtures)
└── conftest.py            (shared fixtures, mock data, Playwright setup)
```

---

## 10. Design Decisions & Tradeoffs

### D1: BaseAdapter owns fill orchestration; adapters only customize detection + submit

**Decision:** `BaseAdapter.fill_form()` provides a default multi-page-aware fill loop that resolves iframes, detects blockers, iterates pages, and calls the shared `run_fill_pipeline()` per page. Adapters only implement `detect_fields()` and optionally `submit()`.

**Why:** The original design had each adapter duplicating the 30-line normalize→match→score→fill loop. This was extracted into `adapters/pipeline.py` and the multi-page loop was moved into `BaseAdapter`. Workday overrides `fill_form()` entirely because its wizard flow requires custom step detection, but all other adapters inherit the default.

**Tradeoff:** Workday is the only adapter with custom fill logic. If future platforms have equally complex flows, they too would override. The shared pipeline handles the 80% case cleanly.

### D2: Fuzzy matching before LLM

**Decision:** The normalizer uses `difflib.SequenceMatcher` (or `rapidfuzz` if installed) for fuzzy matching against answers.json match_phrases *before* falling back to the LLM classifier.

**Why:** Speed (no network round trip), cost (no API call), reliability (deterministic). The LLM is a fallback for the ~10% of fields that don't fuzzy-match any known phrase. This keeps per-application LLM costs near zero.

**Tradeoff:** The fuzzy match threshold (0.80) needs tuning. Too low = false positives (wrong intent). Too high = too many LLM fallbacks. We start at 0.80 and adjust based on testing.

### D3: Separate confidence labels and numeric scores

**Decision:** answers.json stores confidence as string labels ("high", "medium", "low"), which `confidence.py` converts to numeric scores for fill decisions.

**Why:** Human-readable labels in the data file are easier to author and review. Numeric scores are needed for precise threshold logic. The mapping is explicit and tunable.

**Tradeoff:** Two representations of the same concept. The mapping table is a single source of truth.

### D4: fill_only as the safest default for development

**Decision:** During development, `fill_only` is recommended. The default in production is `fill_and_pause`.

**Why:** `fill_only` never touches the submit button — the browser stays open so the user can inspect everything. This is critical during development and testing to avoid accidental submissions.

### D5: No LLM for simple identity fields

**Decision:** Name, email, phone, LinkedIn, etc. are resolved by direct profile lookup — never sent to the LLM.

**Why:** These fields are unambiguous and appear on every application. Profile lookup is instant, free, and deterministic. Sending them to the LLM would be wasteful and slower.

### D6: Review UI before submission, always

**Decision:** Even in `fill_review_submit_if_safe` mode, the review UI is always shown. The "auto-submit" only skips the final confirmation prompt if all fields pass safety checks.

**Why:** The human must see what's about to be submitted. The entire design philosophy is "assist, not replace."

### D7: Generic adapter is intentionally conservative

**Decision:** The generic adapter flags nearly all fields for review, uses strict confidence thresholds, and never auto-submits.

**Why:** On unknown ATS platforms, the system has no structural assumptions to rely on. Being conservative prevents bad fills on unfamiliar forms.

### D8: SQLite for tracking (no external DB)

**Decision:** Application history is stored in a local SQLite file, not a cloud database or service.

**Why:** Zero dependencies, zero setup, zero data exfiltration. The data never leaves the machine. `sqlite3` is in Python's standard library.

### D9: Playwright over Selenium

**Decision:** Playwright is the browser automation engine.

**Why:** Better async/SPA support than Selenium. Handles shadow DOM natively. Built-in wait/auto-retry logic. Better developer experience. Actively maintained by Microsoft.

**Tradeoff:** Slightly larger install size. Requires `playwright install chromium`. But the UX and reliability gains are worth it.

### D10: Claude Haiku for classification, Sonnet for drafting

**Decision:** Two different Claude model tiers for two different tasks.

**Why:** Classification is a structured, low-token task — Haiku is fast and cheap. Drafting is a creative, quality-sensitive task — Sonnet produces better prose. The cost difference is ~10x per token, and we minimize Sonnet calls by only using it for open-ended questions.

---

## 11. Implementation Order

### Phase 2: Platform Detection (start here — unblocks everything)

```
Priority: HIGH — all subsequent phases depend on knowing the platform.

Tasks:
  2.1  Implement detector.detect() with URL pattern matching          [1 hour]
  2.2  Test against known URLs for each platform                      [30 min]
  2.3  Implement detect_from_dom() for Greenhouse (meta tags, form)   [1 hour]
  2.4  Implement detect_from_dom() for Lever                          [45 min]
  2.5  Implement detect_from_dom() for Workday (data-automation-id)   [45 min]
  2.6  Unit tests for all URL patterns + DOM detection                [1 hour]

Dependency: None — Phase 1 (data model) is complete.
```

### Phase 3A: Fill Engine Core (normalizer + matcher + confidence)

```
Priority: HIGH — core logic, no browser dependency.

Tasks:
  3A.1  Implement normalizer.normalize_question() full pipeline       [2 hours]
  3A.2  Implement matcher.match_answer() with all 4 priorities        [2 hours]
  3A.3  Implement PROFILE_FIELD_MAP + resolve_dotpath()               [1 hour]
  3A.4  Extend confidence.score_confidence() with match_score blend   [30 min]
  3A.5  Extend get_fill_decision() with profile preference overrides  [30 min]
  3A.6  Unit tests for normalizer (known labels → expected intents)   [1.5 hours]
  3A.7  Unit tests for matcher (all 4 match priorities)               [1.5 hours]
  3A.8  Unit tests for confidence (score + decision logic)            [1 hour]

Dependency: Phase 1 (data model).
Can be done in parallel with Phase 2.
```

### Phase 3B: Fill Engine — Playwright Filler

```
Priority: MEDIUM — needs browser, but can be tested with fixtures.

Tasks:
  3B.1  Implement fill_field() for text/textarea                      [30 min]
  3B.2  Implement fill_field() for select (with fuzzy option match)   [1 hour]
  3B.3  Implement fill_field() for radio (with label matching)        [1 hour]
  3B.4  Implement fill_field() for checkbox                           [30 min]
  3B.5  Implement fill_field() for file upload                        [30 min]
  3B.6  Implement fill_field() for date                               [30 min]
  3B.7  Implement clear_field()                                       [30 min]
  3B.8  Implement get_label_for_input() (5 strategies)                [1 hour]
  3B.9  Create test fixtures: generic_form.html                       [1 hour]
  3B.10 Playwright-based tests for fill_field() per type              [2 hours]

Dependency: Phase 3A (normalizer/matcher/confidence).
```

### Phase 3C: Generic Adapter + Generic Field Discovery

```
Priority: MEDIUM — unblocks end-to-end testing on any form.

Tasks:
  3C.1  Implement discover_fields() in detector/platforms/generic.py  [2 hours]
  3C.2  Implement GenericAdapter.detect_fields() wiring               [30 min]
  3C.3  Implement GenericAdapter.fill_form() orchestration            [2 hours]
  3C.4  Implement GenericAdapter.submit() (best-effort)               [30 min]
  3C.5  Create test fixture: generic_form.html (comprehensive)        [1 hour]
  3C.6  Integration test: full pipeline on generic fixture            [2 hours]

Dependency: Phases 3A + 3B.
```

### Phase 4: LLM Integration

```
Priority: MEDIUM — needed for unknown fields and open-ended questions.

Tasks:
  4.1  Implement classifier.classify_field() with Anthropic SDK       [1.5 hours]
  4.2  Wire classifier into normalizer as fallback                    [30 min]
  4.3  Implement drafter.draft_answer() with Anthropic SDK            [1.5 hours]
  4.4  Implement drafter.build_profile_summary()                      [1 hour]
  4.5  Wire drafter into adapter fill_form() for unanswered fields    [30 min]
  4.6  Add in-memory caching for classifier results                   [30 min]
  4.7  Unit tests with mocked Anthropic client                        [1.5 hours]

Dependency: Phase 3A (normalizer needs classifier as fallback).
```

### Phase 5: Review UI

```
Priority: MEDIUM — needed before any real application runs.

Tasks:
  5.1  Implement review_session() full flow                           [2 hours]
  5.2  Implement batch approve logic                                  [1 hour]
  5.3  Implement review_single_field() with accept/reject/edit        [1.5 hours]
  5.4  Implement render_decision_summary()                            [30 min]
  5.5  Manual testing with mock fill_results                          [1 hour]

Dependency: Phase 3A (needs FillResult format defined).
```

### Phase 6: Orchestrator (main.py)

```
Priority: HIGH — ties everything together.

Tasks:
  6.1  Wire detector into main.py                                     [30 min]
  6.2  Wire Playwright browser lifecycle                              [1 hour]
  6.3  Wire adapter selection (get_adapter)                           [30 min]
  6.4  Wire fill pipeline → review UI → submission gate               [2 hours]
  6.5  Wire tracker logging                                           [30 min]
  6.6  Implement apply_edits() (re-fill edited fields)                [1 hour]
  6.7  Implement handle_submission() mode logic                       [1 hour]
  6.8  End-to-end test: full pipeline on local fixture                [2 hours]

Dependency: Phases 2 + 3 + 4 + 5.
```

### Phase 7: Platform-Specific Adapters

```
Priority: LOW (initial) → HIGH (when targeting real applications)

Tasks:
  7.1  GreenhouseAdapter.detect_fields() with CSS selectors           [2 hours]
  7.2  GreenhouseAdapter.fill_form() orchestration                    [2 hours]
  7.3  GreenhouseAdapter.submit()                                     [1 hour]
  7.4  Greenhouse test fixture + integration tests                    [2 hours]
  7.5  LeverAdapter (same pattern as Greenhouse)                      [3 hours]
  7.6  AshbyAdapter (research DOM structure first)                    [4 hours]
  7.7  WorkdayAdapter (multi-step — most complex)                     [8 hours]
  7.8  Integration tests per adapter                                  [4 hours]

Dependency: Phase 6 (main.py orchestrator working).
```

### Phase 8: Tracking & Polish

```
Priority: LOW — non-critical but valuable.

Tasks:
  8.1  Extend get_stats() with GROUP BY query                         [30 min]
  8.2  Add company/role extraction from page metadata                 [1 hour]
  8.3  Time-saved estimation logic                                    [30 min]
  8.4  Pretty-print session summary at end of run                     [1 hour]
  8.5  Error messages and help text polish                            [1 hour]

Dependency: Phase 6.
```

---

## 12. Open Questions

### Q1: Should we add `rapidfuzz` as a dependency?

`difflib.SequenceMatcher` is in the standard library but is slower and less accurate than `rapidfuzz` for fuzzy string matching. `rapidfuzz` is a common, well-maintained library.

**Recommendation:** Add `rapidfuzz` to `requirements.txt`. The accuracy improvement for fuzzy matching justifies the dependency.

**Status:** Not yet added. Current implementation uses `difflib` throughout. Can be swapped in as a drop-in improvement.

### Q2: How to handle ATS login walls?

~~Some Workday and Ashby applications require creating an account or signing in before the application form is shown.~~

**Status: RESOLVED.** Implemented in `src/browser/helpers.py`:
- `detect_login_wall()` checks for password inputs, sign-in/log-in buttons, account creation links (including Workday-specific `data-automation-id` selectors)
- `wait_for_user_to_clear_blocker()` pauses automation, prompts the user to complete login manually, then resumes after the user presses Enter
- `BaseAdapter.fill_form()` calls these automatically before starting the fill loop

### Q3: Should the LLM classifier learn from corrections?

When the user edits a field in the review UI, should we log the correction and improve future matching?

**Recommendation:** Not in v1. Track it as a future feature. For now, if a field is commonly misclassified, add its phrasing to `answers.json.match_phrases` manually.

**Status:** Still deferred. Could be revisited after real-world testing reveals common misclassifications.

### Q4: How to estimate time saved?

**Recommendation:** Option C — per-field estimate. Count the number of fields *actually filled* by the system and multiply by 15 seconds per field.

**Status:** Current implementation uses wall-clock elapsed time. Could be enhanced to per-field counting.

### Q5: Should we support multiple profiles?

**Recommendation:** Not in v1. The `--profile` flag already allows pointing to a different file.

**Status:** Unchanged. The `--profile` CLI flag provides sufficient flexibility.

### Q6: CAPTCHA handling?

~~No current mitigation plan.~~

**Status: RESOLVED.** Implemented in `src/browser/helpers.py`:
- `detect_captcha()` checks for reCAPTCHA, hCaptcha, and Turnstile iframes, plus `.g-recaptcha`, `.h-captcha`, and `[data-sitekey]` markers
- Same `wait_for_user_to_clear_blocker()` mechanism pauses for manual solving
- `BaseAdapter.fill_form()` calls these checks automatically

### Q7: Should `discover_fields()` handle shadow DOM?

~~Some ATS platforms use shadow DOM for custom components.~~

**Status: RESOLVED.** Implemented in two places:
- `src/browser/helpers.py`: `discover_fields_with_shadow_dom()` performs a piercing scan using Playwright's native CSS combinator
- `src/detector/platforms/generic.py`: Calls shadow DOM discovery as fallback if initial scan finds fewer than 2 fields
- `BaseAdapter.fill_form()`: Also triggers shadow DOM fallback when field count is below `MIN_EXPECTED_FIELDS`

### Q8: How to handle iframe-embedded forms?

**Status: RESOLVED.** Implemented in `src/browser/helpers.py`:
- `get_form_frame()` checks for known iframe patterns (Greenhouse embed `#grnhse_iframe`, iCIMS, BambooHR, Jobvite, Workday, Ashby)
- Falls back to heuristic: checks all iframes for one containing a `<form>` element
- Returns the inner Frame if found, or the Page itself
- `BaseAdapter.fill_form()` calls this before any field detection

### Q9: What about multi-page / wizard-style forms beyond Workday?

**Status: RESOLVED for core architecture.** The `BaseAdapter.fill_form()` default implementation:
- Calls `detect_multi_page()` to check for step indicators, progress bars, and next/continue buttons
- Loops up to `MAX_PAGES` (15) iterations: detect → fill → advance
- `try_next_page()` clicks Next/Continue/Save and Continue buttons
- `is_final_step()` detects review/submit/confirm headings
- Workday keeps its own override with Workday-specific step detection

**Open:** Non-browser application types (email, LinkedIn Easy Apply, PDF forms) are not addressed by this architecture. See `docs/PLATFORM_RESEARCH.md` for expansion plans.

---

*This document is the source of truth for the project's architecture. Update it as design decisions evolve during development.*
