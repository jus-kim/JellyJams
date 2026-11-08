# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Native drawing dialogs and document task ownership on supported FreeCAD hosts.

Run only through run_gui.py with disposable configurations.
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "info": {"version": App.Version()}}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=1200):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, guarded)


def form(name):
    from jellyjams import fcgui
    panel = fcgui.task_panel()
    found = panel.findChild(QtWidgets.QWidget, name) if panel else None
    if found is None and panel is not None:
        found = panel.findChild(QtWidgets.QWidget, name.replace("::", "__"))
    if found is None:
        RES["info"][name] = {
            "panel": panel.metaObject().className() if panel else None,
            "widgets": [(w.objectName(), w.metaObject().className()) for w in
                        Gui.getMainWindow().findChildren(QtWidgets.QWidget)
                        if "Task" in w.objectName() or "Balloon" in w.objectName()
                        or "RichAnno" in w.objectName()],
        }
    return found


def label_text(widget, names):
    if widget is None:
        return None
    for name in names:
        label = widget.findChild(QtWidgets.QLabel, name)
        if label is not None:
            return label.text()
    return None


def close_task():
    Gui.activeDocument().resetEdit()
    Gui.Control.closeDialog()


def start():
    from jellyjams import make_drawing, templates
    Gui.activateWorkbench("JellyJamsWorkbench")
    doc = App.newDocument("HostCompatibility")
    try:
        Gui.Control.activeDialog(Gui.activeDocument())
        RES["info"]["document_task_api"] = True
    except TypeError:
        RES["info"]["document_task_api"] = False
    box = doc.addObject("Part::Box", "Box")
    page = make_drawing._add_sheet(doc, templates.new_drawing_template(templates.FORMAT_A4_PORTRAIT))
    view = doc.addObject("TechDraw::DrawViewPart", "View")
    view.Source = [box]
    page.addView(view)
    balloon = doc.addObject("TechDraw::DrawViewBalloon", "Balloon")
    balloon.SourceView = view
    balloon.Text = "1"
    page.addView(balloon)
    doc.recompute()
    STATE.update(doc=doc, page=page, view=view, balloon=balloon)
    make_drawing._show(doc, page)
    later(balloon_start, 2500)


def balloon_start():
    Gui.activeDocument().setEdit(STATE["balloon"].Name)
    later(balloon_check)


def balloon_check():
    widget = form("TechDrawGui::TaskBalloon")
    note("native_balloon_form", widget is not None)
    for role, names, expected in (
        ("text", ("lText", "label"), "Balloon text"),
        ("style", ("lBShape", "label_3"), "Style"),
        ("arrow", ("lSymbol", "label_4"), "Arrow style"),
        ("width", ("lWidth", "label_8"), "Leader thickness"),
        ("kink", ("lKink", "label_6"), "Bent leader length"),
    ):
        text = label_text(widget, names) if widget is not None else None
        note("balloon_" + role, text == expected, text)
    leader = widget.findChild(QtWidgets.QGroupBox, "gbLeader") if widget is not None else None
    text = leader.title() if leader is not None else label_text(widget, ("label_9",))
    note("balloon_leader", text == "Leader", text)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "native_balloon.png"))
    close_task()
    later(annotation_start, 500)


def annotation_start():
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["page"])
    Gui.runCommand("TechDraw_RichTextAnnotation")
    later(annotation_check)


def annotation_check():
    widget = form("TechDrawGui::TaskRichAnno")
    note("native_annotation_form", widget is not None)
    for role, names, expected in (
        ("color", ("label_colorThickness", "label_4"), "Line color"),
        ("width", ("label_frameThickness", "label_5"), "Line thickness"),
        ("style", ("label_patternThickness", "label_6"), "Line style"),
    ):
        text = label_text(widget, names) if widget is not None else None
        note("annotation_" + role, text == expected, text)
    border = widget.findChild(QtWidgets.QGroupBox, "gbFrame") if widget is not None else None
    text = border.title() if border is not None else label_text(widget, ("label_3",))
    note("annotation_border", text == "Border", text)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "native_annotation.png"))
    close_task()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["view"], "Edge1")
    Gui.runCommand("JellyJams_LineFormat")
    later(line_check)


