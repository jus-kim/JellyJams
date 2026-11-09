# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Run real FreeCAD acceptance scripts with disposable configs and check their JSON.

Run with ordinary Python, not inside FreeCAD. JellyJams must already be installed.
Results are kept in a unique folder under scratch; the real config is never read.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
SUITES = {
    "cad_baseline": ("gui_cad_baseline.py", "cad_baseline.json", 333),
    "quick_access": ("gui_quick_access.py", "quick_access.json", 44),
    "plane_pick": ("gui_plane_pick.py", "plane_pick.json", 35),
    "smart_dimension": ("gui_smart_dimension.py", "smart_dimension.json", 22),
    "sketch_assist": ("gui_sketch_assist.py", "sketch_assist.json", 35),
    "host_compatibility": ("gui_host_compatibility.py", "host_compatibility.json", 23),
    "surface_geometry": ("gui_surface_geometry.py", "surface_geometry.json", 27),
    "measure": ("gui_measure.py", "measure.json", 72),
    "smoke": ("gui_smoke.py", "gui_smoke_results.json", 31),
    "sketch": ("gui_sketch_first.py", "sketch_first.json", 20),
    "orientation": ("gui_orientation.py", "orientation.json", 84),
    "orbit": ("gui_orbit.py", "orbit.json", 49),
    "features": ("gui_features.py", "features.json", 52),
    "assembly_tree": ("gui_assembly_tree.py", "assembly_tree.json", 104),
    "appearances": ("gui_appearances.py", "appearances.json", 38),
    "report_view": ("gui_report_view.py", "report_view.json", 9),
    "report_startup": ("gui_report_view.py", "report_startup.json", 3),
    "tabs": ("gui_tabs.py", "tabs_results.json", 0),
    "cancel": ("gui_lifecycle.py", "lifecycle_cancel.json", 16),
    "discard": ("gui_lifecycle.py", "lifecycle_discard.json", 9),
    "save": ("gui_lifecycle.py", "lifecycle_save.json", 9),
    "after": ("gui_lifecycle.py", "lifecycle_after.json", 5),
    "autoload": ("gui_lifecycle.py", "lifecycle_autoload.json", 6),
    "crash": ("gui_crash.py", "crash.json", 2),
    "recover": ("gui_crash.py", "recover.json", 3),
    "theme_dark": ("gui_theme.py", "theme_dark.json", 22),
    "theme_light": ("gui_theme.py", "theme_light.json", 22),
}
CORE_SUITES = ("cad_baseline", "smoke")
SUITE_PREREQUISITES = {"after": "discard", "recover": "crash", "report_startup": "report_view"}


def select_suites(requested):
    """Run each suite once, preserving order and validating shared-profile pairs."""
    selected = list(dict.fromkeys(requested))
    if not selected or any(name not in SUITES for name in selected):
        raise ValueError("Select at least one known GUI suite")
    for suite, prerequisite in SUITE_PREREQUISITES.items():
        if suite in selected and (prerequisite not in selected or
                                  selected.index(prerequisite) > selected.index(suite)):
            raise ValueError("%s must follow %s in the same run" % (suite, prerequisite))
    return selected


def validate_result(result, minimum=1):
    """Reject missing checks, failed assertions, exceptions and incomplete tab runs."""
    if result.get("errors"):
        raise ValueError(str(result["errors"]))
    if result.get("ok") is False:
        raise ValueError("script reported an unsuccessful run")
    checks = result.get("checks", {})
    if len(checks) < minimum:
        raise ValueError("incomplete run: %d checks, expected at least %d" % (len(checks), minimum))
    failed = {name: item for name, item in checks.items() if item.get("ok") is not True}
    if failed:
        raise ValueError(str(failed))
    if minimum == 0 or "tabs" in result:
        names = [tab["name"] for tab in result.get("tabs", [])]
        if names != ["Features", "Sketch", "Evaluate", "Assembly", "Drawing"]:
            raise ValueError("incomplete tabs: %r" % names)
    return len(checks)


