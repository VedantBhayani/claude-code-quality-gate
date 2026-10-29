"""Shared helpers for the quality-gate dataset build (stdlib only)."""
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = RAW / "_probe_cache"
DISCOVERY = DATA / "discovery"

USER_AGENT = ("frontal-hire-quality-gate/0.1 (independent research; reads public job-board "
              "APIs only; one list call per board, >=1s between requests)")
DELAY_S = 1.1

ENDPOINTS = {
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true",
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
}
BOARD_URL = {
    "ashby": "https://jobs.ashbyhq.com/{t}",
    "greenhouse": "https://job-boards.greenhouse.io/{t}",
    "lever": "https://jobs.lever.co/{t}",
}

_last = [0.0]


def get(url):
    """One polite GET. Returns (status, bytes|None)."""
    wait = DELAY_S - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        status, body = e.code, None
    except Exception as e:  # network error
        status, body = f"ERR:{type(e).__name__}", None
    _last[0] = time.time()
    return status, body


def jobs_of(ats, payload):
    if ats == "lever":
        return payload if isinstance(payload, list) else []
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def text_of(ats, job):
    if ats == "greenhouse":
        t = html.unescape(job.get("content") or "")
    elif ats == "ashby":
        t = job.get("descriptionPlain") or ""
    else:
        t = (job.get("descriptionPlain") or "") + " " + (job.get("additionalPlain") or "")
        for l in job.get("lists") or []:
            t += " " + (l.get("content") or "")
    return re.sub(r"<[^>]+>", " ", t)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


DOMAIN_RX = re.compile(r"\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b")
ATS_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com")


def identity(ats, payload, name, domain):
    """How sure are we that this board belongs to the listed company?
    domain_in_text > gh_company_name / name_in_text > short_name_in_text; 'mismatch' if the board
    points at a different domain with the same stem (same name, different company)."""
    jobs = jobs_of(ats, payload)
    if not jobs:
        return "empty"
    domain = domain.lower()
    stem = domain.split(".")[0]
    blob = " ".join(text_of(ats, j) for j in jobs[:40]).lower()
    hosts = set()
    for j in jobs[:40]:
        u = (j.get("absolute_url") or j.get("hostedUrl") or j.get("jobUrl") or "").lower()
        m = re.match(r"https?://([^/]+)", u)
        if m and not any(h in m.group(1) for h in ATS_HOSTS):
            hosts.add(m.group(1).removeprefix("www."))
    if domain in blob or any(h == domain or h.endswith("." + domain) for h in hosts):
        return "domain_in_text"
    seen = {d.removeprefix("www.") for d in DOMAIN_RX.findall(blob)} | hosts
    rivals = [d for d in seen if d.split(".")[0] == stem and d != domain and not d.endswith("." + domain)]
    if rivals:
        return "mismatch"
    if ats == "greenhouse":
        cn = {norm(j.get("company_name")) for j in jobs}
        if norm(name) in cn:
            return "gh_company_name" if len(norm(name)) >= 6 or " " in name.strip() else "short_name_in_text"
    if re.search(r"\b" + re.escape(name.lower()) + r"\b", blob):
        return "name_in_text" if (len(norm(name)) >= 6 or " " in name.strip()) else "short_name_in_text"
    return "mismatch"
