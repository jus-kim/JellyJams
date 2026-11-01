# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Decision rules for the Add Relations panel (no FreeCAD imports).

Maps Sketcher selection names to entities, works out which SolidWorks-style
relations FreeCAD will accept for them, and finds the geometric constraints
that already refer to them. The sketch is only read through ``Geometry``,
``ExternalGeo``, ``getGeoVertexIndex`` and constraint-like items, so plain
stand-in objects work too.

Offers come from ``RELATION_CAPABILITIES``: for each relation, the selection
shapes (how many points, how many edges of which kinds, plus a few named
checks) that the mapped Sketcher command of FreeCAD 1.1 takes without a
"wrong selection" refusal and turns into the SolidWorks relation the button
is named after.
"""

import re

GEO_UNDEFINED = -2000
H_AXIS = -1
V_AXIS = -2
POS_NONE, POS_START, POS_END, POS_MID = 0, 1, 2, 3

LINE = "line"
CIRCLE = "circle"
ARC = "arc"
ELLIPSE = "ellipse"
PARTIAL_ELLIPSE = "partial ellipse"
SPLINE = "spline"
POINT = "point"
EDGE = "edge"
AXIS = "axis"

GEOMETRY_KINDS = {
    "Part::GeomLineSegment": (LINE, "Line"),
    "Part::GeomCircle": (CIRCLE, "Circle"),
    "Part::GeomArcOfCircle": (ARC, "Arc"),
    "Part::GeomEllipse": (ELLIPSE, "Ellipse"),
    "Part::GeomArcOfEllipse": (PARTIAL_ELLIPSE, "Partial ellipse"),
    "Part::GeomBSplineCurve": (SPLINE, "Spline"),
    "Part::GeomPoint": (POINT, "Point"),
}
GENERIC_KIND = (EDGE, "Edge")

# Button label -> Sketcher command run on click, in panel order: the common
# relations first, then On entity and Block.
RELATION_COMMANDS = {
    "Horizontal": "Sketcher_ConstrainHorizontal",
    "Vertical": "Sketcher_ConstrainVertical",
    "Collinear": "Sketcher_ConstrainTangent",
    "Perpendicular": "Sketcher_ConstrainPerpendicular",
    "Parallel": "Sketcher_ConstrainParallel",
    "Tangent": "Sketcher_ConstrainTangent",
    "Concentric": "Sketcher_ConstrainCoincident",
    "Midpoint": "Sketcher_ConstrainSymmetric",
    "Coincident": "Sketcher_ConstrainCoincident",
    "Equal": "Sketcher_ConstrainEqual",
    "Symmetric": "Sketcher_ConstrainSymmetric",
    "Fix": "Sketcher_ConstrainLock",
    "On entity": "Sketcher_ConstrainPointOnObject",
    "Block": "Sketcher_ConstrainBlock",
}

# Constraint Type -> name under Existing Relations, in the same panel order.
# Dimensions are deliberately missing.
CONSTRAINT_NAMES = {
    "Horizontal": "Horizontal",
    "Vertical": "Vertical",
    "Perpendicular": "Perpendicular",
    "Parallel": "Parallel",
    "Tangent": "Tangent",
    "Coincident": "Coincident",
    "Equal": "Equal",
    "Symmetric": "Symmetric",
    "PointOnObject": "On entity",
    "Block": "Blocked",
    "InternalAlignment": "Internal alignment",
}

# Edge kinds grouped the way the Sketcher commands test them. FreeCAD stores
# the two axes as line segments, so its "is a line segment" test passes them.
SEGMENT_KINDS = frozenset((LINE, AXIS))
CIRCULAR_KINDS = frozenset((CIRCLE, ARC))
ELLIPTIC_KINDS = frozenset((ELLIPSE, PARTIAL_ELLIPSE))
CONIC_KINDS = CIRCULAR_KINDS | ELLIPTIC_KINDS
ALL_EDGE_KINDS = frozenset((LINE, AXIS, CIRCLE, ARC, ELLIPSE, PARTIAL_ELLIPSE, SPLINE, EDGE))
# Sizes Equal can compare: arcs go with circles, partial ellipses with ellipses.
EQUAL_FAMILIES = (frozenset((LINE,)), CIRCULAR_KINDS, ELLIPTIC_KINDS)

_NUMBERED_NAME = re.compile(r"^(Edge|ExternalEdge|Vertex)([1-9][0-9]*)$")


class Entity:
    """A selected sketch item the panel knows how to handle."""

    __slots__ = ("label", "is_point", "geo_id", "pos_id", "kind", "external",
                 "origin", "axis")

    def __init__(self, label, is_point, geo_id, pos_id=POS_NONE, kind=EDGE,
                 external=False, origin=False, axis=False):
        self.label = label
        self.is_point = bool(is_point)
        self.geo_id = int(geo_id)
        self.pos_id = int(pos_id)
        self.kind = kind
        self.external = bool(external)
        self.origin = bool(origin)
        self.axis = bool(axis)

    @property
    def is_edge(self):
        return not self.is_point

    @property
    def is_axis(self):
        return self.is_edge and (self.axis or self.kind == AXIS)

    @property
    def own(self):
        """True for the sketch's own geometry (no axis, origin or external edge)."""
        return self.geo_id >= 0 and not (self.external or self.origin or self.is_axis)

    @property
    def fixed(self):
        """True for geometry the solver may not move: axes, the origin, external items."""
        return not self.own

    @property
    def edge_kind(self):
        """The kind an edge is matched by (axes always count as AXIS); None for points."""
        if self.is_point:
            return None
        return AXIS if self.is_axis else self.kind

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)

    def __hash__(self):
        return hash(tuple(getattr(self, name) for name in self.__slots__))

    def __repr__(self):
        return "Entity(%r, %s %d/%d, %s%s%s%s)" % (
            self.label, "point" if self.is_point else "edge", self.geo_id, self.pos_id,
            self.kind, ", external" if self.external else "",
            ", origin" if self.origin else "", ", axis" if self.axis else "")


