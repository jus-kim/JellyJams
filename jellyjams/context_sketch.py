# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Floating "Sketch" button shown beside a picked planar face.

A selection observer runs while JellyJams is active. If the user picks exactly
one flat face of a model (not inside an assembly, no task dialog open, and the
``ShowSketchButtonOnFace`` preference not switched off), a small borderless button pops
up above and to the right of the pointer. Moving the pointer away dims it until, at
HIDE_PX, it closes; a click on it runs ``PartDesign_NewSketch`` on that face.
"""

import math

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, constants, doc_utils, fcgui, params

NEW_SKETCH = "PartDesign_NewSketch"
TOOLTIP = "Sketch"
TEXT_FALLBACK = "Sketch"

# Top-left corner of the popup relative to the pointer, px (screen y grows downward).
# With the sizes below, the pointer starts about 40 px from the popup centre, inside
# the fully opaque zone, and the popup's lower edge stays a few pixels above the click.
OFFSET_X = 16
OFFSET_Y = -40
FULL_OPACITY_PX = 50.0   # fully opaque up to this pointer distance from the centre
HIDE_PX = 180.0          # closed from this distance on; linear fade in between
FADE_MS = 50             # opacity refresh interval while the popup is shown
BUTTON_PX = 30
ICON_PX = 22
MARGIN_PX = 3

_FALLBACK_COLORS = {"PANEL": "#ffffff", "BORDER": "#c9ced6",
                    "HOVER": "#e8f2fb", "PRESSED": "#cfe6f8"}

_listener = None
_enabled = False
_generation = 0      # bumped per selection event; queued checks for older events are skipped
_popup = None
_fade_timer = None


# --- pure helpers -------------------------------------------------------------------


def opacity_for_distance(d):
    """Opacity for a pointer `d` px from the button center, or None to hide it."""
    if d <= FULL_OPACITY_PX:
        return 1.0
    if d >= HIDE_PX:
        return None
    return 1.0 - (d - FULL_OPACITY_PX) / (HIDE_PX - FULL_OPACITY_PX)


def popup_position(x, y):
    """Global top-left position of the button for a click at (x, y)."""
    return (x + OFFSET_X, y + OFFSET_Y)


# --- selection evaluation -------------------------------------------------------------


def _resolve_object(doc_name, obj_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
        return doc.getObject(obj_name) if doc is not None else None
    except Exception:
        return None


def _is_assembly(obj):
    return (doc_utils.type_id(obj) == constants.TYPE_ASSEMBLY
            or doc_utils.is_derived(obj, constants.TYPE_ASSEMBLY))


def _in_assembly(obj):
    if _is_assembly(obj):
        return True
    return any(_is_assembly(parent) for parent in (obj.InListRecursive or ()))


def _is_planar(shape):
    shape_type = getattr(shape, "ShapeType", None)
    if shape_type is not None and shape_type != "Face":
        return False
    for method in ("isPlanar", "findPlane"):
        test = getattr(shape, method, None)
        if callable(test):
            try:
                result = test()
                return bool(result) if method == "isPlanar" else result is not None
            except Exception:
                pass
    try:
        surface = shape.Surface
        return (getattr(surface, "TypeId", "") == "Part::GeomPlane"
                or type(surface).__name__ == "Plane")
    except Exception:
        return False


def _selected_element_count():
    selection = fcgui.selection_ex("*", 0) or fcgui.selection_ex()
    total = 0
    for item in selection:
        names = getattr(item, "SubElementNames", None) or ()
        total += len(names) if names else 1
    return total


def _qualifies(doc_name, obj_name, sub_name):
    if not fcgui.jellyjams_active():
        return False
    if not params.get_bool(constants.PARAM_ROOT, constants.KEY_CONTEXT_SKETCH, True):
        return False
    if fcgui.task_dialog_open() or fcgui.active_sheet_window() is not None:
        return False
    obj = _resolve_object(doc_name, obj_name)
    if obj is None or not doc_utils.is_alive(obj):
        return False
    if doc_utils.type_id(obj).startswith("TechDraw::") or _in_assembly(obj):
        return False
    sub_name = sub_name or ""
    if not sub_name.split(".")[-1].startswith("Face"):
        return False
    shape = obj.getSubObject(sub_name)
    if shape is None or not _is_planar(shape):
        return False
    return _selected_element_count() == 1


def _evaluate(generation, doc_name, obj_name, sub_name, point):
    if not _enabled or generation != _generation:
        return
    try:
        qualifies = _qualifies(doc_name, obj_name, sub_name)
    except Exception as exc:
        console.log("Sketch context icon: selection check raised: %s" % exc)
        qualifies = False
    if qualifies:
        _show_at(point)
    else:
        _hide()


class _SelectionListener:
    """Selection observer behind the button (registered in NoResolve mode)."""

    def addSelection(self, doc_name, obj_name, sub_name, *args):
        global _generation
        try:
            _generation += 1
            generation = _generation
            cursor = QtGui.QCursor.pos()
            point = (cursor.x(), cursor.y())
            fcgui.defer(
                lambda: _evaluate(generation, doc_name, obj_name, sub_name, point), 0
            )
        except Exception as exc:
            console.log("Sketch context icon: selection event ignored: %s" % exc)

    def removeSelection(self, *args):
        _dismiss()

    def setSelection(self, *args):
        _dismiss()

    def clearSelection(self, *args):
        _dismiss()


def _dismiss():
    global _generation
    try:
        _generation += 1
        _hide()
    except Exception:
        pass


# --- popup -------------------------------------------------------------------------------


def _colors():
    colors = dict(_FALLBACK_COLORS)
    try:
        from jellyjams import theme

        palette = theme.widget_colors()

        for name in colors:
            colors[name] = getattr(palette, name, colors[name])
    except Exception:
        pass
    return colors


def _style_sheet():
    c = _colors()
    name = constants.OBJ_CONTEXT_TOOLBAR
    return (
        "QFrame#%(n)s { background-color: %(PANEL)s; border: 1px solid %(BORDER)s;"
        " border-radius: 4px; }\n"
        "QFrame#%(n)s QToolButton { background-color: transparent;"
        " border: 1px solid transparent; border-radius: 3px; padding: 0px; }\n"
        "QFrame#%(n)s QToolButton:hover { background-color: %(HOVER)s;"
        " border-color: %(BORDER)s; }\n"
        "QFrame#%(n)s QToolButton:pressed { background-color: %(PRESSED)s; }\n"
    ) % dict(c, n=name)


class _ContextPopup(QtWidgets.QFrame):
    """Borderless tool window that carries the one Sketch button."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            | QtCore.Qt.WindowType.NoDropShadowWindowHint
        )
        self.setObjectName(constants.OBJ_CONTEXT_TOOLBAR)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(MARGIN_PX, MARGIN_PX, MARGIN_PX, MARGIN_PX)
        layout.setSpacing(0)

        self.button = QtWidgets.QToolButton(self)
        self.button.setObjectName(constants.OBJ_CONTEXT_TOOLBAR + "Button")
        self.button.setFixedSize(BUTTON_PX, BUTTON_PX)
        self.button.setIconSize(QtCore.QSize(ICON_PX, ICON_PX))
        self.button.setAutoRaise(True)
        self.button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.button.setToolTip(TOOLTIP)
        self.button.clicked.connect(_on_clicked)
        layout.addWidget(self.button)

        self.has_icon = False
        self.setStyleSheet(_style_sheet())
        self.adjustSize()

    def refresh_icon(self):
        if self.has_icon:
            return
        icon = None
        try:
            from jellyjams import icons

            icon = icons.command_icon(NEW_SKETCH)
        except Exception as exc:
            console.log("Sketch context icon: %s icon not found, showing text (%s)"
                        % (NEW_SKETCH, exc))
        if icon is not None and not icon.isNull():
            self.button.setIcon(icon)
            self.button.setText("")
            self.button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.has_icon = True
        else:
            self.button.setText(TEXT_FALLBACK)
            self.button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)


