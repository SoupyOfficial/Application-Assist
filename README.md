# Application-Assist

A free, local, semi-automatic job application assistant. Application-Assist uses browser automation (Playwright) to detect the ATS platform behind a job posting, intelligently fill application forms using your personal profile and answer bank, and present a terminal-based review UI before anything is submitted.

No third-party services, no subscriptions — just Python, Playwright, SQLite, and the Anthropic API for the fields that need it.

---

## What It Does

1. **Detects the ATS platform** from a job application URL (Greenhouse, Lever, Ashby, Workday, or generic).
2. **Maps form fields** to canonical intents (e.g., "Are you authorized to work in the US?" → `work_authorization_us`).
3. **Fills fields automatically** using `profile.json` and `answers.json`, with confidence scoring on every match.
4. **Presents a review UI** in the terminal so you can accept, reject, or edit each answer before anything is submitted.
5. **Tracks every application** in a local SQLite database with time savings and outcome notes.

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

### Full options
```
--url URL         Job application URL (required)
--mode MODE       fill_only | fill_and_pause | fill_review_submit_if_safe (default: fill_and_pause)
--profile PATH    Path to profile.json (default: data/profile.json)
--answers PATH    Path to answers.json (default: data/answers.json)
--resume LABEL    Resume variant: backend | fullstack | ai (default: backend)
```

---

## Phases

| Phase | Name | Status |
|---|---|---|
| 1 | **Data Model** — `profile.json` + `answers.json` | Complete |
| 2 | **Platform Detection** — URL + DOM-based ATS identification | Next |
| 3 | **Fill Engine** — field normalization, matching, confidence scoring, Playwright filling | Scaffolded |
| 4 | **Review UI** — terminal-based accept/reject/edit interface | Scaffolded |
| 5 | **Metrics & Tracking** — SQLite application log, time-saved stats | Scaffolded |

---

## Project Structure

```
Application-Assist/
├── data/
│   ├── profile.json          ← canonical applicant profile
│   └── answers.json          ← normalized answer bank
├── resumes/                  ← PDF resume variants (not committed)
├── cover_letters/            ← generated cover letters
├── src/
│   ├── detector/             ← ATS platform detection
│   ├── adapters/             ← per-platform form adapters
│   ├── engine/               ← field normalization, matching, filling
│   ├── llm/                  ← LLM classifier and drafter
│   ├── review/               ← terminal review UI
│   ├── tracker/              ← SQLite application tracker
│   └── main.py               ← CLI entry point
└── tests/
```

---

## Notes

- Resume PDFs are excluded from git (see `.gitignore`). Place your resume files in `resumes/` before running.
- Application tracking database (`applications.db`) is also excluded from git — it's local only.
- Demographic fields default to "Decline to self-identify" per `answers.json` settings.
