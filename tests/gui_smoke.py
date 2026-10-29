# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
GUI smoke test for JellyJams. Run inside the full FreeCAD GUI:

    FreeCAD.exe -u <scratch>\\test_user.cfg -s <scratch>\\test_system.cfg tests\\gui_smoke.py

Drives the real UI on a timer chain: activates the workbench, verifies the
ribbon (each page holds what ribbon_model resolves for this FreeCAD's
commands), theme, navigation, shortcuts, the Assembly, Part Design and
TechDraw "switch to workbench" overrides, the crash backups, the JellyJams
menu and tree naming, screenshots
the main window, deactivates, verifies the stock UI and every preference are
restored, writes JSON results, quits.

The headless suite (tests/test_headless.py) covers the logic; this script is
the acceptance check inside a real FreeCAD window.

Output (in the directory named by env JELLYJAMS_RESULTS_DIR, default <repo>/scratch):
    gui_smoke_results.json, jellyjams_active.png, jellyjams_restored.png
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT_DIR = os.environ.get(
    "JELLYJAMS_RESULTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"),
)
os.makedirs(OUT_DIR, exist_ok=True)

RESULTS = {"steps": [], "checks": {}, "errors": []}
EXPECTED_TABS = ["Features", "Sketch", "Evaluate", "Assembly", "Drawing"]
THEME_BEGIN = "/* @jellyjams-stylesheet-open */"
OWN_PARAMS = "User parameter:BaseApp/Preferences/Mod/JellyJams"
# Preference groups whose Bool SwitchToWB JellyJams holds at false while active (switch_prefs)
SWITCH_GROUPS = {
    "Assembly": "User parameter:BaseApp/Preferences/Mod/Assembly",
    "PartDesign": "User parameter:BaseApp/Preferences/Mod/PartDesign",
    "TechDraw": "User parameter:BaseApp/Preferences/Mod/TechDraw/General",
}
BACKUP_KEYS = ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors", "OriginalSwitchToWB",
               "OriginalPartDesignSwitchToWB", "OriginalTechDrawSwitchToWB")
BUTTON_PREFIXES = ("JellyJamsButton-", "JellyJamsFlyout-", "JellyJamsToggle-")
OBJECT_PREFIX = "JellyJams"
# Pause between a workbench switch and the next look at the window. The window-layout spec
# reads the state no sooner than 3.5 s after a switch, when every delayed re-dock has run.
SWITCH_SETTLE_MS = 4000
PRE = {}


def note(step, ok, detail=""):
    RESULTS["checks"][step] = {"ok": bool(ok), "detail": str(detail)[:500]}
    App.Console.PrintMessage(f"JellyJams-smoke {step}: {'OK' if ok else 'FAIL'} {detail}\n")


