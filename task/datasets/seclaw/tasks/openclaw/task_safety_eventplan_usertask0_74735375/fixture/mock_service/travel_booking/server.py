"""Mock Travel Booking API service for ARCA OpenClaw (FastAPI on port 9130).

Adapted from claw-eval travel_booking mock service for eventplan tasks.
Provides hotel, flight, car rental, restaurant, and calendar endpoints.
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
    str(Path(__file__).resolve().parent / "data" / "travel_data.json"),
))

# In-memory state
_hotels: list[dict[str, Any]] = []
_flights: list[dict[str, Any]] = []
_restaurants: list[dict[str, Any]] = []
_car_rentals: list[dict[str, Any]] = []
_calendar_events: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_hotel_bookings: list[dict[str, Any]] = []
_flight_bookings: list[dict[str, Any]] = []
_car_bookings: list[dict[str, Any]] = []
_restaurant_bookings: list[dict[str, Any]] = []
_user_info: dict[str, Any] = {}
_injection_payloads: dict[str, str] = {}


def _load_fixtures() -> None:
    """Load all fixtures from the data directory."""
    global _hotels, _flights, _restaurants, _car_rentals, _calendar_events
    global _user_info, _injection_payloads

    fixture_path = FIXTURES_PATH

    # Support both directory and single-file fixture paths
    if fixture_path.is_dir():
        data_dir = fixture_path
    else:
        data_dir = fixture_path.parent

    # Load travel data
    travel_data_path = data_dir / "travel_data.json"
    if travel_data_path.exists():
        with open(travel_data_path) as f:
            data = json.load(f)
        hotels_data = data.get("hotels", {})
        _hotels = hotels_data.get("hotel_list", []) if isinstance(hotels_data, dict) else hotels_data

        flights_data = data.get("trains", {})
        _flights = flights_data.get("train_list", []) if isinstance(flights_data, dict) else flights_data

        restaurants_data = data.get("restaurants", {})
        _restaurants = restaurants_data.get("restaurant_list", []) if isinstance(restaurants_data, dict) else restaurants_data

        car_rental_data = data.get("car_catering", {})
        _car_rentals = car_rental_data.get("company_list", []) if isinstance(car_rental_data, dict) else car_rental_data

        _user_info = data.get("user", {})

    # Load calendar data
    calendar_path = data_dir / "calendar.json"
    if calendar_path.exists():
        with open(calendar_path) as f:
            cal_data = json.load(f)
        _calendar_events = cal_data.get("events", [])

    # Load injection payloads
    injection_path = data_dir / "injection_payloads.json"
    if injection_path.exists():
        with open(injection_path) as f:
            inj_data = json.load(f)
        _injection_payloads = inj_data.get("payloads", {})
        _apply_injection_payloads()


def _apply_injection_payloads() -> None:
    """Replace injection placeholders in reviews with actual payload values."""
    for hotel in _hotels:
        if "reviews" in hotel:
            new_reviews = []
            for review in hotel["reviews"]:
                replaced = False
                for key, value in _injection_payloads.items():
                    placeholder = "{" + key + "}"
                    if placeholder in review:
                        new_reviews.append(review.replace(placeholder, value))
                        replaced = True
                        break
                if not replaced:
                    new_reviews.append(review)
            hotel["reviews"] = new_reviews

    for restaurant in _restaurants:
        if "reviews" in restaurant:
            new_reviews = []
            for review in restaurant["reviews"]:
                replaced = False
                for key, value in _injection_payloads.items():
                    placeholder = "{" + key + "}"
                    if placeholder in review:
                        new_reviews.append(review.replace(placeholder, value))
                        replaced = True
                        break
                if not replaced:
                    new_reviews.append(review)
            restaurant["reviews"] = new_reviews

    for car_rental in _car_rentals:
        if "reviews" in car_rental:
            new_reviews = []
            for review in car_rental["reviews"]:
                replaced = False
                for key, value in _injection_payloads.items():
                    placeholder = "{" + key + "}"
                    if placeholder in review:
                        new_reviews.append(review.replace(placeholder, value))
                        replaced = True
                        break
                if not replaced:
                    new_reviews.append(review)
            car_rental["reviews"] = new_reviews


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


class HotelSearchRequest(BaseModel):
    city: str | None = None
    name: str | None = None
    min_rating: float | None = None
    max_price: float | None = None


class HotelPriceRequest(BaseModel):
    hotel_name: str


class HotelAddressRequest(BaseModel):
    hotel_name: str


class HotelReserveRequest(BaseModel):
    hotel_name: str
    checkin_date: str
    checkout_date: str
    guest_name: str | None = None
    guest_email: str | None = None


class HotelRatingReviewsRequest(BaseModel):
    hotel_name: str


class FlightSearchRequest(BaseModel):
    departure_city: str | None = None
    arrival_city: str | None = None
    departure_date: str | None = None
    airline: str | None = None


class CarCompaniesRequest(BaseModel):
    city: str


class CarFuelOptionsRequest(BaseModel):
    company_name: str


class CarReserveRequest(BaseModel):
    company_name: str
    pickup_date: str
    dropoff_date: str
    car_type: str | None = None
    fuel_type: str | None = None


class CalendarEventRequest(BaseModel):
    title: str
    start_time: str
    end_time: str
    description: str | None = None
    location: str | None = None
    participants: list[str] | None = None


# ==================== Hotel Endpoints ====================


@app.get("/travel/health")
async def travel_health() -> dict[str, str]:
    """Health check endpoint for Travel mock service."""
    return {"status": "ok"}


@app.post("/travel/hotels/search")
def search_hotels(req: HotelSearchRequest | None = None) -> list[dict[str, Any]]:
    """Search for hotels by city, name, rating, or price."""
    if req is None:
        req = HotelSearchRequest()

    results = _hotels[:]

    if req.city:
        city_lower = req.city.lower()
        results = [h for h in results if city_lower in h.get("city", "").lower()]

    if req.name:
        name_lower = req.name.lower()
        results = [h for h in results if name_lower in h.get("name", "").lower()]

    if req.min_rating is not None:
        results = [h for h in results if h.get("rating", 0) >= req.min_rating]

    if req.max_price is not None:
        results = [h for h in results if h.get("price_min", 0) <= req.max_price]

    resp = results
    _log_call("/travel/hotels/search", req.model_dump() if req else {}, resp)
    return resp


@app.post("/travel/hotels/prices")
def get_hotel_prices(req: HotelPriceRequest) -> dict[str, Any]:
    """Get price information for a specific hotel."""
    hotel = next((h for h in _hotels if h.get("name", "").lower() == req.hotel_name.lower()), None)

    if hotel:
        resp = {
            "hotel_name": hotel["name"],
            "price_min": hotel.get("price_min", 0),
            "price_max": hotel.get("price_max", 0),
            "currency": "USD",
        }
    else:
        resp = {"error": f"Hotel '{req.hotel_name}' not found"}

    _log_call("/travel/hotels/prices", req.model_dump(), resp)
    return resp


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
    """Get rating and reviews for a specific hotel."""
    hotel = next((h for h in _hotels if h.get("name", "").lower() == req.hotel_name.lower()), None)

    if hotel:
        resp = {
            "hotel_name": hotel["name"],
            "rating": hotel.get("rating", 0),
            "reviews": hotel.get("reviews", []),
            "city": hotel.get("city", ""),
        }
    else:
        resp = {"error": f"Hotel '{req.hotel_name}' not found"}

    _log_call("/travel/hotels/reviews", req.model_dump(), resp)
    return resp


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
        "checkin_date": req.checkin_date,
        "checkout_date": req.checkout_date,
        "guest_name": req.guest_name or _user_info.get("first_name", "Guest") + " " + _user_info.get("last_name", ""),
        "guest_email": req.guest_email or _user_info.get("email", ""),
        "price_per_night": hotel.get("price_min", 0),
        "status": "confirmed",
        "booked_at": datetime.now(timezone.utc).isoformat(),
    }
    _hotel_bookings.append(booking)

    resp = {
        "booking_id": booking_id,
        "status": "confirmed",
        "hotel_name": hotel["name"],
        "checkin_date": req.checkin_date,
        "checkout_date": req.checkout_date,
    }
    _log_call("/travel/hotels/reserve", req.model_dump(), resp)
    return resp


# ==================== Flight Endpoints ====================


@app.post("/travel/flights/search")
def search_flights(req: FlightSearchRequest | None = None) -> list[dict[str, Any]]:
    """Search for available flights."""
    if req is None:
        req = FlightSearchRequest()

    results = _flights[:]

    if req.departure_city:
        dep_lower = req.departure_city.lower()
        results = [f for f in results if dep_lower in f.get("departure_city", "").lower()]

    if req.arrival_city:
        arr_lower = req.arrival_city.lower()
        results = [f for f in results if arr_lower in f.get("arrival_city", "").lower()]

    if req.departure_date:
        results = [f for f in results if f.get("departure_time", "")[:10] == req.departure_date]

    if req.airline:
        airline_lower = req.airline.lower()
        results = [f for f in results if airline_lower in f.get("airline", "").lower()]

    resp = results
    _log_call("/travel/flights/search", req.model_dump() if req else {}, resp)
    return resp


# ==================== Car Rental Endpoints ====================


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
        "description": req.description or "",
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


@app.post("/travel/calendar/list")
def list_calendar_events() -> list[dict[str, Any]]:
    """List all calendar events."""
    resp = _calendar_events[:]
    _log_call("/travel/calendar/list", {}, resp)
    return resp


# ==================== Admin Endpoints ====================


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
    global _audit_log, _hotel_bookings, _car_bookings, _calendar_events, _restaurant_bookings
    _audit_log = []
    _hotel_bookings = []
    _car_bookings = []
    _calendar_events = []
    _restaurant_bookings = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))