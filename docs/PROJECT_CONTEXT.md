# Application-Assist: Project Context

**Last updated:** 2026-04-05
**Status:** Fully implemented — all modules coded, syntax-verified, ready for integration testing

---

## Project Goal

Build a free, local, semi-automatic job application engine that:
- Detects the ATS (Applicant Tracking System) behind any job application URL
- Fills forms intelligently using a structured personal profile and normalized answer bank
- Presents a terminal-based review UI before anything is submitted
- Tracks every application locally in SQLite
- Uses the Anthropic API only for fields that need drafting or classification

The system is **semi-automatic by design** — it handles the tedious mechanical parts (field detection, data lookup, form filling) while keeping the human in the loop for anything that requires judgment (compensation, company-specific answers, legal acknowledgments).

---

## Core Architecture

### Components

| Component | Location | Responsibility |
|---|---|---|
| CLI entry point | `src/main.py` | Argument parsing, dotenv loading, orchestration |
| ATS Detector | `src/detector/` | Identify platform from URL + DOM |
| Browser Layer | `src/browser/` | Iframe, login wall, CAPTCHA, shadow DOM, SPA nav |
| Platform Adapters | `src/adapters/` | Per-ATS field detection + submit; shared fill pipeline |
| Fill Engine | `src/engine/` | Field normalization, matching, confidence, filling |
| LLM Layer | `src/llm/` | Classify ambiguous fields, draft open-ended answers |
| Review UI | `src/review/` | Terminal-based accept/reject/edit interface |
| Tracker | `src/tracker/` | SQLite application log |

### Data Files

| File | Purpose |
|---|---|
| `data/profile.json` | Canonical applicant profile — identity, work history, education, skills, projects, preferences |
| `data/answers.json` | Normalized answer bank — intent → match phrases → answer + metadata |
| `resumes/*.pdf` | Resume variants (excluded from git) |
| `applications.db` | SQLite tracking database (excluded from git, local only) |

### Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Browser automation | Playwright (Python) | Handles dynamic SPAs, multi-step forms, shadow DOM |
| LLM | Anthropic SDK (Claude) | Best-in-class for structured reasoning and instruction-following |
| Terminal UI | Rich | High-quality terminal rendering without a web UI |
| Tracking | SQLite | Zero-dependency, local, durable |
| Config | python-dotenv | Standard `.env` management |

### Submission Policy Modes

| Mode | Behavior |
|---|---|
| `fill_only` | Fill form, do not submit. Browser stays open for manual review. |
| `fill_and_pause` | Fill form, pause, prompt for confirmation before submitting. **Default.** |
| `fill_review_submit_if_safe` | Fill, show review UI, auto-submit if no `requires_review` fields flagged. |

---

## Build Phases

### Phase 1 — Data Model
**Status: Complete**

- `profile.json`: Full canonical applicant profile for Jacob Campbell
- `answers.json`: Normalized answer bank with 25+ entries covering work auth, compensation, demographics, behavioral questions, and skill-specific questions
- Schema designed for extensibility: intents, match phrases, field types, confidence, auto_submit flags, behavioral stories

### Phase 2 — Platform Detection
**Status: Complete**

- URL pattern matching for Greenhouse, Lever, Ashby, Workday
- DOM marker detection fallback (meta tags, data attributes, form actions, JavaScript globals)
- Generic fallback for unknown platforms
- Files: `src/detector/detector.py`, `src/detector/platforms/*.py`

### Phase 3 — Fill Engine
**Status: Complete**

- `normalizer.py`: Raw label → canonical intent via profile map, exact match, fuzzy match (0.80 threshold), LLM fallback
- `matcher.py`: Intent → best answer via 4-priority chain (exact intent, profile lookup, fuzzy cross-match, no match). Includes inverted phrasing detection with `answer_inverted` swap
- `confidence.py`: Match score blending (70%/30%), inverted phrasing penalty, profile preference overrides
- `filler.py`: Playwright filling for text, textarea, select (fuzzy option), radio (label matching), checkbox, date, file

### Phase 3B — Browser Hardening
**Status: Complete**

- `browser/helpers.py`: Page readiness (SPA-aware), iframe detection, login wall/CAPTCHA detection with user pause, shadow DOM piercing, multi-page navigation, loader/spinner detection
- Integrated into `BaseAdapter.fill_form()` default implementation

