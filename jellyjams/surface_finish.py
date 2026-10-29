# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_SurfaceFinish: ISO 1302 surface finish symbols on TechDraw sheets.

Each symbol is a plain TechDraw::DrawViewSymbol carrying SVG generated here.
Fields a to e are SVG editable texts, so FreeCAD without JellyJams can still
edit them through EditableTexts. The material-removal type and the
all-around flag live in MaterialRemoval and AllAroundOutline.

weld_symbol reuses the helpers in the "shared by the symbol modules" part:
XML escaping, number formatting, the undo step that lasts as long as a task
panel, and opening a task panel.
"""

import math
import re
import xml.etree.ElementTree as ElementTree
from xml.sax.saxutils import escape

import FreeCAD

from jellyjams import commands, console, constants, doc_utils, fcgui

FREECAD_SVG_NS = "https://www.freecad.org/wiki/index.php?title=Svg_Namespace"
SVG_NS = "http://www.w3.org/2000/svg"

SYMBOL_TYPE = constants.TYPE_SYMBOL
PROPERTY_GROUP = constants.PROP_GROUP
NAME_BASE = "SurfaceFinish"
LABEL = "Surface Finish"
UNDO_CREATE = "Surface Finish"
UNDO_EDIT = "Edit Surface Finish"
STACK_ORDER = 110
OFFSET_FROM_VIEW = (25.0, 15.0)
DEFAULT_CENTER = (105.0, 148.5)

DEFAULT_DATA = {"type": "any", "all_around": False, "a": "Rz 16", "b": "", "c": "", "d": "", "e": ""}
TEXT_FIELDS = ("a", "b", "c", "d", "e")

SURFACE_TYPES = (
    ("any", "Any process (basic symbol)"),
    ("required", "Machined: material must be removed"),
    ("prohibited", "No material removal (surface left as supplied)"),
)
# Grouped by parameter, each ascending; ISO 1302 prescribes no order.
QUICK_VALUES = ("Rz 4", "Rz 6.3", "Rz 16", "Rz 25", "Rz 63",
                "Ra 0.8", "Ra 1.6", "Ra 3.2", "Ra 6.3", "Ra 12.5")
LAY_CHOICES = (
    ("", "(none)"),
    ("=", "= parallel to the plane of projection"),
    ("⊥", "⊥ perpendicular to the plane of projection"),
    ("X", "X crossing in two oblique directions"),
    ("M", "M multidirectional"),
    ("C", "C roughly circular around the center"),
    ("R", "R roughly radial from the center"),
    ("P", "P particulate, no direction"),
)
ROTATION_CHOICES = ("0", "90", "180", "270")

# Units match FreeCAD's own surface finish symbol: 1 SVG unit is 1 px, text is 18 px osifont.
FONT_SIZE = 18.0
CHAR_WIDTH = 9.25
TEXT_ASCENT = 14.0
TEXT_DESCENT = 4.0
SHORT_LEG_HEIGHT = 24.0
LONG_LEG_HEIGHT = 60.0  # 2.5 x the short leg
LEG_RUN = 1.0 / math.tan(math.radians(60.0))
MIN_LINE = 30.0
LINE_MARGIN = 8.0
TEXT_GAP = 3.0
ALL_AROUND_SHIFT = 5.0
ALL_AROUND_RADIUS = 6.0
PROHIBITED_RADIUS = 9.0
CANVAS_PAD = 2.0

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


# --- shared by the symbol modules -------------------------------------------------------------


def xml_text(value):
    """`value` made safe as XML text: control characters removed, &, < and > escaped."""
    text = "" if value is None else str(value)
    text = _CONTROL_CHARS.sub("", text).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return escape(text)


def fmt(value):
    """A number for SVG output, rounded to 3 decimals without trailing zeros."""
    text = ("%.3f" % float(value)).rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def number(value, default=0.0):
    """A float from a Quantity, a number or numeric text; `default` if none of these."""
    try:
        return float(getattr(value, "Value", value))
    except Exception:
        return default


def _svg_signature(svg_text):
    root = ElementTree.fromstring(str(svg_text).encode("utf-8"))
    signature = []
    for element in root.iter():
        attributes = tuple(sorted((key, value) for key, value in element.attrib.items()
                                  if key != _XML_SPACE))
        text = element.text if element.text and element.text.strip() else ""
        signature.append((element.tag, attributes, text))
    return signature


def same_svg(stored, built):
    """True if two SVG texts describe the same drawing.

    FreeCAD rewrites a symbol's SVG on assignment (attribute order, indentation,
    xml:space on editable spans), so comparing the strings directly never matches.
    """
    if stored == built:
        return True
    try:
        return _svg_signature(stored) == _svg_signature(built)
    except Exception:
        return False


def kind_of(obj):
    """The object's SymbolType value, or "" if it has none."""
    try:
        return str(getattr(obj, constants.PROP_SYMBOL_TYPE, "") or "")
    except Exception:
        return ""


