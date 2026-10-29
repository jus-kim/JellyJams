# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""The Orientation panel that Space opens, and Normal To (Ctrl+8), as in SolidWorks.

A small floating panel appears at the pointer with Normal To, saved views and
the standard views laid out around Front (Top above, Bottom below, Left / Right
/ Back beside), plus Isometric, Trimetric and Dimetric. Clicking a view applies
it and closes the panel unless it is pinned. Esc, Space, the close button,
clicking a view (unpinned) or clicking anywhere outside the panel (unpinned)
closes it.

Both commands only change the camera, so they are declared as 3D-view commands:
FreeCAD then keeps them available while a sketch or a task dialog is open.
Space is a window-wide shortcut, so a filter decides who gets it: with the pointer
over a 3D view or the model tree it opens the panel; elsewhere a focused button,
check box, combo box or checkable list keeps it, as in any dialog.
"""

import time

from jellyjams import commands, console, constants, fcgui

OBJ_PANEL = "JellyJamsOrientation"
CMD_TYPE_VIEW = "Alter3DView"

# (row, column, FreeCAD command, label): the unfolded-box arrangement around Front.
VIEW_GRID = (
    (0, 1, "Std_ViewTop", "Top"),
    (1, 0, "Std_ViewLeft", "Left"),
    (1, 1, "Std_ViewFront", "Front"),
    (1, 2, "Std_ViewRight", "Right"),
    (1, 3, "Std_ViewRear", "Back"),
    (2, 1, "Std_ViewBottom", "Bottom"),
)
AXONOMETRIC = (
    ("Std_ViewIsometric", "Isometric"),
    ("Std_ViewTrimetric", "Trimetric"),
    ("Std_ViewDimetric", "Dimetric"),
)
TOOLS = (
    (constants.CMD_NORMAL_TO, "Normal To"),
    ("Std_ViewSaveCamera", "Remember this view"),
    ("Std_ViewRestoreCamera", "Go back to the remembered view"),
    ("Std_ViewFitAll", "Zoom to Fit"),
)
# FreeCAD 1.1 ships no icon for these two commands.
FALLBACK_ICONS = {"Std_ViewSaveCamera": "view_save", "Std_ViewRestoreCamera": "view_restore"}
BUTTON_PX = 30
CURSOR_OFFSET_PX = 12
# A deactivation this soon after opening is the opening itself settling (a menu closing,
# for example), not a click elsewhere.
OPEN_SETTLE_S = 0.3

ALIGN_COMMAND = "Std_AlignToSelection"
SKETCH_VIEW_COMMAND = "Sketcher_ViewSketch"
SKETCH_TYPES = ("Part::Part2DObject",)
# Whole objects FreeCAD's Align to Selection handles itself.
DATUM_TYPES = ("App::Plane", "App::Line", "Part::Datum")
NORMAL_TO_HINT = "Normal To: select one face, edge, plane or sketch first."
HINT_MS = 4000
TOOLTIP_DELAY_MS = 150

MODEL_TREE_CLASS = "Gui::TreeWidget"
# With the pointer over one of these, Space opens the panel whatever has the keyboard.
SPACE_FOR_PANEL_CLASSES = (constants.CLASS_VIEW3D, "Gui::View3DInventorViewer",
                           "Gui::AbstractSplitView", MODEL_TREE_CLASS)
PARENT_WALK_LIMIT = 40

_panel = None
_return_to = None         # the window that had the keyboard before the panel opened
_space_filter = None
_filtered = []            # widgets the Space filter is installed on
_generation = 0           # counts openings, so a late check never closes a newer opening
_opened_at = 0.0
_seen_active = False      # the panel has had the keyboard since it last opened


class OrientationCommand(commands.BaseCommand):
    command_id = constants.CMD_ORIENTATION
    menu_text = "View Orientation"
    tooltip = "Open the Orientation panel at the pointer: standard views, Normal To and saved views (Space)."
    cmd_type = CMD_TYPE_VIEW

    def run(self):
        toggle()

    def is_active(self):
        return view3d_active()


class NormalToCommand(commands.BaseCommand):
    command_id = constants.CMD_NORMAL_TO
    menu_text = "Normal To"
    tooltip = ("Look straight at the selected face, edge, plane or sketch; in a sketch with "
               "nothing selected, at the sketch plane (Ctrl+8).")
    cmd_type = CMD_TYPE_VIEW

    def run(self):
        normal_to()

    def is_active(self):
        return view3d_active()


def get_commands():
    return {
        constants.CMD_ORIENTATION: OrientationCommand(),
        constants.CMD_NORMAL_TO: NormalToCommand(),
    }


def _active_view():
    """The view FreeCAD's own view commands act on, or None.

    That is the main window's active window, which follows undocked and fullscreen views and
    is the Start page or a drawing when one of those is in front. FreeCADGui.activeView() is
    only the fallback: it answers with the document's last 3D view even while a page without
    a camera is in front.
    """
    getter = getattr(fcgui.main_window(), "getActiveWindow", None)
    try:
        if getter is not None:
            return getter()
        return fcgui.gui().activeView()
    except Exception:
        return None


def view3d_active():
    """True while the view in front is a 3D view, docked, undocked or fullscreen."""
    view = _active_view()
    return view is not None and hasattr(view, "getCameraNode")


# --- Normal To ---------------------------------------------------------------------------


def _picks_inside(sketch, picked):
    try:
        key = (sketch.Document.Name, sketch.Name)
        return all((item.DocumentName, item.ObjectName) == key for item in picked)
    except Exception:
        return False


def _picks(items):
    """(selection item, sub-element name or "") for every pick in a getSelectionEx list."""
    found = []
    for item in items:
        subs = [s for s in (getattr(item, "SubElementNames", None) or ()) if s]
        if subs:
            found.extend((item, sub) for sub in subs)
        else:
            found.append((item, ""))
    return found


def _single_pick(picked):
    """The one pick when exactly one thing is selected, else None.

    Counted along the selection paths as well: the same object picked through two links is
    one entry once resolved, but two places on screen.
    """
    found = _picks(picked)
    paths = _picks(fcgui.selection_ex("", 0))
    if len(found) != 1 or len(paths) > 1:
        return None
    return found[0]


def _derived(obj, type_ids):
    try:
        return any(obj.isDerivedFrom(type_id) for type_id in type_ids)
    except Exception:
        return False


def _single_face_or_edge(obj):
    """True when a whole object's shape is one face or one edge, which FreeCAD can align to."""
    try:
        shape = obj.Shape
        if shape.isNull() or shape.Solids:
            return False
        return len(shape.Faces) == 1 or (not shape.Faces and len(shape.Edges) == 1)
    except Exception:
        return False


