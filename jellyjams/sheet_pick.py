# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Click-on-the-sheet mode used by Text, Weld Symbol and Projected View.

While it runs, a left click on the sheet goes to the owning command as a point in sheet
mm and never reaches TechDraw. Right click or Esc cancels. Panning and zooming with the
middle button and the wheel keep working. At most one mode runs; a new one ends the old.
"""

from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, fcgui

DRAIN_TIMEOUT_MS = 1500
RELEASE_RETRY_MS = 50

_Type = QtCore.QEvent.Type
_Button = QtCore.Qt.MouseButton
_PRESS_TYPES = (_Type.MouseButtonPress, _Type.MouseButtonDblClick)
_KEY_TYPES = (_Type.KeyPress, _Type.ShortcutOverride)

_current = None
# A mode cancelled by a right press keeps filtering until the matching release and context
# menu event are through; otherwise TechDraw would receive half of that click.
_draining = []
# Finished modes stay referenced while any eventFilter() call is still running: releasing
# the last reference inside the filter would destroy the QObject Qt is calling into.
_retired = []
_filter_depth = 0


def _retire(mode):
    mode.on_click = None
    _retired.append(mode)
    QtCore.QTimer.singleShot(0, _release_retired)


def _release_retired():
    if _filter_depth > 0:
        QtCore.QTimer.singleShot(RELEASE_RETRY_MS, _release_retired)
        return
    del _retired[:]


def _event_scene_pos(view, event):
    try:
        point = event.position().toPoint()
    except AttributeError:
        point = event.pos()
    return view.mapToScene(point)


class _PickMode(QtCore.QObject):
    """A running click mode, filtering events of one sheet view and its viewport."""

    def __init__(self, view, on_click, on_end, status, owner):
        super().__init__()
        self.view = view
        self.viewport = view.viewport()
        self.on_click = on_click
        self.on_end = on_end
        self.status = status
        self.owner = owner
        self.running = False
        self.left_down = False
        self.press_pos = None
        self.click_pending = False
        self.drain_right = False
        self.installed = False
        self._saved_cursor = None

    # --- setup and teardown -----------------------------------------------------------

    def install(self):
        self.running = True
        viewport = self.viewport
        self._saved_cursor = (
            viewport.testAttribute(QtCore.Qt.WidgetAttribute.WA_SetCursor),
            QtGui.QCursor(viewport.cursor()),
        )
        for widget in (self.view, viewport):
            widget.installEventFilter(self)
        self.installed = True
        self.view.destroyed.connect(self._on_view_destroyed)
        viewport.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        if self.status:
            fcgui.status_message(self.status)
        self.view.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def uninstall(self):
        if not self.installed:
            return
        self.installed = False
        for widget in (self.view, self.viewport):
            if fcgui.is_alive(widget):
                widget.removeEventFilter(self)
        if fcgui.is_alive(self.view):
            try:
                self.view.destroyed.disconnect(self._on_view_destroyed)
            except Exception:
                pass

    def restore_ui(self):
        if fcgui.is_alive(self.viewport) and self._saved_cursor is not None:
            had_own_cursor, cursor = self._saved_cursor
            if had_own_cursor:
                self.viewport.setCursor(cursor)
            else:
                self.viewport.unsetCursor()
        fcgui.clear_status()

    def keep_crosshair(self):
        if self.running and fcgui.is_alive(self.viewport):
            if self.viewport.cursor().shape() != QtCore.Qt.CursorShape.CrossCursor:
                self.viewport.setCursor(QtCore.Qt.CursorShape.CrossCursor)

    def finish_drain(self):
        self.uninstall()
        if self in _draining:
            _draining.remove(self)
            _retire(self)

    def _on_view_destroyed(self, *_args):
        self.installed = False
        if self.running:
            _end(self, cancelled=True)
        if self in _draining:
            _draining.remove(self)
            _retire(self)

    # --- event handling -----------------------------------------------------------------

    def eventFilter(self, watched, event):
        global _filter_depth
        _filter_depth += 1
        try:
            if self.running:
                return self._filter_running(watched, event)
            return self._filter_draining(event)
        except Exception as exc:
            console.log("sheet click mode: event filter error: %s" % exc)
            return False
        finally:
            _filter_depth -= 1

    def _filter_running(self, watched, event):
        event_type = event.type()
        if event_type in _KEY_TYPES:
            if event.key() != QtCore.Qt.Key.Key_Escape:
                return False
            if event_type == _Type.ShortcutOverride:
                event.accept()
                return True
            _end(self, cancelled=True)
            return True
        if watched is not self.viewport:
            return False
        if event_type in _PRESS_TYPES:
            button = event.button()
            if button == _Button.LeftButton:
                self.left_down = True
                if not self.click_pending:
                    self.press_pos = _event_scene_pos(self.view, event)
                return True
            if button == _Button.RightButton:
                self.drain_right = True
                _end(self, cancelled=True)
                return True
            return False
        if event_type == _Type.MouseButtonRelease:
            if event.button() != _Button.LeftButton or not self.left_down:
                return False
            self.left_down = False
            position, self.press_pos = self.press_pos, None
            if position is not None and not self.click_pending:
                self.click_pending = True
                QtCore.QTimer.singleShot(0, lambda: self._deliver(position))
            return True
        if event_type == _Type.ContextMenu:
            return True
        if event_type == _Type.MouseMove and event.buttons() == _Button.NoButton:
            self.keep_crosshair()
        return False

    def _filter_draining(self, event):
        event_type = event.type()
        if event_type == _Type.ContextMenu:
            return True
        if event_type == _Type.MouseButtonRelease and event.button() == _Button.RightButton:
            # Qt sends the context-menu event right after this release, in the same pass.
            QtCore.QTimer.singleShot(0, self.finish_drain)
            return True
        return False

    def _deliver(self, scene_pos):
        try:
            self.click_pending = False
            if _current is not self or not self.running:
                return
            x_mm, y_mm = fcgui.scene_to_sheet(scene_pos.x(), scene_pos.y())
            cancelled = False
            try:
                keep_picking = bool(self.on_click(x_mm, y_mm))
            except Exception:
                console.error("handling the click on the sheet raised an error", with_traceback=True)
                keep_picking, cancelled = False, True
            if _current is self and self.running:
                if keep_picking:
                    self.keep_crosshair()
                else:
                    _end(self, cancelled=cancelled)
        except Exception as exc:
            console.log("sheet click mode: passing on the click failed: %s" % exc)


def _end(mode, cancelled):
    """Stop `mode`: cursor and status bar back, filter removed, then on_end called once."""
    global _current
    if not mode.running:
        return
    mode.running = False
    if _current is mode:
        _current = None
    try:
        mode.restore_ui()
    except Exception as exc:
        console.log("sheet click mode: cursor not restored: %s" % exc)
    if mode.drain_right and mode.installed:
        _draining.append(mode)
        QtCore.QTimer.singleShot(DRAIN_TIMEOUT_MS, mode.finish_drain)
    else:
        mode.uninstall()
        _retire(mode)
    callback, mode.on_end = mode.on_end, None
    if callback is not None:
        try:
            callback(bool(cancelled))
        except Exception:
            console.error("the end-of-picking callback raised an error", with_traceback=True)


def _graphics_view(window):
    if window is None:
        window = fcgui.active_sheet_window()
    if window is None or not fcgui.is_alive(window):
        return None
    if isinstance(window, QtWidgets.QGraphicsView):
        return window
    return fcgui.sheet_graphics_view(window)


def start(window, on_click, on_end=None, status="", owner=""):
    """Begin click mode on sheet window `window`, or on the active sheet window when None.

    Any running mode is cancelled first (its on_end receives True). Returns False when no
    sheet view is available. During the mode the viewport shows a crosshair and the status
    bar shows `status`. A left press stores the point and is swallowed, as is its release;
    on the next event-loop turn on_click(x_mm, y_mm) receives sheet coordinates and returns
    True to wait for another click or False to finish. Left double-clicks are swallowed. A
    right press or Esc cancels (swallowed too). Middle button, wheel and moves are passed
    on. on_end(cancelled) runs exactly once when the mode finishes.
    """
    global _current
    try:
        while _current is not None:
            _end(_current, cancelled=True)
        view = _graphics_view(window)
        if view is None:
            return False
        mode = _PickMode(view, on_click, on_end, str(status or ""), str(owner or ""))
        _current = mode
        try:
            mode.install()
        except Exception:
            _current = None
            mode.running = False
            mode.uninstall()
            mode.restore_ui()
            raise
        return True
    except Exception:
        console.error("starting the sheet click mode failed", with_traceback=True)
        return False


def set_status(text):
    """Change the status-bar hint of the running click mode; does nothing when none runs."""
    mode = _current
    if mode is None:
        return
    mode.status = str(text or "")
    if mode.status:
        fcgui.status_message(mode.status)
    else:
        fcgui.clear_status()


def cancel(owner=None):
    """Cancel the running click mode; with `owner` given, only a mode of that owner."""
    try:
        mode = _current
        if mode is None:
            return
        if owner is not None and mode.owner != owner:
            return
        _end(mode, cancelled=True)
    except Exception as exc:
        console.log("stopping the sheet click mode failed: %s" % exc)


def is_active(owner=None):
    """True while a click mode runs; with `owner` given, only if that owner started it."""
    mode = _current
    if mode is None or not mode.running:
        return False
    return owner is None or mode.owner == owner


def current_owner():
    """Owner of the running click mode, or None."""
    mode = _current
    return mode.owner if mode is not None and mode.running else None