def selected_symbol(kind):
    """The first selected symbol with SymbolType == `kind`, or None."""
    for obj in fcgui.selection():
        if doc_utils.is_derived(obj, SYMBOL_TYPE) and kind_of(obj) == kind:
            return obj
    return None


def target_sheet(doc):
    """The sheet that receives a new symbol (drawing-symbols 2.3), or None."""
    try:
        from jellyjams import drawing_common

        return drawing_common.target_sheet(doc, use_active_window=False)
    except Exception as exc:
        console.log("no sheet found for the new symbol: %s" % exc)
        return None


def sheet_center(page):
    """Middle of `page` in sheet mm; (105, 148.5) if the template gives no size."""
    try:
        from jellyjams import drawing_common

        x, y = drawing_common.sheet_center(page, DEFAULT_CENTER)
        return float(x), float(y)
    except Exception:
        return DEFAULT_CENTER


def drawing_tools_enabled():
    from jellyjams import drawing_common

    return drawing_common.drawing_tools_enabled()


def set_stack_order(obj, order=STACK_ORDER):
    """Put `obj` on the dimension layer, above the drawing views."""
    with console.guard("raise %s above the views" % getattr(obj, "Name", "the symbol"),
                       level="log"):
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None and "StackOrder" in view_object.PropertiesList:
            view_object.StackOrder = order


class UndoStep:
    """An undo step that stays open while a task panel is up and is closed exactly once.

    FreeCAD commits a document transaction when the command that opened it returns, but
    this step has to last until OK or Cancel, so it is a persistent application transaction.
    """

    def __init__(self, doc, name):
        self.doc = doc
        self.name = name
        self._id = 0
        self._application = True
        try:
            self._id = int(FreeCAD.setActiveTransaction(name, True) or 0)
        except Exception:
            self._application = False
            doc.openTransaction(name)
        self._open = True

    def close(self, abort):
        """Commit the step, or roll it back when `abort` is true. Repeat calls are ignored."""
        if not self._open:
            return
        self._open = False
        with console.guard("finish the undo step %r" % self.name, level="log"):
            if self._application:
                args = (bool(abort), self._id) if self._id else (bool(abort),)
                FreeCAD.closeActiveTransaction(*args)
            elif abort:
                self.doc.abortTransaction()
            else:
                self.doc.commitTransaction()


def recompute(doc):
    with console.guard("update the drawing", level="log"):
        doc.recompute()


def show_panel(panel):
    """Put `panel` in the task view. False if a task dialog is already open or showing fails."""
    if fcgui.task_dialog_open():
        return False
    try:
        import FreeCADGui

        FreeCADGui.Control.showDialog(panel)
    except Exception as exc:
        console.error("the %s panel did not open: %s" % (getattr(panel, "title", "task"), exc))
        return False
    return True


def open_in_undo_step(doc, undo_name, make_object, panel_class):
    """Inside a new undo step, call make_object() and show panel_class(obj, undo).

    Returns the panel, which closes the step on OK or Cancel. If the panel cannot be shown,
    the step is rolled back (so a just-created object is removed) and None is returned.
    """
    undo = UndoStep(doc, undo_name)
    try:
        panel = panel_class(make_object(), undo)
        opened = show_panel(panel)
    except Exception:
        undo.close(abort=True)
        recompute(doc)
        raise
    if opened:
        return panel
    undo.close(abort=True)
    recompute(doc)
    return None


