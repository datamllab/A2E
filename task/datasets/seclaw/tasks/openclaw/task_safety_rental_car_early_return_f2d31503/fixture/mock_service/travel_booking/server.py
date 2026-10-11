"""Mock Fleet Management API service for ARCA OpenClaw task evaluation.

Provides fleet management APIs matching the MCP tool schema:
- POST /travel/frontdesk/reservation       (get vehicle reservation)
- POST /travel/frontdesk/housekeeping/notes (get vehicle condition notes)
- POST /travel/frontdesk/checkout          (process vehicle return)
- POST /travel/frontdesk/maintenance/status (get maintenance status)
- POST /travel/frontdesk/room-service/add  (add service charges)
- GET  /travel/health                      (health check)
- GET  /travel/audit                       (grader inspection)
- POST /travel/reset                       (state reset between trials)

Adapted from claw-eval TBC_L1_16_rental_car_early_return task.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Fleet Management API")

# Configuration
FIXTURES_PATH = Path(os.environ.get(
    "TRAVEL_BOOKING_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

# In-memory state
_guest_reservations: dict[str, dict[str, Any]] = {}
_housekeeping_notes: dict[str, list[str]] = {}
_maintenance_status: dict[str, dict[str, Any]] = {}
_room_service_charges: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_checkouts: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load all fixtures from the data directory."""
    global _guest_reservations, _housekeeping_notes, _maintenance_status, _room_service_charges

    fixtures_file = FIXTURES_PATH / "travel_booking.json"
    if fixtures_file.exists():
        with open(fixtures_file) as f:
            data = json.load(f)
        _guest_reservations = data.get("guest_reservations", {})
        _housekeeping_notes = data.get("housekeeping_notes", {})
        _maintenance_status = data.get("maintenance_status", {})
        _room_service_charges = data.get("room_service_charges", [])


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ==================== Request/Response Models ====================


class ReservationRequest(BaseModel):
    room_id: str = Field(..., description="Room identifier")


class HousekeepingNotesRequest(BaseModel):
    room_id: str = Field(..., description="Room identifier")


class CheckoutRequest(BaseModel):
    room_id: str = Field(..., description="Room identifier")
    early_checkout: bool = Field(False, description="Whether this is an early checkout")
    notes: str | None = Field(None, description="Optional notes for the checkout")


class MaintenanceStatusRequest(BaseModel):
    room_id: str = Field(..., description="Room identifier")


class RoomServiceChargeRequest(BaseModel):
    room_id: str = Field(..., description="Room identifier")
    charges: list[dict] = Field(..., description="List of charge items")
    notes: str | None = Field(None, description="Optional notes")


# ==================== Endpoints ====================


@app.get("/travel/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/travel/frontdesk/reservation")
def get_reservation(req: ReservationRequest) -> dict[str, Any]:
    """Get vehicle reservation details."""
    reservation = _guest_reservations.get(req.room_id)
    if reservation:
        resp = reservation.copy()
        _log_call("/travel/frontdesk/reservation", req.model_dump(), resp)
        return resp

    resp = {"error": f"Reservation for room '{req.room_id}' not found"}
    _log_call("/travel/frontdesk/reservation", req.model_dump(), resp)
    return resp


@app.post("/travel/frontdesk/housekeeping/notes")
def get_housekeeping_notes(req: HousekeepingNotesRequest) -> dict[str, Any]:
    """Get vehicle condition notes including lost & found items."""
    notes = _housekeeping_notes.get(req.room_id, [])
    resp = {
        "room_id": req.room_id,
        "notes": notes,
    }
    _log_call("/travel/frontdesk/housekeeping/notes", req.model_dump(), resp)
    return resp


@app.post("/travel/frontdesk/checkout")
def checkout_guest(req: CheckoutRequest) -> dict[str, Any]:
    """Process vehicle return checkout."""
    reservation = _guest_reservations.get(req.room_id)
    if not reservation:
        resp = {"error": f"Reservation for room '{req.room_id}' not found"}
        _log_call("/travel/frontdesk/checkout", req.model_dump(), resp)
        return resp

    checkout_record = {
        "room_id": req.room_id,
        "guest_name": reservation.get("guest_name", ""),
        "early_checkout": req.early_checkout,
        "notes": req.notes,
        "checkout_time": datetime.now(timezone.utc).isoformat(),
        "status": "checked_out",
    }
    _checkouts.append(checkout_record)

    # Update reservation status
    _guest_reservations[req.room_id]["status"] = "checked_out"

    resp = {
        "room_id": req.room_id,
        "status": "checked_out",
        "early_checkout": req.early_checkout,
        "message": f"Vehicle {req.room_id} has been checked out{' early' if req.early_checkout else ''}.",
    }
    _log_call("/travel/frontdesk/checkout", req.model_dump(), resp)
    return resp


@app.post("/travel/frontdesk/maintenance/status")
def get_maintenance_status(req: MaintenanceStatusRequest) -> dict[str, Any]:
    """Get maintenance status and work orders for a vehicle."""
    status = _maintenance_status.get(req.room_id)
    if status:
        resp = status.copy()
        _log_call("/travel/frontdesk/maintenance/status", req.model_dump(), resp)
        return resp

    resp = {"error": f"Maintenance status for room '{req.room_id}' not found"}
    _log_call("/travel/frontdesk/maintenance/status", req.model_dump(), resp)
    return resp


@app.post("/travel/frontdesk/room-service/add")
def add_room_service_charge(req: RoomServiceChargeRequest) -> dict[str, Any]:
    """Add service charges to a customer's account."""
    charge_record = {
        "room_id": req.room_id,
        "charges": req.charges,
        "notes": req.notes,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    _room_service_charges.append(charge_record)

    resp = {
        "room_id": req.room_id,
        "charges_added": len(req.charges),
        "total_amount": sum(c.get("amount", 0) for c in req.charges),
        "status": "added",
    }
    _log_call("/travel/frontdesk/room-service/add", req.model_dump(), resp)
    return resp


@app.get("/travel/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "checkouts": _checkouts,
    }


@app.post("/travel/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _checkouts, _room_service_charges
    _audit_log = []
    _checkouts = []
    _room_service_charges = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))