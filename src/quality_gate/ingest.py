"""Ingest: the data agent's collection (layout in config/facts/data.toml) -> Posts.

  ingest(seed_csv, raw_dir)  qualified seed rows + raw/<ats>-<token>-<date>.json -> redacted Posts,
                             each stamped with its raw file's collection date
  sales_ish(posts, cfg)      the posts config/title_filter.toml keeps (the gate's population)
  write_posts(path, posts)   the local post cache (data/posts/posts.jsonl; holds text, never published)
  write_fixture(...)         evals/fixtures/posts.csv: URLs + metadata + sample membership, no text

Rebuild (from builds/quality-gate/):
  python -m quality_gate.ingest posts
  python -m quality_gate sample --natural 200 --ambiguous 80 --pilot 20
  python -m quality_gate.ingest fixture
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Sequence

from .collector import Board, parse_board
from .config import PACKAGE_ROOT, Config, MissingFactError, load_config
from .gate import SampleIds, read_samples
from .labels import load_posts
from .sampler import classify_title
from .types import Post

RAW_NAME = re.compile(r"^(ashby|greenhouse|lever)-(.+)-(\d{4}-\d{2}-\d{2})\.json$")


class IngestError(ValueError):
    """The seed list and the raw files do not line up."""


def qualified_boards(seed_csv: Path) -> dict[tuple[str, str], Board]:
    """(ats, token) -> Board for every seed row with qualified=True."""
    with Path(seed_csv).open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["qualified"].strip() == "True"]
    return {(r["ats"], r["token"]): Board(r["ats"], r["token"], r["company"], r["domain"]) for r in rows}


def ingest(seed_csv: Path, raw_dir: Path) -> list[Post]:
    """Every listed post of every qualified board, sorted by post_id."""
    boards = qualified_boards(seed_csv)
    files: dict[tuple[str, str], list[tuple[Path, date]]] = {}
    for path in sorted(Path(raw_dir).glob("*.json")):  # top level only: skips _probe_cache/
        m = RAW_NAME.match(path.name)
        if not m:
            raise IngestError(f"{path.name}: raw files must be named <ats>-<token>-<YYYY-MM-DD>.json")
        ats, token, collected = m.groups()
        if (ats, token) not in boards:
            raise IngestError(f"{path.name}: {ats}:{token} is not a qualified board in {Path(seed_csv).name}")
        files.setdefault((ats, token), []).append((path, date.fromisoformat(collected)))
    for (ats, token) in sorted(boards):
        found = files.get((ats, token), [])
        if not found:
            raise IngestError(f"no raw file for qualified board {ats}:{token} in {raw_dir}")
        if len(found) > 1:
            names = ", ".join(p.name for p, _ in found)
            raise IngestError(f"{ats}:{token} has {len(found)} raw files ({names}); keep exactly one")
    posts: list[Post] = []
    for key, [(path, collected)] in sorted(files.items()):
        payload = json.loads(path.read_text(encoding="utf-8"))
        posts += parse_board(boards[key], payload, collection_date=collected)
    return sorted(posts, key=lambda p: p.post_id)


def sales_ish(posts: list[Post], cfg: Config) -> list[Post]:
    """The posts whose title passes config/title_filter.toml (natural or ambiguous)."""
    rules = cfg.title_filter()
    return [p for p in posts if classify_title(p.title, rules)[0]]


def write_posts(path: Path, posts: list[Post]) -> None:
    """The local post cache read by labels.load_posts: one JSON object per line, ISO dates.

    ASCII-escaped, so U+2028/U+2029/U+0085 in post text cannot split a line for str.splitlines().
    """
    lines = [json.dumps({**asdict(p), "post_date": p.post_date.isoformat(),
                         "collection_date": p.collection_date.isoformat()}, ensure_ascii=True)
             for p in posts]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(line + "\n" for line in lines), encoding="utf-8", newline="\n")


FIXTURE_COLUMNS = ("post_id", "company", "domain", "ats", "title", "url", "post_date", "collection_date",
                   "ambiguous_family", "samples")


def write_fixture(path: Path, posts: list[Post], samples: SampleIds, cfg: Config) -> None:
    """The published evals/fixtures/posts.csv: URLs + metadata only, never post text.

    `samples` lists the samples a post is in (natural/ambiguous/opus/pilot, ';'-joined).
    """
    rules = cfg.title_filter()
    member = {name: set(ids) for name, ids in (("natural", samples.natural), ("ambiguous", samples.ambiguous),
                                               ("opus", samples.opus), ("pilot", samples.pilot))}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIXTURE_COLUMNS)
        for p in sorted(posts, key=lambda p: p.post_id):
            family = classify_title(p.title, rules)[1] or ""
            in_ = ";".join(name for name, ids in member.items() if p.post_id in ids)
            w.writerow([p.post_id, p.company, p.domain, p.ats, p.title, p.url, p.post_date.isoformat(),
                        p.collection_date.isoformat(), family, in_])


# ---------------------------------------------------------------- command line

FIXTURE_OUT = Path("evals") / "fixtures" / "posts.csv"


def _layout_path(cfg: Config, root: Path, given: Path | None, key: str) -> Path:
    """An explicit path, else FACT data.layout.<key> (relative to the package root)."""
    return Path(given) if given is not None else root / cfg.fact(f"data.layout.{key}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m quality_gate.ingest",
        description="Normalise the data agent's collection into the local post cache, and write the "
                    "published metadata-only fixture. Default paths come from config/facts/data.toml.")
    parser.add_argument("--config", type=Path, default=PACKAGE_ROOT, help="package root holding config/")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("posts", help="seed + raw list responses -> sales-ish posts JSONL (with text; local only)")
    p.add_argument("--seed", type=Path)
    p.add_argument("--raw", type=Path)
    p.add_argument("--out", type=Path)
    p = sub.add_parser("fixture", help="posts JSONL + samples.json -> evals/fixtures/posts.csv (no text)")
    p.add_argument("--posts", type=Path)
    p.add_argument("--samples", type=Path)
    p.add_argument("--out", type=Path)
    a = parser.parse_args(argv)
    root = Path(a.config)
    cfg = load_config(root)
    try:
        if a.cmd == "posts":
            seed = _layout_path(cfg, root, a.seed, "seed")
            posts = ingest(seed, _layout_path(cfg, root, a.raw, "raw_dir"))
            kept = sales_ish(posts, cfg)
            out = _layout_path(cfg, root, a.out, "posts_out")
            write_posts(out, kept)
            rules = cfg.title_filter()
            ambiguous = sum(1 for p in kept if classify_title(p.title, rules)[1])
            boards = len(qualified_boards(seed))
            print(f"wrote {out}: {len(kept)} sales-ish posts ({ambiguous} ambiguous) from {boards} boards; "
                  f"{len(posts)} listed posts in all")
        else:
            posts = load_posts(_layout_path(cfg, root, a.posts, "posts_out"))
            samples = read_samples(_layout_path(cfg, root, a.samples, "samples_out"))
            out = Path(a.out) if a.out is not None else root / FIXTURE_OUT
            write_fixture(out, posts, samples, cfg)
            print(f"wrote {out}: {len(posts)} posts, URLs + metadata only")
    except (IngestError, MissingFactError, FileNotFoundError) as e:
        print(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
