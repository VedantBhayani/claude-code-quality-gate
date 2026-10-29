"""Run prompts. Signal: one post + its collection date + Frontal's offer wording.
Draft (Part B): one account + its signal + the offer wording. Nothing else."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from quality_gate.types import Post

# Part B output shape. Lives here because only the runner asks for drafts.
DRAFT_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "body"],
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
}


def read_offer_wording(path: Path) -> str:
    """The offer text of config/facts/offer.md: everything from the first
    'Source:' line on (front matter, title and usage note dropped), verbatim."""
    lines = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Source:"):
            return "\n".join(lines[i:]).strip() + "\n"
    raise ValueError(f"{path}: no 'Source:' line marks the start of the offer wording")


def signal_prompt(post: Post, offer: str) -> str:
    return (
        "Score this one job post as a buying signal for the offer below, following your instructions.\n"
        f"Collection date (measure the signal's age from this date): {post.collection_date.isoformat()}\n\n"
        "## Offer\n"
        f"{offer.strip()}\n\n"
        "## Job post\n"
        f"Company: {post.company}\n"
        f"Title: {post.title}\n"
        f"URL: {post.url}\n"
        f"Posted: {post.post_date.isoformat()}\n\n"
        f"{post.text.strip()}\n"
    )


# Filled from the lead list at send time. The prompt fixes them so no draft names a real person.
DRAFT_MERGE_FIELDS = frozenset({"{{firstName}}", "{{senderName}}"})


def draft_prompt(*, company: str, domain: str, role_title: str, evidence: Sequence[str], offer: str) -> str:
    quotes = "\n".join(f'- "{q}"' for q in evidence)
    return (
        "Write one cold email to this account about the signal below, following your instructions.\n"
        "Use only the offer wording below; add no numbers or claims about the sender.\n"
        "Greet the recipient as {{firstName}} and sign off with {{senderName}} on the last line. Use no other name "
        "for the sender or the recipient, and no other placeholder.\n\n"
        "## Offer\n"
        f"{offer.strip()}\n\n"
        "## Account\n"
        f"Company: {company}\n"
        f"Domain: {domain}\n\n"
        "## Signal\n"
        f"Hiring: {role_title}\n"
        f"Evidence from the job post:\n{quotes}\n"
    )
