# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Native colouring, undo, persistence and dock lifecycle; run_gui.py --suites appearances."""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "info": {"version": App.Version()}}
STATE = {}
FIELDS = ("DiffuseColor", "AmbientColor", "SpecularColor", "EmissiveColor", "Shininess", "Transparency")


def material(material):
    return tuple(getattr(material, field) for field in FIELDS)


def snapshot(obj):
    return [material(value) for value in obj.ViewObject.ShapeAppearance]


def same_appearance(first, second):
    # FCStd encodes material colour channels at 8-bit precision. The lighting
    # and transparency scalars remain floating-point values.
    if len(first) != len(second):
        return False
    for old, new in zip(first, second):
        for index, (left, right) in enumerate(zip(old, new)):
            if index < 4:
                if any(abs(a - b) > 1 / 255 + 1e-6 for a, b in zip(left, right)):
                    return False
            elif abs(left - right) > 1e-5:
                return False
    return True


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=200):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, guarded)


def start():
    Gui.activateWorkbench("PartDesignWorkbench")
    later(activate, 3500)


def activate():
    from jellyjams import fcgui
    tasks = fcgui.task_dock()
    STATE["tasks_tabs"] = [dock.objectName() for dock in Gui.getMainWindow().tabifiedDockWidgets(tasks)]
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(create, 4000)


def create():
    import Part
    from jellyjams import appearances as a, constants
    STATE["a"] = a
    note("command_registered", constants.CMD_APPEARANCES in Gui.listCommands())
    Gui.runCommand(constants.CMD_APPEARANCES)
    dock = a.dock()
    note("dock_visible", dock is not None and dock.isVisible())
    from jellyjams import fcgui
    note("tab_beside_tasks", dock in Gui.getMainWindow().tabifiedDockWidgets(fcgui.task_dock()))
    a.enable()
    a.enable()
    note("single_dock_after_repeated_enable", len(Gui.getMainWindow().findChildren(
        QtWidgets.QDockWidget, constants.OBJ_APPEARANCES)) == 1)
    doc = App.newDocument("AppearanceTest")
    doc.UndoMode = 1
    body = doc.addObject("PartDesign::Body", "Body")
    base = body.newObject("PartDesign::Feature", "Base")
    base.Shape = Part.makeBox(25, 20, 10)
    box = doc.addObject("Part::Box", "Box")
    box.Placement.Base.x = 40
    doc.recompute()
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    STATE.update(doc=doc, box=box, body=body, base=base, before=snapshot(box))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(box, "Face1")
    Gui.Selection.addSelection(box, "Face3")
    panel = dock.widget()
    STATE["panel"] = panel
    panel.gallery.setCurrentRow(5)
    note("preview_does_not_change_model", snapshot(box) == STATE["before"])
    from jellyjams.appearance_rules import Appearance
    App.setActiveTransaction("External appearance audit transaction")
    transaction = App.getActiveTransaction()
    try:
        try:
            a.apply_appearance(Appearance("Blocked", "#ff0000"))
            blocked = False
        except ValueError:
            blocked = True
        note("external_application_transaction_preserved", blocked
             and App.getActiveTransaction() == transaction and snapshot(box) == STATE["before"])
    finally:
        App.closeActiveTransaction(True, transaction[1])
    note("library_has_colour_thumbnails", panel.gallery.count() == 12 and not panel.gallery.item(5).icon().isNull())
    panel.search.setText("blue")
    shown = [panel.gallery.item(i).text() for i in range(panel.gallery.count()) if not panel.gallery.item(i).isHidden()]
    note("search_filters_library", len(shown) == 1 and "Blue" in shown[0], shown)
    panel.search.clear()
    panel.apply_button.click()
    later(check_faces)


def check_faces():
    doc, box, a = STATE["doc"], STATE["box"], STATE["a"]
    mats = box.ViewObject.ShapeAppearance
    note("face_appearance_expands_native_list", len(mats) == 6)
    note("two_selected_faces_are_red", all(mats[i].DiffuseColor[0] > .7 and mats[i].DiffuseColor[1] < .3 for i in (0, 2)))
    note("other_faces_unchanged", all(material(mats[i]) == STATE["before"][0] for i in (1, 3, 4, 5)))
    note("gloss_native_shininess", abs(mats[0].Shininess - .85) < .001)
    STATE["face_red"] = snapshot(box)
    doc.undo()
    note("native_undo_restores_original", snapshot(box) == STATE["before"])
    doc.redo()
    note("native_redo_restores_faces", snapshot(box) == STATE["face_red"])
    panel = STATE["panel"]
    panel.color.setText("#24aa66")
    panel.finish.setCurrentText("Matte")
    panel.transparency.setValue(35)
    panel.apply_button.click()
    mats = box.ViewObject.ShapeAppearance
    note("custom_colour_applies_to_faces", abs(mats[0].DiffuseColor[1] - 170 / 255) < .001)
    note("per_face_transparency", abs(mats[0].Transparency - .35) < .001 and mats[1].Transparency == 0)
    note("matte_native_shininess", abs(mats[0].Shininess - .08) < .001)
    panel.color.setText("invalid")
    before = snapshot(box)
    panel.apply_button.click()
    note("invalid_colour_keeps_document_unchanged", snapshot(box) == before)
    panel.color.setText("#245ac9")
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(STATE["body"])
    panel.gallery.setCurrentRow(6)
    panel.apply_button.click()
    note("body_can_be_coloured", STATE["body"].ViewObject.ShapeAppearance[0].DiffuseColor[2] > .7)
    # A native double-click on a library tile, with nothing selected, applies
    # to the visible model. No test-specific click handler is substituted.
    Gui.Selection.clearSelection()
    tile = panel.gallery.item(7)
    panel.gallery.scrollToItem(tile)
    rect = panel.gallery.visualItemRect(tile)
    QtTest.QTest.mouseClick(panel.gallery.viewport(), QtCore.Qt.MouseButton.LeftButton,
                          QtCore.Qt.KeyboardModifier.NoModifier, rect.center())
    QtTest.QTest.mouseDClick(panel.gallery.viewport(), QtCore.Qt.MouseButton.LeftButton,
                           QtCore.Qt.KeyboardModifier.NoModifier, rect.center())
    later(check_double_click)


