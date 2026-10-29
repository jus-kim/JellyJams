# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""What JellyJams runs when FreeCAD initializes, activates and deactivates the
workbench, and what the quit guard undoes and redoes.

Every sequence is a table of ``(key, what, module, function)`` steps. ``what``
completes the error line "could not <what>" printed when that step raises.
Steps run in table order, and a failing step does not stop the ones after it.
"""

import importlib

import jellyjams
from jellyjams import commands, console, constants

# Initialize step 3: helpers that run once per process.
INIT_HELPERS = [
    ("view_labels", "start lettering section and detail views",
     "jellyjams.view_labels", "install"),
    ("zoom_lines", "start matching drawing line widths to the zoom level",
     "jellyjams.zoom_lines", "start"),
    ("weld_watcher", "start keeping weld symbols on their arrows",
     "jellyjams.weld_symbol", "install_watcher"),
    ("sheet_sketch_watcher", "start watching for edits of sheet sketches",
     "jellyjams.sheet_sketch", "install_watcher"),
]

# layout comes first: its window snapshot has to be taken before anything else changes.
ACTIVATION_STEPS = [
    ("layout", "set up the window layout",
     "jellyjams.layout", "apply"),
    ("theme", "add the light theme",
     "jellyjams.theme", "apply"),
    ("viewport", "set the 3D view background and sketch colors",
     "jellyjams.viewport", "apply"),
    ("navigation", "turn on the SolidWorks navigation style",
     "jellyjams.navigation", "install"),
    ("shortcuts", "set the SolidWorks-style keyboard shortcuts",
     "jellyjams.shortcuts", "install"),
    ("orientation", "let focused buttons and lists keep the Space key",
     "jellyjams.orientation", "install"),
    ("ribbon", "display the CommandManager ribbon",
     "jellyjams.ribbon", "show"),
    ("naming", "turn on FeatureManager-style tree names",
     "jellyjams.naming", "enable"),
    ("sketch_edit", "keep JellyJams active while a sketch is edited",
     "jellyjams.sketch_edit", "install"),
    ("edit_guard", "keep JellyJams active while a feature is edited",
     "jellyjams.edit_guard", "install"),
    ("context_sketch", "turn on the Sketch context icon",
     "jellyjams.context_sketch", "enable"),
    ("relations_panel", "turn on the Add Relations panel",
     "jellyjams.relations_panel", "enable"),
    ("mate_panel", "turn on the Mate panel",
     "jellyjams.mate_panel", "enable"),
    ("assembly_drop", "accept files dropped onto an assembly",
     "jellyjams.assembly_drop", "enable"),
    ("switch_prefs", "stop Assembly, Part Design and TechDraw from switching workbenches",
     "jellyjams.switch_prefs", "apply"),
    ("dialog_terms", "start relabeling FreeCAD dialogs with SolidWorks terms",
     "jellyjams.dialog_terms", "start"),
    ("qt_filter", "set up the Qt message filter",
     "jellyjams.qt_filter", "install_and_enable"),
    ("quit_guard", "set up the quit guard",
     "jellyjams.quit_guard", "install"),
]

# layout comes last: FreeCAD already shows the next workbench's toolbars, and
# the layout undoes only JellyJams' own changes.
DEACTIVATION_STEPS = [
    ("qt_filter", "turn off the Qt message filter",
     "jellyjams.qt_filter", "disable"),
    ("dialog_terms", "stop relabeling FreeCAD dialogs",
     "jellyjams.dialog_terms", "stop"),
    ("assembly_drop", "stop accepting files dropped onto an assembly",
     "jellyjams.assembly_drop", "disable"),
    ("switch_prefs", "put back the workbench-switch preferences",
     "jellyjams.switch_prefs", "restore"),
    ("mate_panel", "turn off the Mate panel",
     "jellyjams.mate_panel", "disable"),
    ("relations_panel", "turn off the Add Relations panel",
     "jellyjams.relations_panel", "disable"),
    ("context_sketch", "turn off the Sketch context icon",
     "jellyjams.context_sketch", "disable"),
    ("sheet_pick", "cancel picking a point on the sheet",
     "jellyjams.sheet_pick", "cancel"),
    ("rotate_component", "stop Rotate Component",
     "jellyjams.assembly_commands", "stop_rotate_component"),
    ("sketch_tools", "stop a running Centerline or Midpoint Line tool",
     "jellyjams.sketch_tools", "stop_running"),
    ("edit_guard", "let feature editing switch workbenches again",
     "jellyjams.edit_guard", "uninstall"),
    ("sketch_edit", "let sketch editing switch workbenches again",
     "jellyjams.sketch_edit", "uninstall"),
    ("naming", "pause FeatureManager-style tree names",
     "jellyjams.naming", "disable"),
    ("orientation", "close the Orientation panel and stop watching the Space key",
     "jellyjams.orientation", "uninstall"),
    ("ribbon", "hide the CommandManager ribbon",
     "jellyjams.ribbon", "hide"),
    ("shortcuts", "put back the user's keyboard shortcuts",
     "jellyjams.shortcuts", "uninstall"),
    ("navigation", "put back the user's navigation style",
     "jellyjams.navigation", "uninstall"),
    ("viewport", "put back the user's 3D view colors",
     "jellyjams.viewport", "restore"),
    ("theme", "take off the light theme",
     "jellyjams.theme", "remove"),
    ("layout", "put back the window layout",
     "jellyjams.layout", "revert"),
]

# Used by the quit guard on Close, before FreeCAD writes its window state and parameters.
QUIT_REVERT_STEPS = [
    ("switch_prefs", "put back the workbench-switch preferences on quit",
     "jellyjams.switch_prefs", "restore"),
    ("ribbon", "hide the CommandManager ribbon on quit",
     "jellyjams.ribbon", "hide"),
    ("shortcuts", "put back the user's keyboard shortcuts on quit",
     "jellyjams.shortcuts", "uninstall"),
    ("navigation", "put back the user's navigation style on quit",
     "jellyjams.navigation", "uninstall"),
    ("viewport", "put back the user's 3D view colors on quit",
     "jellyjams.viewport", "restore"),
    ("theme", "take off the light theme on quit",
     "jellyjams.theme", "remove"),
    ("layout", "put back the window layout on quit",
     "jellyjams.layout", "revert"),
]

# Used by the quit guard once, after the user cancelled quitting.
QUIT_REAPPLY_STEPS = [
    ("layout", "set up the window layout again after the quit was cancelled",
     "jellyjams.layout", "apply"),
    ("theme", "add the light theme again after the quit was cancelled",
     "jellyjams.theme", "apply"),
    ("viewport", "set the 3D view colors again after the quit was cancelled",
     "jellyjams.viewport", "apply"),
    ("navigation", "turn the SolidWorks navigation style back on after the quit was cancelled",
     "jellyjams.navigation", "install"),
    ("shortcuts", "set the SolidWorks-style shortcuts again after the quit was cancelled",
     "jellyjams.shortcuts", "install"),
    ("ribbon", "display the CommandManager ribbon again after the quit was cancelled",
     "jellyjams.ribbon", "show"),
    ("switch_prefs", "override the workbench-switch preferences again after the quit was cancelled",
     "jellyjams.switch_prefs", "apply"),
]

_active = False
_helpers_started = False
# ids of workbench objects that got the menu but could not hold the marker attribute.
_menu_ids = set()

_MENU_FLAG = "_jellyjams_menu_added"


def run_steps(steps) -> list:
    """Run the steps in order and return the keys of those that raised.

    Each step's module and function are looked up on every call, so tests can
    patch them.
    """
    failed = []
    for key, what, module_name, function_name in steps:
        try:
            module = importlib.import_module(module_name)
            getattr(module, function_name)()
        except Exception as exc:
            console.error("could not %s: %s" % (what, exc), with_traceback=True)
            failed.append(key)
    return failed


def initialize(workbench) -> None:
    """FreeCAD's Initialize: the first use of the workbench in a session."""
    global _helpers_started
    try:
        with console.guard("print the version line"):
            _report_environment()

        with console.guard("register the JellyJams commands"):
            commands.register_all()

        if not _helpers_started:
            _helpers_started = True
            run_steps(INIT_HELPERS)

        with console.guard("create the JellyJams menu"):
            _add_menu_once(workbench)

        console.message("workbench set up and ready")
    except Exception:
        console.error("setting up the workbench failed", with_traceback=True)


