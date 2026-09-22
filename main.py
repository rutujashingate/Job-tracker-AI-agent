"""Command-line interface with approval-gated local persistence."""

from copy import deepcopy
from datetime import date
import json

from storage import load_database, save_database
from tracker import (
    get_follow_up_reminders,
    log_application,
    make_session_state,
    summarise_pipeline,
    update_status,
)
from validation import STATUSES, validate_search_goal


APPROVAL_WORDS = ("yes", "confirm", "save")
CANCEL_WORDS = ("no", "cancel")


def ask_for_goal():
    """Ask for all goal fields until they form a valid search goal."""
    while True:
        print("\nTell me about your job search goal.")
        role_type = input("Target role type: ")
        company_focus = input("Target company size or industry: ")
        application_goal_text = input("Number of applications to submit: ")
        deadline = input("Deadline (YYYY-MM-DD): ")
        weekly_hours_text = input("Hours available per week: ")

        try:
            application_goal = int(application_goal_text)
            weekly_hours = float(weekly_hours_text)
            return validate_search_goal(
                role_type, company_focus, application_goal, deadline, weekly_hours
            )
        except ValueError as exc:
            print(f"Please try again: {exc}")


def request_save_approval(action, change, input_func=input):
    """Preview one proposed change and wait for a clear decision."""
    print("\nProposed change:")
    print(json.dumps({"action": action, "change": change}, indent=2))
    while True:
        response = input_func(
            "Type yes, confirm, or save to approve; no or cancel to reject: "
        ).strip().lower()
        if response in APPROVAL_WORDS:
            return True
        if response in CANCEL_WORDS:
            return False
        print("Please enter a clear decision: yes, confirm, save, no, or cancel.")


def commit_proposed_change(database, proposed_database, action, change):
    """Save a proposed database and adopt it only after user approval."""
    if not request_save_approval(action, change):
        print("Change cancelled. Nothing was saved.")
        return False

    file_path = save_database(proposed_database, approved=True)
    database.clear()
    database.update(proposed_database)
    print(f"Saved successfully to {file_path}.")
    return True


def collect_and_save_goal(database):
    """Collect the initial goal and offer to save it."""
    search_goal = ask_for_goal()
    proposed_database = deepcopy(database)
    proposed_database["search_goal"] = search_goal
    commit_proposed_change(
        database,
        proposed_database,
        "set_search_goal",
        {"search_goal": search_goal},
    )
    return search_goal


def display_goal(search_goal):
    """Show the validated goal at the beginning of a session."""
    print("\nGoal captured for this session:")
    print(f"  Target role: {search_goal['role_type']}")
    print(f"  Company focus: {search_goal['company_focus']}")
    print(f"  Application goal: {search_goal['application_goal']}")
    print(f"  Deadline: {search_goal['deadline']}")
    print(f"  Weekly hours: {search_goal['weekly_hours']}")
    sponsorship_needs = search_goal.get("sponsorship_needs", ["stem_opt", "h1b"])
    print(f"  Sponsorship needs: {', '.join(sponsorship_needs)}")


def display_pipeline(applications):
    """Print the number of applications in every pipeline status."""
    summary = summarise_pipeline(applications)
    print("\nCurrent pipeline:")
    for status in STATUSES:
        print(f"  {status.title()}: {summary[status]}")
    print(f"  Total: {sum(summary.values())}")


def display_applications(applications):
    """Print a numbered list and return whether any records were shown."""
    if not applications:
        print("\nNo applications are tracked yet.")
        return False

    print("\nApplications:")
    for number, application in enumerate(applications, start=1):
        print(
            f"  [{number}] {application['company_name']} — "
            f"{application['role_title']} ({application['status']})"
        )
        print(
            f"      Applied: {application['date_applied']} | "
            f"Follow up: {application.get('follow_up_date') or 'not set'}"
        )
    return True