def geometry_kind(type_id):
    """Return (kind, label stem) for a Part geometry TypeId; unknown ones are plain edges."""
    return GEOMETRY_KINDS.get(type_id or "", GENERIC_KIND)


def _origin():
    return Entity("Origin", True, H_AXIS, POS_START, POINT, origin=True)


def _axis(geo_id, label):
    return Entity(label, False, geo_id, POS_NONE, AXIS, axis=True)


def _entity_from_geometry(geometry, geo_id, number, label_prefix=None, external=False):
    kind, stem = geometry_kind(getattr(geometry, "TypeId", ""))
    label = "%s%d" % (label_prefix or stem, number)
    if kind == POINT:
        return Entity(label, True, geo_id, POS_START, POINT, external=external)
    return Entity(label, False, geo_id, POS_NONE, kind, external=external)


class _SketchReader:
    """Cached sketch access for one parse; Geometry hands out copies, so read it once."""

    def __init__(self, sketch):
        self._sketch = sketch
        self._geometry = None
        self._external = None

    def geometry(self, index):
        if self._geometry is None:
            self._geometry = list(self._sketch.Geometry)
        if index < 0:
            raise IndexError(index)
        return self._geometry[index]

    def external(self, index):
        if self._external is None:
            self._external = list(self._sketch.ExternalGeo)
        if index < 0:
            raise IndexError(index)
        return self._external[index]

    def vertex(self, index):
        geo_id, pos_id = self._sketch.getGeoVertexIndex(index)
        return int(geo_id), int(pos_id)


def _parse_one(reader, name):
    name = str(name or "").rsplit(".", 1)[-1]
    if name == "RootPoint":
        return _origin()
    if name == "H_Axis":
        return _axis(H_AXIS, "Horizontal axis")
    if name == "V_Axis":
        return _axis(V_AXIS, "Vertical axis")
    match = _NUMBERED_NAME.match(name)
    if not match:
        return None
    family, number = match.group(1), int(match.group(2))
    if family == "Edge":
        return _entity_from_geometry(reader.geometry(number - 1), number - 1, number)
    if family == "ExternalEdge":
        geo_id = -(number + 2)
        return _entity_from_geometry(reader.external(-geo_id - 1), geo_id, number,
                                     label_prefix="Converted", external=True)
    geo_id, pos_id = reader.vertex(number - 1)
    if geo_id == GEO_UNDEFINED or pos_id == POS_NONE:
        return None
    if (geo_id, pos_id) == (H_AXIS, POS_START):
        return _origin()
    return Entity("Point%d" % number, True, geo_id, pos_id, POINT, external=geo_id <= -3)


def parse_selection(sketch, subnames):
    """Entities for the given selection names, kept in selection order.

    Constraint names, malformed names and names that fail to resolve are
    dropped; everything else is still returned.
    """
    reader = _SketchReader(sketch)
    entities = []
    for name in subnames or ():
        try:
            entity = _parse_one(reader, name)
        except Exception:
            entity = None
        if entity is not None:
            entities.append(entity)
    return entities


