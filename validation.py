"""Check user input before it becomes part of the tracker."""

from datetime import date
from math import isfinite


STATUSES = ("applied", "interviewing", "offer", "rejected", "withdrawn")
SPONSORSHIP_STATUSES = ("confirmed", "not_available", "unclear")
REPLY_STATUSES = ("no_reply", "replied")
VISA_NEEDS = ("stem_opt", "h1b")


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


def validate_search_goal(
    role_type,
    company_focus,
    application_goal,
    deadline,
    weekly_hours,
    sponsorship_needs=None,
):
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
    sponsorship_needs = sponsorship_needs or list(VISA_NEEDS)
    normalized_needs = [need.strip().lower() for need in sponsorship_needs]
    invalid_needs = [need for need in normalized_needs if need not in VISA_NEEDS]
    if invalid_needs:
        raise ValueError(f"Sponsorship needs must be one of: {', '.join(VISA_NEEDS)}.")

    return {
        "role_type": role_type,
        "company_focus": company_focus,
        "application_goal": application_goal,
        "deadline": deadline,
        "weekly_hours": weekly_hours,
        "sponsorship_needs": normalized_needs,
    }


def validate_application(
    company_name,
    role_title,
    date_applied,
    status,
    notes,
    job_id="",
    location="",
    job_url="",
    sponsorship_status="unclear",
    stem_opt_evidence="",
    h1b_evidence="",
    source_email_id="",
    last_email_date="",
    follow_up_date="",
):
    """Validate and normalize an application before assigning it an ID."""
    company_name = _required_text(company_name, "Company name")
    role_title = _required_text(role_title, "Role title")
    applied_date = _iso_date(date_applied, "Date applied")
    if applied_date > date.today():
        raise ValueError("Date applied cannot be in the future.")
    normalized_status = status.strip().lower()
    if normalized_status not in STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")
    normalized_sponsorship = sponsorship_status.strip().lower()
    if normalized_sponsorship not in SPONSORSHIP_STATUSES:
        allowed = ", ".join(SPONSORSHIP_STATUSES)
        raise ValueError(f"Sponsorship status must be one of: {allowed}.")
    if last_email_date:
        _iso_date(last_email_date, "Last email date")
    if follow_up_date:
        _iso_date(follow_up_date, "Follow-up date")

    return {
        "company_name": company_name,
        "role_title": role_title,
        "job_id": job_id.strip(),
        "location": location.strip(),
        "job_url": job_url.strip(),
        "date_applied": date_applied,
        "status": normalized_status,
        "sponsorship_status": normalized_sponsorship,
        "stem_opt_evidence": stem_opt_evidence.strip(),
        "h1b_evidence": h1b_evidence.strip(),
        "source_email_id": source_email_id.strip(),
        "last_email_date": last_email_date,
        "follow_up_date": follow_up_date,
        "notes": notes.strip(),
    }


def validate_outreach(
    contact_name,
    email_address,
    company_name,
    role_title,
    email_subject,
    message_body,
    date_sent,
    application_id="",
    reply_status="no_reply",
    follow_up_date="",
):
    """Validate and normalize a hiring-contact outreach record."""
    contact_name = _required_text(contact_name, "Contact name")
    company_name = _required_text(company_name, "Company name")
    role_title = _required_text(role_title, "Role title")
    email_subject = _required_text(email_subject, "Email subject")
    message_body = _required_text(message_body, "Message body")
    normalized_email = email_address.strip().lower()
    if (
        not normalized_email
        or normalized_email.count("@") != 1
        or "." not in normalized_email.split("@", 1)[1]
    ):
        raise ValueError("Email address must be valid.")
    sent_date = _iso_date(date_sent, "Date sent")
    if sent_date > date.today():
        raise ValueError("Date sent cannot be in the future.")
    normalized_reply = reply_status.strip().lower()
    if normalized_reply not in REPLY_STATUSES:
        raise ValueError(f"Reply status must be one of: {', '.join(REPLY_STATUSES)}.")
    if follow_up_date:
        _iso_date(follow_up_date, "Follow-up date")

    return {
        "contact_name": contact_name,
        "email_address": normalized_email,
        "company_name": company_name,
        "role_title": role_title,
        "application_id": application_id.strip(),
        "email_subject": email_subject,
        "message_body": message_body,
        "date_sent": date_sent,
        "reply_status": normalized_reply,
        "follow_up_date": follow_up_date,
    }
