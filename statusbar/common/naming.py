#!/usr/bin/env python3
from __future__ import annotations

import re

JIRA_TICKET_RE = re.compile(r"[A-Z]+-\d+")

SEPARATORS = set("-_/. ")

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "\U000020E3"             # combining enclosing keycap
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000231A-\U0000231B"  # watch/hourglass
    "\U00002934-\U00002935"  # arrows
    "\U000025AA-\U000025AB"  # squares
    "\U000025FB-\U000025FE"  # squares
    "\U00002B05-\U00002B07"  # arrows
    "\U00002B1B-\U00002B1C"  # squares
    "\U00002B50"             # star
    "\U00002B55"             # circle
    "\U00003030"             # wavy dash
    "\U0000303D"             # part alternation mark
    "\U00003297"             # circled ideograph congratulation
    "\U00003299"             # circled ideograph secret
    "]+",
    flags=re.UNICODE,
)


def clean_title(title: str) -> str:
    """Remove emojis, CJK brackets, collapse whitespace, and strip."""
    title = EMOJI_RE.sub("", title)
    title = title.replace("\u300c", "").replace("\u300d", "")
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def strip_prefix_and_jira(name: str, keep_number: bool = False) -> str:
    """Strip prefix and JIRA project key.

    With keep_number=True, retains the ticket number
    (e.g. 'ofirg-DR-1299-fix-bug' -> '1299-fix-bug').
    Otherwise drops it (e.g. 'ofirg-DR-1299-fix-bug' -> 'fix-bug').
    """
    m = JIRA_TICKET_RE.search(name)
    if m:
        ticket = m.group()
        number = ticket.split("-", 1)[1]
        rest = name[m.end():].lstrip("-_ ")
        if keep_number:
            return f"{number}-{rest}" if rest else number
        return rest or name
    return name


def longest_common_prefix(names: list[str]) -> str:
    """Find the longest separator-terminated prefix shared by at least 2 names.

    Collects every prefix that ends at a separator character from each name,
    then returns the longest one that appears in at least 2 names.
    """
    if len(names) < 2:
        return ""
    prefix_counts: dict[str, int] = {}
    for name in names:
        seen: set[str] = set()
        for i, ch in enumerate(name):
            if ch in SEPARATORS:
                prefix = name[: i + 1]
                if prefix not in seen:
                    seen.add(prefix)
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    best = ""
    for prefix, count in prefix_counts.items():
        if count >= 2 and len(prefix) > len(best):
            best = prefix
    return best
