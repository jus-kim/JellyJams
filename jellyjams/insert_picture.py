# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Insert Picture (JellyJams_InsertPicture): put an SVG, PNG, JPG or BMP file on a drawing sheet.

An SVG becomes a TechDraw symbol, so it stays vector in PDF output. A bitmap becomes a
TechDraw image whose file is embedded in the document. TechDraw only knows a scale factor;
the panel shows a width in mm instead, computed from the picture's size at scale 1.
"""

import math
import os
import re

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

from jellyjams import commands, console, constants, fcgui

INSERT_STEP = "Insert Picture"
EDIT_STEP = "Edit Picture"
PICTURE_NAME = "Picture"
FILE_FILTERS = "Pictures (*.svg *.png *.jpg *.jpeg *.bmp);;SVG (*.svg);;PNG / JPG (*.png *.jpg *.jpeg)"
SVG_SUFFIX = ".svg"
BITMAP_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")
INITIAL_WIDTH_SHARE = 0.25   # a new picture covers at most a quarter of the sheet width
SYNC_MS = 200
SYNC_TOLERANCE = 0.05
PLACEHOLDER = "–"
DEFAULT_REZ = 10.0
POSITION_TOOLTIP = "Centre of the picture, in mm from the lower-left corner of the sheet."

PX_PER_UNIT = {
    "": 1.0,
    "px": 1.0,
    "pt": 96.0 / 72.0,
    "pc": 16.0,
    "in": 96.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
}

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ROOT = re.compile(r"""<(?:[\w.-]+:)?svg\b((?:[^>"']|"[^"]*"|'[^']*')*)>""")
_ATTRIBUTE = re.compile(r"""([\w:.-]+)\s*=\s*(["'])(.*?)\2""", re.DOTALL)
_LENGTH = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z%]*)\s*$")

_panel = None


class PictureError(Exception):
    """The chosen file cannot become a picture; reported without a traceback."""


# --- size model ----------------------------------------------------------------------------------


def _valid_rez(rez):
    try:
        rez = float(rez)
    except (TypeError, ValueError):
        return DEFAULT_REZ
    return rez if rez > 0 and math.isfinite(rez) else DEFAULT_REZ


def _root_attributes(svg_text):
    match = _ROOT.search(_COMMENT.sub("", str(svg_text or "")))
    if match is None:
        return None
    return {name: value for name, _quote, value in _ATTRIBUTE.findall(match.group(1))}


def _length(text):
    """(number, unit) of an SVG length like "12.5mm"; None if missing or malformed."""
    match = _LENGTH.match(text or "")
    if match is None:
        return None
    return float(match.group(1)), match.group(2).lower()


def _view_box_size(text):
    parts = [part for part in re.split(r"[\s,]+", (text or "").strip()) if part]
    if len(parts) != 4:
        return None
    try:
        width, height = float(parts[2]), float(parts[3])
    except ValueError:
        return None
    return (width, height) if width > 0 and height > 0 else None


def svg_natural_size(svg_text, rez):
    """Size in mm (width, height) that TechDraw gives an SVG at scale 1; None if unknown."""
    attributes = _root_attributes(svg_text)
    if attributes is None:
        return None
    rez = _valid_rez(rez)
    view_box = _view_box_size(attributes.get("viewBox"))
    by_view_box = (view_box[0] / rez, view_box[1] / rez) if view_box else None
    width = _length(attributes.get("width"))
    height = _length(attributes.get("height"))
    if height is not None and height[1] == "mm" and view_box:
        return view_box
    if width is None or height is None:
        return by_view_box
    if "%" in (width[1], height[1]):
        return by_view_box
    if width[1] not in PX_PER_UNIT or height[1] not in PX_PER_UNIT:
        return None
    width_px = width[0] * PX_PER_UNIT[width[1]]
    height_px = height[0] * PX_PER_UNIT[height[1]]
    if width_px <= 0 or height_px <= 0:
        return None
    return (width_px / rez, height_px / rez)


def bitmap_natural_size(px_w, px_h, rez):
    """Size in mm (width, height) of a bitmap at scale 1, i.e. its pixel counts divided by Rez."""
    rez = _valid_rez(rez)
    return (float(px_w) / rez, float(px_h) / rez)


def initial_scale(natural_w, sheet_w):
    """Starting scale: 1, or less when needed to keep the picture within
    INITIAL_WIDTH_SHARE of the sheet width.

    Returns 1 when either width is missing or not a positive number.
    """
    try:
        natural_w, sheet_w = float(natural_w), float(sheet_w)
    except (TypeError, ValueError):
        return 1.0
    if not (natural_w > 0 and sheet_w > 0 and math.isfinite(natural_w) and math.isfinite(sheet_w)):
        return 1.0
    return min(1.0, INITIAL_WIDTH_SHARE * sheet_w / natural_w)


def _bitmap_pixels(path):
    size = QtGui.QImageReader(path).size()
    if size.width() > 0 and size.height() > 0:
        return size.width(), size.height()
    return None


def _natural_size(picture):
    try:
        if picture.TypeId == constants.TYPE_SYMBOL:
            return svg_natural_size(picture.Symbol, fcgui.rez())
        pixels = _bitmap_pixels(picture.ImageFile)
        return bitmap_natural_size(pixels[0], pixels[1], fcgui.rez()) if pixels else None
    except Exception:
        return None


# --- pictures in the document ------------------------------------------------------------------


def _number(value):
    return float(getattr(value, "Value", value))


def _is_picture(obj):
    try:
        if obj.TypeId == constants.TYPE_IMAGE:
            return True
        return obj.TypeId == constants.TYPE_SYMBOL and not getattr(obj, constants.PROP_SYMBOL_TYPE, "")
    except Exception:
        return False


def _selected_picture():
    for obj in fcgui.selection():
        if _is_picture(obj):
            return obj
    return None


def _read_picture(path):
    """("svg", text, natural size) or ("bitmap", path, natural size); raises PictureError."""
    suffix = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if suffix == SVG_SUFFIX:
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                content = handle.read()
        except UnicodeDecodeError:
            raise PictureError("the SVG file %s is not UTF-8 encoded" % name) from None
        except OSError as exc:
            raise PictureError("reading %s failed: %s" % (name, exc.strerror or exc)) from None
        return "svg", content, svg_natural_size(content, fcgui.rez())
    if suffix in BITMAP_SUFFIXES:
        try:
            with open(path, "rb") as handle:
                handle.read(1)
        except OSError as exc:
            raise PictureError("reading %s failed: %s" % (name, exc.strerror or exc)) from None
        pixels = _bitmap_pixels(path)
        natural = bitmap_natural_size(pixels[0], pixels[1], fcgui.rez()) if pixels else None
        return "bitmap", path, natural
    raise PictureError("%s has an unsupported file type; use SVG, PNG, JPG or BMP" % name)


def _sheet_size(page):
    from jellyjams import drawing_common

    return drawing_common.sheet_size(page)


def _open_undo_step(doc, name):
    """An undo step that stays open across the panel's lifetime (see surface_finish.UndoStep)."""
    from jellyjams import surface_finish

    return surface_finish.UndoStep(doc, name)


def _add_picture(page, kind, data, natural):
    doc = page.Document
    size = _sheet_size(page)
    if kind == "svg":
        picture = doc.addObject(constants.TYPE_SYMBOL, PICTURE_NAME)
        picture.Symbol = data
    else:
        picture = doc.addObject(constants.TYPE_IMAGE, PICTURE_NAME)
        picture.ImageFile = data
    picture.ScaleType = "Custom"
    picture.Scale = initial_scale(natural[0] if natural else None, size[0] if size else None)
    page.addView(picture)
    if size:
        picture.X, picture.Y = size[0] / 2.0, size[1] / 2.0
    doc.recompute()
    return picture


def _ask_file(doc):
    folder = os.path.dirname(doc.FileName or "") or os.path.expanduser("~")
    path, _chosen_filter = QtWidgets.QFileDialog.getOpenFileName(
        fcgui.main_window(), "Insert Picture", folder, FILE_FILTERS
    )
    return path


# --- panel -------------------------------------------------------------------------------------


def _spin(minimum, maximum, suffix):
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(1)
    spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


class PicturePanel:
    """Task panel bound to one picture.

    The fields follow the picture (re-read every SYNC_MS) and write back only what the user
    edits. OK commits the undo step `undo`, Cancel rolls it back.
    """

    def __init__(self, picture, created, undo):
        self._doc_name = picture.Document.Name
        self._name = picture.Name
        self._created = created
        self._undo = undo
        self._before = None if created else self._values(picture)
        self._natural = _natural_size(picture)
        self.form = self._build()
        self._timer = QtCore.QTimer(self.form)
        self._timer.setInterval(SYNC_MS)
        self._timer.timeout.connect(self._sync)
        self._sync()
        self._timer.start()

    # -- widgets --

    def _build(self):
        form = QtWidgets.QWidget()
        form.setObjectName(constants.OBJ_PICTURE_FORM)
        form.setWindowTitle("Insert Picture")
        layout = QtWidgets.QFormLayout(form)
        self.x = _spin(-2000.0, 2000.0, " mm")
        self.y = _spin(-2000.0, 2000.0, " mm")
        self.width = _spin(0.1, 5000.0, " mm")
        self.width.setEnabled(self._natural is not None)
        self.height = QtWidgets.QLabel(PLACEHOLDER)
        self.rotation = _spin(-360.0, 360.0, " °")
        layout.addRow("Position X (centre):", self.x)
        layout.addRow("Position Y (centre):", self.y)
        layout.addRow("Width:", self.width)
        layout.addRow("Height:", self.height)
        layout.addRow("Rotation:", self.rotation)
        for spin in (self.x, self.y):
            spin.setToolTip(POSITION_TOOLTIP)
        self.x.valueChanged.connect(lambda value: self._write("X", value))
        self.y.valueChanged.connect(lambda value: self._write("Y", value))
        self.rotation.valueChanged.connect(lambda value: self._write("Rotation", value))
        self.width.valueChanged.connect(self._write_width)
        return form

    # -- picture access --

    def _document(self):
        return FreeCAD.listDocuments().get(self._doc_name)

    def _picture(self):
        doc = self._document()
        return doc.getObject(self._name) if doc is not None else None

    @staticmethod
    def _values(picture):
        return {name: _number(getattr(picture, name)) for name in ("X", "Y", "Scale", "Rotation")}

    @console.guarded("apply the edited picture value", level="log")
    def _write(self, prop, value):
        picture = self._picture()
        if picture is None:
            return
        setattr(picture, prop, float(value))
        picture.Document.recompute()

    @console.guarded("apply the new picture width", level="log")
    def _write_width(self, value):
        if self._natural and value > 0:
            self._write("Scale", value / self._natural[0])

    @console.guarded("refresh the picture fields", level="silent")
    def _sync(self):
        picture = self._picture()
        if picture is None or not fcgui.is_alive(self.form):
            self._timer.stop()
            return
        values = self._values(picture)
        self._show(self.x, values["X"])
        self._show(self.y, values["Y"])
        self._show(self.rotation, values["Rotation"])
        if self._natural:
            self._show(self.width, self._natural[0] * values["Scale"])
            self.height.setText("%.1f mm (set by the aspect ratio)" % (self._natural[1] * values["Scale"]))

    @staticmethod
    def _show(spin, value):
        if abs(spin.value() - value) > SYNC_TOLERANCE:
            spin.blockSignals(True)
            try:
                spin.setValue(value)
            finally:
                spin.blockSignals(False)

    # -- closing --

    def _finish(self):
        global _panel
        with console.guard("stop the picture field refresh", level="silent"):
            self._timer.stop()
        if _panel is self:
            _panel = None

    def _undo_leftovers(self, doc):
        """Finish a Cancel whose undo step was already closed by another action.

        Another FreeCAD command (dragging the picture, for instance) commits the open step,
        so rolling it back no longer removes the new picture or restores the old values.
        """
        picture = doc.getObject(self._name)
        if picture is None:
            return
        if self._created:
            doc.removeObject(self._name)
            return
        for name, value in self._before.items():
            if abs(_number(getattr(picture, name)) - value) > 1e-9:
                setattr(picture, name, value)

    def accept(self):
        with console.guard("keep the picture changes", level="error"):
            self._sync()
            self._undo.close(abort=False)
        self._finish()
        return True

    def reject(self):
        with console.guard("discard the picture changes", level="error"):
            self._undo.close(abort=True)
            doc = self._document()
            if doc is not None:
                self._undo_leftovers(doc)
                doc.recompute()
        self._finish()
        return True


def _open_panel(picture, created, undo):
    """Show the panel for `picture`; if that fails, `undo` is rolled back before re-raising."""
    global _panel
    try:
        panel = PicturePanel(picture, created, undo)
    except Exception:
        undo.close(abort=True)
        raise
    _panel = panel
    try:
        FreeCADGui.Control.showDialog(panel)
    except Exception:
        panel.reject()
        raise


# --- command ---------------------------------------------------------------------------------


def _edit_picture(picture):
    _open_panel(picture, False, _open_undo_step(picture.Document, EDIT_STEP))


def _insert_picture():
    from jellyjams import drawing_common

    page = drawing_common.target_sheet(FreeCAD.ActiveDocument)
    if page is None:
        return
    path = _ask_file(page.Document)
    if not path:
        return
    try:
        kind, data, natural = _read_picture(path)
    except PictureError as exc:
        console.error("the picture was not inserted: %s" % exc)
        return
    doc = page.Document
    undo = _open_undo_step(doc, INSERT_STEP)
    try:
        picture = _add_picture(page, kind, data, natural)
    except Exception:
        undo.close(abort=True)
        with console.guard("recompute after the failed insert", level="log"):
            doc.recompute()
        console.error("the picture %s was not inserted" % os.path.basename(path), with_traceback=True)
        return
    _open_panel(picture, True, undo)


class InsertPictureCommand(commands.BaseCommand):
    command_id = constants.CMD_INSERT_PICTURE
    menu_text = "Insert Picture"
    tooltip = (
        "Adds an image file (SVG, PNG, JPG or BMP) to the current sheet, then opens a panel "
        "for its placement, width and rotation. Run it with a picture selected to adjust "
        "that picture instead."
    )

    def is_active(self):
        from jellyjams import drawing_common

        return drawing_common.drawing_tools_enabled()

    def run(self):
        picture = _selected_picture()
        if picture is not None:
            _edit_picture(picture)
        else:
            _insert_picture()


def get_commands():
    """Command table of this module: JellyJams_InsertPicture."""
    return {constants.CMD_INSERT_PICTURE: InsertPictureCommand()}
