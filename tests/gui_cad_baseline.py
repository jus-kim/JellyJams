# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Dimensioned STEP, native feature and solved assembly regression gate.

Run only through run_gui.py with disposable profiles. Downloaded data is never
executed. Reference values and STEP bytes are fixed before this script runs.
"""

import json
import math
import os
from pathlib import Path
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from cad_fixtures import CACHE, close_number, verify_cache
from cad_models import build, circle, difference_volume, metrics

OUT = Path(os.environ["JELLYJAMS_RESULTS_DIR"])
RESULT = {"checks": {}, "errors": [], "info": {"freecad": App.Version()}}
STATE = {}


def record(name, ok, detail=None):
    if name in RESULT["checks"]:
        raise AssertionError("Duplicate check: " + name)
    RESULT["checks"][name] = {"ok": bool(ok), "detail": detail}
    (OUT / "cad_baseline.json").write_text(json.dumps(RESULT, indent=2), encoding="utf-8")


def inspect_shape(prefix, shape, expected):
    record(prefix + "/valid", not shape.isNull() and shape.isValid()
           and all(s.isClosed() for s in shape.Solids))
    actual = metrics(shape)
    record(prefix + "/solids", actual["solids"] == expected["solids"], actual["solids"])
    for key in ("volume_mm3", "area_mm2", "bbox_mm", "center_mm"):
        got, want = actual[key], expected[key]
        if isinstance(got, list):
            ok = all(close_number(a, b, absolute=1e-5, relative=0) for a, b in zip(got, want))
        else:
            ok = close_number(got, want)
        record(prefix + "/" + key, ok, {"actual": got, "expected": want})


def same_shape(prefix, shape, reference):
    residual = difference_volume(shape, reference)
    tolerance = max(1e-7, abs(reference.Volume) * 1e-8)
    record(prefix + "/symmetric_difference", residual <= tolerance,
           {"volume_mm3": residual, "limit_mm3": tolerance})


def later(function, milliseconds=300):
    def guarded():
        try:
            function()
        except Exception:
            RESULT["errors"].append(traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(milliseconds, guarded)


def finish():
    RESULT["ok"] = (bool(RESULT["checks"]) and not RESULT["errors"]
                    and all(value["ok"] for value in RESULT["checks"].values()))
    (OUT / "cad_baseline.json").write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
    if not STATE.get("owns_session"):
        # Quitting an unowned session would save its real profile. Leave it alone.
        return
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    QtCore.QTimer.singleShot(200, QtWidgets.QApplication.instance().quit)


def accept_task():
    for box in Gui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        button = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if button is not None and button.isVisible() and button.isEnabled():
            button.click()
            return
    raise AssertionError("Native task has no visible enabled OK button")


def start():
    # Refuse a direct launch against a real profile, before activating JellyJams.
    for key in ("UserParameter", "SystemParameter"):
        profile = Path(App.ConfigGet(key)).resolve()
        if not profile.is_relative_to(TESTS.parent / "scratch") or profile.parent != OUT.resolve():
            raise RuntimeError("CAD tests require runner-owned scratch configs: " + str(profile))
    STATE["owns_session"] = True
    from jellyjams import constants, paths
    record("checkout_under_test", Path(paths.addon_dir()).resolve() == TESTS.parent.resolve())
    data = verify_cache()
    record("pinned_fixture_bytes", True)
    RESULT["info"]["manifest_sha256"] = __import__("hashlib").sha256(
        (TESTS / "fixtures/cad_manifest.json").read_bytes()).hexdigest()
    STATE["cases"] = data["cases"]
    Gui.activateWorkbench(constants.WORKBENCH_KEY)
    later(import_cases, 1500)


def import_cases():
    import Part
    STATE["references"] = {}
    for case in STATE["cases"]:
        shape = Part.Shape()
        shape.read(str(CACHE / case["file"]))
        inspect_shape("import/" + case["id"], shape, case)
        if not case["id"].startswith("nist_"):
            target = OUT / (case["id"] + "_roundtrip.step")
            shape.exportStep(str(target))
            restored = Part.Shape()
            restored.read(str(target))
            inspect_shape("step_roundtrip/" + case["id"], restored, case)
        STATE["references"][case["id"]] = shape
    later(rebuild_cases)


def rebuild_cases():
    from jellyjams import surface_geometry
    for case in STATE["cases"]:
        recipe = case.get("rebuild")
        if not recipe:
            continue
        doc = App.newDocument("Rebuild_" + case["id"])
        doc.UndoMode = 1
        body, sketches = build(doc, recipe)
        prefix = "rebuild/" + case["id"]
        record(prefix + "/solved_sketches", all(sketch.FullyConstrained and sketch.solve() == 0
                                                for sketch in sketches))
        record(prefix + "/native_feature_tree", body.Tip.TypeId.startswith("PartDesign::")
               and all(not obj.isDerivedFrom("PartDesign::Feature") or "Invalid" not in obj.State
                       for obj in body.Group))
        inspect_shape(prefix, body.Shape, case)
        same_shape(prefix, body.Shape, STATE["references"][case["id"]])
        if recipe in ("cylinder", "tiny_pin", "sheet_disc", "washer"):
            before = body.Shape.Volume
            doc.openTransaction("Change driving radius")
            sketches[0].setDatum("OuterRadius", App.Units.Quantity(
                sketches[0].getDatum("OuterRadius").Value * 1.1))
            doc.recompute()
            doc.commitTransaction()
            record(prefix + "/dimension_edit", body.Shape.isValid() and body.Shape.Volume > before * 1.1)
            edited = body.Shape.Volume
            doc.undo()
            doc.recompute()
            record(prefix + "/undo", close_number(body.Shape.Volume, before))
            doc.redo()
            doc.recompute()
            record(prefix + "/redo", close_number(body.Shape.Volume, edited))
            doc.undo()
            doc.recompute()
        if recipe in ("cylinder", "washer", "cone", "dome"):
            restored = surface_geometry.decode(surface_geometry.encode(
                body.Shape, include_parametric_trims=(recipe == "cone")))
            same_shape(prefix + "/jellyjams_geometry", restored, STATE["references"][case["id"]])
        path = OUT / (case["id"] + "_rebuilt.FCStd")
        name = body.Name
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        doc = App.openDocument(str(path))
        body = doc.getObject(name)
        for obj in body.Group:
            obj.touch()
        doc.recompute()
        same_shape(prefix + "/saved_recomputed", body.Shape, STATE["references"][case["id"]])
        record(prefix + "/saved_editable", body.Tip.TypeId.startswith("PartDesign::")
               and doc.getObject("Profile").FullyConstrained)
        App.closeDocument(doc.Name)
    record("rebuild/keeps_workbench", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
    later(assembly_cases)


def make_assembly(label):
    from jellyjams import constants
    doc = App.ActiveDocument
    doc.Label = label
    assembly = next(obj for obj in doc.Objects if obj.TypeId == constants.TYPE_ASSEMBLY)
    joints = next(obj for obj in assembly.Group if obj.TypeId == "Assembly::JointGroup")
    return doc, assembly, joints


def source(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Visibility = False
    return obj


def component(assembly, original, name):
    link = assembly.newObject("App::Link", name)
    link.setLink(original)
    return link


def ground(joints, link):
    import JointObject
    obj = joints.newObject("App::FeaturePython", "GroundedBase")
    JointObject.GroundedJoint(obj, link)
    JointObject.ViewProviderGroundedJoint(obj.ViewObject)
    return obj


def fixed_joint(joints, base, moving, target, name):
    """Native custom JCS connectors; target is relative to the grounded base."""
    import JointObject
    obj = joints.newObject("App::FeaturePython", name)
    JointObject.Joint(obj, 0)
    JointObject.ViewProviderJoint(obj.ViewObject)
    obj.Detach1 = obj.Detach2 = True
    obj.Reference1 = (base, ["", ""])
    obj.Reference2 = (moving, ["", ""])
    obj.Placement1 = target
    obj.Placement2 = App.Placement()
    return obj


def assembly_cases():
    from jellyjams import constants
    Gui.runCommand(constants.CMD_NEW_ASSEMBLY)
    later(repeated_assembly, 700)


def repeated_assembly():
    import Part
    from jellyjams import assembly_commands
    doc, assembly, joints = make_assembly("Repeated STEP components")
    src = source(doc, "CylinderSource", STATE["references"]["cylinder"])
    first = component(assembly, src, "BaseCylinder")
    second = component(assembly, src, "TurnedCylinder")
    ground(joints, first)
    target = App.Placement(App.Vector(60, 0, 10), App.Rotation(App.Vector(0, 0, 1), App.Vector(1, 0, 0)))
    mount = fixed_joint(joints, first, second, target, "TurnedMount")
    second.Placement = App.Placement(App.Vector(-30, 70, -20), App.Rotation(15, 20, 40))
    doc.recompute()
    assembly.solve()
    doc.recompute()
    record("assembly/repeated/solved_pose", second.Placement.isSame(target, 1e-6))
    record("assembly/repeated/shared_source", first.LinkedObject == second.LinkedObject)
    combined = Part.makeCompound([first.Shape, second.Shape])
    expected = next(c for c in STATE["cases"] if c["id"] == "cylinder_twice")
    inspect_shape("assembly/repeated", combined, expected)
    same_shape("assembly/repeated", combined, STATE["references"]["cylinder_twice"])
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(second)
    selected_assembly, selected_component, reason = assembly_commands.rotate_target()
    record("assembly/repeated/mated_rotation_refused", selected_assembly == assembly
           and selected_component is None and assembly_commands.selected_components(assembly) == [second]
           and reason is not None and mount.Label in reason, reason)
    # A deliberately wrong placement must be detected, even though volume is unchanged.
    second.Placement.Base += App.Vector(0, 2, 0)
    wrong = Part.makeCompound([first.Shape, second.Shape])
    record("assembly/repeated/negative_pose_control",
           difference_volume(wrong, STATE["references"]["cylinder_twice"]) > 1)
    assembly.solve()
    path = OUT / "repeated_assembly.FCStd"
    assembly_name = assembly.Name
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    doc = App.openDocument(str(path))
    assembly = doc.getObject(assembly_name)
    second = doc.getObject("TurnedCylinder")
    second.Placement.Base += App.Vector(2, 3, 4)
    assembly.solve()
    doc.recompute()
    record("assembly/repeated/reopen_resolve", second.Placement.isSame(target, 1e-6))
    App.closeDocument(doc.Name)
    from jellyjams import constants
    Gui.runCommand(constants.CMD_NEW_ASSEMBLY)
    later(spool_assembly, 700)


def spool_assembly():
    import Part
    doc, assembly, joints = make_assembly("Three component spool")
    shaft_src = source(doc, "ShaftSource", STATE["references"]["cylinder"])
    washer_src = source(doc, "WasherSource", STATE["references"]["washer"])
    shaft = component(assembly, shaft_src, "Shaft")
    low = component(assembly, washer_src, "LowerWasher")
    high = component(assembly, washer_src, "UpperWasher")
    ground(joints, shaft)
    for name, link, z in (("LowerMount", low, -3), ("UpperMount", high, 30)):
        fixed_joint(joints, shaft, link, App.Placement(App.Vector(0, 0, z), App.Rotation()), name)
        link.Placement = App.Placement(App.Vector(50, 40, 80), App.Rotation(30, 15, 60))
    doc.recompute()
    assembly.solve()
    doc.recompute()
    combined = Part.makeCompound([shaft.Shape, low.Shape, high.Shape])
    expect = {"solids": 3, "volume_mm3": 5250 * math.pi, "area_mm2": 2600 * math.pi,
              "bbox_mm": [-20, -20, -3, 20, 20, 33], "center_mm": [0, 0, 15]}
    inspect_shape("assembly/spool", combined, expect)
    for name, a, b in (("lower_shaft", low, shaft), ("upper_shaft", high, shaft), ("washers", low, high)):
        record("assembly/spool/" + name + "_no_interference", abs(a.Shape.common(b.Shape).Volume) < 1e-7)
        distance = a.Shape.distToShape(b.Shape)[0]
        record("assembly/spool/" + name + "_clearance", close_number(distance, 30 if name == "washers" else 0), distance)
    doc.saveAs(str(OUT / "spool_assembly.FCStd"))
    combined.exportStep(str(OUT / "spool_assembly.step"))
    Gui.activeDocument().activeView().viewIsometric()
    Gui.activeDocument().activeView().fitAll()
    Gui.activeDocument().activeView().saveImage(str(OUT / "spool_assembly.png"), 1000, 750, "White")
    STATE.update(spool_doc=doc, spool_assembly=assembly, spool_shaft=shaft, spool_high=high)
    later(mate_selection)


def mate_selection():
    """Exercise JellyJams' actual geometry classification on imported links."""
    import Part
    from jellyjams import mate_panel
    assembly = STATE["spool_assembly"]
    Gui.Selection.clearSelection()
    for link in (STATE["spool_shaft"], STATE["spool_high"]):
        index = next(i for i, face in enumerate(link.LinkedObject.Shape.Faces, 1)
                     if isinstance(face.Surface, Part.Cylinder))
        Gui.Selection.addSelection(assembly, link.Name + ".Face%d" % index)
    mate_panel.refresh_now()
    frame = mate_panel._host.frame()
    labels = [button.text() for button in frame.findChildren(QtWidgets.QToolButton)] if frame else []
    record("assembly/spool/mate_panel_two_entities", frame is not None and frame.entities.count() == 2)
    record("assembly/spool/cylindrical_mates", all(name in labels for name in ("Hinge", "Concentric", "Slider")), labels)
    Gui.Selection.clearSelection()
    App.closeDocument(STATE["spool_doc"].Name)
    later(workflow_start)


