"""Mock Travel Booking API service for ARCA OpenClaw (FastAPI on port 9130).

Adapted from claw-eval eventplan_usertask13.
Provides travel booking APIs: Hotels, Car Rentals, Calendar.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Travel Booking API")

from _base import add_error_injection
add_error_injection(app)

# Configuration
FIXTURES_PATH = Path(os.environ.get(
    "TRAVEL_BOOKING_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

# In-memory state
_hotels: list[dict[str, Any]] = []
_flights: list[dict[str, Any]] = []
_restaurants: list[dict[str, Any]] = []
_car_rentals: list[dict[str, Any]] = []
_calendar_events: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_hotel_bookings: list[dict[str, Any]] = []
_car_bookings: list[dict[str, Any]] = []
_user_info: dict[str, Any] = {}


def _load_fixtures() -> None:
    """Load all fixtures from the data directory."""
    global _hotels, _flights, _restaurants, _car_rentals, _calendar_events
    global _user_info, _hotel_bookings, _car_bookings

    # Load travel data
    travel_data_path = FIXTURES_PATH / "travel_data.json"
    if travel_data_path.exists():
        with open(travel_data_path) as f:
            data = json.load(f)

        hotels_data = data.get("hotels", {})
        _hotels = hotels_data.get("hotel_list", []) if isinstance(hotels_data, dict) else hotels_data if isinstance(hotels_data, list) else []

        flights_data = data.get("flights", {})
        _flights = flights_data.get("flight_list", []) if isinstance(flights_data, dict) else flights_data if isinstance(flights_data, list) else []

        restaurants_data = data.get("restaurants", {})
        _restaurants = restaurants_data.get("restaurant_list", []) if isinstance(restaurants_data, dict) else restaurants_data if isinstance(restaurants_data, list) else []

        car_rental_data = data.get("car_catering", {})
        _car_rentals = car_rental_data.get("company_list", []) if isinstance(car_rental_data, dict) else car_rental_data if isinstance(car_rental_data, list) else []

        _user_info = data.get("user", {})

    # Load calendar data
    calendar_path = FIXTURES_PATH / "calendar.json"
    if calendar_path.exists():
        with open(calendar_path) as f:
            cal_data = json.load(f)
        _calendar_events = cal_data.get("events", [])

    # Load and apply injection payloads
    injection_path = FIXTURES_PATH / "injection_payloads.json"
    if injection_path.exists():
        with open(injection_path) as f:
            inj_data = json.load(f)
        payloads = inj_data.get("payloads", {})
        if payloads:
            _apply_injection_payloads(payloads)

    _hotel_bookings = []
    _car_bookings = []


def _apply_injection_payloads(payloads: dict[str, str]) -> None:
    """Replace injection placeholders in reviews with payload values.

    Replaces {injection_X_N} patterns in hotel, restaurant, and car rental
    reviews with corresponding payload values from injection_payloads.json.
    """
    for hotel in _hotels:
        if "reviews" in hotel:
            new_reviews = []
            for review in hotel["reviews"]:
                if isinstance(review, str):
                    for key, value in payloads.items():
                        placeholder = "{" + key + "}"
                        if placeholder in review:
                            review = value
                            break
                new_reviews.append(review)
            hotel["reviews"] = new_reviews

    for restaurant in _restaurants:
        if "reviews" in restaurant:
            new_reviews = []
            for review in restaurant["reviews"]:
                if isinstance(review, str):
                    for key, value in payloads.items():
                        placeholder = "{" + key + "}"
                        if placeholder in review:
                            review = value
                            break
                new_reviews.append(review)
            restaurant["reviews"] = new_reviews

    for car in _car_rentals:
        if "reviews" in car:
            new_reviews = []
            for review in car["reviews"]:
                if isinstance(review, str):
                    for key, value in payloads.items():
                        placeholder = "{" + key + "}"
                        if placeholder in review:
                            review = value
                            break
                new_reviews.append(review)
            car["reviews"] = new_reviews


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ==================== Request/Response Models ====================


class HotelPriceRequest(BaseModel):
    hotel_names: list[str] = Field(..., description="List of hotel names")


class HotelAddressRequest(BaseModel):
    hotel_name: str = Field(..., description="Hotel name")


class HotelRatingReviewsRequest(BaseModel):
    hotel_names: list[str] = Field(..., description="List of hotel names")


class HotelReserveRequest(BaseModel):
    hotel_name: str = Field(..., description="Hotel name")
    check_in: str = Field(..., description="Check-in date")
    check_out: str = Field(..., description="Check-out date")
    guests: int = Field(1, description="Number of guests")


class CarCompaniesRequest(BaseModel):
    city: str = Field(..., description="City name")


class CarFuelOptionsRequest(BaseModel):
    company_name: str = Field(..., description="Car rental company name")


class CarReserveRequest(BaseModel):
    company_name: str = Field(..., description="Car rental company name")
    pickup_date: str = Field(..., description="Pickup date")
    dropoff_date: str = Field(..., description="Dropoff date")
    car_type: str | None = Field(None, description="Car type")
    fuel_type: str | None = Field(None, description="Fuel type")


class CalendarEventRequest(BaseModel):
    title: str = Field(..., description="Event title")
    start_time: str = Field(..., description="Event start time")
    end_time: str = Field(..., description="Event end time")
    location: str | None = Field(None, description="Event location")
    participants: list[str] | None = Field(None, description="Event participants")


# ==================== Hotel Endpoints ====================


@app.get("/travel/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/travel/hotels/prices")
def get_hotel_prices(req: HotelPriceRequest) -> dict[str, Any]:
    """Get price information for one or more hotels."""
    results = []
    for hotel_name in req.hotel_names:
        hotel = next((h for h in _hotels if h.get("name", "").lower() == hotel_name.lower()), None)
        if hotel:
            results.append({
                "hotel_name": hotel["name"],
                "price_min": hotel.get("price_min", 0),
                "price_max": hotel.get("price_max", 0),
                "currency": "USD",
            })
        else:
            results.append({"hotel_name": hotel_name, "error": f"Hotel '{hotel_name}' not found"})

    _log_call("/travel/hotels/prices", req.model_dump(), results)
    return {"hotels": results}


@app.post("/travel/hotels/address")
def get_hotel_address(req: HotelAddressRequest) -> dict[str, Any]:
    """Get address for a specific hotel."""
    hotel = next((h for h in _hotels if h.get("name", "").lower() == req.hotel_name.lower()), None)

    if hotel:
        resp = {
            "hotel_name": hotel["name"],
            "address": hotel.get("address", ""),
            "city": hotel.get("city", ""),
        }
    else:
        resp = {"error": f"Hotel '{req.hotel_name}' not found"}

    _log_call("/travel/hotels/address", req.model_dump(), resp)
    return resp


@app.post("/travel/hotels/reviews")
def get_hotel_rating_reviews(req: HotelRatingReviewsRequest) -> dict[str, Any]:
    """Get rating and reviews for one or more hotels."""
    results = []
    for hotel_name in req.hotel_names:
        hotel = next((h for h in _hotels if h.get("name", "").lower() == hotel_name.lower()), None)
        if hotel:
            results.append({
                "hotel_name": hotel["name"],
                "rating": hotel.get("rating", 0),
                "reviews": hotel.get("reviews", []),
                "city": hotel.get("city", ""),
            })
        else:
            results.append({"hotel_name": hotel_name, "error": f"Hotel '{hotel_name}' not found"})

    _log_call("/travel/hotels/reviews", req.model_dump(), {"hotels": results})
    return {"hotels": results}


@app.post("/travel/hotels/reserve")
def reserve_hotel(req: HotelReserveRequest) -> dict[str, Any]:
    """Reserve a hotel room."""
    hotel = next((h for h in _hotels if h.get("name", "").lower() == req.hotel_name.lower()), None)

    if not hotel:
        resp = {"error": f"Hotel '{req.hotel_name}' not found"}
        _log_call("/travel/hotels/reserve", req.model_dump(), resp)
        return resp

    booking_id = f"HTL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{len(_hotel_bookings) + 1}"

    booking = {
        "booking_id": booking_id,
        "hotel_name": hotel["name"],
        "hotel_city": hotel.get("city", ""),
        "checkin_date": req.check_in,
        "checkout_date": req.check_out,
        "guests": req.guests,
        "guest_name": _user_info.get("first_name", "Guest") + " " + _user_info.get("last_name", ""),
        "guest_email": _user_info.get("email", ""),
        "price_per_night": hotel.get("price_min", 0),
        "status": "confirmed",
        "booked_at": datetime.now(timezone.utc).isoformat(),
    }
    _hotel_bookings.append(booking)

    resp = {
        "booking_id": booking_id,
        "status": "confirmed",
        "hotel_name": hotel["name"],
        "checkin_date": req.check_in,
        "checkout_date": req.check_out,
    }
    _log_call("/travel/hotels/reserve", req.model_dump(), resp)
    return resp


# ==================== Car Rental / Catering Endpoints ====================


@app.post("/travel/cars/companies")
def get_car_rental_companies(req: CarCompaniesRequest) -> list[dict[str, Any]]:
    """Get all car rental companies in a specific city."""
    results = _car_rentals[:]

    if req.city:
        city_lower = req.city.lower()
        results = [c for c in results if city_lower in c.get("city", "").lower()]

    _log_call("/travel/cars/companies", req.model_dump(), results)
    return results


@app.post("/travel/cars/fuel_options")
def get_car_fuel_options(req: CarFuelOptionsRequest) -> dict[str, Any]:
    """Get fuel options for a specific car rental company."""
    company = next((c for c in _car_rentals if c.get("name", "").lower() == req.company_name.lower()), None)

    if company:
        resp = {
            "company_name": company["name"],
            "fuel_options": company.get("fuel_options", []),
            "city": company.get("city", ""),
        }
    else:
        resp = {"error": f"Car rental company '{req.company_name}' not found"}

    _log_call("/travel/cars/fuel_options", req.model_dump(), resp)
    return resp


@app.post("/travel/cars/reserve")
def reserve_car(req: CarReserveRequest) -> dict[str, Any]:
    """Reserve a car rental."""
    company = next((c for c in _car_rentals if c.get("name", "").lower() == req.company_name.lower()), None)

    if not company:
        resp = {"error": f"Car rental company '{req.company_name}' not found"}
        _log_call("/travel/cars/reserve", req.model_dump(), resp)
        return resp

    car_types = company.get("car_types_available", ["Sedan"])
    if req.car_type and req.car_type not in car_types:
        resp = {"error": f"Car type '{req.car_type}' not available at {company['name']}"}
        _log_call("/travel/cars/reserve", req.model_dump(), resp)
        return resp

    fuel_options = company.get("fuel_options", ["Regular"])
    if req.fuel_type and req.fuel_type not in fuel_options:
        resp = {"error": f"Fuel type '{req.fuel_type}' not available at {company['name']}"}
        _log_call("/travel/cars/reserve", req.model_dump(), resp)
        return resp

    booking_id = f"CAR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{len(_car_bookings) + 1}"

    booking = {
        "booking_id": booking_id,
        "company_name": company["name"],
        "company_city": company.get("city", ""),
        "pickup_date": req.pickup_date,
        "dropoff_date": req.dropoff_date,
        "car_type": req.car_type or car_types[0] if car_types else "Sedan",
        "fuel_type": req.fuel_type or fuel_options[0] if fuel_options else "Regular",
        "price_per_day": company.get("price_per_day", 0),
        "status": "confirmed",
        "booked_at": datetime.now(timezone.utc).isoformat(),
    }
    _car_bookings.append(booking)

    resp = {
        "booking_id": booking_id,
        "status": "confirmed",
        "company_name": company["name"],
        "pickup_date": req.pickup_date,
        "dropoff_date": req.dropoff_date,
    }
    _log_call("/travel/cars/reserve", req.model_dump(), resp)
    return resp


# ==================== Calendar Endpoints ====================


@app.post("/travel/calendar/create")
def create_calendar_event(req: CalendarEventRequest) -> dict[str, Any]:
    """Create a calendar event."""
    event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{len(_calendar_events) + 1}"

    event = {
        "event_id": event_id,
        "title": req.title,
        "start_time": req.start_time,
        "end_time": req.end_time,
        "description": "",
        "location": req.location or "",
        "participants": req.participants or [],
        "status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _calendar_events.append(event)

    resp = {
        "event_id": event_id,
        "status": "created",
        "title": req.title,
        "start_time": req.start_time,
        "end_time": req.end_time,
    }
    _log_call("/travel/calendar/create", req.model_dump(), resp)
    return resp


# ==================== Audit Endpoints ====================


@app.get("/travel/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "hotel_bookings": _hotel_bookings,
        "car_bookings": _car_bookings,
        "calendar_events": _calendar_events,
    }


@app.post("/travel/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _hotel_bookings, _car_bookings, _calendar_events
    _audit_log = []
    _hotel_bookings = []
    _car_bookings = []
    _calendar_events = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))