ANY_NUMBER = None


class Shape:
    """One kind of selection a relation takes.

    ``points`` and ``edges`` are (fewest, most) counts, where a ``most`` of
    ANY_NUMBER sets no upper limit. Every selected edge must be of one of the
    ``edge_kinds``, and each function in ``checks`` must return True for the
    (points, edges) lists.
    """

    __slots__ = ("points", "edges", "edge_kinds", "checks")

    def __init__(self, points=(0, 0), edges=(0, 0), edge_kinds=ALL_EDGE_KINDS, checks=()):
        self.points = tuple(points)
        self.edges = tuple(edges)
        self.edge_kinds = frozenset(edge_kinds)
        self.checks = tuple(checks)

    def accepts(self, points, edges):
        if not (_count_fits(len(points), self.points) and _count_fits(len(edges), self.edges)):
            return False
        if any(edge.edge_kind not in self.edge_kinds for edge in edges):
            return False
        return all(check(points, edges) for check in self.checks)

    def __repr__(self):
        return "Shape(points=%r, edges=%r, %d edge kinds, checks=%s)" % (
            self.points, self.edges, len(self.edge_kinds),
            [check.__name__ for check in self.checks])


def _count_fits(count, bounds):
    fewest, most = bounds
    return count >= fewest and (most is ANY_NUMBER or count <= most)


# Checks used by the capability table. Each takes the selected points and edges.

def _nothing_fixed(points, edges):
    return not any(entity.fixed for entity in points + edges)


def _at_most_one_fixed(points, edges):
    return sum(1 for entity in points + edges if entity.fixed) <= 1


def _something_movable(points, edges):
    return any(not entity.fixed for entity in points + edges)


def _not_both_straight(points, edges):
    return any(edge.edge_kind not in SEGMENT_KINDS for edge in edges)


def _single_size_family(points, edges):
    kinds = set(edge.edge_kind for edge in edges)
    return any(kinds <= family for family in EQUAL_FAMILIES)


def _points_on_distinct_geometry(points, edges):
    geo_ids = [point.geo_id for point in points]
    return len(set(geo_ids)) == len(geo_ids)


def _each_point_can_meet_each_edge(points, edges):
    # A point of the edge itself is skipped by FreeCAD; a fixed point on a fixed
    # edge is refused.
    return all(point.geo_id != edge.geo_id and not (point.fixed and edge.fixed)
               for point in points for edge in edges)


def _points_not_both_on_mirror(points, edges):
    mirror = edges[0]
    return not all(point.geo_id == mirror.geo_id for point in points)


# Horizontal and Vertical run the same selection code in FreeCAD.
_ALIGNMENT = (
    # A fixed line cannot turn. When an edge is selected FreeCAD drops any
    # selected points, so edges and points never mix here.
    Shape(edges=(1, ANY_NUMBER), edge_kinds=(LINE,), checks=(_nothing_fixed,)),
    # The points are aligned in a chain, each to the next one.
    Shape(points=(2, ANY_NUMBER), checks=(_at_most_one_fixed,)),
)

