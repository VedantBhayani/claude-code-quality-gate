"""Step 1: resolve each listed company to a Greenhouse/Lever/Ashby board token.

Reads data/discovery/*.txt listings, probes slug variants on the three documented
public list endpoints (404 = miss), checks the board belongs to the company, caches
hit payloads in data/raw/_probe_cache/, logs every request to data/discovery/probe_log.jsonl.
Resumable. Usage: python -I scripts/probe.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DISCOVERY, ENDPOINTS, get, identity, norm  # noqa: E402

ORDER = ("ashby", "greenhouse", "lever")
PREFIXES = ("try", "get", "use", "with", "join", "go")


def parse_listings():
    rows, src, rnd = [], None, None
    for f in sorted(DISCOVERY.glob("*listings*.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                src, rnd = [x.strip() for x in line[1:].split("|")]
                continue
            parts = [x.strip() for x in line.split("|")]
            if len(parts) < 3:
                continue
            name, month, domain = parts[:3]
            rows.append(dict(company=name, round=rnd, round_month=month,
                             domain=domain.lower(), source_url=src))
    seen, out = set(), []
    for r in rows:  # first listing wins (later-stage pages may repeat a company)
        if r["domain"] in seen:
            continue
        seen.add(r["domain"])
        out.append(r)
    return out


def variants(name, domain):
    stem = domain.split(".")[0]
    v = [norm(name), stem]
    for p in PREFIXES:
        if stem.startswith(p) and len(stem) > len(p) + 2:
            v.append(stem[len(p):])
    v.append(re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"))
    out = []
    for x in v:
        if x and len(x) >= 3 and x not in out:
            out.append(x)
    return out[:3]  # capped to keep total requests (and runtime at >=1s spacing) bounded


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    log_path = DISCOVERY / "probe_log.jsonl"
    done = set()
    retry = "--retry-errors" in sys.argv  # re-probe misses where any request hit a network error
    if log_path.exists():
        buf_err = False
        for line in log_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("kind") == "request":
                buf_err = buf_err or str(r["status"]).startswith("ERR") or r["status"] in (429, 500, 502, 503, 504)
                continue
            if r.get("kind") == "company":
                if retry and buf_err and not r.get("ats"):
                    done.discard(r["domain"])
                else:
                    done.add(r["domain"])
                buf_err = False
    companies = parse_listings()
    print(f"{len(companies)} unique companies, {len(done)} already probed", flush=True)
    with log_path.open("a", encoding="utf-8") as log:
        for c in companies:
            if c["domain"] in done:
                continue
            result = dict(kind="company", **c, ats=None, token=None, identity=None, tries=0)
            fallback = None
            for v in variants(c["company"], c["domain"]):
                for ats in ORDER:
                    url = ENDPOINTS[ats].format(t=v)
                    status, body = get(url)
                    result["tries"] += 1
                    log.write(json.dumps(dict(kind="request", url=url, status=status)) + "\n")
                    if status != 200 or body is None:
                        continue
                    try:
                        payload = json.loads(body)
                    except ValueError:
                        continue
                    idn = identity(ats, payload, c["company"], c["domain"])
                    if idn == "mismatch":
                        continue
                    (CACHE / f"{ats}-{v}.json").write_bytes(body)
                    hit = dict(ats=ats, token=v, identity=idn, probe_url=url)
                    if idn in ("gh_company_name", "domain_in_text", "name_in_text"):
                        result.update(hit)
                        break
                    fallback = fallback or hit
                if result["ats"]:
                    break
            if not result["ats"] and fallback:
                result.update(fallback)
            log.write(json.dumps(result) + "\n")
            log.flush()
            print(c["company"], result["ats"], result["token"], result["identity"], flush=True)


if __name__ == "__main__":
    main()
