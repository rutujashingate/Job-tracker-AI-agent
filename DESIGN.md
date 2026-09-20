# Job Application Tracker: design

## Assistant role

The assistant helps a job seeker set an application goal, record applications,
track their statuses, and identify when a follow-up is due. It asks for missing
information before proposing an action. It may read local data and show a
summary without approval. Before it changes the local JSON file, it shows the
exact proposed change and asks for an explicit confirmation. It does not submit
applications or send messages on the user's behalf.

## Search goal inputs

- Target role type
- Target company size or industry
- Number of applications to submit
- Deadline (YYYY-MM-DD; today or a future date)
- Weekly availability in hours

## Application record

Each application has a unique ID, company name, role title, date applied,
status, and notes. Allowed statuses are `applied`, `interviewing`, `offer`,
`rejected`, and `withdrawn`.

## Approval rules

Every change to saved data needs approval, including setting or editing the
search goal, adding an application, changing a status, editing notes, and
deleting a record. The assistant previews the proposed change first. It saves
only after `yes`, `confirm`, or `save`; an unclear response causes another
prompt. Viewing the pipeline and calculating a follow-up date do not change
saved data.

The default follow-up date is seven days after the application date. This is
a reminder calculation, not an automatic email.

## Learning milestones

1. Define the role, data model, and validation rules.
2. Add tracker functions and an interactive CLI.
3. Add approval gates and JSON persistence.
4. Test edge cases, document the program, and prepare a portfolio repository.
