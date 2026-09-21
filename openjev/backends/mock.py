from __future__ import annotations

from openjev.backends.local import LocalHeuristicBackend


class MockBackend(LocalHeuristicBackend):
    """A deterministic backend with no network or model dependency."""

    name = "mock"
    model = "mock-deterministic-v1"