### Phase 4 — LLM Integration
**Status: Complete**

- `classifier.py`: Claude Haiku for field intent classification (JSON structured output)
- `drafter.py`: Claude Sonnet for answer drafting with full profile summary builder
- Both are fallback paths — majority of fields resolved without LLM

### Phase 5 — Review UI
**Status: Complete**

- Rich terminal display: summary table, batch approve, individual accept/reject/edit, decision summary
- Color-coded confidence indicators
- File: `src/review/terminal.py`

### Phase 6 — Platform Adapters
**Status: Complete**

- `BaseAdapter` provides default multi-page `fill_form()` with shared pipeline
- `pipeline.py`: Shared normalize→match→score→fill loop with demographic defaults and inverted phrasing
- Greenhouse, Lever, Ashby: Custom `detect_fields()` + `submit()`; fill inherited
- Workday: Custom multi-step `fill_form()` override with step navigation
- Generic: Fallback using DOM scanning

### Phase 7 — Metrics & Tracking
**Status: Complete**

- SQLite schema with applications table
- Log each application: date, company, role, URL, ATS, mode, status, time_saved_seconds
- `get_stats()` with GROUP BY platform breakdown
- File: `src/tracker/db.py`

### Phase 8 — Testing & Integration
**Status: Not started**

- Unit tests: not yet written (tests/ directory empty)
- HTML test fixtures: not yet created
- Integration tests: not yet written
- See `ARCHITECTURE.md` Section 9 for test strategy

---

## Research Needed

