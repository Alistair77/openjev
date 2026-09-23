"""Focused-element check before typing (idea adapted from FluidVoice's
no-text-field detection; original implementation here, zero GPL code).

Rule: editable roles -> type; never-text roles (buttons, menus, static text)
-> refuse with a clear message and keep the transcript; anything else
(including "no Accessibility permission") -> unknown, proceed as before.
Never crashes, never blocks: any failure reads as unknown.
"""

from __future__ import annotations

from typing import Any

TEXT_ROLES = frozenset({"AXTextField", "AXTextArea", "AXComboBox", "AXSecureTextField"})

NEVER_TEXT_ROLES = frozenset({
    "AXButton", "AXMenu", "AXMenuItem", "AXMenuBar", "AXMenuBarItem",
    "AXStaticText", "AXImage", "AXLink", "AXSlider", "AXToolbar",
    "AXWindow", "AXSheet", "AXApplication", "AXScrollBar", "AXSplitter",
    "AXColorWell", "AXDisclosureTriangle",
})


def delivery_decision(role: str | None) -> str:
    """Pure verdict on an AX role: 'paste', 'refuse', or 'unknown'."""
    if role in TEXT_ROLES:
        return "paste"
    if role in NEVER_TEXT_ROLES:
        return "refuse"
    return "unknown"


def focused_target() -> dict[str, Any]:
    """Focused app + AX role of the focused element. Unknowns, never raises."""
    app_name: str | None = None
    try:
        from AppKit import NSWorkspace
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_name = front.localizedName() if front is not None else None
    except Exception:  # noqa: BLE001, S110 - probing must never raise
        pass
    try:
        from ApplicationServices import (
            AXUIElementCopyAttributeValue,
            AXUIElementCreateSystemWide,
            kAXFocusedUIElementAttribute,
            kAXRoleAttribute,
        )
    except Exception:  # noqa: BLE001 - no AX framework means not accessible
        return {"role": None, "app": app_name, "accessible": False}
    try:
        error, element = AXUIElementCopyAttributeValue(
            AXUIElementCreateSystemWide(), kAXFocusedUIElementAttribute, None)
        if error != 0 or element is None:
            return {"role": None, "app": app_name, "accessible": False}
        error, role = AXUIElementCopyAttributeValue(element, kAXRoleAttribute, None)
        if error != 0:
            return {"role": None, "app": app_name, "accessible": True}
        return {"role": str(role), "app": app_name, "accessible": True}
    except Exception:  # noqa: BLE001 - any AX failure reads as unknown
        return {"role": None, "app": app_name, "accessible": False}