def _ensure_popup():
    global _popup
    main = fcgui.main_window()
    if main is None:
        return None
    if _popup is not None and fcgui.is_alive(_popup) and _popup.parentWidget() is main:
        _popup.setStyleSheet(_style_sheet())
        return _popup
    _discard_popup()
    _popup = _ContextPopup(main)
    return _popup


def _discard_popup():
    global _popup
    popup, _popup = _popup, None
    if popup is not None and fcgui.is_alive(popup):
        try:
            popup.hide()
            popup.deleteLater()
        except Exception:
            pass


def _show_at(point):
    popup = _ensure_popup()
    if popup is None:
        return
    popup.refresh_icon()
    x, y = popup_position(point[0], point[1])
    popup.move(int(x), int(y))
    popup.setWindowOpacity(1.0)
    popup.show()
    popup.raise_()
    _start_fade()


def _hide():
    _stop_fade()
    popup = _popup
    if popup is not None and fcgui.is_alive(popup) and popup.isVisible():
        popup.hide()


def _start_fade():
    global _fade_timer
    if _fade_timer is None or not fcgui.is_alive(_fade_timer):
        _fade_timer = QtCore.QTimer()
        _fade_timer.setInterval(FADE_MS)
        _fade_timer.timeout.connect(_fade_tick)
    _fade_timer.start()


def _stop_fade():
    if _fade_timer is not None and fcgui.is_alive(_fade_timer):
        _fade_timer.stop()


def _fade_tick():
    try:
        popup = _popup
        if popup is None or not fcgui.is_alive(popup) or not popup.isVisible():
            _stop_fade()
            return
        if fcgui.task_dialog_open() or not fcgui.jellyjams_active():
            _hide()
            return
        cursor = QtGui.QCursor.pos()
        center = popup.frameGeometry().center()
        distance = math.hypot(cursor.x() - center.x(), cursor.y() - center.y())
        opacity = opacity_for_distance(distance)
        if opacity is None:
            _hide()
        else:
            popup.setWindowOpacity(opacity)
    except Exception as exc:
        console.log("Sketch context icon: fade update raised: %s" % exc)
        _hide()


def _on_clicked():
    try:
        _hide()
    except Exception:
        pass
    try:
        fcgui.gui().runCommand(NEW_SKETCH)
    except Exception as exc:
        console.error("no sketch was created on the selected face: %s" % exc)


# --- lifecycle ------------------------------------------------------------------------------


def _resolve_mode(selection):
    mode = getattr(selection, "ResolveMode", None)
    return getattr(mode, "NoResolve", 0) if mode is not None else 0


def enable():
    """Register the selection observer once; repeated calls change nothing."""
    global _listener, _enabled
    if _enabled:
        return
    try:
        selection = fcgui.gui().Selection
        listener = _SelectionListener()
        try:
            selection.addObserver(listener, _resolve_mode(selection))
        except TypeError:
            selection.addObserver(listener)
    except Exception as exc:
        console.warning(
            "Sketch context icon is not available: the selection observer could not "
            "be registered (%s)" % exc
        )
        return
    _listener = listener
    _enabled = True


def disable():
    """Unregister the observer and hide the button; harmless if never enabled."""
    global _listener, _enabled, _generation
    _enabled = False
    _generation += 1
    listener, _listener = _listener, None
    if listener is not None:
        try:
            fcgui.gui().Selection.removeObserver(listener)
        except Exception:
            pass
    try:
        _hide()
    except Exception:
        pass


def is_enabled():
    return _enabled
