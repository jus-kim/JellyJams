# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Mathematical curves and surfaces for reconstructed document geometry.

No BREP, mesh or external source-file payload is stored in this schema.
Part is imported only when a real document is being rebuilt.
"""

import FreeCAD as App

def encode_surface(surface):
    import Part
    kind = type(surface).__name__
    if kind != 'BSplineSurface':
        if kind not in ('Plane', 'Cylinder', 'Sphere', 'Cone', 'Toroid'):
            raise ValueError('Unsupported surface ' + kind)
        return {'kind': kind, 'position': list(surface.Position if kind == 'Plane' else surface.Center), 'rotation': list(surface.Rotation.Q), 'parameters': {name: getattr(surface, name) for name in ('Radius', 'MajorRadius', 'MinorRadius', 'SemiAngle') if hasattr(surface, name)}}
    return {'kind': kind, 'poles': [[list(v) for v in row] for row in surface.getPoles()], 'weights': surface.getWeights(), 'u_knots': surface.getUKnots(), 'v_knots': surface.getVKnots(), 'u_mults': surface.getUMultiplicities(), 'v_mults': surface.getVMultiplicities(), 'u_degree': surface.UDegree, 'v_degree': surface.VDegree, 'u_periodic': surface.isUPeriodic(), 'v_periodic': surface.isVPeriodic()}


def decode_surface(data):
    import Part
    if data.get('kind', 'BSplineSurface') != 'BSplineSurface':
        surface = getattr(Part, data['kind'])()
        if data['kind'] == 'Toroid':
            # Keep both radii valid while shrinking below the constructor defaults.
            surface.MinorRadius = min(surface.MinorRadius, data['parameters']['MinorRadius']) / 2
        for name, value in data['parameters'].items():
            setattr(surface, name, value)
        surface.transform(App.Placement(App.Vector(*data['position']), App.Rotation(*data['rotation'])).toMatrix())
        return surface
    surface = Part.BSplineSurface()
    surface.buildFromPolesMultsKnots([[App.Vector(*p) for p in row] for row in data['poles']], data['u_mults'], data['v_mults'], data['u_knots'], data['v_knots'], data['u_periodic'], data['v_periodic'], data['u_degree'], data['v_degree'], data['weights'])
    return surface


def curve_data(edge):
    import Part
    if edge.Degenerated:
        return {'kind': 'Degenerated', 'point': list(edge.Vertexes[0].Point)}
    curve = edge.Curve
    kind = type(curve).__name__
    data = {'kind': kind, 'range': [edge.FirstParameter, edge.LastParameter]}
    if kind == 'Line':
        data['points'] = [list(curve.value(p)) for p in data['range']]
    elif kind in ('Circle', 'Ellipse'):
        data.update(position=list(curve.Center), rotation=list(curve.Rotation.Q), parameters={p: getattr(curve, p) for p in ('Radius', 'MajorRadius', 'MinorRadius') if hasattr(curve, p)})
    elif kind == 'BSplineCurve':
        data.update(poles=[list(v) for v in curve.getPoles()], weights=curve.getWeights(), knots=curve.getKnots(), mults=curve.getMultiplicities(), periodic=curve.isPeriodic(), degree=curve.Degree)
    else:
        raise ValueError('Unsupported 3D curve ' + kind)
    return data


def edge_from_data(data, surface):
    import Part
    kind = data['kind']
    if kind == 'Degenerated':
        face = surface.toShape()
        candidates = [e for e in face.Edges if e.Degenerated]
        if not candidates:
            raise ValueError('Surface has no natural degenerate boundary')
        point = App.Vector(*data['point'])
        return min(candidates, key=lambda e: (e.Vertexes[0].Point - point).Length).copy()
    if kind == 'Line':
        return Part.makeLine(*[App.Vector(*v) for v in data['points']])
    if kind in ('Circle', 'Ellipse'):
        curve = getattr(Part, kind)()
        if kind == 'Ellipse':
            # Set a valid temporary minor radius before reducing the major radius.
            curve.MinorRadius = min(curve.MinorRadius, data['parameters']['MinorRadius']) / 2
        for p, value in data['parameters'].items():
            setattr(curve, p, value)
        curve.transform(App.Placement(App.Vector(*data['position']), App.Rotation(*data['rotation'])).toMatrix())
    else:
        curve = Part.BSplineCurve()
        curve.buildFromPolesMultsKnots([App.Vector(*v) for v in data['poles']], data['mults'], data['knots'], data['periodic'], data['degree'], data['weights'])
    return curve.toShape(*data['range'])


def pcurve_data(face, edge):
    """Retain trimming in surface parameter space without another projection."""
    result = face.curveOnSurface(edge)
    if result is None:
        return None
    curve, first, last = result
    spline = curve.toBSpline(first, last)
    return {"poles": [[p.x, p.y] for p in spline.getPoles()],
            "weights": spline.getWeights(), "knots": spline.getKnots(),
            "mults": spline.getMultiplicities(), "degree": spline.Degree,
            "periodic": spline.isPeriodic(),
            "range": [spline.FirstParameter, spline.LastParameter]}


def edge_from_pcurve(data, surface):
    """Construct a trim edge directly on its mathematical support."""
    import Part

    curve = Part.Geom2d.BSplineCurve2d()
    curve.buildFromPolesMultsKnots([App.Base.Vector2d(*p) for p in data['poles']],
                                  data['mults'], data['knots'], data['periodic'],
                                  data['degree'], data['weights'])
    return curve.toShape(surface, *data['range'])


def face_from_data(data, validate_reference=True, edge_pool=None):
    """Rebuild a trimmed face, resolving the two sides of a periodic loop."""
    import Part

    surface = decode_surface(data['surface'])
    wires = []
    for boundary in data['wires']:
        edges = []
        for item in boundary:
            key = item.get('edge_id')
            edge = edge_pool.get(key) if edge_pool is not None and key is not None else None
            if edge is None:
                edge = (edge_from_pcurve(item['geometry2d'], surface) if item.get('geometry2d')
                        else edge_from_data(item['geometry3d'], surface))
                edge.fixTolerance(max(1e-7, item['tolerance']))
                if edge_pool is not None and key is not None:
                    edge_pool[key] = edge
            if item['reversed']:
                edge = edge.reversed()
            edges.append(edge)
        wires.append(Part.Wire(edges))

    def candidate(outer):
        face = Part.Face(surface, outer)
        if len(wires) > 1:
            face.cutHoles(wires[1:])
        if not face.isValid():
            face.fix(1e-7, 1e-7, max(1e-7, data['tolerance']))
        return face

    face = candidate(wires[0])
    expected = data.get('area')
    tolerance = max(2e-4, abs(expected or 0) * .002)
    if not face.isValid() or face.Area < 0 or expected is not None and abs(face.Area - expected) > tolerance:
        alternate = candidate(wires[0].reversed())
        if alternate.isValid() and (not face.isValid() or
                abs(alternate.Area - (expected or abs(face.Area))) < abs(face.Area - (expected or abs(face.Area)))):
            face = alternate
    if validate_reference and expected is not None and abs(face.Area - expected) > tolerance:
        raise ValueError('Reconstructed trim differs from its reference face area')
    if data['reversed']:
        face.reverse()
    return face


def decode(data, validate_reference=True):
    """Build solids from their mathematical supports and oriented boundaries."""
    import Part

    if data.get('version') != 1:
        raise ValueError('Unsupported mathematical geometry version')
    solids = []
    for solid_data in data['solids']:
        edge_pool = {}
        faces = [face_from_data(face, validate_reference, edge_pool) for face in solid_data['faces']]
        shell = Part.makeShell(faces)
        shell.sewShape(max(1e-6, max(face['tolerance'] for face in solid_data['faces'])))
        if shell.ShapeType == 'Face':
            shell = Part.makeShell([shell])
        if len(shell.Shells) != 1:
            raise ValueError('Boundaries did not join to one shell')
        solid = Part.makeSolid(shell.Shells[0])
        if solid.Volume < 0:
            solid.reverse()
        solids.append(solid)
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)



def encode(shape, include_parametric_trims=False):
    """Capture analytic/NURBS supports and their three-dimensional boundaries."""
    solids = []
    for solid in shape.Solids:
        faces = []
        source_edges = solid.Edges
        for face in solid.Faces:
            source_wires = [face.OuterWire] + [w for w in face.Wires if not w.isSame(face.OuterWire)]
            wires = []
            for wire in source_wires:
                edges = [{"geometry3d": curve_data(edge),
                          "geometry2d": pcurve_data(face, edge) if include_parametric_trims else None,
                          "edge_id": next(i for i, source in enumerate(source_edges) if edge.isSame(source)),
                          "reversed": edge.Orientation == "Reversed",
                          "tolerance": edge.getTolerance(2)} for edge in wire.OrderedEdges]
                if edges:
                    wires.append(edges)
            faces.append({"surface": encode_surface(face.Surface), "wires": wires,
                          "tolerance": face.getTolerance(2), "area": face.Area, "reversed": face.Orientation == "Reversed"})
        solids.append({"faces": faces})
    return {"version": 1, "solids": solids}
