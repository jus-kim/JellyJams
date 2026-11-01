# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Appearance library dock and native, undoable face/object colouring.

Library choices are previews until Apply or a double-click. Only user-requested
document view properties change; no global material/colour preferences change.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui
from jellyjams import appearance_rules as rules

_dock = None
_enabled = False
_timer = None
_suspended_visible = None
TITLE = "Appearances"
SCOPES = ("Selection (faces or objects)", "Whole selected objects", "Entire model")


class AppearancesCommand(commands.BaseCommand):
    command_id = constants.CMD_APPEARANCES
    menu_text = TITLE
    tooltip = "Browse colours and finishes, then apply an appearance to faces, parts or components."

    def run(self):
        show()


def get_commands():
    return {constants.CMD_APPEARANCES: AppearancesCommand()}


def _is_link(obj):
    return any(doc_utils.is_derived(obj, kind)
               for kind in (constants.TYPE_LINK, constants.TYPE_ASSEMBLY_LINK))


def _face_count(obj):
    try:
        return len(obj.Shape.Faces)
    except Exception:
        return 0


def _paintable(obj):
    if not doc_utils.is_alive(obj):
        return False
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return False
    if _is_link(obj):
        return hasattr(view, "ShapeMaterial") and hasattr(view, "OverrideMaterial")
    return _face_count(obj) > 0 and hasattr(view, "ShapeAppearance")


def _members(obj, visible_only=False, seen=None):
    seen = set() if seen is None else seen
    key = (obj.Document.Name, obj.Name)
    if key in seen:
        return []
    seen.add(key)
    if visible_only and not getattr(obj.ViewObject, "Visibility", False):
        return []
    if _paintable(obj):
        return [obj]
    result = []
    for child in getattr(obj, "Group", ()):
        result.extend(_members(child, visible_only, seen))
    return result


def _resolve(root, sub):
    """Resolve containment paths, stopping at links so a source is never edited."""
    parts = str(sub).split(".")
    obj = root
    for name in parts[:-1]:
        if not name or name == obj.Name:
            continue
        if _is_link(obj):
            return obj, parts[-1]
        child = next((child for child in getattr(obj, "Group", ()) if child.Name == name), None)
        if child is None:
            return None, ""
        obj = child
    return obj, parts[-1]


def targets(scope=0):
    """(object, face-index-set-or-None) pairs for the current active document.

    None means the whole object's appearance, including any existing face colours.
    Explicit but unsupported selections never fall back to colouring the model.
    """
    doc = FreeCAD.ActiveDocument
    if doc is None or fcgui.task_dialog_open():
        return []
    # A failed query is not an empty selection: treating it as one would apply
    # to the entire model. Keep the distinction instead of using the shared
    # query helper's empty-list fallback.
    try:
        selection = list(FreeCADGui.Selection.getSelectionEx("*", 0))
    except Exception:
        return []
    found = {}

    def add(obj, faces=None):
        key = obj.Name
        if key not in found:
            found[key] = (obj, faces)
        elif faces is None:
            found[key] = (obj, None)
        elif found[key][1] is not None:
            found[key][1].update(faces)

    if scope == 2 or not selection:
        for root in doc_utils.root_objects(doc):
            for obj in _members(root, visible_only=True):
                add(obj)
        return list(found.values())
    for entry in selection:
        root = entry.Object
        if not doc_utils.is_alive(root) or root.Document != doc:
            continue
        subs = list(entry.SubElementNames or ()) or [""]
        for sub in subs:
            obj, element = _resolve(root, sub)
            if obj is None:
                continue
            if element.startswith("Face") and scope == 0:
                # Link-level material overrides are supported, per-face link
                # overrides are not. Never follow the link to edit its source.
                index = rules.face_index(element, _face_count(obj))
                if not _is_link(obj) and _paintable(obj) and index is not None:
                    add(obj, {index})
            elif not element or scope == 1:
                for member in _members(obj):
                    add(member)
    return list(found.values())


def _material(values):
    color, specular, shininess, transparency = values
    material = FreeCAD.Material()
    material.DiffuseColor = color
    material.AmbientColor = (0.25, 0.25, 0.25)
    material.SpecularColor = (specular,) * 3
    material.EmissiveColor = (0.0, 0.0, 0.0)
    material.Shininess = shininess
    material.Transparency = transparency
    return material