def line_check():
    from jellyjams import constants, dialog_terms
    widget = form("TechDrawGui::TaskLineDecor")
    note("native_line_format_form", widget is not None)
    control = widget.findChild(QtWidgets.QWidget, "cb_Visible") if widget is not None else None
    if isinstance(control, QtWidgets.QCheckBox):
        visible_ok = control.text() == "Show Edges"
    elif isinstance(control, QtWidgets.QComboBox):
        visible_ok = [control.itemText(i) for i in range(control.count())] == ["Hide", "Show"]
    else:
        visible_ok = False
    note("line_visibility_control", visible_ok)
    presets = widget.findChild(QtWidgets.QComboBox, dialog_terms.OBJ_WEIGHT_COMBO) if widget else None
    note("native_iso_presets_present", presets is not None)
    if presets is not None:
        presets.setCurrentIndex(4)
        presets.activated.emit(4)
    field = widget.findChild(QtWidgets.QWidget, "dsb_Weight") if widget else None
    value = field.property("rawValue") if field else None
    note("native_iso_preset_updates_weight", value is not None and abs(float(value) - 0.35) < 1e-9, value)
    note("one_iso_presets_row", widget is not None and len(widget.findChildren(
        QtWidgets.QWidget, constants.OBJ_LINE_WIDTH_PRESETS)) == 1)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "native_line_format.png"))
    close_task()
    later(measure_start)


def measure_start():
    from jellyjams import measure
    # Use a separate 3D document because Measure intentionally excludes drawings.
    doc = App.newDocument("MeasureOwner")
    doc.addObject("Part::Box", "Box")
    doc.recompute()
    STATE["measure_doc"] = doc
    Gui.Selection.clearSelection()
    measure.start()
    later(measure_switch)


def measure_switch():
    import Part
    from jellyjams import measure
    note("measure_opens_on_owner", measure.is_active())
    doc = App.newDocument("SecondTaskOwner")
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    sketch.addGeometry(Part.LineSegment(App.Vector(), App.Vector(10, 4, 0)), False)
    doc.recompute()
    STATE["second_doc"] = doc
    if RES["info"]["document_task_api"]:
        # Open the new task before Measure's timer runs: cleanup must target
        # the previous document even when a different task is now active.
        second_task_open()
    else:
        # 1.1 has one global dialog. Let Measure's document-change timer close
        # it before the next edit, avoiding the native task-close modal prompt.
        later(second_task_open)


def second_task_open():
    Gui.activeDocument().setEdit(STATE["second_doc"].getObject("Sketch").Name)
    later(measure_check)


def measure_check():
    from jellyjams import fcgui, measure, relations_panel
    measure.stop()
    note("measure_stops_after_switch", not measure.is_active())
    note("other_document_sketch_edit_survives", Gui.activeDocument().getInEdit() is not None)
    note("active_task_panel_found", fcgui.task_panel() is not None)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["second_doc"].getObject("Sketch"), "Edge1")
    relations_panel.refresh_now()
    later(relations_check)


def relations_check():
    from jellyjams import fcgui, relations_panel
    panel = fcgui.task_panel()
    frame = relations_panel._host.frame()
    note("relations_in_current_document", panel is not None and frame is not None
         and panel.isAncestorOf(frame))
    Gui.activeDocument().resetEdit()
    App.setActiveDocument(STATE["measure_doc"].Name)
    later(owner_check)


def owner_check():
    note("no_stale_measure_dialog_on_owner", not Gui.Control.activeDialog())
    finish()


def finish():
    try:
        from jellyjams import measure
        measure.stop()
        if Gui.activeDocument():
            close_task()
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        RES["errors"].append("cleanup: " + traceback.format_exc())
    RES["ok"] = bool(RES["checks"]) and not RES["errors"] and all(c["ok"] for c in RES["checks"].values())
    with open(os.path.join(OUT, "host_compatibility.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(1000, QtWidgets.QApplication.instance().quit)


later(start, 2500)
