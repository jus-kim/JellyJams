# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Linked Boolean geometry with explicit connected-cell selection."""

import math

from jellyjams import console, constants, surface_rules

CUT = "Cut"
FUSE = "Fuse"


def build(base, tool, operation, tolerance=0.0, keep_largest=False):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Boolean tolerance must be finite and non-negative")
    first, second = base.Shape.copy(True, False), tool.Shape.copy(True, False)
    largest_input_volume = max((abs(s.Volume) for s in first.Solids), default=0.0)
    if operation == CUT:
        shape = first.cut(second, tolerance)
    elif operation == FUSE:
        shape = first.fuse(second, tolerance)
    else:
        raise ValueError("Unknown Boolean operation")
    solids = shape.Solids
    discarded = 0
    if keep_largest and solids:
        shape = max(solids, key=lambda solid: abs(solid.Volume))
        discarded = len(solids) - 1
    if shape.isNull() or not shape.isValid() or not shape.isClosed() or not shape.Solids:
        raise ValueError("The selected Boolean output is not valid closed solid geometry")
    if operation == FUSE and not surface_rules.fusion_retains_input(
            largest_input_volume, max(abs(s.Volume) for s in shape.Solids)):
        raise ValueError("The union lost the input solid; the kernel result cannot be accepted")
    return shape, discarded


class BooleanFeature:
    @console.guarded("recompute reconstructed geometry Boolean")
    def execute(self, obj):
        placement = obj.Placement
        try:
            shape, count = build(getattr(obj, constants.PROP_BOOLEAN_BASE),
                                 getattr(obj, constants.PROP_BOOLEAN_TOOL),
                                 getattr(obj, constants.PROP_BOOLEAN_OPERATION),
                                 getattr(obj, constants.PROP_BOOLEAN_TOLERANCE).Value,
                                 getattr(obj, constants.PROP_KEEP_LARGEST_SOLID))
            shape.Placement = placement
            obj.Shape = shape
            setattr(obj, constants.PROP_DISCARDED_SOLIDS, count)
            setattr(obj, constants.PROP_GEOMETRY_ERROR, "")
        except Exception as error:
            import Part

            obj.Shape = Part.Shape()
            obj.Placement = placement
            setattr(obj, constants.PROP_DISCARDED_SOLIDS, 0)
            setattr(obj, constants.PROP_GEOMETRY_ERROR, str(error))
            console.error("reconstructed geometry Boolean failed: %s" % error)

    def dumps(self):
        return None

    def loads(self, state):
        pass


def create(doc, name, base, tool, operation, tolerance=0.0, keep_largest=False):
    shape, count = build(base, tool, operation, tolerance, keep_largest)
    obj = doc.addObject(constants.TYPE_PART_FEATURE_PYTHON, name)
    for kind, prop, description in (
            ("App::PropertyLink", constants.PROP_BOOLEAN_BASE, "Input solid geometry"),
            ("App::PropertyLink", constants.PROP_BOOLEAN_TOOL, "Linked Boolean tool"),
            ("App::PropertyEnumeration", constants.PROP_BOOLEAN_OPERATION, "Boolean operation"),
            ("App::PropertyLength", constants.PROP_BOOLEAN_TOLERANCE, "Kernel intersection tolerance"),
            ("App::PropertyBool", constants.PROP_KEEP_LARGEST_SOLID, "Keep only the largest solid; discard other connected cells"),
            ("App::PropertyInteger", constants.PROP_DISCARDED_SOLIDS, "Number of discarded cells on the last successful recompute"),
            ("App::PropertyString", constants.PROP_GEOMETRY_ERROR, "Last error, empty after success")):
        obj.addProperty(kind, prop, constants.PROP_GROUP, description)
    setattr(obj, constants.PROP_BOOLEAN_BASE, base)
    setattr(obj, constants.PROP_BOOLEAN_TOOL, tool)
    setattr(obj, constants.PROP_BOOLEAN_OPERATION, [CUT, FUSE])
    setattr(obj, constants.PROP_BOOLEAN_OPERATION, operation)
    setattr(obj, constants.PROP_BOOLEAN_TOLERANCE, tolerance)
    setattr(obj, constants.PROP_KEEP_LARGEST_SOLID, keep_largest)
    setattr(obj, constants.PROP_DISCARDED_SOLIDS, count)
    for prop in (constants.PROP_DISCARDED_SOLIDS, constants.PROP_GEOMETRY_ERROR):
        obj.setEditorMode(prop, 1)
    obj.Proxy = BooleanFeature()
    obj.Shape = shape
    obj.purgeTouched()
    return obj
