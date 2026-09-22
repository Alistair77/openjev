"""Email body cleaning for decision states.

Ported from NandhaKishorM/laya (`laya/email.py`, Apache-2.0): strip quoted
history, signatures, and disclaimer boilerplate so the state handed to a
backend is the sender's actual request, not the thread footer.
"""

from __future__ import annotations

import re

_QUOTE_HEADERS = [
    re.compile(r"^\s*On .{0,300}wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*(Original|Forwarded) Message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^\s*_{8,}\s*$"),
    re.compile(r"^\s*From:\s.+$", re.IGNORECASE),
]
_SIGNATURE_MARKERS = [
    re.compile(r"^\s*--\s*$"),
    re.compile(r"^\s*(best|kind|warm|many thanks|thanks|thank you|regards|cheers|sincerely)[\w ,!.]*$", re.IGNORECASE),
    re.compile(r"^\s*sent from my (iphone|android|mobile|ipad)", re.IGNORECASE),
]
_DISCLAIMER = re.compile(
    r"(confidential|intended (solely )?for the (use of the )?(named )?(addressee|recipient)|"
    r"if you (have )?received this (e-?mail|message) in error)",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _strip_disclaimer(paragraph: str) -> str:
    if not _DISCLAIMER.search(paragraph):
        return paragraph
    parts = [piece.strip() for piece in _SENTENCE.split(paragraph) if piece.strip()]
    return " ".join(piece for piece in parts if not _DISCLAIMER.search(piece))


def clean_email_body(body: str, max_chars: int = 3000) -> str:
    """Remove quoted history, signatures, and disclaimers; cap length."""
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
    lines = []
    for line in text.split("\n"):
        if any(pattern.match(line) for pattern in _QUOTE_HEADERS) and lines:
            break
        if line.lstrip().startswith(">"):
            continue
        lines.append(line.rstrip())
    cut = len(lines)
    for index in range(max(1, min(int(len(lines) * 0.6), len(lines) - 8)), len(lines)):
        if len(lines[index].strip()) <= 40 and any(
            pattern.match(lines[index]) for pattern in _SIGNATURE_MARKERS
        ):
            cut = index
            break
    cleaned = "\n".join(lines[:cut])
    paragraphs = [_strip_disclaimer(paragraph) for paragraph in cleaned.split("\n\n")]
    cleaned = "\n\n".join(paragraph for paragraph in paragraphs if paragraph.strip())
    return cleaned[:max_chars]
