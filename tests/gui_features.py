# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Real FreeCAD feature integration checks; run via tests/run_gui.py --suites features.

Exercises real commands and objects. File/format pickers are replaced with deterministic
scratch destinations; pointer placement and native file dialogs are outside this test.
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


def step(fn):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            finish()
    return guarded


def later(fn, ms=1000):
    QtCore.QTimer.singleShot(ms, step(fn))


def close_task(accept):
    wanted = (QtWidgets.QDialogButtonBox.StandardButton.Ok if accept
              else QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    for dock in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget):
        if dock.objectName() not in ("Tasks", "Combo View", "ComboView"):
            continue
        for box in dock.findChildren(QtWidgets.QDialogButtonBox):
            button = box.button(wanted)
            if button is not None and button.isVisible():
                button.click()
                return True
    return False


def finish():
    try:
        from jellyjams import sketch_tools, sheet_pick, assembly_commands
        sketch_tools.stop_running()
        sheet_pick.cancel()
        assembly_commands.stop_rotate_component()
        if Gui.ActiveDocument and Gui.ActiveDocument.getInEdit():
            Gui.ActiveDocument.resetEdit()
        Gui.Control.closeDialog()
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        RES["errors"].append("cleanup: " + traceback.format_exc())
    RES["ok"] = bool(RES["checks"]) and not RES["errors"] and all(
        check["ok"] for check in RES["checks"].values())
    with open(os.path.join(OUT, "features.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(1000, QtWidgets.QApplication.instance().quit)


def start():
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(sketch_start, 4000)


def sketch_start():
    import Part
    from jellyjams import constants, ribbon, relations_rules, mate_rules, theme

    palette = theme.widget_colors()
    note("all_custom_commands_registered", set(constants.ALL_COMMANDS) <= set(Gui.listCommands()))
    RES["info"]["dock_titles"] = [{
        "dock": dock.objectName(),
        "title_widget": dock.titleBarWidget().metaObject().className() if dock.titleBarWidget() else None,
        "labels": [(label.objectName(), label.text()) for label in
                   (dock.titleBarWidget().findChildren(QtWidgets.QLabel) if dock.titleBarWidget() else [])],
    } for dock in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget)]
    title_widgets = [dock.titleBarWidget() for dock in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget)
                     if dock.titleBarWidget() and
                     dock.titleBarWidget().metaObject().className() == "Gui::OverlayTitleBar"]
    title_colors = [widget.palette().color(widget.foregroundRole()).name() for widget in title_widgets]
    note("dock_titles_use_readable_color", bool(title_colors) and all(
        color == palette.TEXT_SECONDARY for color in title_colors), title_colors)
    note("no_ribbon_commands_missing", not ribbon.skipped_ids(), ribbon.skipped_ids())
    panel_ids = set(relations_rules.RELATION_COMMANDS.values()) | set(mate_rules.MATE_COMMANDS.values())
    note("all_panel_commands_registered", panel_ids <= set(Gui.listCommands()),
         sorted(panel_ids - set(Gui.listCommands())))
    doc = App.newDocument("FeatureSketch")
    STATE["model"] = doc
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(30, 5, 0)), False)
    doc.recompute()
    STATE["sketch"] = sketch
    Gui.activeDocument().setEdit(sketch.Name)
    later(relation_select)


def relation_select():
    from jellyjams import relations_panel, ribbon
    sketch = STATE["sketch"]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch, "Edge1")
    relations_panel.refresh_now()
    frame = relations_panel._host.frame()
    note("relations_panel_visible", frame is not None and relations_panel._host.is_shown())
    buttons = frame.findChildren(QtWidgets.QToolButton) if frame else []
    horizontal = next((button for button in buttons if button.text() == "Horizontal"), None)
    note("horizontal_relation_offered", horizontal is not None)
    ribbon.refresh_now()
    note("sketch_context_tab", ribbon.current_tab_title() == "Sketch", ribbon.current_tab_title())
    if horizontal:
        horizontal.click()
    later(relation_verify)


