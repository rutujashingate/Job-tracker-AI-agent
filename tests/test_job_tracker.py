"""Behavior tests for validation, tracking, approvals, and persistence."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date, timedelta
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dashboard_data import APPLICATION_COLUMNS, records_to_csv
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


if __name__ == "__main__":
    unittest.main()
