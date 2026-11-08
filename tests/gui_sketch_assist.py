# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Native sketch aids and exact restore; run through run_gui.py with scratch configs."""

import json
import os
import traceback
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "version": App.Version()}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=600):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, run)


def finish():
    with open(os.path.join(OUT, "sketch_assist.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


def snapping():
    from jellyjams import constants as C, params
    group = params.group(C.PARAM_SKETCH_SNAP)
    return {key: [params.has_key(group, key, "Bool"), group.GetBool(key)]
            for key in (C.KEY_SKETCH_SNAP, C.KEY_SKETCH_SNAP_OBJECTS)}


def active():
    return all(existed and value for existed, value in snapping().values())


def start():
    from jellyjams import constants as C, params
    Gui.activateWorkbench("PartDesignWorkbench")
    group = params.group(C.PARAM_SKETCH_SNAP)
    group.SetBool(C.KEY_SKETCH_SNAP, False)
    group.RemBool(C.KEY_SKETCH_SNAP_OBJECTS)
    group.SetBool("SnapToGrid", False)
    STATE["before"] = snapping()
    doc = App.newDocument("SketchAssist")
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    import Part
    sketch.addGeometry(Part.LineSegment(App.Vector(15, 10, 0), App.Vector(25, 10, 0)), False)
    sketch.ViewObject.Autoconstraints = False
    STATE["property_status"] = sketch.ViewObject.getPropertyStatus("Autoconstraints")
    other = doc.addObject("Sketcher::SketchObject", "OtherSketch")
    other.ViewObject.Autoconstraints = False
    other.Visibility = False
    doc.recompute()
    STATE.update(doc=doc, sketch=sketch, other=other)
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(idle, 4000)


def idle():
    note("idle_preferences_unchanged", snapping() == STATE["before"])
    Gui.activeDocument().setEdit(STATE["sketch"].Name)
    later(edited)


def edited():
    from jellyjams import constants as C, params
    sketch, other = STATE["sketch"], STATE["other"]
    note("editing_stays_in_jellyjams", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
    note("native_snapping_enabled", active(), snapping())
    note("native_auto_constraints_enabled", sketch.ViewObject.Autoconstraints)
    note("property_status_preserved", sketch.ViewObject.getPropertyStatus("Autoconstraints")
         == STATE["property_status"])
    note("other_sketch_preserved", not other.ViewObject.Autoconstraints)
    note("grid_snap_preserved", not params.group(C.PARAM_SKETCH_SNAP).GetBool("SnapToGrid"))
    note("snapping_backup_present", params.backup_pending(C.KEY_SKETCH_ASSIST_BACKUP))
    # Save while still in edit: check serialized GUI property, not just the live value.
    path = os.path.join(OUT, "sketch_assist.FCStd")
    STATE["doc"].saveAs(path)
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("GuiDocument.xml"))
    vp = root.find(".//ViewProvider[@name='Sketch']")
    prop = vp.find(".//Property[@name='Autoconstraints']/Bool")
    note("saved_auto_constraints_original", prop.attrib["value"] == "false", prop.attrib)
    note("live_auto_constraints_resumed_after_save", sketch.ViewObject.Autoconstraints)
    from jellyjams import sketch_assist
    saver = sketch_assist._autosaver
    note("native_recovery_save_filter_installed", saver is not None)
    dispatcher = QtCore.QAbstractEventDispatcher.instance()
    timers = dispatcher.registeredTimers(saver)
    # This process owns only our test document. Deliver its real registered timer
    # now, instead of waiting the native 15-minute recovery interval.
    note("native_recovery_timer_found", bool(timers), timers)
    QtWidgets.QApplication.sendEvent(saver, QtCore.QTimerEvent(timers[0].timerId))
    path = os.path.join(STATE["doc"].TransientDir, "fc_recovery_file.fcstd")
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("GuiDocument.xml"))
    prop = root.find(".//ViewProvider[@name='Sketch']//Property[@name='Autoconstraints']/Bool")
    note("recovery_file_auto_constraints_original", prop.attrib["value"] == "false", prop.attrib)
    later(start_line, 200)


def start_line():
    note("auto_constraints_resumed_after_recovery_save", STATE["sketch"].ViewObject.Autoconstraints)
    # Start the same native tool used by the ribbon; send real viewport input.
    view = Gui.activeDocument().activeView()
    view.viewTop()
    camera = view.getCameraNode()
    camera.position.setValue(12, 7, 100)
    camera.height = 45
    camera.focalDistance = 100
    camera.nearDistance = 1
    camera.farDistance = 1000
    Gui.runCommand("Sketcher_CreateLine")
    later(draw_origin)


def click_near(x, y):
    view = Gui.activeDocument().activeView()
    wrapper = next(w for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget)
                   if w.inherits("Gui::View3DInventor") and w.isVisible())
    gl = max((w for w in wrapper.findChildren(QtWidgets.QWidget)
              if w.inherits("QOpenGLWidget") and w.isVisible()), key=lambda w: w.width() * w.height())
    screen = view.getPointOnScreen(App.Vector(x, y, 0))
    # Coin's viewport origin is at the bottom left; Qt's is at the top left.
    ratio = gl.devicePixelRatioF()
    point = QtCore.QPoint(round(screen[0] / ratio) + 2,
                         gl.height() - 1 - round(screen[1] / ratio) + 2)
    STATE.setdefault("clicks", []).append({"world": [x, y], "screen": list(screen),
                                         "qt": [point.x(), point.y()], "ratio": ratio,
                                         "viewport": [gl.width(), gl.height()]})
    RES["clicks"] = STATE["clicks"]
    for kind, button, buttons in (
        (QtCore.QEvent.Type.MouseMove, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton),
        (QtCore.QEvent.Type.MouseButtonPress, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton),
        (QtCore.QEvent.Type.MouseButtonRelease, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton),
    ):
        event = QtGui.QMouseEvent(kind, QtCore.QPointF(point), QtCore.QPointF(gl.mapToGlobal(point)),
                                 button, buttons, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(gl, event)


def draw_origin():
    click_near(0, 0)
    later(draw_corner, 200)


def draw_corner():
    click_near(15, 10)
    later(check_line, 200)


def check_line():
    sketch = STATE["sketch"]
    note("native_line_created", sketch.GeometryCount == 2, sketch.GeometryCount)
    if sketch.GeometryCount == 2:
        line = sketch.Geometry[1]
        note("native_line_snaps_to_origin", line.StartPoint.Length < 1e-7, line.StartPoint)
        note("native_line_snaps_to_corner", (line.EndPoint - App.Vector(15, 10, 0)).Length < 1e-7,
             line.EndPoint)
        coincident = [c for c in sketch.Constraints if c.Type == "Coincident"]
        note("native_coincident_constraints_created", len(coincident) >= 2,
             [(c.First, c.FirstPos, c.Second, c.SecondPos) for c in coincident])
    # A second line ends on the interior of an existing edge, away from its
    # midpoint. Check both the snapped coordinate and persistent native relation.
    click_near(5, 3)
    later(draw_edge, 200)


def draw_edge():
    click_near(18, 10)
    later(check_edge, 200)


def check_edge():
    sketch = STATE["sketch"]
    note("native_edge_line_created", sketch.GeometryCount == 3, sketch.GeometryCount)
    if sketch.GeometryCount == 3:
        line = sketch.Geometry[2]
        note("native_line_snaps_to_edge", abs(line.EndPoint.y - 10) < 1e-7, line.EndPoint)
        note("native_point_on_object_created", any(c.Type == "PointOnObject"
             and c.First == 2 and c.Second == 0 for c in sketch.Constraints),
             [(c.Type, c.First, c.Second) for c in sketch.Constraints])
    Gui.runCommand("Sketcher_LeaveSketch")
    later(closed)


def closed():
    from jellyjams import constants as C, params
    note("close_preferences_restored", snapping() == STATE["before"], snapping())
    note("close_auto_constraints_restored", not STATE["sketch"].ViewObject.Autoconstraints)
    note("close_backup_removed", C.KEY_SKETCH_ASSIST_BACKUP not in params.own().GetStrings())
    Gui.activeDocument().setEdit(STATE["sketch"].Name)
    later(leave_open)


def leave_open():
    from jellyjams import lifecycle
    note("reentry_enables_again", active() and STATE["sketch"].ViewObject.Autoconstraints)
    lifecycle.revert_for_quit()
    note("quit_preferences_restored", snapping() == STATE["before"])
    note("quit_auto_constraints_restored", not STATE["sketch"].ViewObject.Autoconstraints)
    lifecycle.reapply_after_cancel()
    note("cancel_resumes_aids", active() and STATE["sketch"].ViewObject.Autoconstraints)
    Gui.activateWorkbench("PartDesignWorkbench")
    later(left, 4000)


def left():
    from jellyjams import constants as C, params
    note("leave_preferences_restored", snapping() == STATE["before"])
    note("leave_auto_constraints_restored", not STATE["sketch"].ViewObject.Autoconstraints)
    note("leave_backup_removed", C.KEY_SKETCH_ASSIST_BACKUP not in params.own().GetStrings())
    from jellyjams import sketch_assist
    note("leave_recovery_filter_removed", sketch_assist._autosaver is None)
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(already_open, 4000)


def already_open():
    note("enter_workbench_with_open_sketch", active() and STATE["sketch"].ViewObject.Autoconstraints)
    Gui.runCommand("Sketcher_LeaveSketch")
    later(absent_keys)


def absent_keys():
    from jellyjams import constants as C, params
    group = params.group(C.PARAM_SKETCH_SNAP)
    for key in (C.KEY_SKETCH_SNAP, C.KEY_SKETCH_SNAP_OBJECTS):
        group.RemBool(key)
    STATE["before"] = snapping()
    Gui.activeDocument().setEdit(STATE["sketch"].Name)
    later(absent_edit)


def absent_edit():
    note("absent_keys_enabled_in_edit", active())
    Gui.runCommand("Sketcher_LeaveSketch")
    later(absent_closed)


def absent_closed():
    note("absent_keys_removed_after_edit", snapping() == STATE["before"], snapping())
    finish()


later(start, 5000)
