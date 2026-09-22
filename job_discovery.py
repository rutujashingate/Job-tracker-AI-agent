"""Discover target roles from official public university job feeds."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
import json
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


USER_AGENT = "UniversityJobTracker/1.0"
REQUEST_TIMEOUT_SECONDS = 20
WORKDAY_SEARCH_TERMS = (
    "software",
    "developer",
    "frontend",
    "artificial intelligence",
    "machine learning",
)

# Each URL belongs to the university named in the same record. These sources do
# not need an API key or a job-board account.
JOB_SOURCES = (
    {
        "name": "University of Iowa",
        "kind": "rss",
        "url": "https://hris.uiowa.edu/otac-rss/jobs.php",
    },
    {
        "name": "University of Chicago",
        "kind": "workday",
        "api_url": (
            "https://uchicago.wd5.myworkdayjobs.com/wday/cxs/"
            "uchicago/External/jobs"
        ),
        "public_url": "https://uchicago.wd5.myworkdayjobs.com/en-US/External",
    },
    {
        "name": "Georgetown University",
        "kind": "workday",
        "api_url": (
            "https://georgetown.wd1.myworkdayjobs.com/wday/cxs/"
            "georgetown/Georgetown_Admin_Careers/jobs"
        ),
        "public_url": (
            "https://georgetown.wd1.myworkdayjobs.com/en-US/"
            "Georgetown_Admin_Careers"
        ),
    },
    {
        "name": "Arizona State University",
        "kind": "workday",
        "api_url": (
            "https://asu.wd1.myworkdayjobs.com/wday/cxs/"
            "asu/ASUStaffCareers/jobs"
        ),
        "public_url": "https://asu.wd1.myworkdayjobs.com/en-US/ASUStaffCareers",
    },
    {
        "name": "Western Governors University",
        "kind": "workday",
        "api_url": (
            "https://wgu.wd5.myworkdayjobs.com/wday/cxs/wgu/External/jobs"
        ),
        "public_url": "https://wgu.wd5.myworkdayjobs.com/en-US/External",
    },
    {
        "name": "University of Southern California",
        "kind": "workday",
        "api_url": (
            "https://usc.wd5.myworkdayjobs.com/wday/cxs/"
            "usc/ExternalUSCCareers/jobs"
        ),
        "public_url": (
            "https://usc.wd5.myworkdayjobs.com/en-US/ExternalUSCCareers"
        ),
    },
    {
        "name": "University of Texas at Dallas",
        "kind": "atom",
        "url": (
            "https://jobs.utdallas.edu/postings/search.atom?"
            "utf8=%E2%9C%93&query=software"
        ),
        "location": "Richardson, TX",
    },
)

TARGET_ROLE_PATTERNS = (
    r"\bsoftware (?:developer|engineer)\b",
    r"\bapplications? (?:developer|engineer|programmer)\b",
    r"\bweb (?:developer|engineer)\b",
    r"\bfront[ -]?end (?:developer|engineer)\b",
    r"\bui (?:developer|engineer)\b",
    r"\buser interface (?:developer|engineer)\b",
    r"\bai engineer\b",
    r"\bartificial intelligence engineer\b",
    r"\bmachine learning engineer\b",
    r"\bprogrammer(?: analyst)?\b",
)
SENIOR_ROLE_PATTERN = re.compile(
    r"\b(?:senior|sr\.?|lead|principal|manager|director|architect|head|chief|"
    r"vice president|staff software|supervisor)\b",
    re.IGNORECASE,
)


def is_target_role(title):
    """Return True for a target software or AI title without senior wording."""
    normalized = " ".join((title or "").split())
    if SENIOR_ROLE_PATTERN.search(normalized):
        return False
    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in TARGET_ROLE_PATTERNS
    )


def job_family(title):
    """Group a matching title for dashboard filtering and charts."""
    normalized = (title or "").lower()
    if re.search(r"\b(?:ai|artificial intelligence|machine learning)\b", normalized):
        return "AI / Machine Learning"
    if re.search(r"\b(?:front[ -]?end|ui|user interface|web)\b", normalized):
        return "Frontend / UI"
    return "Software Development"


def _clean_text(value):
    return " ".join(unescape(value or "").split())


def _stable_id(url):
    return sha256(url.encode("utf-8")).hexdigest()[:20]


def _iso_datetime(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _new_lead(
    university,
    title,
    location,
    url,
    posted_at,
    source,
    found_at,
):
    """Build one normalized job lead from a public source record."""
    return {
        "id": _stable_id(url),
        "university": university,
        "role_title": _clean_text(title),
        "job_family": job_family(title),
        "location": _clean_text(location),
        "job_url": url,
        "date_found": found_at.date().isoformat(),
        "date_posted": posted_at.date().isoformat(),
        "posted_at": _iso_datetime(posted_at),
        "sponsorship_status": "unclear",
        "stem_opt_evidence": "",
        "h1b_evidence": "",
        "source": source,
        "status": "new",
        "notes": "Verify STEM OPT and H-1B eligibility in the original posting.",
    }


def _fetch_bytes(url, data=None, headers=None):
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = Request(url, data=data, headers=request_headers)
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_rss_source(source, now=None):
    """Read matching jobs from an official RSS feed."""
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(_fetch_bytes(source["url"]))
    leads = []
    for item in root.findall("./channel/item"):
        title = _clean_text(item.findtext("title"))
        if not is_target_role(title):
            continue
        url = _clean_text(item.findtext("link"))
        if not url:
            continue
        published = parsedate_to_datetime(_clean_text(item.findtext("pubDate")))
        description = _clean_text(item.findtext("description"))
        department_match = re.search(r"Department:\s*([^<]+)", description)
        location = department_match.group(1).strip() if department_match else "Iowa City, IA"
        leads.append(
            _new_lead(
                source["name"],
                title,
                location,
                url,
                published,
                source["name"] + " official RSS",
                now,
            )
        )
    return leads


def fetch_atom_source(source, now=None):
    """Read matching jobs from an official Atom search feed."""
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(_fetch_bytes(source["url"]))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    leads = []
    for entry in root.findall("atom:entry", namespace):
        title = _clean_text(entry.findtext("atom:title", namespaces=namespace))
        if not is_target_role(title):
            continue
        alternate_link = entry.find("atom:link[@rel='alternate']", namespace)
        url = alternate_link.get("href", "") if alternate_link is not None else ""
        if not url:
            continue
        published_text = entry.findtext("atom:published", namespaces=namespace)
        try:
            published = datetime.fromisoformat(published_text)
        except (TypeError, ValueError):
            published = now
        leads.append(
            _new_lead(
                source["name"],
                title,
                source.get("location", "United States"),
                url,
                published,
                source["name"] + " official Atom feed",
                now,
            )
        )
    return leads


def workday_posted_at(label, now=None):
    """Convert Workday's relative posting label into a filterable timestamp."""
    now = now or datetime.now(timezone.utc)
    normalized = (label or "").strip().lower()
    if normalized == "posted today":
        return now
    if normalized == "posted yesterday":
        return now - timedelta(days=1)
    match = re.search(r"posted\s+(\d+)\+?\s+days?\s+ago", normalized)
    if match:
        return now - timedelta(days=int(match.group(1)))
    return now - timedelta(days=365)


