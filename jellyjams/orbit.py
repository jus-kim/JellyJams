# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Balance native middle-button orbiting without replacing FreeCAD's camera engine.

Only 3D OpenGL widgets receive corrected mouse events; their viewers also watch
key events. A drag keeps a continuous virtual mouse
position so switching to Ctrl-pan or Shift-zoom cannot jump the camera. There
are no persistent overrides; navigation's existing lifecycle owns this hook.
"""

from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, constants, fcgui, params
from jellyjams.orbit_rules import OrbitDrag

_filter = None


def _is_viewport(widget):
    if not widget.inherits("QOpenGLWidget"):
        return False
    parent = widget.parentWidget()
    while parent is not None:
        if parent.inherits(constants.CLASS_VIEWER3D):
            return True
        parent = parent.parentWidget()
    return False


class _OrbitFilter(QtCore.QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.forwarding = False
        self.watched = set()
        self.drags = {}
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.focus_timer = QtCore.QTimer(self)
        self.focus_timer.setSingleShot(True)
        self.focus_timer.timeout.connect(self.refresh)
        QtWidgets.QApplication.instance().focusChanged.connect(self.schedule_refresh)
        self.schedule_refresh()
        self.timer.start()

    @console.guarded("schedule 3D orbit view discovery")
    def schedule_refresh(self):
        # focusChanged can run inside QWidget's destructor. Traversing its
        # children there can crash inside PySide before Python can catch it.
        # Queue no widget arguments: old focus objects may already be deleted
        # when the timer runs. Coalesce focus changes into one event-loop pass.
        if self.running and not self.focus_timer.isActive():
            self.focus_timer.start(0)

    @console.guarded("watch 3D views for balanced orbiting")
    def refresh(self):
        if not self.running:
            return
        self.watched = {w for w in self.watched if fcgui.is_alive(w)}
        self.drags = {w: d for w, d in self.drags.items() if w in self.watched}
        for root in QtWidgets.QApplication.topLevelWidgets():
            for widget in [root] + root.findChildren(QtWidgets.QWidget):
                if widget not in self.watched and (widget.inherits(constants.CLASS_VIEWER3D)
                                                   or _is_viewport(widget)):
                    widget.installEventFilter(self)
                    self.watched.add(widget)

    def _forward(self, widget, event, position):
        replacement = QtGui.QMouseEvent(
            event.type(), QtCore.QPointF(*position), event.globalPosition(),
            event.button(), event.buttons(), event.modifiers(),
        )
        self.forwarding = True
        try:
            QtWidgets.QApplication.sendEvent(widget, replacement)
        finally:
            self.forwarding = False

    def eventFilter(self, widget, event):
        if self.forwarding or not self.running:
            return False
        try:
            if not fcgui.jellyjams_active():
                return False
            kind = event.type()
            types = QtCore.QEvent.Type
            middle = QtCore.Qt.MouseButton.MiddleButton
            if kind in (types.KeyPress, types.KeyRelease):
                # Native key events may reset the navigation's last position to
                # the physical cursor. Rebase before the next mouse movement.
                for viewport, drag in self.drags.items():
                    if viewport is widget or widget.isAncestorOf(viewport):
                        drag.rebase = True
                return False
            if widget.inherits(constants.CLASS_VIEWER3D):
                return False
            if kind == types.Wheel:
                # Native wheel zoom uses the real pointer as its anchor.
                self.drags.pop(widget, None)
                return False
            if kind not in (types.MouseButtonPress, types.MouseButtonRelease, types.MouseMove):
                return False
            pos = event.position()
            if kind == types.MouseButtonPress and event.button() == middle:
                # Cursor-warp navigation has a different mouse-position contract.
                if not params.group(constants.PARAM_VIEW).GetBool("ResetCursorPosition", False):
                    drag = OrbitDrag(pos.x(), pos.y())
                    drag.modifiers, drag.rebase = event.modifiers(), False
                    self.drags[widget] = drag
                return False
            drag = self.drags.get(widget)
            if drag is None:
                return False
            release = kind == types.MouseButtonRelease and event.button() == middle
            if not release and not event.buttons() & middle:
                self.drags.pop(widget, None)
                return False
            orbit = (kind == types.MouseMove and event.buttons() == middle
                     and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier)
            if kind == types.MouseMove and (drag.rebase or drag.modifiers != event.modifiers()):
                # A repeated middle press updates native position/mode without
                # moving the camera or invoking middle-click recenter-on-release.
                self.forwarding = True
                try:
                    press = QtGui.QMouseEvent(
                        types.MouseButtonPress, QtCore.QPointF(*drag.raw), event.globalPosition(),
                        middle, event.buttons(), event.modifiers(),
                    )
                    QtWidgets.QApplication.sendEvent(widget, press)
                finally:
                    self.forwarding = False
                drag = OrbitDrag(*drag.raw)
                drag.modifiers, drag.rebase = event.modifiers(), False
                self.drags[widget] = drag
            mapped = drag.move(pos.x(), pos.y(), widget.width(), widget.height(), orbit)
            if release:
                self.drags.pop(widget, None)
            if mapped == (pos.x(), pos.y()):
                return False
            self._forward(widget, event, mapped)
            return True
        except Exception as exc:
            self.drags.pop(widget, None)
            console.warning("balancing the orbit drag failed: %s" % exc)
            return False

    def stop(self):
        self.running = False
        self.timer.stop()
        self.focus_timer.stop()
        with console.guard("disconnect the orbit focus watcher", level="log"):
            QtWidgets.QApplication.instance().focusChanged.disconnect(self.schedule_refresh)
        for widget in self.watched:
            if fcgui.is_alive(widget):
                drag = self.drags.get(widget)
                if drag is not None and drag.mapped != drag.raw:
                    # End a transformed drag before handing physical coordinates
                    # back to FreeCAD, even when the old style is the same one.
                    with console.guard("end the balanced orbit drag", level="warning"):
                        event = QtGui.QMouseEvent(
                            QtCore.QEvent.Type.MouseButtonRelease, QtCore.QPointF(*drag.mapped),
                            QtCore.QPointF(QtGui.QCursor.pos()), QtCore.Qt.MouseButton.MiddleButton,
                            QtCore.Qt.MouseButton.NoButton, drag.modifiers,
                        )
                        QtWidgets.QApplication.sendEvent(widget, event)
                widget.removeEventFilter(self)
        self.watched.clear()
        self.drags.clear()
        self.deleteLater()


def install():
    """Install once; also discover document views created after activation."""
    global _filter
    with console.guard("enable balanced middle-button orbiting"):
        if not fcgui.is_alive(_filter):
            _filter = _OrbitFilter(fcgui.main_window())


def uninstall():
    """Remove every viewport hook on leave/quit, including quit cancellation."""
    global _filter
    current, _filter = _filter, None
    with console.guard("remove balanced middle-button orbiting"):
        if fcgui.is_alive(current):
            current.stop()