def prompt_to_log_application(database):
    """Collect an application and save it only after approval."""
    print("\nLog a job application")
    company_name = input("University name: ")
    role_title = input("Role title: ")
    date_applied = input(f"Date applied [{date.today().isoformat()}]: ").strip()
    date_applied = date_applied or date.today().isoformat()
    status = input("Status [applied]: ").strip() or "applied"
    job_id = input("Job ID (optional): ")
    location = input("Location (optional): ")
    job_url = input("Job URL (optional): ")
    sponsorship_status = input(
        "Sponsorship status [confirmed/not_available/unclear]: "
    ).strip()
    sponsorship_status = sponsorship_status or "unclear"
    stem_opt_evidence = input("STEM OPT evidence (optional): ")
    h1b_evidence = input("H-1B evidence (optional): ")
    notes = input("Notes (optional): ")

    proposed_database = deepcopy(database)
    try:
        application = log_application(
            proposed_database["applications"],
            company_name,
            role_title,
            date_applied,
            status,
            notes,
            job_id=job_id,
            location=location,
            job_url=job_url,
            sponsorship_status=sponsorship_status,
            stem_opt_evidence=stem_opt_evidence,
            h1b_evidence=h1b_evidence,
        )
    except ValueError as exc:
        print(f"Application was not added: {exc}")
        return None

    saved = commit_proposed_change(
        database,
        proposed_database,
        "add_application",
        {"application": application},
    )
    return application if saved else None


def choose_application(applications):
    """Ask the user to choose one application by its displayed number."""
    if not display_applications(applications):
        return None

    selection = input("Choose an application number: ").strip()
    try:
        index = int(selection) - 1
    except ValueError:
        print("Please enter one of the displayed numbers.")
        return None
    if index < 0 or index >= len(applications):
        print("Please enter one of the displayed numbers.")
        return None
    return applications[index]


def prompt_to_update_status(database):
    """Propose a status change and save it only after approval."""
    application = choose_application(database["applications"])
    if application is None:
        return None

    print(f"Allowed statuses: {', '.join(STATUSES)}")
    new_status = input("New status: ")
    proposed_database = deepcopy(database)
    try:
        updated = update_status(
            proposed_database["applications"], application["id"], new_status
        )
    except ValueError as exc:
        print(f"Status was not updated: {exc}")
        return None

    saved = commit_proposed_change(
        database,
        proposed_database,
        "update_application_status",
        {
            "before": application,
            "after": updated,
        },
    )
    return updated if saved else None


def display_reminders(applications):
    """Show applications whose follow-up date is today or earlier."""
    reminders = get_follow_up_reminders(applications)
    if not reminders:
        print("\nNo follow-up reminders are due.")
        return

    print("\nFollow-up reminders:")
    for application in reminders:
        print(
            f"  {application['follow_up_date']}: "
            f"{application['company_name']} — {application['role_title']}"
        )


def display_menu():
    """Print the available tracker actions."""
    print("\nChoose an action:")
    print("  1. Log an application")
    print("  2. Update an application status")
    print("  3. View applications")
    print("  4. View follow-up reminders")
    print("  5. Exit")


def main():
    """Load saved data and run the approval-gated application loop."""
    print("University Job Application Tracker")
    try:
        database = load_database()
    except (OSError, ValueError) as exc:
        print(f"The saved tracker could not be loaded: {exc}")
        return

    search_goal = database["search_goal"]
    if search_goal is None:
        search_goal = collect_and_save_goal(database)
    else:
        print("Loaded the existing tracker from local JSON.")

    session_state = make_session_state(
        search_goal,
        database["applications"],
        database["outreach_history"],
    )

    display_goal(search_goal)
    display_pipeline(database["applications"])
    print("Every change requires approval before it is saved.")

    while True:
        display_menu()
        choice = input("Enter 1-5: ").strip()

        if choice == "1":
            result = prompt_to_log_application(database)
            action = "logged application" if result else "log application failed"
        elif choice == "2":
            result = prompt_to_update_status(database)
            action = "updated status" if result else "status update failed"
        elif choice == "3":
            display_applications(database["applications"])
            action = "viewed applications"
        elif choice == "4":
            display_reminders(database["applications"])
            action = "viewed reminders"
        elif choice == "5":
            print("Session ended. Your approved changes are saved.")
            break
        else:
            print("Please choose a number from 1 to 5.")
            continue

        session_state = make_session_state(
            search_goal,
            database["applications"],
            database["outreach_history"],
        )
        session_state["last_action"] = action
        display_pipeline(database["applications"])


if __name__ == "__main__":
    main()
