# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""A constant-radius local fillet change tool, linked to native input geometry."""

import math

import FreeCAD as App

from jellyjams import console, constants, surface_rules

ADD = "Add material"
REMOVE = "Remove material"
FULL = "Full result"


def build(base, edge_names, scope, radius, operation):
    """Return only the added/removed material; keep full-model Booleans native."""
    import Part

    if not math.isfinite(radius) or radius <= 0 or operation not in (ADD, REMOVE, FULL):
        raise ValueError("A positive radius and a valid operation are required")
    if scope is None and operation != FULL:
        raise ValueError("A material-change tool requires a scope")
    if scope is not None and (scope.TypeId != constants.TYPE_PART_BOX
                             or not scope.Placement.Rotation.isSame(App.Rotation(), 1e-10)):
        raise ValueError("The local fillet scope must be an axis-aligned native box")
    original = base.Shape.copy(True, False)
    if operation == FULL:
        if scope is not None:
            raise ValueError("A full-result fillet must not clip the input with a scope")
        local = original
    else:
        box = Part.makeBox(scope.Length.Value, scope.Width.Value, scope.Height.Value, scope.Placement.Base)
        local = original.common(box).copy(True, False)
    targets = [original.getElement(name) for name in edge_names]
    selected = []
    for target in targets:
        first, last = target.valueAt(target.FirstParameter), target.valueAt(target.LastParameter)
        candidates = []
        for edge in local.Edges:
            if edge.Degenerated:
                continue
            if type(edge.Curve) is not type(target.Curve):
                continue
            score = surface_rules.edge_match_score(
                tuple(edge.valueAt(edge.FirstParameter)), tuple(edge.valueAt(edge.LastParameter)), edge.Length,
                tuple(first), tuple(last), target.Length)
            candidates.append((score, edge))
        if not candidates:
            raise ValueError("A selected edge is missing from the scope")
        score, edge = min(candidates, key=lambda item: item[0])
        if score > 1e-5:
            raise ValueError("The scope clips a selected edge")
        selected.append(edge)
    if not selected:
        raise ValueError("Select at least one edge for the local fillet")
    rounded = local.makeFillet(radius, selected)
    shape = rounded if operation == FULL else rounded.cut(local) if operation == ADD else local.cut(rounded)
    if shape.isNull() or not shape.isValid() or not shape.Solids or not shape.isClosed():
        raise ValueError("The local fillet did not produce valid closed change solids")
    return shape


class LocalFilletTool:
    @console.guarded("recompute a local fillet")
    def execute(self, obj):
        placement = obj.Placement
        try:
            base, edges = getattr(obj, constants.PROP_ROUND_BASE)
            shape = build(base, edges, getattr(obj, constants.PROP_ROUND_SCOPE),
                          getattr(obj, constants.PROP_ROUND_RADIUS).Value,
                          getattr(obj, constants.PROP_ROUND_OPERATION))
            shape.Placement = placement
            obj.Shape = shape
            setattr(obj, constants.PROP_GEOMETRY_ERROR, "")
        except Exception as error:
            import Part

            obj.Shape = Part.Shape()
            obj.Placement = placement
            setattr(obj, constants.PROP_GEOMETRY_ERROR, str(error))
            console.error("local fillet failed: %s" % error)

    def dumps(self):
        return None

    def loads(self, state):
        pass


def create(doc, name, base, edges, scope, radius, operation):
    """Create a persistent change tool with an actual driving Radius property."""
    shape = build(base, edges, scope, radius, operation)
    obj = doc.addObject(constants.TYPE_PART_FEATURE_PYTHON, name)
    group = constants.PROP_GROUP
    for kind, prop, description in (
            ("App::PropertyLinkSub", constants.PROP_ROUND_BASE, "Input solid and selected edges"),
            ("App::PropertyLink", constants.PROP_ROUND_SCOPE, "Axis-aligned box that isolates the round"),
            ("App::PropertyLength", constants.PROP_ROUND_RADIUS, "Driving fillet radius"),
            ("App::PropertyEnumeration", constants.PROP_ROUND_OPERATION, "Material change returned by this tool"),
            ("App::PropertyString", constants.PROP_GEOMETRY_ERROR, "Last error, empty after success")):
        obj.addProperty(kind, prop, group, description)
    setattr(obj, constants.PROP_ROUND_BASE, (base, list(edges)))
    setattr(obj, constants.PROP_ROUND_SCOPE, scope)
    setattr(obj, constants.PROP_ROUND_RADIUS, radius)
    setattr(obj, constants.PROP_ROUND_OPERATION, [ADD, REMOVE, FULL])
    setattr(obj, constants.PROP_ROUND_OPERATION, operation)
    obj.setEditorMode(constants.PROP_GEOMETRY_ERROR, 1)
    obj.Proxy = LocalFilletTool()
    obj.Shape = shape
    obj.purgeTouched()
    return obj
