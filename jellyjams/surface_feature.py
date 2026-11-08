# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Portable reconstructed surfaces with editable native control-point lists."""

import json

import FreeCAD as App

from jellyjams import console, constants
from jellyjams import surface_geometry, surface_rules


def _pole_name(index):
    return "%s%02d%s" % (constants.SURFACE_POLES_PREFIX, index, constants.SURFACE_POLES_SUFFIX)


def definition_for(obj):
    """Apply the document's editable control grids to its immutable trim schema."""
    definition = json.loads(getattr(obj, constants.PROP_GEOMETRY_DATA))
    for index, surface in surface_rules.surfaces(definition):
        if surface["kind"] != "BSplineSurface":
            continue
        points = getattr(obj, _pole_name(index))
        surface["poles"] = surface_rules.pole_grid(
            [tuple(point) for point in points], len(surface["poles"]), len(surface["poles"][0]))
    return definition


class GeometryFeature:
    """Recompute geometry from math and control points, with no source CAD dependency."""

    @console.guarded("recompute reconstructed surface geometry")
    def execute(self, obj):
        placement = obj.Placement
        try:
            shape = surface_geometry.decode(definition_for(obj), validate_reference=False)
            if shape.isNull() or not shape.isValid() or not shape.Solids or not shape.isClosed():
                raise ValueError("The edited surfaces do not form valid closed solids")
            shape.Placement = placement
            obj.Shape = shape
            setattr(obj, constants.PROP_GEOMETRY_ERROR, "")
        except Exception as error:
            import Part

            obj.Shape = Part.Shape()
            obj.Placement = placement
            setattr(obj, constants.PROP_GEOMETRY_ERROR, str(error))
            console.error("reconstructed surface geometry failed: %s" % error)

    def dumps(self):
        return None

    def loads(self, state):
        pass


def create(doc, name, definition, source_name="", nominal_radius=None):
    """Create a mathematical geometry tool for native linked Boolean features.

    The nominal source radius is provenance, not a driving fillet parameter.
    B-spline control points are exposed as FreeCAD's editable VectorList fields.
    """
    # Preflight before adding document objects. Never accept a failed cached shape.
    shape = surface_geometry.decode(definition)
    if shape.isNull() or not shape.isValid() or not shape.Solids or not shape.isClosed():
        raise ValueError("The mathematical definition does not form closed valid solids")
    obj = doc.addObject(constants.TYPE_PART_FEATURE_PYTHON, name)
    group = constants.PROP_GROUP
    obj.addProperty("App::PropertyString", constants.PROP_GEOMETRY_DATA, group,
                    "Versioned mathematical surface and boundary definitions")
    setattr(obj, constants.PROP_GEOMETRY_DATA, json.dumps(definition, separators=(",", ":")))
    obj.setEditorMode(constants.PROP_GEOMETRY_DATA, 1)
    obj.addProperty("App::PropertyString", constants.PROP_GEOMETRY_ERROR, group,
                    "The last reconstruction error, empty after a successful recompute")
    obj.setEditorMode(constants.PROP_GEOMETRY_ERROR, 1)
    obj.addProperty("App::PropertyString", constants.PROP_SOURCE_FEATURE_NAME, group)
    setattr(obj, constants.PROP_SOURCE_FEATURE_NAME, source_name)
    obj.setEditorMode(constants.PROP_SOURCE_FEATURE_NAME, 1)
    if nominal_radius is not None:
        obj.addProperty("App::PropertyLength", constants.PROP_SOURCE_NOMINAL_RADIUS, group,
                        "Original radius for reference; edit the surface control points to change geometry")
        setattr(obj, constants.PROP_SOURCE_NOMINAL_RADIUS, nominal_radius)
        obj.setEditorMode(constants.PROP_SOURCE_NOMINAL_RADIUS, 1)
    for index, surface in surface_rules.surfaces(definition):
        if surface["kind"] != "BSplineSurface":
            continue
        rows, columns = len(surface["poles"]), len(surface["poles"][0])
        name = _pole_name(index)
        obj.addProperty("App::PropertyVectorList", name, group,
                        "Surface %d control grid: %d U rows by %d V columns, U-major order" % (index, rows, columns))
        setattr(obj, name, [App.Vector(*p) for row in surface["poles"] for p in row])
    obj.Proxy = GeometryFeature()
    obj.Shape = shape
    obj.purgeTouched()
    return obj
