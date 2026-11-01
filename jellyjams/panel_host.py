# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Shared hosting and widgets for the Add Relations and Add Mate panels.

``PanelHost`` keeps one panel frame at the top of FreeCAD's task panel
(``Gui::TaskView::TaskPanel``) or, when that is missing, in an optional dock of
its own. FreeCAD can delete the task panel, and the frame inside it, whenever
it likes, so every access checks that the widgets still exist and rebuilds them
with the caller's factory when they do not.
"""

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui

ROW_LIMITS = (1, 6)
MIN_ROW_HEIGHT = 18
LIST_PADDING = 4
BUTTON_ICON_SIZE = 16


def _panel_layout():
    panel = fcgui.task_panel()
    if not fcgui.is_alive(panel):
        return None
    layout = panel.layout()
    return layout if fcgui.is_alive(layout) else None


def _place_first(layout, frame):
    index = layout.indexOf(frame)
    if index == 0:
        return
    if index > 0:
        layout.removeWidget(frame)
    layout.insertWidget(0, frame)


class PanelHost:
    """Tracks one panel frame and its optional fallback dock."""

    def __init__(self, fallback_dock_name=None, fallback_title=None):
        self._fallback_name = fallback_dock_name or None
        self._fallback_title = fallback_title or ""
        self._frame = None
        self._dock = None

    def frame(self):
        """Return the frame if it still exists, else None."""
        if not fcgui.is_alive(self._frame):
            self._frame = None
        return self._frame

    def dock(self):
        """Return the fallback dock if it still exists, else None."""
        if not fcgui.is_alive(self._dock):
            self._dock = None
        return self._dock

    def is_shown(self):
        frame = self.frame()
        return frame is not None and not frame.isHidden()

    def in_dock(self):
        frame, dock = self.frame(), self.dock()
        return frame is not None and dock is not None and dock.widget() is frame

    def ensure(self, factory):
        """Return a live frame placed at the top of the task panel, else in the fallback dock.

        ``factory()`` is called when no frame exists yet. Returns None when
        neither host is available.
        """
        layout = _panel_layout()
        if layout is not None:
            return self._ensure_in_panel(layout, factory)
        if self._fallback_name:
            return self._ensure_in_dock(factory)
        return None

    def show(self):
        """Make the frame visible and raise whichever dock holds it."""
        frame = self.frame()
        if frame is None:
            return
        frame.show()
        dock = self.dock()
        if dock is not None and dock.widget() is frame:
            dock.show()
            dock.raise_()
            return
        tasks = fcgui.task_dock()
        if fcgui.is_alive(tasks):
            tasks.raise_()

    def hide(self):
        """Hide the frame and the fallback dock, keeping the frame for later."""
        frame = self.frame()
        if frame is not None:
            frame.hide()
        dock = self.dock()
        if dock is not None:
            dock.hide()

    def _new_frame(self, factory):
        frame = factory()
        self._frame = frame if fcgui.is_alive(frame) else None
        return self._frame

    def _ensure_in_panel(self, layout, factory):
        frame = self.frame() or self._new_frame(factory)
        if frame is None:
            return None
        dock = self.dock()
        if dock is not None:
            if dock.widget() is frame:
                dock.setWidget(None)
            dock.hide()
        _place_first(layout, frame)
        return frame

    def _ensure_in_dock(self, factory):
        dock = self._ensure_dock()
        if dock is None:
            return None
        frame = self.frame() or self._new_frame(factory)
        if frame is None:
            return None
        if dock.widget() is not frame:
            dock.setWidget(frame)
        return frame

    def _ensure_dock(self):
        dock = self.dock()
        if dock is not None:
            return dock
        window = fcgui.main_window()
        if not fcgui.is_alive(window):
            return None
        dock = window.findChild(QtWidgets.QDockWidget, self._fallback_name)
        if not fcgui.is_alive(dock):
            dock = QtWidgets.QDockWidget(self._fallback_title, window)
            dock.setObjectName(self._fallback_name)
            window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
            dock.hide()
        self._dock = dock
        return dock


class PanelFrame(QtWidgets.QFrame):
    """Frame whose objectNames match the JellyJams theme's panel rules."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName(constants.OBJ_PANEL)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.title = self._add_label(title, constants.OBJ_PANEL_TITLE)

    def _add_label(self, text, object_name=None):
        label = QtWidgets.QLabel(text, self)
        if object_name:
            label.setObjectName(object_name)
        self.layout().addWidget(label)
        return label

    def add_heading(self, text):
        return self._add_label(text, constants.OBJ_PANEL_HEADING)

    def add_list(self, multi_select=False):
        widget = QtWidgets.QListWidget(self)
        widget.setObjectName(constants.OBJ_PANEL_LIST)
        widget.setUniformItemSizes(True)
        widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if multi_select:
            widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.layout().addWidget(widget)
        fit_list_height(widget)
        return widget

    def add_button_column(self):
        column = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.layout().addWidget(column)
        return column

    def add_hint(self, text=""):
        label = self._add_label(text)
        label.setWordWrap(True)
        label.hide()
        return label


