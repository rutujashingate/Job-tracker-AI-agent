"""The local JSON store will be connected after approval gates are built."""

from pathlib import Path


DATA_FILE = Path(__file__).parent / "data" / "applications.json"


def empty_database():
    """Return the shape that the saved JSON document will use."""
    return {"search_goal": None, "applications": []}
