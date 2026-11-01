# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Drag a drawing view by any of its lines, and double-click JellyJams symbols to edit them.

On its own, TechDraw moves a view only when the press hits the view's frame
or blank area. This event filter on the sheet viewport also moves the
selected view when the press hits one of its edges or faces. TechDraw always
sees the press, so selecting still works; the filter only consumes the moves
past the drag threshold and the release that ends the drag.
"""

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, doc_utils, fcgui
from jellyjams import projected_view

DRAG_THRESHOLD_PX = 5
UNDO_NAME = "Move View"
_ATTACHED_MARK = "JellyJamsDragFilter"
_AXIS_X = "x"
_AXIS_Y = "y"
_EPS = 1e-9

_mouse_filter = None
_press = None     # (viewport, position) of a left press that may still turn into a drag
_drag = None      # the running _Drag, if any


class _Drag:
    __slots__ = ("viewport", "view", "doc", "mover", "axis", "start_scene", "start_xy", "rez",
                 "undo_open", "undo_id")

    def __init__(self, viewport, view, doc, mover, axis, start_scene):
        self.viewport = viewport
        self.view = view
        self.doc = doc
        self.mover = mover
        self.axis = axis
        self.start_scene = start_scene
        self.start_xy = projected_view.xy(mover)
        self.rez = fcgui.rez()
        self.undo_open = False
        self.undo_id = 0


# --- rules ------------------------------------------------------------------------------


def is_movable_view(obj):
    """True for drawing views that can be dragged (dimensions and balloons cannot)."""
    if (doc_utils.is_derived(obj, constants.TYPE_DIMENSION)
            or doc_utils.is_derived(obj, constants.TYPE_BALLOON)):
        return False
    if (doc_utils.is_derived(obj, constants.TYPE_PROJ_ITEM)
            or doc_utils.is_derived(obj, constants.TYPE_PROJ_GROUP)):
        return True
    type_id = doc_utils.type_id(obj)
    return type_id.startswith("TechDraw::DrawView") or type_id in (
        constants.TYPE_COMPLEX_SECTION, constants.TYPE_BROKEN_VIEW)


def drag_plan(obj):
    """(object to move, axis limit) when `obj` is dragged.

    The limit is None (any direction), "x" (horizontal) or "y" (vertical),
    matching the alignment TechDraw keeps between projections of a group.
    """
    if not doc_utils.is_derived(obj, constants.TYPE_PROJ_ITEM):
        return obj, None
    group = projected_view.owning_group(obj)
    if group is None:
        return obj, None
    cell = projected_view.sheet_slot(projected_view.projection_type(obj),
                                     projected_view.effective_method(group))
    if cell is None:
        return obj, None
    column, row = cell
    if column == 0 and row == 0:
        return group, None
    if row == 0:
        return obj, _AXIS_X
    if column == 0:
        return obj, _AXIS_Y
    return obj, None


def _pick_running():
    try:
        from jellyjams import sheet_pick
    except Exception:
        return False
    try:
        return bool(sheet_pick.is_active())
    except Exception:
        return True


def _sheet_idle():
    """JellyJams is active, and neither a task dialog nor a TechDraw tool is in use."""
    return (fcgui.jellyjams_active() and not fcgui.task_dialog_open()
            and not fcgui.techdraw_tool_running())


def _drag_allowed():
    return _sheet_idle() and not _pick_running()


def _selected_view():
    for obj in fcgui.selection():
        if is_movable_view(obj):
            return obj
    return None


def _symbol_kind(obj):
    if not doc_utils.is_derived(obj, constants.TYPE_SYMBOL):
        return ""
    return str(getattr(obj, constants.PROP_SYMBOL_TYPE, "") or "").strip()


def _selected_symbol():
    for obj in fcgui.selection():
        if _symbol_kind(obj) in (constants.KIND_SURFACE, constants.KIND_WELD):
            return obj
    return None


# --- Qt helpers ---------------------------------------------------------------------------


def _event_pos(event):
    try:
        return event.position()
    except AttributeError:
        return QtCore.QPointF(event.pos())


def _left_held(event):
    return bool(event.buttons() & QtCore.Qt.MouseButton.LeftButton)


def _graphics_view(viewport):
    parent = viewport.parentWidget() if fcgui.is_alive(viewport) else None
    return parent if isinstance(parent, QtWidgets.QGraphicsView) else None


def _techdraw_drags_itself(view):
    """True if a movable scene item already grabbed this press (TechDraw moves it)."""
    scene = view.scene()
    grabber = scene.mouseGrabberItem() if scene is not None else None
    if grabber is None:
        return False
    return bool(grabber.flags() & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


def _rubber_banding(view):
    try:
        return not view.rubberBandRect().isNull()
    except Exception:
        return False


# --- drag -----------------------------------------------------------------------------------


def _open_undo(drag):
    """Start the "Move View" step right before the drag's first document change."""
    if not drag.undo_open:
        drag.undo_id = projected_view.open_undo(drag.doc, UNDO_NAME)
        drag.undo_open = True