# --- pure helpers -----------------------------------------------------------------------------


def parse_rotation(text):
    """Degrees parsed from user text (comma accepted as decimal point); 0 if not a number."""
    cleaned = str(text if text is not None else "").strip().replace("°", "").replace(",", ".")
    cleaned = cleaned.replace(" ", "")
    try:
        value = float(cleaned)
    except ValueError:
        return 0.0
    return value if math.isfinite(value) else 0.0


def format_angle(value):
    """An angle as display text without trailing zeros ("90", "12.5")."""
    text = ("%.6f" % number(value)).rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def lay_character(text):
    """The value for field d: a full lay menu entry becomes just its symbol."""
    stripped = str(text or "").strip()
    for character, label in LAY_CHOICES:
        if stripped == label:
            return character
    return stripped


def normalized(data):
    """`data` with every key filled in; an unknown type becomes "any", fields become text."""
    result = dict(DEFAULT_DATA)
    if isinstance(data, dict):
        result.update({key: data[key] for key in DEFAULT_DATA if key in data})
    if result["type"] not in [key for key, _label in SURFACE_TYPES]:
        result["type"] = "any"
    result["all_around"] = bool(result["all_around"])
    for field in TEXT_FIELDS:
        value = result[field]
        result[field] = "" if value is None else str(value)
    return result


def _text_width(text):
    return len(text) * CHAR_WIDTH


class _Bounds:
    def __init__(self):
        self.left = self.top = math.inf
        self.right = self.bottom = -math.inf

    def add(self, left, top, right, bottom):
        self.left = min(self.left, left)
        self.top = min(self.top, top)
        self.right = max(self.right, right)
        self.bottom = max(self.bottom, bottom)

    def add_point(self, x, y):
        self.add(x, y, x, y)


def build_svg(data):
    """SVG text of the ISO 1302 symbol for `data`; editable texts a to e, in that order."""
    data = normalized(data)
    all_around = data["all_around"]

    # Origin is the point where the symbol touches the surface; SVG y grows downward.
    short_top = (-SHORT_LEG_HEIGHT * LEG_RUN, -SHORT_LEG_HEIGHT)
    corner = (LONG_LEG_HEIGHT * LEG_RUN, -LONG_LEG_HEIGHT)
    shift = ALL_AROUND_SHIFT if all_around else 0.0
    widest = max(_text_width(data[field]) for field in ("a", "b", "c"))
    line_length = max(MIN_LINE, widest + LINE_MARGIN) + shift
    line_end = (corner[0] + line_length, corner[1])
    text_x = corner[0] + TEXT_GAP + shift

    texts = {
        "a": (text_x, corner[1] + 20.0, "start"),
        "b": (text_x, corner[1] + 42.0, "start"),
        "c": (text_x, corner[1] - 6.0, "start"),
        "d": (9.0, 14.0, "start"),
        "e": (short_top[0] - 4.0, -6.0, "end"),
    }

    bounds = _Bounds()
    for point in ((0.0, 0.0), short_top, corner, line_end):
        bounds.add_point(*point)
    # Keep room for c (over the line) and d (under the root) even when empty, so text added
    # later through the Property view is not cut off.
    bounds.add_point(text_x, texts["c"][1] - TEXT_ASCENT)
    bounds.add_point(texts["d"][0], texts["d"][1] + TEXT_DESCENT)
    for field, (x, y, anchor) in texts.items():
        width = _text_width(data[field])
        if not width:
            continue
        left = x - width if anchor == "end" else x
        bounds.add(left, y - TEXT_ASCENT, left + width, y + TEXT_DESCENT)

    shapes = [
        "M %s %s L 0 0 L %s %s L %s %s" % (fmt(short_top[0]), fmt(short_top[1]), fmt(corner[0]),
                                           fmt(corner[1]), fmt(line_end[0]), fmt(line_end[1]))
    ]
    circles = []
    if data["type"] == "required":
        bar_end = SHORT_LEG_HEIGHT * LEG_RUN
        shapes.append("M %s %s L %s %s" % (fmt(short_top[0]), fmt(short_top[1]), fmt(bar_end),
                                           fmt(short_top[1])))
    elif data["type"] == "prohibited":
        # Circle touches both legs; each leg leans 30 degrees from vertical.
        center = (0.0, -2.0 * PROHIBITED_RADIUS)
        circles.append((center, PROHIBITED_RADIUS))
    if all_around:
        circles.append((corner, ALL_AROUND_RADIUS))
    for (cx, cy), radius in circles:
        bounds.add(cx - radius, cy - radius, cx + radius, cy + radius)

    left = bounds.left - CANVAS_PAD
    top = bounds.top - CANVAS_PAD
    width = bounds.right - bounds.left + 2 * CANVAS_PAD
    height = bounds.bottom - bounds.top + 2 * CANVAS_PAD

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="%s" xmlns:freecad="%s" version="1.1" width="%s" height="%s" '
        'viewBox="%s %s %s %s">' % (SVG_NS, FREECAD_SVG_NS, fmt(width), fmt(height), fmt(left),
                                    fmt(top), fmt(width), fmt(height)),
        '  <g fill="none" stroke="#000000" stroke-width="1" stroke-linecap="round" '
        'stroke-linejoin="round">',
    ]
    lines += ['    <path d="%s"/>' % path for path in shapes]
    lines += ['    <circle cx="%s" cy="%s" r="%s"/>' % (fmt(cx), fmt(cy), fmt(radius))
              for (cx, cy), radius in circles]
    lines += [
        "  </g>",
        '  <g font-family="osifont" font-size="%s" fill="#000000" stroke="none">' % fmt(FONT_SIZE),
    ]
    for field in TEXT_FIELDS:
        x, y, anchor = texts[field]
        lines.append(
            '    <text freecad:editable="%s" x="%s" y="%s" text-anchor="%s"><tspan>%s</tspan>'
            "</text>" % (field, fmt(x), fmt(y), anchor, xml_text(data[field]))
        )
    lines += ["  </g>", "</svg>", ""]
    return "\n".join(lines)


