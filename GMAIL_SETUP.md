# Connect Gmail to the local dashboard

The tracker uses Google's OAuth screen and the Gmail API. You select your Gmail
account in Google's browser window. The tracker never asks for or stores your
Gmail password.

The first Gmail permission is read-only:

```text
https://www.googleapis.com/auth/gmail.readonly
```

It allows the local dashboard to search and read application-related messages.
It does not allow the app to send, edit, or delete email.

## 1. Create a Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project or select a project you control.
3. Open **APIs & Services** and enable the **Gmail API**.

## 2. Configure Google OAuth

1. Open the Google Auth or OAuth consent-screen section.
2. Configure the app name and your support email.
3. Choose **External** if you are using a personal Gmail account.
4. Keep the app in testing while developing locally.
5. Add your Gmail account as a test user.

## 3. Download a desktop OAuth client

1. Open **APIs & Services → Credentials**.
2. Create an **OAuth client ID**.
3. Choose **Desktop app** as the application type.
4. Download its JSON file.
5. Rename it to `credentials.json`.
6. Move it into the project root beside `dashboard.py`.

The path should be:

```text
Job_Tracker_AI/credentials.json
```

`credentials.json` is excluded from Git and must never be committed.

## 4. Connect from the portal

Start the dashboard:

```bash
source .venv/bin/activate
streamlit run dashboard.py
```

Then open **Connect Gmail** in the sidebar and select the **Connect Gmail**
button. If you did not place `credentials.json` in the project root, upload the
downloaded JSON on this page and select **Save OAuth configuration** first.

Google opens an account chooser after you select the connect button. Select the
Gmail account that receives your job application emails and approve read-only
access. The resulting token is stored locally in `data/gmail_token.json`, which
is also excluded from Git.

## 5. Import application email

Open **Inbox Sync** and keep the start date at `2025-06-01`. Select **Scan
Gmail**. The dashboard:

1. searches candidate email from that date onward;
2. excludes messages containing hackathon-related terms;
3. classifies application confirmations, interviews, offers, withdrawals, and
   rejections;
4. matches later status messages to an existing application by Gmail thread or
   exact university and role; and
5. shows all proposed additions and updates before saving them.

Message bodies are processed in memory. The tracker stores message identifiers,
subject-based notes, dates, and application fields so it can avoid importing the
same email twice.

## Local and deployed authorization

The current OAuth flow is designed for this local Streamlit dashboard. A public
multi-user deployment needs a Google **Web application** OAuth client, registered
redirect URLs, encrypted per-user token storage, user accounts, and a production
OAuth consent-screen review.

Official Google reference:
[Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).
