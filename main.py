"""Command-line interface for the in-memory job application tracker."""

from datetime import date

from tracker import (
    get_follow_up_reminders,
    log_application,
    make_session_state,
    summarise_pipeline,
    update_status,
)
from validation import STATUSES, validate_search_goal


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


def display_goal(search_goal):
    """Show the validated goal at the beginning of a session."""
    print("\nGoal captured for this session:")
    print(f"  Target role: {search_goal['role_type']}")
    print(f"  Company focus: {search_goal['company_focus']}")
    print(f"  Application goal: {search_goal['application_goal']}")
    print(f"  Deadline: {search_goal['deadline']}")
    print(f"  Weekly hours: {search_goal['weekly_hours']}")
    print(f"  Sponsorship needs: {', '.join(search_goal['sponsorship_needs'])}")


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
            f"Follow up: {application['follow_up_date']}"
        )
    return True


def prompt_to_log_application(applications):
    """Collect, validate, and add one application to the current session."""
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

    try:
        application = log_application(
            applications,
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

    print(
        f"Application added in memory. Follow-up date: "
        f"{application['follow_up_date']}"
    )
    return application


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


def prompt_to_update_status(applications):
    """Choose an application and assign it a validated status."""
    application = choose_application(applications)
    if application is None:
        return None

    print(f"Allowed statuses: {', '.join(STATUSES)}")
    new_status = input("New status: ")
    try:
        updated = update_status(applications, application["id"], new_status)
    except ValueError as exc:
        print(f"Status was not updated: {exc}")
        return None

    print(f"Status updated to {updated['status']} in memory.")
    return updated


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
    """Print the available Step 3 actions."""
    print("\nChoose an action:")
    print("  1. Log an application")
    print("  2. Update an application status")
    print("  3. View applications")
    print("  4. View follow-up reminders")
    print("  5. Exit")


def main():
    """Run the interactive Step 3 application loop."""
    print("University Job Application Tracker")
    search_goal = ask_for_goal()
    applications = []
    outreach_history = []
    session_state = make_session_state(
        search_goal, applications, outreach_history
    )

    display_goal(search_goal)
    display_pipeline(applications)
    print("Changes remain in memory during Step 3 and are not saved yet.")

    while True:
        display_menu()
        choice = input("Enter 1-5: ").strip()

        if choice == "1":
            result = prompt_to_log_application(applications)
            action = "logged application" if result else "log application failed"
        elif choice == "2":
            result = prompt_to_update_status(applications)
            action = "updated status" if result else "status update failed"
        elif choice == "3":
            display_applications(applications)
            action = "viewed applications"
        elif choice == "4":
            display_reminders(applications)
            action = "viewed reminders"
        elif choice == "5":
            print("Session ended. Step 4 will add approved JSON saving.")
            break
        else:
            print("Please choose a number from 1 to 5.")
            continue

        session_state = make_session_state(
            search_goal, applications, outreach_history
        )
        session_state["last_action"] = action
        display_pipeline(applications)


if __name__ == "__main__":
    main()
