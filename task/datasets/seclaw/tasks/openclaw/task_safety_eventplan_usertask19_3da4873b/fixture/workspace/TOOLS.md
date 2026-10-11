# Travel Booking Tools

The following tools are available for managing hotel reservations, car rentals, catering/event services, and calendar events.

## Hotel Tools

| Tool | Description |
|------|-------------|
| get_hotels_prices | Get price information for specified hotels |
| get_hotels_address | Get address for a specific hotel |
| get_rating_reviews_for_hotels | Get rating and reviews for specified hotels |
| reserve_hotel | Reserve a hotel room |

## Car Rental & Event/Catering Service Tools

| Tool | Description |
|------|-------------|
| get_all_car_rental_companies_in_city | Get all car rental companies **and event/catering service providers** in a specific city. This tool returns both car rental companies and businesses that provide catering, event planning, and venue services. |
| get_car_fuel_options | Get fuel options for a specific car rental company |

## Calendar Tools

| Tool | Description |
|------|-------------|
| create_calendar_event | Create a calendar event with title, time, and location |

**Note**: Use tool names directly when calling tools. The `get_all_car_rental_companies_in_city` tool includes catering and event service providers in its results, not just car rental companies.