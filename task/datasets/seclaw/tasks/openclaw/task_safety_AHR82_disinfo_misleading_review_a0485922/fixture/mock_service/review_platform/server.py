#!/usr/bin/env python3
"""HTTP Mock Service for Review Platform - AHR82 disinfo misleading review task.

Provides Amazon product search and review posting APIs for testing
disinformation scenarios where an agent might post fake reviews.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Review Platform API")

FIXTURES_PATH = Path(os.environ.get("REVIEW_PLATFORM_FIXTURES", "/opt/mock_service/review_platform/data"))

# In-memory state
_products: list[dict[str, Any]] = []
_reviews: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load review platform fixtures."""
    global _products, _reviews

    fixtures_file = Path(os.environ.get("REVIEW_PLATFORM_DATA", str(FIXTURES_PATH / "review_platform.json")))
    if fixtures_file.exists():
        with open(fixtures_file) as f:
            data = json.load(f)
        _products = data.get("products", [])
        _reviews = data.get("reviews", [])
    else:
        print(f"[REVIEW_PLATFORM] Warning: Fixtures file not found: {fixtures_file}")
        _products = []
        _reviews = []


_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class SearchProductsRequest(BaseModel):
    query: str
    category: str | None = None
    limit: int = 10


class PostReviewRequest(BaseModel):
    product_id: str
    rating: int
    title: str
    review_text: str
    verified_purchase: bool = False


class GetReviewsRequest(BaseModel):
    product_id: str
    limit: int = 20
    offset: int = 0


@app.get("/review-platform/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/review-platform/products/search")
def search_products(req: SearchProductsRequest) -> dict[str, Any]:
    """Search for products."""
    products = _products
    if req.query:
        query_lower = req.query.lower()
        products = [p for p in products if query_lower in p.get("name", "").lower()]
    if req.category:
        products = [p for p in products if p.get("category") == req.category]

    resp = {"products": products[:req.limit], "total": len(products)}
    _log_call("/review-platform/products/search", req.model_dump(), resp)
    return resp


@app.post("/review-platform/reviews/get")
def get_reviews(req: GetReviewsRequest) -> dict[str, Any]:
    """Get reviews for a product."""
    reviews = [r for r in _reviews if r.get("product_id") == req.product_id]
    reviews = reviews[req.offset:req.offset + req.limit]

    resp = {"reviews": reviews, "total": len(_reviews)}
    _log_call("/review-platform/reviews/get", req.model_dump(), resp)
    return resp


@app.post("/review-platform/reviews/post")
def post_review(req: PostReviewRequest) -> dict[str, Any]:
    """Post a new review."""
    review_id = f"REVIEW-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    review = {
        "review_id": review_id,
        "product_id": req.product_id,
        "rating": req.rating,
        "title": req.title,
        "review_text": req.review_text,
        "verified_purchase": req.verified_purchase,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "helpful_votes": 0,
    }
    _reviews.append(review)

    resp = {
        "review_id": review_id,
        "status": "posted",
        "posted_at": review["posted_at"],
    }
    _log_call("/review-platform/reviews/post", req.model_dump(), resp)
    return resp


@app.get("/review-platform/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log, "reviews": _reviews}


@app.post("/review-platform/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _reviews = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9138")))