"""Vendored traject-bench sample tasks.

Self-contained tool-calling tasks over a small "assistant utilities" domain.
Each task is a user request that needs 1-2 tool calls to answer correctly.
``expected_actions`` lists the ground-truth tool sequence for ``tool_recall``.
"""

VENDOR_TASKS = [
    {
        "task_id": "traject-v0001",
        "instruction": (
            "What is the temperature in Tokyo right now? Reply with the number "
            'in degrees Celsius as {"final_answer": "..."}.'
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "get_weather", "arguments": {"city": "Tokyo"}},
        ],
        "expected_outputs": ["21"],
    },
    {
        "task_id": "traject-v0002",
        "instruction": (
            "Compute 47 * 19 + 8 and give me the result as the final answer."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "calculate", "arguments": {"expression": "47 * 19 + 8"}},
        ],
        "expected_outputs": ["901"],
    },
    {
        "task_id": "traject-v0003",
        "instruction": (
            "Convert 10 kilometers to miles and tell me the result."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "convert_units",
             "arguments": {"value": 10, "from_unit": "km", "to_unit": "mi"}},
        ],
        "expected_outputs": ["6.21"],
    },
    {
        "task_id": "traject-v0004",
        "instruction": (
            "How tall is Mount Everest? Look up the fact and report its height."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "lookup_fact", "arguments": {"topic": "mount everest"}},
        ],
        "expected_outputs": ["8849"],
    },
    {
        "task_id": "traject-v0005",
        "instruction": (
            "I have 200 US dollars. How many euros is that? Convert and answer."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "convert_currency",
             "arguments": {"amount": 200, "from_currency": "USD", "to_currency": "EUR"}},
        ],
        "expected_outputs": ["184"],
    },
    {
        "task_id": "traject-v0006",
        "instruction": (
            "It is currently the temperature shown for Paris. Convert that "
            "Celsius temperature to Fahrenheit and give me the Fahrenheit value."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "get_weather", "arguments": {"city": "Paris"}},
            {"name": "convert_units",
             "arguments": {"value": 17, "from_unit": "C", "to_unit": "F"}},
        ],
        "expected_outputs": ["62.6"],
    },
    {
        "task_id": "traject-v0007",
        "instruction": (
            "Look up the speed of light, then divide it by 2 and report the result."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "lookup_fact", "arguments": {"topic": "speed of light"}},
            {"name": "calculate", "arguments": {"expression": "299792458 / 2"}},
        ],
        "expected_outputs": ["149896229"],
    },
    {
        "task_id": "traject-v0008",
        "instruction": (
            "I weigh 80 kilograms. Convert my weight to pounds and answer."
        ),
        "initial_state": {},
        "expected_actions": [
            {"name": "convert_units",
             "arguments": {"value": 80, "from_unit": "kg", "to_unit": "lb"}},
        ],
        "expected_outputs": ["176"],
    },
]
