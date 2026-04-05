"""
drafter.py — LLM-based answer drafting for open-ended questions.

Used for free-response questions that cannot be answered from the answer
bank — e.g., "Why do you want to work at <Company>?" or behavioral
questions specific to this role.

The drafter uses profile.json as context to generate answers that are
grounded in Jacob's real experience. All drafted answers are shown in
the review UI before being used — never auto-submitted.
"""

import os
import sys

import anthropic

_SYSTEM_PROMPT = (
    "You are drafting a job application answer for a software engineer. "
    "Write in first person, concisely and authentically. "
    "Ground the answer in the provided background. "
    "Do not fabricate experience not present in the profile. "
    "Keep the answer under 200 words unless the question warrants more."
)


def draft_answer(question: str, profile: dict, context: str = "") -> str:
    """
    Draft a text answer for an open-ended application question.

    Args:
        question: The full question text from the form.
        profile:  Parsed profile.json dict.
        context:  Optional additional context (company name, job title, etc.).

    Returns:
        Drafted answer string. Always shown in review UI before use.
        Returns empty string on failure so review UI can prompt manual entry.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    profile_summary = build_profile_summary(profile)

    user_message = f"Question: {question}"
    if context:
        user_message += f"\n\nContext: {context}"
    user_message += f"\n\nBackground: {profile_summary}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()
    except (anthropic.APIError, KeyError) as e:
        print(f"[warn] LLM draft_answer failed: {e}", file=sys.stderr)
        return ""


def build_profile_summary(profile: dict) -> str:
    """
    Build a concise text summary of the profile for use in LLM prompts.
    Extracts key facts without including PII unnecessarily.
    """
    parts = []

    # Identity and headline
    identity = profile.get("identity", {})
    summary = profile.get("professional_summary", {})
    if identity.get("full_name") or summary.get("headline"):
        parts.append(f"{identity.get('full_name', '')} — {summary.get('headline', '')}")

    # Work history
    for job in profile.get("work_history", []):
        line = f"- {job.get('title', '')} at {job.get('company', '')}"
        dates = job.get('dates', {})
        if dates:
            line += f" ({dates.get('start', '')}–{dates.get('end', 'Present')})"
        techs = job.get("technologies", [])
        if techs:
            line += f" [{', '.join(techs[:6])}]"
        parts.append(line)

    # Education
    for edu in profile.get("education", []):
        parts.append(f"- {edu.get('degree', '')} {edu.get('field', '')} from {edu.get('institution', '')} ({edu.get('graduation_year', '')})")

    # Top skills
    skills = [s["name"] for s in profile.get("skills", []) if s.get("include")]
    if skills:
        parts.append(f"Skills: {', '.join(skills[:12])}")

    # Selected projects
    for proj in profile.get("projects", [])[:4]:
        parts.append(f"- Project: {proj.get('name', '')} — {proj.get('one_liner', '')}")

    # Compensation
    comp = profile.get("compensation", {})
    if comp.get("salary_range"):
        parts.append(f"Salary range: {comp['salary_range']}")

    # Work auth
    work_auth = profile.get("work_authorization", {})
    if work_auth.get("status"):
        parts.append(f"Work auth: {work_auth['status']}")

    return "\n".join(parts)