def relation_verify():
    import Part
    from jellyjams import relations_panel, sketch_tools
    sketch = STATE["sketch"]
    note("relation_click_adds_constraint", any(c.Type == "Horizontal" for c in sketch.Constraints))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch, "Edge1")
    relations_panel.refresh_now()
    frame = relations_panel._host.frame()
    note("existing_relation_listed", frame is not None and frame.relations.count() == 1)
    if frame and frame.relations.count():
        frame.relations.item(0).setSelected(True)
        frame.delete_button.click()
    note("delete_relation_button", sketch.ConstraintCount == 0, sketch.ConstraintCount)
    # Drive the processing modes against actual Sketcher geometry and solver APIs.
    centerline = sketch_tools._CenterlineMode(sketch)
    index = sketch.addGeometry(Part.LineSegment(App.Vector(0, 10, 0), App.Vector(20, 10, 0)), False)
    centerline.process()
    note("centerline_new_geometry_only", sketch.getConstruction(index) and not sketch.getConstruction(0))
    midpoint = sketch_tools._MidpointMode(sketch)
    index = sketch.addGeometry(Part.LineSegment(App.Vector(10, 20, 0), App.Vector(15, 20, 0)), False)
    midpoint.process()
    note("midpoint_adds_mirrored_half", sketch.GeometryCount == 4, sketch.GeometryCount)
    end1, end2, middle = sketch.getPoint(index, 2), sketch.getPoint(index + 1, 2), sketch.getPoint(index, 1)
    note("midpoint_solver_symmetry", ((end1 + end2) * 0.5 - middle).Length < 1e-6)
    Gui.ActiveDocument.resetEdit()
    later(drawing_start)


def drawing_start():
    from jellyjams import make_drawing, templates
    doc = App.newDocument("AuditPart")
    box = doc.addObject("Part::Box", "Box")
    box.Length, box.Width, box.Height = 30, 20, 10
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "AuditPart.FCStd"))
    STATE["part"] = doc
    original_format, original_path = make_drawing._ask_format, make_drawing._ask_drawing_path
    try:
        make_drawing._ask_format = lambda *_args: templates.FORMAT_A4_PORTRAIT
        make_drawing._ask_drawing_path = lambda *_args: os.path.join(OUT, "AuditDrawing.FCStd")
        Gui.runCommand("JellyJams_MakeDrawing")
    finally:
        make_drawing._ask_format, make_drawing._ask_drawing_path = original_format, original_path
    later(drawing_verify, 2500)


def drawing_verify():
    from jellyjams import doc_utils, projected_view, view_scale, sheet_text, ribbon, fcgui
    doc = App.ActiveDocument
    STATE["drawing"] = doc
    pages = doc_utils.pages(doc)
    note("make_drawing_command", doc.Name != "AuditPart" and len(pages) == 1)
    page = pages[0]
    STATE["page"] = page
    group = next(obj for obj in doc.Objects if obj.TypeId == "TechDraw::DrawProjGroup")
    STATE["group"] = group
    note("three_linked_projections", len(group.Views) == 3 and len(group.XSource) == 1)
    note("title_block_prefilled", bool(page.Template.EditableTexts.get("drawing_number")))
    note("projection_drag_released", not group.AutoDistribute)
    ribbon.refresh_now()
    area = fcgui.mdi_area()
    RES["info"]["drawing_windows"] = {
        "active": fcgui.active_mdi_widget().metaObject().className() if fcgui.active_mdi_widget() else None,
        "windows": [(w.windowTitle(), w.widget().metaObject().className()) for w in area.subWindowList()],
        "report": Gui.getMainWindow().findChild(QtWidgets.QTextEdit).toPlainText()[-2000:]
                  if Gui.getMainWindow().findChild(QtWidgets.QTextEdit) else "",
    }
    note("drawing_context_tab", ribbon.current_tab_title() == "Drawing", ribbon.current_tab_title())
    item = projected_view.create_projection(group, group.Anchor, float(group.X) - 50, float(group.Y))
    note("projected_view_creates_left", item is not None and item.Type == "Left")
    note("scale_applied", view_scale.apply_scale(group, "Custom", 0.5) and abs(group.Scale - 0.5) < 1e-8)
    sheet_text._create_text(page, 40, 50, "Audit note\\nSecond line", 3.5)
    notes = [obj for obj in page.Views if obj.TypeId == "TechDraw::DrawViewAnnotation"]
    note("sheet_text_created", len(notes) == 1 and list(notes[0].Text) == ["Audit note", "Second line"])
    from jellyjams import sheet_properties, templates
    sheet_properties.apply_sheet_properties(page, page.Template.Template, templates.FIRST_ANGLE,
                                           dict(page.Template.EditableTexts))
    note("sheet_projection_changes_group", page.ProjectionType == templates.FIRST_ANGLE
         and group.ProjectionType == templates.FIRST_ANGLE)
    sheet_properties.apply_sheet_properties(page, page.Template.Template, templates.THIRD_ANGLE,
                                           dict(page.Template.EditableTexts))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(page)
    Gui.runCommand("JellyJams_SheetProperties")
    later(sheet_properties_verify)