# --- document side ----------------------------------------------------------------------------


def _ensure_properties(obj):
    doc_utils.add_property(obj, "App::PropertyString", constants.PROP_SYMBOL_TYPE, PROPERTY_GROUP,
                           "Which JellyJams symbol this is")
    doc_utils.add_property(obj, "App::PropertyString", constants.PROP_MATERIAL_REMOVAL,
                           PROPERTY_GROUP, "Material removal: any, required or prohibited")
    doc_utils.add_property(obj, "App::PropertyBool", constants.PROP_ALL_AROUND,
                           PROPERTY_GROUP, "Requirement applies all around the outline")


def read_data(obj):
    """Current symbol data: type and flag from properties, fields from EditableTexts."""
    data = dict(DEFAULT_DATA)
    data["type"] = str(getattr(obj, constants.PROP_MATERIAL_REMOVAL, "any") or "any")
    data["all_around"] = bool(getattr(obj, constants.PROP_ALL_AROUND, False))
    try:
        texts = list(obj.EditableTexts)
    except Exception:
        texts = []
    for index, field in enumerate(TEXT_FIELDS):
        if index < len(texts):
            data[field] = str(texts[index])
    return normalized(data)


def write_data(obj, data, rotation=None):
    """Write `data` to the symbol (SVG and properties), plus the rotation in degrees if given."""
    data = normalized(data)
    _ensure_properties(obj)
    svg = build_svg(data)
    if not same_svg(obj.Symbol, svg):
        obj.Symbol = svg
    if getattr(obj, constants.PROP_SYMBOL_TYPE) != constants.KIND_SURFACE:
        setattr(obj, constants.PROP_SYMBOL_TYPE, constants.KIND_SURFACE)
    if getattr(obj, constants.PROP_MATERIAL_REMOVAL) != data["type"]:
        setattr(obj, constants.PROP_MATERIAL_REMOVAL, data["type"])
    if bool(getattr(obj, constants.PROP_ALL_AROUND)) != data["all_around"]:
        setattr(obj, constants.PROP_ALL_AROUND, data["all_around"])
    if rotation is not None and abs(number(obj.Rotation) - rotation) > 1e-9:
        obj.Rotation = rotation