def normal_to_target():
    """What Normal To does right now, or None when there is nothing it could look at.

    ("command", id) runs a FreeCAD command; ("sketch", object) looks straight at a whole
    sketch, which FreeCAD's Align to Selection cannot do. In a sketch with nothing selected,
    or only the sketch's own geometry, that is the view of the sketch plane. Otherwise exactly
    one pick is needed: a face or edge (FreeCAD decides whether it can align to it), a sketch,
    a datum plane, line or axis, or an object that is a single face or edge.
    """
    picked = fcgui.selection_ex()
    sketch = fcgui.sketch_in_edit()
    if sketch is not None and (not picked or _picks_inside(sketch, picked)):
        return ("command", SKETCH_VIEW_COMMAND)
    pick = _single_pick(picked)
    if pick is None:
        return None
    item, sub = pick
    if sub:
        return ("command", ALIGN_COMMAND)
    obj = getattr(item, "Object", None)
    if obj is None:
        return None
    if _derived(obj, SKETCH_TYPES):
        return ("sketch", obj)
    if _derived(obj, DATUM_TYPES) or _single_face_or_edge(obj):
        return ("command", ALIGN_COMMAND)
    return None


def _sketch_rotation(obj):
    """The sketch's rotation where it is shown: along the selection path, so a sketch reached
    through a link or an assembly component is looked at in place."""
    try:
        import FreeCAD

        unresolved = fcgui.selection_ex("", 0)
        if len(unresolved) == 1:
            item = unresolved[0]
            subs = [s for s in (item.SubElementNames or ()) if s]
            if len(subs) <= 1:
                path = subs[0] if subs else ""
                return FreeCAD.GeoFeature.getGlobalPlacementOf(obj, item.Object, path).Rotation
    except Exception as exc:
        console.log("Normal To used the sketch's own placement: %s" % exc)
    return obj.getGlobalPlacement().Rotation


