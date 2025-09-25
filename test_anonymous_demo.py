#!/usr/bin/env python3
"""
Test script to demonstrate the difference between anonymous and non-anonymous voting.
This script creates sample sessions to show how the results differ.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def create_test_session(anonymous=True, session_title="Test Session"):
    """Create a test voting session with sample data"""

    session_id = str(uuid.uuid4())
    date_folder = datetime.now().strftime("%Y-%m-%d")

    # Create the session data
    session_data = {
        "id": session_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "completed": None,
        "title": session_title,
        "description": f"Demo session showing {'anonymous' if anonymous else 'non-anonymous'} voting results",
        "items": [
            {"id": 1, "name": "Pizza", "description": "Classic Italian pizza"},
            {"id": 2, "name": "Burger", "description": "American cheeseburger"},
            {"id": 3, "name": "Sushi", "description": "Japanese sushi rolls"},
            {"id": 4, "name": "Tacos", "description": "Mexican street tacos"},
        ],
        "participants": {
            "participant-1": {
                "email": "alice@company.com",
                "token": "token123",
                "voted": True,
                "votes": {},
                "added": datetime.now(timezone.utc).isoformat(),
                "vote_timestamp": "2025-09-25T14:30:15.123456",
            },
            "participant-2": {
                "email": "bob@company.com",
                "token": "token456",
                "voted": True,
                "votes": {},
                "added": datetime.now(timezone.utc).isoformat(),
                "vote_timestamp": "2025-09-25T14:32:22.654321",
            },
            "participant-3": {
                "email": "carol@company.com",
                "token": "token789",
                "voted": True,
                "votes": {},
                "added": datetime.now(timezone.utc).isoformat(),
                "vote_timestamp": "2025-09-25T14:35:45.987654",
            },
        },
        "votes": {
            "participant-1": {"1": 5, "2": 3, "3": 2, "4": 0},  # Alice: Pizza fan
            "participant-2": {"1": 2, "2": 6, "3": 1, "4": 1},  # Bob: Burger lover
            "participant-3": {
                "1": 1,
                "2": 1,
                "3": 7,
                "4": 1,
            },  # Carol: Sushi enthusiast
        },
        "settings": {
            "anonymous": anonymous,
            "show_results_live": True,
            "votes_per_participant": 10,
            "results_access": "public",
            "show_item_names": True,
            "presentation_mode": True,
        },
        "status": "completed",
        "creator_id": "demo_creator_123",
        "creator_type": "admin",
    }

    # Create directory structure
    data_dir = Path("data/active") / date_folder
    data_dir.mkdir(parents=True, exist_ok=True)

    # Save session file
    session_file = data_dir / f"{session_id}.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)

    # Create empty key file
    key_file = data_dir / f"{session_id}.key"
    key_file.write_bytes(b"demo_key_for_testing_only")

    print(f"Created {'anonymous' if anonymous else 'non-anonymous'} test session:")
    print(f"  Session ID: {session_id}")
    print(f"  URL: http://127.0.0.1:5000/results/{session_id}")
    print(f"  File: {session_file}")
    print()

    return session_id


if __name__ == "__main__":
    print(
        "Creating demo voting sessions to show anonymous vs non-anonymous differences...\n"
    )

    # Create anonymous session
    anonymous_id = create_test_session(
        anonymous=True, session_title="🔒 Anonymous Lunch Vote"
    )

    # Create non-anonymous session
    non_anonymous_id = create_test_session(
        anonymous=False, session_title="👁️ Non-Anonymous Lunch Vote"
    )

    print("Demo sessions created successfully!")
    print("\nCompare the results pages to see the difference:")
    print(f"Anonymous:     http://127.0.0.1:5000/results/{anonymous_id}")
    print(f"Non-Anonymous: http://127.0.0.1:5000/results/{non_anonymous_id}")
    print("\nThe non-anonymous session will show individual participant voting details")
    print("while the anonymous session will only show aggregate totals.")
