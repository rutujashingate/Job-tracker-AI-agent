# University Job Search Assistant: design

## Step 1: role and boundaries

### Assistant role

The assistant helps an international candidate find junior technology jobs at
universities across the United States. Its target roles are Junior Software
Developer, UI Developer, Frontend Developer, and AI Engineer. It prioritizes
roles with evidence relevant to STEM OPT and future H-1B sponsorship.

The assistant can:

- find matching jobs on public university career pages;
- capture the source URL and the sponsorship evidence it found;
- detect application confirmations and status changes from relevant emails;
- track applications, statuses, and seven-day follow-up reminders;
- find public professional contact information for a hiring team;
- draft outreach and follow-up emails; and
- maintain an outreach history so the same person is not contacted twice.

The assistant does not assume that a discovered job has been applied to. It
does not claim that sponsorship is available when the source is unclear. It
does not add or change tracker rows, submit applications, or send email without
showing the proposed action and receiving explicit approval.

### Required search-goal inputs

- Target role types
- Employer focus (U.S. universities)
- Sponsorship needs (STEM OPT and future H-1B)
- Number of applications to submit
- Deadline (YYYY-MM-DD; today or a future date)
- Weekly availability in hours

### Approval gates

The following actions always require confirmation:

- adding an application detected from email;
- changing an application status or notes;
- deleting an application;
- adding or editing an outreach-history entry;
- emailing a hiring contact; and
- contacting an email address that already appears in outreach history.

Before an approved write, the assistant shows the exact fields that will be
saved. Before an approved email, it shows the recipient, subject, and complete
message. It accepts `yes`, `confirm`, or `save` for data writes and `send` for
email. An unclear response such as `maybe` causes another prompt.

Reading data, searching public job pages, calculating reminders, checking for
duplicate contacts, and displaying summaries do not require approval.

## Step 2: data model

The tracker has two logical sheets. They are represented as two lists in local
JSON first and can later be synchronized to two tabs in a spreadsheet.

### Applications sheet

Each application contains:

- `id`
- `company_name` (the university employer)
- `role_title`
- `job_id`
- `location`
- `job_url`
- `date_applied`
- `status` (`applied`, `interviewing`, `offer`, `rejected`, or `withdrawn`)
- `sponsorship_status` (`confirmed`, `not_available`, or `unclear`)
- `stem_opt_evidence`
- `h1b_evidence`
- `source_email_id`
- `last_email_date`
- `follow_up_date`
- `notes`

An email-derived application remains a proposed record until the user approves
it. The source email ID lets the assistant avoid importing the same message
twice.

### Outreach history sheet

Each outreach entry contains:

- `id`
- `contact_name`
- `email_address`
- `company_name`
- `role_title`
- `application_id`
- `email_subject`
- `message_body`
- `date_sent`
- `reply_status`
- `follow_up_date`

Email addresses are stored in lowercase for duplicate checks. A previous entry
blocks another send unless the user explicitly approves an override.

### Session state

During one run, `session_state` holds the search goal, deadline, application
count, outreach count, current pipeline, pending action, and last completed
action. The saved JSON is the long-term memory; session state is working memory.

## Step 3: helper functions and CLI

The in-memory tracker provides these actions:

- `log_application` validates a record, calculates its default seven-day
  follow-up date, and adds it to the current session;
- `update_status` finds an application by ID and assigns an allowed status;
- `calculate_follow_up_date` performs the reminder date calculation;
- `summarise_pipeline` counts applications in every status;
- `get_follow_up_reminders` finds active applications whose reminder is due;
  and
- `find_duplicate_contact` compares normalized email addresses before future
  outreach.

The CLI collects the search goal, lets the user log applications, update a
status, view applications, and view reminders. It displays the complete
pipeline after every action. Step 3 keeps changes in memory so that approval
and persistence can be added together in Step 4.

## Later milestones

1. Add approval gates and local JSON persistence.
2. Connect job discovery, email reading, and the two spreadsheet tabs.
3. Test edge cases, document the program, and prepare a portfolio repository.