def _look_at_sketch(obj):
    try:
        _active_view().setCameraOrientation(_sketch_rotation(obj).Q)
        return True
    except Exception as exc:
        console.warning("Normal To could not turn the view to %s: %s" % (getattr(obj, "Label", obj), exc))
        return False


def _show_tooltip():
    _QtCore, QtGui, QtWidgets = fcgui.qt()
    QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), NORMAL_TO_HINT)


def _show_hint():
    """The hint in the status bar now and next to the pointer shortly after: Qt hides a
    tooltip on any window activation, and the panel closing hands the keyboard back first."""
    fcgui.status_message(NORMAL_TO_HINT, HINT_MS)
    fcgui.defer(_show_tooltip, TOOLTIP_DELAY_MS)


def normal_to():
    """Run Normal To. With nothing to look at, say so next to the pointer and in the status
    bar, and return False."""
    target = normal_to_target()
    if target is None:
        _show_hint()
        return False
    kind, value = target
    if kind == "sketch":
        return _look_at_sketch(value)
    return fcgui.run_command(value)


# --- the panel -----------------------------------------------------------------------------


def is_open():
    try:
        return _panel is not None and _panel.isVisible()
    except Exception:
        return False


def toggle():
    """Open the panel at the pointer, or close it when it is already open."""
    _stop_auto_repeat()
    if is_open():
        close()
    else:
        open_at_cursor()


def close():
    """Hide the panel. Never raises.

    The keyboard goes back only when the panel had it, so closing after the user clicked into
    another program does not pull FreeCAD to the front. It goes to the window that had it
    before the panel opened (an undocked or fullscreen 3D view, for example), else to the
    main window.
    """
    try:
        if _panel is not None and _panel.isVisible():
            had_focus = _panel.isActiveWindow()
            _panel.hide()
            if had_focus:
                window = _return_to
                if not (fcgui.is_alive(window) and window.isVisible()):
                    window = fcgui.main_window()
                if window is not None:
                    window.activateWindow()
    except Exception as exc:
        console.log("closing the Orientation panel: %s" % exc)


def open_at_cursor():
    global _panel, _generation, _opened_at, _seen_active, _return_to
    QtCore, QtGui, QtWidgets = fcgui.qt()
    if _panel is None or not fcgui.is_alive(_panel):
        _panel = _build(QtCore, QtGui, QtWidgets)
    active = QtWidgets.QApplication.activeWindow()
    _return_to = active if active is not _panel else None
    _generation += 1
    _opened_at = time.monotonic()
    _seen_active = False
    _refresh_buttons()
    _panel.adjustSize()
    _panel.move(_placement(QtCore, QtGui, _panel.sizeHint()))
    _panel.show()
    _panel.raise_()
    _panel.activateWindow()
    _panel.setFocus()


def _pinned():
    try:
        return bool(_panel is not None and _panel.pin_button.isChecked())
    except Exception:
        return False


def _activation_changed(active):
    """Panel activation changed: remember the panel had the keyboard, or schedule the
    click-elsewhere check for this opening."""
    global _seen_active
    if active:
        _seen_active = True
        return
    if is_open():
        generation = _generation
        fcgui.defer(lambda: _close_if_left(generation))


def _close_if_left(generation):
    """Close the unpinned panel once another window has taken the keyboard from it.

    The FreeCAD window that took it is remembered first, so a pinned panel later hands the
    keyboard back to the window the user was last in.
    """
    global _return_to
    try:
        if generation != _generation or not is_open() or not _seen_active:
            return
        if _panel.isActiveWindow():
            return
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        taker = QtWidgets.QApplication.activeWindow()
        if taker is not None and taker is not _panel and fcgui.is_alive(taker):
            _return_to = taker
        if _pinned():
            return
        if taker is not None and time.monotonic() - _opened_at < OPEN_SETTLE_S:
            # Still opening within FreeCAD: take the keyboard back, so Esc works and the
            # next click elsewhere is noticed. Another program in front simply closes it.
            _panel.activateWindow()
            return
        close()
    except Exception as exc:
        console.log("closing the Orientation panel after a click elsewhere: %s" % exc)