def autoload_config(path):
    root = ET.Element("FCParameters")
    group = ET.SubElement(root, "FCParamGroup", Name="Root")
    for name in ("BaseApp", "Preferences", "General"):
        group = ET.SubElement(group, "FCParamGroup", Name=name)
    ET.SubElement(group, "FCText", Name="AutoloadModule").text = "JellyJamsWorkbench"
    ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)


def theme_config(path, dark):
    """Seed only a disposable profile with FreeCAD's installed native theme."""
    root = ET.Element("FCParameters")
    group = ET.SubElement(root, "FCParamGroup", Name="Root")
    for name in ("BaseApp", "Preferences", "MainWindow"):
        group = ET.SubElement(group, "FCParamGroup", Name=name)
    ET.SubElement(group, "FCText", Name="Theme").text = "FreeCAD Dark" if dark else "FreeCAD Light"
    ET.SubElement(group, "FCText", Name="StyleSheet").text = "FreeCAD.qss"
    ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", default="C:/Program Files/FreeCAD 1.1/bin/FreeCAD.exe")
    parser.add_argument("--timeout", type=int, default=240, help="seconds per FreeCAD process")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--suites", nargs="+", choices=SUITES, help="focused suites; default: CAD and smoke")
    selection.add_argument("--full", action="store_true", help="run all registered native suites once")
    args = parser.parse_args()
    try:
        args.suites = select_suites(SUITES if args.full else (args.suites or CORE_SUITES))
    except ValueError as exc:
        parser.error(str(exc))
    if "cad_baseline" in args.suites:
        from cad_fixtures import verify_cache
        verify_cache()
    (REPO / "scratch").mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="gui_", dir=REPO / "scratch"))
    print("Results: %s" % out, flush=True)
    summary = {}
    for suite in args.suites:
        started = time.perf_counter()
        script, filename, minimum = SUITES[suite]
        profile = "discard" if suite == "after" else suite
        if suite == "recover":
            profile = "crash"
        if suite == "report_startup":
            profile = "report_view"
        user, system = out / (profile + "_user.cfg"), out / (profile + "_system.cfg")
        if suite == "autoload":
            autoload_config(user)
        if suite in ("theme_dark", "theme_light"):
            theme_config(user, suite == "theme_dark")
        env = dict(os.environ, JELLYJAMS_RESULTS_DIR=str(out), JELLYJAMS_LIFECYCLE_MODE=suite)
        command = [args.freecad, "-u", str(user), "-s", str(system), str(REPO / "tests" / script)]
        try:
            # subprocess waits for this exact GUI process, including on Windows.
            with (out / (suite + ".log")).open("w", encoding="utf-8") as log:
                process = subprocess.run(command, env=env, cwd=REPO, stdout=log, stderr=log,
                                         timeout=args.timeout, check=False)
            expected_exit = 86 if suite == "crash" else 0
            if process.returncode != expected_exit:
                raise ValueError("FreeCAD exited %s, expected %s" % (process.returncode, expected_exit))
            result = json.loads((out / filename).read_text(encoding="utf-8"))
            count = validate_result(result, minimum)
            if suite in ("discard", "save"):
                info = result["info"]
                switches = info["switch_before"]
                check = subprocess.run([
                    sys.executable, str(REPO / "tests/check_saved_cfg.py"), str(user),
                    info["nav_before"], *[str(switches[name]) for name in
                                            ("Assembly", "PartDesign", "TechDraw")],
                ], capture_output=True, text=True, check=True)
                (out / (suite + "_saved_cfg.json")).write_text(check.stdout, encoding="utf-8")
            summary[suite] = {"ok": True, "checks": count}
            print("%s: PASS (%d checks)" % (suite, count), flush=True)
        except Exception as exc:
            summary[suite] = {"ok": False, "error": str(exc)}
            print("%s: FAIL: %s" % (suite, exc), flush=True)
        summary[suite]["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if all(item["ok"] for item in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
