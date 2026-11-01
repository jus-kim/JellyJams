# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Centerline (JellyJams_Centerline) and Midpoint Line (JellyJams_MidpointLine).

Each tool launches FreeCAD's ``Sketcher_CreateLine`` and then polls the sketch
in edit. While the tool runs, every new line segment is either switched to
construction geometry (Centerline) or given a mirrored second half, held by a
Coincident and a Symmetric constraint (Midpoint Line). FreeCAD draws the lines;
this module only post-processes them.

A run stops on Esc or a right mouse press (noticed by an application event
filter that exists only during a run and never consumes events), when another
ribbon button is pressed (``stop_running``), when the workbench is left, or
when the sketch is no longer in edit. Every stop except the last one processes
the sketch one more time first.
"""

import FreeCAD
from PySide import QtCore, QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui

CREATE_LINE = "Sketcher_CreateLine"
LINE_TYPE = "Part::GeomLineSegment"
POLL_MS = 150             # keeps the reaction to a new line under ~0.3 s
ZERO_LENGTH = 1e-9

_mode = None              # active _ToolMode instance, if any
_timer = None             # poll timer, reused across runs
_filter = None            # Esc / right-click watcher, reused across runs
_filter_target = None     # QApplication currently holding the watcher


# --- pure helpers ---------------------------------------------------------------


def _xy(point):
    if hasattr(point, "x") and hasattr(point, "y"):
        return point.x, point.y
    return point[0], point[1]


def mirrored_end(mid, end):
    """Reflect `end` through `mid`; the result is where the second half ends."""
    mx, my = _xy(mid)
    ex, ey = _xy(end)
    return (2 * mx - ex, 2 * my - ey)


# --- sketch access ----------------------------------------------------------------


def _geometry_count(sketch):
    count = getattr(sketch, "GeometryCount", None)
    if isinstance(count, int):
        return count
    return len(sketch.Geometry)


def _tag(geometry):
    return getattr(geometry, "Tag", None) or None


def _tags(geometries):
    return {tag for tag in (_tag(g) for g in geometries) if tag}


def _is_new_line(geometry, known_tags):
    if getattr(geometry, "TypeId", "") != LINE_TYPE:
        return False
    tag = _tag(geometry)
    return tag is None or tag not in known_tags


class _ToolMode:
    """State of a single tool run, bound to one sketch."""

    cmd_id = ""
    title = ""
    failure = ""

    def __init__(self, sketch):
        self.sketch = sketch
        self.doc = sketch.Document
        self.doc_name = self.doc.Name
        self.sketch_name = sketch.Name
        self.start_count = _geometry_count(sketch)
        # Tags stay stable across solve, undo and redo. With the index floor
        # they stop older geometry, and the halves added here, from being processed.
        self.known_tags = _tags(sketch.Geometry)
        self.end_requested = False

    def owns_edit(self):
        try:
            current = fcgui.sketch_in_edit()
            return (current is not None
                    and current.Name == self.sketch_name
                    and current.Document.Name == self.doc_name)
        except Exception:
            return False

    def process(self):
        raise NotImplementedError


class _CenterlineMode(_ToolMode):
    cmd_id = constants.CMD_CENTERLINE
    title = "Centerline"
    failure = "a new line could not be switched to construction geometry"

    def __init__(self, sketch):
        super().__init__(sketch)
        self.floor = self.start_count

    def process(self):
        sketch = self.sketch
        count = _geometry_count(sketch)
        if count < self.floor:
            self.floor = count
        candidates = [i for i in range(self.floor, count) if not sketch.getConstruction(i)]
        if not candidates:
            return
        geometry = sketch.Geometry
        targets = [i for i in candidates if _is_new_line(geometry[i], self.known_tags)]
        if not targets:
            return
        with doc_utils.transaction(self.doc, self.title, join_pending=True):
            for index in targets:
                sketch.setConstruction(index, True)


class _MidpointMode(_ToolMode):
    cmd_id = constants.CMD_MIDPOINT_LINE
    title = "Midpoint Line"
    failure = "the mirrored second half could not be added"

    def __init__(self, sketch):
        super().__init__(sketch)
        self.seen = self.start_count

    def process(self):
        sketch = self.sketch
        count = _geometry_count(sketch)
        if count < self.seen:
            self.seen = count
        if count == self.seen:
            return
        geometry = sketch.Geometry
        mirrored = False
        for index in range(self.seen, count):
            drawn = geometry[index]
            if not _is_new_line(drawn, self.known_tags):
                continue
            if _tag(drawn):
                self.known_tags.add(_tag(drawn))
            if self._mirror(index):
                mirrored = True
        self.seen = _geometry_count(sketch)
        if self.seen > count:
            self.known_tags.update(_tags(sketch.Geometry[count:]))
        if mirrored:
            try:
                sketch.solve()
            except Exception:
                pass

    def _mirror(self, index):
        import Part
        import Sketcher

        sketch = self.sketch
        start = sketch.getPoint(index, 1)
        end = sketch.getPoint(index, 2)
        if (end - start).Length <= ZERO_LENGTH:
            return False
        ex, ey = mirrored_end(start, end)
        partner_geometry = Part.LineSegment(
            FreeCAD.Vector(start.x, start.y, 0), FreeCAD.Vector(ex, ey, 0)
        )
        construction = bool(sketch.getConstruction(index))
        with doc_utils.transaction(self.doc, self.title, join_pending=True):
            partner = sketch.addGeometry(partner_geometry, construction)
            sketch.addConstraint(Sketcher.Constraint("Coincident", partner, 1, index, 1))
            sketch.addConstraint(
                Sketcher.Constraint("Symmetric", index, 2, partner, 2, index, 1)
            )
        return True


_MODES = {mode.cmd_id: mode for mode in (_CenterlineMode, _MidpointMode)}


# --- end detection ------------------------------------------------------------------

_END_KEY_TYPES = (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.ShortcutOverride)


def _is_end_event(event):
    etype = event.type()
    if etype in _END_KEY_TYPES:
        key = getattr(event, "key", None)
        return key is not None and key() == QtCore.Qt.Key.Key_Escape
    if etype == QtCore.QEvent.Type.MouseButtonPress:
        button = getattr(event, "button", None)
        return button is not None and button() == QtCore.Qt.MouseButton.RightButton
    return False


class _EndEventFilter(QtCore.QObject):
    """Notices Esc and right mouse presses without consuming them."""

    def eventFilter(self, watched, event):
        try:
            if _mode is not None and _is_end_event(event):
                _request_end()
        except Exception:
            pass
        return False


def _request_end():
    mode = _mode
    if mode is None or mode.end_requested:
        return
    mode.end_requested = True
    # Deferred: FreeCAD has to handle the event first so its line tool closes cleanly.
    fcgui.defer(lambda: _finish(mode, final_pass=True), 0)


def _install_filter():
    global _filter, _filter_target
    app = QtWidgets.QApplication.instance()
    if app is None or _filter_target is app:
        return
    _remove_filter()
    if _filter is None:
        _filter = _EndEventFilter()
    app.installEventFilter(_filter)
    _filter_target = app


def _remove_filter():
    global _filter_target
    target, _filter_target = _filter_target, None
    if target is None or _filter is None:
        return
    try:
        target.removeEventFilter(_filter)
    except Exception:
        pass


# --- mode lifecycle -------------------------------------------------------------------


def _start_timer():
    global _timer
    if _timer is None or not fcgui.is_alive(_timer):
        _timer = QtCore.QTimer()
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(_poll)
    _timer.start()


def _stop_timer():
    if _timer is not None:
        try:
            _timer.stop()
        except Exception:
            pass


def _poll():
    mode = _mode
    try:
        if mode is None:
            _stop_timer()
            return
        if not mode.owns_edit():
            _finish(mode, final_pass=False)
            return
        try:
            mode.process()
        except Exception as exc:
            console.warning("%s stopped: %s (%s)" % (mode.title, mode.failure, exc))
            _finish(mode, final_pass=False)
    except Exception as exc:
        console.log("Centerline / Midpoint Line poll raised: %s" % exc)


def _finish(mode, final_pass):
    global _mode
    if mode is None or _mode is not mode:
        return
    try:
        if final_pass and mode.owns_edit():
            try:
                mode.process()
            except Exception as exc:
                console.warning("%s stopped: %s (%s)" % (mode.title, mode.failure, exc))
    finally:
        _mode = None
        _stop_timer()
        _remove_filter()


def _start(cmd_id):
    global _mode
    sketch = fcgui.sketch_in_edit()
    if sketch is None:
        return
    stop_running()
    mode = _MODES[cmd_id](sketch)
    _mode = mode
    _start_timer()
    _install_filter()
    if not fcgui.run_command(CREATE_LINE):
        _finish(mode, final_pass=False)


def stop_running(except_cmd=None):
    """Stop the running Centerline / Midpoint Line after one last pass.

    No-op when nothing runs, or when `except_cmd` names the running tool (that
    command restarts the tool itself). Never raises.
    """
    try:
        mode = _mode
        if mode is None:
            return
        if except_cmd is not None and except_cmd == mode.cmd_id:
            return
        _finish(mode, final_pass=True)
    except Exception as exc:
        console.log("stopping Centerline / Midpoint Line raised: %s" % exc)


def running_tool():
    """Id of the tool that is currently running, or None."""
    mode = _mode
    return mode.cmd_id if mode is not None else None


# --- commands ---------------------------------------------------------------------------


class _SketchToolCommand(commands.BaseCommand):
    def is_active(self):
        return fcgui.sketch_in_edit() is not None

    def run(self):
        _start(self.command_id)


class CenterlineCommand(_SketchToolCommand):
    command_id = constants.CMD_CENTERLINE
    menu_text = "Centerline"
    tooltip = ("Draw lines that switch to construction geometry as soon as they are "
               "placed. Press Esc or right-click to stop.")
    icon = constants.COMMAND_ICONS[constants.CMD_CENTERLINE]


class MidpointLineCommand(_SketchToolCommand):
    command_id = constants.CMD_MIDPOINT_LINE
    menu_text = "Midpoint Line"
    tooltip = ("Pick the middle point first, then one end. The opposite half is added "
               "as a symmetric mirror. Press Esc or right-click to stop.")
    icon = constants.COMMAND_ICONS[constants.CMD_MIDPOINT_LINE]


def get_commands():
    """Command instances for JellyJams_Centerline and JellyJams_MidpointLine, keyed by id."""
    return {
        constants.CMD_CENTERLINE: CenterlineCommand(),
        constants.CMD_MIDPOINT_LINE: MidpointLineCommand(),
    }
