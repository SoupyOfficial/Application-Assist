# Application-Assist

A free, local, semi-automatic job application assistant. Application-Assist uses browser automation (Playwright) to detect the ATS platform behind a job posting, intelligently fill application forms using your personal profile and answer bank, and present a terminal-based review UI before anything is submitted.

No third-party services, no subscriptions — just Python, Playwright, SQLite, and the Anthropic API for the fields that need it.

---

## What It Does

1. **Detects the ATS platform** from a job application URL (Greenhouse, Lever, Ashby, Workday, or generic).
2. **Maps form fields** to canonical intents (e.g., "Are you authorized to work in the US?" → `work_authorization_us`).
3. **Fills fields automatically** using `profile.json` and `answers.json`, with confidence scoring on every match.
4. **Handles browser complexity** — iframes, login walls, CAPTCHAs, shadow DOM, multi-page wizards, SPAs.
5. **Presents a review UI** in the terminal so you can accept, reject, or edit each answer before anything is submitted.
6. **Tracks every application** in a local SQLite database with time savings and outcome notes.

---

## Submission Policy Modes

| Mode | Behavior |
|---|---|
| `fill_only` | Fill the form but do not submit. Leaves the browser open for manual review. Safe for exploration. |
| `fill_and_pause` | Fill the form, then pause and prompt you to confirm before submitting. **Default.** |
| `fill_review_submit_if_safe` | Fill the form, show the terminal review UI, and auto-submit only if all fields pass safety thresholds (no `requires_review` fields flagged). |

**Application safety rule:** Fields marked `requires_review: true` in `answers.json` (salary, sponsorship, why-this-company, etc.) are **never auto-submitted**, regardless of mode. You must explicitly approve them.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) |
| LLM integration | [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) |
| Review UI | [Rich](https://rich.readthedocs.io/) |
| Application tracking | SQLite (via Python `sqlite3`) |
| Config / secrets | python-dotenv |

---

## Data Model

### `data/profile.json`
The canonical applicant profile. Contains all identity, location, work history, education, skills, projects, and preferences for Jacob Campbell. Used as the source of truth for form-filling and LLM-assisted drafting.

### `data/answers.json`
A normalized answer bank. Each entry maps a canonical intent (e.g., `work_authorization_us`) to:
- Match phrases for fuzzy/exact lookup
- A short answer and a long-form answer
- Field type hints (`boolean`, `select`, `text`, `number`)
- A confidence level and `requires_review` flag
- Notes on edge cases (inverted phrasing, never auto-submit, etc.)

---

## How to Run

### Prerequisites
```bash
pip install -r requirements.txt
playwright install chromium
```

Set up a `.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```

### Run
```bash
python src/main.py --url "https://boards.greenhouse.io/company/jobs/12345" --mode fill_and_pause
```

### Test without a browser

```bash
python -m src.main --dry-run
```

Runs the full normalize → match → score pipeline against sample form labels using your profile and answer bank. No browser needed.

### Full options

```
--url URL            Job application URL (required unless --dry-run)
--mode MODE          fill_only | fill_and_pause | fill_review_submit_if_safe (default: fill_and_pause)
--profile PATH       Path to profile.json (default: data/profile.json)
--answers PATH       Path to answers.json (default: data/answers.json)
--resume LABEL       Resume variant: backend | fullstack | ai (default: backend)
--cover-letter       Generate a tailored cover letter before filling the form
--company NAME       Company name (auto-detected from page title if omitted)
--role TITLE         Role/job title (auto-detected from page title if omitted)
--dry-run            Test the pipeline against sample labels (no browser)
```

---

## Phases

| Phase | Name | Status |
|---|---|---|
| 1 | **Data Model** — `profile.json` + `answers.json` | Complete |
| 2 | **Platform Detection** — URL + DOM-based ATS identification | Complete |
| 3 | **Fill Engine** — field normalization, matching, confidence scoring, Playwright filling | Complete |
| 3B | **Browser Hardening** — iframe, login wall, CAPTCHA, shadow DOM, multi-page | Complete |
| 4 | **LLM Integration** — Claude classifier + drafter for ambiguous fields | Complete |
| 5 | **Review UI** — terminal-based accept/reject/edit interface | Complete |
| 6 | **Platform Adapters** — per-ATS adapters with shared fill pipeline | Complete |
| 7 | **Metrics & Tracking** — SQLite application log, time-saved stats | Complete |
| 8 | **Testing** — unit tests, integration tests | 190 tests passing |

---

## Project Structure

```
Application-Assist/
├── .env.example              ← template for environment variables
├── data/
│   ├── profile.json          ← canonical applicant profile
│   └── answers.json          ← normalized answer bank
├── docs/
│   ├── ARCHITECTURE.md       ← full architecture & design doc
│   ├── PROJECT_CONTEXT.md    ← condensed project overview
│   └── PLATFORM_RESEARCH.md  ← ATS expansion research & roadmap
├── resumes/                  ← PDF resume variants (not committed)
├── cover_letters/            ← generated cover letters
├── src/
│   ├── main.py               ← CLI entry point + dotenv + Playwright lifecycle
│   ├── browser/              ← iframe, login wall, CAPTCHA, shadow DOM, SPA nav
│   │   └── helpers.py
│   ├── detector/             ← ATS platform detection
│   │   └── platforms/        ← per-ATS detection signatures
│   ├── adapters/             ← per-platform form adapters
│   │   ├── base.py           ← BaseAdapter with default multi-page fill_form()
│   │   ├── pipeline.py       ← shared normalize→match→score→fill loop
│   │   └── (greenhouse, lever, ashby, workday, generic).py
│   ├── engine/               ← field normalization, matching, filling
│   ├── llm/                  ← LLM classifier and drafter
│   ├── review/               ← terminal review UI
│   └── tracker/              ← SQLite application tracker
└── tests/                    ← 169+ pytest tests across 12 files
```

---

## Notes

- Resume PDFs are excluded from git (see `.gitignore`). Place your resume files in `resumes/` before running.
- Application tracking database (`applications.db`) is also excluded from git — it's local only.
- Demographic fields default to "Decline to self-identify" per `answers.json` settings.
