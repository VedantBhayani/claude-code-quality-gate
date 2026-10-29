"""Hand-labelling tools: blank sheet export, sheet validation, blind re-label draw,
and a resumable terminal labelling session. Stdlib only, no network.

The sheet is a CSV holding post metadata and labels only. Post text never goes in
it; the terminal session shows text from the local posts file (the cache).
The guide the labeller follows is evals/labelling/guide.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import TextIO

from quality_gate.types import SIGNAL_TYPES, HandLabel, Post

COLUMNS: tuple[str, ...] = (
    "post_id", "url", "company", "title", "post_date", "collection_date",
    "signal", "signal_type", "labelled_on", "notes",
)


class SheetError(ValueError):
    """A filled sheet failed validation. .problems lists every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("labelling sheet is invalid:\n" + "\n".join(f"- {p}" for p in problems))


def _write_rows(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def read_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise SheetError([f"header must be {','.join(COLUMNS)}; got {','.join(reader.fieldnames or [])}"])
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if len(value) == 10 else None
    except ValueError:
        return None


def blank_row(post: Post) -> dict[str, str]:
    return {
        "post_id": post.post_id, "url": post.url, "company": post.company, "title": post.title,
        "post_date": post.post_date.isoformat(), "collection_date": post.collection_date.isoformat(),
        "signal": "", "signal_type": "", "labelled_on": "", "notes": "",
    }


def export_sheet(posts: Iterable[Post], path: Path) -> None:
    """Write a blank labelling sheet: URL, company, title, dates; no post text."""
    _write_rows(path, (blank_row(p) for p in posts))


def validate_sheet(path: Path, expected_post_ids: Sequence[str]) -> list[HandLabel]:
    """Return the sheet's labels in sheet order, or raise SheetError listing every problem."""
    rows = read_rows(path)
    problems: list[str] = []
    labels: list[HandLabel] = []
    expected = set(expected_post_ids)
    seen: set[str] = set()
    for row in rows:
        pid = row["post_id"]
        if pid in seen:
            problems.append(f"{pid}: duplicate row")
            continue
        seen.add(pid)
        if pid not in expected:
            problems.append(f"{pid}: unexpected row (not in the sample)")
            continue
        signal = row["signal"].lower()
        if signal not in ("yes", "no"):
            problems.append(f"{pid}: signal must be yes or no; got {row['signal']!r}")
            continue
        try:
            labels.append(HandLabel(post_id=pid, signal=signal == "yes", signal_type=row["signal_type"]))
        except ValueError as e:
            problems.append(f"{pid}: {e}")
            continue
        if parse_day(row["labelled_on"]) is None:
            problems.append(f"{pid}: labelled_on must be an ISO date (YYYY-MM-DD); got {row['labelled_on']!r}")
    missing = [pid for pid in expected_post_ids if pid not in seen]
    if missing:
        problems.append(f"missing rows for {len(missing)} post(s): {', '.join(missing)}")
    if problems:
        raise SheetError(problems)
    return labels


RELABEL_SIZE = 50
RELABEL_MIN_DAYS = 3
# Fixed seed for the blind re-label draw (next after the seeds in config/gate.toml).
RELABEL_SEED = 20261025


class RelabelError(RuntimeError):
    """The blind re-label set cannot be drawn yet (too soon, or pass 1 not valid)."""


def draw_relabel(
    pass1_sheet: Path,
    expected_post_ids: Sequence[str],
    out_path: Path,
    *,
    today: date,
    n: int = RELABEL_SIZE,
    seed: int = RELABEL_SEED,
) -> list[str]:
    """Draw n posts from a valid, complete pass-1 sheet into a blank sheet at out_path.

    Pass-1 labels are not copied. Refuses unless today is at least 3 days after
    the latest pass-1 labelled_on date. Returns the drawn post IDs in sheet order.
    """
    try:
        labels = validate_sheet(pass1_sheet, expected_post_ids)
    except SheetError as e:
        raise RelabelError(f"pass-1 sheet is not valid and complete; fix it first.\n{e}") from e
    rows = {r["post_id"]: r for r in read_rows(pass1_sheet)}
    last = max(date.fromisoformat(rows[lab.post_id]["labelled_on"]) for lab in labels)
    earliest = last + timedelta(days=RELABEL_MIN_DAYS)
    if today < earliest:
        raise RelabelError(
            f"blind re-label must start at least {RELABEL_MIN_DAYS} days after pass 1 "
            f"(last pass-1 label {last.isoformat()}); earliest start is {earliest.isoformat()}"
        )
    if len(labels) < n:
        raise RelabelError(f"pass 1 has {len(labels)} posts; cannot draw {n}")
    drawn = random.Random(seed).sample(sorted(rows), n)
    keep = ("post_id", "url", "company", "title", "post_date", "collection_date")
    _write_rows(out_path, ({c: (rows[pid][c] if c in keep else "") for c in COLUMNS} for pid in drawn))
    return drawn


SIGNAL_TYPE_KEYS: dict[str, str] = {str(i): t for i, t in enumerate(SIGNAL_TYPES[:-1], start=1)}
TEXT_PREVIEW_CHARS = 4000


def _ask_until(ask: Callable[[str], str], prompt: str, valid: Sequence[str]) -> tuple[str, str]:
    """Ask until the first word is valid. Returns (answer, note): text after the answer is a note."""
    while True:
        first, _, note = ask(prompt).strip().partition(" ")
        if first.lower() in valid:
            return first.lower(), note.strip()


def run_session(
    sheet: Path,
    posts: Iterable[Post],
    *,
    today: date,
    prior: Mapping[str, HandLabel] | None = None,
    blind: bool = False,
    ask: Callable[[str], str] = input,
    out: TextIO | None = None,
) -> int:
    """Label every unlabelled row of `sheet` in the terminal, saving after each label.

    Resumable: rows already labelled are skipped, so quitting (q, Ctrl-D/Ctrl-Z)
    and re-running picks up where it stopped. Post text comes from `posts` (the
    local cache) and is never written to the sheet. Outside blind mode, a label
    in `prior` (e.g. pass 1, when re-labelling disputed items) is shown; in blind
    mode it never is. Returns the number of posts labelled in this session.
    """
    out = out or sys.stdout
    by_id = {p.post_id: p for p in posts}
    shown_prior = {} if blind else dict(prior or {})
    rows = read_rows(sheet)
    todo = [i for i, r in enumerate(rows) if not r["signal"]]
    menu = "  ".join(f"{k}={t}" for k, t in SIGNAL_TYPE_KEYS.items())
    done = 0
    for n, i in enumerate(todo, start=1):
        row = rows[i]
        post = by_id.get(row["post_id"])
        print(f"\n=== {n}/{len(todo)} unlabelled ({len(rows) - len(todo) + done} of {len(rows)} done) ===", file=out)
        print(f"{row['title']}  |  {row['company']}  |  posted {row['post_date']}, "
              f"collected {row['collection_date']}", file=out)
        print(row["url"], file=out)
        if row["post_id"] in shown_prior:
            p = shown_prior[row["post_id"]]
            print(f"Prior label: {'yes' if p.signal else 'no'} / {p.signal_type}", file=out)
        if post is None:
            print("[post text not in the local cache: open the URL]", file=out)
        else:
            text = post.text if len(post.text) <= TEXT_PREVIEW_CHARS else (
                post.text[:TEXT_PREVIEW_CHARS] + "\n[truncated: open the URL for the rest]")
            print("-" * 60, file=out)
            print(text, file=out)
            print("-" * 60, file=out)
        try:
            answer, note = _ask_until(ask, "Signal? y=yes  n=no  q=quit  (optional note after a space) > ",
                                      ("y", "n", "q"))
            if answer == "q":
                break
            if answer == "n":
                signal_type = "not_signal"
            else:
                key, type_note = _ask_until(ask, f"Type? {menu} > ", tuple(SIGNAL_TYPE_KEYS))
                signal_type = SIGNAL_TYPE_KEYS[key]
                note = " ".join(x for x in (note, type_note) if x)
        except (EOFError, KeyboardInterrupt):
            break
        row["signal"] = "yes" if answer == "y" else "no"
        row["signal_type"] = signal_type
        row["labelled_on"] = today.isoformat()
        row["notes"] = note
        _write_rows(sheet, rows)
        done += 1
    print(f"\nLabelled {done} this session; sheet saved to {sheet}", file=out)
    return done


def load_posts(path: Path) -> list[Post]:
    """Read the local post cache: one JSON object per line with Post's fields (ISO dates)."""
    posts = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            d["post_date"] = date.fromisoformat(d["post_date"])
            d["collection_date"] = date.fromisoformat(d["collection_date"])
            posts.append(Post(**d))
    return posts


def _expected_ids(path: Path) -> list[str]:
    if Path(path).suffix == ".csv":
        return [r["post_id"] for r in read_rows(path)]
    return [p.post_id for p in load_posts(path)]


def _labels_in(sheet: Path) -> dict[str, HandLabel]:
    labels = {}
    for r in read_rows(sheet):
        try:
            labels[r["post_id"]] = HandLabel(r["post_id"], r["signal"].lower() == "yes", r["signal_type"])
        except ValueError:
            pass
    return labels


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m quality_gate.labels",
        description="Hand-labelling tools. Follow evals/labelling/guide.md. Post text is read from the "
                    "local posts JSONL and never written to a sheet.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export", help="write a blank labelling sheet for the posts")
    p.add_argument("--posts", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("label", help="label unlabelled rows in the terminal (resumable)")
    p.add_argument("--posts", required=True)
    p.add_argument("--sheet", required=True)
    p.add_argument("--blind", action="store_true", help="never show prior labels (re-label pass)")
    p.add_argument("--prior", help="a labelled sheet whose labels are shown (not allowed with --blind)")
    p.add_argument("--today", type=date.fromisoformat, default=None)
    p = sub.add_parser("validate", help="check a filled sheet: every expected post once, valid labels")
    p.add_argument("--sheet", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--posts", help="expected posts: the posts JSONL")
    group.add_argument("--expected", help="expected posts: a posts JSONL or a sheet CSV")
    p = sub.add_parser("draw-relabel", help="draw the blind 50-post re-label sheet (>= 3 days after pass 1)")
    p.add_argument("--posts", required=True)
    p.add_argument("--pass1", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--today", type=date.fromisoformat, default=None)
    p.add_argument("--n", type=int, default=RELABEL_SIZE)
    p.add_argument("--seed", type=int, default=RELABEL_SEED)
    args = parser.parse_args(argv)
    today = getattr(args, "today", None) or date.today()
    # Post text carries emoji; Git Bash on Windows hands Python a cp1252 stdout.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        if args.cmd == "export":
            posts = load_posts(args.posts)
            export_sheet(posts, Path(args.out))
            print(f"wrote blank sheet with {len(posts)} rows to {args.out}")
        elif args.cmd == "label":
            if args.blind and args.prior:
                print("--blind never shows prior labels; drop --prior", file=sys.stderr)
                return 2
            prior = _labels_in(Path(args.prior)) if args.prior else None
            run_session(Path(args.sheet), load_posts(args.posts), today=today, prior=prior, blind=args.blind)
        elif args.cmd == "validate":
            labels = validate_sheet(Path(args.sheet), _expected_ids(Path(args.posts or args.expected)))
            yes = sum(lab.signal for lab in labels)
            print(f"ok: {len(labels)} labels ({yes} signal yes, {len(labels) - yes} no)")
        elif args.cmd == "draw-relabel":
            drawn = draw_relabel(Path(args.pass1), _expected_ids(Path(args.posts)), Path(args.out),
                                 today=today, n=args.n, seed=args.seed)
            print(f"wrote blind re-label sheet with {len(drawn)} rows to {args.out}")
    except (SheetError, RelabelError) as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