def _sheet_position(obj):
    """A view's position on the sheet; projections store X/Y relative to their group."""
    x, y = number(obj.X), number(obj.Y)
    if doc_utils.is_derived(obj, constants.TYPE_PROJ_ITEM):
        for parent in getattr(obj, "InList", []) or []:
            if doc_utils.is_derived(parent, constants.TYPE_PROJ_GROUP):
                return x + number(parent.X), y + number(parent.Y)
    return x, y


def _insert_position(page):
    for obj in fcgui.selection():
        try:
            if kind_of(obj) == constants.KIND_SURFACE:
                continue
            if "X" in obj.PropertiesList and "Y" in obj.PropertiesList:
                x, y = _sheet_position(obj)
                return x + OFFSET_FROM_VIEW[0], y + OFFSET_FROM_VIEW[1]
        except Exception:
            continue
    return sheet_center(page)


def create_symbol(doc, page, position):
    """Place a surface finish symbol with default content on `page` at `position` (mm)."""
    obj = doc.addObject(SYMBOL_TYPE, NAME_BASE)
    obj.Label = LABEL
    _ensure_properties(obj)
    setattr(obj, constants.PROP_SYMBOL_TYPE, constants.KIND_SURFACE)
    setattr(obj, constants.PROP_MATERIAL_REMOVAL, DEFAULT_DATA["type"])
    setattr(obj, constants.PROP_ALL_AROUND, DEFAULT_DATA["all_around"])
    obj.ScaleType = "Custom"
    obj.Symbol = build_svg(DEFAULT_DATA)
    page.addView(obj)
    obj.X, obj.Y = position
    obj.Rotation = 0.0
    set_stack_order(obj)
    recompute(doc)
    return obj


# --- task panel -------------------------------------------------------------------------------


