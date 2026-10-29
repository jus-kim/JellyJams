# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Qt side of the ribbon: the dock widget, one page per tab and three button kinds.

RibbonUI draws a ribbon_model.Resolved. Clicks are handed to the
`dispatch(cmd_id, index)` callable passed in; nothing here runs a command
directly.
"""

import functools

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui, params
from jellyjams import icons, ribbon_text
from jellyjams.ribbon_layout import STYLE_ICON
from jellyjams.ribbon_model import RButton, RFlyout, RStack, RToggle, object_name

DOCK_TITLE = "JellyJams Ribbon"
LARGE_ICON_PX = 32
SMALL_ICON_PX = 20
STACK_ROWS = 3
PAGE_MARGINS = (4, 2, 4, 2)
PAGE_SPACING = 2
STACK_SPACING = 1

MODE_LARGE = "large"
MODE_ICON = "icon"
MODE_TEXT = "text"

_Qt = QtCore.Qt


def command_is_active(cmd_id):
    """Whether FreeCAD reports the command as usable now; True if it cannot say."""
    gui = fcgui.gui()
    if gui is None:
        return True
    try:
        command = gui.Command.get(cmd_id)
        return True if command is None else bool(command.isActive())
    except Exception:
        return True


def command_texts(cmd_id, index=None):
    """FreeCAD's (menu text, tooltip) for a command, or for sub-entry `index` of a group."""
    info = fcgui.command_info(cmd_id) or {}
    menu_text = str(info.get("menuText") or "")
    tool_tip = str(info.get("toolTip") or "")
    if index is not None:
        action = icons.command_action(cmd_id, index)
        if action is not None:
            try:
                text, tip = action.text(), action.toolTip()
            except Exception:
                text, tip = "", ""
            if text:
                return text, tip
    return menu_text, tool_tip


class _Facts:
    """Icon and texts of one command, read from FreeCAD once while building."""

    def __init__(self, button):
        self.button = button
        self.icon = icons.command_icon(button.cmd, button.index, button.jj_icon, button.fc_icon)
        self.menu_text, self.tool_tip = command_texts(button.cmd, button.index)


def _new_tool_button(mode):
    button = QtWidgets.QToolButton()
    button.setAutoRaise(True)
    if mode == MODE_LARGE:
        button.setIconSize(QtCore.QSize(LARGE_ICON_PX, LARGE_ICON_PX))
        button.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    else:
        button.setIconSize(QtCore.QSize(SMALL_ICON_PX, SMALL_ICON_PX))
        if mode == MODE_TEXT:
            button.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                 QtWidgets.QSizePolicy.Policy.Fixed)
        else:
            button.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonIconOnly)
    return button


