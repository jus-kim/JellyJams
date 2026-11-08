# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Real geometry checks; run FreeCAD with disposable -u/-s configs under scratch."""

import json
import math
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT = os.environ.get("JELLYJAMS_RESULTS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch"))
os.makedirs(OUT, exist_ok=True)
RESULTS = {"checks": {}, "errors": []}


def check(name, value):
    RESULTS["checks"][name] = {"ok": bool(value)}


def run():
    try:
        import Part
        from jellyjams import constants, local_fillet, surface_boolean, surface_feature, surface_geometry

        Gui.activateWorkbench("JellyJamsWorkbench")
        for name, shape in [("box", Part.makeBox(2, 3, 4)), ("cylinder", Part.makeCylinder(2, 3))]:
            restored = surface_geometry.decode(surface_geometry.encode(shape))
            restored.check(True)
            check(name + "_round_trip", restored.isValid() and abs(restored.Volume - shape.Volume) < 1e-7)
        ellipse = Part.Ellipse()
        ellipse.MinorRadius = .1
        ellipse.MajorRadius = .4
        ellipse.MinorRadius = .2
        edge = ellipse.toShape(0, math.pi)
        restored = surface_geometry.edge_from_data(surface_geometry.curve_data(edge), Part.Plane())
        check("small_ellipse_boundary_round_trip", abs(restored.Length - edge.Length) < 1e-9)
        torus = Part.makeTorus(1.25, 1, App.Vector(), App.Vector(0, 0, 1), -5, 5, 5)
        torus_data = surface_geometry.encode(torus)
        for face in torus_data["solids"][0]["faces"]:
            if face["surface"]["kind"] == "Toroid":
                face["wires"][0].reverse()
                for edge_data in face["wires"][0]:
                    edge_data["reversed"] = not edge_data["reversed"]
        restored = surface_geometry.decode(torus_data)
        check("periodic_trim_uses_small_patch", restored.isValid() and restored.isClosed()
              and abs(restored.Volume - torus.Volume) < 1e-8)
        tiny_torus = Part.makeTorus(.2, .05, App.Vector(), App.Vector(0, 0, 1), -5, 5, 5)
        tiny_restored = surface_geometry.decode(surface_geometry.encode(tiny_torus, include_parametric_trims=True))
        check("small_torus_radius_round_trip", tiny_restored.isValid() and tiny_restored.isClosed()
              and abs(tiny_restored.Volume - tiny_torus.Volume) < 1e-8)
        doc = App.newDocument("SurfaceGeometryTest")
        cube = doc.addObject("Part::Box", "RoundInput")
        cube.Length = cube.Width = cube.Height = 6
        scope = doc.addObject("Part::Box", "RoundScope")
        scope.Length = scope.Width = scope.Height = 8
        scope.Placement.Base = App.Vector(-1, -1, -1)
        doc.recompute()
        local = local_fillet.create(doc, "LocalRound", cube, ["Edge1"], scope, .5, local_fillet.REMOVE)
        doc.recompute()
        small = local.Shape.Volume
        local.Radius = 1
        doc.recompute()
        check("local_radius_drives_geometry", local.Shape.isValid() and abs(local.Shape.Volume - 4 * small) < 1e-8)
        local.Radius = 0
        doc.recompute()
        check("local_invalid_radius_clears_shape", local.Shape.isNull() and bool(local.GeometryError))
        local.Radius = 1
        doc.recompute()
        check("local_valid_radius_recovers", local.Shape.isValid() and not local.GeometryError)
        full = local_fillet.create(doc, "FullRound", cube, ["Edge1"], None, .5, local_fillet.FULL)
        doc.recompute()
        check("full_round_has_original_solid", full.Shape.isValid()
              and abs(full.Shape.Volume - (216 - small)) < 1e-8)
        full.Radius = 1
        doc.recompute()
        check("full_round_radius_drives_solid", full.Shape.isValid()
              and abs(full.Shape.Volume - (216 - 4 * small)) < 1e-8)
        divider = doc.addObject("Part::Box", "Divider")
        divider.Length, divider.Width, divider.Height = 1, 8, 8
        divider.Placement.Base = App.Vector(1, -1, -1)
        doc.recompute()
        cells = surface_boolean.create(doc, "SelectedCell", cube, divider, surface_boolean.CUT,
                                       keep_largest=True)
        doc.recompute()
        check("boolean_keeps_explicit_largest_cell", cells.Shape.isValid()
              and abs(cells.Shape.Volume - 144) < 1e-8 and cells.DiscardedSolids == 1)
        cells.KeepLargestSolid = False
        doc.recompute()
        check("boolean_can_keep_all_cells", cells.Shape.isValid()
              and len(cells.Shape.Solids) == 2 and cells.DiscardedSolids == 0)
        for label, primitive in (("box", Part.makeBox(2, 3, 4)), ("cylinder", Part.makeCylinder(2, 3))):
            trimmed = surface_geometry.decode(surface_geometry.encode(primitive, include_parametric_trims=True))
            check("parameter_trims_" + label, trimmed.isValid() and trimmed.isClosed()
                  and abs(trimmed.Volume - primitive.Volume) < 1e-6)
        box = Part.makeBox(2, 3, 4)
        definition = surface_geometry.encode(box)
        index = max(range(len(box.Faces)), key=lambda i: box.Faces[i].CenterOfMass.z)
        spline = box.Faces[index].toNurbs().Faces[0].Surface
        spline.increaseDegree(2, 2)
        definition["solids"][0]["faces"][index]["surface"] = surface_geometry.encode_surface(spline)
        obj = surface_feature.create(doc, "SurfaceTool", definition, "TestBlend", .5)
        cutter = doc.addObject("Part::Cylinder", "Cutter")
        cutter.Radius = .25
        cutter.Height = 10
        cutter.Placement.Base = App.Vector(1, 1.5, -1)
        result = doc.addObject("Part::Cut", "DependentCut")
        result.Base, result.Tool = obj, cutter
        doc.recompute()
        before, cut_before = obj.Shape.Volume, result.Shape.Volume
        property_name = surface_feature._pole_name(index + 1)
        original = list(getattr(obj, property_name))
        edited = list(original)
        edited[4] = edited[4] + App.Vector(0, 0, .2)
        setattr(obj, property_name, edited)
        doc.recompute()
        obj.Shape.check(True)
        result.Shape.check(True)
        check("interior_pole_changes_solid", obj.Shape.isValid() and abs(obj.Shape.Volume - before) > .01)
        check("native_dependent_cut_updates", result.Shape.isValid() and abs(result.Shape.Volume - cut_before) > .01)
        mode = obj.getEditorMode(constants.PROP_SOURCE_NOMINAL_RADIUS)
        check("radius_is_reference_only", mode == 1 or "ReadOnly" in mode)
        path = os.path.join(OUT, "surface_geometry.FCStd")
        expected = obj.Shape.Volume
        doc.saveAs(path)
        App.closeDocument(doc.Name)
        doc = App.openDocument(path)
        obj = doc.getObject("SurfaceTool")
        obj.touch()
        doc.recompute()
        check("proxy_restored", isinstance(obj.Proxy, surface_feature.GeometryFeature))
        local = doc.getObject("LocalRound")
        local.touch()
        doc.recompute()
        check("local_proxy_restored", isinstance(local.Proxy, local_fillet.LocalFilletTool)
              and local.Shape.isValid() and abs(local.Shape.Volume - 4 * small) < 1e-8)
        cells = doc.getObject("SelectedCell")
        cells.touch()
        doc.recompute()
        check("boolean_proxy_restored", isinstance(cells.Proxy, surface_boolean.BooleanFeature)
              and cells.Shape.isValid() and len(cells.Shape.Solids) == 2)
        check("save_reopen_recomputes", obj.Shape.isValid() and abs(obj.Shape.Volume - expected) < 1e-8)
        obj.Placement.Base = App.Vector(3, 4, 5)
        obj.touch()
        doc.recompute()
        check("placement_survives_recompute", (obj.Placement.Base - App.Vector(3, 4, 5)).Length < 1e-9)
        setattr(obj, property_name, [])
        doc.recompute()
        check("bad_grid_clears_cached_shape", obj.Shape.isNull())
        check("bad_grid_reports_error", bool(getattr(obj, constants.PROP_GEOMETRY_ERROR)))
        check("placement_survives_failed_edit", (obj.Placement.Base - App.Vector(3, 4, 5)).Length < 1e-9)
        setattr(obj, property_name, edited)
        doc.recompute()
        check("valid_grid_recovers", obj.Shape.isValid() and not getattr(obj, constants.PROP_GEOMETRY_ERROR))
        check("editing_keeps_workbench", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
    except Exception:
        RESULTS["errors"].append(traceback.format_exc())
    finally:
        RESULTS["ok"] = (bool(RESULTS["checks"])
                         and all(item["ok"] for item in RESULTS["checks"].values())
                         and not RESULTS["errors"])
        with open(os.path.join(OUT, "surface_geometry.json"), "w", encoding="utf-8") as stream:
            json.dump(RESULTS, stream, indent=2)
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        QtCore.QTimer.singleShot(200, QtWidgets.QApplication.instance().quit)


QtCore.QTimer.singleShot(2500, run)
