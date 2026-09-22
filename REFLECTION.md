# Reflection: agentic thinking in the job tracker

This project is a small command-line program, but its structure contains the
main building blocks of a larger AI agent.

## Helper functions act as tools

An agent needs a set of actions it can perform. In this project,
`log_application`, `update_status`, `calculate_follow_up_date`, and
`summarise_pipeline` are those tools. Each function has a focused job, receives
specific inputs, and returns a predictable result. Validation sits in front of
the tools so invalid or incomplete information does not silently enter the
tracker.

This separation matters as the project grows. A future language model could
interpret a sentence such as "I applied to the developer role at Example
University yesterday," but it would still call the same validated application
tool. The model would not need direct access to the JSON file.

## Session state is working memory

The `session_state` dictionary records the search goal, deadline, counts,
pipeline, pending action, and last action. It gives the assistant the context
needed to decide what to show next. For example, it can display the pipeline
after an update or identify applications with due follow-ups.

Session state lasts for one run. The JSON document acts as long-term memory by
preserving the search goal, applications, and outreach history between runs.
Keeping these forms of memory separate makes it clear which information is
temporary and which information has been approved for storage.

## Approval gates keep the user in control

Writing data and sending email have consequences. The program builds changes
on a copy, displays the exact proposal, and waits for an unambiguous decision.
A response such as `maybe` does not count as approval. If the user cancels, the
live state and saved file remain unchanged. If the save fails, the live state
also remains unchanged.

This is a human-in-the-loop pattern: the assistant prepares an action, while
the user retains authority over execution. The same pattern will protect
future email outreach by previewing the recipient, subject, and full message
before sending.

## How the pattern scales

A more capable version can add job-search, Gmail, Google Sheets, and email tools
without discarding the current architecture. The reasoning layer can gather
missing details and choose a tool. The validation layer can check its proposed
arguments. The approval layer can pause consequential actions. The storage
layer can record the result and update the state.

As the number of tools grows, the system will also need stronger duplicate
detection, retry handling, audit records, access controls, and tests around
external services. The current project establishes the control flow needed for
those additions: understand the goal, inspect state, propose an action, obtain
approval, execute the tool, and report the result.