def check_double_click():
    a, doc, box = STATE["a"], STATE["doc"], STATE["box"]
    note("double_click_applies_to_model_without_selection", box.ViewObject.ShapeAppearance[0].DiffuseColor[1] > .5)
    link = doc.addObject("App::Link", "Link")
    link.setLink(box)
    sibling = doc.addObject("App::Link", "Sibling")
    sibling.setLink(box)
    link.Placement.Base.y = 30
    sibling.Placement.Base.y = 60
    doc.recompute()
    STATE.update(link=link, sibling=sibling, source_before=snapshot(box))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(link)
    panel = STATE["panel"]
    panel.color.setText("#dfbd62")
    panel.finish.setCurrentText("Polished")
    panel.transparency.setValue(0)
    panel.apply_button.click()
    note("component_uses_native_local_override", link.ViewObject.OverrideMaterial
         and abs(link.ViewObject.ShapeMaterial.DiffuseColor[0] - 223 / 255) < .001)
    note("component_colour_does_not_change_source", snapshot(box) == STATE["source_before"])
    note("sibling_component_unchanged", not sibling.ViewObject.OverrideMaterial)
    doc.undo()
    note("component_override_undo", not link.ViewObject.OverrideMaterial)
    doc.redo()
    note("component_override_redo", link.ViewObject.OverrideMaterial)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(link, "Face1")
    note("linked_face_does_not_edit_source", a.targets() == [])
    note("whole_component_scope_resolves_linked_face", a.targets(1) == [(link, None)])
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(box)
    Gui.Selection.addSelection(STATE["body"])
    before_box, before_body = snapshot(box), snapshot(STATE["body"])
    original = a._material
    calls = []

    def fail_second(values):
        calls.append(None)
        if len(calls) == 2:
            raise RuntimeError("test an atomic rollback")
        return original(values)

    a._material = fail_second
    try:
        from jellyjams.appearance_rules import Appearance
        a.apply_appearance(Appearance("Rollback", "#ff0000"))
        note("failed_apply_raises", False)
    except RuntimeError:
        note("failed_apply_raises", True)
    finally:
        a._material = original
    note("failed_multi_object_edit_rolls_back", snapshot(box) == before_box and snapshot(STATE["body"]) == before_body)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(box, "Face2")
    panel.color.setText("#e97d28")
    panel.transparency.setValue(20)
    panel.apply_button.click()
    STATE["saved_box"] = snapshot(box)
    doc.recompute()
    STATE["file"] = os.path.join(OUT, "appearance_saved.FCStd")
    doc.saveAs(STATE["file"])
    a.show()
    Gui.Selection.clearSelection()
    Gui.activeDocument().activeView().fitAll()
    later(save_and_reopen)


def save_and_reopen():
    a = STATE["a"]
    a.dock().grab().save(os.path.join(OUT, "appearances_panel.png"))
    Gui.getMainWindow().grab().save(os.path.join(OUT, "appearances_full.png"))
    App.closeDocument(STATE["doc"].Name)
    doc = App.openDocument(STATE["file"])
    STATE["doc"] = doc
    reopened = snapshot(doc.getObject("Box"))
    RES["info"]["saved_appearance"] = STATE["saved_box"]
    RES["info"]["reopened_appearance"] = reopened
    note("face_appearances_survive_save_reopen", same_appearance(reopened, STATE["saved_box"]))
    STATE["reopened_box"] = reopened
    note("component_override_survives_save_reopen", doc.getObject("Link").ViewObject.OverrideMaterial)
    Gui.activateWorkbench("PartDesignWorkbench")
    later(check_leave, 4000)


def check_leave():
    from jellyjams import constants, fcgui
    a = STATE["a"]
    note("dock_removed_after_leave", Gui.getMainWindow().findChild(QtWidgets.QDockWidget, constants.OBJ_APPEARANCES) is None)
    note("timer_stopped_after_leave", not a._timer.isActive())
    note("document_colours_retained_after_leave", snapshot(STATE["doc"].getObject("Box")) == STATE["reopened_box"])
    tabs = [dock.objectName() for dock in Gui.getMainWindow().tabifiedDockWidgets(fcgui.task_dock())]
    note("stock_task_tabs_restored", tabs == STATE["tasks_tabs"], tabs)
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(check_reentry, 4000)


def check_reentry():
    a = STATE["a"]
    note("panel_returns_after_reentry", a.dock() is not None)
    a.suspend_for_quit()
    note("panel_removed_during_quit", a.dock() is None and not a._timer.isActive())
    a.resume_after_cancel()
    note("panel_returns_after_cancel", a.dock() is not None and a._timer.isActive())
    finish()


def finish():
    try:
        Gui.activateWorkbench("PartDesignWorkbench")
        for name in list(App.listDocuments()):
            App.closeDocument(name)
    except Exception:
        RES["errors"].append("cleanup: " + traceback.format_exc())
    RES["ok"] = bool(RES["checks"]) and not RES["errors"] and all(check["ok"] for check in RES["checks"].values())
    with open(os.path.join(OUT, "appearances.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(800, QtWidgets.QApplication.instance().quit)


later(start, 2500)
