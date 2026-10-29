"""Steps 1-3: build seed_candidates.csv, seed.csv, raw board JSON and posts.csv.

Uses only the payloads cached by probe.py (one successful GET per board; no refetch).
Funding evidence is read from data/discovery/funding_evidence.csv (filled by hand from
public announcement pages, one row per company domain).
Usage: python -I scripts/qualify.py
"""
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BOARD_URL, CACHE, DATA, DISCOVERY, RAW, identity, jobs_of  # noqa: E402
from titles import classify  # noqa: E402

# collection date = the day the board JSON was fetched (cache file mtime, local time)
QUALIFIER_CAP = 120  # research note 04: "Stop at ~120 qualifiers"
STRONG_ID = {"gh_company_name", "domain_in_text", "name_in_text"}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PERSON_AFTER_ROLE = re.compile(
    r"((?:recruiter|recruiting partner|talent partner|hiring manager|talent acquisition|contact)\s*(?:is|:|-|–)\s*)"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z'\-]+){0,2})")
PERSON_KEYS = re.compile(r"recruiter|hiringmanager|hiring_manager|owner|contact", re.I)


def load_probe():
    rows = []
    for line in (DISCOVERY / "probe_log.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("kind") == "company":
            rows.append(r)
    return rows


def listed(ats, j):
    return j.get("isListed", True) if ats == "ashby" else True


def posted(ats, j):
    try:
        if ats == "greenhouse":
            s = j.get("first_published") or j.get("updated_at")
            return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
        if ats == "ashby":
            s = j.get("publishedAt")
            return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
        ms = j.get("createdAt")
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None
    except (ValueError, TypeError, AttributeError):
        return None


def fields(ats, j):
    if ats == "greenhouse":
        return str(j.get("id")), j.get("title", ""), j.get("absolute_url", ""), (j.get("location") or {}).get("name", "")
    if ats == "ashby":
        return str(j.get("id")), j.get("title", ""), j.get("jobUrl", ""), j.get("location", "") or ""
    return str(j.get("id")), j.get("text", ""), j.get("hostedUrl", ""), (j.get("categories") or {}).get("location", "") or ""


def redact(obj):
    if isinstance(obj, dict):
        return {k: ("[redacted]" if PERSON_KEYS.search(k) and isinstance(v, (str, dict)) else redact(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        s = EMAIL.sub(lambda m: "[redacted-email]@" + m.group(0).split("@")[1], obj)  # keep company domain only
        return PERSON_AFTER_ROLE.sub(lambda m: m.group(1) + "[redacted-name]", s)
    return obj


def load_funding():
    p = DISCOVERY / "funding_evidence.csv"
    if not p.exists():
        return {}
    with p.open(encoding="utf-8", newline="") as f:
        return {r["domain"].lower(): r for r in csv.DictReader(f)}


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    probe = load_probe()
    funding = load_funding()
    cands, seed, posts, board_pass = [], [], [], []
    seen_boards = {}
    for old in RAW.glob("*.json"):  # rebuilt from cache each run; drop stale copies
        old.unlink()
    for r in probe:
        if not r.get("ats"):
            continue
        ats, tok = r["ats"], r["token"]
        cpath = CACHE / f"{ats}-{tok}.json"
        payload = json.loads(cpath.read_text(encoding="utf-8"))
        fetched = datetime.fromtimestamp(cpath.stat().st_mtime).date()
        COLLECTION_DATE = fetched.isoformat()
        WINDOW_START = datetime(fetched.year, fetched.month, fetched.day, tzinfo=timezone.utc) - timedelta(days=60)
        r["identity"] = identity(ats, payload, r["company"], r["domain"])  # recheck with current rule
        if r["identity"] == "mismatch":
            continue  # board belongs to a same-named different company: no board found
        jobs = [j for j in jobs_of(ats, payload) if listed(ats, j)]
        cands.append(dict(company=r["company"], domain=r["domain"], ats=ats, token=tok,
                          board_url=BOARD_URL[ats].format(t=tok), identity_check=r["identity"],
                          listed_round=r["round"], listed_round_month=r["round_month"],
                          source_url=r["source_url"], board_check=""))
        dates = [d for d in (posted(ats, j) for j in jobs) if d]
        newest = max(dates) if dates else None
        sales = [j for j in jobs if classify(fields(ats, j)[1])[0]]
        fund = funding.get(r["domain"], {})
        reasons = []
        if r["identity"] not in STRONG_ID:
            reasons.append(f"board identity weak ({r['identity']})")
        if len(jobs) < 3:
            reasons.append(f"only {len(jobs)} listed jobs")
        if not newest or newest < WINDOW_START:
            reasons.append("no post in last 60 days")
        if not sales:
            reasons.append("no sales-ish role open")
        board_ok = not reasons
        cands[-1]["board_check"] = "pass" if board_ok else "; ".join(reasons)
        if not board_ok:
            continue  # seed.csv holds only companies whose board passed; failures stay in seed_candidates.csv
        if sum(1 for x in seed if x["qualified"]) >= QUALIFIER_CAP:
            cands[-1]["board_check"] = f"pass (reserve: {QUALIFIER_CAP}-qualifier cap reached, not evaluated further)"
            continue
        board_pass.append(r["domain"])
        if not fund.get("funding_evidence_url"):
            reasons.append("no Series A+ evidence recorded" if board_ok else "funding not checked (board failed)")
        elif fund.get("series_a_plus", "").lower() != "yes":
            reasons.append(f"funding check failed: {fund.get('note', '')}".strip())
        if fund.get("exclude"):
            reasons.append(f"excluded: {fund['exclude']}")
        if (ats, tok) in seen_boards:
            reasons.append(f"duplicate of {seen_boards[(ats, tok)]} (same board)")
        else:
            seen_boards[(ats, tok)] = r["domain"]
        q = not reasons
        seed.append(dict(company=r["company"], domain=r["domain"], ats=ats, token=tok,
                         funding_stage=fund.get("funding_stage", ""),
                         funding_evidence_url=fund.get("funding_evidence_url", ""),
                         sales_roles_open=len(sales), jobs_listed=len(jobs),
                         newest_post_date=newest.date().isoformat() if newest else "",
                         qualified=q, reason="; ".join(reasons) if reasons else
                         f"identity {r['identity']}; {fund.get('note', '')}".strip()))
        if q:
            out = RAW / f"{ats}-{tok}-{COLLECTION_DATE}.json"
            out.write_text(json.dumps(redact(payload), ensure_ascii=False), encoding="utf-8")
            for j in sales:
                jid, title, url, loc = fields(ats, j)
                d = posted(ats, j)
                amb = classify(title)[1]
                posts.append(dict(company=r["company"], ats=ats, job_id=jid, title=EMAIL.sub("", title).strip(),
                                  url=url, posted_date=d.date().isoformat() if d else "",
                                  collection_date=COLLECTION_DATE, location=loc,
                                  is_ambiguous_title=bool(amb), ambiguous_family=amb or ""))
    write_csv(DATA / "seed_candidates.csv", ["company", "domain", "ats", "token", "board_url", "identity_check",
                                            "listed_round", "listed_round_month", "source_url", "board_check"], cands)
    write_csv(DATA / "seed.csv", ["company", "domain", "ats", "token", "funding_stage", "funding_evidence_url",
                                  "sales_roles_open", "jobs_listed", "newest_post_date", "qualified", "reason"], seed)
    write_csv(DATA / "posts.csv", ["company", "ats", "job_id", "title", "url", "posted_date", "collection_date",
                                   "location", "is_ambiguous_title", "ambiguous_family"], posts)
    (DISCOVERY / "board_pass_domains.txt").write_text("\n".join(board_pass), encoding="utf-8")
    names = {c["domain"]: c["company"] for c in cands}
    todo = [f"{names[d]} | {d}" for d in board_pass if d not in funding]
    (DISCOVERY / "funding_todo.txt").write_text("\n".join(todo), encoding="utf-8")
    print("funding todo:", len(todo))
    nq = sum(1 for s in seed if s["qualified"])
    na = sum(1 for p in posts if p["is_ambiguous_title"])
    print(f"candidates={len(cands)} board_pass={len(board_pass)} qualified={nq} posts={len(posts)} ambiguous={na}")


if __name__ == "__main__":
    main()
