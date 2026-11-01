# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Add Mate panel rules without FreeCAD: entity kinds, mates to offer, and the hint text.

Every mate carries a capability entry: the unordered pairs of reference kinds
it accepts, each with the number of degrees of freedom the underlying FreeCAD
joint removes for that pair. The pairs follow what FreeCAD 1.1 can actually
build from a reference: the joint coordinate system (JCS) that
``UtilsAssembly.findPlacement`` derives from it, and the geometry pairs that
the Distance joint resolves to a dedicated solver joint.
"""

HINGE = "Hinge"
SLIDER = "Slider"
CONCENTRIC = "Concentric"
BALL_JOINT = "Ball Joint"
COINCIDENT = "Coincident"
TANGENT = "Tangent"
PARALLEL = "Parallel"
PERPENDICULAR = "Perpendicular"
ANGLE = "Angle"
DISTANCE = "Distance…"

MATE_COMMANDS = {
    HINGE: "Assembly_CreateJointRevolute",
    SLIDER: "Assembly_CreateJointSlider",
    CONCENTRIC: "Assembly_CreateJointCylindrical",
    BALL_JOINT: "Assembly_CreateJointBall",
    # Coincident and Tangent are a Distance joint left at its default of 0: FreeCAD
    # adds the radii of round references, so zero means touching for those.
    COINCIDENT: "Assembly_CreateJointDistance",
    TANGENT: "Assembly_CreateJointDistance",
    PARALLEL: "Assembly_CreateJointParallel",
    PERPENDICULAR: "Assembly_CreateJointPerpendicular",
    ANGLE: "Assembly_CreateJointAngle",
    DISTANCE: "Assembly_CreateJointDistance",
}

PLANAR_FACE = "Planar face"
CYLINDRICAL_FACE = "Cylindrical face"
CONICAL_FACE = "Conical face"
SPHERICAL_FACE = "Spherical face"
FACE = "Face"
LINEAR_EDGE = "Linear edge"
CIRCULAR_EDGE = "Circular edge"
EDGE = "Edge"
POINT = "Point"
COMPONENT = "Component"

_FACE_KINDS = {
    "Plane": PLANAR_FACE,
    "Cylinder": CYLINDRICAL_FACE,
    "Cone": CONICAL_FACE,
    "Sphere": SPHERICAL_FACE,
}
_EDGE_KINDS = {
    "Line": LINEAR_EDGE,
    "LineSegment": LINEAR_EDGE,
    "Circle": CIRCULAR_EDGE,
    "ArcOfCircle": CIRCULAR_EDGE,
}

# Kinds grouped by what their JCS is good for. A cylinder or a circle gives an
# axis with its origin on that axis; a cone gives its axis with the origin at
# the apex; a linear edge gives its direction; a planar face gives its normal.
# Points carry no direction, and generic faces or edges no reliable one.
_PIVOTS = (CYLINDRICAL_FACE, CIRCULAR_EDGE)
_TURNED = (CYLINDRICAL_FACE, CONICAL_FACE, CIRCULAR_EDGE)
_LINES = _TURNED + (LINEAR_EDGE,)
_GUIDES = (LINEAR_EDGE, CYLINDRICAL_FACE)
_NORMALS = (PLANAR_FACE,)


def _pair_key(kind_a, kind_b):
    return frozenset((kind_a, kind_b))


def _every(group_a, group_b, removes):
    """One kind from each group, in either order, all removing `removes` freedoms."""
    return {_pair_key(a, b): removes for a in group_a for b in group_b}


def _each(*rows):
    """Pairs listed one by one as (kind, kind, freedoms removed)."""
    return {_pair_key(a, b): removes for a, b, removes in rows}


def _same_direction_kind(removes):
    # Parallel, Perpendicular and Angle compare the Z axes of the two JCSs. A
    # plane's Z axis is its normal, an edge's or turned face's is its direction,
    # so mixing the two would give the opposite of what the button says.
    entry = _every(_NORMALS, _NORMALS, removes)
    entry.update(_every(_LINES, _LINES, removes))
    return entry


# Capability matrix: mate -> {unordered pair of kinds: degrees of freedom removed}.
# Insertion order is the catalogue order, used only to break ties.
MATE_CAPABILITIES = {
    # Revolute: shared axis and shared origin, one rotation left.
    HINGE: _every(_PIVOTS, _PIVOTS, 5),
    # Slider: shared straight axis with the twist locked, one translation left.
    SLIDER: _every(_GUIDES, _GUIDES, 5),
    # Cylindrical: collinear axes; two plain lines are a Coincident instead.
    CONCENTRIC: _every(_TURNED, _LINES, 4),
    # Ball: shared centre. Two points are already a ball joint as Coincident.
    BALL_JOINT: _every((SPHERICAL_FACE,), (SPHERICAL_FACE, POINT), 3),
    # Distance 0 on pairs where zero means lying on one another.
    COINCIDENT: _each(
        (LINEAR_EDGE, LINEAR_EDGE, 4),
        (POINT, POINT, 3),
        (PLANAR_FACE, PLANAR_FACE, 3),
        (CIRCULAR_EDGE, PLANAR_FACE, 3),
        (POINT, LINEAR_EDGE, 2),
        (LINEAR_EDGE, PLANAR_FACE, 2),
        (POINT, PLANAR_FACE, 1),
        (POINT, CYLINDRICAL_FACE, 1),
        (POINT, SPHERICAL_FACE, 1),
    ),
    # Distance 0 on pairs where FreeCAD adds the radii, so zero means touching.
    TANGENT: _each(
        (CYLINDRICAL_FACE, CYLINDRICAL_FACE, 3),
        (PLANAR_FACE, CYLINDRICAL_FACE, 2),
        (PLANAR_FACE, SPHERICAL_FACE, 1),
        (CYLINDRICAL_FACE, SPHERICAL_FACE, 1),
        (SPHERICAL_FACE, SPHERICAL_FACE, 1),
    ),
    PARALLEL: _same_direction_kind(2),
    PERPENDICULAR: _same_direction_kind(1),
    ANGLE: _same_direction_kind(1),
    # Every pair the Distance joint handles with a non-zero value.
    DISTANCE: _each(
        (LINEAR_EDGE, LINEAR_EDGE, 3),
        (LINEAR_EDGE, CIRCULAR_EDGE, 3),
        (CIRCULAR_EDGE, CIRCULAR_EDGE, 3),
        (CIRCULAR_EDGE, PLANAR_FACE, 3),
        (PLANAR_FACE, PLANAR_FACE, 3),
        (CYLINDRICAL_FACE, CYLINDRICAL_FACE, 3),
        (LINEAR_EDGE, PLANAR_FACE, 2),
        (PLANAR_FACE, CYLINDRICAL_FACE, 2),
        (POINT, POINT, 1),
        (POINT, LINEAR_EDGE, 1),
        (POINT, PLANAR_FACE, 1),
        (POINT, CYLINDRICAL_FACE, 1),
        (POINT, SPHERICAL_FACE, 1),
        (PLANAR_FACE, SPHERICAL_FACE, 1),
        (CYLINDRICAL_FACE, SPHERICAL_FACE, 1),
        (SPHERICAL_FACE, SPHERICAL_FACE, 1),
    ),
}


def _geometry_name(geometry):
    name = str(geometry or "").strip()
    for prefix in ("Part::Geom", "Part::", "Part."):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def kind_from(shape_type, geometry):
    """The row text describing one selected element.

    shape_type: "Face", "Edge", "Vertex", or None when a whole object is picked.
    geometry: TypeId ("Part::GeomPlane") or class name ("Plane") of the face's
    surface or the edge's curve. A face or edge whose geometry is unknown is
    reported as a Component.
    """
    shape_type = str(shape_type or "")
    if shape_type == "Vertex":
        return POINT
    name = _geometry_name(geometry)
    if shape_type == "Face":
        return _FACE_KINDS.get(name, FACE) if name else COMPONENT
    if shape_type == "Edge":
        return _EDGE_KINDS.get(name, EDGE) if name else COMPONENT
    return COMPONENT


def removed_freedoms(mate, kind_a, kind_b):
    """Degrees of freedom `mate` removes between the two kinds; None if it rejects them."""
    return MATE_CAPABILITIES.get(mate, {}).get(_pair_key(kind_a, kind_b))


def offered_mates(kind_a, kind_b, same_component=False):
    """Labels of the mate buttons for two kinds, the most constraining mate first.

    Mates removing equally many degrees of freedom keep their catalogue order.
    Two entities of one component never get a mate.
    """
    if same_component:
        return []
    scored = []
    for mate in MATE_CAPABILITIES:
        removes = removed_freedoms(mate, kind_a, kind_b)
        if removes is not None:
            scored.append((removes, mate))
    scored.sort(key=lambda item: -item[0])
    return [mate for _removes, mate in scored]


def hint(count, same_component, offered):
    """Guidance shown under the mate buttons, or None when no guidance is needed."""
    if count == 1:
        return "Now pick one more entity, on a different component."
    if count > 2:
        return "A mate takes two entities. Reduce the selection to two."
    if count == 2 and same_component:
        return ("These two entities belong to one component. "
                "Pick the second one on a different component.")
    if count == 2 and not offered:
        return "None of the mates fits this pair of entities."
    return None
