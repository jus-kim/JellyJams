# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Real S/D, context return and native task controls with disposable profiles."""

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


def later(fn, ms=400):
    def call():
        try:
            with open(os.path.join(OUT, "quick_access_progress.json"), "w", encoding="utf-8") as stream:
                json.dump({"phase": fn.__name__, "checks": RES["checks"]}, stream, indent=2)
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, call)


def finish():
    with open(os.path.join(OUT, "quick_access.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    try:
        if Gui.activeDocument() and Gui.activeDocument().getInEdit():
            Gui.activeDocument().resetEdit()
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        pass
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


def key(widget, letter, text="", modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    widget.setFocus()
    QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress, letter, modifiers, text))
    QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyRelease, letter, modifiers, text))


def view_widget():
    from jellyjams import fcgui
    sheet = fcgui.active_sheet_window()
    if sheet is not None:
        return fcgui.sheet_graphics_view(sheet).viewport()
    host = fcgui.active_mdi_widget()
    return max((w for w in host.findChildren(QtWidgets.QWidget)
                if w.inherits("QOpenGLWidget") and w.isVisible()), key=lambda w: w.width() * w.height())


def popup():
    from jellyjams import quick_access
    service = quick_access._service
    return service.popup if service and service.popup and service.popup.isVisible() else None


