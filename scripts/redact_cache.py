"""Redact emails / recruiter names in every cached board payload in place, keeping each file's
mtime (qualify.py reads mtime as the collection date). Usage: python -I scripts/redact_cache.py"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE  # noqa: E402
from qualify import redact  # noqa: E402

n = 0
for f in CACHE.glob("*.json"):
    st = f.stat()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        continue
    f.write_text(json.dumps(redact(data), ensure_ascii=False), encoding="utf-8")
    os.utime(f, (st.st_atime, st.st_mtime))
    n += 1
print(f"redacted {n} cached payloads")
