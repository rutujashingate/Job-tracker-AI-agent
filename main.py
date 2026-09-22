"""First milestone: collect a search goal and show session state in memory."""

from tracker import make_session_state
from validation import validate_search_goal


def ask_for_goal():
    """Ask for all five goal fields until they form a valid goal."""
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


def main():
    print("Job Application Tracker")
    search_goal = ask_for_goal()
    session_state = make_session_state(search_goal, [])

    print("\nGoal captured for this session:")
    print(f"  Target role: {search_goal['role_type']}")
    print(f"  Company focus: {search_goal['company_focus']}")
    print(f"  Application goal: {search_goal['application_goal']}")
    print(f"  Deadline: {session_state['deadline']}")
    print(f"  Weekly hours: {search_goal['weekly_hours']}")
    print(f"  Sponsorship needs: {', '.join(search_goal['sponsorship_needs'])}")
    print(f"  Applications tracked: {session_state['application_count']}")
    print(f"  Hiring contacts emailed: {session_state['outreach_count']}")
    print("Nothing has been saved yet. Approval and saving come in a later step.")


if __name__ == "__main__":
    main()
