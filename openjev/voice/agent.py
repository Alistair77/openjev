"""Push-to-talk loop: hotkey toggles continuous listening; every utterance is
classified and executed immediately.

Heavy imports (pynput, speech_recognition) happen inside `start()` so importing
this module — and running `--text` mode — never needs a microphone or permissions.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from openjev.backends.local import LocalHeuristicBackend
from openjev.models import EvaluateRequest
from openjev.voice.actions import MacActions
from openjev.voice.commands import INTENT_QUESTION, build_action, extract_slots

DEFAULT_HOTKEY = "<cmd>+<shift>+v"
DEFAULT_CONFIDENCE = 0.30


def parse_hotkey(spec: str) -> str:
    """Validate a pynput GlobalHotKeys spec like `<cmd>+<shift>+v`."""
    if not re.fullmatch(r"[<>\w+ ]+", spec) or "+" not in spec:
        raise ValueError(f"hotkey must look like '<cmd>+<shift>+v', got {spec!r}")
    return spec


def classify(text: str, confidence_threshold: float = DEFAULT_CONFIDENCE) -> dict[str, Any]:
    """Classify one utterance: intent + slots + executable action (or abstain)."""
    request = EvaluateRequest.model_validate(
        {"state": text, "questions": INTENT_QUESTION,
         "options": {"abstain_below": confidence_threshold, "top_k": 2}}
    )
    answer = asyncio.run(LocalHeuristicBackend().evaluate(request)).answers["intent"]
    if answer.abstained:
        return {"intent": None, "confidence": answer.confidence,
                "action": {"action": "unheard", "heard": text}}
    intent = answer.choice
    slots = extract_slots(text, intent)
    return {"intent": intent, "confidence": answer.confidence,
            "probabilities": answer.probabilities,
            "action": build_action(intent, slots, text)}


class VoiceAgent:
    """Toggle-listening voice agent. `start()` blocks until Ctrl-C."""

    def __init__(self, hotkey: str = DEFAULT_HOTKEY, live: bool = False,
                 confidence: float = DEFAULT_CONFIDENCE,
                 stt: str = "sphinx", allowed_apps: set[str] | None = None) -> None:
        self.hotkey = parse_hotkey(hotkey)
        self.actions = MacActions(live=live, allowed_apps=allowed_apps)
        self.confidence = confidence
        self.stt = stt
        self.listening = False
        self._stop_background = None

    # -- text mode (no mic; demo + tests of the full pipeline) -------------
    def handle_text(self, text: str) -> dict[str, Any]:
        """Classify + execute one typed utterance. Returns the full report."""
        result = classify(text, self.confidence)
        report = self.actions.run(result["action"])
        return {"heard": text, "intent": result["intent"],
                "confidence": round(result["confidence"], 3) + 0.0,  # avoid -0.0 display
                "report": report}

    def run_text_mode(self) -> None:
        print("text mode: type commands, empty line quits. "
              f"{'LIVE — actions execute!' if self.actions.live else 'dry-run — nothing executes.'}")
        while True:
            try:
                text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                break
            outcome = self.handle_text(text)
            print(f"jev> intent={outcome['intent']} conf={outcome['confidence']} -> {outcome['report']['detail']}")

    # -- live microphone mode ----------------------------------------------
    def start(self) -> None:
        from pynput import keyboard

        print(f"push-to-talk: press {self.hotkey} to start/stop listening. Ctrl-C quits. "
              f"{'LIVE' if self.actions.live else 'dry-run (add --live to execute)'}")
        with keyboard.GlobalHotKeys({self.hotkey: self.toggle}):
            try:
                import time
                while True:
                    time.sleep(0.2)
            except KeyboardInterrupt:
                self._stop_listening()

    def toggle(self) -> None:
        if self.listening:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self) -> None:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        with mic:
            recognizer.adjust_for_ambient_noise(mic, duration=0.5)
        print("listening... speak now. Hotkey again to stop.")

        def callback(_recognizer, audio) -> None:
            try:
                if self.stt == "google":
                    text = _recognizer.recognize_google(audio)
                else:
                    text = _recognizer.recognize_sphinx(audio)
            except (sr.UnknownValueError, sr.RequestError) as error:  # stay listening either way
                print(f"(didn't catch that: {error})")
                return
            if not text.strip():
                return
            outcome = self.handle_text(text)
            print(f"heard> {text}\njev> intent={outcome['intent']} "
                  f"conf={outcome['confidence']} -> {outcome['report']['detail']}")

        self._stop_background = recognizer.listen_in_background(mic, callback)
        self.listening = True

    def _stop_listening(self) -> None:
        if self._stop_background is not None:
            self._stop_background(wait_for_stop=False)
            self._stop_background = None
        if self.listening:
            print("stopped listening.")
        self.listening = False
