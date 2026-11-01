# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Selection-driven, temporary measurements; no document or preference writes."""

import math

from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, fcgui

_session = None


def is_active():
    return _session is not None and not _session.closed


def _refresh_button():
    with console.guard("update the Measure button"):
        from jellyjams import ribbon
        ribbon.refresh_measure_button()


def toggle():
    if is_active():
        stop()
    else:
        start()


def _active_view():
    """Follow the actual front view, including Start/drawing and undocked views."""
    getter = getattr(fcgui.main_window(), "getActiveWindow", None)
    return getter() if getter is not None else fcgui.gui().activeView()


def selected_items(selection):
    """Flatten unresolved paths, keeping separate edges of the same object."""
    result = []
    for entry in selection:
        for sub in entry.SubElementNames or ("",):
            item = (entry.Object, sub)
            if item not in result:
                result.append(item)
    return result


def _reference_shape(shape, part):
    """Use a circular edge's centre or a cylindrical face's finite axis."""
    if getattr(shape, "ShapeType", "") == "Edge" and isinstance(shape.Curve, part.Circle):
        return part.Vertex(shape.Curve.Center)
    if getattr(shape, "ShapeType", "") == "Face" and isinstance(shape.Surface, part.Cylinder):
        surface = shape.Surface
        _umin, _umax, vmin, vmax = shape.ParameterRange
        first = surface.Center + surface.Axis * vmin
        last = surface.Center + surface.Axis * vmax
        return part.makeLine(first, last)
    if getattr(shape, "ShapeType", "") == "Face" and isinstance(shape.Surface, getattr(part, "Sphere", ())):
        return part.Vertex(shape.Surface.Center)
    return shape


def shortest_distance(items, use_centers=True):
    """Measure in world space, using circular centres/axes unless clearance is requested."""
    import Part
    shapes = [Part.getShape(obj, sub, needSubElement=True) for obj, sub in items]
    if len(shapes) != 2 or any(shape.isNull() for shape in shapes):
        raise ValueError("Select two faces, edges, vertices or objects.")
    if use_centers:
        shapes = [_reference_shape(shape, Part) for shape in shapes]
    distance, points, _info = shapes[0].distToShape(shapes[1])
    if not points:
        raise ValueError("No nearest points found.")
    return distance, points[0]


def _quantity(value, power=1):
    import FreeCAD
    unit = FreeCAD.Units.Unit("mm" if power == 1 else "mm^{}".format(power))
    return FreeCAD.Units.Quantity(value, unit).UserString


def _coordinates(point):
    return ", ".join(_quantity(v) for v in point)


def _angle(value):
    import FreeCAD
    return FreeCAD.Units.Quantity(value, FreeCAD.Units.Angle).UserString


def _perimeter(face):
    # Periodic surfaces have topological seams, which are not face boundaries.
    return sum(edge.Length for edge in face.Edges if not edge.isSeam(face))


def _direction(shape, part):
    kind = shape.ShapeType
    if kind == "Edge" and isinstance(shape.Curve, part.Line):
        return shape.Vertexes[-1].Point - shape.Vertexes[0].Point, False
    if kind == "Face" and isinstance(shape.Surface, part.Plane):
        return shape.Surface.Axis, True
    if kind == "Face" and isinstance(shape.Surface, part.Cylinder):
        return shape.Surface.Axis, False
    return None


def _pair_angle(first, second, part):
    a, b = _direction(first, part), _direction(second, part)
    if a is None or b is None or a[0].Length < 1e-12 or b[0].Length < 1e-12:
        return None
    cosine = min(1.0, abs(a[0].dot(b[0])) / (a[0].Length * b[0].Length))
    return math.degrees(math.asin(cosine) if a[1] != b[1] else math.acos(cosine))


