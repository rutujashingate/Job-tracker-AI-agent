"""Streamlit dashboard for the university job application tracker."""

from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
import json

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import (
    APPLICATION_COLUMNS,
    JOB_LEAD_COLUMNS,
    OUTREACH_COLUMNS,
    records_to_csv,
)
from email_importer import build_email_import_plan, classify_messages
from gmail_service import (
    build_gmail_service,
    connect_gmail,
    credentials_file,
    disconnect_gmail,
    gmail_profile,
    load_credentials,
    scan_gmail_messages,
)
from job_discovery import (
    JOB_SOURCES,
    build_job_discovery_plan,
    discover_jobs,
    filter_jobs,
    merge_job_leads,
)
from storage import get_data_file, load_database, save_database
from tracker import (
    find_duplicate_contact,
    get_follow_up_reminders,
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


NAVIGATION_PAGES = (
    "Dashboard",
    "Connect Gmail",
    "Applications",
    "Inbox Sync",
    "Jobs",
    "Outreach",
    "Notifications",
    "Settings",
)


def gmail_connection_warning():
    """Show the missing-connection message with a direct navigation link."""
    st.warning(
        "Gmail is not connected. "
        "[**Connect Gmail →**](?page=Connect%20Gmail) to import applications "
        "automatically."
    )


def navigation_changed():
    """Keep the URL in sync so direct links can select another dashboard view."""
    selected_page = st.session_state.navigation_page
    st.query_params["page"] = selected_page
    st.session_state.query_page_applied = selected_page


@st.cache_data(ttl=1800, show_spinner=False)
def cached_job_discovery():
    """Avoid repeatedly requesting university feeds during UI reruns."""
    return discover_jobs()


def initialize_state():
    """Load local data once for this browser session."""
    if "database" not in st.session_state:
        try:
            st.session_state.database = load_database()
        except (OSError, ValueError) as exc:
            st.error(f"The saved tracker could not be loaded: {exc}")
            st.stop()
    st.session_state.setdefault("pending_change", None)
    st.session_state.setdefault("gmail_scan_plan", None)


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
            if pending["action"] == "gmail_import":
                st.session_state.gmail_scan_plan = None
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


def job_leads_frame(job_leads):
    """Build a consistently ordered discovered-jobs table."""
    return pd.DataFrame(job_leads, columns=JOB_LEAD_COLUMNS)


def gmail_connection_page():
    """Provide one visible place to configure and connect Gmail."""
    st.title("Connect Gmail")
    st.write(
        "Connect the Gmail account that receives your job application email. "
        "Google handles the sign-in; this dashboard never asks for your password."
    )

    try:
        gmail_credentials = load_credentials()
    except Exception as exc:
        gmail_credentials = None
        st.error(f"Stored Gmail authorization could not be loaded: {exc}")

    if gmail_credentials:
        try:
            profile = gmail_profile(build_gmail_service(gmail_credentials))
        except Exception as exc:
            st.error(f"Gmail could not be reached: {exc}")
        else:
            st.success(
                f"Connected read-only to {profile.get('emailAddress', 'Gmail')}."
            )
            st.info(
                "Open Inbox Sync to scan application email beginning June 1, 2025."
            )
        if st.button("Disconnect Gmail", width="stretch"):
            disconnect_gmail()
            st.session_state.gmail_scan_plan = None
            st.rerun()
        return

    st.warning("Complete the Gmail setup below to authorize inbox scanning.")
    client_file = credentials_file()
    if not client_file.exists():
        st.subheader("First-time OAuth setup")
        st.write(
            "Create a Desktop OAuth client in Google Cloud, download its JSON "
            "file, and upload it here. It stays on this computer and is excluded "
            "from Git."
        )
        uploaded_file = st.file_uploader(
            "Upload Google OAuth client JSON",
            type=("json",),
        )
        if uploaded_file is not None:
            try:
                client_data = json.loads(uploaded_file.getvalue())
                installed_client = client_data.get("installed", {})
                if not installed_client.get("client_id") or not installed_client.get(
                    "client_secret"
                ):
                    raise ValueError(
                        "Upload a Desktop app OAuth client JSON file from Google Cloud."
                    )
            except (json.JSONDecodeError, ValueError) as exc:
                st.error(exc)
            else:
                if st.button(
                    "Save OAuth configuration",
                    type="primary",
                    width="stretch",
                ):
                    client_file.write_text(
                        json.dumps(client_data, indent=2),
                        encoding="utf-8",
                    )
                    st.rerun()
        st.markdown(
            "Detailed steps: [Gmail setup guide]"
            "(https://github.com/rutujashingate/Job-tracker-application/"
            "blob/main/GMAIL_SETUP.md)"
        )
        return

    st.success("OAuth configuration is ready.")
    st.caption(f"Local configuration: {client_file}")
    if st.button("Connect Gmail", type="primary", width="stretch"):
        try:
            with st.spinner("Waiting for Google authorization..."):
                connect_gmail()
        except Exception as exc:
            st.error(f"Gmail authorization failed: {exc}")
        else:
            st.rerun()


def dashboard_page(database):
    """Display high-level metrics, charts, and due reminders."""
    st.title("Job search dashboard")
    st.caption("University roles · STEM OPT · Future H-1B sponsorship")
    try:
        gmail_connected = load_credentials() is not None
    except Exception:
        gmail_connected = False
    if not gmail_connected:
        gmail_connection_warning()
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
    """Display Gmail-detected applications and allow status corrections."""
    st.title("Applications")
    if render_approval_gate():
        st.stop()

    applications = database["applications"]
    try:
        gmail_connected = load_credentials() is not None
    except Exception:
        gmail_connected = False
    if gmail_connected:
        st.info(
            "Applications are added automatically from confirmation emails. "
            "[**Scan Gmail now →**](?page=Inbox%20Sync)"
        )
    else:
        gmail_connection_warning()

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

    if applications:
        with st.expander("Correct a detected status"):
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


def inbox_sync_page(database):
    """Scan Gmail and stage detected application changes for approval."""
    st.title("Gmail application sync")
    if render_approval_gate():
        st.stop()

    try:
        credentials = load_credentials()
    except Exception as exc:
        st.error(f"The Gmail connection needs attention: {exc}")
        return
    if credentials is None:
        gmail_connection_warning()
        return

    try:
        service = build_gmail_service(credentials)
        profile = gmail_profile(service)
    except Exception as exc:
        st.error(f"Gmail could not be reached: {exc}")
        return

    st.success(f"Connected read-only to {profile.get('emailAddress', 'Gmail')}.")
    sync_state = database.get("email_sync", {})
    stored_start = sync_state.get("start_date", "2025-06-01")
    start_date = st.date_input(
        "Scan application emails beginning",
        value=date.fromisoformat(stored_start),
    )
    st.caption(
        "The search excludes hackathons. Local classification keeps job "
        "application confirmations, interviews, offers, withdrawals, and rejections."
    )

    if st.button("Scan Gmail", type="primary"):
        try:
            with st.spinner("Reading and classifying matching Gmail messages..."):
                messages = scan_gmail_messages(service, start_date)
                detections = classify_messages(messages)
                plan = build_email_import_plan(database, detections)
                plan["messages_scanned"] = len(messages)
                plan["detections_found"] = len(detections)
                plan["start_date"] = start_date.isoformat()
                plan["database"]["email_sync"]["start_date"] = start_date.isoformat()
                st.session_state.gmail_scan_plan = plan
        except Exception as exc:
            st.error(f"The Gmail scan failed: {exc}")
        else:
            st.rerun()

    plan = st.session_state.gmail_scan_plan
    if plan is None:
        last_scan = sync_state.get("last_scan_at")
        if last_scan:
            st.info(f"Last approved scan: {last_scan}")
        return

    metric_columns = st.columns(3)
    metric_columns[0].metric("Messages scanned", plan["messages_scanned"])
    metric_columns[1].metric("Job emails detected", plan["detections_found"])
    metric_columns[2].metric("Changes ready", len(plan["changes"]))

    if plan["changes"]:
        preview_rows = []
        for change in plan["changes"]:
            after = change["after"]
            preview_rows.append(
                {
                    "action": change["action"],
                    "university": after["company_name"],
                    "role": after["role_title"],
                    "status": after["status"],
                    "email_date": after.get("last_email_date", ""),
                }
            )
        st.subheader("Detected changes")
        st.dataframe(
            pd.DataFrame(preview_rows),
            hide_index=True,
            width="stretch",
        )
        if st.button("Review and approve detected changes", type="primary"):
            stage_change(
                "gmail_import",
                plan["database"],
                {"email_changes": plan["changes"]},
            )
    else:
        st.info("No new application records or matched status changes were found.")

    if plan["unmatched"]:
        st.subheader("Needs review")
        st.warning(
            "These job-related emails could not be matched safely. They were not "
            "written to the tracker."
        )
        unmatched_rows = [
            {
                "subject": detection["subject"],
                "sender": detection["sender_address"],
                "email_date": detection["received_date"],
                "detected_status": detection["detected_status"],
                "suggested_university": detection["company_name"],
                "suggested_role": detection["role_title"],
            }
            for detection in plan["unmatched"]
        ]
        st.dataframe(
            pd.DataFrame(unmatched_rows),
            hide_index=True,
            width="stretch",
        )


def _render_job_charts(job_leads):
    """Show the university mix and posting activity for filtered jobs."""
    if not job_leads:
        return
    chart_data = pd.DataFrame(job_leads)
    university_counts = (
        chart_data.groupby("university", as_index=False)
        .size()
        .rename(columns={"size": "jobs"})
        .sort_values("jobs", ascending=False)
    )
    posting_counts = (
        chart_data.groupby("date_posted", as_index=False)
        .size()
        .rename(columns={"size": "jobs"})
        .sort_values("date_posted")
    )

    university_column, timeline_column = st.columns(2)
    with university_column:
        st.subheader("Jobs by university")
        university_chart = (
            alt.Chart(university_counts)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("jobs:Q"),
                color=alt.Color("university:N", title="University"),
                tooltip=["university:N", "jobs:Q"],
            )
            .properties(height=330)
        )
        st.altair_chart(university_chart, width="stretch")

    with timeline_column:
        st.subheader("Jobs by posting date")
        timeline_chart = (
            alt.Chart(posting_counts)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("date_posted:T", title="Date posted"),
                y=alt.Y("jobs:Q", title="Jobs"),
                tooltip=["date_posted:T", "jobs:Q"],
            )
            .properties(height=330)
        )
        st.altair_chart(timeline_chart, width="stretch")


