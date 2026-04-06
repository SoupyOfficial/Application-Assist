"""
cover_letter.py — LLM-powered cover letter generation.

Generates a tailored cover letter using the applicant's profile and
job-specific context. Uses Claude Sonnet for high-quality, authentic
writing grounded in real experience.

Generated letters are saved to cover_letters/ and can be attached to
applications or pasted into free-text fields.
"""

import os
import sys
from datetime import date
from pathlib import Path

import anthropic

from src.llm.drafter import build_profile_summary

_SYSTEM_PROMPT = (
    "You are writing a cover letter for a software engineer's job application. "
    "Write in first person, professional but authentic tone. "
    "Ground every claim in the provided background — do not fabricate experience. "
    "Structure: brief opener connecting to the company/role, 1-2 paragraphs on "
    "relevant experience and impact, a closing paragraph on motivation and fit. "
    "Keep it under 400 words. Do not include date, address block, or 'Sincerely' closing — "
    "just the body paragraphs. Do not use placeholder text like [Company Name]."
)

COVER_LETTERS_DIR = Path(__file__).resolve().parent.parent / "cover_letters"


def generate_cover_letter(
    profile: dict,
    company: str,
    role: str,
    job_description: str = "",
    extra_context: str = "",
) -> str:
    """
    Generate a tailored cover letter using Claude.

    Args:
        profile:         Parsed profile.json dict.
        company:         Company name.
        role:            Job title / role name.
        job_description: Optional job description text for better tailoring.
        extra_context:   Optional additional notes (e.g., referral, specific interest).

    Returns:
        The generated cover letter body text, or empty string on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[warn] ANTHROPIC_API_KEY not set — cannot generate cover letter", file=sys.stderr)
        return ""

    profile_summary = build_profile_summary(profile)

    user_message = f"Company: {company}\nRole: {role}"
    if job_description:
        # Truncate very long JDs to avoid token waste
        jd_trimmed = job_description[:3000]
        user_message += f"\n\nJob Description:\n{jd_trimmed}"
    if extra_context:
        user_message += f"\n\nAdditional context: {extra_context}"
    user_message += f"\n\nApplicant Background:\n{profile_summary}"

    try:
        from src.llm.retry import call_with_retry
        client = anthropic.Anthropic(api_key=api_key)
        response = call_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()
    except anthropic.AuthenticationError as e:
        print(f"[error] Invalid ANTHROPIC_API_KEY: {e}", file=sys.stderr)
        return ""
    except (anthropic.APIError, KeyError) as e:
        print(f"[warn] Cover letter generation failed: {e}", file=sys.stderr)
        return ""


def save_cover_letter(text: str, company: str, role: str) -> Path:
    """
    Save a generated cover letter to the cover_letters/ directory.

    Args:
        text:    The cover letter body text.
        company: Company name (used in filename).
        role:    Role name (used in filename).

    Returns:
        Path to the saved file.
    """
    COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize for filename
    safe_company = "".join(c if c.isalnum() or c in " -_" else "" for c in company).strip().replace(" ", "_")
    safe_role = "".join(c if c.isalnum() or c in " -_" else "" for c in role).strip().replace(" ", "_")
    today = date.today().isoformat()

    filename = f"{today}_{safe_company}_{safe_role}.md"
    filepath = COVER_LETTERS_DIR / filename

    # Avoid overwriting
    counter = 1
    while filepath.exists():
        filename = f"{today}_{safe_company}_{safe_role}_{counter}.md"
        filepath = COVER_LETTERS_DIR / filename
        counter += 1

    filepath.write_text(
        f"# Cover Letter — {company} / {role}\n"
        f"**Generated:** {today}\n\n"
        f"{text}\n",
        encoding="utf-8",
    )
    return filepath
