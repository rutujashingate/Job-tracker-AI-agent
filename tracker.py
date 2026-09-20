"""The in-memory model for a search session and its applications."""

from uuid import uuid4

from validation import STATUSES, validate_application


def make_session_state(search_goal, applications):
    """Build a fresh snapshot from a goal and application list."""
    pipeline = {status: 0 for status in STATUSES}
    for application in applications:
        pipeline[application["status"]] += 1

    return {
        "search_goal": search_goal,
        "deadline": search_goal["deadline"] if search_goal else None,
        "application_count": len(applications),
        "current_pipeline": pipeline,
        "last_action": None,
    }


def new_application(company_name, role_title, date_applied, status="applied", notes=""):
    """Create an application record in memory; this does not save it."""
    fields = validate_application(company_name, role_title, date_applied, status, notes)
    return {"id": uuid4().hex, **fields}
