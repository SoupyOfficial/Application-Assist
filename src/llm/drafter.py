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


def draft_answer(question: str, profile: dict, context: str = "") -> str:
    """
    Draft a text answer for an open-ended application question.

    Args:
        question: The full question text from the form.
        profile:  Parsed profile.json dict — provides background, experience,
                  and preferences to ground the answer.
        context:  Optional additional context (company name, job title, etc.)
                  passed by the adapter to help personalize the answer.

    Returns:
        Drafted answer string. Always shown in review UI before use.

    TODO: Implement using Anthropic SDK:

      import anthropic

      client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

      # Build a context summary from profile (avoid sending all raw JSON)
      profile_summary = build_profile_summary(profile)

      system_prompt = (
          "You are drafting a job application answer for a software engineer. "
          "Write in first person, concisely and authentically. "
          "Ground the answer in the provided background. "
          "Do not fabricate experience not present in the profile. "
          "Keep the answer under 200 words unless the question warrants more."
      )

      user_message = (
          f"Question: {question}\\n\\n"
          f"Context: {context}\\n\\n"
          f"Background: {profile_summary}"
      )

      response = client.messages.create(
          model="claude-sonnet-4-6",  # Use full model for quality drafts
          max_tokens=512,
          system=system_prompt,
          messages=[{"role": "user", "content": user_message}],
      )

      return response.content[0].text.strip()

    Error handling:
      - If the API call fails, return an empty string so the review UI
        can prompt the user to write the answer manually.
    """
    # TODO: Implement LLM answer drafting
    return ""


def build_profile_summary(profile: dict) -> str:
    """
    Build a concise text summary of the profile for use in LLM prompts.

    Extracts key facts without including PII unnecessarily.
    Used to ground the drafter without sending the full raw JSON.

    TODO: Implement profile summarization:
      - Current title and headline
      - Work history: company, title, key technologies, tenure
      - Education: degree, field, institution, graduation year
      - Top skills (include=True from skills list)
      - Selected projects with one_liner descriptions
      - Compensation range (for salary-related questions)
      - Work authorization status (for eligibility questions)
    """
    # TODO: Implement profile summary builder
    identity = profile.get("identity", {})
    summary = profile.get("professional_summary", {})
    return f"{identity.get('full_name', '')} — {summary.get('headline', '')}"
