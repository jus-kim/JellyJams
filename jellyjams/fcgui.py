# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Small FreeCAD GUI lookups used across JellyJams.

Each function catches its own errors and then returns its fallback (None, "", False, [] or
{}). FreeCADGui and PySide are imported inside the functions, so importing this module works
without a GUI.
"""

import importlib

from jellyjams import console, constants, params

_preloaded = None


def qt():
    """(QtCore, QtGui, QtWidgets) via FreeCAD's PySide shim; (None, None, None) without it."""
    try:
        from PySide import QtCore, QtGui, QtWidgets

        return QtCore, QtGui, QtWidgets
    except Exception:
        return None, None, None


def gui():
    """The FreeCADGui module, or None."""
    try:
        import FreeCADGui

        return FreeCADGui
    except Exception:
        return None


def main_window():
    """FreeCAD's QMainWindow, or None."""
    try:
        return gui().getMainWindow()
    except Exception:
        return None


def active_workbench_name():
    """Name of the active workbench (e.g. "JellyJamsWorkbench"), or ""."""
    try:
        return str(gui().activeWorkbench().name())
    except Exception:
        return ""


def jellyjams_active():
    """True while JellyJams is the active workbench."""
    return active_workbench_name() == constants.WORKBENCH_KEY


def task_dialog_open():
    """True while the task panel hosts a task dialog."""
    try:
        return bool(gui().Control.activeDialog())
    except Exception:
        return False


def active_gui_document():
    """FreeCADGui.ActiveDocument, or None."""
    try:
        return gui().ActiveDocument
    except Exception:
        return None


def object_in_edit():
    """The document object being edited right now, or None."""
    try:
        document = active_gui_document()
        if document is None:
            return None
        view_provider = document.getInEdit()
        if view_provider is None:
            return None
        return view_provider.Object
    except Exception:
        return None


def sketch_in_edit():
    """The sketch being edited right now, or None."""
    obj = object_in_edit()
    try:
        if obj is not None and obj.TypeId == constants.TYPE_SKETCH:
            return obj
    except Exception:
        pass
    return None


def find_dock(candidates):
    """QDockWidget matched by objectName: exact matches are tried for every candidate in
    order before substring matches; None when neither finds one."""
    try:
        _QtCore, _QtGui, QtWidgets = qt()
        window = main_window()
        if window is None or QtWidgets is None:
            return None
        docks = [dock for dock in window.findChildren(QtWidgets.QDockWidget) if is_alive(dock)]
        names = [(dock, dock.objectName() or "") for dock in docks]
        for candidate in candidates:
            for dock, name in names:
                if name == candidate:
                    return dock
        for candidate in candidates:
            for dock, name in names:
                if candidate in name and not name.startswith(constants.OBJ_PREFIX):
                    return dock
    except Exception:
        pass
    return None


def task_dock():
    """FreeCAD's task panel dock, which plays the PropertyManager role; None if absent."""
    return find_dock(constants.TASK_DOCK_CANDIDATES)


def task_panel():
    """The Gui::TaskView::TaskPanel inside a QScrollArea of the task dock, or None."""
    try:
        _QtCore, _QtGui, QtWidgets = qt()
        dock = task_dock()
        if dock is None or QtWidgets is None:
            return None
        for area in dock.findChildren(QtWidgets.QScrollArea):
            content = area.widget()
            if (
                is_alive(content)
                and content.metaObject().className() == constants.CLASS_TASK_PANEL
            ):
                return content
    except Exception:
        pass
    return None


def mdi_area():
    """The main window's QMdiArea, or None."""
    try:
        _QtCore, _QtGui, QtWidgets = qt()
        window = main_window()
        if window is None or QtWidgets is None:
            return None
        central = window.centralWidget()
        if isinstance(central, QtWidgets.QMdiArea):
            return central
        return window.findChild(QtWidgets.QMdiArea)
    except Exception:
        return None


def active_mdi_widget():
    """The widget of the active MDI sub-window, or None."""
    try:
        area = mdi_area()
        if area is None:
            return None
        # With focus in another top-level window activeSubWindow() is None, while
        # currentSubWindow() still points at the window the user is working in.
        sub_window = area.activeSubWindow() or area.currentSubWindow()
        if sub_window is None:
            return None
        return sub_window.widget()
    except Exception:
        return None


def is_sheet_window(widget):
    """True when `widget` is a TechDraw page window."""
    try:
        if widget is None:
            return False
        return widget.metaObject().className() == constants.CLASS_SHEET_WINDOW
    except Exception:
        return False


def active_sheet_window():
    """The active TechDraw page window, or None."""
    widget = active_mdi_widget()
    return widget if is_sheet_window(widget) else None


