# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Real native orbit/pan/zoom regression, including an ultrawide viewport.

Run through run_gui.py --suites orbit, always with disposable configurations.
"""

import json
import math
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "info": {"version": App.Version(), "measurements": []}}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=1000):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, run)


def settings():
    wanted = {"OrbitStyle", "Sensitivity", "RotationMode", "ResetCursorPosition"}
    return sorted(e for e in (App.ParamGet("User parameter:BaseApp/Preferences/View").GetContents() or [])
                  if e[1] in wanted)


def start():
    grp = App.ParamGet("User parameter:BaseApp/Preferences/View")
    grp.SetInt("OrbitStyle", 4)
    grp.SetInt("RotationMode", 0)
    grp.SetBool("UseNavigationAnimations", False)
    STATE["settings"] = settings()
    Gui.activateWorkbench("JellyJamsWorkbench")
    doc = App.newDocument("OrbitCheck")
    doc.addObject("Part::Box", "Box")
    doc.recompute()
    later(measure, 4500)


def viewport():
    view = next(w for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget)
                if w.inherits("Gui::View3DInventor") and w.isVisible())
    return max((w for w in view.findChildren(QtWidgets.QWidget)
                if w.inherits("QOpenGLWidget") and w.isVisible()), key=lambda w: w.width() * w.height())


def mouse(widget, kind, position, button, buttons, modifiers):
    event = QtGui.QMouseEvent(kind, QtCore.QPointF(position),
                             QtCore.QPointF(widget.mapToGlobal(position)), button, buttons, modifiers)
    QtWidgets.QApplication.sendEvent(widget, event)


def reset_camera():
    view = Gui.activeDocument().activeView()
    camera = view.getCameraNode()
    camera.orientation.setValue(0, 0, 0, 1)
    camera.position.setValue(5, 5, 100)
    camera.height = 40
    camera.focalDistance = 95
    camera.nearDistance = 1
    camera.farDistance = 1000
    return view


def camera_state(view):
    camera = view.getCameraNode()
    return (tuple(camera.position.getValue()) + tuple(view.getCameraOrientation().Q)
            + (camera.height.getValue(), camera.focalDistance.getValue()))


def drag(dx, dy, modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    gl = viewport()
    view = reset_camera()
    before = view.getCameraOrientation()
    pos = gl.rect().center()
    middle, none = QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.NoButton
    mouse(gl, QtCore.QEvent.Type.MouseButtonPress, pos, middle, middle, modifiers)
    for i in range(1, 11):
        mouse(gl, QtCore.QEvent.Type.MouseMove, pos + QtCore.QPoint(dx * i // 10, dy * i // 10),
              none, middle, modifiers)
    mouse(gl, QtCore.QEvent.Type.MouseButtonRelease, pos + QtCore.QPoint(dx, dy), middle, none, modifiers)
    delta = view.getCameraOrientation().multiply(before.inverted())
    return math.degrees(delta.Angle), camera_state(view)


def near(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) < 1e-5


def enable_orbit():
    from jellyjams import orbit

    orbit.install()
    # Discovery intentionally waits until the current native callback has ended.
    # Synthetic events below must give that deferred setup an event-loop turn.
    QtTest.QTest.qWait(20)


def modifier_transition():
    """A real key event between orbit and pan must not create a camera jump."""
    gl = viewport()
    view = reset_camera()
    middle, none = QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.NoButton
    no_mod, ctrl = QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.KeyboardModifier.ControlModifier
    pos = gl.rect().center()
    mouse(gl, QtCore.QEvent.Type.MouseButtonPress, pos, middle, middle, no_mod)
    pos += QtCore.QPoint(100, 0)
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, no_mod)
    before = camera_state(view)
    key = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Control, ctrl)
    QtWidgets.QApplication.sendEvent(gl, key)
    # No physical movement at the modifier transition means no camera movement.
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, ctrl)
    note("ctrl_transition_no_jump", near(before, camera_state(view)))
    pos += QtCore.QPoint(20, 0)
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, ctrl)
    after_pan = camera_state(view)
    note("ctrl_transition_still_pans", not near(before[:3], after_pan[:3]) and near(before[3:], after_pan[3:]))
    QtWidgets.QApplication.sendEvent(gl, QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyRelease, QtCore.Qt.Key.Key_Control, no_mod))
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, no_mod)
    note("orbit_transition_no_jump", near(after_pan, camera_state(view)))
    pos += QtCore.QPoint(20, 0)
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, no_mod)
    note("orbit_transition_still_rotates", not near(after_pan[3:7], camera_state(view)[3:7]))
    mouse(gl, QtCore.QEvent.Type.MouseButtonRelease, pos, middle, none, no_mod)


def measure():
    from jellyjams import orbit

    grp = App.ParamGet("User parameter:BaseApp/Preferences/View")
    note("new_view_watched", viewport() in orbit._filter.watched)
    for width in (1800, 4800):
        Gui.getMainWindow().resize(width, 1150)
        QtTest.QTest.qWait(200)
        gl = viewport()
        label = "wide" if width == 4800 else "normal"
        for style in range(5):
            grp.SetInt("OrbitStyle", style)
            horizontal, _state = drag(100, 0)
            vertical, _state = drag(0, 100)
            detail = dict(size=(gl.width(), gl.height()), orbit=style, x=horizontal, y=vertical)
            RES["info"]["measurements"].append(detail)
            note(label + "_balanced_orbit_" + str(style), vertical > 1 and
                 abs(horizontal / vertical - 1) < 0.08, detail)
        grp.SetInt("OrbitStyle", 4)
        orbit.uninstall()
        native_x, _state = drag(100, 0)
        native_y, _state = drag(0, 100)
        if label == "wide":
            note("native_wide_imbalance_reproduced", native_x < native_y * 0.6,
                 dict(x=native_x, y=native_y))
            STATE["native_wide"] = native_x
            STATE["native_wide_size"] = (gl.width(), gl.height())
        native_pan = drag(100, 20, QtCore.Qt.KeyboardModifier.ControlModifier)
        native_zoom = drag(0, 100, QtCore.Qt.KeyboardModifier.ShiftModifier)
        native_click = drag(0, 0)
        enable_orbit()
        pan = drag(100, 20, QtCore.Qt.KeyboardModifier.ControlModifier)
        zoom = drag(0, 100, QtCore.Qt.KeyboardModifier.ShiftModifier)
        click = drag(0, 0)
        note(label + "_pan_matches_native", near(pan[1], native_pan[1]), (pan, native_pan))
        note(label + "_zoom_matches_native", near(zoom[1], native_zoom[1]), (zoom, native_zoom))
        note(label + "_middle_click_matches_native", near(click[1], native_click[1]), (click, native_click))
    modifier_transition()
    gl, view = viewport(), reset_camera()
    pos = gl.rect().center()
    middle, none = QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.NoButton
    no_mod = QtCore.Qt.KeyboardModifier.NoModifier
    mouse(gl, QtCore.QEvent.Type.MouseButtonPress, pos, middle, middle, no_mod)
    pos += QtCore.QPoint(100, 0)
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos, none, middle, no_mod)
    before = camera_state(view)
    orbit.uninstall()
    note("remove_mid_drag_does_not_move_camera", near(before, camera_state(view)))
    mouse(gl, QtCore.QEvent.Type.MouseMove, pos + QtCore.QPoint(20, 0), none, none, no_mod)
    note("remove_mid_drag_releases_native_orbit", near(before, camera_state(view)))
    mouse(gl, QtCore.QEvent.Type.MouseButtonRelease, pos, middle, none, no_mod)
    enable_orbit()
    grp.SetBool("ResetCursorPosition", True)
    x, _state = drag(100, 0)
    note("cursor_warp_keeps_native_orbit", abs(x - STATE["native_wide"]) < 0.1)
    grp.RemBool("ResetCursorPosition")
    grp.SetInt("OrbitStyle", 4)
    note("navigation_preferences_unchanged", settings() == STATE["settings"])
    later(feature_setup)


def feature_setup():
    import Part

    doc = App.ActiveDocument
    doc.getObject("Box").Visibility = False
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    points = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    for a, b in zip(points, points[1:]):
        sketch.addGeometry(Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0)), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10
    doc.recompute()
    sketch.Visibility = False
    STATE["feature_cycle"] = 0
    later(feature_open, 300)


def feature_open():
    Gui.ActiveDocument.setEdit("Pad")
    later(feature_close, 200)


def feature_close():
    # This exact transition crashed inside PySide's QObject child traversal
    # when the orbit watcher scanned synchronously from focusChanged.
    for box in Gui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        if not box.isVisible():
            continue
        button = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if button is not None and button.isVisible():
            button.setFocus()
            QtWidgets.QApplication.processEvents()
            button.click()
            later(feature_check, 200)
            return
    raise RuntimeError("No visible Pad OK button")


def feature_check():
    cycle = STATE["feature_cycle"]
    angle, _state = drag(100, 0)
    pad = App.ActiveDocument.getObject("Pad")
    note("feature_close_then_orbit_%02d" % cycle,
         Gui.ActiveDocument.getInEdit() is None and Gui.activeWorkbench().name() == "JellyJamsWorkbench"
         and abs(pad.Shape.Volume - 1000) < 1e-5 and angle > 1,
         dict(volume=pad.Shape.Volume, angle=angle))
    STATE["feature_cycle"] += 1
    if STATE["feature_cycle"] < 20:
        later(feature_open, 100)
        return
    Gui.activateWorkbench("PartDesignWorkbench")
    later(restored, 4000)


def restored():
    from jellyjams import orbit

    note("filter_removed_on_leave", orbit._filter is None)
    note("original_orbit_preferences_retained", settings() == STATE["settings"])
    # Use the same native button mapping for this isolated post-removal check.
    # It is restored before the test exits.
    grp = App.ParamGet("User parameter:BaseApp/Preferences/View")
    entries = grp.GetContents() or []
    original = next((e[2] for e in entries if e[1] == "NavigationStyle"), None)
    grp.SetString("NavigationStyle", "Gui::SolidWorksNavigationStyle")
    # Leaving restores dock/toolbars, which changes viewport dimensions. Native
    # orbit response depends on those dimensions, so recreate the measured
    # viewport before comparing with the pre-install native baseline.
    wanted_width, wanted_height = STATE["native_wide_size"]
    window, gl = Gui.getMainWindow(), viewport()
    window.resize(window.width() + wanted_width - gl.width(),
                  window.height() + wanted_height - gl.height())
    QtTest.QTest.qWait(200)
    # Windows may clamp the outer window to the monitor's maximum track size
    # after stock toolbars return. Control the whole test 3D view in that case;
    # retain the exact dimension assertion instead of comparing different views.
    # Resizing only QOpenGLWidget leaves Coin's native viewer viewport at the
    # old size, so its parent View3DInventor must participate in the resize.
    host = gl
    while not host.inherits("Gui::View3DInventor"):
        host = host.parentWidget()
    minimum, maximum = host.minimumSize(), host.maximumSize()
    fixed = (gl.width(), gl.height()) != (wanted_width, wanted_height)
    try:
        if fixed:
            host.setFixedSize(host.width() + wanted_width - gl.width(),
                              host.height() + wanted_height - gl.height())
            QtTest.QTest.qWait(200)
        x, _state = drag(100, 0)
        size = (viewport().width(), viewport().height())
    finally:
        if fixed:
            host.setMinimumSize(minimum)
            host.setMaximumSize(maximum)
    note("native_response_restored", size == STATE["native_wide_size"]
         and abs(x - STATE["native_wide"]) < 0.1,
         dict(expected_size=STATE["native_wide_size"], actual_size=size,
              expected_angle=STATE["native_wide"], actual_angle=x,
              viewport_fixed_size_fallback=fixed))
    if original is None:
        grp.RemString("NavigationStyle")
    else:
        grp.SetString("NavigationStyle", original)
    finish()


def finish():
    try:
        if App.ActiveDocument:
            App.closeDocument(App.ActiveDocument.Name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        RES["errors"].append(traceback.format_exc())
    RES["ok"] = not RES["errors"] and all(c["ok"] for c in RES["checks"].values())
    with open(os.path.join(OUT, "orbit.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


later(start, 2000)
