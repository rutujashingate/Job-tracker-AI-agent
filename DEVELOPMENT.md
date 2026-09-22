# Development guide

## Local environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the dashboard:

```bash
streamlit run dashboard.py
```

Run the unit suite:

```bash
python -m unittest discover -s tests -v
```

Check syntax without starting Streamlit:

```bash
python -m py_compile *.py tests/*.py
```

## Design rules

### Keep tools separate from UI

Network retrieval, validation, classification, and storage belong in their own
modules. Streamlit pages should orchestrate those functions and display their
results. This allows unit tests to exercise business logic without a browser.

### Build writes on copies

Never mutate the live database before approval. Use `deepcopy`, build a proposed
database, and pass it to `stage_change`. The approval renderer is the only UI
path that calls `save_database(..., approved=True)`.

### Preserve conservative matching

Email and sponsorship mistakes can mislead the user. Match a status email by a
unique Gmail thread first and exact normalized employer plus role second. Leave
ambiguous messages unmatched. Leave sponsorship `unclear` without explicit
source evidence.

### Keep private state out of Git

Do not commit OAuth credentials, OAuth tokens, application data, exported user
data, or environment files. Review `.gitignore` before adding a new secret path.

## Add a university job source

Sources live in `job_discovery.JOB_SOURCES`.

### Existing parser kinds

- `rss`: RSS 2.0 with `channel/item`, title, link, and `pubDate`.
- `atom`: Atom entries with title, alternate link, and published timestamp.
- `workday`: public Workday CXS endpoint plus its public job-board root.

Example Workday source:

```python
{
    "name": "Example University",
    "kind": "workday",
    "api_url": (
        "https://example.wd1.myworkdayjobs.com/wday/cxs/"
        "example/External/jobs"
    ),
    "public_url": "https://example.wd1.myworkdayjobs.com/en-US/External",
}
```

Before adding it:

1. confirm the source is the university's official public job board;
2. request it without credentials and verify its response shape;
3. confirm generated original-posting links open correctly;
4. run discovery and inspect role filtering;
5. add a parser test for any new response format; and
6. document the institution in the README.

If a source needs a different payload or HTML parser, add a new focused fetch
function and dispatch it from `fetch_source`. A failed source must produce a
source-specific error without stopping other sources.

## Change target roles

Edit `TARGET_ROLE_PATTERNS` and `SENIOR_ROLE_PATTERN` in `job_discovery.py`.
Patterns operate on job titles, not descriptions. Add positive, negative, and
unrelated title examples to `JobDiscoveryTests.test_target_role_matching...`.

## Extend Gmail classification

- Search terms sent to Gmail are in `gmail_service.build_job_email_query`.
- Event phrases are in `email_importer.STATUS_SIGNALS` and
  `APPLICATION_SIGNALS`.
- Non-job exclusions are in `email_importer.EXCLUDED_TERMS`.
- Subject extraction patterns are in `email_importer.DETAIL_PATTERNS`.

Add tests with fictional messages before changing detection phrases. Verify that
confirmation plus later rejection still yields one application.

## Change the database schema

1. Add defaults to `storage.empty_database`.
2. Add matching `setdefault` logic in `storage.load_database` for old files.
3. Validate the top-level type.
4. Update stable CSV columns if the field is exported.
5. Update [ARCHITECTURE.md](ARCHITECTURE.md).
6. Test loading a database created before the new field existed.

## Testing external integrations

The unit suite should not depend on live Google or university services. Put
parsing and planning logic behind functions that accept ordinary dictionaries
or XML strings, then test those functions with fixtures or mocks.

Before a release, run a separate smoke test:

```bash
python - <<'PY'
from job_discovery import discover_jobs

jobs, errors = discover_jobs()
print(f"jobs={len(jobs)} errors={errors}")
for job in jobs[:5]:
    print(job["university"], job["role_title"], job["job_url"])
PY
```

Live Gmail testing requires the local OAuth files and should never print token
contents or full email bodies.

## Git workflow

The project uses small milestone commits. Before committing:

```bash
git diff --check
python -m unittest discover -s tests -v
git status --short
```

Commit source, tests, and related documentation together. Confirm private files
remain ignored with `git status --ignored` when changing credential paths.