def activated() -> None:
    """FreeCAD's Activated: JellyJams was selected or autoloaded."""
    global _active
    _active = True
    try:
        run_steps(ACTIVATION_STEPS)
    except Exception:
        console.error("switching to JellyJams failed", with_traceback=True)


def deactivated() -> None:
    """FreeCAD's Deactivated: another workbench was selected."""
    global _active
    _active = False
    try:
        run_steps(DEACTIVATION_STEPS)
    except Exception:
        console.error("leaving JellyJams failed", with_traceback=True)


def is_active() -> bool:
    """True from the start of activated() until the start of deactivated()."""
    return _active


def revert_for_quit() -> None:
    """On quit, undo every saved JellyJams change before FreeCAD writes it out."""
    try:
        run_steps(QUIT_REVERT_STEPS)
    except Exception:
        console.error("undoing JellyJams before the quit failed", with_traceback=True)


def reapply_after_cancel() -> None:
    """Apply JellyJams again once the user has cancelled quitting."""
    try:
        run_steps(QUIT_REAPPLY_STEPS)
    except Exception:
        console.error("bringing JellyJams back after the cancelled quit failed",
                      with_traceback=True)


def _report_environment() -> None:
    from jellyjams import diagnostics

    line = diagnostics.environment_line()
    version = tuple(diagnostics.freecad_version())
    minimum = tuple(jellyjams.MIN_FREECAD_VERSION)
    if version[:2] < minimum:
        console.warning(
            "%s; this FreeCAD (%s) is older than %s, the earliest version JellyJams "
            "is tested with"
            % (line, ".".join(str(part) for part in version),
               ".".join(str(part) for part in minimum)))
    else:
        console.message(line)


def _add_menu_once(workbench) -> None:
    if _menu_added(workbench):
        return
    # A command gets a QAction, and so a working keyboard shortcut, only once it sits in a
    # menu or toolbar; the ribbon's own buttons do not create one.
    workbench.appendMenu(constants.MENU_NAME, [constants.CMD_ORIENTATION, constants.CMD_NORMAL_TO,
                                               constants.CMD_DIAGNOSTICS])
    try:
        setattr(workbench, _MENU_FLAG, True)
    except Exception:
        _menu_ids.add(id(workbench))


def _menu_added(workbench) -> bool:
    if id(workbench) in _menu_ids:
        return True
    try:
        return bool(getattr(workbench, _MENU_FLAG, False))
    except Exception:
        return False