def single_measurement(shape):
    """Geometry-dependent rows and a real on-shape anchor for a single pick."""
    import Part
    kind = shape.ShapeType
    rows = []
    anchor = shape.CenterOfMass if kind != "Vertex" else shape.Point
    if kind == "Vertex":
        rows = [(name, _quantity(value)) for name, value in zip(("X", "Y", "Z"), shape.Point)]
    elif kind in ("Edge", "Wire"):
        if kind == "Edge" and isinstance(shape.Curve, Part.Circle):
            curve = shape.Curve
            rows = [("Radius", _quantity(curve.Radius)),
                    ("Diameter", _quantity(2 * curve.Radius)), ("Center", _coordinates(curve.Center))]
            full = abs(shape.Length - 2 * math.pi * curve.Radius) < max(1e-7, shape.Length * 1e-7)
            if full:
                rows.append(("Circumference", _quantity(shape.Length)))
            else:
                rows.extend([("Arc length", _quantity(shape.Length)),
                             ("Chord length", _quantity((shape.Vertexes[-1].Point - shape.Vertexes[0].Point).Length)),
                             ("Angle", _angle(math.degrees(shape.Length / curve.Radius)))])
        else:
            rows = [("Length", _quantity(shape.Length))]
        if kind == "Edge":
            anchor = shape.valueAt((shape.FirstParameter + shape.LastParameter) * 0.5)
    elif kind == "Face":
        rows = [("Area", _quantity(shape.Area, 2))]
        perimeter = _perimeter(shape)
        if perimeter > 1e-9:
            rows.append(("Perimeter", _quantity(perimeter)))
        if isinstance(shape.Surface, (Part.Cylinder, Part.Sphere)):
            rows.extend([("Radius", _quantity(shape.Surface.Radius)),
                         ("Diameter", _quantity(2 * shape.Surface.Radius))])
            if isinstance(shape.Surface, Part.Sphere):
                rows.append(("Center", _coordinates(shape.Surface.Center)))
        # Centre of mass can lie inside a hole or off a curved face.
        _distance, nearest, _info = Part.Vertex(anchor).distToShape(shape)
        anchor = nearest[0][1]
    elif shape.Faces:
        rows = [("Area", _quantity(shape.Area, 2))]
        if shape.Solids:
            rows.append(("Volume", _quantity(shape.Volume, 3)))
    if not rows:
        raise ValueError("This geometry has no supported measurement.")
    return rows, (anchor, anchor)


def measurement(items, use_centers=True, show_xyz=False):
    """Return labelled results and world-space endpoints for the current picks."""
    import Part
    shapes = [Part.getShape(obj, sub, needSubElement=True) for obj, sub in items]
    if not shapes or any(shape.isNull() for shape in shapes):
        raise ValueError("Select geometry to measure.")
    if len(shapes) == 1:
        return single_measurement(shapes[0])
    rows = []
    edges = all(shape.ShapeType in ("Edge", "Wire") for shape in shapes)
    faces = all(shape.ShapeType == "Face" for shape in shapes)
    if len(shapes) == 2:
        references = [_reference_shape(shape, Part) for shape in shapes] if use_centers else shapes
        distance, nearest, _info = references[0].distToShape(references[1])
        points = nearest[0]
        centered = use_centers and any(ref is not original for ref, original in zip(references, shapes))
        rows.append(("Center distance" if centered else "Distance", _quantity(distance)))
        angle = _pair_angle(shapes[0], shapes[1], Part)
        if angle is not None:
            rows.append(("Angle", _angle(angle)))
        if show_xyz:
            rows.extend((name, _quantity(abs(value))) for name, value in
                        zip(("dX", "dY", "dZ"), points[1] - points[0]))
    elif len(shapes) == 3 and all(shape.ShapeType == "Vertex" for shape in shapes):
        a, center, b = (shape.Point for shape in shapes)
        first, second = a - center, b - center
        if min(first.Length, second.Length) < 1e-12:
            raise ValueError("Select three distinct points; the second point is the angle vertex.")
        rows = [("Angle", _angle(math.degrees(first.getAngle(second))))]
        points = (center, center)
    else:
        points = (shapes[0].CenterOfMass, shapes[0].CenterOfMass)
    if edges:
        rows.append(("Total length", _quantity(sum(shape.Length for shape in shapes))))
    if faces:
        rows.extend([("Total area", _quantity(sum(shape.Area for shape in shapes), 2)),
                     ("Total perimeter", _quantity(sum(_perimeter(shape) for shape in shapes)))])
    if not rows:
        raise ValueError("Select one or two features, three points, or multiple edges or faces.")
    return rows, points


