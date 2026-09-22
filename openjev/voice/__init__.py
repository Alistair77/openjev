"""Push-to-talk voice control for macOS.

Press the hotkey once: continuous voice input starts. Speak commands, each
utterance is classified by OpenJev and executed immediately — no per-command
confirmation. Press the hotkey again: listening stops.

Optional dependency set (`pip install -e '.[voice]'`); everything in
:mod:`openjev.voice.commands` and dry-run actions works without a microphone.
"""

from openjev.voice.commands import APPS, VOICE_INTENTS, build_action, extract_slots

__all__ = ["APPS", "VOICE_INTENTS", "build_action", "extract_slots"]
