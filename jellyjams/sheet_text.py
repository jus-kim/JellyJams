# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Text on the drawing sheet (JellyJams_Note).

JellyJams texts are TechDraw annotations marked with the SheetNote property. With such a text
selected, the command edits it. Otherwise the user clicks a spot on the sheet (sheet_pick,
owner "text") and enters the text in a small modal dialog.
"""

import FreeCAD
from PySide import QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui, params

ISO_HEIGHTS_MM = (2.5, 3.5, 5, 7, 10, 14, 20)
DEFAULT_HEIGHT_MM = 3.5
UNITS = ("mm", "pt")
HEIGHT_RANGE = (0.5, 500.0)
LINE_BREAK = "\\n"
PLACEHOLDER = "–"

PICK_OWNER = "text"
TEXT_STEP = "Text"
TEXT_NAME = "Text"
HINT_MS = 6000
PICK_HINT = "Text: click where the text should go. Press Esc to cancel."
NOT_A_SHEET_HINT = "Text: make a sheet window active, then start Text again."


def split_lines(text):
    """Lines of `text`, separated wherever a backslash is followed by "n"."""
    return str(text).split(LINE_BREAK)


def mm_to_pt(mm):
    """Convert mm to typographic points (72 pt per inch)."""
    return float(mm) * 72.0 / 25.4


def pt_to_mm(pt):
    """Convert typographic points to mm."""
    return float(pt) * 25.4 / 72.0


def _to_unit(mm, unit):
    return mm_to_pt(mm) if unit == "pt" else float(mm)


def _from_unit(value, unit):
    return pt_to_mm(value) if unit == "pt" else float(value)


def _number(value):
    return float(getattr(value, "Value", value))


# --- remembered height and unit --------------------------------------------------------------


def _last_height_mm():
    height = params.get_float(constants.PARAM_ROOT, constants.KEY_NOTE_HEIGHT, DEFAULT_HEIGHT_MM)
    return height if height > 0 else DEFAULT_HEIGHT_MM


def _last_unit():
    unit = params.get_string(constants.PARAM_ROOT, constants.KEY_NOTE_UNIT, "mm")
    return unit if unit in UNITS else "mm"


def _remember(height_mm, unit):
    with console.guard("store the last text height", level="log"):
        own = params.own()
        params.set_value(own, "Float", constants.KEY_NOTE_HEIGHT, float(height_mm))
        params.set_value(own, "String", constants.KEY_NOTE_UNIT, unit)


# --- dialog --------------------------------------------------------------------------------------


class _TextDialog:
    """Modal "Text" dialog. The height is held in mm, so switching units never rounds it off."""

    def __init__(self, text, height_mm, unit):
        self._height_mm = float(height_mm)
        self._unit = unit if unit in UNITS else "mm"
        self._accepted = False

        dialog = QtWidgets.QDialog(fcgui.main_window())
        dialog.setObjectName(constants.OBJ_NOTE_DIALOG)
        dialog.setWindowTitle("Text")
        form = QtWidgets.QFormLayout(dialog)

        self.text = QtWidgets.QLineEdit(text)
        self.text.setMinimumWidth(320)
        self.text.setToolTip("Write \\n where a new line should begin.")
        form.addRow("Text:", self.text)

        self.height = QtWidgets.QDoubleSpinBox()
        self.height.setRange(*HEIGHT_RANGE)
        self.height.setDecimals(2)
        self.unit = QtWidgets.QComboBox()
        self.unit.addItems(list(UNITS))
        self.unit.setCurrentIndex(UNITS.index(self._unit))
        height_row = QtWidgets.QHBoxLayout()
        height_row.addWidget(self.height, 1)
        height_row.addWidget(self.unit)
        form.addRow("Height:", height_row)

        self.preset = QtWidgets.QComboBox()
        self.preset.addItem(PLACEHOLDER)
        for height in ISO_HEIGHTS_MM:
            self.preset.addItem("%g mm" % height)
        form.addRow("Standard height (ISO 3098):", self.preset)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        self.dialog = dialog
        self._show_height()
        self.height.valueChanged.connect(self._height_edited)
        self.unit.currentIndexChanged.connect(self._unit_changed)
        self.preset.currentIndexChanged.connect(self._preset_chosen)

    def _show_height(self):
        self.height.blockSignals(True)
        try:
            self.height.setValue(_to_unit(self._height_mm, self._unit))
        finally:
            self.height.blockSignals(False)

    def _show_placeholder(self):
        self.preset.blockSignals(True)
        try:
            self.preset.setCurrentIndex(0)
        finally:
            self.preset.blockSignals(False)

    @console.guarded("take over the typed text height", level="log")
    def _height_edited(self, value):
        self._height_mm = _from_unit(value, self._unit)
        index = self.preset.currentIndex()
        if index > 0 and abs(ISO_HEIGHTS_MM[index - 1] - self._height_mm) > 1e-3:
            self._show_placeholder()

    @console.guarded("change the unit of the text height", level="log")
    def _unit_changed(self, index):
        if 0 <= index < len(UNITS):
            self._unit = UNITS[index]
            self._show_height()

    @console.guarded("use the chosen ISO 3098 height", level="log")
    def _preset_chosen(self, index):
        if 0 < index <= len(ISO_HEIGHTS_MM):
            self._height_mm = float(ISO_HEIGHTS_MM[index - 1])
            self._show_height()

    def _ok(self):
        self._accepted = True
        self.dialog.accept()

    def run(self):
        """Show the dialog; (text, height_mm, unit) when OK was pressed, else None."""
        try:
            self.dialog.exec()
            if not self._accepted:
                return None
            return self.text.text(), self._height_mm, self._unit
        finally:
            self.dialog.deleteLater()


def _ask(text, height_mm):
    """Ask for text and height; (text, height_mm) to apply, or None if nothing should change."""
    result = _TextDialog(text, height_mm, _last_unit()).run()
    if result is None:
        return None
    text, height_mm, unit = result
    if not text.strip() or height_mm <= 0:
        return None
    _remember(height_mm, unit)
    return text, height_mm


# --- create and edit -------------------------------------------------------------------------------


def _is_jellyjams_text(obj):
    try:
        return obj.TypeId == constants.TYPE_ANNOTATION and constants.PROP_SHEET_NOTE in obj.PropertiesList
    except Exception:
        return False


def _selected_text():
    for obj in fcgui.selection():
        if _is_jellyjams_text(obj):
            return obj
    return None


def _edit_text(obj):
    answer = _ask(LINE_BREAK.join(str(line) for line in obj.Text), _number(obj.TextSize))
    if answer is None:
        return
    text, height_mm = answer
    doc = obj.Document
    try:
        with doc_utils.transaction(doc, TEXT_STEP, abort_on_error=True):
            obj.Text = split_lines(text)
            obj.TextSize = height_mm
            doc.recompute()
    except Exception:
        console.error("the text was left unchanged because of an error", with_traceback=True)


def _create_text(page, x, y, text, height_mm):
    doc = page.Document
    try:
        with doc_utils.transaction(doc, TEXT_STEP, abort_on_error=True):
            annotation = doc.addObject(constants.TYPE_ANNOTATION, TEXT_NAME)
            doc_utils.add_property(
                annotation,
                "App::PropertyBool",
                constants.PROP_SHEET_NOTE,
                tooltip="True for texts created with the JellyJams Text command",
            )
            setattr(annotation, constants.PROP_SHEET_NOTE, True)
            annotation.Text = split_lines(text)
            annotation.TextSize = height_mm
            page.addView(annotation)
            annotation.X, annotation.Y = x, y
            doc.recompute()
    except Exception:
        console.error("the new text was not added because of an error", with_traceback=True)


def _new_text_at(page_key, x, y):
    doc = FreeCAD.listDocuments().get(page_key[0])
    page = doc.getObject(page_key[1]) if doc is not None else None
    if not doc_utils.is_derived(page, constants.TYPE_PAGE):
        return
    answer = _ask("", _last_height_mm())
    if answer is not None:
        _create_text(page, x, y, *answer)


def _page_of_window():
    from jellyjams import drawing_common

    return drawing_common.page_of_active_window()


def _start_placing():
    window = fcgui.active_sheet_window()
    page = _page_of_window() if window is not None else None
    if page is None:
        fcgui.status_message(NOT_A_SHEET_HINT, HINT_MS)
        return
    page_key = (page.Document.Name, page.Name)

    def on_click(x, y):
        # A modal dialog must not open inside the mouse event; wait until the click is done.
        fcgui.defer(lambda: _new_text_at(page_key, x, y))
        return False

    from jellyjams import sheet_pick

    if not sheet_pick.start(window, on_click, status=PICK_HINT, owner=PICK_OWNER):
        fcgui.status_message(NOT_A_SHEET_HINT, HINT_MS)


class NoteCommand(commands.BaseCommand):
    command_id = constants.CMD_NOTE
    menu_text = "Text"
    tooltip = (
        "Text: click a spot on the sheet and type. With a JellyJams text selected, it edits "
        "that text instead. Esc cancels."
    )

    def is_active(self):
        from jellyjams import drawing_common

        return drawing_common.drawing_tools_enabled()

    def run(self):
        selected = _selected_text()
        if selected is not None:
            _edit_text(selected)
        else:
            _start_placing()


def get_commands():
    """Command table of this module: JellyJams_Note."""
    return {constants.CMD_NOTE: NoteCommand()}