def callout_image(rows, font=None):
    """A constant-screen-size, two-column white measurement card."""
    from jellyjams import palette
    font = QtGui.QFont(font or QtWidgets.QApplication.font())
    font.setPixelSize(18)
    font.setBold(False)
    metrics = QtGui.QFontMetrics(font)
    padding = 9
    labels = max(metrics.horizontalAdvance(label + ":") for label, _ in rows)
    values = max(metrics.horizontalAdvance(value) for _, value in rows)
    column = labels + 2 * padding
    row_height = metrics.height() + 10
    image = QtGui.QImage(column + values + 2 * padding + 1, row_height * len(rows) + 2,
                         QtGui.QImage.Format.Format_RGBA8888)
    image.fill(QtGui.QColor(palette.MEASURE_BACKGROUND))
    painter = QtGui.QPainter(image)
    try:
        painter.setFont(font)
        painter.setPen(QtGui.QColor(palette.MEASURE_FOREGROUND))
        painter.drawRect(0, 0, image.width() - 1, image.height() - 1)
        painter.drawLine(column, 0, column, image.height() - 1)
        for index, (label, value) in enumerate(rows):
            baseline = 1 + index * row_height + (row_height - metrics.height()) // 2 + metrics.ascent()
            painter.drawText(padding, baseline, label + ":")
            painter.drawText(column + padding, baseline, value)
    finally:
        painter.end()
    return image