def fit_list_height(widget):
    """Size the list to its rows (kept within ROW_LIMITS) plus frame and padding."""
    count = widget.count()
    rows = max(ROW_LIMITS[0], min(ROW_LIMITS[1], count))
    row_height = max(MIN_ROW_HEIGHT, widget.fontMetrics().height() + 2)
    if count:
        row_height = max(row_height, widget.sizeHintForRow(0))
    widget.setFixedHeight(rows * row_height + 2 * widget.frameWidth() + LIST_PADDING)


def fill_list(widget, rows):
    """Fill the list with (text, data) rows and resize it."""
    widget.clear()
    for text, data in rows:
        item = QtWidgets.QListWidgetItem(text)
        item.setToolTip(text)
        if data is not None:
            item.setData(QtCore.Qt.ItemDataRole.UserRole, data)
        widget.addItem(item)
    fit_list_height(widget)


def rebuild_buttons(column, entries):
    """Recreate the column's buttons: one flat tool button per (label, icon, tooltip, slot)."""
    layout = column.layout()
    while layout.count():
        old = layout.takeAt(0).widget()
        if old is not None:
            old.hide()
            old.deleteLater()
    for label, icon, tooltip, slot in entries:
        button = QtWidgets.QToolButton(column)
        button.setText(label)
        button.setToolTip(tooltip or label)
        button.setAutoRaise(True)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                             QtWidgets.QSizePolicy.Policy.Fixed)
        button.setIconSize(QtCore.QSize(BUTTON_ICON_SIZE, BUTTON_ICON_SIZE))
        if icon is not None:
            button.setIcon(icon)
        button.clicked.connect(slot)
        layout.addWidget(button)
        button.setVisible(True)
    column.setVisible(bool(entries))


def command_tooltip(cmd_id, fallback):
    """Return the command's FreeCAD tooltip, or ``fallback`` when it has none."""
    info = fcgui.command_info(cmd_id)
    text = info.get("toolTip") if isinstance(info, dict) else None
    text = str(text or "").strip()
    return text or fallback


def _usable(icon):
    try:
        return icon is not None and not icon.isNull()
    except Exception:
        return False


def freecad_icon(cmd_id):
    """The command's FreeCAD icon, looked up as the ribbon does, or None."""
    try:
        from jellyjams import icons
        icon = icons.command_icon(cmd_id)
    except Exception:
        return None
    return icon if _usable(icon) else None


def jj_icon(base):
    """Load a JellyJams icon from resources/icons, or None."""
    try:
        from jellyjams import icons
        icon = icons.jj_icon(base)
    except Exception:
        return None
    return icon if _usable(icon) else None


def same_object(a, b):
    """True if both refer to the same document object (matched by document and name)."""
    if a is None or b is None:
        return False
    if a is b:
        return True
    try:
        return a.Name == b.Name and a.Document.Name == b.Document.Name
    except Exception:
        return False


class SelectionRelay:
    """Selection observer that calls one callback for every kind of change."""

    def __init__(self, callback):
        self._callback = callback

    def _notify(self):
        try:
            self._callback()
        except Exception as exc:
            console.log("panel selection callback raised: %s" % exc)

    def addSelection(self, *_args):
        self._notify()

    def removeSelection(self, *_args):
        self._notify()

    def setSelection(self, *_args):
        self._notify()

    def clearSelection(self, *_args):
        self._notify()


class RefreshScheduler:
    """Merges a burst of refresh requests into one call on the next event-loop pass."""

    def __init__(self, callback):
        self._callback = callback
        self._pending = False

    @property
    def pending(self):
        return self._pending

    def schedule(self):
        if self._pending:
            return
        self._pending = True
        try:
            QtCore.QTimer.singleShot(0, self._run)
        except Exception:
            self._pending = False
            raise

    def _run(self):
        self._pending = False
        try:
            self._callback()
        except Exception as exc:
            console.log("queued panel refresh raised: %s" % exc)
