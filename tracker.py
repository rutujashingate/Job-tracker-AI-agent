"""The in-memory model for a search session and its applications."""

from uuid import uuid4

from validation import STATUSES, validate_application, validate_outreach


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