def workflow_start():
    from jellyjams import ribbon
    doc = App.newDocument("RibbonFixture")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Profile")
    circle(sketch, 10)
    doc.recompute()
    Gui.activeDocument().activeView().setActiveObject("pdbody", body)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    STATE.update(workflow_doc=doc, workflow_body=body)
    ribbon.run_entry("PartDesign_Pad")
    later(workflow_pad, 700)


def workflow_pad():
    doc = STATE["workflow_doc"]
    feature = next(obj for obj in doc.Objects if obj.TypeId == "PartDesign::Pad")
    # Set the native task field so accepting the task cannot restore its old value.
    from jellyjams import fcgui
    field = next(w for w in fcgui.task_panel().findChildren(QtWidgets.QAbstractSpinBox)
                 if "length" in w.objectName().lower())
    if not field.setProperty("rawValue", 30.0):
        raise AssertionError("Native Pad length field is not writable")
    doc.recompute()
    record("workflow/pad_native_dialog", bool(Gui.Control.activeDialog()))
    accept_task()
    STATE["workflow_pad"] = feature
    later(workflow_pocket_start, 700)


def workflow_pocket_start():
    from jellyjams import ribbon
    doc, body = STATE["workflow_doc"], STATE["workflow_body"]
    doc.recompute()
    same_shape("workflow/ribbon_pad", body.Shape, STATE["references"]["cylinder"])
    sketch = body.newObject("Sketcher::SketchObject", "Bore")
    sketch.Placement.Base = App.Vector(0, 0, 30)
    circle(sketch, 5)
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    ribbon.run_entry("PartDesign_Pocket")
    later(workflow_pocket, 700)


def workflow_pocket():
    from jellyjams import fcgui
    field = next(w for w in fcgui.task_panel().findChildren(QtWidgets.QAbstractSpinBox)
                 if "length" in w.objectName().lower())
    if not field.setProperty("rawValue", 30.0):
        raise AssertionError("Native Pocket length field is not writable")
    record("workflow/pocket_native_dialog", bool(Gui.Control.activeDialog()))
    accept_task()
    later(workflow_finish, 700)


def workflow_finish():
    import Part
    from jellyjams import constants
    doc, body = STATE["workflow_doc"], STATE["workflow_body"]
    doc.recompute()
    target = Part.makeCylinder(10, 30).cut(Part.makeCylinder(5, 30))
    same_shape("workflow/ribbon_pocket", body.Shape, target)
    record("workflow/pocket_volume", close_number(body.Shape.Volume, 2250 * math.pi))
    record("workflow/keeps_workbench", Gui.activeWorkbench().name() == constants.WORKBENCH_KEY)
    record("workflow/no_open_task", not Gui.Control.activeDialog())
    doc.saveAs(str(OUT / "ribbon_feature_workflow.FCStd"))
    finish()


later(start, 2000)
