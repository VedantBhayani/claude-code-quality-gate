"""Print a short company blurb from each board in funding_todo.txt (or given domains) so a human can
confirm the board belongs to the listed company. Usage: python -I scripts/peek.py [domain ...]"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DISCOVERY, jobs_of, text_of  # noqa: E402

want = sys.argv[1:] or [l.split("|")[1].strip() for l in
                        (DISCOVERY / "funding_todo.txt").read_text(encoding="utf-8").splitlines() if "|" in l]
rows = {}
for line in (DISCOVERY / "probe_log.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r.get("kind") == "company" and r.get("ats"):
        rows[r["domain"]] = r
for d in want:
    r = rows.get(d)
    if not r:
        print(d, "-> no board")
        continue
    p = json.loads((CACHE / f"{r['ats']}-{r['token']}.json").read_text(encoding="utf-8"))
    jobs = jobs_of(r["ats"], p)
    t = re.sub(r"\s+", " ", text_of(r["ats"], jobs[0]) if jobs else "")
    print(f"{r['company']} | {d} | {r['ats']}:{r['token']} | {t[:260].encode('ascii', 'replace').decode()}")
