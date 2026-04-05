"""
main.py — CLI entry point for Application-Assist.

Usage:
    python src/main.py --url <job_url> [--mode <mode>] [--profile <path>] [--answers <path>] [--resume <label>]
"""

import argparse
import json
import sys
from pathlib import Path


VALID_MODES = ["fill_only", "fill_and_pause", "fill_review_submit_if_safe"]
VALID_RESUME_LABELS = ["backend", "fullstack", "ai"]


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


def main():
    args = parse_args()

    # --- Step 1: Load data files ---
    profile = load_json(args.profile, "profile.json")
    answers = load_json(args.answers, "answers.json")

    print(f"[info] Loaded profile for: {profile['identity']['full_name']}")
    print(f"[info] Answer bank: {len(answers['answers'])} entries")
    print(f"[info] Mode: {args.mode}")
    print(f"[info] Resume variant: {args.resume}")
    print(f"[info] Target URL: {args.url}")

    # --- Step 2: Detect ATS platform ---
    # TODO: Import and call detector.detect(args.url) -> platform_name
    # from src.detector.detector import detect
    # platform = detect(args.url)
    # print(f"[info] Detected platform: {platform}")
    platform = "generic"  # placeholder until detector is implemented
    print(f"[info] Platform (stub): {platform}")

    # --- Step 3: Launch Playwright browser ---
    # TODO: from playwright.sync_api import sync_playwright
    # with sync_playwright() as p:
    #     browser = p.chromium.launch(headless=False)
    #     page = browser.new_page()
    #     page.goto(args.url)
    #     run_application(page, platform, profile, answers, args)
    #     browser.close()
    print("[info] Browser launch not yet implemented — Playwright stub only")

    # --- Step 4: Route to the appropriate platform adapter ---
    # TODO: Import adapter by platform name and instantiate it
    # adapter = get_adapter(platform)
    # fields = adapter.detect_fields(page)

    # --- Step 5: Run fill engine ---
    # TODO: For each field, call engine to normalize, match, score confidence
    # from src.engine.normalizer import normalize_question
    # from src.engine.matcher import match_answer
    # from src.engine.confidence import score_confidence
    # from src.engine.filler import fill_field

    # --- Step 6: Show review UI ---
    # TODO: from src.review.terminal import review_session
    # approved_fields = review_session(filled_fields)

    # --- Step 7: Submit or pause based on mode ---
    # TODO:
    # if args.mode == "fill_only":
    #     print("[info] fill_only mode — browser left open. Submit manually.")
    # elif args.mode == "fill_and_pause":
    #     input("[prompt] Press Enter to submit, or Ctrl+C to cancel...")
    #     adapter.submit(page)
    # elif args.mode == "fill_review_submit_if_safe":
    #     if all(not f.get("requires_review") for f in approved_fields):
    #         adapter.submit(page)
    #     else:
    #         print("[warn] Review-flagged fields present — not submitting automatically.")

    # --- Step 8: Track the application ---
    # TODO: from src.tracker.db import init_db, log_application
    # init_db()
    # log_application(company=..., role=..., url=args.url, ats_platform=platform, mode=args.mode, status="filled")

    print("[info] Application-Assist scaffold complete. Implement TODOs to activate each phase.")


if __name__ == "__main__":
    main()
