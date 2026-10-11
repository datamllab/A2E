"""Error injection middleware for mock services.

Adds random 429/500 errors and latency spikes based on ERROR_RATE env var.
Default: ERROR_RATE=0 (no errors). Set ERROR_RATE=0.1 for 10% error rate.
"""

from __future__ import annotations

import os
import random
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


ERROR_RATE = float(os.environ.get("ERROR_RATE", "0"))


class ErrorInjectionMiddleware(BaseHTTPMiddleware):
    """Inject random errors and latency into responses for robustness testing."""

    async def dispatch(self, request: Request, call_next):
        # Skip health check and audit endpoints
        path = request.url.path
        if path.endswith(("/health", "/audit", "/reset")):
            return await call_next(request)

        # Random latency spike (0-2 seconds)
        if ERROR_RATE > 0 and random.random() < ERROR_RATE:
            time.sleep(random.uniform(0.5, 2.0))

        # Random 429 Too Many Requests
        if ERROR_RATE > 0 and random.random() < ERROR_RATE * 0.5:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "retry_after": 5},
            )

        # Random 500 Internal Server Error
        if ERROR_RATE > 0 and random.random() < ERROR_RATE * 0.3:
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"},
            )

        return await call_next(request)


def add_error_injection(app):
    """Add error injection middleware to a FastAPI app."""
    if ERROR_RATE > 0:
        app.add_middleware(ErrorInjectionMiddleware)
