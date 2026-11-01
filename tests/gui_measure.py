# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Centre/axis distance and clearance regression with disposable runner configs."""
import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": []}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=250):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, guarded)


def start():
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(create, 3500)


def create():
    import Part
    from jellyjams import ribbon, constants, measure
    doc = App.newDocument("MeasureRegression")
    obj = doc.addObject("PartDesign::Feature", "PCB")
    obj.Shape = Part.makeCompound([
        Part.makeCircle(1, App.Vector(5, 5, 0)),
        Part.makeLine(App.Vector(0, 0, 0), App.Vector(0, 10, 0)),
        Part.makeCircle(1, App.Vector(10, 5, 0))])
    doc.recompute()
    Gui.activeDocument().activeView().viewTop()
    Gui.activeDocument().activeView().fitAll()
    STATE.update(doc=doc, obj=obj, count=len(doc.Objects), measure=measure)
    ribbon._live_ui().select_tab(constants.TAB_EVALUATE)
    ribbon.refresh_now()
    button = ribbon.find_button(constants.MEASURE_COMMAND)
    STATE["button"] = button
    note("measure_button_starts_unchecked", button.isCheckable() and not button.isChecked())
    button.click()
    note("task_open", measure._session is not None)
    note("measure_button_selected_when_active", button.isChecked() and button.isEnabled())
    Gui.Selection.addSelection(obj, "Edge1")
    later(first)


def first():
    m = STATE["measure"]
    note("one_circle_has_radius_callout", m._session.node is not None and "Radius" in m._session.result.text())
    # The sequence emitted by a normal native click (without Ctrl).
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["obj"], "Edge2")
    later(pair)


def pair():
    m = STATE["measure"]
    task = m._session
    distance, _ = m.shortest_distance(task.items)
    note("plain_clicks_accumulate", len(task.items) == 2, task.items)
    note("hole_center_to_edge", abs(distance - 5) < 1e-8, distance)
    note("annotation_visible", task.node is not None)
    note("result_visible", "distance" in task.result.text().lower(), task.result.text())
    task.reference.setCurrentIndex(1)
    clearance, _ = m.shortest_distance(task.items, False)
    note("clearance_mode_keeps_rim_gap", abs(clearance - 4) < 1e-8 and "4.00" in task.result.text(),
         task.result.text())
    task.reference.setCurrentIndex(0)
    note("no_measurement_objects", len(STATE["doc"].Objects) == STATE["count"])
    Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "measure_view.png"), 1000, 700, "Current")
    Gui.getMainWindow().grab().save(os.path.join(OUT, "measure.png"))
    on = STATE["button"].grab().toImage()
    on.save(os.path.join(OUT, "measure_button_on.png"))
    task_before = task
    STATE["button"].click()
    note("measure_button_toggle_off_closes", not m.is_active() and not STATE["button"].isChecked())
    note("measure_button_toggle_off_clears", task_before.node is None and not task_before.callout_rows
         and task_before.callout_bitmap is None and task_before.closed)
    off = STATE["button"].grab().toImage()
    off.save(os.path.join(OUT, "measure_button_off.png"))
    note("measure_button_visible_highlight", on.pixelColor(5, 5) != off.pixelColor(5, 5),
         [on.pixelColor(5, 5).name(), off.pixelColor(5, 5).name()])
    STATE["button"].click()
    note("measure_button_reopens_selected", m.is_active() and STATE["button"].isChecked())
    Gui.Selection.clearSelection()
    later(empty)


def empty():
    task = STATE["measure"]._session
    note("empty_clears_annotation", task.node is None)
    note("empty_clears_result", task.result.text() == "")
    note("empty_clears_picks", not task.items)
    note("empty_selection_keeps_measure_on", STATE["button"].isChecked())
    Gui.Selection.addSelection(STATE["obj"], "Edge1")
    Gui.Selection.addSelection(STATE["obj"], "Edge3")
    later(circles)


