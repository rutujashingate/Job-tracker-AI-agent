"""CSV export helpers shared by the dashboard's spreadsheet-style views."""

import csv
from io import StringIO


APPLICATION_COLUMNS = (
    "id",
    "company_name",
    "role_title",
    "job_id",
    "location",
    "job_url",
    "date_applied",
    "status",
    "sponsorship_status",
    "stem_opt_evidence",
    "h1b_evidence",
    "source_email_id",
    "source_thread_id",
    "last_status_email_id",
    "last_email_date",
    "follow_up_date",
    "notes",
)

OUTREACH_COLUMNS = (
    "id",
    "contact_name",
    "email_address",
    "company_name",
    "role_title",
    "application_id",
    "email_subject",
    "message_body",
    "date_sent",
    "reply_status",
    "follow_up_date",
)

JOB_LEAD_COLUMNS = (
    "id",
    "university",
    "role_title",
    "job_family",
    "location",
    "job_url",
    "date_found",
    "date_posted",
    "posted_at",
    "sponsorship_status",
    "stem_opt_evidence",
    "h1b_evidence",
    "source",
    "status",
    "notes",
)


def records_to_csv(records, columns):
    """Return records as CSV text with a stable column order."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()
