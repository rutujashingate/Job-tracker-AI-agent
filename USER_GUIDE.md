# User guide

This guide explains how to operate every part of the local dashboard.

## Start the dashboard

From the project directory, run:

```bash
source .venv/bin/activate
streamlit run dashboard.py
```

Open <http://localhost:8501>. Keep the terminal running while using the portal.
Stop it with `Control-C` in the terminal.

## Recommended first-time sequence

1. **Settings:** save your target roles, deadline, application goal, and weekly
   availability.
2. **Jobs:** review automatically discovered jobs and open original postings.
3. **Connect Gmail:** upload the Desktop OAuth client and authorize your Gmail
   account.
4. **Inbox Sync:** scan email and approve detected applications and status
   updates.
5. **Dashboard:** review totals, pipeline status, sponsorship evidence, and
   follow-up reminders.

## Dashboard

The home page shows:

- total applications;
- applications in interviewing and offer states;
- follow-ups due;
- progress toward the application target;
- an application status chart;
- a sponsorship evidence chart;
- job discovery metrics and charts for the last 30 days; and
- applications due for follow-up.

If Gmail is disconnected, **Connect Gmail** inside the warning is a direct link
to the connection page.

## Connect Gmail

This page is the only place used to add or remove Gmail authorization.

For first-time setup, follow [GMAIL_SETUP.md](GMAIL_SETUP.md). You can upload the
downloaded Desktop OAuth JSON directly on this page. After it is stored, select
**Connect Gmail**, choose the account that receives application messages, and
approve read-only access.

The connected email address appears on the page. **Disconnect Gmail** deletes
the local token. You can separately revoke access from your Google Account if
needed.

## Jobs

Opening this page automatically searches the configured official university job
sources. The result list contains only matching early career role titles.

### Filters

- **Posted:** last 24 hours, 3 days, 7 days, 30 days, or any time.
- **Search:** text contained in the title, university, or location.
- **Universities:** one or more employers.
- **Role groups:** software development, frontend/UI, or AI/machine learning.

The metric cards update with the selected filters. Each result is displayed as a
structured card with the role, university, location, posting age, employment
type, sponsorship state, and available job details. The description excerpt and
requirements use text pulled directly from the original posting. The tracker
does not generate its own job description.

Click anywhere on a job card, including **Go to original posting**, to read the
full source and apply. The original university posting opens in a new browser
tab, keeping your filtered Jobs page available. Keyboard users can press `Tab`
to focus a card and `Enter` to open it; the focused card has a visible outline.
If a record has no usable posting URL, its card shows **Original posting
unavailable** and cannot be opened.

Opening a posting does not save the lead or mark it as applied. Applications
are tracked after Gmail confirmations are imported and approved. Job charts
are displayed on the home **Dashboard**.

**Refresh jobs now** starts a new network scan. Normal page interactions reuse
the 30-minute cache.

Live search results appear before they are saved. Select **Review and save N
job updates** (where N is the number of new or enriched leads), inspect the JSON
preview, and select **Approve and save** to save them to local history.
Canceling leaves the file unchanged.

Sponsorship starts as `unclear` unless the source explicitly provides evidence.
Read the original posting before applying.

## Inbox Sync

This page reads relevant Gmail messages after the selected start date. The
default is June 1, 2025.

Select **Scan Gmail**. The dashboard reports:

- messages returned by Gmail;
- job-related messages detected; and
- application changes ready for review.

It recognizes confirmation, interview, offer, rejection, and withdrawal
phrases. Hackathons, coding competitions, career fairs, webinars, and workshops
are excluded by local classification.

Select **Review and approve detected changes** to see the exact batch. Saving
requires a second explicit **Approve and save** action. Messages that cannot be
matched safely appear under **Needs review** and are not saved.

## Applications

Applications are created from approved Gmail detections. There is no manual
application-entry form in the dashboard.

The table can be downloaded as CSV. **Correct a detected status** exists for a
classification error or a status change communicated outside email. The
correction still passes through the approval gate.

## Outreach

This table records contacts and messages so the same email address is not used
twice accidentally. The current version records an email sent outside the app;
it does not send email through Gmail.

The form checks for an existing normalized address. Any new outreach record is
shown before it is saved.

## Notifications

This page lists application follow-ups that are due. Gmail sending is currently
disabled because the app requests read-only permission.

## Settings

Use this page to update:

- target roles;
- employer focus;
- application count goal;
- deadline; and
- weekly hours available.

The page also shows Gmail and Google Sheets connection states and the absolute
path of the local JSON database.

## CSV exports

Applications and outreach history provide CSV downloads. Job leads remain in
the structured card interface and local JSON. CSV files can be opened in Excel,
Numbers, or Google Sheets. Export does not modify the local database.

## Troubleshooting

### The dashboard is blank

Confirm Streamlit is running and open the health endpoint:

```bash
curl http://localhost:8501/_stcore/health
```

It should return `ok`. Then refresh the browser with `Command-Shift-R`.

### Gmail has no Connect button

The app needs a Desktop OAuth client first. Upload its JSON on **Connect Gmail**,
select **Save OAuth configuration**, and the connect button will appear.

### Google blocks the OAuth login

Keep the OAuth app in testing and add the Gmail account as a test user in Google
Cloud. Confirm that Gmail API is enabled and the client type is Desktop app.

### Inbox Sync finds nothing

- Widen the start date.
- Confirm the connected account receives the application email.
- Search Gmail manually for phrases such as `application received`.
- Check whether the sender used wording not covered by the current classifier.

### A message appears in Needs review

The parser could not confidently identify a unique role and university or could
not match a status email to an existing application. It intentionally avoids a
guess. Current review rows are informational; a future version can add a manual
mapping control.

### A university job source fails

Open the source-warning expander on **Jobs**. Other sources continue to work.
The university may have changed its public feed or job-board URL; update the
source configuration as described in [DEVELOPMENT.md](DEVELOPMENT.md).

### Data looks stale

Select **Reload saved data** in the sidebar for JSON changes or **Refresh jobs
now** for university-source changes.