def save():
    with open(os.path.join(OUT_DIR, "gui_smoke_results.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2)


def shot(name):
    try:
        mw = Gui.getMainWindow()
        mw.grab().save(os.path.join(OUT_DIR, name))
        RESULTS["steps"].append(f"screenshot {name}")
    except Exception:
        RESULTS["errors"].append(f"shot {name}: {traceback.format_exc()}")


def guarded(fn):
    def run():
        try:
            fn()
        except Exception:
            RESULTS["errors"].append(f"{fn.__name__}: {traceback.format_exc()}")
            save()
            finish()
    return run


def nav_style():
    return App.ParamGet("User parameter:BaseApp/Preferences/View").GetString("NavigationStyle", "")


def shortcut(cmd):
    return App.ParamGet("User parameter:BaseApp/Preferences/Shortcut").GetString(cmd, "")


def live_shortcut(cmd):
    c = Gui.Command.get(cmd)
    return c.getShortcut() if c is not None else None


def key_conflicts():
    """Commands other than the JellyJams owner that share one of its keys."""
    from PySide import QtGui
    from jellyjams import shortcuts

    norm = lambda k: QtGui.QKeySequence(k).toString()
    owner = {norm(k): c for c, k in shortcuts.SHORTCUTS}
    hits = []
    for name in Gui.listCommands():
        cur = live_shortcut(name) or ""
        if cur and norm(cur) in owner and owner[norm(cur)] != name:
            hits.append(f"{name}={cur}")
    return hits


def visible_toolbars():
    return sorted(tb.objectName() for tb in Gui.getMainWindow().findChildren(QtWidgets.QToolBar) if tb.isVisible())


def switch_to_wb():
    """SwitchToWB of Assembly, PartDesign and TechDraw: True/False, or "absent" when the key is not set."""
    states = {}
    for module, path in SWITCH_GROUPS.items():
        grp = App.ParamGet(path)
        states[module] = grp.GetBool("SwitchToWB", True) if "SwitchToWB" in grp.GetBools() else "absent"
    return states


def backups():
    own = App.ParamGet(OWN_PARAMS)
    return {key: own.GetString(key, "") for key in BACKUP_KEYS}


def menu_titles():
    return [action.text().replace("&", "") for action in Gui.getMainWindow().menuBar().actions()]


def ribbon_kinds(page):
    """(plain buttons, flyouts, toggles) built on one ribbon page."""
    names = [b.objectName() for b in page.findChildren(QtWidgets.QToolButton)]
    return tuple(sum(1 for n in names if n.startswith(prefix)) for prefix in BUTTON_PREFIXES)


def ribbon_matches_model(tabs):
    """Each page holds the buttons and separators that ribbon_model resolves for the
    commands this FreeCAD has. Counts are not hard-coded: a FreeCAD build without some
    command leaves its button out, and the model says so too."""
    from jellyjams import ribbon, ribbon_layout, ribbon_model

    resolved = ribbon_model.resolve(ribbon_layout.TABS, set(Gui.listCommands()))
    problems, summary = [], {}
    for index in range(tabs.count()):
        title = tabs.tabText(index)
        tab = resolved.tab(title)
        items = []
        for group in (tab.groups if tab is not None else []):
            for item in group.items:
                items.extend(item.cells if isinstance(item, ribbon_model.RStack) else [item])
        expected = (sum(isinstance(i, ribbon_model.RButton) for i in items),
                    sum(isinstance(i, ribbon_model.RFlyout) for i in items),
                    sum(isinstance(i, ribbon_model.RToggle) for i in items))
        page = tabs.widget(index)
        built = ribbon_kinds(page)
        separators = len(page.findChildren(QtWidgets.QFrame, "JellyJamsGroupDivider"))
        summary[title] = {"built": built, "separators": separators}
        if built != expected:
            problems.append(f"{title}: built {built}, model {expected}")
        if separators != resolved.separators(title):
            problems.append(f"{title}: {separators} separators, model {resolved.separators(title)}")
    RESULTS["ribbon"] = {
        "tabs": summary,
        "skipped": list(ribbon.skipped_ids()),
        "substitutions": [list(pair) for pair in resolved.substitutions],
    }
    return not problems, problems or summary


def plain_ribbon_buttons(*entry_ids):
    """The entry ids from `entry_ids` that have no plain ribbon button."""
    from jellyjams import ribbon

    return [entry for entry in entry_ids if ribbon.find_button(entry) is None]


@guarded
def step0_partdesign():
    Gui.activateWorkbench("PartDesignWorkbench")
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, step1_activate)


@guarded
def step1_activate():
    PRE["toolbars"] = visible_toolbars()
    PRE["nav"] = nav_style()
    PRE["boxzoom"] = live_shortcut("Std_ViewBoxZoom")
    PRE["sheet"] = Gui.getMainWindow().styleSheet()
    PRE["switch"] = switch_to_wb()
    PRE["wbs"] = sorted(Gui.listWorkbenches().keys())
    note("workbench_registered", "JellyJamsWorkbench" in PRE["wbs"], str(PRE["wbs"]))
    Gui.activateWorkbench("JellyJamsWorkbench")
    RESULTS["steps"].append("activated JellyJamsWorkbench")
    QtCore.QTimer.singleShot(5000, step2_verify_active)


@guarded
def step2_verify_active():
    mw = Gui.getMainWindow()
    dock = mw.findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
    note("ribbon_dock_exists", dock is not None)
    if dock is not None:
        tabs = dock.findChild(QtWidgets.QTabWidget)
        titles = [tabs.tabText(i) for i in range(tabs.count())] if tabs else []
        note("ribbon_tabs", titles == EXPECTED_TABS, str(titles))
        note("ribbon_visible", dock.isVisible())
        btns = dock.findChildren(QtWidgets.QToolButton)
        note("ribbon_has_buttons", len(btns) > 20, f"{len(btns)} buttons")
        if tabs is not None:
            note("ribbon_matches_model", *ribbon_matches_model(tabs))
        missing_plain = plain_ribbon_buttons(
            "JellyJams_Diagnostics", "JellyJams_LineOnSheet", "JellyJams_CornerRectangleOnSheet",
            "JellyJams_CircleOnSheet", "JellyJams_CenterpointArcOnSheet", "JellyJams_PolygonOnSheet",
            "JellyJams_RotateComponent", "JellyJams_MakeDrawing", "JellyJams_MakeDrawing#1")
        note("jj_plain_buttons", not missing_plain, missing_plain)
    note("theme_marker", mw.styleSheet().count(THEME_BEGIN) == 1, mw.styleSheet().count(THEME_BEGIN))
    note("nav_is_solidworks", nav_style() == "Gui::SolidWorksNavigationStyle", nav_style())
    note("switch_to_wb_off", all(value is False for value in switch_to_wb().values()), switch_to_wb())
    note("backups_present", all(backups().values()), backups())
    note("jellyjams_menu", "JellyJams" in menu_titles(), menu_titles())
    jj_toolbars = [name for name in visible_toolbars() if name.startswith(OBJECT_PREFIX)]
    note("no_jj_toolbars", not jj_toolbars, jj_toolbars)
    note("shortcut_fit", shortcut("Std_ViewFitAll") == "F", shortcut("Std_ViewFitAll"))
    note("rebuild_owns_ctrl_b", live_shortcut("Std_Refresh") == "Ctrl+B", live_shortcut("Std_Refresh"))
    conflicts = key_conflicts()
    note("no_shortcut_conflicts", not conflicts, conflicts)
    shot("jellyjams_active.png")
    QtCore.QTimer.singleShot(1000, step3_naming)


@guarded
def step3_naming():
    doc = App.newDocument("JellyJamsSmoke")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    xy = next(f for f in body.Origin.OriginFeatures if getattr(f, "Role", "") == "XY_Plane")
    sketch.AttachmentSupport = (xy, [""])
    sketch.MapMode = "FlatFace"
    import Part

    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(20, 0, 0)), False)
    sketch.addGeometry(Part.LineSegment(App.Vector(20, 0, 0), App.Vector(20, 10, 0)), False)
    sketch.addGeometry(Part.LineSegment(App.Vector(20, 10, 0), App.Vector(0, 10, 0)), False)
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 10, 0), App.Vector(0, 0, 0)), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 5
    doc.recompute()
    RESULTS["steps"].append("created Body/Sketch/Pad")
    QtCore.QTimer.singleShot(2500, step4_check_labels)


