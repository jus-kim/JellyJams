# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_MakeDrawing, the counterpart of SolidWorks "Make Drawing from Part/Assembly".

The result is a document of its own that links back to the model. It is suggested next to
the model's file and holds a single sheet: an installed FreeCAD template with an ISO 7200
title block, and a Standard 3 View group placed on it.
"""

import datetime
import getpass
import os
import re

import FreeCAD
from PySide import QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui, params
from jellyjams import drawing_common, templates

TITLE = "Make Drawing"
FORMATS = (templates.FORMAT_A4_PORTRAIT, templates.FORMAT_A3_LANDSCAPE)
# Largest model extent from which the A3 sheet is preselected. A judgement value: bigger
# parts get the bigger sheet, so the automatic view scale stays closer to full size.
LARGE_PART_MM = 120.0
DEFAULT_PROJECTION = templates.THIRD_ANGLE
PROJECTIONS = {
    templates.THIRD_ANGLE: ("Front", "Top", "Right"),
    templates.FIRST_ANGLE: ("Front", "Top", "Left"),
}
FRONT_DIRECTION = (0.0, -1.0, 0.0)
FRONT_X_DIRECTION = (1.0, 0.0, 0.0)
SHEET_LABEL = "Sheet1"
GROUP_LABEL = "Standard 3 View"
DRAWING_SUFFIX = "_Drawing"
FILE_EXTENSION = ".FCStd"
FILE_FILTER = "FreeCAD file (*.FCStd)"
LANGUAGE_CODE = "EN"
UNIT = "mm"
# UUID of FreeCAD 1.1's built-in "Default" material, which every shape has until the user
# assigns a real one; it is not worth printing in the title block.
DEFAULT_MATERIAL_UUID = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"

_UNSAFE_FILE_CHARS = re.compile(r'[\\/:*?"<>|]+')
_NON_IDENTIFIER_CHARS = re.compile(r"[^A-Za-z0-9_]")


# --- pure helpers ---------------------------------------------------------------------------


def default_format(max_extent_mm):
    """Sheet format to preselect: "A3 landscape" once the largest model extent reaches
    LARGE_PART_MM, "A4 portrait" below that or when the extent is not a number."""
    try:
        large = float(max_extent_mm) >= LARGE_PART_MM
    except (TypeError, ValueError):
        large = False
    return templates.FORMAT_A3_LANDSCAPE if large else templates.FORMAT_A4_PORTRAIT


def document_name_for(stem):
    """Internal document name for a file stem; characters outside [A-Za-z0-9_] become "_"."""
    return _NON_IDENTIFIER_CHARS.sub("_", str(stem or "")) or "Drawing"


# --- title block --------------------------------------------------------------------------------


def _template_keys(page):
    try:
        return set(dict(page.Template.EditableTexts))
    except Exception:
        return set()


def _source_of(view):
    for name in ("XSource", "Source"):
        try:
            linked = list(getattr(view, name, None) or [])
        except Exception:
            linked = []
        for obj in linked:
            if obj is not None:
                return obj
    return None


def _sheet_views(page):
    try:
        return list(page.Views or [])
    except Exception:
        return []


def _source_view(page):
    """(first positioned view on the sheet that has a source, that source), or (None, None)."""
    for view in _sheet_views(page):
        if not (hasattr(view, "X") and hasattr(view, "Y")):
            continue
        source = _source_of(view)
        if source is not None:
            return view, source
    return None, None


def _scale_view(page, source_view):
    if source_view is not None and hasattr(source_view, "Scale"):
        return source_view
    for view in _sheet_views(page):
        if hasattr(view, "Scale"):
            return view
    return None


def _text(value):
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _material_name(obj):
    try:
        material = getattr(obj, "ShapeMaterial", None)
        if material is not None and getattr(material, "UUID", "") != DEFAULT_MATERIAL_UUID:
            name = _text(getattr(material, "Name", ""))
            if name:
                return name
    except Exception:
        pass
    try:
        material = getattr(obj, "Material", None)
    except Exception:
        return ""
    if isinstance(material, str):
        return material.strip()
    return _text(getattr(material, "Name", "")) if material is not None else ""


def _author():
    author = _text(params.get_string(constants.PARAM_DOCUMENT, "prefAuthor", ""))
    if author:
        return author
    try:
        return _text(getpass.getuser())
    except Exception:
        return ""


def title_block_values(page, drawing_doc):
    """Title-block entries derived from the model (drawing-sheet 5.4).

    Only keys present in the sheet's template are returned, and entries whose value cannot
    be worked out are omitted.
    """
    keys = _template_keys(page)
    if not keys:
        return {}
    view, source = _source_view(page)
    values = {
        "drawing_number": _text(getattr(drawing_doc, "Label", "")),
        "creator": _author(),
        "date_of_issue": datetime.date.today().isoformat(),
        "language_code": LANGUAGE_CODE,
        "unit": UNIT,
    }
    if source is not None:
        try:
            title = _text(source.Document.Label)
        except Exception:
            title = ""
        values["title"] = title or _text(getattr(source, "Label", ""))
        values["part_material"] = _material_name(source)
    scale_view = _scale_view(page, view)
    if scale_view is not None:
        values["scale"] = drawing_common.scale_text(getattr(scale_view, "Scale", None))
    return {key: value for key, value in values.items() if key in keys and value}


# --- the command flow ---------------------------------------------------------------------------


def _largest_extent(objects):
    try:
        import Part
    except Exception:
        Part = None
    largest = 0.0
    for obj in objects:
        try:
            shape = Part.getShape(obj) if Part is not None else obj.Shape
            box = shape.BoundBox
            if box.isValid():
                largest = max(largest, box.XLength, box.YLength, box.ZLength)
        except Exception:
            continue
    return largest


def _ask_format(parent, objects):
    items = list(FORMATS)
    preselected = items.index(default_format(_largest_extent(objects)))
    choice, accepted = QtWidgets.QInputDialog.getItem(
        parent, TITLE, "Sheet format (title block ISO 7200):", items, preselected, False
    )
    return choice if accepted and choice in items else None


def _path_key(path):
    """`path` made absolute and normalized, lower-cased so the comparison ignores case."""
    return os.path.normcase(os.path.abspath(os.path.normpath(path))).lower()


def _open_document_using(path):
    """The open document whose FileName is `path` (normalized, case-insensitive), or None."""
    wanted = _path_key(path)
    for doc in list(FreeCAD.listDocuments().values()):
        try:
            file_name = str(doc.FileName or "")
        except Exception:
            continue
        if file_name and _path_key(file_name) == wanted:
            return doc
    return None


def _ask_drawing_path(parent, model):
    home = os.path.expanduser("~")
    folder = os.path.dirname(model.FileName or "") or home
    if not os.path.isdir(folder):
        folder = home
    stem = _UNSAFE_FILE_CHARS.sub("_", _text(model.Label) or model.Name)
    suggestion = os.path.join(folder, stem + DRAWING_SUFFIX + FILE_EXTENSION)
    path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Save drawing as", suggestion, FILE_FILTER
    )
    if not path:
        return None
    if not path.lower().endswith(FILE_EXTENSION.lower()):
        path += FILE_EXTENSION
    path = os.path.normpath(path)
    taken = _open_document_using(path)
    if taken is not None:
        console.error(
            "no drawing was made: %s is the file of the open document \"%s\"; "
            "pick another file name" % (path, _text(getattr(taken, "Label", "")) or taken.Name)
        )
        return None
    return path


def _ensure_model_saved(parent, model):
    if model.FileName:
        return True
    QtWidgets.QMessageBox.information(
        parent,
        TITLE,
        "The drawing links to the model's file, so the part or assembly has to be saved "
        "first.\n\nChoose where to save it in the Save As dialog that follows.",
    )
    fcgui.run_command("Std_SaveAs")
    try:
        return bool(model.FileName)
    except Exception:
        return False


def _add_sheet(drawing, template_path):
    template = drawing.addObject(constants.TYPE_TEMPLATE, "Template")
    template.Template = template_path
    page = drawing.addObject(constants.TYPE_PAGE, "Page")
    page.Template = template
    page.ProjectionType = DEFAULT_PROJECTION
    page.Label = SHEET_LABEL
    return page


def _add_standard_3_view(drawing, page, objects):
    group = drawing.addObject(constants.TYPE_PROJ_GROUP, "ProjGroup")
    page.addView(group)
    group.ProjectionType = DEFAULT_PROJECTION
    group.ScaleType = "Automatic"
    group.XSource = list(objects)
    anchor_type, *other_types = PROJECTIONS[DEFAULT_PROJECTION]
    group.addProjection(anchor_type)
    anchor = group.Anchor
    if anchor is not None:
        anchor.Direction = FreeCAD.Vector(*FRONT_DIRECTION)
        if hasattr(anchor, "XDirection"):
            anchor.XDirection = FreeCAD.Vector(*FRONT_X_DIRECTION)
    for projection_type in other_types:
        group.addProjection(projection_type)
    group.Label = GROUP_LABEL
    return group


def _apply_start_layout(group):
    try:
        from jellyjams import projected_view

        projected_view.apply_start_layout(group)
    except Exception as exc:
        console.log("Standard 3 View kept FreeCAD's layout: %s" % exc)


def _fill_title_block(page, drawing):
    template = page.Template
    values = title_block_values(page, drawing)
    template.EditableTexts = {key: values.get(key, "") for key in dict(template.EditableTexts)}


def _show(drawing, page):
    with console.guard("bring the new drawing to the front", level="log"):
        FreeCAD.setActiveDocument(drawing.Name)
        gui = fcgui.gui()
        if gui is not None:
            gui.setActiveDocument(drawing.Name)
    drawing_common.open_sheet_window(page)


def _build_drawing(objects, fmt, path):
    template_path = templates.new_drawing_template(fmt)
    if not template_path:
        raise RuntimeError(
            "there is no TechDraw template for %s in %s" % (fmt, templates.templates_dir())
        )
    template_path = templates.resolve_for_method(template_path, DEFAULT_PROJECTION)
    stem = os.path.splitext(os.path.basename(path))[0]
    drawing = FreeCAD.newDocument(document_name_for(stem))
    drawing.Label = stem
    # Views link into the model document, and FreeCAD rejects such links while the owning
    # document has never been saved.
    drawing.saveAs(path)
    drawing.Label = stem
    page = _add_sheet(drawing, template_path)
    group = _add_standard_3_view(drawing, page, objects)
    drawing.recompute()
    _apply_start_layout(group)
    _fill_title_block(page, drawing)
    drawing.recompute()
    drawing.save()
    _show(drawing, page)
    console.message("new %s drawing saved as %s" % (fmt, path))


def make_drawing():
    """Make Drawing for the active document, following drawing-sheet 4.2."""
    model = FreeCAD.ActiveDocument
    if model is None:
        return
    parent = fcgui.main_window()
    objects = doc_utils.primary_model_objects(model)
    if not objects:
        QtWidgets.QMessageBox.information(
            parent,
            TITLE,
            "The active document has no part or assembly to make a drawing of.",
        )
        return
    if not _ensure_model_saved(parent, model):
        return
    fmt = _ask_format(parent, objects)
    if fmt is None:
        return
    path = _ask_drawing_path(parent, model)
    if path is None:
        return
    try:
        _build_drawing(objects, fmt, path)
    except Exception:
        console.error("Make Drawing stopped because of an error", with_traceback=True)


class MakeDrawingCommand(commands.BaseCommand):
    command_id = constants.CMD_MAKE_DRAWING
    menu_text = "Make Drawing"
    tooltip = (
        "Starts a new drawing document, saved under its own file name and linked to this "
        "part or assembly. Sheet 1 receives front, top and right views and a pre-filled "
        "ISO 7200 title block."
    )

    def is_active(self):
        model = FreeCAD.ActiveDocument
        if model is None or drawing_common.has_page(model):
            return False
        return bool(doc_utils.primary_model_objects(model))

    def run(self):
        make_drawing()


def get_commands():
    """Command table of this module: JellyJams_MakeDrawing."""
    return {constants.CMD_MAKE_DRAWING: MakeDrawingCommand()}
