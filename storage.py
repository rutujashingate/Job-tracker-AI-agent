"""Load and save the tracker's local JSON document."""

import json
import os
from pathlib import Path


DATA_FILE = Path(__file__).parent / "data" / "applications.json"


def empty_database():
    """Return the shape that the saved JSON document will use."""
    return {
        "search_goal": None,
        "applications": [],
        "outreach_history": [],
        "job_leads": [],
        "email_sync": {
            "start_date": "2025-06-01",
            "last_scan_at": None,
            "processed_message_ids": [],
        },
    }


def get_data_file(path=None):
    """Resolve the normal data path or an explicit testing override."""
    if path is not None:
        return Path(path)
    environment_path = os.environ.get("JOB_TRACKER_DATA_FILE")
    return Path(environment_path).expanduser() if environment_path else DATA_FILE


def load_database(path=None):
    """Load saved tracker data, or return a new database when no file exists."""
    file_path = get_data_file(path)
    if not file_path.exists():
        return empty_database()

    try:
        with file_path.open("r", encoding="utf-8") as file:
            database = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Saved data is not valid JSON: {file_path}") from exc

    if not isinstance(database, dict):
        raise ValueError("Saved data must be a JSON object.")

    database.setdefault("search_goal", None)
    database.setdefault("applications", [])
    database.setdefault("outreach_history", [])
    database.setdefault("job_leads", [])
    database.setdefault(
        "email_sync",
        {
            "start_date": "2025-06-01",
            "last_scan_at": None,
            "processed_message_ids": [],
        },
    )
    if database["search_goal"] is not None and not isinstance(
        database["search_goal"], dict
    ):
        raise ValueError("Saved search_goal must be an object or null.")
    if not isinstance(database["applications"], list):
        raise ValueError("Saved applications must be a list.")
    if not isinstance(database["outreach_history"], list):
        raise ValueError("Saved outreach_history must be a list.")
    if not isinstance(database["job_leads"], list):
        raise ValueError("Saved job_leads must be a list.")
    if not isinstance(database["email_sync"], dict):
        raise ValueError("Saved email_sync must be an object.")
    return database


def save_database(database, approved=False, path=None):
    """Atomically save tracker data after the caller records approval."""
    if approved is not True:
        raise PermissionError("Saving requires explicit user approval.")

    file_path = get_data_file(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(database, file, indent=2)
        file.write("\n")
    temporary_path.replace(file_path)
    return file_path