def _command_usable(cmd_id):
    if not fcgui.command_exists(cmd_id):
        return False
    try:
        return bool(fcgui.gui().Command.get(cmd_id).isActive())
    except Exception:
        return True


def _refresh_buttons():
    """Enable each button only when FreeCAD can run its command in the current view."""
    try:
        for button in getattr(_panel, "view_buttons", {}).values():
            cmd_id = button.property("jellyjams_command")
            usable = True if cmd_id == constants.CMD_NORMAL_TO else _command_usable(cmd_id)
            button.setEnabled(bool(usable) and fcgui.command_exists(cmd_id))
    except Exception as exc:
        console.log("updating the Orientation panel buttons: %s" % exc)


def _placement(QtCore, QtGui, size):
    pos = QtGui.QCursor.pos() + QtCore.QPoint(CURSOR_OFFSET_PX, CURSOR_OFFSET_PX)
    screen = QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos()) or QtGui.QGuiApplication.primaryScreen()
    area = screen.availableGeometry()
    x = min(max(pos.x(), area.left()), area.right() - size.width())
    y = min(max(pos.y(), area.top()), area.bottom() - size.height())
    return QtCore.QPoint(x, y)


def _style():
    """The panel's own colors for every state, so the user's FreeCAD theme cannot leave
    light text on its light background."""
    from jellyjams import palette

    return (
        "#%(obj)s { background: %(panel)s; border: 1px solid %(border)s; }"
        "#%(obj)s QLabel { color: %(text)s; background: transparent; }"
        "#%(obj)s QLabel#title { font-weight: 600; padding: 2px 4px; }"
        "#%(obj)s QToolButton { color: %(text)s; background: transparent;"
        " border: 1px solid transparent; border-radius: 3px; padding: 2px; }"
        "#%(obj)s QToolButton:hover { color: %(text)s; background: %(hover)s; border-color: %(border)s; }"
        "#%(obj)s QToolButton:pressed, #%(obj)s QToolButton:checked"
        " { color: %(text)s; background: %(pressed)s; border-color: %(border)s; }"
        "#%(obj)s QToolButton:focus { border-color: %(accent)s; }"
        "#%(obj)s QToolButton:disabled { color: %(disabled)s; background: transparent; }"
        "#%(obj)s QFrame#rule { background: %(border)s; border: none; max-height: 1px; }"
    ) % {"obj": OBJ_PANEL, "panel": palette.PANEL, "border": palette.BORDER, "text": palette.TEXT,
         "hover": palette.HOVER, "pressed": palette.PRESSED, "accent": palette.ACCENT,
         "disabled": palette.TEXT_DISABLED}


def _shortcut_suffix(cmd_id):
    try:
        keys = fcgui.gui().Command.get(cmd_id).getShortcut()
        return " (%s)" % keys if keys else ""
    except Exception:
        return ""


# --- who gets Space ------------------------------------------------------------------------


def _class_name(widget):
    try:
        return widget.metaObject().className()
    except Exception:
        return ""


def _within(widget, class_names=(), types=(), object_names=()):
    """True when `widget` or one of its parents matches a class name, Qt type or object name."""
    for _ in range(PARENT_WALK_LIMIT):
        if widget is None:
            return False
        if _class_name(widget) in class_names or (types and isinstance(widget, types)):
            return True
        try:
            if object_names and widget.objectName() in object_names:
                return True
            widget = widget.parentWidget()
        except Exception:
            return False
    return False


def _item_takes_space(view, QtCore, QtWidgets):
    """A list uses Space when its current item can be checked or edited by typing."""
    try:
        index = view.currentIndex()
        if index.isValid() and (index.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable):
            return True
        return bool(view.editTriggers() & QtWidgets.QAbstractItemView.EditTrigger.AnyKeyPressed)
    except Exception:
        return False