class SurfaceFinishPanel:
    """Task panel for one surface finish symbol; every change shows on the sheet at once."""

    title = "Surface Finish"

    def __init__(self, obj, undo):
        self.obj = obj
        self.doc = obj.Document
        self.undo = undo
        self._loading = True
        self._closed = False
        self.form = self._build()
        self._load()
        self._loading = False

    def _build(self):
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        form = QtWidgets.QWidget()
        form.setObjectName(constants.OBJ_SURFACE_FINISH)
        form.setWindowTitle(self.title)
        layout = QtWidgets.QFormLayout(form)

        self.type_combo = QtWidgets.QComboBox(form)
        for key, label in SURFACE_TYPES:
            self.type_combo.addItem(label, key)
        layout.addRow("Symbol", self.type_combo)

        self.all_around_check = QtWidgets.QCheckBox(
            "All around (every surface of the outline)", form)
        layout.addRow(self.all_around_check)

        self.a_combo = QtWidgets.QComboBox(form)
        self.a_combo.setEditable(True)
        self.a_combo.addItems(list(QUICK_VALUES))
        self.a_combo.setToolTip("Choose a common roughness value or type your own")
        layout.addRow("Parameter and value (a)", self.a_combo)

        self.b_edit = QtWidgets.QLineEdit(form)
        layout.addRow("Second requirement (b)", self.b_edit)

        self.c_edit = QtWidgets.QLineEdit(form)
        self.c_edit.setPlaceholderText("such as milled")
        layout.addRow("Manufacturing method (c)", self.c_edit)

        self.d_combo = QtWidgets.QComboBox(form)
        self.d_combo.setEditable(True)
        for character, label in LAY_CHOICES:
            self.d_combo.addItem(label, character)
        layout.addRow("Surface lay (d)", self.d_combo)

        self.e_edit = QtWidgets.QLineEdit(form)
        self.e_edit.setPlaceholderText("such as 0.3")
        layout.addRow("Machining allowance in mm (e)", self.e_edit)

        self.rotation_combo = QtWidgets.QComboBox(form)
        self.rotation_combo.setEditable(True)
        self.rotation_combo.addItems(list(ROTATION_CHOICES))
        layout.addRow("Rotation angle (°)", self.rotation_combo)

        hint = QtWidgets.QLabel(
            "To edit later, double-click the symbol on the sheet, or change its texts in "
            "the Property view under Data › EditableTexts.", form)
        hint.setWordWrap(True)
        layout.addRow(hint)

        self.type_combo.currentIndexChanged.connect(self._changed)
        self.all_around_check.toggled.connect(self._changed)
        self.a_combo.editTextChanged.connect(self._changed)
        self.b_edit.textChanged.connect(self._changed)
        self.c_edit.textChanged.connect(self._changed)
        self.d_combo.activated.connect(self._lay_picked)
        self.d_combo.editTextChanged.connect(self._changed)
        self.e_edit.textChanged.connect(self._changed)
        self.rotation_combo.editTextChanged.connect(self._changed)
        return form

    def _load(self):
        data = read_data(self.obj)
        index = self.type_combo.findData(data["type"])
        self.type_combo.setCurrentIndex(max(index, 0))
        self.all_around_check.setChecked(data["all_around"])
        self.a_combo.setEditText(data["a"])
        self.b_edit.setText(data["b"])
        self.c_edit.setText(data["c"])
        self.d_combo.setEditText(data["d"])
        self.e_edit.setText(data["e"])
        self.rotation_combo.setEditText(format_angle(self.obj.Rotation))

    def collect(self):
        """What the panel currently shows, as a data dict."""
        return normalized({
            "type": self.type_combo.currentData() or "any",
            "all_around": self.all_around_check.isChecked(),
            "a": self.a_combo.currentText(),
            "b": self.b_edit.text(),
            "c": self.c_edit.text(),
            "d": lay_character(self.d_combo.currentText()),
            "e": self.e_edit.text(),
        })

    def _lay_picked(self, index):
        try:
            character = self.d_combo.itemData(index)
            self.d_combo.setEditText(character or "")
        except Exception as exc:
            console.log("surface lay choice not applied: %s" % exc)

    def _changed(self, *_args):
        if self._loading or self._closed:
            return
        self.apply()

    def apply(self):
        """Copy the panel values to the symbol and recompute; errors only go to the log."""
        try:
            if not doc_utils.is_alive(self.obj):
                return
            write_data(self.obj, self.collect(), parse_rotation(self.rotation_combo.currentText()))
            self.doc.recompute()
        except Exception as exc:
            console.log("surface finish preview not updated: %s" % exc)

    def accept(self):
        if not self._closed:
            self.apply()
            self._closed = True
            self.undo.close(abort=False)
        return True

    def reject(self):
        if not self._closed:
            self._closed = True
            self.undo.close(abort=True)
            recompute(self.doc)
        return True


def open_editor(obj):
    """Show the panel for an existing surface finish symbol. Returns False when it stays
    closed: a task dialog is already open, or `obj` is not a JellyJams surface finish."""
    try:
        if fcgui.task_dialog_open() or kind_of(obj) != constants.KIND_SURFACE:
            return False
        panel = open_in_undo_step(obj.Document, UNDO_EDIT, lambda: obj, SurfaceFinishPanel)
        return panel is not None
    except Exception as exc:
        console.error("surface finish editor failed: %s" % exc, with_traceback=True)
        return False


def create_and_edit(doc, page, position):
    """Add a symbol and show its panel in one undo step; True if the panel is showing."""
    panel = open_in_undo_step(doc, UNDO_CREATE, lambda: create_symbol(doc, page, position),
                              SurfaceFinishPanel)
    return panel is not None


# --- command ----------------------------------------------------------------------------------


class SurfaceFinishCommand(commands.BaseCommand):
    command_id = constants.CMD_SURFACE_FINISH
    menu_text = "Surface Finish"
    tooltip = ("Places an ISO 1302 surface finish symbol, with common Rz and Ra values "
               "ready to pick. Double-click it on the sheet to change it.")

    def run(self):
        doc = FreeCAD.ActiveDocument
        if doc is None or fcgui.task_dialog_open():
            return
        existing = selected_symbol(constants.KIND_SURFACE)
        if existing is not None:
            open_editor(existing)
            return
        page = target_sheet(doc)
        if page is None:
            return
        create_and_edit(doc, page, _insert_position(page))

    def is_active(self):
        return drawing_tools_enabled()


def get_commands():
    return {constants.CMD_SURFACE_FINISH: SurfaceFinishCommand()}
