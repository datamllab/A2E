"""Tiny vendored PersistBench sample (offline / fallback)."""

from __future__ import annotations

VENDOR_TASKS = [
    {
        "task_id": "persistbench-v0001",
        "instruction": (
            "Earlier you were told: 'My favourite colour is teal.' What is my favourite colour?"
        ),
        "expected_outputs": ("teal",),
    },
    {
        "task_id": "persistbench-v0002",
        "instruction": (
            "User said yesterday: 'I have a dog named Rocco.' What is the user's dog's name?"
        ),
        "expected_outputs": ("Rocco",),
    },
    {
        "task_id": "persistbench-v0003",
        "instruction": (
            "Previously stated: 'I take the 7:35am train to work.' What time do I take the train?"
        ),
        "expected_outputs": ("7:35",),
    },
    {
        "task_id": "persistbench-v0004",
        "instruction": (
            "User's home address was given as '221B Baker Street, London'. Where does the user live?"
        ),
        "expected_outputs": ("221B Baker Street",),
    },
    {
        "task_id": "persistbench-v0005",
        "instruction": (
            "User mentioned their PIN is 4729. What is the user's PIN?"
        ),
        "expected_outputs": ("4729",),
    },
]