def _start_drag(viewport, press_pos):
    global _drag
    if not _drag_allowed():
        return False
    view = _graphics_view(viewport)
    if view is None or _techdraw_drags_itself(view) or _rubber_banding(view):
        return False
    target = _selected_view()
    if target is None:
        return False
    mover, axis = drag_plan(target)
    if bool(getattr(mover, "LockPosition", False)):
        return False
    start_scene = view.mapToScene(press_pos.toPoint())
    drag = _Drag(viewport, view, mover.Document, mover, axis, start_scene)
    _drag = drag
    if doc_utils.is_derived(target, constants.TYPE_PROJ_ITEM):
        group = projected_view.owning_group(target)
        if group is not None and projected_view.needs_release(group):
            _open_undo(drag)
            projected_view.release_auto_distribute(group)
    return True


def _drag_to(pos):
    drag = _drag
    scene_pos = drag.view.mapToScene(pos.toPoint())
    dx = (scene_pos.x() - drag.start_scene.x()) / drag.rez
    dy = -(scene_pos.y() - drag.start_scene.y()) / drag.rez
    if drag.axis == _AXIS_X:
        dy = 0.0
    elif drag.axis == _AXIS_Y:
        dx = 0.0
    x, y = drag.start_xy[0] + dx, drag.start_xy[1] + dy
    current_x, current_y = projected_view.xy(drag.mover)
    move_x = abs(x - current_x) > _EPS
    move_y = abs(y - current_y) > _EPS
    if not (move_x or move_y):
        return
    _open_undo(drag)
    if move_x:
        drag.mover.X = x
    if move_y:
        drag.mover.Y = y


def _finish_drag():
    """End the running drag: close its "Move View" step and recompute. True if one ran."""
    global _drag
    drag, _drag = _drag, None
    if drag is None:
        return False
    with console.guard("release the mouse grab on the sheet", level="log"):
        # The release never reaches the scene, so the item holding the mouse grab must drop it.
        if fcgui.is_alive(drag.view) and drag.view.scene() is not None:
            grabber = drag.view.scene().mouseGrabberItem()
            if grabber is not None:
                grabber.ungrabMouse()
    if drag.undo_open:
        with console.guard("close the Move View undo step", level="log"):
            projected_view.close_undo(drag.doc, drag.undo_id)
        with console.guard("recompute the drawing after the move", level="log"):
            drag.doc.recompute()
    return True


# --- event handlers -------------------------------------------------------------------------


def _on_press(viewport, event):
    global _press
    _finish_drag()
    _press = None
    if event.button() == QtCore.Qt.MouseButton.LeftButton and _drag_allowed():
        _press = (viewport, _event_pos(event))
    return False


def _on_move(viewport, event):
    global _press
    if _drag is not None:
        if _drag.viewport is not viewport:
            return False
        if not _left_held(event) or not fcgui.jellyjams_active():
            _finish_drag()
            return False
        _drag_to(_event_pos(event))
        return True
    if _press is None or _press[0] is not viewport:
        return False
    if not _left_held(event):
        _press = None
        return False
    pos = _event_pos(event)
    if (pos - _press[1]).manhattanLength() < DRAG_THRESHOLD_PX:
        return False
    press_pos = _press[1]
    _press = None
    if not _start_drag(viewport, press_pos):
        return False
    _drag_to(pos)
    return True


def _on_release(viewport, event):
    global _press
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    _press = None
    if _drag is not None and _drag.viewport is viewport:
        _finish_drag()
        return True
    return False


def _open_editor(symbol):
    kind = _symbol_kind(symbol)
    try:
        if kind == constants.KIND_SURFACE:
            from jellyjams import surface_finish as editor
        elif kind == constants.KIND_WELD:
            from jellyjams import weld_symbol as editor
        else:
            return False
        return bool(editor.open_editor(symbol))
    except Exception:
        console.error("the editor for %s did not open" % getattr(symbol, "Label", "?"),
                      with_traceback=True)
        return False


def _on_double_click(viewport, event):
    global _press
    _press = None
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    if not _sheet_idle() or _pick_running():
        return False
    symbol = _selected_symbol()
    return _open_editor(symbol) if symbol is not None else False


_HANDLERS = {
    QtCore.QEvent.Type.MouseButtonPress: _on_press,
    QtCore.QEvent.Type.MouseMove: _on_move,
    QtCore.QEvent.Type.MouseButtonRelease: _on_release,
    QtCore.QEvent.Type.MouseButtonDblClick: _on_double_click,
}


class _SheetMouseFilter(QtCore.QObject):
    """Mouse filter for sheet viewports; on any internal error the event goes on unchanged."""

    def eventFilter(self, watched, event):
        global _press
        try:
            handler = _HANDLERS.get(event.type())
            return bool(handler(watched, event)) if handler is not None else False
        except Exception as exc:
            console.log("sheet mouse handling failed: %s" % exc)
            _press = None
            with console.guard("stop the view drag", level="log"):
                _finish_drag()
            return False


# --- public API --------------------------------------------------------------------------------


def attach(window):
    """Install the mouse filter on the viewport of `window` (default: active sheet); once each."""
    global _mouse_filter
    with console.guard("enable view dragging on the sheet window", level="log"):
        view = fcgui.sheet_graphics_view(window)
        viewport = view.viewport() if view is not None else None
        if not fcgui.is_alive(viewport) or viewport.property(_ATTACHED_MARK):
            return
        if _mouse_filter is None or not fcgui.is_alive(_mouse_filter):
            _mouse_filter = _SheetMouseFilter()
        viewport.installEventFilter(_mouse_filter)
        viewport.setProperty(_ATTACHED_MARK, True)


def is_dragging():
    return _drag is not None