def keeps_space(widget, pointer=None):
    """True when the focused `widget` should get Space instead of the Orientation panel.

    `pointer` is the widget under the mouse pointer. Over a 3D view or the model tree Space is
    always for the panel, as in SolidWorks, so a check box clicked a moment ago cannot flip
    unnoticed. Elsewhere buttons, check boxes, combo boxes and checkable or type-to-edit lists
    keep it, except controls in toolbars, the status bar or the ribbon.
    """
    QtCore, _QtGui, QtWidgets = fcgui.qt()
    if widget is None or QtWidgets is None:
        return False
    try:
        if pointer is not None and _within(pointer, class_names=SPACE_FOR_PANEL_CLASSES):
            return False
        if _within(widget, types=(QtWidgets.QToolBar, QtWidgets.QStatusBar),
                   object_names=(constants.OBJ_RIBBON,)):
            return False
        if isinstance(widget, (QtWidgets.QAbstractButton, QtWidgets.QComboBox)):
            return True
        if isinstance(widget, QtWidgets.QAbstractItemView):
            if _class_name(widget) == MODEL_TREE_CLASS:
                return False
            return _item_takes_space(widget, QtCore, QtWidgets)
    except Exception:
        pass
    return False


def _is_plain_space(event, QtCore):
    try:
        return (event.key() == QtCore.Qt.Key.Key_Space
                and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier)
    except Exception:
        return False


def _hand_space_to_focus(event, use_pointer=True):
    """Accept a ShortcutOverride for Space when the focused widget keeps Space, so Qt delivers
    the key to that widget instead of the shortcut. Returns True if accepted."""
    QtCore, QtGui, QtWidgets = fcgui.qt()
    if QtCore is None or event.type() != QtCore.QEvent.Type.ShortcutOverride:
        return False
    if not _is_plain_space(event, QtCore):
        return False
    pointer = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos()) if use_pointer else None
    if not keeps_space(QtWidgets.QApplication.focusWidget(), pointer):
        return False
    event.accept()
    return True


def _build(QtCore, QtGui, QtWidgets):
    from jellyjams import icons

    class Panel(QtWidgets.QFrame):
        def event(self, event):
            # The panel opens beside the pointer, usually still over the 3D view; a view
            # button reached with Tab gets Space wherever the pointer is.
            if _hand_space_to_focus(event, use_pointer=False):
                return True
            return super().event(event)

        def keyPressEvent(self, event):
            if event.key() in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Space):
                if not event.isAutoRepeat():
                    close()
                event.accept()
                return
            super().keyPressEvent(event)

        def changeEvent(self, event):
            super().changeEvent(event)
            if event.type() == QtCore.QEvent.Type.ActivationChange:
                _activation_changed(self.isActiveWindow())

    flags = QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint
    panel = Panel(fcgui.main_window(), flags)
    panel.setObjectName(OBJ_PANEL)
    panel.setStyleSheet(_style())
    panel.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    outer = QtWidgets.QVBoxLayout(panel)
    outer.setContentsMargins(6, 4, 6, 6)
    outer.setSpacing(4)

    header = QtWidgets.QHBoxLayout()
    title = QtWidgets.QLabel("Orientation")
    title.setObjectName("title")
    header.addWidget(title)
    header.addStretch(1)
    pin = QtWidgets.QToolButton()
    pin.setCheckable(True)
    pin.setText("Pin")
    pin.setToolTip("Keep this panel open after choosing a view or clicking elsewhere")
    header.addWidget(pin)
    closer = QtWidgets.QToolButton()
    closer.setText("✕")
    closer.setToolTip("Close (Esc)")
    closer.clicked.connect(close)
    header.addWidget(closer)
    outer.addLayout(header)
    panel.pin_button = pin
    panel.view_buttons = {}

    def view_button(cmd_id, label):
        button = QtWidgets.QToolButton()
        icon = icons.command_icon(cmd_id)
        if icon.isNull() and cmd_id in FALLBACK_ICONS:
            icon = icons.jj_icon(FALLBACK_ICONS[cmd_id]) or icon
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(BUTTON_PX - 6, BUTTON_PX - 6))
        button.setFixedSize(BUTTON_PX, BUTTON_PX)
        button.setToolTip(label + _shortcut_suffix(cmd_id))
        button.setObjectName("JellyJamsOrientation_" + cmd_id)
        button.setProperty("jellyjams_command", cmd_id)
        button.setEnabled(fcgui.command_exists(cmd_id))
        button.clicked.connect(lambda checked=False, c=cmd_id: _choose(c))
        panel.view_buttons[cmd_id] = button
        return button

    tools = QtWidgets.QHBoxLayout()
    tools.setSpacing(2)
    for cmd_id, label in TOOLS:
        tools.addWidget(view_button(cmd_id, label))
    tools.addStretch(1)
    outer.addLayout(tools)

    rule = QtWidgets.QFrame()
    rule.setObjectName("rule")
    rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    outer.addWidget(rule)

    body = QtWidgets.QHBoxLayout()
    grid = QtWidgets.QGridLayout()
    grid.setSpacing(2)
    for row, column, cmd_id, label in VIEW_GRID:
        grid.addWidget(view_button(cmd_id, label), row, column)
    body.addLayout(grid)
    body.addSpacing(8)
    axo = QtWidgets.QVBoxLayout()
    axo.setSpacing(2)
    for cmd_id, label in AXONOMETRIC:
        axo.addWidget(view_button(cmd_id, label))
    axo.addStretch(1)
    body.addLayout(axo)
    outer.addLayout(body)
    return panel


