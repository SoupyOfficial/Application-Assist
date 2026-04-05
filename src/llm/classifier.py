"""
classifier.py — LLM-based field intent classification.

Used when fuzzy matching in the normalizer fails to identify a field's
canonical intent with sufficient confidence. Calls Claude via the
Anthropic Python SDK to classify the field intent.

Only called as a fallback — the majority of fields should be resolved
through the faster fuzzy matching path in normalizer.py.
"""

import os
import json


def classify_field(label: str, context: str, profile: dict) -> dict:
    """
    Use Claude to classify a form field's canonical intent.

    Args:
        label:   The raw form field label text.
        context: Surrounding page context (e.g., section heading, nearby text).
                 Used to disambiguate fields with generic labels like "Name".
        profile: Parsed profile.json dict. Used only to check which intents
                 are relevant — PII is not sent to the API.

    Returns:
        Classification result dict:
          {
            "intent":     <str — canonical intent string>,
            "confidence": <float 0.0–1.0>,
            "reasoning":  <str — brief explanation from the model>,
          }

    TODO: Implement LLM classification using Anthropic SDK:

      import anthropic

      client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

      system_prompt = (
          "You are a job application form classifier. Given a form field label "
          "and optional context, return the canonical intent as a JSON object. "
          "Use snake_case intent names. Common intents: work_authorization_us, "
          "requires_sponsorship, salary_expectations, years_experience_total, "
          "first_name, last_name, email, phone, linkedin_url, github_url, "
          "willing_to_relocate, work_arrangement, citizenship_status, etc."
      )

      user_message = f"Field label: {label}\\nContext: {context}"

      response = client.messages.create(
          model="claude-haiku-4-5-20251001",  # Use fast/cheap model for classification
          max_tokens=256,
          system=system_prompt,
          messages=[{"role": "user", "content": user_message}],
      )

      # Parse the JSON response
      result = json.loads(response.content[0].text)
      return result

    Error handling:
      - If the API call fails, return {"intent": "unknown", "confidence": 0.0, "reasoning": "API error"}
      - If JSON parsing fails, return the same fallback
      - Log errors for debugging but do not raise — this is a non-critical fallback
    """
    # TODO: Implement LLM classification
    return {
        "intent": "unknown",
        "confidence": 0.0,
        "reasoning": "LLM classifier not yet implemented",
    }
