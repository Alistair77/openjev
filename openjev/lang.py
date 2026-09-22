"""Dependency-free script/language detection for decision states.

Ported from NandhaKishorM/laya (`laya/lang.py`, Apache-2.0). Purpose here is
narrower than Laya's checkpoint routing: our lexical backend only reads
English-like text, so a non-Latin state is flagged in the audit trace as a
reliability warning instead of silently scoring noise. Script detection is
exact; the Latin language guess is explicitly best-effort.
"""

from __future__ import annotations

import re
from typing import Any

_SCRIPT_RANGES = [
    ("greek", ((0x0370, 0x03FF), (0x1F00, 0x1FFF))),
    ("cyrillic", ((0x0400, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F))),
    ("armenian", ((0x0530, 0x058F),)),
    ("hebrew", ((0x0590, 0x05FF),)),
    ("arabic", ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))),
    ("devanagari", ((0x0900, 0x097F), (0xA8E0, 0xA8FF))),
    ("bengali", ((0x0980, 0x09FF),)),
    ("gurmukhi", ((0x0A00, 0x0A7F),)),
    ("gujarati", ((0x0A80, 0x0AFF),)),
    ("tamil", ((0x0B80, 0x0BFF),)),
    ("telugu", ((0x0C00, 0x0C7F),)),
    ("thai", ((0x0E00, 0x0E7F),)),
    ("myanmar", ((0x1000, 0x109F),)),
    ("ethiopic", ((0x1200, 0x137F),)),
    ("khmer", ((0x1780, 0x17FF),)),
    ("hangul", ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))),
    ("kana", ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF))),
    ("han", ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))),
]

_STOP = {
    "en": {"the", "and", "is", "are", "was", "were", "to", "of", "in", "for", "with", "that",
           "this", "it", "you", "have", "has", "not", "but", "on", "at", "be", "as", "from",
           "will", "can", "would", "there", "their", "what", "which", "please", "we", "i"},
    "fr": {"le", "la", "les", "des", "une", "est", "pour", "dans", "que", "qui", "avec", "sur",
           "pas", "plus", "nous", "vous", "mais", "sont", "ont", "ce"},
    "de": {"der", "die", "das", "und", "ist", "ein", "eine", "den", "dem", "nicht", "mit",
           "auf", "von", "zu", "sich", "auch", "werden", "haben", "sind", "oder", "aber"},
    "es": {"el", "los", "las", "que", "por", "con", "para", "una", "es", "se", "del", "como",
           "pero", "son", "este", "esta", "todo", "hay"},
}
_NON_EN_DIACRITICS = set(
    "àâäãáåçéèêëíìîïñóòôöõøúùûüýÿßæœ"
    "ăâîșțşţ"
    "ąćęłńśźż"
    "čďěňřšťůž"
    "őű"
    "ğı"
    "āēģīķļņūž"
    "đ"
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
NON_EN_DIACRITIC_RATE = 0.02


def _iter_text(state: Any, _depth: int = 0) -> list[str]:
    if _depth > 6 or state is None:
        return []
    if isinstance(state, str):
        return [state]
    if isinstance(state, dict):
        out: list[str] = []
        for value in state.values():
            out.extend(_iter_text(value, _depth + 1))
        return out
    if isinstance(state, (list, tuple)):
        out = []
        for value in state:
            out.extend(_iter_text(value, _depth + 1))
        return out
    return []


def state_text(state: Any, max_chars: int = 4000) -> str:
    """Flatten a state into detection text (keys ignored: usually English)."""
    return " ".join(_iter_text(state))[:max_chars]


def detect_script(text: str) -> str:
    """Dominant script: 'latin', 'han', 'devanagari', ... or 'unknown'."""
    counts: dict[str, int] = {}
    latin = 0
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        if code < 0x0250 or 0x1E00 <= code <= 0x1EFF:
            latin += 1
            continue
        for name, ranges in _SCRIPT_RANGES:
            if any(low <= code <= high for low, high in ranges):
                counts[name] = counts.get(name, 0) + 1
                break
    counts["latin"] = latin
    if sum(counts.values()) == 0:
        return "unknown"
    return max(counts.items(), key=lambda item: item[1])[0]


def guess_latin_language(text: str) -> str | None:
    """Best-effort language code for Latin text, None when undecided."""
    words = [word.lower() for word in _WORD.findall(text)]
    lowered = text.lower()
    diacritic_rate = sum(1 for char in lowered if char in _NON_EN_DIACRITICS) / max(1, len(lowered))
    non_english = diacritic_rate >= NON_EN_DIACRITIC_RATE
    if len(words) < 4:
        return None
    scores = {lang: sum(1 for word in words if word in stop) for lang, stop in _STOP.items()}
    english = scores.get("en", 0)
    best_lang, best = max(
        ((lang, score) for lang, score in scores.items() if lang != "en"),
        key=lambda item: item[1],
        default=(None, 0),
    )
    if best == 0:
        best_lang = None
    if best_lang and best >= max(2, english + 2):
        return best_lang
    if best_lang and non_english and best >= max(2, english):
        return best_lang
    if english and not non_english:
        return "en"
    return None


def analyse(state: Any) -> dict[str, Any]:
    """Detection result: script, language (maybe None), is_english flag."""
    text = state_text(state)
    script = detect_script(text)
    if script == "unknown":
        return {"script": "unknown", "language": None, "is_english": True,
                "language_undecided": True, "non_latin_fraction": 0.0}
    if script != "latin":
        profile = _script_profile(text)
        return {"script": script, "language": None, "is_english": False,
                "language_undecided": True,
                "non_latin_fraction": round(1.0 - profile.get("latin", 0.0), 4)}
    language = guess_latin_language(text)
    lowered = text.lower()
    diacritic_rate = sum(1 for char in lowered if char in _NON_EN_DIACRITICS) / max(1, len(lowered))
    undecided = language is None
    english = language == "en" or (undecided and diacritic_rate < NON_EN_DIACRITIC_RATE)
    return {"script": "latin", "language": language, "is_english": english,
            "language_undecided": undecided,
            "non_latin_fraction": 0.0}


def _script_profile(text: str) -> dict[str, float]:
    counts: dict[str, float] = {"latin": 0}
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        if code < 0x0250 or 0x1E00 <= code <= 0x1EFF:
            counts["latin"] += 1
            continue
        for name, ranges in _SCRIPT_RANGES:
            if any(low <= code <= high for low, high in ranges):
                counts[name] = counts.get(name, 0) + 1
                break
    total = sum(counts.values())
    return {key: value / total for key, value in counts.items() if value} if total else {}
