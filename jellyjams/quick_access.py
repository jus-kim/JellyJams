# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""S command search and task-bound confirmation, owned by ribbon visibility.

Scoped ShortcutOverride handling gives S/D priority over native single-letter
and multi-key bindings without writing any shortcut preferences. Typing inputs
keep their keys. Native task buttons remain the authority for confirmation.
"""

import functools

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

from jellyjams import console, constants, fcgui
from jellyjams import access_rules

_service = None
POLL_MS = 150


def document_key():
    doc = getattr(FreeCAD, "ActiveDocument", None)
    return (doc.Name, str(getattr(doc, "Uid", id(doc)))) if doc is not None else None


def typing_focus(widget):
    """Typing editors, editable combos and non-model lists keep S and D."""
    for _ in range(32):
        if widget is None:
            return False
        if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                               QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
                               QtWidgets.QComboBox)):
            return True
        if isinstance(widget, QtWidgets.QAbstractItemView):
            return widget.metaObject().className() != constants.CLASS_MODEL_TREE
        widget = widget.parentWidget()
    return True


def mode():
    if fcgui.sketch_in_edit() is not None:
        return constants.TAB_SKETCH
    if fcgui.active_sheet_window() is not None:
        return constants.TAB_DRAWING
    try:
        import UtilsAssembly
        if UtilsAssembly.activeAssembly() is not None:
            return constants.TAB_ASSEMBLY
    except Exception:
        pass
    return constants.TAB_FEATURES


def catalog(resolved, title, sketch):
    """Selected context first, then every searchable ribbon variant, deduplicated."""
    from jellyjams.ribbon_model import RButton, RFlyout, RStack, RToggle

    def buttons(items):
        for item in items:
            if isinstance(item, RButton):
                yield item
            elif isinstance(item, RFlyout):
                yield from item.variants
            elif isinstance(item, RToggle):
                yield item.variants[1 if sketch else 0]
            elif isinstance(item, RStack):
                yield from buttons(item.cells)

    result, seen = [], set()
    tabs = sorted(resolved.tabs, key=lambda tab: tab.title != title)
    for tab in tabs:
        for group in tab.groups:
            for entry in buttons(group.items):
                if entry.entry_id not in seen:
                    result.append((tab.title, entry))
                    seen.add(entry.entry_id)
    return result


def _style(name):
    from jellyjams import theme
    p = theme.widget_colors()
    return (
        "QWidget#%s { background:%s; color:%s; border:1px solid %s; }"
        "QWidget#%s QLabel, QWidget#%s QToolButton { color:%s; }"
        "QWidget#%s QToolButton { padding:5px; border:1px solid transparent; }"
        "QWidget#%s QToolButton:hover { background:%s; border-color:%s; }"
        "QWidget#%s QToolButton:disabled { color:%s; }"
        "QWidget#%s QLineEdit, QWidget#%s QListWidget { background:%s; color:%s; }"
        "QWidget#%s QListWidget::item:selected { background:%s; color:%s; }"
    ) % (name, p.PANEL, p.TEXT, p.BORDER, name, name, p.TEXT,
         name, name, p.HOVER, p.ACCENT, name, p.TEXT_DISABLED, name, name, p.PANEL, p.TEXT,
         name, p.SELECTION, p.TEXT)


def _position(popup):
    point = QtGui.QCursor.pos() + QtCore.QPoint(12, 12)
    screen = QtGui.QGuiApplication.screenAt(point) or QtGui.QGuiApplication.primaryScreen()
    area = screen.availableGeometry()
    popup.move(max(area.left(), min(point.x(), area.right() - popup.width() + 1)),
               max(area.top(), min(point.y(), area.bottom() - popup.height() + 1)))


def _native_key(widget):
    import shiboken6
    return int(shiboken6.getCppPointer(widget)[0])


def task_state():
    """Identity and actions of the current task; never invent Cancel Sketch."""
    if not fcgui.task_dialog_open() or document_key() is None:
        return None, []
    # Older hosts have a global task panel: changing the active document can
    # leave another document's feature task visible in it.
    active_dialog = getattr(fcgui.gui().Control, "activeTaskDialog", None)
    if callable(active_dialog):
        dialog = active_dialog()
        if dialog is None:
            return None, []
        owner = dialog.getDocumentName()
        if owner and owner != FreeCAD.ActiveDocument.Name:
            return None, []
    panel, dock = fcgui.task_panel(), fcgui.task_dock()
    if panel is None or dock is None:
        return None, []
    # TaskPanel and its button box can be reused. Include native form identities
    # so a popup from a former task cannot accept a later task in that panel.
    forms = tuple(_native_key(w) for w in panel.findChildren(QtWidgets.QWidget)
                  if w.objectName() and not w.objectName().startswith(constants.OBJ_PREFIX))
    sketch = fcgui.sketch_in_edit()
    token = (document_key(), _native_key(panel), forms,
             sketch.Name if sketch is not None else None)
    if sketch is not None:
        return token, [("Exit Sketch", None)]
    actions = []
    for standard, label in ((QtWidgets.QDialogButtonBox.StandardButton.Ok, "OK"),
                            (QtWidgets.QDialogButtonBox.StandardButton.Cancel, "Cancel")):
        for box in dock.findChildren(QtWidgets.QDialogButtonBox):
            button = box.button(standard)
            if button is not None and button.isVisibleTo(dock):
                actions.append((label, button))
                break
    return token, actions


def confirm(token, label):
    if not fcgui.jellyjams_active() or QtWidgets.QApplication.activeModalWidget() is not None:
        return False
    current, actions = task_state()
    if current != token or current is None:
        return False
    for name, button in actions:
        if name != label:
            continue
        if button is None:
            fcgui.gui().runCommand(constants.SKETCH_LEAVE_COMMAND)
        elif fcgui.is_alive(button) and button.isEnabled():
            button.click()
        else:
            return False
        return True
    return False


class SearchPopup(QtWidgets.QDialog):
    def __init__(self, parent, resolved):
        super().__init__(parent, QtCore.Qt.WindowType.Popup)
        self.setObjectName(constants.OBJ_QUICK_ACCESS)
        self.setStyleSheet(_style(constants.OBJ_QUICK_ACCESS))
        self.context = document_key()
        self.title = mode()
        self.chosen = False
        self.entries = catalog(resolved, self.title, fcgui.sketch_in_edit() is not None)
        self.setWindowTitle("Shortcut Bar")
        self.resize(400, 390)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(self.title + " tools · S"))
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search commands…")
        layout.addWidget(self.search)
        self.results = QtWidgets.QListWidget(self)
        layout.addWidget(self.results)
        self.search.textChanged.connect(console.guarded("search commands")(self.populate))
        self.search.returnPressed.connect(console.guarded("choose a shortcut command")(self.choose))
        self.results.itemActivated.connect(console.guarded("choose a shortcut command")(self.choose))
        self.results.itemClicked.connect(console.guarded("choose a shortcut command")(self.choose))
        self.search.installEventFilter(self)
        self.populate()

    def populate(self, text=""):
        from jellyjams import icons, ribbon_widgets
        self.results.clear()
        for title, entry in self.entries:
            if (not text and title != self.title) or not access_rules.matches(text, entry.one_line, entry.cmd):
                continue
            row = QtWidgets.QListWidgetItem(
                icons.command_icon(entry.cmd, entry.index, entry.jj_icon, entry.fc_icon),
                entry.one_line, self.results)
            row.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
            row.setToolTip(entry.one_line)
            if not ribbon_widgets.command_is_active(entry.cmd):
                row.setFlags(row.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            if self.results.count() >= (80 if text else 14):
                break
        for index in range(self.results.count()):
            if self.results.item(index).flags() & QtCore.Qt.ItemFlag.ItemIsEnabled:
                self.results.setCurrentRow(index)
                break

    def eventFilter(self, watched, event):
        try:
            if event.type() == QtCore.QEvent.Type.KeyPress and event.key() == QtCore.Qt.Key.Key_Down:
                self.results.setFocus()
                return True
        except Exception:
            pass
        return False

    def choose(self, *_args):
        from jellyjams import ribbon, ribbon_widgets
        if self.chosen:
            return
        row = self.results.currentItem()
        if row is None or not row.flags() & QtCore.Qt.ItemFlag.ItemIsEnabled:
            return
        entry = row.data(QtCore.Qt.ItemDataRole.UserRole)
        if (self.context != document_key() or mode() != self.title
                or not ribbon_widgets.command_is_active(entry.cmd)):
            self.close()
            return
        self.chosen = True
        self.close()
        # The popup must release keyboard focus before a native tool opens.
        context = self.context
        def dispatch():
            if (fcgui.jellyjams_active() and context == document_key() and mode() == self.title
                    and ribbon_widgets.command_is_active(entry.cmd)
                    and QtWidgets.QApplication.activeModalWidget() is None):
                ribbon.run_entry(entry.cmd, entry.index)
        fcgui.defer(dispatch, 0)


class AccessService(QtCore.QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.targets = []
        self.popup = None
        self.corner = None
        self.signature = None
        self.context = None
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(console.guarded("refresh quick access")(self.tick))
        self.timer.start()

    def watch(self, widget):
        if fcgui.is_alive(widget) and widget not in self.targets:
            widget.installEventFilter(self)
            self.targets.append(widget)

    def close_popup(self):
        if fcgui.is_alive(self.popup):
            self.popup.close()
            self.popup.deleteLater()
        self.popup = None

    def show_search(self):
        from jellyjams import ribbon
        if fcgui.is_alive(self.popup) and self.popup.isVisible():
            self.close_popup()
            return
        ui = ribbon._live_ui()
        if ui is None or document_key() is None:
            return
        self.close_popup()
        self.popup = SearchPopup(self.window, ui.resolved)
        self.popup.show()
        _position(self.popup)
        self.popup.search.setFocus()

    def build_actions(self, parent, token, actions, popup=False):
        frame = QtWidgets.QFrame(parent, QtCore.Qt.WindowType.Popup if popup else QtCore.Qt.WindowType.Widget)
        frame.setObjectName(constants.OBJ_CONFIRMATION)
        frame.setStyleSheet(_style(constants.OBJ_CONFIRMATION))
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(3, 2, 3, 2)
        for label, native in actions:
            button = QtWidgets.QToolButton(frame)
            button.setText(label)
            button.setToolTip(label + (" · D" if popup else " (D: move to pointer)"))
            button.setEnabled(native is None or native.isEnabled())
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.clicked.connect(console.guarded("confirm the active task")(
                functools.partial(self.act, token, label)))
            layout.addWidget(button)
        frame.adjustSize()
        return frame

    def act(self, token, label):
        self.close_popup()
        confirm(token, label)

    def show_confirmation(self):
        token, actions = task_state()
        self.close_popup()
        if not actions:
            return
        self.popup = self.build_actions(self.window, token, actions, popup=True)
        self.popup.show()
        _position(self.popup)

    def tick(self):
        from jellyjams import ribbon
        if not fcgui.jellyjams_active():
            self.close_popup()
            if fcgui.is_alive(self.corner):
                self.corner.hide()
            return
        host = fcgui.active_mdi_widget()
        self.targets = [target for target in self.targets if fcgui.is_alive(target)]
        self.watch(self.window)
        for dock in self.window.findChildren(QtWidgets.QDockWidget):
            self.watch(dock)
        if host is not None:
            self.watch(host.window())
            self.watch(host)
            # Sketcher's viewer can consume letter keys before they bubble to
            # the main window, so the scoped filter also covers drawing areas.
            for widget in host.findChildren(QtWidgets.QWidget):
                if widget.inherits("QOpenGLWidget") or widget.metaObject().className() == constants.CLASS_VIEWER3D:
                    self.watch(widget)
                elif isinstance(widget, QtWidgets.QGraphicsView):
                    self.watch(widget)
                    self.watch(widget.viewport())
        context = (document_key(), mode())
        if context != self.context:
            self.context = context
            self.close_popup()
            ribbon.refresh_now()
        token, actions = task_state()
        signature = (token, _native_key(host) if host is not None else None,
                     tuple((label, native is None or native.isEnabled()) for label, native in actions))
        if signature != self.signature or not fcgui.is_alive(self.corner):
            if fcgui.is_alive(self.corner):
                self.corner.hide()
                self.corner.deleteLater()
            self.corner = None
            self.signature = signature
            if host is not None and actions:
                self.corner = self.build_actions(host, token, actions)
        if fcgui.is_alive(self.corner) and host is not None:
            self.corner.move(max(8, host.width() - self.corner.width() - 170), 10)
            self.corner.setVisible(QtWidgets.QApplication.activeModalWidget() is None)
            self.corner.raise_()

    def eventFilter(self, watched, event):
        try:
            if not fcgui.jellyjams_active() or QtWidgets.QApplication.activeModalWidget() is not None:
                return False
            if event.type() not in (QtCore.QEvent.Type.ShortcutOverride, QtCore.QEvent.Type.KeyPress):
                return False
            if event.modifiers() != QtCore.Qt.KeyboardModifier.NoModifier:
                return False
            if event.key() not in (QtCore.Qt.Key.Key_S, QtCore.Qt.Key.Key_D):
                return False
            if typing_focus(QtWidgets.QApplication.focusWidget()) or document_key() is None:
                return False
            if event.type() == QtCore.QEvent.Type.ShortcutOverride:
                event.accept()
                return True
            if not event.isAutoRepeat():
                if event.key() == QtCore.Qt.Key.Key_S:
                    self.show_search()
                else:
                    self.show_confirmation()
            return True
        except Exception as exc:
            console.log("quick-access key handling: %s" % exc)
            return False

    def stop(self):
        self.timer.stop()
        self.close_popup()
        if fcgui.is_alive(self.corner):
            self.corner.hide()
            self.corner.deleteLater()
        for target in self.targets:
            if fcgui.is_alive(target):
                target.removeEventFilter(self)
        self.targets = []
        self.deleteLater()


@console.guarded("enable quick-access controls", level="log")
def enable():
    global _service
    if fcgui.is_alive(_service):
        return
    window = fcgui.main_window()
    if window is not None:
        _service = AccessService(window)
        _service.tick()


@console.guarded("remove quick-access controls", level="log")
def disable():
    global _service
    service, _service = _service, None
    if fcgui.is_alive(service):
        service.stop()
