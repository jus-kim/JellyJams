# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Inspect a FreeCAD user.cfg written after quitting with JellyJams active: no
SolidWorks navigation, no JellyJams shortcut overrides (and no unbinding of
Box Zoom or Show/Hide), no leftover crash
backups (OriginalNavigationStyle, OriginalShortcuts, OriginalViewColors,
OriginalSwitchToWB, OriginalPartDesignSwitchToWB, OriginalTechDrawSwitchToWB)
and the user's own "switch to workbench" settings of Assembly, Part Design and
TechDraw.

Plain Python (no FreeCAD needed):

    python check_saved_cfg.py <user.cfg> [expected_nav] [expected_switch_to_wb]
                              [expected_partdesign_switch] [expected_techdraw_switch]

expected_nav                NavigationStyle the user had before JellyJams; ""
                            means the key must be absent, "-" skips the check.
expected_switch_to_wb       Preferences/Mod/Assembly SwitchToWB before JellyJams:
                            "absent", "true" or "false" ("1"/"0" also work); "-"
                            or omitted skips the check.
expected_partdesign_switch  Preferences/Mod/PartDesign SwitchToWB before JellyJams,
                            same values; "-" skips the check. Omitted means
                            "absent", the state of a fresh throwaway config.
expected_techdraw_switch    Preferences/Mod/TechDraw/General SwitchToWB before
                            JellyJams, same values and default as above.

gui_lifecycle.py records the values to expect in lifecycle_discard.json:
info.nav_before and info.switch_before (Assembly, PartDesign, TechDraw).

Prints JSON and exits 1 on failure.
"""

import json
import sys
import xml.etree.ElementTree as ET

BACKUP_KEYS = ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors", "OriginalSwitchToWB",
               "OriginalPartDesignSwitchToWB", "OriginalTechDrawSwitchToWB", "OriginalSketchSnapping")
# Commands JellyJams binds (F, Ctrl+B, Ctrl+7, Ctrl+8, Space) or unbinds while active (Box Zoom
# loses Ctrl+B, Show/Hide loses Space); none may keep an override after a quit.
# Std_AlignToSelection (FreeCAD's own Normal To) is checked too: JellyJams leaves it alone.
JELLYJAMS_SHORTCUTS = ("Std_ViewFitAll", "Std_Refresh", "Std_ViewIsometric", "JellyJams_NormalTo",
                       "Std_AlignToSelection", "JellyJams_ViewOrientation", "Std_ViewBoxZoom",
                       "Std_ToggleVisibility")
SKIP = "-"
ABSENT = "absent"
# group path below BaseApp/Preferences of each SwitchToWB that JellyJams holds at false
SWITCH_GROUPS = {
    "Assembly": ("Mod", "Assembly"),
    "PartDesign": ("Mod", "PartDesign"),
    "TechDraw": ("Mod", "TechDraw", "General"),
}


def group(root, *path):
    node = root
    for name in path:
        node = next((g for g in node.findall("FCParamGroup") if g.get("Name") == name), None)
        if node is None:
            return None
    return node


def text(grp, name):
    if grp is None:
        return None
    element = next((e for e in grp.findall("FCText") if e.get("Name") == name), None)
    return None if element is None else (element.text or "")


def boolean(grp, name):
    """True/False for an FCBool entry, or "absent"."""
    if grp is None:
        return ABSENT
    element = next((e for e in grp.findall("FCBool") if e.get("Name") == name), None)
    if element is None:
        return ABSENT
    return element.get("Value") == "1"


def parse_switch_expectation(value, name="expected_switch_to_wb"):
    lowered = value.strip().lower()
    if lowered in (ABSENT, ""):
        return ABSENT
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise SystemExit("%s must be absent, true, false or '-', not %r" % (name, value))


def switch_expectation(position, name, default):
    """The expectation given at argv[position]; `default` when omitted; None skips the check."""
    if len(sys.argv) <= position:
        return default
    if sys.argv[position] == SKIP:
        return None
    return parse_switch_expectation(sys.argv[position], name)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cfg = sys.argv[1]
    expected_nav = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != SKIP else None
    expected_switch = {
        "Assembly": switch_expectation(3, "expected_switch_to_wb", None),
        "PartDesign": switch_expectation(4, "expected_partdesign_switch", ABSENT),
        "TechDraw": switch_expectation(5, "expected_techdraw_switch", ABSENT),
    }

    root = ET.parse(cfg).getroot()
    root = root.find("FCParamGroup") if root.get("Name") != "Root" else root
    prefs = ("BaseApp", "Preferences")
    nav = text(group(root, *prefs, "View"), "NavigationStyle")
    shortcuts = group(root, *prefs, "Shortcut")
    overrides = {e.get("Name"): e.text for e in shortcuts.findall("FCText")} if shortcuts is not None else {}
    own = group(root, *prefs, "Mod", "JellyJams")
    backups = {key: text(own, key) for key in BACKUP_KEYS}
    switches = {module: boolean(group(root, *prefs, *path), "SwitchToWB") for module, path in SWITCH_GROUPS.items()}

    def matches(module):
        expected = expected_switch[module]
        return expected is None or switches[module] == expected

    checks = {
        "nav_not_solidworks": nav != "Gui::SolidWorksNavigationStyle",
        "nav_matches_expected": expected_nav is None or (nav or "") == expected_nav,
        "no_jj_shortcut_overrides": not any(key in overrides for key in JELLYJAMS_SHORTCUTS),
        "no_leftover_backups": not any(value for value in backups.values()),
        "switch_to_wb_matches_expected": matches("Assembly"),
        "partdesign_switch_restored": matches("PartDesign"),
        "techdraw_switch_restored": matches("TechDraw"),
    }
    out = {
        "cfg": cfg,
        "nav": nav,
        "overrides": overrides,
        "backups": backups,
        "switch_to_wb": switches["Assembly"],
        "switches": switches,
        "expected_switches": expected_switch,
        "checks": checks,
        "ok": all(checks.values()),
    }
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