def sheet_graphics_view(window=None):
    """QGraphicsView of `window`, or of the active sheet window when none is given; else None."""
    try:
        _QtCore, _QtGui, QtWidgets = qt()
        if QtWidgets is None:
            return None
        if window is None:
            window = active_sheet_window()
        if window is None or not is_alive(window):
            return None
        if isinstance(window, QtWidgets.QGraphicsView):
            return window
        return window.findChild(QtWidgets.QGraphicsView)
    except Exception:
        return None


def techdraw_tool_running(on_error=True):
    """True while a TechDraw tool has the active sheet view, judged by a non-arrow cursor.

    False when no sheet window is active; `on_error` when the check itself fails.
    """
    try:
        QtCore, _QtGui, _QtWidgets = qt()
        window = active_sheet_window()
        if window is None:
            return False
        view = sheet_graphics_view(window)
        if view is None:
            return bool(on_error)
        shape = view.viewport().cursor().shape()
        return shape != QtCore.Qt.CursorShape.ArrowCursor
    except Exception:
        return bool(on_error)


def rez():
    """TechDraw scene units per mm (its "Resolution" parameter); 10.0 if unset."""
    value = params.get_float(constants.PARAM_TECHDRAW_REZ, "Resolution", 0.0)
    try:
        value = float(value)
    except Exception:
        return 10.0
    return value if value > 0 else 10.0


def scene_to_sheet(x, y):
    """Convert a TechDraw scene point (y down) to sheet millimetres (y up)."""
    resolution = rez()
    return (x / resolution, -y / resolution)


def status_message(text, ms=0):
    """Put `text` in FreeCAD's status bar for `ms` milliseconds (0 keeps it until replaced)."""
    try:
        main_window().statusBar().showMessage(str(text), int(ms))
    except Exception:
        pass


def clear_status():
    """Empty FreeCAD's status bar."""
    try:
        main_window().statusBar().clearMessage()
    except Exception:
        pass


def is_alive(obj):
    """True when `obj` is set and its underlying C++ Qt object has not been deleted."""
    if obj is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(obj))
    except Exception:
        return False


def defer(fn, ms=0):
    """Call fn() from the event loop after `ms` milliseconds; errors go to the log."""
    try:
        QtCore, _QtGui, _QtWidgets = qt()
        what = ("finish the delayed call " + str(getattr(fn, "__name__", ""))).strip()
        QtCore.QTimer.singleShot(int(ms), console.guarded(what, level="log")(fn))
    except Exception as exc:
        console.log("a delayed call could not be scheduled: %s" % exc)


def selection(doc_name=None):
    """FreeCADGui.Selection.getSelection([doc_name]) as a list; [] on failure."""
    try:
        selection_api = gui().Selection
        if doc_name is None:
            return list(selection_api.getSelection())
        return list(selection_api.getSelection(doc_name))
    except Exception:
        return []


def selection_ex(*args):
    """FreeCADGui.Selection.getSelectionEx(*args) as a list; [] on failure."""
    try:
        return list(gui().Selection.getSelectionEx(*args))
    except Exception:
        return []


def command_exists(cmd_id):
    """True when FreeCAD has a command called `cmd_id`."""
    module = gui()
    if module is None:
        return False
    try:
        return cmd_id in module.listCommands()
    except Exception:
        pass
    try:
        return module.Command.get(cmd_id) is not None
    except Exception:
        return False


def command_info(cmd_id):
    """FreeCADGui.Command.get(cmd_id).getInfo() as a dict; {} if unknown or on failure."""
    try:
        command = gui().Command.get(cmd_id)
        if command is None:
            return {}
        return dict(command.getInfo() or {})
    except Exception:
        return {}


def run_command(cmd_id, index=None):
    """Run a FreeCAD command, passing the sub-command index if one is given. False on failure."""
    try:
        module = gui()
        if module is None:
            raise RuntimeError("FreeCADGui is unavailable")
        if index is None:
            module.runCommand(cmd_id)
        else:
            module.runCommand(cmd_id, index)
        return True
    except Exception as exc:
        console.error("running %s failed: %s" % (cmd_id, exc))
        return False


def preload_command_modules():
    """Import the FreeCAD modules whose import registers the ribbon's commands.

    Does the work once per process and hands back that first result afterwards.
    Prints nothing. Returns (gui_failures: [(module, reason)], assembly_failures: [module]).
    """
    global _preloaded
    if _preloaded is None:
        gui_failures = []
        for name in constants.GUI_COMMAND_MODULES:
            try:
                importlib.import_module(name)
            except Exception as exc:
                gui_failures.append((name, str(exc) or type(exc).__name__))
        assembly_failures = []
        for name in constants.ASSEMBLY_COMMAND_MODULES:
            try:
                importlib.import_module(name)
            except Exception:
                assembly_failures.append(name)
        _preloaded = (gui_failures, assembly_failures)
    return (list(_preloaded[0]), list(_preloaded[1]))