class MeasureTask:
    def __init__(self, doc, view):
        self.doc = doc
        self.view = view
        self.items = []
        self.node = None
        self.callout_rows = []
        self.callout_bitmap = None
        self.pending = False
        self.cleared = False
        self.restore_items = []
        self.closed = False
        self.form = QtWidgets.QWidget()
        self.form.destroyed.connect(self.on_destroyed)
        self.form.setWindowTitle("Measure")
        layout = QtWidgets.QVBoxLayout(self.form)
        hint = QtWidgets.QLabel("Select geometry to see its size, or two features for distance and angle. "
                                "Circular edges use their centers and cylindrical faces use their axes. "
                                "Click empty space to clear measurements.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.reference = QtWidgets.QComboBox()
        self.reference.addItems(["Centers / axes", "Nearest surfaces (clearance)"])
        self.reference.currentIndexChanged.connect(
            console.guarded("change measurement reference")(self.refresh))
        layout.addWidget(self.reference)
        self.show_xyz = QtWidgets.QCheckBox("Show XYZ distances")
        self.show_xyz.toggled.connect(console.guarded("show measurement components")(self.refresh))
        layout.addWidget(self.show_xyz)
        self.result = QtWidgets.QLabel()
        self.result.setWordWrap(True)
        result_font = self.result.font()
        result_font.setBold(True)
        if result_font.pointSizeF() > 0:
            result_font.setPointSizeF(result_font.pointSizeF() + 2)
        else:
            result_font.setPixelSize(max(16, result_font.pixelSize() + 3))
        self.result.setFont(result_font)
        layout.addWidget(self.result)
        reset = QtWidgets.QPushButton("Clear")
        reset.clicked.connect(console.guarded("clear measurements")(self.clear))
        layout.addWidget(reset)
        self.timer = QtCore.QTimer(self.form)
        self.timer.timeout.connect(console.guarded("check measurement view")(self.check))

    def start(self):
        fcgui.gui().Selection.addObserver(self, 0)
        self.timer.start(150)
        self.refresh()

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Close

    @console.guarded("close measurements")
    def reject(self):
        stop()
        return True

    def clear(self):
        self.items = []
        self.restore_items = []
        fcgui.gui().Selection.clearSelection()
        self.queue()

    def check(self):
        if self.closed or _session is not self:
            return
        import FreeCAD
        if (not fcgui.jellyjams_active() or FreeCAD.ActiveDocument is not self.doc
                or _active_view() != self.view):
            stop()

    def queue(self):
        if not self.pending and not self.closed:
            self.pending = True
            fcgui.defer(self.refresh)

    @console.guarded("update measurement selection")
    def clearSelection(self, *args):
        # Native normal clicks clear then add in one event. Wait until the event
        # completes to distinguish that replacement from a click on empty space.
        self.cleared = True
        self.queue()

    @console.guarded("add measurement selection")
    def addSelection(self, *args):
        if self.cleared:
            self.restore_items = list(self.items)
        self.queue()

    @console.guarded("remove measurement selection")
    def removeSelection(self, *args):
        self.queue()

    @console.guarded("replace measurement selection")
    def setSelection(self, *args):
        self.queue()

    def remove_annotation(self):
        node, self.node = self.node, None
        self.callout_rows = []
        self.callout_bitmap = None
        if node is not None:
            with console.guard("detach measurement graphics from the old view", level="log"):
                self.view.getSceneGraph().removeChild(node)

    @console.guarded("refresh measurements")
    def refresh(self):
        self.pending = False
        if self.closed:
            return
        self.remove_annotation()
        self.result.setText("")
        selection = fcgui.gui().Selection
        previous = self.items
        items = selected_items(selection.getSelectionEx(self.doc.Name, 0))
        restore, self.restore_items = self.restore_items, []
        self.cleared = False
        # Re-add only after native selection delivery, never inside its observer.
        for obj, sub in restore if items else ():
            if (obj, sub) not in items:
                selection.addSelection(obj, sub)
                items.append((obj, sub))
        # Native replacement restores picks after the newest item. Retain the
        # user's chronological order so the second vertex stays the angle vertex.
        self.items = [item for item in previous if item in items]
        self.items.extend(item for item in items if item not in self.items)
        items = self.items
        if not items:
            return
        try:
            rows, points = measurement(items, self.reference.currentIndex() == 0, self.show_xyz.isChecked())
            self.result.setText("\n".join(label + ": " + value for label, value in rows))
            self.draw(points, rows)
        except Exception as exc:
            self.result.setText("Unable to measure this selection.")
            console.warning("could not measure selection: {}".format(exc))

    def draw(self, points, rows):
        from pivy import coin
        import FreeCAD
        from jellyjams import palette
        # Draw after opaque geometry with depth testing disabled: the label and
        # dimension line often lie exactly on the selected PCB surface.
        node = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        node.addChild(pick)
        anchor = (points[0] + points[1]) * 0.5
        camera = self.view.getCameraNode()
        height = (camera.height.getValue() if hasattr(camera, "height") else
                  2 * camera.focalDistance.getValue() * math.tan(camera.heightAngle.getValue() / 2))
        offset = self.view.getCameraOrientation().multVec(FreeCAD.Vector(height * 0.07, height * 0.08, 0))
        card_position = anchor + offset
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 4, [tuple(points[0]), tuple(points[1]), tuple(anchor), tuple(card_position)])
        node.addChild(coords)
        # A white underlay keeps thin black leaders visible over dark backgrounds.
        for shade, width in ((palette.MEASURE_BACKGROUND, 3), (palette.MEASURE_FOREGROUND, 1)):
            color = coin.SoBaseColor()
            color.rgb = QtGui.QColor(shade).getRgbF()[:3]
            node.addChild(color)
            style = coin.SoDrawStyle()
            style.lineWidth = width
            node.addChild(style)
            line = coin.SoLineSet()
            line.numVertices.setValues(0, 2, [2, 2])
            node.addChild(line)
        position = coin.SoTranslation()
        position.translation = tuple(card_position)
        node.addChild(position)
        bitmap = callout_image(rows, self.form.font())
        pixels = bitmap.mirrored(False, True)
        card = coin.SoImage()
        card.horAlignment = coin.SoImage.LEFT
        card.vertAlignment = coin.SoImage.BOTTOM
        card.image.setValue(coin.SbVec2s(pixels.width(), pixels.height()), 4, bytes(pixels.constBits()))
        node.addChild(card)
        self.view.getSceneGraph().addChild(node)
        self.node = node
        self.callout_rows = list(rows)
        self.callout_bitmap = bitmap

    def dispose(self):
        if self.closed:
            return
        self.closed = True
        if fcgui.is_alive(self.timer):
            self.timer.stop()
        with console.guard("detach measurement observer"):
            fcgui.gui().Selection.removeObserver(self)
        with console.guard("remove measurement annotation"):
            self.remove_annotation()

    @console.guarded("dispose measurement task")
    def on_destroyed(self, *args):
        global _session
        if _session is self:
            _session = None
        self.dispose()
        _refresh_button()


def start():
    """Open the ribbon's Measure task without changing native Measure settings."""
    global _session
    if _session is not None:
        return
    gui = fcgui.gui()
    if gui.Control.activeDialog():
        return
    import FreeCAD
    view = _active_view()
    if FreeCAD.ActiveDocument is None or view is None or not hasattr(view, "getCameraNode"):
        _refresh_button()
        return
    task = MeasureTask(FreeCAD.ActiveDocument, view)
    _session = task
    try:
        gui.Control.showDialog(task)
        task.start()
        _refresh_button()
    except Exception:
        stop()
        raise


def stop():
    global _session
    task, _session = _session, None
    if task is not None:
        with console.guard("stop measurements"):
            task.dispose()
        with console.guard("close measurement task"):
            fcgui.gui().Control.closeDialog()
    _refresh_button()
