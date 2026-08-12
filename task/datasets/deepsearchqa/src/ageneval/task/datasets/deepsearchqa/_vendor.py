"""Tiny DeepSearchQA sample for offline / fallback loads."""

from __future__ import annotations

VENDOR_TASKS = [
    {
        "task_id": "deepsearchqa-v0001",
        "problem": (
            "By using the NHS website for “Shoulder Pain”, which of the possible "
            "causes of the condition creates symptoms like poor balance and coordination?"
        ),
        "problem_category": "Health",
        "answer": "Hypermobility",
        "answer_type": "Single Answer",
    },
    {
        "task_id": "deepsearchqa-v0002",
        "problem": (
            "During the 2014 Term Year for the United States Supreme Court, how many "
            "certiorari denials were on the Order List on December 15th?"
        ),
        "problem_category": "Politics & Government",
        "answer": "86",
        "answer_type": "Single Answer",
    },
    {
        "task_id": "deepsearchqa-v0003",
        "problem": (
            "Of the countries that were part of the top 10 countries with the lowest "
            "GPI scores in both 2022 and 2023 (according to Vision of Humanity), which "
            "countries had a reported gun homicide rate of less than 0.20 per 100,000 "
            "population in both 2022 and 2023 (according to World Population Review)? "
            "Only provide the country names."
        ),
        "problem_category": "Geography",
        "answer": "Austria, Switzerland, Singapore",
        "answer_type": "Set Answer",
    },
]