def selection():
    return [(s.Object.Name, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]


def start():
    import Part
    from jellyjams import ribbon
    App.ParamGet("User parameter:BaseApp/Preferences/View").SetBool("UseNavigationAnimations", False)
    shortcuts = App.ParamGet("User parameter:BaseApp/Preferences/Shortcut")
    shortcuts.SetString("Std_ViewFront", "S")
    shortcuts.SetString("Std_ViewTop", "D")
    shortcuts.SetString("Std_ViewDimetric", "S")
    shortcuts.SetString("Std_ViewTrimetric", "D")
    doc = App.newDocument("QuickAccessA")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    for a, b in (((0, 0), (30, 0)), ((30, 0), (30, 20)), ((30, 20), (0, 20)), ((0, 20), (0, 0))):
        sketch.addGeometry(Part.LineSegment(App.Vector(*a, 0), App.Vector(*b, 0)), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile, pad.Length = sketch, 10
    doc.recompute()
    sketch.Visibility = False
    STATE.update(doc=doc, pad=pad)
    Gui.activateWorkbench("JellyJamsWorkbench")
    STATE["shortcuts"] = shortcuts.GetContents()
    STATE["dispatch"] = ribbon.run_entry
    STATE["calls"] = []
    def dispatch(cmd, index=None):
        STATE["calls"].append((cmd, index))
        STATE["dispatch"](cmd, index)
    ribbon.run_entry = dispatch
    Gui.activeDocument().activeView().viewIsometric()
    Gui.activeDocument().activeView().fitAll()
    later(open_search, 3500)


def open_search():
    from jellyjams import quick_access
    note("one_service_installed", quick_access._service is not None)
    Gui.Selection.addSelection(STATE["doc"].Name, STATE["pad"].Name, "Face1")
    STATE["selection"] = selection()
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    later(search_open)


def search_open():
    p = popup()
    note("s_opens_over_native_shortcut_conflict", p is not None)
    note("part_context", p.title == "Features")
    p.grab().save(os.path.join(OUT, "quick_access_popup.png"))
    note("selection_preserved", selection() == STATE["selection"])
    p.search.setText("pad")
    note("native_name_search", any(p.results.item(i).text() == "Extruded Boss/Base"
                                   for i in range(p.results.count())))
    p.search.setText("style spline")
    note("flyout_variant_search", p.results.count() > 0)
    key(p.search, QtCore.Qt.Key.Key_Escape)
    later(typing)


def typing():
    note("escape_dismisses", popup() is None)
    edit = QtWidgets.QLineEdit(Gui.getMainWindow())
    edit.show()
    key(edit, QtCore.Qt.Key.Key_S, "s")
    key(edit, QtCore.Qt.Key.Key_D, "d")
    note("line_edit_keeps_letters", edit.text() == "sd" and popup() is None, edit.text())
    edit.deleteLater()
    key(view_widget(), QtCore.Qt.Key.Key_D, "D", QtCore.Qt.KeyboardModifier.ShiftModifier)
    note("modified_s_not_intercepted", popup() is None)
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    later(search_dispatch)


def search_dispatch():
    p = popup()
    p.search.setText("top")
    row = next(i for i in range(p.results.count()) if p.results.item(i).text() == "Top")
    p.results.setCurrentRow(row)
    key(p.search, QtCore.Qt.Key.Key_Return)
    later(dispatched)


def dispatched():
    from jellyjams import ribbon
    note("enter_dispatches_native_view_command", ("Std_ViewTop", None) in STATE["calls"])
    note("dispatch_closes_popup", popup() is None)
    ribbon._live_ui().select_tab("Evaluate")
    STATE["other"] = App.newDocument("QuickAccessB")
    later(other_context)


def other_context():
    from jellyjams import ribbon
    note("fresh_part_starts_features", ribbon.current_tab_title() == "Features", ribbon.current_tab_title())
    sketch = STATE["other"].addObject("Sketcher::SketchObject", "Sketch")
    STATE["other"].recompute()
    Gui.activeDocument().setEdit(sketch.Name)
    later(sketch_context)


def sketch_context():
    from jellyjams import quick_access, ribbon
    note("sketch_tab_selected", ribbon.current_tab_title() == "Sketch")
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    p = popup()
    note("s_available_during_sketch", p is not None and p.title == "Sketch")
    note("sketch_exit_in_catalog", any(p.results.item(i).text() == "Exit Sketch"
                                      for i in range(p.results.count())))
    key(p.search, QtCore.Qt.Key.Key_Escape)
    key(view_widget(), QtCore.Qt.Key.Key_D, "d")
    p = popup()
    labels = [b.text() for b in p.findChildren(QtWidgets.QToolButton)]
    note("d_sketch_exit_without_fake_cancel", labels == ["Exit Sketch"], labels)
    p.findChild(QtWidgets.QToolButton).click()
    later(sketch_left)


def sketch_left():
    from jellyjams import ribbon
    note("d_exits_sketch", Gui.activeDocument().getInEdit() is None)
    note("part_tab_restored", ribbon.current_tab_title() == "Features")
    App.setActiveDocument(STATE["doc"].Name)
    later(part_return)


def part_return():
    from jellyjams import quick_access, ribbon
    note("manual_tab_restored_per_document", ribbon.current_tab_title() == "Evaluate", ribbon.current_tab_title())
    Gui.activeDocument().setEdit(STATE["pad"].Name)
    later(feature_task)


def feature_task():
    from jellyjams import quick_access
    token, actions = quick_access.task_state()
    STATE["old_token"] = token
    note("native_ok_cancel_found", [s for s, _ in actions] == ["OK", "Cancel"])
    App.setActiveDocument(STATE["other"].Name)
    note("foreign_document_task_hidden", quick_access.task_state() == (None, []))
    App.setActiveDocument(STATE["doc"].Name)
    corner = quick_access._service.corner
    note("confirmation_corner_visible", corner is not None and corner.isVisible())
    corner.grab().save(os.path.join(OUT, "confirmation_corner.png"))
    ok = next(b for label, b in actions if label == "OK")
    ok.setEnabled(False)
    note("disabled_ok_rejected", not quick_access.confirm(token, "OK"))
    ok.setEnabled(True)
    key(view_widget(), QtCore.Qt.Key.Key_D, "d")
    p = popup()
    note("d_feature_confirmation_open", p is not None)
    next(b for b in p.findChildren(QtWidgets.QToolButton) if b.text() == "Cancel").click()
    later(feature_cancelled)


def feature_cancelled():
    from jellyjams import quick_access
    note("d_cancels_native_task", Gui.activeDocument().getInEdit() is None)
    note("cancel_preserves_length", abs(STATE["pad"].Length.Value - 10) < 1e-9)
    Gui.activeDocument().setEdit(STATE["pad"].Name)
    later(replacement_task)


def replacement_task():
    from jellyjams import quick_access, fcgui
    note("stale_task_token_rejected", not quick_access.confirm(STATE["old_token"], "OK"))
    # Edit the real native quantity control, then accept through the corner.
    controls = fcgui.task_panel().findChildren(QtWidgets.QAbstractSpinBox)
    length = next(w for w in controls if "length" in w.objectName().lower())
    assert length.setProperty("rawValue", 12.0), "native length property not writable"
    assert abs(float(length.property("rawValue")) - 12.0) < 1e-9
    STATE["length_control"] = length.objectName()
    quick_access._service.tick()
    corner = quick_access._service.corner
    next(b for b in corner.findChildren(QtWidgets.QToolButton) if b.text() == "OK").click()
    later(feature_accepted)


def feature_accepted():
    from jellyjams import quick_access, ribbon
    note("corner_accepts_native_task", Gui.activeDocument().getInEdit() is None)
    note("corner_commits_native_value", abs(STATE["pad"].Length.Value - 12) < 1e-9,
         (STATE["pad"].Length.Value, STATE["length_control"]))
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    stale = popup()
    stale.search.setText("top")
    calls = len(STATE["calls"])
    App.setActiveDocument(STATE["other"].Name)
    stale.choose()
    note("stale_search_document_rejected", len(STATE["calls"]) == calls)
    note("shortcut_parameters_unchanged", App.ParamGet(
        "User parameter:BaseApp/Preferences/Shortcut").GetContents() == STATE["shortcuts"])
    ribbon.hide()
    note("hide_removes_service", quick_access._service is None)
    ribbon.show()
    note("show_reinstalls_once", quick_access._service is not None)
    Gui.runCommand("JellyJams_NewAssembly")
    later(assembly_context, 700)


def assembly_context():
    from jellyjams import ribbon
    note("assembly_context_tab", ribbon.current_tab_title() == "Assembly", ribbon.current_tab_title())
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    p = popup()
    note("assembly_shortcut_context", p is not None and p.title == "Assembly")
    key(p.search, QtCore.Qt.Key.Key_Escape)
    doc = App.newDocument("QuickAccessDrawing")
    page = doc.addObject("TechDraw::DrawPage", "Page")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    import glob
    templates = glob.glob(os.path.join(
        App.getResourceDir(), "Mod", "TechDraw", "Templates", "*A4*Landscape*.svg"))
    template.Template = templates[0]
    page.Template = template
    doc.recompute()
    page.ViewObject.show()
    later(drawing_context, 700)


def drawing_context():
    from jellyjams import ribbon
    note("drawing_context_tab", ribbon.current_tab_title() == "Drawing", ribbon.current_tab_title())
    key(view_widget(), QtCore.Qt.Key.Key_S, "s")
    p = popup()
    note("drawing_shortcut_context", p is not None and p.title == "Drawing")
    note("drawing_tools_available", any(p.results.item(i).text() == "Projected View"
                                        for i in range(p.results.count())))
    key(p.search, QtCore.Qt.Key.Key_Escape)
    sketch = App.ActiveDocument.addObject("Sketcher::SketchObject", "Sketch")
    App.ActiveDocument.recompute()
    Gui.activeDocument().setEdit(sketch.Name)
    later(drawing_sketch_entered)


def drawing_sketch_entered():
    from jellyjams import ribbon
    note("drawing_sketch_enters_sketch_tab", ribbon.current_tab_title() == "Sketch")
    Gui.runCommand("Sketcher_LeaveSketch")
    later(drawing_sketch_left)


def drawing_sketch_left():
    from jellyjams import ribbon
    note("drawing_sketch_restores_prior_tab", ribbon.current_tab_title() == "Drawing",
         ribbon.current_tab_title())
    App.setActiveDocument(STATE["doc"].Name)
    later(drawing_return)


def drawing_return():
    from jellyjams import ribbon
    note("drawing_to_part_restores_manual_tab", ribbon.current_tab_title() == "Evaluate", ribbon.current_tab_title())
    Gui.activateWorkbench("PartDesignWorkbench")
    later(left_workbench)


def left_workbench():
    from jellyjams import quick_access
    note("leave_removes_service", quick_access._service is None)
    group = App.ParamGet("User parameter:BaseApp/Preferences/Shortcut")
    note("original_s_shortcut_restored", group.GetString("Std_ViewFront") == "S")
    note("original_d_shortcut_restored", group.GetString("Std_ViewTop") == "D")
    finish()


later(start, 5000)
