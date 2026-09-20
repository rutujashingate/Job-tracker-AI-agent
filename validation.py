"""Check user input before it becomes part of the tracker."""

from datetime import date
from math import isfinite


STATUSES = ("applied", "interviewing", "offer", "rejected", "withdrawn")


def _required_text(value, field_name):
    """Return trimmed text, or explain which required field is missing."""
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be empty.")
    return text


def _iso_date(value, field_name):
    """Parse a date written exactly as YYYY-MM-DD."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must use YYYY-MM-DD.")
    return parsed


def validate_search_goal(role_type, company_focus, application_goal, deadline, weekly_hours):
    """Validate and normalize the five required goal inputs."""
    role_type = _required_text(role_type, "Target role")
    company_focus = _required_text(company_focus, "Company size or industry")
    if isinstance(application_goal, bool) or not isinstance(application_goal, int):
        raise ValueError("Application goal must be a whole number.")
    if application_goal <= 0:
        raise ValueError("Application goal must be greater than zero.")
    deadline_date = _iso_date(deadline, "Deadline")
    if deadline_date < date.today():
        raise ValueError("Deadline cannot be in the past.")
    if isinstance(weekly_hours, bool) or not isinstance(weekly_hours, (int, float)):
        raise ValueError("Weekly availability must be a number of hours.")
    if not isfinite(weekly_hours) or weekly_hours <= 0:
        raise ValueError("Weekly availability must be greater than zero.")

    return {
        "role_type": role_type,
        "company_focus": company_focus,
        "application_goal": application_goal,
        "deadline": deadline,
        "weekly_hours": weekly_hours,
    }


def validate_application(company_name, role_title, date_applied, status, notes):
    """Validate and normalize an application before assigning it an ID."""
    company_name = _required_text(company_name, "Company name")
    role_title = _required_text(role_title, "Role title")
    applied_date = _iso_date(date_applied, "Date applied")
    if applied_date > date.today():
        raise ValueError("Date applied cannot be in the future.")
    normalized_status = status.strip().lower()
    if normalized_status not in STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")

    return {
        "company_name": company_name,
        "role_title": role_title,
        "date_applied": date_applied,
        "status": normalized_status,
        "notes": notes.strip(),
    }
