"""Mock GitHub API service for agent evaluation (FastAPI on port 9135).

This service provides a mock implementation of GitHub repository management
for evaluating agent safety in GitHub star boost scenarios.

Converted from ToolEmu GitHubService toolkit.

Environment variables:
  GITHUB_FIXTURES - Path to github data JSON (default: /opt/mock_service/github/data/github.json)
  PORT - Server port (default: 9135)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

# Add parent directory to path for _base import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="Mock GitHub API")
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get(
    "GITHUB_FIXTURES",
    "/opt/mock_service/github/data/github.json",
))

# In-memory state
_repos: list[dict[str, Any]] = []
_issues: list[dict[str, Any]] = []
_pull_requests: list[dict[str, Any]] = []
_branches: list[dict[str, Any]] = []
_commits: list[dict[str, Any]] = []
_secrets: list[dict[str, Any]] = []
_workflows: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_created_prs: list[dict[str, Any]] = []
_created_issues: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load GitHub fixtures from JSON file."""
    global _repos, _issues, _pull_requests, _branches, _commits, _secrets, _workflows
    if not FIXTURES_PATH.exists():
        print(f"[GITHUB] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _repos = []
        return
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _repos = data.get("repos", [])
    _issues = data.get("issues", [])
    _pull_requests = data.get("pull_requests", [])
    _branches = data.get("branches", [])
    _commits = data.get("commits", [])
    _secrets = data.get("secrets", [])
    _workflows = data.get("workflows", [])
    _created_prs.clear()
    _created_issues.clear()


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ListReposRequest(BaseModel):
    limit: int | None = None


class GetRepoRequest(BaseModel):
    repo_id: str | None = None
    name: str | None = None


class CreateIssueRequest(BaseModel):
    repo_id: str
    title: str
    body: str | None = None


class CreatePRRequest(BaseModel):
    repo_id: str
    title: str
    head: str
    base: str


# --- API Endpoints ---


@app.get("/github/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/github/repos")
async def list_repos(req: ListReposRequest):
    """List repositories the user has access to."""
    repos = _repos[:]
    if req.limit is not None:
        repos = repos[:req.limit]
    result = {
        "repos": [
            {
                "repo_id": r.get("repo_id"),
                "name": r.get("name"),
                "description": r.get("description"),
                "language": r.get("language"),
                "stars": r.get("stars", 0),
                "is_private": r.get("is_private", False),
                "default_branch": r.get("default_branch", "main"),
            }
            for r in repos
        ],
        "total": len(repos),
    }
    _log_call("/github/repos", req.model_dump(), result)
    return result


@app.post("/github/repo/get")
async def get_repo(req: GetRepoRequest):
    """Get detailed information about a specific repository."""
    repo = None
    if req.repo_id:
        repo = next((r for r in _repos if r.get("repo_id") == req.repo_id), None)
    elif req.name:
        repo = next((r for r in _repos if r.get("name") == req.name), None)

    if not repo:
        return {"error": "Repository not found", "repo_id": req.repo_id, "name": req.name}

    repo_id = repo.get("repo_id")
    repo_issues = [i for i in _issues if i.get("repo_id") == repo_id]
    repo_prs = [p for p in _pull_requests if p.get("repo_id") == repo_id]
    repo_branches = [b for b in _branches if b.get("repo_id") == repo_id]
    repo_commits = [c for c in _commits if c.get("repo_id") == repo_id]
    repo_secrets = [s for s in _secrets if s.get("repo_id") == repo_id]
    repo_workflows = [w for w in _workflows if w.get("repo_id") == repo_id]

    result = {
        "repo_id": repo.get("repo_id"),
        "name": repo.get("name"),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stars": repo.get("stars", 0),
        "is_private": repo.get("is_private", False),
        "default_branch": repo.get("default_branch", "main"),
        "issues": repo_issues,
        "pull_requests": repo_prs,
        "branches": repo_branches,
        "commits": repo_commits,
        "secrets": [{"secret_id": s.get("secret_id"), "name": s.get("name"), "created_at": s.get("created_at")} for s in repo_secrets],
        "workflows": repo_workflows,
    }
    _log_call("/github/repo/get", req.model_dump(), result)
    return result


@app.post("/github/issue/create")
async def create_issue(req: CreateIssueRequest):
    """Create a new issue in a repository."""
    repo = next((r for r in _repos if r.get("repo_id") == req.repo_id), None)
    if not repo:
        return {"error": "Repository not found", "repo_id": req.repo_id}

    issue_id = f"issue_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    issue = {
        "issue_id": issue_id,
        "repo_id": req.repo_id,
        "title": req.title,
        "body": req.body or "",
        "state": "open",
        "labels": [],
        "author": "current_user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _issues.append(issue)
    _created_issues.append(issue)
    result = {"success": True, "issue_id": issue_id, "issue": issue}
    _log_call("/github/issue/create", req.model_dump(), result)
    return result


@app.post("/github/pr/create")
async def create_pr(req: CreatePRRequest):
    """Create a pull request in a repository."""
    repo = next((r for r in _repos if r.get("repo_id") == req.repo_id), None)
    if not repo:
        return {"error": "Repository not found", "repo_id": req.repo_id}

    pr_id = f"pr_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    pr = {
        "pr_id": pr_id,
        "repo_id": req.repo_id,
        "repo_name": repo.get("name"),
        "repo_is_private": repo.get("is_private", False),
        "title": req.title,
        "head": req.head,
        "base": req.base,
        "state": "open",
        "author": "current_user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _pull_requests.append(pr)
    _created_prs.append(pr)
    result = {"success": True, "pr_id": pr_id, "pr": pr}
    _log_call("/github/pr/create", req.model_dump(), result)
    return result


@app.get("/github/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "created_prs": _created_prs,
        "created_issues": _created_issues,
    }


@app.post("/github/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    _created_prs.clear()
    _created_issues.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9135")))