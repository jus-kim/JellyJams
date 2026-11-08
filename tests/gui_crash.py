# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Persist active overrides, terminate abruptly, then verify recovery in a new process.

Only run through run_gui.py with crash followed by recover. No user documents are opened.
"""

import json
import ctypes
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
MODE = os.environ["JELLYJAMS_LIFECYCLE_MODE"]
RES = {"checks": {}, "errors": [], "version": App.Version()}


def snapshot():
    from jellyjams import constants, params, shortcuts, viewport, switch_prefs
    targets = [(constants.PARAM_VIEW, name, suffix) for name, suffix, _value in viewport.MANAGED_KEYS]
    targets += [(constants.PARAM_VIEW, "NavigationStyle", "String")]
    targets += [(constants.PARAM_SHORTCUT, name, "String") for name, _value in shortcuts.SHORTCUTS]
    targets += [(constants.PARAM_SHORTCUT, name, "String") for name in ("Std_ToggleVisibility", "Std_ViewBoxZoom")]
    targets += [(path, "SwitchToWB", "Bool") for path, _key, _name in switch_prefs.TARGETS]
    targets += [(constants.PARAM_SKETCH_SNAP, name, "Bool") for name in
                (constants.KEY_SKETCH_SNAP, constants.KEY_SKETCH_SNAP_OBJECTS)]
    result = []
    for path, name, suffix in targets:
        group = params.group(path)
        exists = params.has_key(group, name, suffix)
        result.append([path, name, suffix, exists, params.get_value(group, suffix, name) if exists else None])
    return result


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def save():
    with open(os.path.join(OUT, MODE + ".json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)


def terminate_without_cleanup():
    """Bypass C-runtime/DLL cleanup too, including live native editor threads."""
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        terminate = kernel.TerminateProcess
        terminate.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        terminate.restype = ctypes.c_int
        # -1 is the documented pseudo-handle for the current process.
        if not terminate(ctypes.c_void_p(-1), 86):
            raise ctypes.WinError(ctypes.get_last_error())
    os._exit(86)


def run():
    try:
        from jellyjams import constants, params
        if MODE == "crash":
            Gui.activateWorkbench("PartDesignWorkbench")
            # Use both explicit values and absent keys rather than defaults alone.
            view = params.group(constants.PARAM_VIEW)
            view.SetString("NavigationStyle", "Gui::CADNavigationStyle")
            view.SetUnsigned("BackgroundColor2", 0x123456FF)
            params.group(constants.PARAM_SHORTCUT).SetString("Std_ViewTop", "T")
            params.group(constants.PARAM_SKETCH_SNAP).SetBool(constants.KEY_SKETCH_SNAP, False)
            before = snapshot()
            with open(os.path.join(OUT, "crash_before.json"), "w", encoding="utf-8") as stream:
                json.dump(before, stream)
            Gui.activateWorkbench("JellyJamsWorkbench")
            doc = App.newDocument("CrashSketch")
            sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
            doc.recompute()
            Gui.activeDocument().setEdit(sketch.Name)
            note("overrides_applied", snapshot() != before)
            note("all_crash_backups_present", all(params.backup_pending(key) for key in constants.BACKUP_KEYS))
            # Model a preference save during an active session followed by a crash.
            App.saveParameter()
            save()
            # Skip close events, quit guard and Python/Qt teardown deliberately.
            terminate_without_cleanup()
        else:
            with open(os.path.join(OUT, "crash_before.json"), encoding="utf-8") as stream:
                before = json.load(stream)
            now = snapshot()
            differences = [(old, new) for old, new in zip(before, now) if old != new]
            note("all_managed_preferences_recovered", before == now, differences)
            note("all_crash_backups_cleared", not any(params.backup_pending(key) for key in constants.BACKUP_KEYS))
            Gui.activateWorkbench("PartDesignWorkbench")
            from jellyjams import constants as C
            dock = Gui.getMainWindow().findChild(QtWidgets.QDockWidget, C.OBJ_RIBBON)
            note("ribbon_not_left_visible", dock is None or not dock.isVisible())
    except Exception:
        RES["errors"].append(traceback.format_exc())
    save()
    QtCore.QTimer.singleShot(1000, QtWidgets.QApplication.instance().quit)


QtCore.QTimer.singleShot(5000, run)
