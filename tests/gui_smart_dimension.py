# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Native Smart Dimension placement and cleanup; run with run_gui.py scratch configs."""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "version": App.Version()}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=250):
    def call():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, call)


def finish():
    with open(os.path.join(OUT, "smart_dimension.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


def viewport():
    from jellyjams import fcgui
    return max((w for w in fcgui.active_mdi_widget().findChildren(QtWidgets.QWidget)
                if w.inherits("QOpenGLWidget") and w.isVisible()), key=lambda w: w.width() * w.height())


def move(x, y, click=False):
    gl = viewport()
    view = Gui.activeDocument().activeView()
    screen = view.getPointOnScreen(App.Vector(x, y, 0))
    ratio = gl.devicePixelRatioF()
    point = QtCore.QPoint(round(screen[0] / ratio), gl.height() - 1 - round(screen[1] / ratio))
    kinds = [(QtCore.QEvent.Type.MouseMove, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton)]
    if click:
        kinds += [(QtCore.QEvent.Type.MouseButtonPress, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton),
                  (QtCore.QEvent.Type.MouseButtonRelease, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton)]
    for kind, button, buttons in kinds:
        event = QtGui.QMouseEvent(kind, QtCore.QPointF(point), QtCore.QPointF(gl.mapToGlobal(point)),
                                 button, buttons, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(gl, event)
    return view.getPoint(round(point.x() * ratio), round((gl.height() - 1 - point.y()) * ratio))


def alignment(index, point, name):
    sketch = STATE["sketch"]
    c = sketch.Constraints[index]
    a = sketch.Geometry[c.First].StartPoint
    b = sketch.Geometry[c.First].EndPoint
    if c.Type == "DistanceX":
        normal = App.Vector(0, 1 if b.x >= a.x else -1, 0)
    elif c.Type == "DistanceY":
        normal = App.Vector(-1 if b.y >= a.y else 1, 0, 0)
    else:
        delta = b - a
        delta.normalize()
        normal = App.Vector(-delta.y, delta.x, 0)
    expected = (point - a).dot(normal)
    actual = sketch.getLabelDistance(index)
    pixels = abs(actual - expected) * viewport().height() / 40
    note(name, pixels < 1.1, {"type": c.Type, "actual": actual, "expected": expected, "error_px": pixels})


def start():
    from jellyjams import sketch_dimension
    Gui.activateWorkbench("JellyJamsWorkbench")
    doc = App.newDocument("SmartDimensionCheck")
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    import Part
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(30, 0, 0)), False)
    sketch.addGeometry(Part.LineSegment(App.Vector(40, 0, 0), App.Vector(40, 25, 0)), False)
    doc.recompute()
    STATE.update(doc=doc, sketch=sketch)
    Gui.activeDocument().setEdit(sketch.Name)
    note("no_filter_before_smart_dimension", sketch_dimension._session is None)
    later(camera, 3500)


def camera():
    view = Gui.activeDocument().activeView()
    view.viewTop()
    cam = view.getCameraNode()
    cam.position.setValue(25, 10, 100)
    cam.height = 40
    cam.focalDistance = 100
    cam.nearDistance = 1
    cam.farDistance = 1000
    later(tool)


def tool():
    from jellyjams import ribbon, sketch_dimension
    move(15, 0)
    before = QtGui.QCursor.pos()
    ribbon.run_entry("Sketcher_Dimension")
    note("filter_started_by_ribbon", sketch_dimension._session is not None)
    after = QtGui.QCursor.pos()
    note("pointer_not_warped", (after - before).manhattanLength() <= 1,
         {"before": [before.x(), before.y()], "after": [after.x(), after.y()]})
    move(15, 0, True)
    later(horizontal)


def horizontal():
    note("horizontal_preview_created", len(STATE["sketch"].Constraints) == 1)
    point = move(15, 7)
    alignment(0, point, "horizontal_preview_at_pointer")
    for _ in range(4):
        point = move(16, 9)
    alignment(0, point, "repeated_moves_do_not_accumulate_gap")
    later(lambda: confirm(16, 9, confirmed_horizontal))


def confirm(x, y, next_step):
    def accept():
        modal = QtWidgets.QApplication.activeModalWidget()
        note("native_value_dialog_%d" % len(STATE["sketch"].Constraints), isinstance(modal, QtWidgets.QDialog))
        if modal is not None:
            modal.accept()
        later(next_step)
    later(accept, 200)
    move(x, y, True)


def confirmed_horizontal():
    sketch = STATE["sketch"]
    note("native_horizontal_length_unchanged", abs(sketch.Geometry[0].length() - 30) < 1e-7)
    STATE["first_label"] = sketch.getLabelDistance(0)
    move(18, 14)
    move(19, 14)
    note("confirmed_label_stays_put", abs(sketch.getLabelDistance(0) - STATE["first_label"]) < 1e-6)
    move(40, 12.5, True)
    later(vertical)


def vertical():
    note("continuous_second_preview_created", len(STATE["sketch"].Constraints) == 2)
    point = move(47, 12.5)
    alignment(1, point, "vertical_preview_at_pointer")
    gl = viewport()
    for kind in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(gl, QtGui.QKeyEvent(kind, QtCore.Qt.Key.Key_Escape,
                                                           QtCore.Qt.KeyboardModifier.NoModifier))
    later(cancelled)


def cancelled():
    sketch = STATE["sketch"]
    note("escape_cancels_only_second_preview", len(sketch.Constraints) == 1)
    note("cancel_preserves_first_label", abs(sketch.getLabelDistance(0) - STATE["first_label"]) < 1e-6)
    move(40, 12.5, True)
    later(vertical_again)


def vertical_again():
    point = move(47, 12.5)
    alignment(1, point, "preview_aligned_after_cancel")
    later(lambda: confirm(47, 12.5, confirmed_both))


def confirmed_both():
    from jellyjams import ribbon, sketch_dimension
    sketch = STATE["sketch"]
    note("two_native_dimensions_confirmed", len(sketch.Constraints) == 2)
    note("native_vertical_length_unchanged", abs(sketch.Geometry[1].length() - 25) < 1e-7)
    STATE["labels"] = [sketch.getLabelDistance(i) for i in range(2)]
    for _ in range(4):
        move(18, 14)
    note("completed_dimensions_do_not_drift", STATE["labels"] == [sketch.getLabelDistance(i) for i in range(2)])
    ribbon.run_entry("Sketcher_CreateLine")
    note("next_ribbon_tool_removes_filter", sketch_dimension._session is None)
    Gui.runCommand("Sketcher_LeaveSketch")
    later(reopen)


def reopen():
    from jellyjams import ribbon, sketch_dimension
    Gui.activeDocument().setEdit(STATE["sketch"].Name)
    ribbon.run_entry("Sketcher_Dimension")
    note("filter_can_restart", sketch_dimension._session is not None)
    Gui.activateWorkbench("PartDesignWorkbench")
    later(left, 3500)


def left():
    from jellyjams import sketch_dimension
    note("leaving_jellyjams_removes_filter", sketch_dimension._session is None)
    note("labels_preserved_on_leave", STATE["labels"] == [STATE["sketch"].getLabelDistance(i) for i in range(2)])
    # End the native continuous tool before destroying its document. Older
    # FreeCAD builds can tear it down out of order on direct document closure.
    Gui.runCommand("Sketcher_LeaveSketch")
    later(finish)


later(start, 5000)
