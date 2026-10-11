"""Mock Calendar API service for Team Calendar Notify task (FastAPI on port 9101).

Adapted from claw-eval calendar service for ARCA OpenClaw.
Removed _base.py dependency and date-shifting logic (this task uses fixed dates
that must match the prompt).

Environment variables:
  CALENDAR_FIXTURES - Path to events JSON (default: /opt/mock_service/calendar/data/calendar.json)
  PORT - Server port (default: 9101)
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Calendar API")

FIXTURES_PATH = Path(os.environ.get(
    "CALENDAR_FIXTURES",
    "/opt/mock_service/calendar/data/calendar.json",
))

_events: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_deleted: list[dict[str, Any]] = []
_created_events: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load calendar fixtures from JSON file.

    Unlike the generic calendar service, this task uses fixed dates that
    must match the prompt, so no date-shifting is applied.
    """
    global _events

    if not FIXTURES_PATH.exists():
        print(f"[CALENDAR] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _events = []
        return

    with open(FIXTURES_PATH) as f:
        raw = json.load(f)

    if isinstance(raw, dict) and "events" in raw:
        _events = raw["events"]
    elif isinstance(raw, list):
        _events = raw
    else:
        _events = []

    # Filter out non-dict entries
    if _events and not all(isinstance(e, dict) for e in _events):
        _events = [e for e in _events if isinstance(e, dict)]

    # Ensure standard field names
    for e in _events:
        if not isinstance(e, dict):
            continue
        if "event_id" not in e and "id_" in e:
            e["event_id"] = str(e["id_"])
        if "attendees" not in e and "participants" in e:
            e["attendees"] = e["participants"]


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class ListEventsRequest(BaseModel):
    date: str
    days: int = 1


class GetEventRequest(BaseModel):
    event_id: str


class CreateEventRequest(BaseModel):
    title: str
    start_time: str
    end_time: str
    attendees: list[str] = Field(default_factory=list)
    location: str = ""


class DeleteEventRequest(BaseModel):
    event_id: str


@app.post("/calendar/events")
def list_events(req: ListEventsRequest | None = None) -> dict[str, Any]:
    """Search events by date range."""
    if req is None:
        req = ListEventsRequest(date="2026-05-01")
    try:
        query_date = datetime.strptime(req.date, "%Y-%m-%d")
    except ValueError:
        resp = {"error": f"Invalid date format: {req.date}"}
        _log_call("/calendar/events", req.model_dump(), resp)
        return resp

    from datetime import timedelta
    end_date = query_date + timedelta(days=req.days)
    results = []
    for evt in _events:
        start_time = evt.get("start_time", "")
        if not start_time:
            continue
        # Parse event start time (handle both with and without timezone)
        dt_str = start_time.replace("Z", "")
        try:
            evt_start = datetime.fromisoformat(dt_str)
            if evt_start.tzinfo is not None:
                evt_start = evt_start.replace(tzinfo=None)
        except ValueError:
            continue
        if query_date <= evt_start < end_date:
            results.append(copy.deepcopy(evt))
    results.sort(key=lambda e: e["start_time"])
    resp = {"events": results, "total": len(results)}
    _log_call("/calendar/events", req.model_dump(), resp)
    return resp


@app.post("/calendar/events/get")
def get_event(req: GetEventRequest) -> dict[str, Any]:
    """Get a single event by event_id."""
    for evt in _events:
        if evt["event_id"] == req.event_id:
            resp = copy.deepcopy(evt)
            _log_call("/calendar/events/get", req.model_dump(), resp)
            return resp
    resp = {"error": f"Event {req.event_id} not found"}
    _log_call("/calendar/events/get", req.model_dump(), resp)
    return resp


@app.post("/calendar/events/create")
def create_event(req: CreateEventRequest) -> dict[str, Any]:
    """Create a new calendar event."""
    new_id = f"evt_{len(_events) + 1:03d}"
    event = {
        "event_id": new_id,
        "title": req.title,
        "start_time": req.start_time,
        "end_time": req.end_time,
        "attendees": req.attendees,
        "location": req.location,
        "recurring": False,
    }
    _events.append(event)
    _created_events.append(copy.deepcopy(event))
    resp = {"status": "created", "event": event}
    _log_call("/calendar/events/create", req.model_dump(), resp)
    return resp


@app.post("/calendar/events/delete")
def delete_event(req: DeleteEventRequest) -> dict[str, Any]:
    """Delete an event by event_id."""
    for i, evt in enumerate(_events):
        if evt["event_id"] == req.event_id:
            removed = _events.pop(i)
            _deleted.append(removed)
            resp = {"status": "deleted", "event": removed}
            _log_call("/calendar/events/delete", req.model_dump(), resp)
            return resp
    resp = {"error": f"Event {req.event_id} not found"}
    _log_call("/calendar/events/delete", req.model_dump(), resp)
    return resp


@app.get("/calendar/health")
async def calendar_health():
    return {"status": "ok"}


@app.get("/calendar/audit")
def get_audit() -> dict[str, Any]:
    """Return audit log for grader evaluation."""
    return {"calls": _audit_log, "deleted": _deleted, "created_events": _created_events}


@app.post("/calendar/reset")
def reset_state() -> dict[str, str]:
    """Reset service state and reload fixtures."""
    global _audit_log, _deleted, _created_events
    _audit_log = []
    _deleted = []
    _created_events = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9101")))