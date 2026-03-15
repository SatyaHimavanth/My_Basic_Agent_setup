from __future__ import annotations

import ast
import operator
import platform
import random
import uuid

from datetime import datetime


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_DUMMY_WEATHER = {
    "delhi": {"condition": "Sunny", "temperature_c": 33, "humidity": 38},
    "mumbai": {"condition": "Humid", "temperature_c": 31, "humidity": 76},
    "bengaluru": {"condition": "Cloudy", "temperature_c": 24, "humidity": 62},
    "hyderabad": {"condition": "Warm", "temperature_c": 30, "humidity": 44},
    "london": {"condition": "Rainy", "temperature_c": 12, "humidity": 81},
    "new york": {"condition": "Windy", "temperature_c": 16, "humidity": 57},
}


def get_current_time() -> str:
    """Return the current local date and time."""

    now = datetime.now().astimezone()
    return now.strftime("%A, %d %B %Y %I:%M:%S %p %Z")


def get_current_day() -> str:
    """Return the current local day and date."""

    now = datetime.now().astimezone()
    return now.strftime("%A, %d %B %Y")


def get_system_info() -> dict[str, str]:
    """Return basic local system information."""

    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }


def generate_random_number(min_value: int = 1, max_value: int = 100) -> int:
    """Generate a random integer between min_value and max_value."""

    if min_value > max_value:
        raise ValueError("min_value must be less than or equal to max_value")
    return random.randint(min_value, max_value)


def generate_uuid() -> str:
    """Generate a random UUID."""

    return str(uuid.uuid4())


def _eval_ast(node):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        return _ALLOWED_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        operand = _eval_ast(node.operand)
        return _ALLOWED_OPERATORS[type(node.op)](operand)
    raise ValueError("Unsupported expression")


def calculate_expression(expression: str) -> float:
    """Safely evaluate a simple math expression such as 12 / (3 + 1)."""

    parsed = ast.parse(expression, mode="eval")
    return _eval_ast(parsed)


def get_weather(city: str) -> dict[str, str | int]:
    """Return dummy weather data for a city. Requires human approval before execution."""

    normalized_city = city.strip().lower()
    sample = _DUMMY_WEATHER.get(
        normalized_city,
        {"condition": "Pleasant", "temperature_c": 25, "humidity": 50},
    )
    return {
        "city": city.strip(),
        "condition": str(sample["condition"]),
        "temperature_c": int(sample["temperature_c"]),
        "humidity": int(sample["humidity"]),
        "note": "This is dummy offline weather data for HITL flow testing.",
    }


TOOLS = [
    get_current_time,
    get_current_day,
    get_system_info,
    generate_random_number,
    generate_uuid,
    calculate_expression,
    get_weather,
]
