# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Original native Sketcher/Part Design recipes for the published STEP corpus.

No STEP is used to construct these models. Expected dimensions come from the
CC0 corpus definition; the reference files are read separately by the tests.
"""

import math


def circle(sketch, radius, x=0, y=0):
    import FreeCAD as App
    import Part
    import Sketcher
    index = sketch.addGeometry(Part.Circle(App.Vector(x, y, 0), App.Vector(0, 0, 1), radius), False)
    if x == 0 and y == 0:
        sketch.addConstraint(Sketcher.Constraint("Coincident", index, 3, -1, 1))
    else:
        sketch.addConstraint(Sketcher.Constraint("DistanceX", index, 3, x))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", index, 3, y))
    constraint = sketch.addConstraint(Sketcher.Constraint("Radius", index, radius))
    return constraint


def polygon(sketch, points):
    import FreeCAD as App
    import Part
    import Sketcher
    for i, point in enumerate(points):
        end = points[(i + 1) % len(points)]
        sketch.addGeometry(Part.LineSegment(App.Vector(*point, 0), App.Vector(*end, 0)), False)
    for i in range(len(points)):
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % len(points), 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))


def pad(body, sketch, length):
    obj = body.newObject("PartDesign::Pad", "Pad")
    obj.Profile, obj.Length = sketch, length
    body.Document.recompute()
    sketch.Visibility = False
    return obj


def build(doc, recipe):
    """Return body and dimensioned sketches; the body tip is native/editable."""
    import FreeCAD as App
    import Part
    import Sketcher
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Profile")
    sketches = [sketch]
    if recipe in ("cylinder", "tiny_pin", "sheet_disc", "washer"):
        radius, length = {"cylinder": (10, 30), "tiny_pin": (.25, 2),
                          "sheet_disc": (1800, 19), "washer": (20, 3)}[recipe]
        index = circle(sketch, radius)
        sketch.renameConstraint(index, "OuterRadius")
        if recipe == "washer":
            index = circle(sketch, 5)
            sketch.renameConstraint(index, "BoreRadius")
        pad(body, sketch, length)
    elif recipe in ("cone", "dome"):
        sketch.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        if recipe == "cone":
            polygon(sketch, [(0, 0), (10, 0), (0, 30)])
            for constraint in (Sketcher.Constraint("Horizontal", 0),
                               Sketcher.Constraint("Vertical", 2),
                               Sketcher.Constraint("Distance", 0, 10),
                               Sketcher.Constraint("Distance", 2, 30)):
                sketch.addConstraint(constraint)
        else:
            sketch.addGeometry(Part.LineSegment(App.Vector(), App.Vector(20, 0, 0)), False)
            sketch.addGeometry(Part.ArcOfCircle(Part.Circle(App.Vector(), App.Vector(0, 0, 1), 20),
                                                0, math.pi / 2), False)
            sketch.addGeometry(Part.LineSegment(App.Vector(0, 20, 0), App.Vector()), False)
            for constraint in (Sketcher.Constraint("Coincident", 0, 1, -1, 1),
                               Sketcher.Constraint("Coincident", 0, 2, 1, 1),
                               Sketcher.Constraint("Coincident", 1, 2, 2, 1),
                               Sketcher.Constraint("Coincident", 2, 2, 0, 1),
                               Sketcher.Constraint("Coincident", 1, 3, -1, 1),
                               Sketcher.Constraint("Horizontal", 0),
                               Sketcher.Constraint("Vertical", 2),
                               Sketcher.Constraint("Radius", 1, 20)):
                sketch.addConstraint(constraint)
        feature = body.newObject("PartDesign::Revolution", "Revolution")
        feature.Profile = sketch
        feature.ReferenceAxis = (sketch, ["V_Axis"])
        feature.Angle = 360
        sketch.Visibility = False
    elif recipe == "plate":
        polygon(sketch, [(0, 0), (100, 0), (100, 100), (0, 100)])
        for constraint in (Sketcher.Constraint("Horizontal", 0), Sketcher.Constraint("Vertical", 1),
                           Sketcher.Constraint("Horizontal", 2), Sketcher.Constraint("Vertical", 3),
                           Sketcher.Constraint("Distance", 0, 100), Sketcher.Constraint("Distance", 1, 100)):
            sketch.addConstraint(constraint)
        base = pad(body, sketch, 10)
        edges = ["Edge%d" % (i + 1) for i, edge in enumerate(base.Shape.Edges)
                 if edge.BoundBox.ZLength > 9.99 and edge.BoundBox.XLength < 1e-8
                 and edge.BoundBox.YLength < 1e-8]
        if len(edges) != 4:
            raise AssertionError("Could not identify the four vertical plate edges")
        fillet = body.newObject("PartDesign::Fillet", "CornerRounds")
        fillet.Base, fillet.Radius = (base, edges), 4
        doc.recompute()
        base.Visibility = False
        holes = body.newObject("Sketcher::SketchObject", "HoleGrid")
        holes.Placement.Base = App.Vector(0, 0, 10)
        for x in range(10):
            for y in range(10):
                circle(holes, 3, 5 + 10 * x, 5 + 10 * y)
        pocket = body.newObject("PartDesign::Pocket", "ThroughHoles")
        pocket.Profile, pocket.Length = holes, 10
        holes.Visibility = fillet.Visibility = False
        sketches.append(holes)
    else:
        raise ValueError("Unknown CAD recipe: " + recipe)
    doc.recompute()
    return body, sketches


def metrics(shape):
    """Compounds have no CenterOfMass property: weight their solid centres."""
    # GUI display tessellation can make BoundBox underestimate a curved face.
    # Query exact geometry, independently of whether a viewport has meshed it.
    bounds = shape.optimalBoundingBox(False, False)
    solids = shape.Solids
    volume = sum(solid.Volume for solid in solids)
    return {"solids": len(solids), "volume_mm3": volume, "area_mm2": shape.Area,
            "bbox_mm": [bounds.XMin, bounds.YMin, bounds.ZMin, bounds.XMax, bounds.YMax, bounds.ZMax],
            "center_mm": [sum(solid.CenterOfMass[i] * solid.Volume for solid in solids) / volume
                          for i in range(3)]}


def difference_volume(left, right):
    """Bidirectional difference catches misplaced holes with identical mass."""
    return abs(left.cut(right).Volume) + abs(right.cut(left).Volume)
