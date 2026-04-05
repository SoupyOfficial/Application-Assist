# Application-Assist: Project Context

**Last updated:** 2026-04-05
**Status:** Phase 1 complete — scaffolding in progress

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
| CLI entry point | `src/main.py` | Argument parsing, orchestration |
| ATS Detector | `src/detector/` | Identify platform from URL + DOM |
| Platform Adapters | `src/adapters/` | Per-ATS form interaction logic |
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
**Status: Next**

Goals:
- URL pattern matching (Greenhouse, Lever, Ashby, Workday, generic)
- DOM marker detection fallback
- Form structure signature detection
- Meta tag inspection

Files: `src/detector/detector.py`, `src/detector/platforms/*.py`

### Phase 3 — Fill Engine
**Status: Scaffolded**

Goals:
- `normalizer.py`: Raw label → canonical intent (fuzzy match or LLM)
- `matcher.py`: Intent → best answer from answer bank
- `confidence.py`: Score confidence, flag fields for review
- `filler.py`: Playwright filling for all field types (text, select, radio, checkbox, file upload)

Key challenge: Re-scanning fields after resume upload (some ATS platforms auto-populate fields after parsing a resume PDF).

### Phase 4 — Review UI
**Status: Scaffolded**

Goals:
- Rich terminal display of each extracted field
- Show: question, proposed answer, confidence, source
- Accept / reject / edit options
- Batch approve high-confidence fields

File: `src/review/terminal.py`

### Phase 5 — Metrics & Tracking
**Status: Scaffolded**

Goals:
- SQLite schema: applications table
- Log each application: date, company, role, URL, ATS, mode, status, time_saved_seconds, notes
- `get_history()` for stats display

File: `src/tracker/db.py`

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

1. **Workday**: Multi-step, heavily JavaScript-driven forms. Playwright required. High development complexity.
2. **Resume parsing side effects**: Some ATS platforms auto-populate fields after parsing a PDF resume. Must re-scan fields after upload.
3. **Shadow DOM**: Some ATS widgets use shadow DOM. Playwright handles this but requires careful locator strategy.
4. **CAPTCHAs**: Automated browser behavior may trigger CAPTCHAs on some platforms. No current mitigation plan.
5. **Answer freshness**: Salary expectations, start date, and company-specific answers must be reviewed per application — cannot be static.
6. **Inverted boolean questions**: Some forms ask "Can you work WITHOUT sponsorship?" (answer: Yes) rather than "Do you REQUIRE sponsorship?" (answer: No). Matcher must handle both phrasings.

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
├── docs/
│   └── PROJECT_CONTEXT.md        ← this file
├── data/
│   ├── profile.json              ← canonical applicant profile
│   └── answers.json              ← normalized answer bank
├── resumes/
│   └── .gitkeep                  ← PDFs excluded from git
├── cover_letters/
│   └── .gitkeep
├── src/
│   ├── detector/
│   │   ├── detector.py           ← main detection orchestrator
│   │   └── platforms/            ← per-ATS detection logic
│   ├── adapters/                 ← per-ATS form interaction
│   ├── engine/                   ← normalization, matching, filling
│   ├── llm/                      ← LLM classifier + drafter
│   ├── review/                   ← terminal review UI
│   ├── tracker/                  ← SQLite tracking
│   └── main.py                   ← CLI entry point
└── tests/
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