def circles():
    task = STATE["measure"]._session
    distance, _ = STATE["measure"].shortest_distance(task.items)
    note("circle_centers", abs(distance - 5) < 1e-8, distance)
    Gui.Selection.removeSelection(STATE["obj"], "Edge3")
    later(removed)


def removed():
    task = STATE["measure"]._session
    note("remove_pick_shows_circle_size", len(task.items) == 1 and "Radius" in task.result.text()
         and "distance" not in task.result.text().lower())
    import Part
    doc, obj = STATE["doc"], STATE["obj"]
    link = doc.addObject("App::Link", "Component")
    link.LinkedObject = obj
    link.Placement.Base = App.Vector(20, 0, 0)
    doc.recompute()
    m = STATE["measure"]
    distance, _ = m.shortest_distance([(link, "Edge1"), (obj, "Edge2")])
    note("linked_component_world_placement", abs(distance - 25) < 1e-8, distance)
    wall = doc.addObject("PartDesign::Feature", "HoleWall")
    wall.Shape = Part.makeCylinder(1, 2, App.Vector(5, 5, 0))
    doc.recompute()
    distance, _ = m.shortest_distance([(wall, "Face1"), (obj, "Edge2")])
    note("cylindrical_axis_to_edge", abs(distance - 5) < 1e-8, distance)
    doc.removeObject(link.Name)
    doc.removeObject(wall.Name)
    Gui.Selection.addSelection(obj, "Edge2")
    later(close_task)


def close_task():
    task = STATE["measure"]._session
    Gui.Control.closeDialog()
    later(lambda: closed(task))


def closed(task):
    m = STATE["measure"]
    note("external_close_disposes_task", m._session is None and task.closed and task.node is None)
    note("external_close_unchecks_button", not STATE["button"].isChecked())
    m.start()
    note("reopen_after_close", m._session is not None)
    Gui.Selection.clearSelection()
    later(click_hole)


def click_point(point):
    view = Gui.activeDocument().activeView()
    gl = max((w for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget)
              if w.inherits("QOpenGLWidget") and w.isVisible()),
             key=lambda w: w.width() * w.height())
    x, y = view.getPointOnScreen(App.Vector(*point))[:2]
    ratio = gl.devicePixelRatioF()
    RES.setdefault("clicks", []).append({"point": point, "screen": [x, y],
        "size": [gl.width(), gl.height()], "ratio": ratio,
        "pick": str(view.getObjectInfo((int(x), int(y))))})
    pos = QtCore.QPoint(round(x / ratio), gl.height() - 1 - round(y / ratio))
    QtTest.QTest.mouseMove(gl, pos)
    QtTest.QTest.mouseClick(gl, QtCore.Qt.MouseButton.LeftButton,
                          QtCore.Qt.KeyboardModifier.NoModifier, pos)


def click_hole():
    # Avoid the seam vertex at x=6: pick the circular edge itself.
    click_point((4, 5, 0))
    later(click_edge)


def click_edge():
    click_point((0, 5, 0))
    later(clicked_pair)


def clicked_pair():
    task = STATE["measure"]._session
    note("native_plain_mouse_clicks_accumulate", len(task.items) == 2, task.items)
    note("native_clicks_show_distance", task.node is not None, task.result.text())
    distance, _ = STATE["measure"].shortest_distance(task.items)
    note("native_clicks_measure_hole_center", abs(distance - 5) < 1e-8, distance)
    click_point((-4, 5, 0))
    later(clicked_empty)


def clicked_empty():
    task = STATE["measure"]._session
    note("native_empty_click_clears", not task.items and task.node is None and task.result.text() == "")
    later(check_geometry_types)


