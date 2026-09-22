"""Classify Gmail messages and prepare approval-gated tracker changes."""

from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parseaddr
import re

from tracker import log_application, update_status


EXCLUDED_TERMS = (
    "hackathon",
    "coding competition",
    "career fair",
    "webinar",
    "workshop",
)

STATUS_SIGNALS = {
    "offer": (
        "offer of employment",
        "pleased to offer",
        "job offer",
        "offer letter",
    ),
    "interviewing": (
        "invite you to interview",
        "invitation to interview",
        "schedule an interview",
        "interview availability",
        "next round of interviews",
    ),
    "rejected": (
        "not moving forward",
        "will not be moving forward",
        "not selected",
        "other candidates",
        "regret to inform",
        "position has been filled",
        "unable to offer you",
    ),
    "withdrawn": (
        "application has been withdrawn",
        "you withdrew your application",
    ),
}

APPLICATION_SIGNALS = (
    "thank you for applying",
    "application received",
    "received your application",
    "your application has been submitted",
    "successfully submitted your application",
    "application confirmation",
)

JOB_CONTEXT_TERMS = (
    "application",
    "candidate",
    "position",
    "role",
    "employment",
    "job",
)

DETAIL_PATTERNS = (
    re.compile(
        r"(?:application received for|application for|applied for)\s+(.+?)\s+at\s+(.+?)(?:\s*[|–—-]\s*|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:thank you for applying to|thank you for applying for)\s+(?:the\s+)?(.+?)\s+(?:position\s+)?at\s+(.+?)(?:\s*[|–—-]\s*|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:update on|regarding) your application for\s+(.+?)\s+at\s+(.+?)(?:\s*[|–—-]\s*|$)",
        re.IGNORECASE,
    ),
)


def _normalized(value):
    """Normalize text for conservative record matching."""
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _fallback_company(message):
    """Derive a reviewable employer label from the sender display name."""
    sender_name = message.get("sender_name", "").strip()
    if not sender_name:
        sender_name = parseaddr(message.get("sender_address", ""))[0]
    cleaned = re.sub(
        r"\b(careers?|recruiting|talent|acquisition|team|notifications?)\b",
        "",
        sender_name,
        flags=re.IGNORECASE,
    )
    cleaned = " ".join(cleaned.split()).strip(" -|–—")
    return cleaned or "Needs employer review"


def extract_role_and_company(message):
    """Extract role and employer from common application-email subjects."""
    subject = re.sub(r"^(re|fwd):\s*", "", message.get("subject", ""), flags=re.I)
    for pattern in DETAIL_PATTERNS:
        match = pattern.search(subject)
        if match:
            return match.group(1).strip(), match.group(2).strip(), False
    role = re.sub(
        r"^(application status|application update|application confirmation|thank you for applying)\s*[:\-–—]?\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip()
    return role or "Needs role review", _fallback_company(message), True


def classify_job_email(message):
    """Return a job-application detection or None for unrelated email."""
    searchable = "\n".join(
        (
            message.get("subject", ""),
            message.get("snippet", ""),
            message.get("body", ""),
        )
    ).lower()
    if any(term in searchable for term in EXCLUDED_TERMS):
        return None
    if not any(term in searchable for term in JOB_CONTEXT_TERMS):
        return None

    status = None
    for possible_status, signals in STATUS_SIGNALS.items():
        if any(signal in searchable for signal in signals):
            status = possible_status
            break
    if status is None and any(signal in searchable for signal in APPLICATION_SIGNALS):
        status = "applied"
    if status is None:
        return None

    role_title, company_name, needs_review = extract_role_and_company(message)
    detection = {key: value for key, value in message.items() if key != "body"}
    detection.update(
        {
            "detected_status": status,
            "role_title": role_title,
            "company_name": company_name,
            "needs_review": needs_review,
        }
    )
    return detection


def classify_messages(messages):
    """Classify a collection and discard unrelated messages."""
    detections = []
    for message in messages:
        detection = classify_job_email(message)
        if detection:
            detections.append(detection)
    return detections


def _match_application(applications, detection):
    """Conservatively match a status email to one existing application."""
    thread_id = detection.get("thread_id")
    if thread_id:
        thread_matches = [
            application
            for application in applications
            if application.get("source_thread_id") == thread_id
        ]
        if len(thread_matches) == 1:
            return thread_matches[0]

    company = _normalized(detection.get("company_name", ""))
    role = _normalized(detection.get("role_title", ""))
    if not company or not role or detection.get("needs_review"):
        return None
    matches = [
        application
        for application in applications
        if _normalized(application.get("company_name", "")) == company
        and _normalized(application.get("role_title", "")) == role
    ]
    return matches[0] if len(matches) == 1 else None


def build_email_import_plan(database, detections):
    """Create a proposed database plus reviewable additions and updates."""
    proposed = deepcopy(database)
    applications = proposed["applications"]
    sync = proposed.setdefault(
        "email_sync",
        {
            "start_date": "2025-06-01",
            "last_scan_at": None,
            "processed_message_ids": [],
        },
    )
    processed = set(sync.get("processed_message_ids", []))
    changes = []
    unmatched = []

    chronological_detections = sorted(
        detections,
        key=lambda detection: detection.get("received_at", ""),
    )
    for detection in chronological_detections:
        message_id = detection["message_id"]
        if message_id in processed:
            continue

        status = detection["detected_status"]
        if status == "applied":
            if detection.get("needs_review"):
                unmatched.append(detection)
                continue
            application = log_application(
                applications,
                detection["company_name"],
                detection["role_title"],
                detection["received_date"],
                notes=f"Imported from Gmail: {detection['subject']}",
                source_email_id=message_id,
                source_thread_id=detection.get("thread_id", ""),
                last_email_date=detection["received_date"],
            )
            changes.append({"action": "add_application", "after": application})
            processed.add(message_id)
            continue

        matched = _match_application(applications, detection)
        if matched is None:
            unmatched.append(detection)
            continue
        before = deepcopy(matched)
        updated = update_status(applications, matched["id"], status)
        updated["last_status_email_id"] = message_id
        updated["last_email_date"] = detection["received_date"]
        changes.append(
            {
                "action": "update_application_status",
                "before": before,
                "after": deepcopy(updated),
            }
        )
        processed.add(message_id)

    sync["processed_message_ids"] = sorted(processed)
    sync["last_scan_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "database": proposed,
        "changes": changes,
        "unmatched": unmatched,
    }