def job_leads_page(database):
    """Discover, filter, chart, export, and approval-save current job leads."""
    st.title("Jobs found for you")
    st.caption(
        "Early career software, frontend, UI, and AI roles from official "
        "university job boards."
    )
    if render_approval_gate():
        st.stop()

    refresh_column, source_column = st.columns([1, 3])
    refresh_requested = refresh_column.button(
        "Refresh jobs now",
        type="primary",
        width="stretch",
    )
    source_column.caption(
        f"Scanning {len(JOB_SOURCES)} official sources · results cached for 30 minutes"
    )
    if refresh_requested:
        cached_job_discovery.clear()

    try:
        with st.spinner("Searching official university job boards..."):
            discovered_jobs, source_errors = cached_job_discovery()
    except Exception as exc:
        discovered_jobs, source_errors = [], []
        st.error(f"Job discovery could not run: {exc}")

    saved_jobs = database.get("job_leads", [])
    all_jobs, new_jobs = merge_job_leads(saved_jobs, discovered_jobs)
    if source_errors:
        with st.expander(f"{len(source_errors)} source warning(s)"):
            for error in source_errors:
                st.warning(f"{error['source']}: {error['error']}")

    time_options = {
        "Last 24 hours": 24,
        "Last 3 days": 72,
        "Last 7 days": 168,
        "Last 30 days": 720,
        "Any time": None,
    }
    universities = sorted(
        {lead.get("university", "") for lead in all_jobs if lead.get("university")}
    )
    families = sorted(
        {lead.get("job_family", "") for lead in all_jobs if lead.get("job_family")}
    )
    filter_columns = st.columns((1, 1.5, 1.25, 1.25))
    time_label = filter_columns[0].selectbox(
        "Posted",
        tuple(time_options),
        index=3,
    )
    keyword = filter_columns[1].text_input(
        "Search",
        placeholder="Title, university, or location",
    )
    selected_universities = filter_columns[2].multiselect(
        "Universities",
        universities,
    )
    selected_families = filter_columns[3].multiselect(
        "Role groups",
        families,
    )
    filtered_jobs = filter_jobs(
        all_jobs,
        hours=time_options[time_label],
        universities=selected_universities,
        families=selected_families,
        query=keyword,
    )

    last_day_count = len(filter_jobs(all_jobs, hours=24))
    metric_columns = st.columns(4)
    metric_columns[0].metric("Matching jobs", len(filtered_jobs))
    metric_columns[1].metric("Posted in 24h", last_day_count)
    metric_columns[2].metric(
        "Universities",
        len({job.get("university") for job in filtered_jobs}),
    )
    metric_columns[3].metric("New this scan", len(new_jobs))

    _render_job_charts(filtered_jobs)

    st.subheader("Job postings")
    if filtered_jobs:
        display_columns = (
            "role_title",
            "university",
            "job_family",
            "location",
            "date_posted",
            "sponsorship_status",
            "job_url",
        )
        st.dataframe(
            pd.DataFrame(filtered_jobs).reindex(columns=display_columns),
            hide_index=True,
            width="stretch",
            column_config={
                "role_title": "Role",
                "university": "University",
                "job_family": "Role group",
                "location": "Location",
                "date_posted": st.column_config.DateColumn("Posted"),
                "sponsorship_status": "Sponsorship",
                "job_url": st.column_config.LinkColumn(
                    "Original posting",
                    display_text="Apply / view",
                ),
            },
        )
    else:
        st.info("No jobs match the selected filters. Try a wider posting period.")

    action_column, download_column = st.columns(2)
    if new_jobs:
        if action_column.button(
            f"Review and save {len(new_jobs)} new jobs",
            type="primary",
            width="stretch",
        ):
            plan = build_job_discovery_plan(database, discovered_jobs)
            stage_change(
                "save_discovered_jobs",
                plan["database"],
                {"new_job_leads": plan["additions"]},
            )
    else:
        action_column.success("All discovered jobs are already saved.")
    download_column.download_button(
        "Download filtered jobs CSV",
        records_to_csv(filtered_jobs, JOB_LEAD_COLUMNS),
        file_name="job_leads.csv",
        mime="text/csv",
        width="stretch",
    )

    st.caption(
        "Sponsorship remains unclear until a posting explicitly confirms it. "
        "Always verify STEM OPT and H-1B eligibility on the original posting."
    )


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
    try:
        credentials = load_credentials()
    except Exception:
        credentials = None
    if credentials:
        st.info(
            "Gmail is connected with read-only access for application tracking. "
            "Sending email is still disabled and will require a separate scope."
        )
    else:
        gmail_connection_warning()


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
        try:
            gmail_credentials = load_credentials()
        except Exception:
            gmail_credentials = None
        if gmail_credentials:
            st.success("Connected read-only")
        else:
            st.error("Not connected")
        st.markdown("[**Connect Gmail →**](?page=Connect%20Gmail)")
        st.caption("Requested Gmail permission: read-only.")
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

requested_page = st.query_params.get("page")
if (
    requested_page in NAVIGATION_PAGES
    and st.session_state.get("query_page_applied") != requested_page
):
    st.session_state.navigation_page = requested_page
    st.session_state.query_page_applied = requested_page

with st.sidebar:
    st.title("🎓 Job Tracker")
    page = st.radio(
        "Navigation",
        NAVIGATION_PAGES,
        key="navigation_page",
        on_change=navigation_changed,
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
elif page == "Connect Gmail":
    gmail_connection_page()
elif page == "Applications":
    applications_page(database)
elif page == "Inbox Sync":
    inbox_sync_page(database)
elif page == "Jobs":
    job_leads_page(database)
elif page == "Outreach":
    outreach_page(database)
elif page == "Notifications":
    notifications_page(database)
else:
    settings_page(database)
