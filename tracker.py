"""In-memory helper functions for applications and outreach history."""

from datetime import date, timedelta
from uuid import uuid4

from validation import STATUSES, validate_application, validate_outreach


FOLLOW_UP_DAYS = 7
FOLLOW_UP_STATUSES = ("applied", "interviewing")


def make_session_state(search_goal, applications, outreach_history=None):
    """Build a fresh snapshot from a goal and application list."""
    outreach_history = outreach_history or []
    pipeline = {status: 0 for status in STATUSES}
    for application in applications:
        pipeline[application["status"]] += 1

    return {
        "search_goal": search_goal,
        "deadline": search_goal["deadline"] if search_goal else None,
        "application_count": len(applications),
        "outreach_count": len(outreach_history),
        "current_pipeline": pipeline,
        "pending_action": None,
        "last_action": None,
    }


def new_application(
    company_name,
    role_title,
    date_applied,
    status="applied",
    notes="",
    **job_details,
):
    """Create an application record in memory; this does not save it."""
    fields = validate_application(
        company_name,
        role_title,
        date_applied,
        status,
        notes,
        **job_details,
    )
    return {"id": uuid4().hex, **fields}


def new_outreach_record(
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
    """Create an outreach record in memory; this does not send or save it."""
    fields = validate_outreach(
        contact_name,
        email_address,
        company_name,
        role_title,
        email_subject,
        message_body,
        date_sent,
        application_id,
        reply_status,
        follow_up_date,
    )
    return {"id": uuid4().hex, **fields}


def calculate_follow_up_date(date_applied, days=FOLLOW_UP_DAYS):
    """Return an ISO date a set number of days after the application date."""
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        raise ValueError("Follow-up days must be a positive whole number.")
    try:
        applied_date = date.fromisoformat(date_applied)
    except ValueError as exc:
        raise ValueError("Date applied must use YYYY-MM-DD.") from exc
    if applied_date.isoformat() != date_applied:
        raise ValueError("Date applied must use YYYY-MM-DD.")
    return (applied_date + timedelta(days=days)).isoformat()


def log_application(
    applications,
    company_name,
    role_title,
    date_applied,
    status="applied",
    notes="",
    **job_details,
):
    """Validate and add one application to the in-memory application list."""
    if not job_details.get("follow_up_date"):
        job_details["follow_up_date"] = calculate_follow_up_date(date_applied)
    application = new_application(
        company_name,
        role_title,
        date_applied,
        status,
        notes,
        **job_details,
    )
    applications.append(application)
    return application


def update_status(applications, application_id, new_status):
    """Update one application's status and return the changed record."""
    normalized_status = new_status.strip().lower()
    if normalized_status not in STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")

    for application in applications:
        if application["id"] == application_id:
            application["status"] = normalized_status
            return application
    raise ValueError(f"No application found with ID {application_id}.")


def summarise_pipeline(applications):
    """Count applications in each allowed status."""
    summary = {status: 0 for status in STATUSES}
    for application in applications:
        status = application["status"]
        if status not in summary:
            raise ValueError(f"Application has unsupported status: {status}.")
        summary[status] += 1
    return summary


def get_follow_up_reminders(applications, as_of=None):
    """Return active applications whose follow-up date is due."""
    reminder_date = as_of or date.today()
    reminders = []
    for application in applications:
        follow_up_date = application.get("follow_up_date")
        if not follow_up_date or application["status"] not in FOLLOW_UP_STATUSES:
            continue
        try:
            due_date = date.fromisoformat(follow_up_date)
        except ValueError as exc:
            raise ValueError("Follow-up date must use YYYY-MM-DD.") from exc
        if due_date <= reminder_date:
            reminders.append(application)
    return reminders


def find_duplicate_contact(outreach_history, email_address):
    """Return a previous outreach entry for an email address, if one exists."""
    normalized_email = email_address.strip().lower()
    for outreach in outreach_history:
        if outreach["email_address"].strip().lower() == normalized_email:
            return outreach
    return None
