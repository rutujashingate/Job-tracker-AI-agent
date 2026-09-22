"""Streamlit dashboard for the university job application tracker."""

from collections import Counter
from copy import deepcopy
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard_data import (
    APPLICATION_COLUMNS,
    OUTREACH_COLUMNS,
    records_to_csv,
)
from storage import get_data_file, load_database, save_database
from tracker import (
    find_duplicate_contact,
    get_follow_up_reminders,
    log_application,
    new_outreach_record,
    summarise_pipeline,
    update_status,
)
from validation import SPONSORSHIP_STATUSES, STATUSES, validate_search_goal


st.set_page_config(
    page_title="University Job Tracker",
    page_icon="🎓",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.8rem;
        padding: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_state():
    """Load local data once for this browser session."""
    if "database" not in st.session_state:
        try:
            st.session_state.database = load_database()
        except (OSError, ValueError) as exc:
            st.error(f"The saved tracker could not be loaded: {exc}")
            st.stop()
    st.session_state.setdefault("pending_change", None)


def stage_change(action, proposed_database, change):
    """Place a proposed write in session state for human review."""
    st.session_state.pending_change = {
        "action": action,
        "database": proposed_database,
        "change": change,
    }
    st.rerun()


def render_approval_gate():
    """Render approve and cancel buttons when a write is pending."""
    pending = st.session_state.pending_change
    if pending is None:
        return False

    st.warning("Review this proposed change before anything is saved.")
    st.json({"action": pending["action"], "change": pending["change"]})
    approve_column, cancel_column = st.columns(2)
    if approve_column.button(
        "Approve and save",
        type="primary",
        width="stretch",
    ):
        try:
            path = save_database(pending["database"], approved=True)
        except OSError as exc:
            st.error(f"The change could not be saved: {exc}")
        else:
            st.session_state.database = pending["database"]
            st.session_state.pending_change = None
            st.session_state.flash_message = f"Saved successfully to {path}."
            st.rerun()
    if cancel_column.button("Cancel", width="stretch"):
        st.session_state.pending_change = None
        st.session_state.flash_message = "Change cancelled. Nothing was saved."
        st.rerun()
    return True


def show_flash_message():
    """Show the result of the most recent approval decision once."""
    message = st.session_state.pop("flash_message", None)
    if message:
        st.success(message)


def applications_frame(applications):
    """Build a consistently ordered applications table."""
    return pd.DataFrame(applications, columns=APPLICATION_COLUMNS)


def outreach_frame(outreach_history):
    """Build a consistently ordered outreach-history table."""
    return pd.DataFrame(outreach_history, columns=OUTREACH_COLUMNS)


def dashboard_page(database):
    """Display high-level metrics, charts, and due reminders."""
    st.title("Job search dashboard")
    st.caption("University roles · STEM OPT · Future H-1B sponsorship")
    applications = database["applications"]
    summary = summarise_pipeline(applications)
    reminders = get_follow_up_reminders(applications)
    goal = database.get("search_goal") or {}
    application_goal = goal.get("application_goal", 0)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Applications", len(applications))
    metric_columns[1].metric("Interviewing", summary["interviewing"])
    metric_columns[2].metric("Offers", summary["offer"])
    metric_columns[3].metric("Follow-ups due", len(reminders))

    if application_goal:
        progress = min(len(applications) / application_goal, 1.0)
        st.progress(
            progress,
            text=f"{len(applications)} of {application_goal} applications",
        )

    status_column, sponsorship_column = st.columns(2)
    with status_column:
        st.subheader("Applications by status")
        status_data = pd.DataFrame(
            {
                "Status": [status.title() for status in STATUSES],
                "Applications": [summary[status] for status in STATUSES],
            }
        ).set_index("Status")
        st.bar_chart(status_data)

    with sponsorship_column:
        st.subheader("Sponsorship evidence")
        sponsorship_counts = Counter(
            application.get("sponsorship_status", "unclear")
            for application in applications
        )
        sponsorship_data = pd.DataFrame(
            {
                "Status": [status.replace("_", " ").title() for status in SPONSORSHIP_STATUSES],
                "Applications": [
                    sponsorship_counts.get(status, 0)
                    for status in SPONSORSHIP_STATUSES
                ],
            }
        ).set_index("Status")
        st.bar_chart(sponsorship_data)

    st.subheader("Follow-up reminders")
    if reminders:
        reminder_columns = (
            "company_name",
            "role_title",
            "status",
            "follow_up_date",
        )
        st.dataframe(
            pd.DataFrame(reminders, columns=reminder_columns),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No follow-up reminders are due.")


def applications_page(database):
    """Display, export, add, and update application records."""
    st.title("Applications")
    if render_approval_gate():
        st.stop()

    applications = database["applications"]
    st.dataframe(
        applications_frame(applications),
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "Download applications CSV",
        records_to_csv(applications, APPLICATION_COLUMNS),
        file_name="applications.csv",
        mime="text/csv",
    )

    with st.expander("Log an application", expanded=not applications):
        with st.form("add_application"):
            university = st.text_input("University name")
            role = st.text_input("Role title")
            applied = st.date_input("Date applied", value=date.today())
            status = st.selectbox("Status", STATUSES)
            job_id = st.text_input("Job ID")
            location = st.text_input("Location")
            job_url = st.text_input("Job URL")
            sponsorship = st.selectbox("Sponsorship status", SPONSORSHIP_STATUSES, index=2)
            stem_evidence = st.text_area("STEM OPT evidence")
            h1b_evidence = st.text_area("H-1B evidence")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Review application")

        if submitted:
            proposed = deepcopy(database)
            try:
                application = log_application(
                    proposed["applications"],
                    university,
                    role,
                    applied.isoformat(),
                    status,
                    notes,
                    job_id=job_id,
                    location=location,
                    job_url=job_url,
                    sponsorship_status=sponsorship,
                    stem_opt_evidence=stem_evidence,
                    h1b_evidence=h1b_evidence,
                )
            except ValueError as exc:
                st.error(exc)
            else:
                stage_change("add_application", proposed, {"application": application})

    if applications:
        with st.expander("Update application status"):
            application_map = {application["id"]: application for application in applications}
            with st.form("update_status"):
                application_id = st.selectbox(
                    "Application",
                    tuple(application_map),
                    format_func=lambda value: (
                        f"{application_map[value]['company_name']} — "
                        f"{application_map[value]['role_title']}"
                    ),
                )
                current_status = application_map[application_id]["status"]
                new_status = st.selectbox(
                    "New status",
                    STATUSES,
                    index=STATUSES.index(current_status),
                )
                submitted = st.form_submit_button("Review status change")

            if submitted:
                proposed = deepcopy(database)
                updated = update_status(
                    proposed["applications"], application_id, new_status
                )
                stage_change(
                    "update_application_status",
                    proposed,
                    {
                        "before": application_map[application_id],
                        "after": updated,
                    },
                )


def outreach_page(database):
    """Display, export, and manually record outreach history."""
    st.title("Outreach history")
    st.caption("This table prevents accidental duplicate outreach.")
    if render_approval_gate():
        st.stop()

    outreach_history = database["outreach_history"]
    st.dataframe(
        outreach_frame(outreach_history),
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "Download outreach CSV",
        records_to_csv(outreach_history, OUTREACH_COLUMNS),
        file_name="outreach_history.csv",
        mime="text/csv",
    )

    with st.expander("Record a manually sent email"):
        with st.form("add_outreach"):
            contact_name = st.text_input("Contact name")
            email_address = st.text_input("Contact email")
            university = st.text_input("University")
            role = st.text_input("Role")
            application_id = st.text_input("Application ID (optional)")
            subject = st.text_input("Email subject")
            message = st.text_area("Message sent")
            sent_date = st.date_input("Date sent", value=date.today())
            reply_status = st.selectbox("Reply status", ("no_reply", "replied"))
            submitted = st.form_submit_button("Review outreach record")

        if submitted:
            duplicate = find_duplicate_contact(outreach_history, email_address)
            if duplicate:
                st.error(
                    f"{email_address.strip().lower()} is already in outreach history. "
                    "No duplicate record was created."
                )
            else:
                try:
                    record = new_outreach_record(
                        contact_name,
                        email_address,
                        university,
                        role,
                        subject,
                        message,
                        sent_date.isoformat(),
                        application_id=application_id,
                        follow_up_date=(sent_date + timedelta(days=7)).isoformat(),
                    )
                except ValueError as exc:
                    st.error(exc)
                else:
                    proposed = deepcopy(database)
                    proposed["outreach_history"].append(record)
                    stage_change("add_outreach_record", proposed, {"outreach": record})


def notifications_page(database):
    """Display in-app reminders and explain future email notifications."""
    st.title("Notifications")
    reminders = get_follow_up_reminders(database["applications"])
    if reminders:
        for application in reminders:
            st.warning(
                f"Follow up with {application['company_name']} about "
                f"{application['role_title']} · Due {application['follow_up_date']}"
            )
    else:
        st.success("You have no follow-up reminders due today.")

    st.subheader("Email notifications")
    st.info(
        "Gmail is not connected yet. The next milestone will add a Google OAuth "
        "connection before the dashboard can read or send email."
    )


def settings_page(database):
    """Configure the search goal and show integration status."""
    st.title("Settings")
    if render_approval_gate():
        st.stop()

    goal = database.get("search_goal") or {}
    st.subheader("Search goal")
    with st.form("search_goal"):
        role_type = st.text_input(
            "Target roles",
            value=goal.get(
                "role_type",
                "Junior Software Developer, UI Developer, Frontend Developer, AI Engineer",
            ),
        )
        company_focus = st.text_input(
            "Employer focus",
            value=goal.get("company_focus", "U.S. universities"),
        )
        application_goal = st.number_input(
            "Application goal",
            min_value=1,
            step=1,
            value=int(goal.get("application_goal", 20)),
        )
        stored_deadline = goal.get("deadline")
        default_deadline = (
            date.fromisoformat(stored_deadline)
            if stored_deadline
            else date.today() + timedelta(days=90)
        )
        deadline = st.date_input("Deadline", value=default_deadline)
        weekly_hours = st.number_input(
            "Hours available per week",
            min_value=0.5,
            step=0.5,
            value=float(goal.get("weekly_hours", 10.0)),
        )
        submitted = st.form_submit_button("Review search goal")

    if submitted:
        try:
            validated_goal = validate_search_goal(
                role_type,
                company_focus,
                int(application_goal),
                deadline.isoformat(),
                float(weekly_hours),
            )
        except ValueError as exc:
            st.error(exc)
        else:
            proposed = deepcopy(database)
            proposed["search_goal"] = validated_goal
            stage_change(
                "set_search_goal",
                proposed,
                {"search_goal": validated_goal},
            )

    st.divider()
    st.subheader("Connections")
    connection_columns = st.columns(2)
    with connection_columns[0]:
        st.markdown("**Gmail**")
        st.error("Not connected")
        st.write(
            "Gmail will use Google OAuth. You will choose your account in "
            "Google's sign-in window and will not enter a password in this app."
        )
        st.button("Connect Gmail — coming next", disabled=True)
    with connection_columns[1]:
        st.markdown("**Google Sheets**")
        st.error("Not connected")
        st.write(
            "The local Applications and Outreach History tables can be mapped "
            "to two Google Sheet tabs after OAuth is configured."
        )
        st.button("Connect Google Sheets — coming next", disabled=True)

    st.divider()
    st.subheader("Local storage")
    st.code(str(get_data_file()))
    st.caption("JSON is the source of truth. Each table can be downloaded as CSV.")


initialize_state()
show_flash_message()

with st.sidebar:
    st.title("🎓 Job Tracker")
    page = st.radio(
        "Navigation",
        ("Dashboard", "Applications", "Outreach", "Notifications", "Settings"),
    )
    if st.button("Reload saved data", width="stretch"):
        try:
            st.session_state.database = load_database()
        except (OSError, ValueError) as exc:
            st.error(exc)
        else:
            st.session_state.pending_change = None
            st.rerun()

database = st.session_state.database
if page == "Dashboard":
    dashboard_page(database)
elif page == "Applications":
    applications_page(database)
elif page == "Outreach":
    outreach_page(database)
elif page == "Notifications":
    notifications_page(database)
else:
    settings_page(database)
