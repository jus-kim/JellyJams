# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Keep native Smart Dimension's linear preview on the pointer.

FreeCAD subtracts one percent of the visible width plus height when placing
linear dimension labels. Undo only that label offset after native mouse moves;
native picking, dimension values, transactions and dialogs remain in charge.
"""

import math

from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, constants, fcgui

_session = None
LINEAR_TYPES = ("Distance", "DistanceX", "DistanceY")


def preview_gap(height, aspect):
    """Native View3DInventorViewer::getDimensions, including portrait views."""
    if not (math.isfinite(height) and math.isfinite(aspect) and height > 0 and aspect > 0):
        raise ValueError("invalid camera dimensions")
    width = height * max(1.0, aspect)
    height = height / min(1.0, aspect)
    return (width + height) * 0.01


def _gap(view, viewport):
    camera = view.getCameraNode()
    if hasattr(camera, "height"):
        height = float(camera.height.getValue())
    else:
        height = 2 * math.tan(camera.heightAngle.getValue() / 2) * camera.focalDistance.getValue()
    return preview_gap(height, viewport.width() / viewport.height())


def _linear(sketch, constraint):
    if constraint.Type not in LINEAR_TYPES:
        return False
    # A whole circular arc's Distance means arc length; its native placement
    # takes a different path with no preview offset to undo.
    if constraint.Type == "Distance" and constraint.FirstPos == 0 and constraint.SecondPos == 0:
        if constraint.First >= 0:
            return getattr(sketch.Geometry[constraint.First], "TypeId", "") != "Part::GeomArcOfCircle"
    return True


class _PreviewFilter(QtCore.QObject):
    def __init__(self, sketch, view, viewport, count):
        super().__init__(viewport)
        self.sketch = sketch
        self.view = view
        self.viewport = viewport
        self.floor = count
        self.cursor = viewport.cursor().pixmap().toImage()
        self.forwarding = False
        self.running = True
        viewport.installEventFilter(self)

    def owns_edit(self):
        return (self.running and fcgui.jellyjams_active()
                and fcgui.sketch_in_edit() is self.sketch)

    def same_cursor(self):
        cursor = self.viewport.cursor()
        # FreeCAD 1.1 can reset to an arrow around the modal value dialog
        # while its continuous Dimension handler is still running.
        return (cursor.shape() == QtCore.Qt.CursorShape.ArrowCursor
                or cursor.pixmap().toImage() == self.cursor)

    def correct(self):
        constraints = self.sketch.Constraints
        # Native Dimension clears its selection after confirm/cancel, and can
        # keep running continuously. Completed dimensions become the new floor.
        if not fcgui.selection():
            self.floor = len(constraints)
            return
        self.floor = min(self.floor, len(constraints))
        gap = _gap(self.view, self.viewport)
        for index in range(self.floor, len(constraints)):
            if _linear(self.sketch, constraints[index]):
                self.sketch.setLabelDistance(index, self.sketch.getLabelDistance(index) + gap)

    def eventFilter(self, widget, event):
        if self.forwarding or not self.running:
            return False
        delivered = False
        try:
            if not self.owns_edit():
                stop()
                return False
            kind = event.type()
            if kind == QtCore.QEvent.Type.Hide:
                stop()
            elif kind == QtCore.QEvent.Type.MouseMove:
                # Let FreeCAD pick geometry, choose the dimension type and move
                # its preview first. One native event, one label correction.
                self.forwarding = True
                try:
                    forwarded = QtGui.QMouseEvent(
                        event.type(), event.position(), event.scenePosition(), event.globalPosition(),
                        event.button(), event.buttons(), event.modifiers(), event.pointingDevice())
                    forwarded.setTimestamp(event.timestamp())
                    QtWidgets.QApplication.sendEvent(widget, forwarded)
                    delivered = True
                finally:
                    self.forwarding = False
                if self.owns_edit() and self.same_cursor():
                    self.correct()
                else:
                    stop()
                return True
        except Exception as exc:
            console.warning("could not align the Smart Dimension preview: %s" % exc)
            stop()
        # If correction failed after native delivery, do not deliver the same
        # mouse move a second time through Qt's original dispatch.
        return delivered

    def close(self):
        self.running = False
        if fcgui.is_alive(self.viewport):
            self.viewport.removeEventFilter(self)
        self.deleteLater()


def stop():
    """Remove the temporary viewport filter; keep native document edits."""
    global _session
    previous, _session = _session, None
    if previous is not None:
        with console.guard("stop the Smart Dimension preview correction", level="log"):
            previous.close()


def run():
    """Run native Dimension once, then watch only its edited 3D viewport."""
    global _session
    stop()
    sketch = fcgui.sketch_in_edit()
    count = len(sketch.Constraints) if sketch is not None else 0
    if not fcgui.run_command(constants.SKETCH_DIMENSION_COMMAND) or sketch is None:
        return
    with console.guard("align the Smart Dimension preview", level="warning"):
        root = fcgui.active_mdi_widget()
        if root is None:
            return
        viewports = [w for w in root.findChildren(QtWidgets.QWidget)
                     if w.inherits("QOpenGLWidget") and w.isVisible()]
        if not viewports:
            return
        import FreeCADGui

        viewport = max(viewports, key=lambda w: w.width() * w.height())
        _session = _PreviewFilter(sketch, FreeCADGui.activeView(), viewport, count)
