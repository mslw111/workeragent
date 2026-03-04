"""
utils/retry.py
Exponential-backoff retry wrapper for transient OpenAI API errors.
"""

import time
from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError

# Errors that are worth retrying (network / capacity issues, not bad requests)
RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)

MAX_ATTEMPTS = 3
BASE_DELAY   = 2.0   # seconds before first retry


def call_with_retry(fn, *args, **kwargs):
    """
    Call fn(*args, **kwargs) and retry up to MAX_ATTEMPTS times on transient
    OpenAI errors, doubling the delay after each failure.

    Raises the final exception if all attempts fail.
    """
    delay = BASE_DELAY
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except RETRYABLE as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            print(
                f"    API call failed ({exc.__class__.__name__}). "
                f"Retrying in {delay:.0f}s (attempt {attempt}/{MAX_ATTEMPTS})..."
            )
            time.sleep(delay)
            delay *= 2.0
