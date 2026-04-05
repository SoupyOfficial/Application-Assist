"""
main.py — CLI entry point for Application-Assist.

Usage:
    python src/main.py --url <job_url> [--mode <mode>] [--profile <path>] [--answers <path>] [--resume <label>]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.detector.detector import detect
from src.adapters.generic import GenericAdapter
from src.adapters.greenhouse import GreenhouseAdapter
from src.adapters.lever import LeverAdapter
from src.adapters.ashby import AshbyAdapter
from src.adapters.workday import WorkdayAdapter
from src.review.terminal import review_session
from src.engine.filler import fill_field, clear_field
from src.tracker.db import init_db, log_application


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="application-assist",
        description="Semi-automatic job application engine.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Job application URL to fill.",
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
        print(f"[warn] No resume found for variant '{args.resume}'")

    # Fill the form
    fill_results = adapter.fill_form(page, profile, answers, args.mode)
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
            submitted = adapter.submit(page)
        except KeyboardInterrupt:
            print("\n[info] Submission cancelled by user.")
    elif args.mode == "fill_review_submit_if_safe":
        has_review_flags = any(r.get("requires_review") for r in approved)
        has_rejections = any(r.get("action") == "reject" for r in approved)
        if not has_review_flags and not has_rejections:
            submitted = adapter.submit(page)
            print("[info] Auto-submitted (no review flags).")
        else:
            print("[warn] Review-flagged or rejected fields present — not submitting automatically.")
            try:
                input("[prompt] Press Enter to submit anyway, or Ctrl+C to cancel... ")
                submitted = adapter.submit(page)
            except KeyboardInterrupt:
                print("\n[info] Submission cancelled by user.")

    # Track the application
    elapsed = int(time.time() - start_time)
    init_db()
    log_application(
        url=args.url,
        company=_extract_company(page),
        role=_extract_role(page),
        ats_platform=platform,
        mode=args.mode,
        status="submitted" if submitted else "filled",
        time_saved_seconds=elapsed,
    )
    print(f"[info] Application logged. Time: {elapsed}s")


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


def main():
    args = parse_args()

    # Load data files
    profile = load_json(args.profile, "profile.json")
    answers = load_json(args.answers, "answers.json")

    print(f"[info] Loaded profile for: {profile['identity']['full_name']}")
    print(f"[info] Answer bank: {len(answers['answers'])} entries")
    print(f"[info] Mode: {args.mode}")
    print(f"[info] Resume variant: {args.resume}")
    print(f"[info] Target URL: {args.url}")

    # Detect ATS platform from URL
    platform = detect(args.url)
    print(f"[info] Detected platform: {platform}")

    # Launch Playwright browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(args.url, wait_until="networkidle")

        # Run DOM detection if URL detection returned generic
        if platform == "generic":
            platform = detect(args.url, page=page)
            if platform != "generic":
                print(f"[info] DOM detection refined platform to: {platform}")

        run_application(page, platform, profile, answers, args)

        # Keep browser open for user inspection in fill_only mode
        if args.mode == "fill_only":
            input("[prompt] Press Enter to close browser... ")

        browser.close()


if __name__ == "__main__":
    main()