def apply_appearance(appearance, scope=0):
    """Apply to current targets in one undo step. Roll the whole edit back on error."""
    values = rules.material_values(appearance)
    chosen = targets(scope)
    if not chosen:
        return 0
    doc = FreeCAD.ActiveDocument
    application_transaction = getattr(FreeCAD, "getActiveTransaction", lambda: None)()
    if getattr(doc, "HasPendingTransaction", False) or application_transaction:
        raise ValueError("Finish the current edit before applying an appearance.")
    with doc_utils.transaction(doc, "Apply Appearance", abort_on_error=True):
        for obj, faces in chosen:
            view = obj.ViewObject
            if _is_link(obj):
                view.ShapeMaterial = _material(values)
                view.OverrideMaterial = True
            elif faces is None:
                view.ShapeAppearance = [_material(values)]
            else:
                count = _face_count(obj)
                current = list(view.ShapeAppearance)
                if len(current) == 1:
                    current *= count
                if len(current) != count:
                    raise ValueError("The face appearance list changed; select the faces again.")
                for index in faces:
                    current[index] = _material(values)
                view.ShapeAppearance = current
    return len(chosen)


def swatch_icon(appearance, size=88):
    """Original sphere thumbnail, painted locally without bundled raster assets."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    color = QtGui.QColor(appearance.color)
    sphere = QtCore.QRectF(7, 5, size - 14, size - 14)
    gradient = QtGui.QRadialGradient(size * 0.37, size * 0.30, size * 0.70)
    gradient.setColorAt(0, color.lighter(150))
    gradient.setColorAt(0.48, color)
    gradient.setColorAt(1, color.darker(240))
    painter.setPen(QtGui.QPen(color.darker(180), 1))
    painter.setBrush(gradient)
    painter.drawEllipse(sphere)
    if appearance.finish in ("High Gloss", "Polished", "Clear", "Metallic"):
        highlight = QtGui.QRadialGradient(size * .35, size * .26, size * .22)
        highlight.setColorAt(0, QtGui.QColor(255, 255, 255, 210))
        highlight.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(highlight)
        painter.drawEllipse(sphere)
    painter.end()
    return QtGui.QIcon(pixmap)


class _AppearancePanel(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.summary = QtWidgets.QLabel("Select faces or objects, or apply to the entire model.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.scope = QtWidgets.QComboBox()
        self.scope.addItems(SCOPES)
        self.scope.setToolTip("Whole selected objects replaces their existing face colours.")
        layout.addWidget(self.scope)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search appearances")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.categories = QtWidgets.QTreeWidget()
        self.categories.setHeaderHidden(True)
        self.categories.setMinimumHeight(100)
        self.categories.setMaximumHeight(210)
        split.addWidget(self.categories)
        self.gallery = QtWidgets.QListWidget()
        self.gallery.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.gallery.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.gallery.setMovement(QtWidgets.QListView.Movement.Static)
        self.gallery.setIconSize(QtCore.QSize(88, 88))
        self.gallery.setGridSize(QtCore.QSize(126, 132))
        self.gallery.setWordWrap(True)
        self.gallery.setSpacing(4)
        self.gallery.setMinimumHeight(160)
        split.addWidget(self.gallery)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        hint = QtWidgets.QLabel("Double-click an appearance to apply it.")
        layout.addWidget(hint)
        editor = QtWidgets.QGroupBox("Colour and finish")
        form = QtWidgets.QFormLayout(editor)
        self.color = QtWidgets.QLineEdit("#245ac9")
        self.color.setMaxLength(7)
        self.color_button = QtWidgets.QPushButton("Choose…")
        color_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(color_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.color)
        row.addWidget(self.color_button)
        form.addRow("Colour", color_row)
        self.finish = QtWidgets.QComboBox()
        self.finish.addItems(rules.FINISHES)
        form.addRow("Finish", self.finish)
        self.transparency = QtWidgets.QSpinBox()
        self.transparency.setRange(0, 100)
        self.transparency.setSuffix(" %")
        form.addRow("Transparency", self.transparency)
        layout.addWidget(editor)
        self.apply_button = QtWidgets.QPushButton("Apply Appearance")
        layout.addWidget(self.apply_button)
        self.feedback = QtWidgets.QLabel("")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self._populate_categories()
        self.categories.currentItemChanged.connect(self._category_changed)
        self.gallery.currentItemChanged.connect(self._selected)
        self.gallery.itemDoubleClicked.connect(self._apply_preset)
        self.search.textChanged.connect(self._filter)
        self.color_button.clicked.connect(self._choose_color)
        self.apply_button.clicked.connect(self._apply_custom)
        self.scope.currentIndexChanged.connect(self.refresh_selection)
        self.categories.setCurrentItem(self.categories.topLevelItem(0).child(0))

    def _populate_categories(self):
        groups = {}
        for category, finish in rules.LIBRARY:
            if category not in groups:
                groups[category] = QtWidgets.QTreeWidgetItem(self.categories, [category])
            item = QtWidgets.QTreeWidgetItem(groups[category], [finish])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, (category, finish))
        self.categories.topLevelItem(0).setExpanded(True)

    @console.guarded("browse appearance categories")
    def _category_changed(self, item, _previous):
        if item is None:
            return
        key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if key is None:
            item.setExpanded(True)
            return
        self.gallery.clear()
        for appearance in rules.LIBRARY[tuple(key)]:
            tile = QtWidgets.QListWidgetItem(swatch_icon(appearance), appearance.name)
            tile.setData(QtCore.Qt.ItemDataRole.UserRole, appearance)
            tile.setToolTip(appearance.name + "\nDouble-click to apply")
            self.gallery.addItem(tile)
        self._filter()

    @console.guarded("filter appearance previews")
    def _filter(self, *_args):
        text = self.search.text().strip().casefold()
        for index in range(self.gallery.count()):
            tile = self.gallery.item(index)
            tile.setHidden(text not in tile.text().casefold())

    @console.guarded("select an appearance preview")
    def _selected(self, item, _previous):
        if item is None:
            return
        appearance = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.color.setText(appearance.color)
        self.finish.setCurrentText(appearance.finish)
        self.transparency.setValue(appearance.transparency)
        self.feedback.setText(appearance.name)

    @console.guarded("choose an appearance colour")
    def _choose_color(self, *_args):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.color.text()), self, "Choose Colour")
        if color.isValid():
            self.color.setText(color.name())

    @console.guarded("apply an appearance preset")
    def _apply_preset(self, item):
        self._apply(item.data(QtCore.Qt.ItemDataRole.UserRole))

    @console.guarded("apply a custom appearance")
    def _apply_custom(self, *_args):
        self._apply(rules.Appearance("Custom colour", self.color.text(),
                                     self.finish.currentText(), self.transparency.value()))

    def _apply(self, appearance):
        try:
            count = apply_appearance(appearance, self.scope.currentIndex())
            self.feedback.setText("Applied to %d object(s). Undo restores the previous appearance." % count
                                  if count else "Select a face, solid or component. For a linked face, choose Whole selected objects.")
        except Exception as exc:
            self.feedback.setText(str(exc))
            console.warning("appearance was not applied: %s" % exc)

    @console.guarded("update the appearance selection")
    def refresh_selection(self, *_args):
        count = len(targets(self.scope.currentIndex()))
        self.summary.setText("%d object(s) ready for colouring" % count if count
                             else "Select a face, solid or component to colour.")
        self.apply_button.setEnabled(count > 0)


def dock():
    return _dock if fcgui.is_alive(_dock) else None


def enable():
    """Add the Appearances tab while active, deferring hidden-window startup."""
    global _enabled, _timer
    _enabled = True
    if not fcgui.is_alive(_timer):
        _timer = QtCore.QTimer(fcgui.main_window())
        _timer.setInterval(500)
        _timer.timeout.connect(_refresh)
    _timer.start()
    _refresh()


@console.guarded("update the Appearances tab")
def _refresh():
    global _dock
    if not _enabled or not fcgui.jellyjams_active():
        return
    window = fcgui.main_window()
    if window is None or not window.isVisible():
        return
    if dock() is None:
        created = QtWidgets.QDockWidget(TITLE, window)
        try:
            created.setObjectName(constants.OBJ_APPEARANCES)
            created.setMinimumWidth(290)
            created.setWidget(_AppearancePanel(created))
            window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, created)
            tasks = fcgui.task_dock()
            if tasks is not None:
                window.tabifyDockWidget(tasks, created)
            created.show()
            if tasks is not None:
                tasks.raise_()
        except Exception:
            if fcgui.is_alive(created):
                created.hide()
                window.removeDockWidget(created)
                created.setParent(None)
                created.deleteLater()
            raise
        # Publish only a complete panel. A transient construction failure must
        # not leave a dock with no widget that every later refresh reuses.
        _dock = created
    if not _dock.visibleRegion().isEmpty():
        _dock.widget().refresh_selection()


def show():
    enable()
    if dock() is not None:
        _dock.show()
        _dock.raise_()


def disable():
    """Remove only JellyJams' dock before stock layout restoration."""
    global _enabled, _dock
    _enabled = False
    if fcgui.is_alive(_timer):
        _timer.stop()
    current, _dock = dock(), None
    if current is not None:
        current.hide()
        window = fcgui.main_window()
        if window is not None:
            window.removeDockWidget(current)
        current.setParent(None)
        current.deleteLater()


def suspend_for_quit():
    global _suspended_visible
    _suspended_visible = dock() is not None and not _dock.isHidden()
    disable()


def resume_after_cancel():
    enable()
    if _suspended_visible is False and dock() is not None:
        _dock.hide()
