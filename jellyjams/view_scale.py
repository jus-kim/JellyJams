# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_ViewScale: set the scale of the selected view from a popup menu.

Selecting any projection targets its whole Standard 3 View, since a group
has one scale for all its projections. A rescale also stretches the spacing
of a draggable group and updates a title-block "scale" field that still
shows the previous ratio.
"""

from PySide import QtGui, QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui
from jellyjams import projected_view
from jellyjams.view_labels import scale_text_for

STANDARD_SCALES = ("50:1", "20:1", "10:1", "5:1", "2:1", "1:1",
                   "1:2", "1:5", "1:10", "1:20", "1:50", "1:100")

MODE_CUSTOM = "Custom"
MODE_PAGE = "Page"
MODE_AUTOMATIC = "Automatic"
UNDO_NAME = "Scale"
TITLE_BLOCK_KEY = "scale"

_EXCLUDED_TYPES = (constants.TYPE_DIMENSION, constants.TYPE_BALLOON, constants.TYPE_ANNOTATION)
_EXTRA_VIEW_TYPES = (constants.TYPE_COMPLEX_SECTION, constants.TYPE_BROKEN_VIEW)


def _ratio(text):
    first, second = text.split(":")
    return float(first) / float(second)


def _has_property(obj, name):
    try:
        return name in obj.PropertiesList
    except Exception:
        return False


def scale_target(obj):
    """The object that gets the new scale when `obj` is selected, or None."""
    if obj is None or not doc_utils.is_alive(obj):
        return None
    if (doc_utils.is_derived(obj, constants.TYPE_PROJ_ITEM)
            or doc_utils.is_derived(obj, constants.TYPE_PROJ_GROUP)):
        return projected_view.owning_group(obj)
    if any(doc_utils.is_derived(obj, excluded) for excluded in _EXCLUDED_TYPES):
        return None
    type_id = doc_utils.type_id(obj)
    if type_id.startswith("TechDraw::DrawView") or type_id in _EXTRA_VIEW_TYPES:
        return obj if _has_property(obj, "Scale") else None
    return None


def _selected_target():
    for obj in fcgui.selection():
        target = scale_target(obj)
        if target is not None:
            return target
    return None


def _parse(text):
    try:
        from jellyjams import drawing_common
        return drawing_common.parse_scale(text)
    except Exception as exc:
        console.log("ignored the scale text %r: %s" % (text, exc))
        return None


def _scale_of(target):
    value = projected_view.num(getattr(target, "Scale", 0.0), 0.0)
    return value if value > 0 else 1.0


# --- menu ------------------------------------------------------------------------------


def _ask_custom(parent, current_text):
    text, ok = QtWidgets.QInputDialog.getText(
        parent, "Scale", "Enter a ratio such as 1:3 or 3:1:",
        QtWidgets.QLineEdit.EchoMode.Normal, current_text)
    if not ok:
        return None
    value = _parse(text)
    return (MODE_CUSTOM, value) if value is not None else None


def _ask_choice(target):
    """The (mode, value) picked from the popup menu, or None if the menu was dismissed."""
    parent = fcgui.main_window()
    mode = str(getattr(target, "ScaleType", "") or "")
    current_text = scale_text_for(_scale_of(target))

    menu = QtWidgets.QMenu(parent)
    menu.setObjectName(constants.OBJ_SCALE_MENU)
    menu.setTitle("Scale")
    menu.setToolTipsVisible(True)
    choices = []
    for text in STANDARD_SCALES:
        action = menu.addAction(text)
        action.setCheckable(True)
        action.setChecked(mode not in (MODE_PAGE, MODE_AUTOMATIC) and text == current_text)
        choices.append((action, (MODE_CUSTOM, _ratio(text))))
    menu.addSeparator()
    sheet = menu.addAction("Sheet scale")
    sheet.setCheckable(True)
    sheet.setChecked(mode == MODE_PAGE)
    sheet.setToolTip("Use the scale set on the sheet")
    choices.append((sheet, (MODE_PAGE, None)))
    automatic = menu.addAction("Automatic")
    automatic.setCheckable(True)
    automatic.setChecked(mode == MODE_AUTOMATIC)
    automatic.setToolTip("TechDraw picks a scale that fits the sheet")
    choices.append((automatic, (MODE_AUTOMATIC, None)))
    custom = menu.addAction("User defined …")
    try:
        picked = menu.exec(QtGui.QCursor.pos())
    finally:
        menu.deleteLater()
    if picked is None:
        return None
    if picked == custom:
        return _ask_custom(parent, current_text)
    for action, choice in choices:
        if picked == action:
            return choice
    return None


# --- applying a scale ------------------------------------------------------------------


def _scale_spacing(target, old, new):
    """Stretch a draggable group's projection offsets by new/old scale. True if any moved."""
    if not doc_utils.is_derived(target, constants.TYPE_PROJ_GROUP):
        return False
    if bool(getattr(target, "AutoDistribute", True)) or old <= 0 or new <= 0:
        return False
    ratio = new / old
    if abs(ratio - 1.0) < 1e-12:
        return False
    for item in projected_view.projections(target):
        x, y = projected_view.xy(item)
        item.X = x * ratio
        item.Y = y * ratio
    return True


def _update_title_block(target, old_text, new_text):
    if not old_text or not new_text or old_text == new_text:
        return
    page = projected_view.page_of(target)
    template = getattr(page, "Template", None) if page is not None else None
    texts = dict(getattr(template, "EditableTexts", None) or {})
    if TITLE_BLOCK_KEY not in texts:
        return
    if "".join(str(texts[TITLE_BLOCK_KEY]).split()) != "".join(old_text.split()):
        return
    texts[TITLE_BLOCK_KEY] = new_text
    template.EditableTexts = texts


def apply_scale(target, mode, value=None):
    """Write ScaleType (plus Scale for MODE_CUSTOM) in one "Scale" undo step. True if done."""
    doc = target.Document
    old = _scale_of(target)
    old_text = scale_text_for(old)
    label = str(getattr(target, "Label", "") or getattr(target, "Name", "?"))
    try:
        with projected_view.undo_step(doc, UNDO_NAME):
            target.ScaleType = mode
            if mode == MODE_CUSTOM:
                target.Scale = float(value)
            doc.recompute()
            new = projected_view.num(getattr(target, "Scale", old), old)
            if _scale_spacing(target, old, new):
                doc.recompute()
            new_text = scale_text_for(new)
            _update_title_block(target, old_text, new_text)
    except Exception:
        console.error("changing the scale of %s failed" % label, with_traceback=True)
        return False
    console.message("%s is now drawn at %s" % (label, new_text or new))
    return True


class ViewScaleCommand(commands.BaseCommand):
    command_id = constants.CMD_VIEW_SCALE
    menu_text = "Scale"
    tooltip = ("Sets the scale of the selected view: pick a standard ratio, follow the sheet, "
               "let TechDraw fit it, or type your own ratio.")

    def is_active(self):
        return not fcgui.task_dialog_open() and _selected_target() is not None

    def run(self):
        target = _selected_target()
        if target is None:
            return
        choice = _ask_choice(target)
        if choice is not None:
            apply_scale(target, *choice)


def get_commands():
    return {constants.CMD_VIEW_SCALE: ViewScaleCommand()}