def fetch_workday_source(source, now=None):
    """Search one university's public Workday board for target job titles."""
    now = now or datetime.now(timezone.utc)
    postings_by_path = {}
    for term in WORKDAY_SEARCH_TERMS:
        payload = json.dumps(
            {
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": term,
            }
        ).encode("utf-8")
        response = _fetch_bytes(
            source["api_url"],
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        for posting in json.loads(response).get("jobPostings", []):
            path = posting.get("externalPath", "")
            if path:
                postings_by_path[path] = posting

    leads = []
    for path, posting in postings_by_path.items():
        title = _clean_text(posting.get("title"))
        if not is_target_role(title):
            continue
        url = urljoin(source["public_url"].rstrip("/") + "/", path.lstrip("/"))
        leads.append(
            _new_lead(
                source["name"],
                title,
                posting.get("locationsText", "United States"),
                url,
                workday_posted_at(posting.get("postedOn"), now),
                source["name"] + " official Workday board",
                now,
            )
        )
    return leads


def fetch_source(source, now=None):
    """Dispatch a configured source to its parser."""
    if source["kind"] == "rss":
        return fetch_rss_source(source, now)
    if source["kind"] == "atom":
        return fetch_atom_source(source, now)
    if source["kind"] == "workday":
        return fetch_workday_source(source, now)
    raise ValueError(f"Unsupported job source kind: {source['kind']}")


def discover_jobs(sources=JOB_SOURCES, now=None):
    """Fetch all sources concurrently and return leads plus per-source errors."""
    now = now or datetime.now(timezone.utc)
    leads_by_url = {}
    errors = []
    with ThreadPoolExecutor(max_workers=min(4, len(sources))) as executor:
        future_sources = {
            executor.submit(fetch_source, source, now): source for source in sources
        }
        for future in as_completed(future_sources):
            source = future_sources[future]
            try:
                leads = future.result()
            except Exception as exc:
                errors.append({"source": source["name"], "error": str(exc)})
                continue
            for lead in leads:
                leads_by_url[lead["job_url"]] = lead

    leads = sorted(
        leads_by_url.values(),
        key=lambda lead: lead.get("posted_at", ""),
        reverse=True,
    )
    return leads, sorted(errors, key=lambda error: error["source"])


def filter_jobs(job_leads, hours=None, universities=None, families=None, query=""):
    """Filter job leads by age, university, role family, and free text."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
        if hours is not None
        else None
    )
    normalized_query = query.strip().lower()
    filtered = []
    for lead in job_leads:
        if universities and lead.get("university") not in universities:
            continue
        if families and lead.get("job_family") not in families:
            continue
        if normalized_query:
            searchable = " ".join(
                str(lead.get(field, ""))
                for field in ("role_title", "university", "location")
            ).lower()
            if normalized_query not in searchable:
                continue
        if cutoff:
            try:
                posted_at = datetime.fromisoformat(lead.get("posted_at", ""))
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                try:
                    posted_date = date.fromisoformat(lead.get("date_posted", ""))
                    posted_at = datetime.combine(
                        posted_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )
                except (TypeError, ValueError):
                    continue
            if posted_at < cutoff:
                continue
        filtered.append(lead)
    return filtered


def merge_job_leads(saved_leads, discovered_leads):
    """Return all leads and the records that are new by original posting URL."""
    saved_urls = {lead.get("job_url") for lead in saved_leads if lead.get("job_url")}
    new_leads = [
        lead for lead in discovered_leads if lead.get("job_url") not in saved_urls
    ]
    return [*saved_leads, *new_leads], new_leads


def build_job_discovery_plan(database, discovered_leads, scanned_at=None):
    """Prepare a database update; the caller must obtain approval before saving."""
    scanned_at = scanned_at or datetime.now(timezone.utc)
    proposed = deepcopy(database)
    merged, additions = merge_job_leads(
        proposed.get("job_leads", []),
        discovered_leads,
    )
    proposed["job_leads"] = merged
    proposed["job_discovery"] = {
        "last_scan_at": _iso_datetime(scanned_at),
        "sources": [source["name"] for source in JOB_SOURCES],
    }
    return {
        "database": proposed,
        "additions": additions,
        "discovered_count": len(discovered_leads),
    }