def sheet_properties_verify():
    note("sheet_properties_command_opens_panel", bool(Gui.Control.activeDialog()))
    note("sheet_properties_cancel", close_task(False))
    later(surface_start)


def surface_start():
    page = STATE["page"]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(page)
    Gui.runCommand("JellyJams_SurfaceFinish")
    later(surface_verify)


def surface_verify():
    from jellyjams import constants, surface_finish
    doc, page = STATE["drawing"], STATE["page"]
    symbols = [obj for obj in page.Views if getattr(obj, constants.PROP_SYMBOL_TYPE, "") == constants.KIND_SURFACE]
    note("surface_finish_command_opens_panel", len(symbols) == 1 and bool(Gui.Control.activeDialog()))
    note("surface_finish_cancel", close_task(False))
    note("surface_finish_cancel_removes_object", not any(
        getattr(obj, constants.PROP_SYMBOL_TYPE, "") == constants.KIND_SURFACE for obj in page.Views))
    later(surface_accept)


def surface_accept():
    from jellyjams import constants
    page = STATE["page"]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(page)
    Gui.runCommand("JellyJams_SurfaceFinish")
    later(surface_keep)


def surface_keep():
    from jellyjams import constants
    page = STATE["page"]
    note("surface_finish_accept", close_task(True))
    symbols = [obj for obj in page.Views if getattr(obj, constants.PROP_SYMBOL_TYPE, "") == constants.KIND_SURFACE]
    note("surface_finish_persisted", len(symbols) == 1 and "Rz 16" in symbols[0].Symbol)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(page)
    Gui.runCommand("JellyJams_WeldSymbol")
    later(weld_verify)


def weld_verify():
    from jellyjams import constants, insert_picture
    doc, page = STATE["drawing"], STATE["page"]
    note("weld_symbol_command_opens_panel", bool(Gui.Control.activeDialog()))
    note("weld_symbol_accept", close_task(True))
    note("weld_symbol_created", any(getattr(obj, constants.PROP_SYMBOL_TYPE, "") == constants.KIND_WELD
                                    for obj in page.Views))
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
    picture_path = os.path.join(OUT, "picture.svg")
    with open(picture_path, "w", encoding="utf-8") as stream:
        stream.write(svg)
    original = insert_picture._ask_file
    try:
        insert_picture._ask_file = lambda *_args: picture_path
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(page)
        Gui.runCommand("JellyJams_InsertPicture")
    finally:
        insert_picture._ask_file = original
    later(picture_verify)


def picture_verify():
    from jellyjams import drawing_export
    doc, page = STATE["drawing"], STATE["page"]
    note("insert_picture_command_opens_panel", bool(Gui.Control.activeDialog()))
    note("insert_picture_accept", close_task(True))
    pictures = [obj for obj in page.Views if obj.Name.startswith("Picture")]
    note("svg_picture_created", len(pictures) == 1 and bool(pictures[0].Symbol))
    drawing_export.prepare(doc, [page])
    drawing_export.write_pdf([page], os.path.join(OUT, "single.pdf"))
    drawing_export.write_dxf([page], os.path.join(OUT, "single.dxf"))
    note("single_pdf_export", os.path.getsize(os.path.join(OUT, "single.pdf")) > 500)
    note("single_dxf_export", os.path.getsize(os.path.join(OUT, "single.dxf")) > 100)
    from jellyjams import make_drawing
    page2 = make_drawing._add_sheet(doc, page.Template.Template)
    STATE["page2"] = page2
    drawing_export.prepare(doc, [page, page2])
    drawing_export.write_pdf([page, page2], os.path.join(OUT, "multi.pdf"))
    note("multi_sheet_pdf_export", os.path.isfile(os.path.join(OUT, "multi.pdf")))
    Gui.runCommand("JellyJams_NewAssembly")
    later(assembly_verify, 2000)