# Capability table: relation -> the selection shapes FreeCAD 1.1 takes for it.
# "Fixed" follows isPointOrSegmentFixed in Sketcher/Gui/Utils.cpp: any negative
# GeoId (axes, origin, external geometry). Blocked geometry is fixed there too,
# but spotting it needs the constraint list, so FreeCAD reports that case.
RELATION_CAPABILITIES = {
    "Horizontal": _ALIGNMENT,
    "Vertical": _ALIGNMENT,
    # Sketch.cpp addTangentConstraint: for two lines it puts both ends of one
    # onto the other, which makes them collinear.
    "Collinear": (
        Shape(edges=(2, 2), edge_kinds=SEGMENT_KINDS, checks=(_something_movable,)),
    ),
    # FreeCAD also takes a line with a curve (the line turns normal to it);
    # that is not this relation, so straight edges only.
    "Perpendicular": (
        Shape(edges=(2, 2), edge_kinds=SEGMENT_KINDS, checks=(_something_movable,)),
    ),
    # The lines are chained pairwise; a second fixed one stops the command.
    "Parallel": (
        Shape(edges=(2, ANY_NUMBER), edge_kinds=SEGMENT_KINDS, checks=(_at_most_one_fixed,)),
    ),
    # Sketch.cpp: a B-spline only takes tangency through a point.
    "Tangent": (
        Shape(edges=(2, 2), edge_kinds=ALL_EDGE_KINDS - {SPLINE},
              checks=(_something_movable, _not_both_straight)),
    ),
    # With curves only, the coincident command joins their centers. Each curve
    # is paired with the first, and a pair of fixed ones stops the command.
    "Concentric": (
        Shape(edges=(2, ANY_NUMBER), edge_kinds=CONIC_KINDS, checks=(_at_most_one_fixed,)),
    ),
    # A line and one point: the symmetric command makes the line's two ends
    # symmetric about the point. Axes have no real ends to center on.
    "Midpoint": (
        Shape(points=(1, 1), edges=(1, 1), edge_kinds=(LINE,),
              checks=(_each_point_can_meet_each_edge,)),
    ),
    # Each point is joined to the first; a pair of fixed points stops the
    # command and a pair on one geometry is skipped.
    "Coincident": (
        Shape(points=(2, ANY_NUMBER), checks=(_at_most_one_fixed, _points_on_distinct_geometry)),
    ),
    "Equal": (
        Shape(edges=(2, ANY_NUMBER), edge_kinds=CONIC_KINDS | {LINE},
              checks=(_at_most_one_fixed, _single_size_family)),
    ),
    "Symmetric": (
        # Three points: the last one picked is the center of symmetry.
        Shape(points=(3, 3), checks=(_something_movable,)),
        Shape(points=(2, 2), edges=(1, 1), edge_kinds=SEGMENT_KINDS,
              checks=(_something_movable, _points_not_both_on_mirror)),
    ),
    # With several vertices FreeCAD locks them to the last one instead of in
    # place, and an external vertex only gets reference dimensions.
    "Fix": (
        Shape(points=(1, 1), checks=(_nothing_fixed,)),
    ),
    "On entity": (
        Shape(points=(1, 1), edges=(1, ANY_NUMBER), checks=(_each_point_can_meet_each_edge,)),
        Shape(points=(1, ANY_NUMBER), edges=(1, 1), checks=(_each_point_can_meet_each_edge,)),
    ),
    # FreeCAD also refuses Block while the sketch has conflicts or redundancies
    # and says so itself.
    "Block": (
        Shape(edges=(1, ANY_NUMBER), checks=(_nothing_fixed,)),
    ),
}


def _split(entities):
    entities = list(entities or ())
    return ([entity for entity in entities if entity.is_point],
            [entity for entity in entities if not entity.is_point])


def _fits(relation, points, edges):
    return any(shape.accepts(points, edges) for shape in RELATION_CAPABILITIES.get(relation, ()))


def accepts(relation, entities):
    """True when one of the shapes listed for `relation` fits `entities`."""
    return _fits(relation, *_split(entities))


def offered_relations(entities):
    """Labels of the relations FreeCAD will accept for `entities`, in panel order.

    The selection order of the entities never changes the result.
    """
    points, edges = _split(entities)
    return [relation for relation in RELATION_COMMANDS if _fits(relation, points, edges)]


def _references(constraint):
    for geo_attr, pos_attr in (("First", "FirstPos"), ("Second", "SecondPos"),
                               ("Third", "ThirdPos")):
        try:
            geo_id = int(getattr(constraint, geo_attr))
        except Exception:
            continue
        if geo_id == GEO_UNDEFINED:
            continue
        try:
            pos_id = int(getattr(constraint, pos_attr, POS_NONE))
        except Exception:
            pos_id = POS_NONE
        yield geo_id, pos_id


def _involves(constraint, entities):
    for geo_id, pos_id in _references(constraint):
        for entity in entities:
            if entity.geo_id != geo_id:
                continue
            if not entity.is_point or entity.pos_id == pos_id:
                return True
    return False


def existing_relations(constraints, entities):
    """List (constraint index, display name) for each relation touching the entities.

    Dimensions are left out. Unreadable constraints are skipped, and an
    unreadable constraint list yields [].
    """
    entities = list(entities or ())
    if not entities:
        return []
    try:
        items = list(constraints or ())
    except Exception:
        return []
    found = []
    for index, constraint in enumerate(items):
        try:
            name = CONSTRAINT_NAMES.get(str(constraint.Type))
            if name is not None and _involves(constraint, entities):
                found.append((index, name))
        except Exception:
            continue
    return found


def deletion_order(indices):
    """Distinct valid indices sorted high to low, so one deletion never renumbers the next."""
    unique = set()
    for index in indices or ():
        try:
            value = int(index)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            unique.add(value)
    return sorted(unique, reverse=True)
