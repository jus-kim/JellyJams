# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""One-click sketch-first planes in the native list and 3D view, with scratch configs."""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "version": App.Version()}
STATE = {"case": -1}
CASES = (("XY_Plane", "list"), ("XY_Plane", "view"),
         ("XZ_Plane", "view"), ("YZ_Plane", "view"))
SELECTION_PATH = "User parameter:BaseApp/Preferences/Selection"


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=400):
    def call():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, call)


def finish():
    with open(os.path.join(OUT, "plane_pick.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    try:
        if Gui.activeDocument() and Gui.activeDocument().getInEdit():
            Gui.runCommand("Sketcher_LeaveSketch")
    except Exception:
        pass
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    QtCore.QTimer.singleShot(400, QtWidgets.QApplication.instance().quit)


def picker():
    from jellyjams import fcgui
    panel = fcgui.task_panel()
    if panel is None:
        return None
    for widget in panel.findChildren(QtWidgets.QWidget):
        names = (widget.metaObject().className().replace("__", "::"), widget.objectName().replace("__", "::"))
        if any(name in ("PartDesignGui::TaskFeaturePick", "PartGui::TaskAttacher") for name in names):
            return widget
    return None


def mouse(widget, position, click=True):
    events = [(QtCore.QEvent.Type.MouseMove, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton)]
    if click:
        events += [(QtCore.QEvent.Type.MouseButtonPress, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton),
                   (QtCore.QEvent.Type.MouseButtonRelease, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton)]
    for kind, button, buttons in events:
        QtWidgets.QApplication.sendEvent(widget, QtGui.QMouseEvent(
            kind, QtCore.QPointF(position), QtCore.QPointF(widget.mapToGlobal(position)),
            button, buttons, QtCore.Qt.KeyboardModifier.NoModifier))


def start():
    Gui.activateWorkbench("JellyJamsWorkbench")
    App.ParamGet("User parameter:BaseApp/Preferences/View").SetBool("UseNavigationAnimations", False)
    # Model a user who has native double-click confirmation enabled. Production
    # must not change this preference, even temporarily.
    App.ParamGet(SELECTION_PATH).SetBool("singleClickFeatureSelect", False)
    later(next_case, 3500)


def next_case():
    from jellyjams import ribbon
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    STATE["case"] += 1
    if STATE["case"] == len(CASES):
        later(cancel_case)
        return
    role, mode = CASES[STATE["case"]]
    STATE["tag"] = role + "_" + mode
    STATE["doc"] = App.newDocument("PlanePick" + str(STATE["case"]))
    Gui.Selection.clearSelection()
    ribbon.run_entry("PartDesign_Pad")
    if mode == "view":
        # A previous empty sketch can leave the next document in a tiny Top
        # view. Present the three planes in the isometric view used by the UI.
        view = Gui.activeDocument().activeView()
        view.viewIsometric()
        camera = view.getCameraNode()
        eye = view.getCameraOrientation().multVec(App.Vector(0, 0, 100))
        camera.position.setValue(eye.x, eye.y, eye.z)
        camera.focalDistance = 100
        camera.height = 80
        camera.nearDistance = 1
        camera.farDistance = 1000
    later(choose, 1000)


def choose():
    from jellyjams import fcgui
    doc = STATE["doc"]
    tag = STATE["tag"]
    form = picker()
    note(tag + "_waits_for_choice", form is not None and fcgui.sketch_in_edit() is None)
    if form is None:
        RES['widgets'] = [(w.metaObject().className(), w.objectName()) for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget) if 'task' in (w.metaObject().className() + w.objectName()).lower() or isinstance(w, QtWidgets.QListWidget)]
        RES['objects'] = [(o.Name, o.TypeId) for o in doc.Objects]
        Gui.getMainWindow().grab().save(os.path.join(OUT, 'picker.png'))
        raise RuntimeError('native plane picker form not found')
    choices = form.findChild(QtWidgets.QListWidget, "listWidget")
    role, mode = CASES[STATE["case"]]
    body = next(obj for obj in doc.Objects if obj.TypeId == "PartDesign::Body")
    plane = next(obj for obj in body.Origin.OriginFeatures if getattr(obj, "Role", "") == role)
    STATE["plane"] = plane
    if mode == "list":
        if choices is not None:
            row = next(choices.item(i) for i in range(choices.count())
                       if choices.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == plane.Name)
            choices.scrollToItem(row)
            mouse(choices.viewport(), choices.visualItemRect(row).center())
        else:
            # The 26.3 attachment editor has no plane list; exercise the same
            # one-plane native selection notification used by the viewport.
            Gui.Selection.addSelection(doc.Name, plane.Name)
    else:
        gl = max((w for w in fcgui.active_mdi_widget().findChildren(QtWidgets.QWidget)
                  if w.inherits("QOpenGLWidget") and w.isVisible()), key=lambda w: w.width() * w.height())
        view = Gui.activeDocument().activeView()
        ratio = gl.devicePixelRatioF()
        from pivy import coin
        region = coin.SbViewportRegion(round(gl.width() * ratio), round(gl.height() * ratio))
        scene = coin.SoSeparator()
        scene.addChild(view.getCameraNode())
        scene.addChild(view.getSceneGraph())
        picked = None
        examples = []
        zero_axis = {"XY_Plane": 2, "XZ_Plane": 1, "YZ_Plane": 0}[role]
        other_axes = [axis for axis in range(3) if axis != zero_axis]
        # Include the camera: getSceneGraph exposes document contents, while
        # the render manager's full scene also supplies the camera. Find an
        # unobscured point on the actual plane before sending exactly one click.
        for radius in (0.5, 1, 2, 4, 8, 10, 12, 14, 16, 20, 24, 32):
            world = [radius, radius, radius]
            world[zero_axis] = 0
            screen = view.getPointOnScreen(App.Vector(*world))
            point = QtCore.QPoint(round(screen[0] / ratio), gl.height() - 1 - round(screen[1] / ratio))
            if not gl.rect().contains(point):
                continue
            action = coin.SoRayPickAction(region)
            action.setPoint(coin.SbVec2s(round(point.x() * ratio), round((gl.height() - 1 - point.y()) * ratio)))
            action.setRadius(0)
            action.apply(scene)
            hit = action.getPickedPoint()
            if hit is not None:
                position = list(hit.getPoint().getValue())
                examples.append(position)
                if abs(position[zero_axis]) < 1e-4 and all(abs(position[axis]) > 1e-3 for axis in other_axes):
                    picked = point
                    RES.setdefault("ray_picks", {})[tag] = position
                    break
        note(tag + "_plane_hit_found", picked is not None, examples)
        if picked is None:
            Gui.getMainWindow().grab().save(os.path.join(OUT, "missing_plane.png"))
            RES["view_debug"] = {"size": [gl.width(), gl.height()], "ratio": ratio,
                                 "camera": str(view.getCamera()), "plane": plane.Name}
            raise RuntimeError("could not ray-pick " + role)
        mouse(gl, picked)
    STATE["clicks"] = 1
    later(entered, 700)


def entered():
    from jellyjams import fcgui, sketch_gesture
    tag = STATE["tag"]
    sketch = fcgui.sketch_in_edit()
    note(tag + "_one_click_enters_sketch", sketch is not None and STATE["clicks"] == 1)
    if sketch is None:
        choices = picker().findChild(QtWidgets.QListWidget, "listWidget") if picker() else None
        panel = fcgui.task_panel()
        details = [(obj.Name, str(getattr(obj, 'MapMode', '')), str(getattr(obj, 'AttachmentSupport', ''))) for obj in STATE['doc'].Objects if obj.TypeId == 'Sketcher::SketchObject']
        RES['attachment_debug'] = {'objects': details, 'intent': str(sketch_gesture._intent), 'active_same': sketch_gesture._active_doc() is STATE['doc'], 'helper': sketch_gesture._attachment_has_plane(sketch_gesture._intent, STATE['doc']), 'buttons': [(box.objectName(), [(b.text(), b.isEnabled(), b.isVisibleTo(panel)) for b in box.buttons()]) for box in panel.findChildren(QtWidgets.QDialogButtonBox)]}
        RES.setdefault("picker_state", {})[tag] = {
            "selection": str(Gui.Selection.getSelectionEx()),
            "rows": [item.text() for item in choices.selectedItems()] if choices else []}
        raise RuntimeError("single plane click did not enter sketch: " + tag)
    support = str(sketch.AttachmentSupport)
    note(tag + "_correct_support", STATE["plane"].Name in support or CASES[STATE["case"]][0] in support, support)
    note(tag + "_only_one_sketch", len([obj for obj in STATE["doc"].Objects
                                        if obj.TypeId == "Sketcher::SketchObject"]) == 1)
    note(tag + "_stays_in_jellyjams", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
    note(tag + "_watcher_tracks_edit", (sketch_gesture._intent or {}).get("state") == sketch_gesture.EDITING)
    note(tag + "_user_preference_unchanged", not App.ParamGet(SELECTION_PATH).GetBool("singleClickFeatureSelect", True))
    Gui.runCommand("Sketcher_LeaveSketch")
    later(next_case, 500)


def cancel_case():
    from jellyjams import ribbon
    STATE["doc"] = App.newDocument("CancelPlanePick")
    ribbon.run_entry("PartDesign_Pad")
    later(cancel)


def cancel():
    from jellyjams import fcgui
    note("cancel_picker_open", picker() is not None)
    panel = fcgui.task_dock()
    button = next(box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
                  for box in panel.findChildren(QtWidgets.QDialogButtonBox)
                  if box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel) is not None)
    button.click()
    later(cancelled, 2000)


def cancelled():
    from jellyjams import sketch_gesture
    note("cancel_drops_intent", sketch_gesture._intent is None)
    note("cancel_creates_no_sketch", not any(obj.TypeId == "Sketcher::SketchObject" for obj in STATE["doc"].Objects))
    note("preference_still_unchanged", not App.ParamGet(SELECTION_PATH).GetBool("singleClickFeatureSelect", True))
    finish()


later(start, 5000)
