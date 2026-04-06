"""
retry.py — Shared retry logic for Anthropic API calls.
"""

import time
import sys

import anthropic

# Default timeout for all API calls (seconds)
API_TIMEOUT = 30.0

# Retry config for rate limits
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


def call_with_retry(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    """
    Call client.messages.create() with timeout and retry-on-rate-limit.

    Raises the last exception if all retries are exhausted.
    """
    kwargs.setdefault("timeout", API_TIMEOUT)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            last_error = e
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"[warn] Rate limited (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
        except anthropic.AuthenticationError:
            raise  # Don't retry auth errors
    raise last_error