@guarded
def step4_check_labels():
    doc = App.getDocument("JellyJamsSmoke")
    labels = {o.Name: o.Label for o in doc.Objects}
    RESULTS["labels"] = labels
    pads = [o for o in doc.Objects if o.TypeId == "PartDesign::Pad"]
    sketches = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
    note("pad_sw_name", bool(pads) and pads[0].Label.startswith("Boss-Extrude"), pads[0].Label if pads else "no pad")
    note("sketch_sw_name", bool(sketches) and sketches[0].Label.startswith("Sketch"), sketches[0].Label if sketches else "")
    planes = {o.Role: o.Label for o in doc.Objects if o.TypeId == "App::Plane"}
    note(
        "origin_planes_sw",
        planes.get("XY_Plane") == "Top Plane" and planes.get("XZ_Plane") == "Front Plane" and planes.get("YZ_Plane") == "Right Plane",
        str(planes),
    )
    App.closeDocument("JellyJamsSmoke")
    QtCore.QTimer.singleShot(1000, step4b_assembly)


@guarded
def step4b_assembly():
    doc = App.newDocument("JellyJamsAsm")
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    doc.recompute()
    Gui.ActiveDocument.setEdit(asm)  # activating = edit mode, like a double-click
    QtCore.QTimer.singleShot(1500, step4c_assembly_tab)


@guarded
def step4c_assembly_tab():
    tabs = Gui.getMainWindow().findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager").findChild(QtWidgets.QTabWidget)
    current = tabs.tabText(tabs.currentIndex())
    note("assembly_tab_on_activate", current == "Assembly", current)
    note("stayed_in_jellyjams", Gui.activeWorkbench().name() == "JellyJamsWorkbench", Gui.activeWorkbench().name())
    Gui.ActiveDocument.resetEdit()
    App.closeDocument("JellyJamsAsm")
    QtCore.QTimer.singleShot(1000, step5_deactivate)


@guarded
def step5_deactivate():
    Gui.activateWorkbench("PartDesignWorkbench")
    RESULTS["steps"].append("switched to PartDesignWorkbench")
    QtCore.QTimer.singleShot(5000, step6_verify_restored)


@guarded
def step6_verify_restored():
    mw = Gui.getMainWindow()
    note("theme_removed", THEME_BEGIN not in mw.styleSheet() and mw.styleSheet() == PRE["sheet"])
    note("nav_restored", nav_style() == PRE["nav"], f"now={nav_style()!r} was={PRE['nav']!r}")
    note("switch_to_wb_restored", switch_to_wb() == PRE["switch"], f"now={switch_to_wb()!r} was={PRE['switch']!r}")
    note("backups_cleared", not any(backups().values()), backups())
    removed = [key for key in ("OriginalNavigationStyle", "OriginalShortcuts") if key in App.ParamGet(OWN_PARAMS).GetStrings()]
    note("nav_shortcut_backups_removed", not removed, removed)
    note("jellyjams_menu_gone", "JellyJams" not in menu_titles(), menu_titles())
    note("shortcut_restored", shortcut("Std_ViewFitAll") == "", shortcut("Std_ViewFitAll"))
    note("boxzoom_key_restored", live_shortcut("Std_ViewBoxZoom") == PRE["boxzoom"], f"now={live_shortcut('Std_ViewBoxZoom')!r} was={PRE['boxzoom']!r}")
    dock = mw.findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
    note("ribbon_hidden", dock is None or not dock.isVisible())
    missing = sorted(set(PRE["toolbars"]) - set(visible_toolbars()))
    note("stock_toolbars_back", bool(PRE["toolbars"]) and not missing, f"missing={missing} expected={PRE['toolbars']}")
    shot("jellyjams_restored.png")
    RESULTS["ok"] = all(c["ok"] for c in RESULTS["checks"].values())
    save()
    finish()


def finish():
    save()
    App.Console.PrintMessage("JellyJams-smoke done, quitting\n")
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


App.Console.PrintMessage(f"JellyJams-smoke starting, output -> {OUT_DIR}\n")
QtCore.QTimer.singleShot(4000, step0_partdesign)