### ATS API Research
| ATS | API Available | Notes |
|---|---|---|
| Greenhouse | Yes | [Job Board API](https://developers.greenhouse.io/job-board.html) — can fetch job details, may reduce DOM scraping |
| Lever | Yes | Lever API available — TBD on scope for applications |
| Ashby | TBD | API availability unclear — needs investigation |
| Workday | No public API | Must use browser automation; most complex target |

### Existing Tool Evaluation
- **EasyApplyBot**: LinkedIn-specific, not generalizable
- **JobSpy**: Job scraping, not form filling
- **ResumeWorded / Teal**: SaaS tools, not local or automatable
- Conclusion: No existing OSS tool handles multi-ATS form filling with a structured profile. Building from scratch is warranted.

### LLM Integration Design
- Claude is used for two tasks: (1) classify ambiguous field intent when fuzzy matching fails, (2) draft answers to open-ended questions using profile context
- Both should be cached / memoized where possible to reduce API calls
- Structured output (JSON mode) preferred for classifier
- Draft answers should be presented in review UI, not auto-submitted

---

## Known Blockers and Limitations

1. **Workday**: Multi-step, heavily JavaScript-driven forms. ✅ Handled — custom adapter with step navigation.
2. **Resume parsing side effects**: Some ATS platforms auto-populate fields after parsing a PDF resume. ✅ Handled — pipeline supports `redetect_after_upload` callback.
3. **Shadow DOM**: Some ATS widgets use shadow DOM. ✅ Handled — `discover_fields_with_shadow_dom()` as fallback.
4. **CAPTCHAs**: ✅ Handled — detection + user pause via `detect_captcha()` and `wait_for_user_to_clear_blocker()`.
5. **Login walls**: ✅ Handled — detection + user pause via `detect_login_wall()`.
6. **Iframes**: ✅ Handled — `get_form_frame()` auto-detects and switches context.
7. **Answer freshness**: Salary expectations, start date, and company-specific answers must be reviewed per application. ✅ Enforced via `always_review` and `never_auto_submit` in profile preferences.
8. **Inverted boolean questions**: ✅ Handled — `matcher.py` detects inverted phrasing and swaps to `answer_inverted`.
9. **No tests yet**: Unit and integration tests have not been written. HTML test fixtures do not exist.
10. **Platform coverage**: Only 4 named ATS platforms + generic fallback. Major platforms not yet supported: Taleo, iCIMS, SuccessFactors, SmartRecruiters, plus non-browser types (LinkedIn Easy Apply, Indeed, email, PDF).
11. **No dotenv in LLM modules directly**: LLM modules use `os.getenv()` and depend on `main.py` having called `load_dotenv()` first. If modules are used standalone (e.g., in tests), dotenv must be loaded separately.
12. **No LLM response caching**: Classifier and drafter make fresh API calls every time. In-memory caching for the classifier was planned but not implemented.

---

## Application Safety Rules

These rules are enforced regardless of submission mode:

1. **Fields marked `requires_review: true`** in `answers.json` are never auto-submitted.
2. **`never_auto_submit` fields** in `profile.json` `application_preferences` (salary, custom written responses, legal acknowledgments) are always flagged.
3. **`always_review` fields** (why_this_company, why_this_role, free_response, work_authorization) always require explicit approval.
4. **`fill_only` mode** never submits, regardless of field confidence.
5. **No silent failures**: If a field cannot be matched with confidence ≥ 0.5, it is flagged for manual input rather than left blank or guessed.

---

## Design Principles

1. **Local-first**: No data leaves the machine except for the Anthropic API call (which only receives question text and anonymized profile context, never PII unless necessary).
2. **Human in the loop**: The system assists, not replaces. The goal is to handle the mechanical parts and present clean decisions to the user.
3. **Transparency**: Every filled field shows its source (profile field path or answer bank ID), confidence score, and match method.
4. **Fail safe**: When in doubt, flag for review. Never silently fill sensitive fields.
5. **Extensible**: New ATS platforms should be addable by creating a new detector module and adapter — no changes to core engine.

---

## Repo Structure

```
Application-Assist/
├── README.md
├── requirements.txt
├── .env.example              ← template for environment variables
├── .gitignore
├── docs/
│   ├── PROJECT_CONTEXT.md        ← this file
│   ├── ARCHITECTURE.md           ← full architecture & design doc
│   └── PLATFORM_RESEARCH.md      ← ATS expansion research & roadmap
├── data/
│   ├── profile.json              ← canonical applicant profile
│   └── answers.json              ← normalized answer bank
├── resumes/                      ← PDF resume variants (not committed)
├── cover_letters/                ← generated cover letters
├── src/
│   ├── main.py                   ← CLI entry point + dotenv + Playwright lifecycle
│   ├── browser/                  ← iframe, login wall, CAPTCHA, shadow DOM, SPA nav
│   │   ├── __init__.py
│   │   └── helpers.py
│   ├── detector/                 ← ATS platform detection
│   │   ├── detector.py
│   │   └── platforms/
│   ├── adapters/                 ← per-platform form adapters + shared pipeline
│   │   ├── base.py               ← BaseAdapter with default multi-page fill_form()
│   │   ├── pipeline.py           ← shared normalize→match→score→fill loop
│   │   ├── generic.py
│   │   ├── greenhouse.py
│   │   ├── lever.py
│   │   ├── ashby.py
│   │   └── workday.py
│   ├── engine/                   ← field normalization, matching, filling
│   ├── llm/                      ← LLM classifier and drafter
│   ├── review/                   ← terminal review UI
│   └── tracker/                  ← SQLite application tracker
└── tests/                        ← (empty — not yet written)
```

---

## Immediate Next Steps

1. **Implement `src/detector/detector.py`** with URL pattern matching for the four major platforms
2. **Stub Playwright browser launch** in `src/main.py` and wire in the detector
3. **Research Greenhouse DOM markers** — inspect a live Greenhouse form to identify reliable selectors
4. **Implement `src/engine/matcher.py`** — exact + fuzzy match against answer bank `match_phrases`
5. **Write first integration test** — load a known Greenhouse URL, assert detection returns `greenhouse`

---

## Open Questions

- Should resume upload trigger a re-scan of all fields, or only fields after the upload section?
- Should LLM-drafted answers be saved back to `answers.json` for reuse, or treated as ephemeral?
- Is there a clean way to handle multi-page / multi-step ATS forms without a full state machine?
- Should the tracker expose a simple web UI (via `rich` live display or a minimal FastAPI route) or stay terminal-only?
- How should the system handle forms that require an account/login before reaching the application?

---

## Strategy Ranking (ATS Priority Order)

| Rank | Platform | Reason |
|---|---|---|
| 1 | Greenhouse | Largest market share among tech startups, public API, clean DOM |
| 2 | Lever | Common at mid-size tech companies, relatively clean forms |
| 3 | Ashby | Growing adoption among modern startups |
| 4 | Workday | Enterprise / large company standard — complex but high volume |
| 5 | Generic | Catch-all for custom or niche ATS platforms |