def assembly_verify():
    from jellyjams import constants, assembly_commands, mate_panel
    doc = App.ActiveDocument
    assemblies = [obj for obj in doc.Objects if obj.TypeId == constants.TYPE_ASSEMBLY]
    note("new_assembly_command", len(assemblies) == 1 and doc.Name.startswith("Assembly"))
    assembly = assemblies[0]
    STATE["assembly"] = assembly
    doc.saveAs(os.path.join(OUT, "AuditAssembly.FCStd"))
    source = STATE["part"].getObject("Box")
    links = []
    for index in range(2):
        link = doc.addObject("App::Link", "Component")
        link.setLink(source)
        assembly.addObject(link)
        links.append(link)
    doc.recompute()
    STATE["links"] = links
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(links[0])
    note("floating_component_rotate_target", assembly_commands.rotate_target()[2] is None,
         assembly_commands.rotate_target()[2])
    Gui.runCommand("JellyJams_RotateComponent")
    note("rotate_component_starts", assembly_commands.is_rotating())
    assembly_commands.stop_rotate_component()
    note("rotate_component_stops", not assembly_commands.is_rotating())
    # A failed native placement write must not leave an application undo step open.
    class UnwritableComponent:
        Document = doc

        @property
        def Placement(self):
            return App.Placement()

        @Placement.setter
        def Placement(self, value):
            raise RuntimeError("injected placement failure")

    probe = assembly_commands._RotateTool(None, Gui.ActiveDocument.ActiveView, assembly, links[0])
    probe.component = lambda: UnwritableComponent()
    before = App.getActiveTransaction()
    failed = False
    try:
        probe.rotate((0, 1, 0), 12)
    except RuntimeError as error:
        failed = str(error) == "injected placement failure"
    finally:
        pending = App.getActiveTransaction()
        probe.finish_drag()
    after = App.getActiveTransaction()
    note("failed_rotation_releases_undo_transaction",
         failed and before is None and bool(pending) and after is None,
         {"before": before, "pending": pending, "after": after, "injected_failure": failed})
    Gui.Selection.clearSelection()
    for link in links:
        Gui.Selection.addSelection(assembly, link.Name + ".Face1")
    mate_panel.refresh_now()
    frame = mate_panel._host.frame()
    note("mate_panel_visible", frame is not None and mate_panel._host.is_shown())
    note("mate_panel_two_entities", frame is not None and frame.entities.count() == 2)
    buttons = frame.findChildren(QtWidgets.QToolButton) if frame else []
    note("mate_buttons_offered", bool(buttons), [button.text() for button in buttons])
    Gui.getMainWindow().grab().save(os.path.join(OUT, "features_assembly.png"))
    parallel = next((button for button in buttons if button.text() == "Parallel"), None)
    note("parallel_mate_button_present", parallel is not None)
    if parallel:
        parallel.click()
    later(mate_verify)


def mate_verify():
    from jellyjams import assembly_drop
    note("mate_button_opens_joint_dialog", bool(Gui.Control.activeDialog()))
    note("mate_dialog_accept", close_task(True))
    assembly = STATE["assembly"]
    joints = [obj for obj in assembly.Document.Objects if hasattr(obj, "JointType")]
    note("mate_joint_created", len(joints) == 1 and bool(joints[0].Reference1) and bool(joints[0].Reference2))
    before = len(assembly_drop._components_of(assembly))
    assembly_drop._run_drop_job([STATE["part"].FileName], assembly.Document.Name, assembly.Name)
    note("file_drop_inserts_component", len(assembly_drop._components_of(assembly)) == before + 1)
    note("first_drop_grounds_component", assembly_drop._has_ground(assembly))
    finish()


later(start, 4000)
