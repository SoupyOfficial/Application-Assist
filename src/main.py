"""
main.py — CLI entry point for Application-Assist.

Usage:
    python -m src.main --url <job_url> [--mode <mode>] [--profile <path>] [--answers <path>] [--resume <label>]

Run from the project root directory.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so `from src.xxx` imports work
# regardless of how the script is invoked (python src/main.py, python -m src.main, etc.)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from src.detector.detector import detect
from src.adapters.generic import GenericAdapter
from src.adapters.greenhouse import GreenhouseAdapter
from src.adapters.lever import LeverAdapter
from src.adapters.ashby import AshbyAdapter
from src.adapters.workday import WorkdayAdapter
from src.review.terminal import review_session
from src.engine.filler import fill_field, clear_field
from src.tracker.db import init_db, log_application, get_today_count
from src.llm.cover_letter import generate_cover_letter, save_cover_letter
from src.browser.helpers import (
    wait_for_page_ready,
    detect_login_wall,
    detect_captcha,
    wait_for_user_to_clear_blocker,
    get_form_frame,
)

# Load environment variables (.env file at project root)
load_dotenv()


VALID_MODES = ["fill_only", "fill_and_pause", "fill_review_submit_if_safe"]
VALID_RESUME_LABELS = ["backend", "fullstack", "ai"]

ADAPTER_MAP = {
    "greenhouse": GreenhouseAdapter,
    "lever":      LeverAdapter,
    "ashby":      AshbyAdapter,
    "workday":    WorkdayAdapter,
    "generic":    GenericAdapter,
}


def load_json(path: str, label: str) -> dict:
    """Load and parse a JSON file, exiting cleanly on error."""
    p = Path(path)
    if not p.exists():
        print(f"[error] {label} not found at: {path}", file=sys.stderr)
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


_REQUIRED_PROFILE_KEYS = ["identity", "location", "links", "work_authorization", "skills"]
_REQUIRED_IDENTITY_KEYS = ["legal_first_name", "legal_last_name", "email_primary"]


def validate_profile(profile: dict):
    """Validate required top-level profile keys. Exits on missing keys."""
    missing = [k for k in _REQUIRED_PROFILE_KEYS if k not in profile]
    if missing:
        print(f"[error] profile.json missing required keys: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    identity = profile.get("identity", {})
    missing_id = [k for k in _REQUIRED_IDENTITY_KEYS if k not in identity]
    if missing_id:
        print(f"[error] profile.json 'identity' missing keys: {', '.join(missing_id)}", file=sys.stderr)
        sys.exit(1)


def validate_answers(answers: dict):
    """Validate answers.json has the expected shape."""
    if "answers" not in answers or not isinstance(answers["answers"], list):
        print("[error] answers.json must contain an 'answers' key with a list of entries.", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="application-assist",
        description="Semi-automatic job application engine.",
    )
    parser.add_argument(
        "--url",
        required=False,
        default=None,
        help="Job application URL to fill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Test normalize→match→score pipeline against sample labels (no browser).",
    )
    parser.add_argument(
        "--mode",
        default="fill_and_pause",
        choices=VALID_MODES,
        help=(
            "Submission mode: fill_only (no submit), fill_and_pause (confirm before submit), "
            "fill_review_submit_if_safe (auto-submit if no review flags). Default: fill_and_pause"
        ),
    )
    parser.add_argument(
        "--profile",
        default="data/profile.json",
        help="Path to profile.json (default: data/profile.json)",
    )
    parser.add_argument(
        "--answers",
        default="data/answers.json",
        help="Path to answers.json (default: data/answers.json)",
    )
    parser.add_argument(
        "--resume",
        default="backend",
        choices=VALID_RESUME_LABELS,
        help="Resume variant label: backend, fullstack, ai (default: backend)",
    )
    parser.add_argument(
        "--cover-letter",
        action="store_true",
        default=False,
        help="Generate a tailored cover letter before filling the form.",
    )
    parser.add_argument(
        "--company",
        default=None,
        help="Company name (auto-detected from page title if omitted).",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Role/job title (auto-detected from page title if omitted).",
    )
    return parser.parse_args()


def resolve_resume_path(label: str) -> str | None:
    """Resolve the resume file path from a variant label."""
    resumes_dir = Path("resumes")
    for ext in (".pdf", ".PDF"):
        path = resumes_dir / f"{label}{ext}"
        if path.exists():
            return str(path.resolve())
    # Fallback: any file in resumes/ matching the label
    for f in resumes_dir.glob(f"*{label}*"):
        if f.is_file():
            return str(f.resolve())
    return None


def run_application(page, platform: str, profile: dict, answers: dict, args):
    """Core orchestration: detect fields, fill, review, submit."""
    start_time = time.time()

    # Instantiate the adapter
    adapter_cls = ADAPTER_MAP.get(platform, GenericAdapter)
    adapter = adapter_cls()
    print(f"[info] Using adapter: {adapter_cls.__name__}")

    # Inject resume path into profile for file-upload fields
    resume_path = resolve_resume_path(args.resume)
    if resume_path:
        profile["_resume_path"] = resume_path
        print(f"[info] Resume: {resume_path}")
    else:
        print(
            f"[warn] No resume found for variant '{args.resume}'. "
            f"Place a PDF in resumes/ named '{args.resume}.pdf' or matching '*{args.resume}*'.",
            file=sys.stderr,
        )

    # Generate cover letter if requested
    if getattr(args, "cover_letter", False):
        company = args.company or _extract_company(page) or "the company"
        role = args.role or _extract_role(page) or "the role"
        print(f"[info] Generating cover letter for {company} / {role}...")
        cl_text = generate_cover_letter(profile, company, role)
        if cl_text:
            cl_path = save_cover_letter(cl_text, company, role)
            profile["_cover_letter_text"] = cl_text
            print(f"[info] Cover letter saved: {cl_path}")
        else:
            print("[warn] Cover letter generation failed — continuing without it.")

    # Fill the form
    fill_results = []
    fill_error = False
    try:
        fill_results = adapter.fill_form(page, profile, answers, args.mode)
    except Exception as e:
        fill_error = True
        print(f"[error] fill_form crashed: {e}", file=sys.stderr)
        print("[info] Logging attempt as 'error' and showing any partial results.", file=sys.stderr)

    print(f"[info] Processed {len(fill_results)} field(s)")

    # Review UI
    approved = review_session(fill_results)

    # Apply review decisions back to the page
    for result in approved:
        action = result.get("action")
        field = result.get("field", {})
        if action == "reject" and result.get("filled"):
            clear_field(page, field, field.get("field_type", "text"))
        elif action == "edit" and result.get("final_answer"):
            fill_field(page, field, result["final_answer"], field.get("field_type", "text"))

    # Submit or pause based on mode
    submitted = False
    if args.mode == "fill_only":
        print("[info] fill_only mode — browser left open. Submit manually.")
    elif args.mode == "fill_and_pause":
        try:
            input("[prompt] Press Enter to submit, or Ctrl+C to cancel... ")
            try:
                submitted = adapter.submit(page)
            except Exception as e:
                print(f"[error] Submission failed: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print("\n[info] Submission cancelled by user.")
    elif args.mode == "fill_review_submit_if_safe":
        has_review_flags = any(r.get("requires_review") for r in approved)
        has_rejections = any(r.get("action") == "reject" for r in approved)
        if not has_review_flags and not has_rejections:
            try:
                submitted = adapter.submit(page)
                print("[info] Auto-submitted (no review flags).")
            except Exception as e:
                print(f"[error] Auto-submit failed: {e}", file=sys.stderr)
        else:
            print("[warn] Review-flagged or rejected fields present — not submitting automatically.")
            try:
                input("[prompt] Press Enter to submit anyway, or Ctrl+C to cancel... ")
                try:
                    submitted = adapter.submit(page)
                except Exception as e:
                    print(f"[error] Submission failed: {e}", file=sys.stderr)
            except KeyboardInterrupt:
                print("\n[info] Submission cancelled by user.")

    # Track the application
    elapsed = int(time.time() - start_time)
    status = "submitted" if submitted else "filled"
    if fill_error:
        status = "error"
    init_db()
    log_application(
        url=args.url,
        company=_extract_company(page),
        role=_extract_role(page),
        ats_platform=platform,
        mode=args.mode,
        status=status,
        time_saved_seconds=elapsed,
    )
    print(f"[info] Application logged ({status}). Time: {elapsed}s")


def _extract_company(page) -> str | None:
    """Try to extract company name from page title."""
    title = page.title() or ""
    parts = title.split(" - ")
    if len(parts) >= 2:
        return parts[-1].strip()
    return None


def _extract_role(page) -> str | None:
    """Try to extract role/title from page title."""
    title = page.title() or ""
    parts = title.split(" - ")
    if parts:
        return parts[0].strip()
    return None


# Sample labels for --dry-run mode
_DRY_RUN_LABELS = [
    "First Name",
    "Last Name",
    "Email Address",
    "Phone Number",
    "LinkedIn Profile URL",
    "City",
    "State",
    "Are you legally authorized to work in the United States?",
    "Will you now or in the future require sponsorship?",
    "What are your salary expectations?",
    "When can you start?",
    "Are you willing to relocate?",
    "Do you have experience with Python?",
    "Years of Java experience",
    "What is your highest level of education?",
    "Upload Resume",
    "Tell us why you're interested in this role.",
]


def run_dry_run(profile: dict, answers: dict):
    """Exercise the normalize→match→score pipeline against sample labels."""
    from src.engine.normalizer import normalize_question
    from src.engine.matcher import match_answer
    from src.engine.confidence import score_confidence

    print(f"\n{'Label':<55} {'Intent':<30} {'Answer':<25} {'Conf':>5}  Source")
    print("─" * 145)

    for label in _DRY_RUN_LABELS:
        intent = normalize_question(label, answers=answers)
        result = match_answer(intent, profile, answers, raw_label=label)
        answer = result.get("answer") or ""
        if len(answer) > 22:
            answer = answer[:19] + "..."
        conf = score_confidence(result)
        source = result.get("source", "")
        print(f"{label:<55} {intent:<30} {answer:<25} {conf:>5.2f}  {source}")

    print(f"\n[info] Dry run complete — {len(_DRY_RUN_LABELS)} labels tested.")


def main():
    args = parse_args()

    # Load data files
    profile = load_json(args.profile, "profile.json")
    answers = load_json(args.answers, "answers.json")
    validate_profile(profile)
    validate_answers(answers)

    # Dry-run mode: test pipeline without browser
    if args.dry_run:
        print(f"[info] Loaded profile for: {profile['identity']['full_name']}")
        print(f"[info] Answer bank: {len(answers['answers'])} entries")
        run_dry_run(profile, answers)
        return

    # --url is required for normal operation
    if not args.url:
        print("[error] --url is required (or use --dry-run).", file=sys.stderr)
        sys.exit(1)

    print(f"[info] Loaded profile for: {profile['identity']['full_name']}")
    print(f"[info] Answer bank: {len(answers['answers'])} entries")
    print(f"[info] Mode: {args.mode}")
    print(f"[info] Resume variant: {args.resume}")
    print(f"[info] Target URL: {args.url}")

    # Rate limiting — enforce max_applications_per_day from profile
    init_db()
    max_per_day = profile.get("application_preferences", {}).get("max_applications_per_day")
    if max_per_day is not None:
        today_count = get_today_count()
        if today_count >= max_per_day:
            print(
                f"[warn] Daily application limit reached ({today_count}/{max_per_day}). "
                "Increase max_applications_per_day in profile.json or try again tomorrow.",
                file=sys.stderr,
            )
            sys.exit(0)
        print(f"[info] Daily applications: {today_count}/{max_per_day}")

    # Detect ATS platform from URL
    platform = detect(args.url)
    print(f"[info] Detected platform: {platform}")

    # Validate API key early if LLM features are needed
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_api_key:
        print(
            "[warn] ANTHROPIC_API_KEY not set — LLM classification and drafting will be disabled.\n"
            "       Create a .env file in the project root with: ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
    if getattr(args, "cover_letter", False) and not has_api_key:
        print("[error] --cover-letter requires ANTHROPIC_API_KEY to be set.", file=sys.stderr)
        sys.exit(1)

    # Launch Playwright browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
            wait_for_page_ready(page)
        except Exception as e:
            print(f"[error] Failed to navigate to {args.url}: {e}", file=sys.stderr)
            context.close()
            browser.close()
            sys.exit(1)

        # Check for login wall / CAPTCHA before detection
        if detect_login_wall(page):
            wait_for_user_to_clear_blocker(page, "login wall")
        if detect_captcha(page):
            wait_for_user_to_clear_blocker(page, "CAPTCHA")

        # Run DOM detection if URL detection returned generic
        if platform == "generic":
            platform = detect(args.url, page=page)
            if platform != "generic":
                print(f"[info] DOM detection refined platform to: {platform}")

        try:
            run_application(page, platform, profile, answers, args)
        except KeyboardInterrupt:
            print("\n[info] Interrupted by user.")
        except Exception as e:
            print(f"[error] Application failed: {e}", file=sys.stderr)

        # Keep browser open for user inspection in fill_only mode
        if args.mode == "fill_only":
            try:
                input("[prompt] Press Enter to close browser... ")
            except (KeyboardInterrupt, EOFError):
                pass

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
