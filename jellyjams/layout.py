# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Window layout while JellyJams is active, and its exact undo.

apply() saves the main-window state, hides the visible main-window toolbars
except File, Edit and Workbench, and docks Tasks over an open Report view on the right.
revert() brings the saved state back but re-shows only the toolbars JellyJams
hid: by the time FreeCAD calls Deactivated() it already shows the next
workbench's toolbars, and those have to stay.

While the main window is not shown yet (autoload), apply() waits for it, so the
saved state is never a start-up layout. The saved state lives in memory only;
no parameters are read or written here.
"""

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui

DEFER_POLL_MS = 200
DEFER_POLL_LIMIT = 60
# Follow-up passes after apply(): FreeCAD's dock overlay manager may move panels again
# for a couple of seconds, so the last pass lands about three seconds in.
REDOCK_DELAYS_MS = (350, 1200, 3000)
SECOND_PASS_MS = 250

_active = False          # True from the moment the snapshot exists
_saved_state = None      # QMainWindow.saveState() result, or None

_hidden = []             # toolbars the current apply hid
_generation = 0          # changes on every apply and revert; late timer passes check it
_deferred = False
_defer_generation = 0
_defer_polls = 0


# --- queries -------------------------------------------------------------------


def is_applied():
    return _active


def is_deferred():
    return _deferred


def is_kept_toolbar(object_name):
    """True when the name contains File, Edit or Workbench (any case); those toolbars stay."""
    name = (object_name or "").lower()
    return any(word.lower() in name for word in constants.KEPT_TOOLBAR_WORDS)


# --- helpers -----------------------------------------------------------------------


def _key(widget):
    try:
        import shiboken6
        return shiboken6.getCppPointer(widget)[0]
    except Exception:
        return id(widget)


def _area_toolbars(window):
    """QToolBars placed in a main-window toolbar area (not those inside docks)."""
    no_area = QtCore.Qt.ToolBarArea.NoToolBarArea
    return [bar for bar in window.findChildren(QtWidgets.QToolBar)
            if fcgui.is_alive(bar) and window.toolBarArea(bar) != no_area]


def _toolbar_visibility(window):
    return [(bar, bar.isVisibleTo(window)) for bar in _area_toolbars(window)]


def _put_back_visibility(window, recorded, skip=()):
    for bar, visible in recorded:
        if _key(bar) in skip or not fcgui.is_alive(bar):
            continue
        if bar.isVisibleTo(window) != visible:
            bar.setVisible(visible)


def _report_dock(window):
    for dock in window.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() == constants.DOCK_REPORT:
            return dock
    return None


def _contains(widgets, widget):
    key = _key(widget)
    return any(_key(other) == key for other in widgets)


def _panels_in_place(window, tasks, report):
    right = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    for dock in (tasks, report):
        if dock is None:
            continue
        if dock.isFloating() or window.dockWidgetArea(dock) != right or not dock.isVisibleTo(window):
            return False
    if report is not None:
        if _contains(window.tabifiedDockWidgets(tasks), report):
            return False
        if tasks.geometry().top() >= report.geometry().top():
            return False
    return True


def _place_panels(window, warn_missing):
    """Put Tasks on the right; place Report view below only if it is already open."""
    tasks = fcgui.task_dock()
    if tasks is None:
        if warn_missing:
            names = sorted(d.objectName() for d in window.findChildren(QtWidgets.QDockWidget))
            console.warning("no Tasks panel found, so Tasks and Report view stay where they are "
                            "(docks present: %s)"
                            % (", ".join(repr(n) for n in names) or "none"))
        return
    report = _report_dock(window)
    # Respect explicit closure, including during the delayed startup passes.
    # Leave a hidden dock's placement and visibility untouched.
    if report is not None and report.isHidden():
        report = None
    if _panels_in_place(window, tasks, report):
        return
    right = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    for dock in (tasks, report):
        if dock is not None and dock.isFloating():
            dock.setFloating(False)
    window.addDockWidget(right, tasks)
    tasks.setVisible(True)
    if report is not None:
        window.addDockWidget(right, report)
        window.splitDockWidget(tasks, report, QtCore.Qt.Orientation.Vertical)
        report.setVisible(True)


def _ribbon(function):
    try:
        from jellyjams import ribbon
        getattr(ribbon, function)()
    except Exception as exc:
        console.log("ribbon.%s() raised after the window layout changed: %s" % (function, exc))


def _later(ms, callback, *args):
    def run():
        try:
            callback(*args)
        except Exception as exc:
            console.log("a delayed window layout step raised: %s" % exc)
    QtCore.QTimer.singleShot(int(ms), run)


# --- apply ------------------------------------------------------------------------


def _apply_now(window):
    global _active, _saved_state, _hidden, _generation
    _cancel_deferral()
    _saved_state = window.saveState()
    _active = True
    _hidden = []
    _generation += 1
    generation = _generation

    hidden_names, kept_names = _hide_toolbars(window)
    console.log("window layout set; toolbars hidden: %s; toolbars left visible: %s"
                % (", ".join(hidden_names) or "none", ", ".join(kept_names) or "none"))

    for delay in REDOCK_DELAYS_MS:
        _later(delay, _redock, generation)
    _place_panels(window, warn_missing=True)


def _hide_toolbars(window):
    """Record and hide visible stock bars, including bars restored late at startup."""
    hidden_names, kept_names = [], []
    for bar in _area_toolbars(window):
        if not bar.isVisible():
            continue
        name = bar.objectName()
        if is_kept_toolbar(name):
            kept_names.append(name)
            continue
        bar.setVisible(False)
        if not _contains(_hidden, bar):
            _hidden.append(bar)
        hidden_names.append(name)
    return hidden_names, kept_names


def _redock(generation):
    if not _active or generation != _generation or not fcgui.jellyjams_active():
        return
    window = fcgui.main_window()
    if window is not None:
        _hide_toolbars(window)
        _place_panels(window, warn_missing=False)


def apply():
    """Switch to the JellyJams window layout, waiting first while the main
    window is hidden. Does nothing while applied."""
    if _active:
        return
    window = fcgui.main_window()
    if window is None or not window.isVisible():
        _start_deferral()
        return
    try:
        _apply_now(window)
    except Exception:
        console.error("setting up the window layout failed", with_traceback=True)


# --- deferral (autoload) ---------------------------------------------------------------


def _start_deferral():
    global _deferred, _defer_generation, _defer_polls
    if _deferred:
        return
    _deferred = True
    _defer_generation += 1
    _defer_polls = 0
    console.log("main window still hidden; the window layout waits until it is shown")
    _later(DEFER_POLL_MS, _poll, _defer_generation)


def _cancel_deferral():
    global _deferred, _defer_generation
    if _deferred:
        _deferred = False
        _defer_generation += 1


def _poll(generation):
    global _defer_polls
    if not _deferred or generation != _defer_generation:
        return
    workbench = fcgui.active_workbench_name()
    if workbench and workbench != constants.WORKBENCH_KEY:
        _cancel_deferral()
        return
    window = fcgui.main_window()
    if window is not None and window.isVisible():
        _cancel_deferral()
        if _active:
            return
        try:
            _apply_now(window)
        except Exception:
            console.error("setting up the window layout failed once the main window was shown",
                          with_traceback=True)
            return
        _ribbon("show_if_requested")
        return
    _defer_polls += 1
    if _defer_polls >= DEFER_POLL_LIMIT:
        _cancel_deferral()
        console.warning("gave up on the window layout: the main window never became visible")
        return
    _later(DEFER_POLL_MS, _poll, generation)


# --- revert -----------------------------------------------------------------------------


def _restore(window, state, hidden):
    """Restore `state`, then re-show only the toolbars JellyJams hid; every
    other toolbar keeps the visibility it has at this moment."""
    hidden_keys = {_key(bar) for bar in hidden if fcgui.is_alive(bar)}
    current = _toolbar_visibility(window)
    # We arrange Report view but never own its visibility. Preserve the user's
    # latest choice so closing it inside JellyJams survives quit and restart.
    report = _report_dock(window)
    report_visible = not report.isHidden() if report is not None else None
    window.restoreState(state)
    if report is not None and fcgui.is_alive(report):
        report.setVisible(report_visible)
    _put_back_visibility(window, current, skip=hidden_keys)
    for bar in hidden:
        if fcgui.is_alive(bar):
            bar.setVisible(True)


def _second_pass(generation, state, hidden):
    if _active or generation != _generation:
        return
    window = fcgui.main_window()
    if window is None:
        return
    # FreeCAD can hide the old workbench's general toolbars after the first
    # restore. Re-show the bars JellyJams hid while preserving every other bar.
    _restore(window, state, hidden)
    _ribbon("hide_if_not_requested")


def revert():
    """Stop a pending wait, undo what apply() did and queue the second restore
    pass. When nothing is applied, only the wait is stopped."""
    global _active, _saved_state, _hidden, _generation
    _cancel_deferral()
    if not _active:
        return
    state, hidden = _saved_state, list(_hidden)
    _active = False
    _saved_state = None
    _hidden = []
    _generation += 1
    generation = _generation
    window = fcgui.main_window()
    if window is None or state is None:
        return
    try:
        _restore(window, state, hidden)
    except Exception:
        console.error("putting back the window layout failed", with_traceback=True)
    _ribbon("hide_if_not_requested")
    _later(SECOND_PASS_MS, _second_pass, generation, state, hidden)
