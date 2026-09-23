"""Overlay state machine for the push-to-talk agent.

States: IDLE -> LISTENING -> TRANSCRIBING -> EXECUTING -> SUCCESS | ERROR,
then back to LISTENING (still toggled on) or IDLE (toggled off).

Anything unheard-of returns TRANSCRIBING -> LISTENING directly: the overlay
never shows success or failure for something it did not attempt.
"""

from __future__ import annotations

import enum


class VoiceState(enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"


_TRANSITIONS: dict[VoiceState, set[VoiceState]] = {
    VoiceState.IDLE: {VoiceState.LISTENING},
    VoiceState.LISTENING: {VoiceState.TRANSCRIBING, VoiceState.IDLE},
    VoiceState.TRANSCRIBING: {VoiceState.EXECUTING, VoiceState.LISTENING, VoiceState.IDLE},
    VoiceState.EXECUTING: {VoiceState.SUCCESS, VoiceState.ERROR, VoiceState.IDLE},
    VoiceState.SUCCESS: {VoiceState.LISTENING, VoiceState.IDLE},
    VoiceState.ERROR: {VoiceState.LISTENING, VoiceState.IDLE},
}


def transition(current: VoiceState, nxt: VoiceState) -> VoiceState:
    """Guard a state change; raises ValueError on illegal transitions."""
    allowed = _TRANSITIONS.get(current, set())
    if nxt not in allowed:
        raise ValueError(f"illegal voice transition: {current.value} -> {nxt.value}")
    return nxt


def legal_next(current: VoiceState) -> set[VoiceState]:
    """States reachable from `current` (for tests and UI hints)."""
    return set(_TRANSITIONS.get(current, set()))
