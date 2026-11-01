# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Visual QA: walk all five ribbon tabs with a document open and screenshot each.

    FreeCAD.exe -u <scratch>\\tabs_user.cfg -s <scratch>\\tabs_system.cfg tests\\gui_tabs.py

Writes tab_<n>_<name>.png (ribbon dock only) + tabs_results.json to the folder named
by JELLYJAMS_RESULTS_DIR (default <repo>/scratch).
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
RES = {"tabs": [], "errors": [], "report_tail": []}


def save():
    with open(os.path.join(OUT_DIR, "tabs_results.json"), "w", encoding="utf-8") as f:
        json.dump(RES, f, indent=2)


def finish():
    save()
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


def guarded(fn):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(f"{fn.__name__}: {traceback.format_exc()}")
            finish()
    return run


STATE = {"i": 0, "tabs": None, "dock": None}


@guarded
def start():
    doc = App.newDocument("TabQA")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    xy = next(f for f in body.Origin.OriginFeatures if getattr(f, "Role", "") == "XY_Plane")
    sk.AttachmentSupport = (xy, [""])
    sk.MapMode = "FlatFace"
    import Part

    for a, b in (((0, 0), (30, 0)), ((30, 0), (30, 20)), ((30, 20), (0, 20)), ((0, 20), (0, 0))):
        sk.addGeometry(Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0)), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 10
    doc.recompute()
    Gui.activateWorkbench("JellyJamsWorkbench")
    QtCore.QTimer.singleShot(4000, locate)


@guarded
def locate():
    mw = Gui.getMainWindow()
    try:
        Gui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass
    STATE["dock"] = mw.findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
    STATE["tabs"] = STATE["dock"].findChild(QtWidgets.QTabWidget) if STATE["dock"] else None
    if STATE["tabs"] is None:
        RES["errors"].append("no JellyJamsCommandManager/QTabWidget found")
        finish()
        return
    QtCore.QTimer.singleShot(500, step_tab)


@guarded
def step_tab():
    tabs, i = STATE["tabs"], STATE["i"]
    if i >= tabs.count():
        Gui.getMainWindow().grab().save(os.path.join(OUT_DIR, "tabs_full_window.png"))
        done()
        return
    tabs.setCurrentIndex(i)
    QtCore.QTimer.singleShot(1200, lambda: snap(i))


def snap(i):
    try:
        tabs = STATE["tabs"]
        name = tabs.tabText(i)
        fn = os.path.join(OUT_DIR, f"tab_{i}_{name}.png")
        STATE["dock"].grab().save(fn)
        buttons = tabs.currentWidget().findChildren(QtWidgets.QToolButton)
        enabled = sum(1 for b in buttons if b.isEnabled())
        names = [b.objectName() for b in buttons]
        # plain buttons, flyouts (split buttons with an arrow menu) and the Sketch / Exit Sketch toggle
        prefixes = (("plain", "JellyJamsButton-"), ("flyouts", "JellyJamsFlyout-"),
                    ("toggles", "JellyJamsToggle-"))
        kinds = {kind: sum(1 for n in names if n.startswith(prefix)) for kind, prefix in prefixes}
        separators = len(tabs.currentWidget().findChildren(QtWidgets.QFrame, "JellyJamsGroupDivider"))
        RES["tabs"].append({"index": i, "name": name, "buttons": len(buttons), "enabled": enabled,
                            "kinds": kinds, "separators": separators, "png": os.path.basename(fn)})
        STATE["i"] = i + 1
        QtCore.QTimer.singleShot(200, step_tab)
    except Exception:
        RES["errors"].append(f"snap {i}: {traceback.format_exc()}")
        finish()


@guarded
def done():
    # collect JellyJams lines from the report view for error spotting
    mw = Gui.getMainWindow()
    try:
        rv = mw.findChild(QtWidgets.QDockWidget, "Report view")
        te = rv.findChild(QtWidgets.QPlainTextEdit) or rv.findChild(QtWidgets.QTextEdit)
        text = te.toPlainText() if te else ""
        RES["report_tail"] = [ln for ln in text.splitlines() if "JellyJams" in ln or "Error" in ln][-40:]
    except Exception:
        pass
    try:
        App.closeDocument("TabQA")
    except Exception:
        pass
    Gui.activateWorkbench("PartDesignWorkbench")
    QtCore.QTimer.singleShot(2000, finish)


App.Console.PrintMessage(f"JellyJams-tabs starting, out -> {OUT_DIR}\n")
QtCore.QTimer.singleShot(4000, start)
