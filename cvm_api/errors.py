"""
Custom exceptions and retry logic for CVM scrapers.
"""

import asyncio
import functools
import httpx


# ── Exceptions ────────────────────────────────────────────────────────────────

class CVMError(Exception):
    """Base exception for CVM API errors."""
    pass


class CVMConnectionError(CVMError):
    """Network or timeout error communicating with CVM."""
    pass


class CVMParsingError(CVMError):
    """CVM returned an unexpected or unparseable response."""
    pass


class CompanyNotFoundError(CVMError):
    """Ticker, CVM code, or company name not found."""
    pass


class CategoryNotFoundError(CVMError):
    """Unknown document category name."""
    pass


# ── Retry decorator ──────────────────────────────────────────────────────────

def retry_on_transient(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for async functions that retries on transient CVM errors.
    Retries on: ConnectError, TimeoutException, HTTP 5xx.
    Backoff: base_delay * 2^attempt (1s, 2s, 4s).
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                    last_exc = e
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500:
                        last_exc = e
                    else:
                        raise
                except CVMConnectionError as e:
                    last_exc = e

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

            raise CVMConnectionError(f"Failed after {max_retries} retries: {last_exc}") from last_exc
        return wrapper
    return decorator
