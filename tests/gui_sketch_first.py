# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Sketch-first test for profile features. Run inside the full FreeCAD GUI with a
throwaway config:

    FreeCAD.exe -u <copy of user.cfg> -s <copy of system.cfg> tests/gui_sketch_first.py

Presses the ribbon's Extruded Boss/Base exactly as a click does (ribbon.run_entry):

    A  a plane is selected: a sketch opens on it, no "No sketch" warning;
       after drawing and exiting the sketch, a Pad is created from it, and
       JellyJams stays the active workbench after the exit and after OK.
    B  nothing selected, no sketch: FreeCAD's plane picker opens instead of
       the warning; cancelling it leaves no pending sketch-first state.
    C  a finished free sketch exists: the press uses it directly.
    D  editing an existing Pad keeps JellyJams active; a switch to Part Design
       through Std_Workbench (the workbench selector, View > Workbench)
       still happens.

Results: <JELLYJAMS_RESULTS_DIR>/sketch_first.json (default <repo>/scratch).
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT_DIR = os.environ.get(
    "JELLYJAMS_RESULTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"),
)
os.makedirs(OUT_DIR, exist_ok=True)
RES = {"checks": {}, "info": {}, "errors": []}
PAD = "PartDesign_Pad"
CTX = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)[:600]}
    App.Console.PrintMessage(f"JellyJams-sketch-first {name}: {'OK' if ok else 'FAIL'} {detail}\n")


def finish():
    RES["ok"] = bool(RES["checks"]) and all(c["ok"] for c in RES["checks"].values()) and not RES["errors"]
    with open(os.path.join(OUT_DIR, "sketch_first.json"), "w", encoding="utf-8") as f:
        json.dump(RES, f, indent=2)
    # Unsaved documents would stop the quit at FreeCAD's "Save changes?" prompt.
    for name in list(App.listDocuments()):
        try:
            App.closeDocument(name)
        except Exception:
            pass
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


def guarded(fn):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(f"{fn.__name__}: {traceback.format_exc()}")
            finish()
    return run


def later(ms, fn):
    QtCore.QTimer.singleShot(ms, fn)


def press(cmd_id):
    from jellyjams import ribbon

    ribbon.run_entry(cmd_id)


def modal_text():
    modal = QtWidgets.QApplication.activeModalWidget()
    if modal is None:
        return None
    text = modal.windowTitle()
    if isinstance(modal, QtWidgets.QMessageBox):
        text += " | " + modal.text()
        modal.close()
    return text


def new_body_doc(name):
    doc = App.newDocument(name)
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    return doc, body


def plane(body, role):
    return next(f for f in body.Origin.OriginFeatures if getattr(f, "Role", "") == role)


def sketch_in_edit():
    vp = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument else None
    obj = vp.Object if vp is not None else None
    return obj if obj is not None and obj.TypeId == "Sketcher::SketchObject" else None


