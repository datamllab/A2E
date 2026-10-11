"""Shared error injection middleware for mock services."""

import os
import random
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


EXEMPT_PATHS = {"/audit", "/reset", "/health", "/docs", "/openapi.json"}


class ErrorInjectionMiddleware(BaseHTTPMiddleware):
    """Injects random errors based on ERROR_RATE env var."""

    def __init__(self, app, error_rate: float = 0.0):
        super().__init__(app)
        self.error_rate = error_rate

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip error injection for audit/reset/health/docs
        for exempt in EXEMPT_PATHS:
            if path.endswith(exempt):
                return await call_next(request)

        # Only inject on POST requests
        if request.method != "POST":
            return await call_next(request)

        if random.random() < self.error_rate:
            roll = random.random()
            if roll < 0.35:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded. Please retry later."},
                )
            elif roll < 0.70:
                return JSONResponse(
                    status_code=500,
                    content={"error": "Internal server error. Please retry."},
                )
            else:
                time.sleep(random.uniform(2.0, 4.0))

        return await call_next(request)


def add_error_injection(app):
    """Add error injection middleware to a FastAPI app if ERROR_RATE is set."""
    error_rate = float(os.environ.get("ERROR_RATE", "0"))
    if error_rate > 0:
        app.add_middleware(ErrorInjectionMiddleware, error_rate=error_rate)