def check_geometry_types():
    import math
    import Part
    m = STATE["measure"]
    doc = STATE["doc"]
    obj = doc.addObject("PartDesign::Feature", "MeasurementTypes")
    rows_to_test = [
        ("line", Part.makeLine(App.Vector(0, 0, 0), App.Vector(17.05, 0, 0)), ("Length",)),
        ("arc", Part.makeCircle(1.25, App.Vector(0, 0, 0), App.Vector(0, 0, 1), 0, 90),
         ("Radius", "Center", "Arc length", "Chord length", "Angle")),
        ("face", Part.makePlane(10, 5), ("Area", "Perimeter")),
        ("circle", Part.makeCircle(2), ("Radius", "Diameter", "Center", "Circumference")),
        ("vertex", Part.Vertex(App.Vector(1, 2, 3)), ("X", "Y", "Z")),
        ("solid", Part.makeBox(2, 3, 4), ("Area", "Volume")),
        ("cylinder", Part.makeCylinder(1.25, 3).Faces[0], ("Area", "Perimeter", "Radius", "Diameter")),
        ("sphere", Part.makeSphere(2).Faces[0], ("Area", "Radius", "Diameter", "Center")),
    ]
    task = m._session
    for name, shape, expected in rows_to_test:
        obj.Shape = shape
        rows, points = m.measurement([(obj, "")])
        note(name + "_labels", all(label in dict(rows) for label in expected), rows)
        if name == "line":
            note("line_length_value", "17.05" in dict(rows)["Length"], rows)
        if name == "arc":
            note("arc_radius_value", "1.25" in dict(rows)["Radius"], rows)
            note("arc_angle_value", "90" in dict(rows)["Angle"], rows)
        if name == "face":
            note("face_area_perimeter_values", "50" in dict(rows)["Area"] and "30" in dict(rows)["Perimeter"], rows)
        if name == "cylinder":
            perimeter = App.Units.Quantity(dict(rows)["Perimeter"]).Value
            note("cylinder_perimeter_excludes_seam", abs(perimeter - 4 * math.pi * 1.25) < 0.01, perimeter)
        if name == "sphere":
            note("closed_sphere_has_no_fake_perimeter", "Perimeter" not in dict(rows), rows)
        task.remove_annotation()
        task.draw(points, rows)
        bitmap = task.callout_bitmap
        note(name + "_white_black_card", bitmap.pixelColor(2, 2).name() == "#ffffff"
             and bitmap.pixelColor(0, 0).name() == "#000000", [bitmap.width(), bitmap.height()])
        bitmap.save(os.path.join(OUT, "measure_" + name + "_card.png"))
    horizontal = Part.makeLine(App.Vector(0, 0, 0), App.Vector(5, 0, 0))
    vertical = Part.makeLine(App.Vector(0, 0, 0), App.Vector(0, 5, 0))
    obj.Shape = Part.makeCompound([horizontal, vertical, horizontal.translated(App.Vector(0, 0, 2))])
    rows, _ = m.measurement([(obj, "Edge1"), (obj, "Edge2")], show_xyz=True)
    note("pair_angle_and_xyz_labels", all(label in dict(rows) for label in ("Distance", "Angle", "dX", "dY", "dZ", "Total length")), rows)
    note("perpendicular_lines_angle", "90" in dict(rows)["Angle"], rows)
    rows, _ = m.measurement([(obj, "Edge1"), (obj, "Edge2"), (obj, "Edge3")])
    note("multiple_edges_total", "15" in dict(rows)["Total length"], rows)
    obj.Shape = Part.makeCompound([Part.makePlane(10, 5), Part.makePlane(10, 5, App.Vector(0, 0, 3))])
    rows, _ = m.measurement([(obj, "Face1"), (obj, "Face2")])
    note("faces_total_area", abs(App.Units.Quantity(dict(rows)["Total area"]).Value - 100) < 1e-8, rows)
    obj.Shape = Part.makeCompound([Part.Vertex(App.Vector(1, 0, 0)), Part.Vertex(App.Vector(0, 0, 0)),
                                   Part.Vertex(App.Vector(0, 1, 0))])
    rows, _ = m.measurement([(obj, "Vertex1"), (obj, "Vertex2"), (obj, "Vertex3")])
    note("three_point_angle", "90" in dict(rows)["Angle"], rows)
    obj.Shape = Part.makeCompound([Part.makeSphere(1).Faces[0], Part.makeSphere(1, App.Vector(5, 0, 0)).Faces[0]])
    rows, _ = m.measurement([(obj, "Face1"), (obj, "Face2")])
    note("spherical_center_distance", "5.00" in dict(rows)["Center distance"], rows)
    task.remove_annotation()
    obj.Shape = Part.makeCompound([Part.Vertex(App.Vector(1, 0, 0)), Part.Vertex(App.Vector(0, 0, 0)),
                                   Part.Vertex(App.Vector(0, 1, 0))])
    STATE["types_obj"] = obj
    Gui.Selection.addSelection(obj, "Vertex1")
    later(second_point_pick)