def draw_rectangle(sketch, w=30.0, h=20.0):
    import Part

    pts = [App.Vector(0, 0, 0), App.Vector(w, 0, 0), App.Vector(w, h, 0), App.Vector(0, h, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    sketch.Document.recompute()


def pads(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Pad"]


def profile_of(feature):
    value = feature.Profile
    return value[0] if isinstance(value, tuple) else value


def close_task_dialog(accept=False):
    """Press OK (accept) or Cancel in the open task dialog; fall back to closeDialog()."""
    wanted = QtWidgets.QDialogButtonBox.StandardButton.Ok if accept else QtWidgets.QDialogButtonBox.StandardButton.Cancel
    mw = Gui.getMainWindow()
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() not in ("Tasks", "Combo View", "ComboView"):
            continue
        for box in dock.findChildren(QtWidgets.QDialogButtonBox):
            button = box.button(wanted)
            if button is not None and button.isVisible():
                button.click()
                return
    try:
        Gui.Control.closeDialog()
    except Exception:
        pass


def wb_log(label):
    RES["info"].setdefault("workbench", []).append((label, Gui.activeWorkbench().name()))


def when_no_dialog(fn, waited=0):
    """Run fn once no task dialog is open (gives up waiting after 5 s)."""
    if Gui.Control.activeDialog() and waited < 5000:
        later(200, lambda: when_no_dialog(fn, waited + 200))
    else:
        RES["info"].setdefault("dialog_waits_ms", []).append(waited)
        fn()


# --- A: plane selected ------------------------------------------------------------------

@guarded
def start():
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(4000, a_press)


@guarded
def a_press():
    doc, body = new_body_doc("SketchFirstA")
    CTX["a"] = doc.Name
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(plane(body, "XY_Plane"))
    press(PAD)
    later(1500, a_in_sketch)


@guarded
def a_in_sketch():
    warning = modal_text()
    note("a_no_warning_dialog", warning is None, warning)
    sketch = sketch_in_edit()
    note("a_sketch_opened", sketch is not None, sketch.Name if sketch else None)
    if sketch is None:
        close_task_dialog()
        later(500, b_press)
        return
    # FreeCAD 1.1 stores an origin plane either directly or as Origin + "XY_Plane." sub-element.
    support = [(link[0].Name, tuple(link[1])) for link in (sketch.AttachmentSupport or [])]
    xy_name = plane(App.getDocument(CTX["a"]).getObject("Body"), "XY_Plane").Name
    on_xy = bool(support) and (support[0][0] == xy_name or any(s.startswith("XY_Plane") for s in support[0][1]))
    note("a_sketch_on_selected_plane", on_xy, (support, xy_name))
    CTX["a_sketch"] = sketch.Name
    draw_rectangle(sketch)
    wb_log("a_in_sketch")
    RES["info"]["a_prefs"] = {g: App.ParamGet("User parameter:BaseApp/Preferences/Mod/" + g).GetBool("SwitchToWB", True)
                              for g in ("PartDesign", "Assembly", "TechDraw/General")}
    Gui.runCommand("Sketcher_LeaveSketch")
    for ms in (100, 400, 1000, 2000):
        later(ms, lambda ms=ms: wb_log("a_after_leave_%dms" % ms))
    later(2500, a_after_exit)


@guarded
def a_after_exit():
    doc = App.getDocument(CTX["a"])
    made = pads(doc)
    note("a_pad_created_after_exit", len(made) == 1, [p.Name for p in made])
    if made:
        note("a_pad_uses_new_sketch", profile_of(made[0]).Name == CTX["a_sketch"], profile_of(made[0]).Name)
    from jellyjams import sketch_gesture

    note("a_no_pending_state", sketch_gesture._intent is None, sketch_gesture._intent)
    wb_log("a_pad_dialog_open")
    note("a_still_in_jellyjams_after_exit", Gui.activeWorkbench().name() == "JellyJamsWorkbench",
         Gui.activeWorkbench().name())
    close_task_dialog(accept=True)
    later(800, a_after_pad_ok)


@guarded
def a_after_pad_ok():
    wb_log("a_after_pad_ok")
    note("a_still_in_jellyjams_after_ok", Gui.activeWorkbench().name() == "JellyJamsWorkbench",
         Gui.activeWorkbench().name())
    when_no_dialog(b_press)


# --- B: nothing selected, no sketch ------------------------------------------------------------

@guarded
def b_press():
    from jellyjams import fcgui, sketch_gesture

    doc, _body = new_body_doc("SketchFirstB")
    CTX["b"] = doc.Name
    Gui.Selection.clearSelection()
    trace = RES["info"].setdefault("b_trace", [])
    real_advance, real_start = sketch_gesture.advance, sketch_gesture._maybe_start_sketch_first

    def traced_advance(intent, editing, dialog_open, created, now):
        result = real_advance(intent, editing, dialog_open, created, now)
        trace.append({"state": (intent or {}).get("state"), "editing": editing, "dialog": dialog_open,
                      "created": sorted(created), "result": (result[0] or {}).get("state"), "action": result[1],
                      "wb_active": fcgui.jellyjams_active()})
        return result

    def traced_start(cmd_id):
        ok = real_start(cmd_id)
        trace.append({"maybe_start": ok, "intent": dict(sketch_gesture._intent or {}, before=None)})
        return ok

    sketch_gesture.advance, sketch_gesture._maybe_start_sketch_first = traced_advance, traced_start
    CTX["b_restore"] = (real_advance, real_start)
    press(PAD)
    for ms in (50, 200, 600):
        later(ms, lambda ms=ms: trace.append({"t_ms": ms, "workbench": Gui.activeWorkbench().name(),
                                              "intent": (sketch_gesture._intent or {}).get("state")}))
    later(1500, b_picker_open)


@guarded
def b_picker_open():
    from jellyjams import sketch_gesture

    warning = modal_text()
    note("b_no_warning_dialog", warning is None, warning)
    note("b_plane_picker_open", bool(Gui.Control.activeDialog()), Gui.Control.activeDialog())
    note("b_waiting_for_plane", (sketch_gesture._intent or {}).get("state") == sketch_gesture.PICKING,
         sketch_gesture._intent)
    close_task_dialog()
    later(2500, b_after_cancel)


@guarded
def b_after_cancel():
    from jellyjams import sketch_gesture

    doc = App.getDocument(CTX["b"])
    note("b_cancel_drops_state", sketch_gesture._intent is None, sketch_gesture._intent)
    note("b_no_pad_after_cancel", not pads(doc), [p.Name for p in pads(doc)])
    sketch_gesture.advance, sketch_gesture._maybe_start_sketch_first = CTX["b_restore"]
    later(300, lambda: when_no_dialog(c_press))


# --- C: a free sketch exists ---------------------------------------------------------------------

@guarded
def c_press():
    doc, body = new_body_doc("SketchFirstC")
    CTX["c"] = doc.Name
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = (plane(body, "XY_Plane"), [""])
    sketch.MapMode = "FlatFace"
    draw_rectangle(sketch)
    CTX["c_sketch"] = sketch.Name
    Gui.Selection.clearSelection()
    press(PAD)
    later(1500, c_check)


@guarded
def c_check():
    from jellyjams import sketch_gesture

    doc = App.getDocument(CTX["c"])
    warning = modal_text()
    note("c_no_warning_dialog", warning is None, warning)
    made = pads(doc)
    note("c_pad_uses_existing_sketch", len(made) == 1 and profile_of(made[0]).Name == CTX["c_sketch"],
         [(p.Name, profile_of(p).Name) for p in made])
    note("c_no_new_sketch", len([o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]) == 1)
    note("c_no_pending_state", sketch_gesture._intent is None, sketch_gesture._intent)
    close_task_dialog(accept=True)
    later(500, lambda: when_no_dialog(d_edit_existing))


# --- D: editing an existing feature stays; a user's workbench switch still works ---------------

@guarded
def d_edit_existing():
    doc = App.getDocument(CTX["c"])
    pad = pads(doc)[0]
    Gui.ActiveDocument.setEdit(pad.Name)
    later(1200, d_check_edit)


@guarded
def d_check_edit():
    note("d_edit_feature_stays_in_jellyjams", Gui.activeWorkbench().name() == "JellyJamsWorkbench",
         Gui.activeWorkbench().name())
    note("d_feature_dialog_open", bool(Gui.Control.activeDialog()))
    close_task_dialog(accept=True)
    later(500, lambda: when_no_dialog(d_user_switch))


@guarded
def d_user_switch():
    actions = Gui.Command.get("Std_Workbench").getAction()
    index = [a.objectName() for a in actions].index("PartDesignWorkbench")
    Gui.runCommand("Std_Workbench", index)   # what the workbench dropdown and View > Workbench do
    later(1500, d_check_switch)


@guarded
def d_check_switch():
    note("d_user_switch_to_part_design_works", Gui.activeWorkbench().name() == "PartDesignWorkbench",
         Gui.activeWorkbench().name())
    finish()


App.Console.PrintMessage(f"JellyJams-sketch-first starting, results -> {OUT_DIR}\n")
later(4000, start)
