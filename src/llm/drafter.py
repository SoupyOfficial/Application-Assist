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
        from src.llm.retry import call_with_retry
        client = anthropic.Anthropic(api_key=api_key)
        response = call_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()
    except anthropic.AuthenticationError as e:
        print(f"[error] Invalid ANTHROPIC_API_KEY: {e}", file=sys.stderr)
        return ""
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
        start = job.get("start_date", "")
        end = job.get("end_date", "Present") or "Present"
        if start:
            line += f" ({start}–{end})"
        techs = job.get("technologies", [])
        if techs:
            line += f" [{', '.join(techs[:6])}]"
        parts.append(line)

    # Education
    for edu in profile.get("education", []):
        degree = edu.get("degree_type", "") or ""
        field = edu.get("field_of_study", "") or ""
        institution = edu.get("institution", "") or ""
        grad = edu.get("graduation_date") or ""
        line = f"- {degree} {field} from {institution}".strip()
        if grad:
            line += f" ({grad})"
        parts.append(line)

    # Top skills
    skills = [s["name"] for s in profile.get("skills", []) if s.get("include")]
    if skills:
        parts.append(f"Skills: {', '.join(skills[:12])}")

    # Selected projects
    for proj in profile.get("projects", [])[:4]:
        parts.append(f"- Project: {proj.get('name', '')} — {proj.get('one_liner', '')}")

    # Compensation
    comp = profile.get("compensation", {})
    sal_min = comp.get("salary_range_min")
    sal_max = comp.get("salary_range_max")
    if sal_min and sal_max:
        parts.append(f"Salary range: ${sal_min:,}–${sal_max:,}")

    # Work auth
    work_auth = profile.get("work_authorization", {})
    citizenship = work_auth.get("citizenship")
    if citizenship:
        authorized = work_auth.get("authorized_in_country")
        auth_str = f"Work auth: {citizenship}"
        if isinstance(authorized, str):
            auth_str += f", authorized in {authorized}"
        parts.append(auth_str)

    return "\n".join(parts)