def second_point_pick():
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["types_obj"], "Vertex2")
    later(third_point_pick)


def third_point_pick():
    Gui.Selection.addSelection(STATE["types_obj"], "Vertex3")
    later(ordered_angle)


def ordered_angle():
    task = STATE["measure"]._session
    note("mixed_plain_additive_angle_keeps_second_vertex", "90" in dict(task.callout_rows).get("Angle", ""), task.callout_rows)
    Gui.Selection.clearSelection()
    STATE["doc"].removeObject(STATE.pop("types_obj").Name)
    later(check_user_step)


def check_user_step():
    # Optional supplied model: do not commit or require a user's Downloads file.
    path = os.environ.get("JELLYJAMS_MEASURE_STEP")
    if path:
        import Part
        shape = Part.Shape()
        shape.read(path)
        pcb = STATE["doc"].addObject("PartDesign::Feature", "SuppliedPCB")
        pcb.Shape = shape.Solids[202]
        STATE["obj"].ViewObject.hide()
        STATE["doc"].recompute()
        STATE["supplied"] = pcb
        RES["step"] = {"file": path, "solid": 202}
        Gui.activeDocument().activeView().fitAll()
        Gui.Selection.addSelection(pcb, "Edge1066")
        Gui.Selection.addSelection(pcb, "Edge1015")
        later(check_step_pair)
        return
    later(check_front_view_change)


def check_step_pair():
    m = STATE["measure"]
    task = m._session
    pcb = STATE["supplied"]
    distance, points = m.shortest_distance(task.items)
    note("supplied_step_center_distance", abs(distance - 1.5) < 1e-8, distance)
    note("supplied_step_result", task.node is not None and "1.50" in task.result.text(), task.result.text())
    center = pcb.Shape.Edges[1065].Curve.Center
    note("supplied_step_annotation_starts_at_center", (points[0] - center).Length < 1e-8, points)
    task.reference.setCurrentIndex(1)
    clearance, _ = m.shortest_distance(task.items, False)
    note("supplied_step_clearance", abs(clearance - 0.925) < 1e-8, clearance)
    task.reference.setCurrentIndex(0)
    Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "supplied_pcb_measure.png"), 1400, 1000, "Current")
    Gui.Selection.clearSelection()
    later(select_step_wall)


def select_step_wall():
    pcb = STATE["supplied"]
    Gui.Selection.addSelection(pcb, "Face1799")
    Gui.Selection.addSelection(pcb, "Edge1015")
    later(check_step_wall)


def check_step_wall():
    from pivy import coin
    m = STATE["measure"]
    task = m._session
    distance, points = m.shortest_distance(task.items)
    note("supplied_inner_face_center_distance", abs(distance - 1.5) < 1e-8, distance)
    note("supplied_inner_face_visible_result", "1.50" in task.result.text(), task.result.text())
    note("supplied_inner_face_annotation_distance", abs((points[0] - points[1]).Length - 1.5) < 1e-8, points)
    note("annotation_drawn_above_pcb", task.node.isOfType(coin.SoAnnotation.getClassTypeId()))
    search = coin.SoSearchAction()
    search.setType(coin.SoImage.getClassTypeId())
    search.apply(task.node)
    card = search.getPath().getTail()
    note("annotation_white_card", card is not None and task.callout_bitmap.pixelColor(2, 2).name() == "#ffffff")
    task.callout_bitmap.save(os.path.join(OUT, "supplied_pcb_distance_card.png"))
    note("task_result_bold", task.result.font().bold())
    note("inner_face_full_annotation_text", dict(task.callout_rows).get("Center distance") == "1.50 mm", task.callout_rows)
    view = Gui.activeDocument().activeView()
    # View the wall and top surface obliquely, as in the user's screenshot.
    view.viewAxonometric()
    view.fitAll()
    later(capture_step_wall)