def _choose(cmd_id):
    if not _pinned():
        close()
    fcgui.run_command(cmd_id)


# --- the Space key while JellyJams is active -------------------------------------------------


def _stop_auto_repeat():
    """Make a held Space open or close the panel once instead of flickering it."""
    try:
        from jellyjams import icons

        action = icons.command_action(constants.CMD_ORIENTATION)
        if action is not None and action.autoRepeat():
            action.setAutoRepeat(False)
    except Exception as exc:
        console.log("could not turn off key repeat for View Orientation: %s" % exc)


def _make_space_filter(QtCore, parent):
    class SpaceFilter(QtCore.QObject):
        def eventFilter(self, watched, event):
            try:
                return _hand_space_to_focus(event)
            except Exception:
                return False

    return SpaceFilter(parent)


def install():
    """Activation: stop Space from auto-repeating the panel and decide who gets Space.

    The filter sits on FreeCAD's main window and on each of its docks, since a dock that
    floats is a window of its own and its key events never reach the main window; docks made
    later get it when one of their widgets takes focus. Safe to repeat.
    """
    global _space_filter
    _stop_auto_repeat()
    window = fcgui.main_window()
    if window is None or (_space_filter is not None and fcgui.is_alive(_space_filter)):
        return
    QtCore, _QtGui, QtWidgets = fcgui.qt()
    _space_filter = _make_space_filter(QtCore, window)
    _filtered[:] = []
    _watch(window)
    try:
        for dock in window.findChildren(QtWidgets.QDockWidget):
            _watch(dock)
    except Exception as exc:
        console.log("the Space key filter covers the main window only: %s" % exc)
    try:
        QtWidgets.QApplication.instance().focusChanged.connect(_focus_changed)
    except Exception as exc:
        console.log("docks made later will not get the Space key filter: %s" % exc)


def _watch(widget):
    if fcgui.is_alive(widget) and widget not in _filtered:
        widget.installEventFilter(_space_filter)
        _filtered.append(widget)


def _focus_changed(_old, new):
    """Docks made after activation get the filter when one of their widgets takes focus."""
    try:
        if _space_filter is None or new is None:
            return
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        widget = new
        for _ in range(PARENT_WALK_LIMIT):
            if widget is None:
                return
            if isinstance(widget, QtWidgets.QDockWidget):
                _watch(widget)
                return
            widget = widget.parentWidget()
    except Exception as exc:
        console.log("adding the Space key filter to a new dock: %s" % exc)


def uninstall():
    """Deactivation: close the panel and remove the Space filter. Never raises."""
    global _space_filter
    close()
    space_filter, _space_filter = _space_filter, None
    targets, _filtered[:] = list(_filtered), []
    if space_filter is None:
        return
    try:
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        QtWidgets.QApplication.instance().focusChanged.disconnect(_focus_changed)
    except Exception:
        pass
    try:
        if fcgui.is_alive(space_filter):
            for target in targets:
                if fcgui.is_alive(target):
                    target.removeEventFilter(space_filter)
            space_filter.deleteLater()
    except Exception as exc:
        console.log("removing the Space key filter: %s" % exc)
