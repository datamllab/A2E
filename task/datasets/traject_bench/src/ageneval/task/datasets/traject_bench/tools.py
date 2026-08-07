"""traject-bench tool schemas + deterministic stub executor.

The domain is a small "assistant utilities" toolkit. No sandbox: the executor
returns deterministic, self-consistent results so tool-calling trajectories are
reproducible across runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Deterministic stub data ------------------------------------------------------

_WEATHER_C: dict[str, int] = {
    "tokyo": 21,
    "paris": 17,
    "london": 14,
    "new york": 19,
    "sydney": 24,
}

_FACTS: dict[str, str] = {
    "mount everest": "Mount Everest is 8849 metres tall.",
    "speed of light": "The speed of light is 299792458 metres per second.",
    "earth": "Earth has a mean radius of 6371 kilometres.",
    "moon": "The Moon is on average 384400 kilometres from Earth.",
}

# Linear conversion factors keyed by (from_unit, to_unit), lowercased.
_LINEAR_UNITS: dict[tuple[str, str], float] = {
    ("km", "mi"): 0.621371,
    ("mi", "km"): 1.609344,
    ("kg", "lb"): 2.20462,
    ("lb", "kg"): 0.453592,
    ("m", "ft"): 3.28084,
    ("ft", "m"): 0.3048,
}

# USD-based exchange rates (1 unit of currency -> USD).
_USD_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.087,
    "GBP": 1.27,
    "JPY": 0.0067,
}


def get_traject_bench_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-style function schemas for the traject-bench tool domain."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current temperature (Celsius) for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate an arithmetic expression and return the number.",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "convert_units",
                "description": (
                    "Convert a value between units. Supports km/mi, kg/lb, m/ft "
                    "and Celsius/Fahrenheit (C/F)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "from_unit": {"type": "string"},
                        "to_unit": {"type": "string"},
                    },
                    "required": ["value", "from_unit", "to_unit"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lookup_fact",
                "description": "Look up a short factual statement about a topic.",
                "parameters": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "convert_currency",
                "description": "Convert a money amount between currencies (USD, EUR, GBP, JPY).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "from_currency": {"type": "string"},
                        "to_currency": {"type": "string"},
                    },
                    "required": ["amount", "from_currency", "to_currency"],
                },
            },
        },
    ]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def traject_bench_tool_executor(
    name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]
) -> Any:
    """Deterministic stub executor for the traject-bench tool domain."""
    if name == "get_weather":
        city = str(arguments.get("city", "")).strip().lower()
        if city in _WEATHER_C:
            return {"city": arguments.get("city"), "temperature_c": _WEATHER_C[city]}
        return {"error": f"no weather data for {arguments.get('city')!r}"}

    if name == "calculate":
        expr = str(arguments.get("expression", ""))
        allowed = set("0123456789.+-*/() ")
        if not expr or set(expr) - allowed:
            return {"error": f"unsupported expression {expr!r}"}
        try:
            result = eval(expr, {"__builtins__": {}}, {})
        except (SyntaxError, ZeroDivisionError, ValueError) as exc:
            return {"error": str(exc)}
        return {"expression": expr, "result": result}

    if name == "convert_units":
        value = _to_float(arguments.get("value"))
        from_u = str(arguments.get("from_unit", "")).strip().lower()
        to_u = str(arguments.get("to_unit", "")).strip().lower()
        if from_u in ("c", "celsius") and to_u in ("f", "fahrenheit"):
            return {"value": value, "from": "C", "to": "F", "result": value * 9 / 5 + 32}
        if from_u in ("f", "fahrenheit") and to_u in ("c", "celsius"):
            return {"value": value, "from": "F", "to": "C", "result": (value - 32) * 5 / 9}
        factor = _LINEAR_UNITS.get((from_u, to_u))
        if factor is None:
            return {"error": f"no conversion from {from_u!r} to {to_u!r}"}
        return {"value": value, "from": from_u, "to": to_u, "result": value * factor}

    if name == "lookup_fact":
        topic = str(arguments.get("topic", "")).strip().lower()
        if topic in _FACTS:
            return {"topic": topic, "fact": _FACTS[topic]}
        return {"error": f"no fact for {topic!r}"}

    if name == "convert_currency":
        amount = _to_float(arguments.get("amount"))
        from_c = str(arguments.get("from_currency", "")).strip().upper()
        to_c = str(arguments.get("to_currency", "")).strip().upper()
        if from_c not in _USD_RATES or to_c not in _USD_RATES:
            return {"error": f"unsupported currency pair {from_c}->{to_c}"}
        result = amount * _USD_RATES[from_c] / _USD_RATES[to_c]
        return {"amount": amount, "from": from_c, "to": to_c, "result": round(result, 2)}

    return {"error": f"unknown tool {name!r}"}
