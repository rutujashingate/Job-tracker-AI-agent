# University Job Application Tracker

A beginner-friendly Python command-line app that tracks university job
applications for an international candidate seeking STEM OPT and future H-1B
sponsorship. It demonstrates agentic thinking through goals, state, tools,
validation, human approval, and local memory.

## Current features

- Collects a job-search goal, deadline, application target, and weekly capacity.
- Tracks Junior Software Developer, UI Developer, Frontend Developer, and AI
  Engineer applications at U.S. universities.
- Logs applications and the available sponsorship evidence.
- Supports `applied`, `interviewing`, `offer`, `rejected`, and `withdrawn`.
- Calculates a follow-up date seven days after applying.
- Shows due reminders and a pipeline summary after every action.
- Previews every proposed data change and requires explicit approval.
- Saves approved changes to local JSON and reloads them on the next run.
- Includes an outreach-history data model for future duplicate-email checks.

## Agent workflow

```text
Collect goal
    ↓
Gather and validate input
    ↓
Build a proposed change
    ↓
Show the exact change
    ↓
Request approval
    ↓
Save and update state
    ↓
Display the current pipeline
```

## Project structure

```text
.
├── main.py             # Interactive command-line interface and approval gate
├── tracker.py          # Application, status, summary, and reminder tools
├── validation.py       # Input rules and normalization
├── storage.py          # Approved JSON loading and atomic saving
├── DESIGN.md           # Requirements and architecture decisions
├── REFLECTION.md       # What this project teaches about agentic systems
├── data/
│   └── applications.json  # Created locally; excluded from Git
└── tests/
    └── test_job_tracker.py
```

## Requirements

- Python 3.9 or newer
- No third-party packages

## Run the app

From the project directory:

```bash
python3 main.py
```

On the first run, enter the search goal and review the JSON preview. A save is
approved only by `yes`, `confirm`, or `save`. Use `no` or `cancel` to reject it.
Unclear responses such as `maybe` cause another prompt.

Approved data is stored in `data/applications.json`. The next run loads that
file instead of asking for the goal again.

## Example interaction

```text
Choose an action:
  1. Log an application
  2. Update an application status
  3. View applications
  4. View follow-up reminders
  5. Exit

Enter 1-5: 1
University name: Example University
Role title: Junior Software Developer
Date applied [2026-09-21]:
Status [applied]:

Proposed change:
{
  "action": "add_application",
  "change": {
    "application": {
      "company_name": "Example University",
      "role_title": "Junior Software Developer",
      "status": "applied"
    }
  }
}

Type yes, confirm, or save to approve: save
Saved successfully to data/applications.json.
```

The real preview contains every application field, including its unique ID,
date, follow-up date, job details, sponsorship evidence, and notes.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover the normal application workflow, empty company names, invalid
statuses, past deadlines, vague approval responses, cancelled writes, approved
persistence, and malformed JSON.

## Local data and privacy

`data/applications.json` is excluded by `.gitignore` because it may contain
private job-search information. `.env` is also excluded for future API secrets.

## Current limitations

- Job discovery is still manual.
- Gmail application detection is not connected yet.
- The two data collections are local JSON lists rather than Google Sheet tabs.
- The app prepares outreach-history records but does not send email yet.
- Sponsorship evidence is entered by the user and should be verified against
  the employer's current job posting and policies.
- The tracker is designed for one local user.

## Planned extensions

1. Find matching jobs on public university career pages.
2. Read application and status emails with user-authorized Gmail access.
3. Synchronize applications and outreach history to two Google Sheet tabs.
4. Draft hiring-team emails, check for duplicate contacts, and send only after
   the user approves the exact recipient, subject, and message.
