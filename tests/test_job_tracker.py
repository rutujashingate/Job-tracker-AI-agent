"""Behavior tests for validation, tracking, approvals, and persistence."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dashboard_data import APPLICATION_COLUMNS, records_to_csv
from email_importer import build_email_import_plan, classify_job_email
from gmail_service import build_job_email_query
from job_discovery import (
    build_job_discovery_plan,
    extract_job_content,
    filter_jobs,
    is_target_role,
    workday_posted_at,
)
from main import commit_proposed_change, request_save_approval
from storage import empty_database, load_database, save_database
from tracker import (
    get_follow_up_reminders,
    log_application,
    summarise_pipeline,
    update_status,
)
from validation import validate_search_goal


class TrackerWorkflowTests(unittest.TestCase):
    def test_normal_application_workflow(self):
        applications = []
        applied_date = date.today() - timedelta(days=8)

        application = log_application(
            applications,
            "Example University",
            "Junior Software Developer",
            applied_date.isoformat(),
        )

        self.assertEqual(len(applications), 1)
        self.assertEqual(
            application["follow_up_date"],
            (applied_date + timedelta(days=7)).isoformat(),
        )
        self.assertEqual(summarise_pipeline(applications)["applied"], 1)
        self.assertEqual(get_follow_up_reminders(applications), [application])

        update_status(applications, application["id"], "interviewing")
        summary = summarise_pipeline(applications)
        self.assertEqual(summary["applied"], 0)
        self.assertEqual(summary["interviewing"], 1)

    def test_empty_company_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Company name cannot be empty"):
            log_application([], "   ", "Developer", date.today().isoformat())

    def test_invalid_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Status must be one of"):
            log_application(
                [],
                "Example University",
                "Developer",
                date.today().isoformat(),
                status="waiting",
            )

    def test_past_search_deadline_is_rejected(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "Deadline cannot be in the past"):
            validate_search_goal(
                "Junior Developer",
                "U.S. universities",
                20,
                yesterday,
                10,
            )


class ApprovalTests(unittest.TestCase):
    def test_vague_response_is_reprompted_before_approval(self):
        responses = iter(["maybe", "save"])
        prompts = []

        def answer(prompt):
            prompts.append(prompt)
            return next(responses)

        with redirect_stdout(StringIO()) as output:
            approved = request_save_approval(
                "add_application",
                {"company_name": "Example University"},
                input_func=answer,
            )

        self.assertTrue(approved)
        self.assertEqual(len(prompts), 2)
        self.assertIn("Please enter a clear decision", output.getvalue())

    def test_cancelled_change_does_not_mutate_or_write(self):
        database = empty_database()
        proposed = deepcopy(database)
        proposed["search_goal"] = {"role_type": "Junior Developer"}

        with TemporaryDirectory() as directory:
            path = Path(directory) / "applications.json"
            with patch.dict(os.environ, {"JOB_TRACKER_DATA_FILE": str(path)}):
                with redirect_stdout(StringIO()):
                    saved = commit_proposed_change(
                        database,
                        proposed,
                        "set_search_goal",
                        proposed["search_goal"],
                        input_func=lambda prompt: "no",
                    )

            self.assertFalse(saved)
            self.assertEqual(database, empty_database())
            self.assertFalse(path.exists())

    def test_approved_change_is_saved_and_loaded(self):
        database = empty_database()
        proposed = deepcopy(database)
        proposed["search_goal"] = {"role_type": "Junior Developer"}

        with TemporaryDirectory() as directory:
            path = Path(directory) / "applications.json"
            with patch.dict(os.environ, {"JOB_TRACKER_DATA_FILE": str(path)}):
                with redirect_stdout(StringIO()):
                    saved = commit_proposed_change(
                        database,
                        proposed,
                        "set_search_goal",
                        proposed["search_goal"],
                        input_func=lambda prompt: "confirm",
                    )
                loaded = load_database()

            self.assertTrue(saved)
            self.assertEqual(database, proposed)
            self.assertEqual(loaded, proposed)


class StorageTests(unittest.TestCase):
    def test_storage_refuses_a_write_without_approval(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "applications.json"
            with self.assertRaises(PermissionError):
                save_database(empty_database(), path=path)
            self.assertFalse(path.exists())

    def test_invalid_json_is_not_silently_replaced(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "applications.json"
            path.write_text("not valid json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                load_database(path)


class CsvExportTests(unittest.TestCase):
    def test_application_records_export_with_stable_headers(self):
        csv_text = records_to_csv(
            [
                {
                    "id": "application-1",
                    "company_name": "Example University",
                    "role_title": "Junior Developer",
                    "status": "applied",
                }
            ],
            APPLICATION_COLUMNS,
        )

        lines = csv_text.splitlines()
        self.assertEqual(lines[0].split(","), list(APPLICATION_COLUMNS))
        self.assertIn("Example University", lines[1])
        self.assertIn("Junior Developer", lines[1])


class GmailImportTests(unittest.TestCase):
    def make_message(self, **overrides):
        message = {
            "message_id": "message-1",
            "thread_id": "thread-1",
            "subject": (
                "Application received for Junior Software Developer "
                "at Example University"
            ),
            "sender_name": "Example University Careers",
            "sender_address": "careers@example.edu",
            "received_at": "2025-06-02T12:00:00+00:00",
            "received_date": "2025-06-02",
            "snippet": "Thank you for applying.",
            "body": "We received your application for this position.",
        }
        message.update(overrides)
        return message

    def test_hackathon_email_is_excluded(self):
        message = self.make_message(
            subject="Hackathon application received",
            body="Thank you for applying to our hackathon.",
        )
        self.assertIsNone(classify_job_email(message))

    def test_confirmation_and_rejection_update_one_application(self):
        confirmation = classify_job_email(self.make_message())
        rejection = classify_job_email(
            self.make_message(
                message_id="message-2",
                subject=(
                    "Update on your application for Junior Software Developer "
                    "at Example University"
                ),
                received_at="2025-06-10T12:00:00+00:00",
                received_date="2025-06-10",
                snippet="We are not moving forward.",
                body=(
                    "We have decided not to move forward with your application "
                    "for this position."
                ),
            )
        )

        plan = build_email_import_plan(
            empty_database(),
            [rejection, confirmation],
        )

        self.assertEqual(len(plan["changes"]), 2)
        self.assertEqual(len(plan["database"]["applications"]), 1)
        application = plan["database"]["applications"][0]
        self.assertEqual(application["company_name"], "Example University")
        self.assertEqual(application["role_title"], "Junior Software Developer")
        self.assertEqual(application["status"], "rejected")
        self.assertEqual(application["last_status_email_id"], "message-2")
        self.assertEqual(plan["unmatched"], [])

    def test_gmail_query_starts_in_june_2025_and_excludes_hackathons(self):
        query = build_job_email_query(date(2025, 6, 1))
        self.assertIn("after:2025/06/01", query)
        self.assertIn("-hackathon", query)


class JobDiscoveryTests(unittest.TestCase):
    def make_job(self, url, posted_at, **overrides):
        job = {
            "id": url.rsplit("/", 1)[-1],
            "university": "Example University",
            "role_title": "Software Engineer",
            "job_family": "Software Development",
            "location": "Phoenix, AZ",
            "job_url": url,
            "date_found": posted_at.date().isoformat(),
            "date_posted": posted_at.date().isoformat(),
            "posted_at": posted_at.isoformat(),
            "sponsorship_status": "unclear",
            "source": "Official job board",
            "status": "new",
        }
        job.update(overrides)
        return job

    def test_target_role_matching_excludes_senior_roles(self):
        self.assertTrue(is_target_role("Junior Software Developer"))
        self.assertTrue(is_target_role("Associate AI Engineer"))
        self.assertTrue(is_target_role("Front-end Developer"))
        self.assertFalse(is_target_role("Senior Software Engineer"))
        self.assertFalse(is_target_role("Web Developer Supervisor"))
        self.assertFalse(is_target_role("Financial Analyst"))

    def test_last_24_hours_filter(self):
        now = datetime.now(timezone.utc)
        recent = self.make_job("https://example.edu/recent", now - timedelta(hours=2))
        old = self.make_job("https://example.edu/old", now - timedelta(days=3))

        self.assertEqual(filter_jobs([recent, old], hours=24), [recent])

    def test_discovery_plan_deduplicates_original_posting_urls(self):
        now = datetime.now(timezone.utc)
        existing = self.make_job("https://example.edu/job/1", now)
        new = self.make_job("https://example.edu/job/2", now)
        database = empty_database()
        database["job_leads"] = [existing]

        plan = build_job_discovery_plan(database, [existing, new], scanned_at=now)

        self.assertEqual(plan["additions"], [new])
        self.assertEqual(len(plan["database"]["job_leads"]), 2)
        self.assertEqual(
            plan["database"]["job_discovery"]["last_scan_at"],
            now.isoformat(),
        )

    def test_workday_relative_posting_date(self):
        now = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
        self.assertEqual(workday_posted_at("Posted Today", now), now)
        self.assertEqual(
            workday_posted_at("Posted 3 Days Ago", now),
            now - timedelta(days=3),
        )

    def test_job_card_content_is_extracted_from_original_description(self):
        original_description = """
        <h2>About the Role</h2>
        <p>Build accessible interfaces for university students.</p>
        <h2>Minimum Qualifications</h2>
        <ul>
          <li>One year of JavaScript experience.</li>
          <li>Experience with accessible HTML.</li>
        </ul>
        <h2>Preferred Qualifications</h2>
        <p>Visa sponsorship is not available for this position.</p>
        """

        content = extract_job_content(original_description)

        self.assertEqual(
            content["summary"],
            "Build accessible interfaces for university students.",
        )
        self.assertEqual(
            content["requirements"],
            [
                "One year of JavaScript experience.",
                "Experience with accessible HTML.",
            ],
        )
        self.assertEqual(content["sponsorship_status"], "not_available")
        self.assertEqual(
            content["h1b_evidence"],
            "Visa sponsorship is not available for this position.",
        )


if __name__ == "__main__":
    unittest.main()
