# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Preserve closed Report view, then relaunch with JellyJams autoload.

Run tests/run_gui.py --suites report_view report_startup. Both processes share
only the disposable profile prepared by the runner, never the real profile.
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
MODE = os.environ["JELLYJAMS_LIFECYCLE_MODE"]
RES = {"checks": {}, "errors": []}


def note(name, ok):
    RES["checks"][name] = {"ok": bool(ok)}


def report():
    from jellyjams import constants
    return Gui.getMainWindow().findChild(QtWidgets.QDockWidget, constants.DOCK_REPORT)


def later(fn, ms=4000):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, guarded)


def start():
    if MODE == "report_startup":
        note("jellyjams_autoloaded", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
        note("saved_closed_report_stays_closed", report().isHidden())
        Gui.activateWorkbench("PartDesignWorkbench")
        later(after_startup_leave)
    else:
        Gui.activateWorkbench("PartDesignWorkbench")
        later(seed)


def seed():
    report().hide()
    note("report_closed_before_activation", report().isHidden())
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(check_active)


def check_active():
    from jellyjams import layout
    note("report_stays_closed_after_startup_passes", report().isHidden())
    report().show()
    note("user_can_open_report", not report().isHidden())
    report().hide()
    note("user_can_close_report", report().isHidden())
    layout._redock(layout._generation)
    note("redocking_does_not_reopen_report", report().isHidden())
    Gui.activateWorkbench("PartDesignWorkbench")
    later(check_leave)


def check_leave():
    from jellyjams import constants
    note("closed_report_restored_on_leave", report().isHidden())
    # Prepare the next real process to autoload JellyJams using this scratch
    # profile's saved native window state.
    App.ParamGet(constants.PARAM_GENERAL).SetString("AutoloadModule", constants.WORKBENCH_KEY)
    note("report_closed_before_native_quit", report().isHidden())
    finish()


def after_startup_leave():
    note("closed_report_restored_after_autoload_leave", report().isHidden())
    finish()


def finish():
    RES["ok"] = bool(RES["checks"]) and not RES["errors"] and all(c["ok"] for c in RES["checks"].values())
    with open(os.path.join(OUT, MODE + ".json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


later(start, 6000)
