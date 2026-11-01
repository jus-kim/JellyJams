# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_SheetProperties: the SolidWorks "Sheet Properties" panel for a TechDraw sheet.

The panel edits the sheet format (template), the type of projection and the title-block
texts. The document is left alone until OK, which applies everything as one undo step.
"""

import os

from PySide import QtCore, QtGui, QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui, paths
from jellyjams import drawing_common, make_drawing, templates

UNDO_NAME = "Sheet Properties"
WINDOW_TITLE = "Sheet Properties"
CUSTOM_PREFIX = "Custom: "
METHODS = (templates.FIRST_ANGLE, templates.THIRD_ANGLE)
FIELD_OBJECT_PREFIX = "JellyJamsSheetField-"

# Template key -> label, in panel order (drawing-sheet 5.3).
FIELD_LABELS = {
    "title": "Title",
    "supplementary_title_1": "Supplementary title 1",
    "supplementary_title_2": "Supplementary title 2",
    "drawing_number": "Drawing number",
    "part_material": "Material",
    "scale": "Scale",
    "unit": "Unit",
    "general_tolerances": "General tolerances",
    "creator": "Drawn by",
    "approval_person": "Approved by",
    "date_of_issue": "Date of issue",
    "revision_index": "Revision",
    "sheet_number": "Sheet",
    "document_type": "Document type",
    "document_status": "Document status",
    "responsible_department": "Responsible department",
    "language_code": "Language",
    "legal_owner_1": "Legal owner (line 1)",
    "legal_owner_2": "Legal owner (line 2)",
    "legal_owner_3": "Legal owner (line 3)",
    "legal_owner_4": "Legal owner (line 4)",
}

# Their X/Y are offsets from another view, not sheet positions.
_ATTACHED_TYPES = (
    constants.TYPE_PROJ_ITEM,
    constants.TYPE_DIMENSION,
    constants.TYPE_BALLOON,
    constants.TYPE_LEADER,
    "TechDraw::DrawWeldSymbol",
)
_RICH_ANNOTATION = "TechDraw::DrawRichAnno"
_CROP_FRAME = "TechDraw::DrawViewClip"
_CUSTOM_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


# --- pure helpers ---------------------------------------------------------------------------


def field_label(key):
    """Display label of a title-block key: from FIELD_LABELS, else the key made readable."""
    key = str(key)
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    text = key.replace("_", " ")
    return text[:1].upper() + text[1:]


def ordered_keys(keys):
    """The keys in FIELD_LABELS order, then the remaining keys sorted alphabetically."""
    unique = list(dict.fromkeys(str(key) for key in keys))
    known = [key for key in FIELD_LABELS if key in unique]
    unknown = sorted(key for key in unique if key not in FIELD_LABELS)
    return known + unknown


# --- document helpers -----------------------------------------------------------------------


def _same_path(a, b):
    if not a or not b:
        return a == b
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _all_views(page):
    """All views of the sheet, including those nested in groups and crop frames, no repeats."""
    seen = set()
    result = []
    pending = list(getattr(page, "Views", None) or [])
    while pending:
        view = pending.pop(0)
        try:
            name = view.Name
        except Exception:
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(view)
        pending.extend(getattr(view, "Views", None) or [])
    return result


def _projection_groups(page):
    return [
        view for view in _all_views(page) if doc_utils.is_derived(view, constants.TYPE_PROJ_GROUP)
    ]


def current_method(page):
    """Projection method of the sheet: from its first projection group, else from the page."""
    groups = _projection_groups(page)
    if groups:
        method = getattr(groups[0], "ProjectionType", "")
        if method in METHODS:
            return method
    method = getattr(page, "ProjectionType", "")
    return method if method in METHODS else templates.FIRST_ANGLE


def _number(value):
    return float(getattr(value, "Value", value))


def _name(obj):
    try:
        return obj.Name
    except Exception:
        return None


def _in_container(view):
    """True when a crop frame or another non-page view lists `view` among its Views.

    Such a view's X/Y are relative to that parent. Objects that merely link to the view
    (dimensions, section views, labels) are not containers.
    """
    name = _name(view)
    for parent in list(getattr(view, "InList", None) or []):
        if doc_utils.is_derived(parent, constants.TYPE_PAGE):
            continue
        if doc_utils.is_derived(parent, _CROP_FRAME):
            return True
        members = getattr(parent, "Views", None) or []
        if name is not None and any(_name(member) == name for member in members):
            return True
    return False


def _is_free_view(view):
    if not (hasattr(view, "X") and hasattr(view, "Y")):
        return False
    if any(doc_utils.is_derived(view, type_id) for type_id in _ATTACHED_TYPES):
        return False
    if doc_utils.is_derived(view, _RICH_ANNOTATION) and getattr(view, "AnnoParent", None):
        return False
    return not _in_container(view)


def _is_view_label(view):
    return constants.PROP_CAPTION_FOR in (getattr(view, "PropertiesList", None) or ())


def _weld_tip(view):
    """(ArrowheadX, ArrowheadY) of a JellyJams weld symbol, else None."""
    if str(getattr(view, constants.PROP_SYMBOL_TYPE, "") or "") != constants.KIND_WELD:
        return None
    properties = getattr(view, "PropertiesList", None) or ()
    if constants.PROP_ARROWHEAD_X not in properties or constants.PROP_ARROWHEAD_Y not in properties:
        return None
    return (
        _number(getattr(view, constants.PROP_ARROWHEAD_X)),
        _number(getattr(view, constants.PROP_ARROWHEAD_Y)),
    )


def _position_snapshot(page):
    """[(view, x, y, weld tip or None)] of the sheet's free views, view labels at the end.

    Labels come last because the view-label observer shifts a label whenever its view
    moves; writing the labels afterwards replaces that shift with the scaled position.
    """
    views, labels = [], []
    for view in list(getattr(page, "Views", None) or []):
        if not _is_free_view(view):
            continue
        entry = (view, _number(view.X), _number(view.Y), _weld_tip(view))
        (labels if _is_view_label(view) else views).append(entry)
    return views + labels


def _rescale_positions(snapshot, old_size, new_size):
    """Write each snapshot position scaled from the old to the new sheet size."""
    factor_x = new_size[0] / old_size[0]
    factor_y = new_size[1] / old_size[1]
    if factor_x == 1.0 and factor_y == 1.0:
        return
    for view, x, y, tip in snapshot:
        view.X = x * factor_x
        view.Y = y * factor_y
        if tip is not None:
            setattr(view, constants.PROP_ARROWHEAD_X, tip[0] * factor_x)
            setattr(view, constants.PROP_ARROWHEAD_Y, tip[1] * factor_y)


def _apply_method(page, method):
    if page.ProjectionType != method:
        page.ProjectionType = method
    for group in _projection_groups(page):
        if group.ProjectionType != method:
            group.ProjectionType = method


def _write_texts(template, values):
    keys = dict(template.EditableTexts)
    template.EditableTexts = {key: values.get(key, "") for key in keys}


def _switch_template(page, template, new_path, field_values, snapshot):
    # Assigning Template makes FreeCAD replace all editable texts with the new file's samples.
    collected = dict(template.EditableTexts)
    collected.update(field_values)
    old_size = drawing_common.sheet_size(page)
    template.Template = new_path
    new_size = drawing_common.sheet_size(page)
    _write_texts(template, collected)
    if old_size is not None and new_size is not None:
        _rescale_positions(snapshot, old_size, new_size)


def apply_sheet_properties(page, template_path, method, field_values):
    """Set the format, the projection method and the title-block texts in one undo step."""
    template = page.Template
    document = page.Document
    snapshot = _position_snapshot(page)
    with doc_utils.transaction(document, UNDO_NAME):
        _apply_method(page, method)
        current = template.Template
        effective = templates.resolve_for_method(template_path or current, method)
        if effective and not _same_path(effective, current):
            _switch_template(page, template, effective, field_values, snapshot)
        else:
            _write_texts(template, field_values)
        document.recompute()


# --- panel ------------------------------------------------------------------------------------


def _heading(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName(constants.OBJ_PANEL_HEADING)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


class SheetPropertiesPanel:
    """Task panel for one sheet; FreeCAD shows its `form` widget in the Tasks area."""

    def __init__(self, page):
        self.page = page
        self.template = page.Template
        self.fields = {}
        self.form = QtWidgets.QWidget()
        self.form.setObjectName(constants.OBJ_SHEET_PROPERTIES)
        self.form.setWindowTitle(WINDOW_TITLE)
        icon = paths.icon_path(constants.COMMAND_ICONS[constants.CMD_SHEET_PROPERTIES])
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        layout = QtWidgets.QVBoxLayout(self.form)
        self._build_format_section(layout)
        self._build_projection_section(layout)
        self._build_title_block_section(layout)
        layout.addStretch(1)

    # --- sections ---------------------------------------------------------------------

    def _build_format_section(self, layout):
        layout.addWidget(_heading("Sheet Format/Size"))
        row = QtWidgets.QHBoxLayout()
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.format_combo.setMinimumContentsLength(16)
        for display, path in templates.catalog():
            self.format_combo.addItem(display, path)
        browse = QtWidgets.QPushButton("Browse…")
        browse.setToolTip(
            "Use any SVG template file as the sheet format, such as your company's title block."
        )
        browse.clicked.connect(console.guarded("pick a sheet format file")(self._browse))
        row.addWidget(self.format_combo, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        self._select_format(self._current_base_template())

    def _build_projection_section(self, layout):
        layout.addWidget(_heading("Type of projection"))
        tooltip = (
            "First angle (ISO, Europe): the top view goes below the front view.\n"
            "Third angle (US): the top view goes above the front view.\n"
            "The projection symbol in the title block is switched to match when the "
            "template allows it."
        )
        self.method_buttons = {}
        self.method_group = QtWidgets.QButtonGroup(self.form)
        self.method_group.setExclusive(True)
        row = QtWidgets.QHBoxLayout()
        for method in METHODS:
            button = QtWidgets.QRadioButton(method)
            button.setToolTip(tooltip)
            self.method_group.addButton(button)
            self.method_buttons[method] = button
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        self.method_buttons[current_method(self.page)].setChecked(True)

    def _build_title_block_section(self, layout):
        layout.addWidget(_heading("Title Block"))
        fill = QtWidgets.QPushButton("Fill from Model")
        fill.setToolTip(
            "Takes the title, drawing number, material, scale, author and date from the "
            "model. Nothing is written to the document before OK."
        )
        fill_slot = console.guarded("read title block values from the model")(self._fill_from_model)
        fill.clicked.connect(fill_slot)
        layout.addWidget(fill)
        form = QtWidgets.QFormLayout()
        texts = dict(self.template.EditableTexts)
        for key in ordered_keys(texts):
            field = QtWidgets.QLineEdit(str(texts.get(key, "")))
            field.setObjectName(FIELD_OBJECT_PREFIX + key)
            form.addRow(field_label(key) + ":", field)
            self.fields[key] = field
        layout.addLayout(form)

    # --- format list ------------------------------------------------------------------

    def _current_base_template(self):
        current = str(getattr(self.template, "Template", "") or "")
        if templates.is_third_angle_variant(current):
            return templates.resolve_for_method(current, templates.FIRST_ANGLE)
        return current

    def _catalog_index(self, path):
        combo = self.format_combo
        catalog_items = [
            index for index in range(combo.count()) if not combo.itemData(index, _CUSTOM_ROLE)
        ]
        for index in catalog_items:
            if _same_path(combo.itemData(index), path):
                return index
        if path and not os.path.isfile(path):
            # Drawing made on another computer: look the template up by its file name.
            name = os.path.basename(path).lower()
            for index in catalog_items:
                if os.path.basename(str(combo.itemData(index))).lower() == name:
                    return index
        return -1

    def _set_custom(self, path):
        combo = self.format_combo
        text = CUSTOM_PREFIX + os.path.basename(path)
        if combo.count() and combo.itemData(0, _CUSTOM_ROLE):
            combo.setItemText(0, text)
            combo.setItemData(0, path)
        else:
            combo.insertItem(0, text, path)
            combo.setItemData(0, True, _CUSTOM_ROLE)
        combo.setCurrentIndex(0)

    def _select_format(self, path):
        index = self._catalog_index(path)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        elif path:
            self._set_custom(path)

    def _browse(self):
        current = str(getattr(self.template, "Template", "") or "")
        folder = os.path.dirname(current)
        if not folder or not os.path.isdir(folder):
            folder = templates.templates_dir()
        path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self.form, "Select a sheet format", folder, "Drawing template (*.svg)"
        )
        if path:
            self._select_format(os.path.normpath(path))

    # --- title block ------------------------------------------------------------------

    def _fill_from_model(self):
        values = make_drawing.title_block_values(self.page, self.page.Document)
        for key, value in values.items():
            field = self.fields.get(key)
            if field is not None:
                field.setText(value)

    def chosen_method(self):
        for method, button in self.method_buttons.items():
            if button.isChecked():
                return method
        return current_method(self.page)

    def field_values(self):
        return {key: field.text() for key, field in self.fields.items()}

    # --- task dialog interface ----------------------------------------------------------

    def accept(self):
        try:
            if not (doc_utils.is_alive(self.page) and doc_utils.is_alive(self.template)):
                raise RuntimeError("the sheet or its template was deleted")
            apply_sheet_properties(
                self.page,
                self.format_combo.currentData(),
                self.chosen_method(),
                self.field_values(),
            )
        except Exception:
            console.error("applying the sheet properties failed", with_traceback=True)
        return True

    def reject(self):
        return True


def open_panel(page=None):
    """Open the Sheet Properties panel for `page`, or for the target sheet when None."""
    if fcgui.task_dialog_open():
        return False
    if page is None:
        page = drawing_common.target_sheet()
    template = getattr(page, "Template", None) if page is not None else None
    if template is None or not hasattr(template, "EditableTexts"):
        return False
    fcgui.gui().Control.showDialog(SheetPropertiesPanel(page))
    return True


class SheetPropertiesCommand(commands.BaseCommand):
    command_id = constants.CMD_SHEET_PROPERTIES
    menu_text = "Sheet Properties"
    tooltip = (
        "Opens the setup of the current sheet: paper size or template, first- or third-angle "
        "projection, and the title block entries."
    )

    def is_active(self):
        return drawing_common.drawing_tools_enabled()

    def run(self):
        open_panel()


def get_commands():
    """Command table of this module: JellyJams_SheetProperties."""
    return {constants.CMD_SHEET_PROPERTIES: SheetPropertiesCommand()}