def capture_step_wall():
    Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "supplied_pcb_wall_measure.png"), 1600, 1100, "Current")
    Gui.Selection.clearSelection()
    later(cleanup_step)


def cleanup_step():
    pcb = STATE.pop("supplied")
    STATE["doc"].removeObject(pcb.Name)
    later(check_front_view_change)


def check_front_view_change():
    STATE["front_task"] = STATE["measure"]._session
    Gui.runCommand("Start_Start")
    from jellyjams import fcgui
    area = fcgui.mdi_area()
    for sub in area.subWindowList():
        if sub.widget().inherits("StartGui::StartView"):
            area.setActiveSubWindow(sub)
            break
    later(front_view_changed, 400)


def activate_model_view():
    from jellyjams import fcgui
    App.setActiveDocument(STATE["doc"].Name)
    area = fcgui.mdi_area()
    for sub in area.subWindowList():
        if sub.widget().inherits("Gui::View3DInventor"):
            area.setActiveSubWindow(sub)
            break


def front_view_changed():
    task = STATE.pop("front_task")
    note("start_page_stops_measure", not STATE["measure"].is_active() and task.closed)
    note("start_page_clears_callouts", task.node is None and not STATE["button"].isChecked())
    STATE["measure"].start()
    note("start_page_refuses_measure_activation", not STATE["measure"].is_active())
    activate_model_view()
    later(start_document_switch)


def start_document_switch():
    STATE["measure"].start()
    STATE["document_task"] = STATE["measure"]._session
    STATE["other_doc"] = App.newDocument("MeasureAuditOther")
    later(document_changed, 400)


def document_changed():
    task = STATE.pop("document_task")
    note("document_switch_stops_measure", not STATE["measure"].is_active() and task.closed)
    note("document_switch_clears_callouts", task.node is None and not STATE["button"].isChecked())
    obj = STATE["other_doc"].addObject("PartDesign::Feature", "OtherPCB")
    obj.Shape = STATE["obj"].Shape
    STATE["other_doc"].recompute()
    Gui.Selection.addSelection(obj, "Edge1")
    STATE["measure"].start()
    STATE["closed_document_task"] = STATE["measure"]._session
    later(close_other_document)


def close_other_document():
    note("document_close_has_visible_callout", STATE["closed_document_task"].node is not None)
    App.closeDocument(STATE.pop("other_doc").Name)
    later(document_closed, 400)


def document_closed():
    task = STATE.pop("closed_document_task")
    note("document_close_stops_measure", not STATE["measure"].is_active() and task.closed)
    note("document_close_clears_callouts", task.node is None and not task.callout_rows
         and task.callout_bitmap is None)
    activate_model_view()
    later(reopen_before_leave)


def reopen_before_leave():
    STATE["measure"].start()
    note("reopen_after_document_close", STATE["measure"].is_active())
    later(leave)


def leave():
    task = STATE["measure"]._session
    Gui.activateWorkbench("PartDesignWorkbench")
    later(lambda: after_leave(task), 900)


def after_leave(task):
    from jellyjams import fcgui
    note("leave_closes_task", STATE["measure"]._session is None)
    note("leave_removes_annotation", task.node is None)
    note("leave_stops_timer", not fcgui.is_alive(task.timer) or not task.timer.isActive())
    note("leave_unchecks_measure_button", not STATE["button"].isChecked())
    note("leave_no_saved_measurements", len(STATE["doc"].Objects) == STATE["count"])
    finish()


def finish():
    from jellyjams import measure
    measure.stop()
    with open(os.path.join(OUT, "measure.json"), "w", encoding="utf-8") as handle:
        json.dump(RES, handle, indent=2)
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    Gui.getMainWindow().close()


later(start, 1000)