def _show_face(button, mode, icon, caption):
    """Set icon and caption; only large buttons keep the caption's line breaks."""
    button.setIcon(icon)
    text = caption if mode == MODE_LARGE else ribbon_text.one_line(caption)
    button.setText(ribbon_text.mnemonic_safe(text))
    if mode == MODE_ICON:
        # Without an icon this button would be empty, so fall back to its text.
        style = (_Qt.ToolButtonStyle.ToolButtonTextOnly if icon.isNull()
                 else _Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setToolButtonStyle(style)


def _set_enabled(widget, enabled):
    if widget.isEnabled() != enabled:
        widget.setEnabled(enabled)


class PlainButton:
    """Runs a single command when clicked."""

    def __init__(self, entry, mode, dispatch):
        self.entry = entry
        self.mode = mode
        self._dispatch = dispatch
        self.facts = _Facts(entry)
        self.widget = _new_tool_button(mode)
        self.widget.setObjectName(object_name(constants.OBJ_BTN_PREFIX, entry.entry_id))
        _show_face(self.widget, mode, self.facts.icon, entry.label)
        self.widget.setToolTip(ribbon_text.button_tooltip(
            entry.label, entry.cmd, self.facts.menu_text, self.facts.tool_tip,
            indexed=entry.index is not None, icon_only=mode == MODE_ICON))
        self.widget.clicked.connect(self._on_clicked)

    def _on_clicked(self, *_args):
        self._dispatch(self.entry.cmd, self.entry.index)

    def refresh(self, sketch_editing):
        _set_enabled(self.widget, command_is_active(self.entry.cmd))


class FlyoutButton:
    """Split button: clicking runs the current variant, the arrow menu offers all of them."""

    def __init__(self, flyout, mode, dispatch):
        self.flyout = flyout
        self.mode = mode
        self._dispatch = dispatch
        self.facts = [_Facts(variant) for variant in flyout.variants]
        self.widget = _new_tool_button(mode)
        self.widget.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menu = QtWidgets.QMenu(self.widget)
        for position, (variant, facts) in enumerate(zip(flyout.variants, self.facts)):
            action = self.menu.addAction(facts.icon, ribbon_text.mnemonic_safe(variant.one_line))
            action.triggered.connect(functools.partial(self._on_chosen, position))
        self.widget.setMenu(self.menu)
        self.widget.clicked.connect(self._on_clicked)
        self.current = self._remembered_position()
        self._show_current()

    @property
    def variant(self):
        return self.flyout.variants[self.current]

    def variant_ids(self):
        return [variant.entry_id for variant in self.flyout.variants]

    def _remembered_position(self):
        stored = params.get_string(constants.PARAM_RIBBON, self.flyout.flyout_id, "")
        ids = self.variant_ids()
        return ids.index(stored) if stored in ids else 0

    def _remember(self):
        try:
            group = params.group(constants.PARAM_RIBBON)
            params.set_value(group, "String", self.flyout.flyout_id, self.variant.entry_id)
        except Exception:
            pass

    def _show_current(self):
        variant, facts, title = self.variant, self.facts[self.current], self.flyout.title
        _show_face(self.widget, self.mode, facts.icon, title or variant.label)
        self.widget.setObjectName(object_name(constants.OBJ_FLY_PREFIX, variant.entry_id))
        self.widget.setToolTip(ribbon_text.flyout_tooltip(
            variant.label, variant.cmd, facts.menu_text, facts.tool_tip,
            title=title, label_shown=self.mode != MODE_ICON and not title))

    def choose(self, position):
        """Show variant `position` on the button and store the choice; runs nothing."""
        self.current = position
        self._show_current()
        self._remember()

    def _on_chosen(self, position, *_args):
        with console.guard("change the tool shown on a flyout"):
            self.choose(position)
        self._dispatch(self.variant.cmd, self.variant.index)

    def _on_clicked(self, *_args):
        self._dispatch(self.variant.cmd, self.variant.index)

    def refresh(self, sketch_editing):
        _set_enabled(self.widget, command_is_active(self.variant.cmd))


class ToggleButton:
    """A single slot: variant 0 by default, variant 1 during sketch editing."""

    def __init__(self, toggle, mode, dispatch):
        self.toggle = toggle
        self.mode = mode
        self._dispatch = dispatch
        self.facts = [_Facts(variant) for variant in toggle.variants]
        self.widget = _new_tool_button(mode)
        self.widget.clicked.connect(self._on_clicked)
        self.shown = None
        self.show_variant(0)

    @property
    def variant(self):
        return self.toggle.variants[self.shown]

    def variant_ids(self):
        return [variant.entry_id for variant in self.toggle.variants]

    def show_variant(self, position):
        if position == self.shown:
            return
        self.shown = position
        variant, facts = self.variant, self.facts[position]
        _show_face(self.widget, self.mode, facts.icon, variant.label)
        self.widget.setObjectName(object_name(constants.OBJ_TOG_PREFIX, variant.entry_id))
        self.widget.setToolTip(ribbon_text.toggle_tooltip(
            variant.label, variant.cmd, facts.menu_text, facts.tool_tip))

    def _on_clicked(self, *_args):
        self._dispatch(self.variant.cmd, self.variant.index)

    def refresh(self, sketch_editing):
        self.show_variant(1 if sketch_editing else 0)
        _set_enabled(self.widget, command_is_active(self.variant.cmd))


def _separator():
    line = QtWidgets.QFrame()
    line.setObjectName(constants.OBJ_RIBBON_SEPARATOR)
    line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    return line


class RibbonUI:
    """Dock, tab pages, buttons and the refresh timer of one built ribbon.

    The dock starts hidden. jellyjams.ribbon decides when it is shown or
    hidden and when the timer runs.
    """

    def __init__(self, main_window, resolved, dispatch):
        self.resolved = resolved
        self._dispatch = dispatch
        self.buttons = {}     # entry id -> PlainButton
        self.flyouts = []
        self.toggles = []

        self.dock = QtWidgets.QDockWidget(DOCK_TITLE, main_window)
        self.dock.setObjectName(constants.OBJ_RIBBON)
        self.dock.setTitleBarWidget(QtWidgets.QWidget(self.dock))
        self.dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.dock.setAllowedAreas(_Qt.DockWidgetArea.TopDockWidgetArea)

        self.tabs = QtWidgets.QTabWidget(self.dock)
        self.tabs.setObjectName(constants.OBJ_RIBBON_TABS)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.South)
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                                QtWidgets.QSizePolicy.Policy.Fixed)
        for tab in resolved.tabs:
            self.tabs.addTab(self._build_page(tab), tab.title)
        self.dock.setWidget(self.tabs)
        self.select_tab(constants.START_TAB)

        self.timer = QtCore.QTimer(self.dock)
        # Hide before addDockWidget(); otherwise Qt shows the new dock right away.
        self.dock.hide()
        main_window.addDockWidget(_Qt.DockWidgetArea.TopDockWidgetArea, self.dock)

    # --- building -------------------------------------------------------------------------

    def _build_page(self, tab):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(page)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)
        first = True
        for group in tab.groups:
            widgets = [w for w in (self._build_item(item, MODE_LARGE) for item in group.items) if w]
            if not widgets:
                continue
            if not first:
                layout.addWidget(_separator())
            first = False
            for widget in widgets:
                layout.addWidget(widget, 0, _Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        return page

    def _build_stack(self, stack):
        mode = MODE_ICON if stack.style == STYLE_ICON else MODE_TEXT
        container = QtWidgets.QWidget()
        container.setObjectName(constants.OBJ_RIBBON_STACK)
        grid = QtWidgets.QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(STACK_SPACING)
        placed = 0
        for cell in stack.cells:
            widget = self._build_item(cell, mode)
            if widget is None:
                continue
            grid.addWidget(widget, placed % STACK_ROWS, placed // STACK_ROWS)
            placed += 1
        if not placed:
            container.deleteLater()
            return None
        grid.setRowStretch(STACK_ROWS, 1)
        return container

    def _build_item(self, item, mode):
        try:
            if isinstance(item, RStack):
                return self._build_stack(item)
            if isinstance(item, RFlyout):
                control = FlyoutButton(item, mode, self._dispatch)
                self.flyouts.append(control)
            elif isinstance(item, RToggle):
                control = ToggleButton(item, mode, self._dispatch)
                self.toggles.append(control)
            elif isinstance(item, RButton):
                control = PlainButton(item, mode, self._dispatch)
                self.buttons[item.entry_id] = control
            else:
                raise TypeError("unknown ribbon item: {!r}".format(item))
            return control.widget
        except Exception:
            console.error("ribbon entry {!r} failed to build and was left out".format(item),
                          with_traceback=True)
            return None

    # --- queries --------------------------------------------------------------------------

    def is_alive(self):
        return fcgui.is_alive(self.dock) and fcgui.is_alive(self.tabs)

    def tab_titles(self):
        return [self.tabs.tabText(i) for i in range(self.tabs.count())]

    def tab_index(self, title):
        titles = self.tab_titles()
        return titles.index(title) if title in titles else -1

    def current_title(self):
        index = self.tabs.currentIndex()
        return self.tabs.tabText(index) if index >= 0 else ""

    def select_tab(self, title):
        """Switch to tab `title`; returns False if the ribbon has no such tab."""
        index = self.tab_index(title)
        if index < 0:
            return False
        if self.tabs.currentIndex() != index:
            self.tabs.setCurrentIndex(index)
        return True

    def find_button(self, entry_id):
        control = self.buttons.get(entry_id)
        if control is None or not fcgui.is_alive(control.widget):
            return None
        return control.widget

    def entry_ids(self):
        ids = list(self.buttons)
        for control in self.flyouts:
            ids.extend(control.variant_ids())
        for control in self.toggles:
            ids.extend(control.variant_ids())
        return ids

    def flyout_states(self):
        return [{"id": c.flyout.flyout_id, "variants": c.variant_ids(), "current": c.current}
                for c in self.flyouts]

    def toggle_states(self):
        return [{"variants": c.variant_ids(), "shown": c.shown} for c in self.toggles]

    def counts(self):
        return {
            "tabs": self.tabs.count(),
            "buttons": len(self.buttons),
            "flyouts": len(self.flyouts),
            "variants": sum(len(c.flyout.variants) for c in self.flyouts),
            "toggles": len(self.toggles),
        }

    # --- refresh and disposal -------------------------------------------------------------

    def refresh_states(self, sketch_editing):
        """Update enabled states and pick the variant each toggle shows.

        Tooltips are not reset here, because some commands write their own
        button tooltip while running.
        """
        controls = list(self.buttons.values()) + self.flyouts + self.toggles
        for control in controls:
            try:
                control.refresh(sketch_editing)
            except Exception:
                continue

    def dispose(self, main_window):
        """Tear the dock down step by step; one failing step does not stop the rest."""
        steps = (
            lambda: self.timer.stop(),
            lambda: self.dock.hide(),
            lambda: main_window.removeDockWidget(self.dock) if main_window is not None else None,
            lambda: self.dock.setParent(None),
            lambda: self.dock.deleteLater(),
        )
        for step in steps:
            try:
                step()
            except Exception:
                continue
        self.buttons = {}
        self.flyouts = []
        self.toggles = []
