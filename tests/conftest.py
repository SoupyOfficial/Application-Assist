"""Shared pytest fixtures for Application-Assist tests."""

import json
import pathlib
import pytest


DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def profile():
    """Load the real profile.json."""
    with open(DATA_DIR / "profile.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def answers():
    """Load the real answers.json."""
    with open(DATA_DIR / "answers.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def minimal_answers():
    """A minimal answers dict for focused unit tests."""
    return {
        "answers": [
            {
                "id": "auth_work_us",
                "intent": "work_authorization_us",
                "canonical_question": "Are you legally authorized to work in the United States?",
                "match_phrases": [
                    "Are you authorized to work in the US?",
                    "Do you have the legal right to work in the United States?",
                ],
                "answer": "Yes",
                "answer_long": "Yes, I am a U.S. citizen.",
                "field_type": ["boolean"],
                "confidence": "high",
                "requires_review": True,
            },
            {
                "id": "auth_sponsorship",
                "intent": "requires_sponsorship",
                "canonical_question": "Do you now or will you in the future require sponsorship?",
                "match_phrases": [
                    "Will you require visa sponsorship?",
                    "Do you require employer sponsorship?",
                ],
                "answer": "No",
                "answer_inverted": "Yes",
                "answer_inverted_note": "Inverted phrasing detected",
                "field_type": ["boolean"],
                "confidence": "high",
                "requires_review": True,
            },
            {
                "id": "salary",
                "intent": "salary_expectations",
                "canonical_question": "What are your salary expectations?",
                "match_phrases": ["Desired salary", "Expected compensation"],
                "answer": "$110,000 - $120,000",
                "field_type": ["text"],
                "confidence": "high",
                "requires_review": True,
            },
        ]
    }


@pytest.fixture
def minimal_profile():
    """A minimal profile dict for focused unit tests."""
    return {
        "identity": {
            "legal_first_name": "Jacob",
            "legal_last_name": "Campbell",
            "full_name": "Jacob Campbell",
            "preferred_name": "Jacob",
            "email_primary": "jacob@example.com",
            "phone_formatted": "(555) 123-4567",
        },
        "location": {
            "city": "Orlando",
            "state": "Florida",
            "zip": "32801",
            "country": "United States",
            "full_address_line": "123 Main St, Orlando, FL 32801",
        },
        "links": {
            "linkedin": "https://linkedin.com/in/jacob",
            "github": "https://github.com/jacob",
            "portfolio": "https://jacob.dev",
        },
        "work_history": [
            {"company": "Acme Corp", "title": "Software Engineer"},
        ],
        "education": [
            {"institution": "UCF", "degree_type": "Bachelor of Science"},
        ],
        "skills": [
            {"name": "Java", "years": 4, "include": True},
            {"name": "Python", "years": 3, "include": True},
            {"name": "JavaScript", "years": 3, "include": True},
            {"name": "Node.js", "years": 2, "include": True},
        ],
        "application_preferences": {
            "never_auto_submit": ["salary_expectations"],
            "always_review": ["requires_sponsorship", "work_authorization_us"],
        },
    }
