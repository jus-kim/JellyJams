# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Puts SolidWorks labels on FreeCAD's own task dialogs and adds the ISO 128 presets row.

A timer looks for open catalog forms and rewrites their visible texts. Combo indices,
item data, values and FreeCAD's dialog logic are left alone.
"""

from collections.abc import Mapping

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui
from jellyjams import dialog_terms_data as data

INTERVAL_MS = constants.DIALOG_TERMS_MS
WEIGHT_TOLERANCE_MM = 1e-6
CUSTOM_SCALE_INDEX = 2
PRESETS_ROW_POSITION = 1
RAW_VALUE_PROPERTY = "rawValue"
OBJ_WEIGHT_LABEL = constants.OBJ_LINE_WIDTH_PRESETS + "Label"
OBJ_WEIGHT_COMBO = constants.OBJ_LINE_WIDTH_PRESETS + "Combo"

_timer = None
_form_pattern = None
_logged = set()


# --- service ------------------------------------------------------------------------------


def start():
    global _timer
    try:
        if _timer is not None and fcgui.is_alive(_timer):
            if not _timer.isActive():
                _timer.start(INTERVAL_MS)
            return
        timer = QtCore.QTimer()
        timer.setInterval(INTERVAL_MS)
        timer.timeout.connect(_tick)
        timer.start()
        _timer = timer
    except Exception as exc:
        console.warning("task dialogs will keep FreeCAD's labels: %s" % exc)


def stop():
    try:
        if _timer is not None and fcgui.is_alive(_timer):
            _timer.stop()
    except Exception as exc:
        console.log("dialog label timer did not stop: %s" % exc)


def is_running():
    try:
        return _timer is not None and fcgui.is_alive(_timer) and _timer.isActive()
    except Exception:
        return False


@console.guarded("relabel the open task dialog", level="log", default=0)
def _tick():
    if not fcgui.jellyjams_active():
        return 0
    return process_once()


# --- one pass -------------------------------------------------------------------------------


def process_once():
    if not fcgui.task_dialog_open():
        return 0
    writes = 0
    try:
        window = fcgui.main_window()
        if window is None:
            return 0
        for form in _find_forms(window):
            try:
                writes += process_form(form)
            except Exception as exc:
                _log_once(("form", _object_name(form)),
                          "skipped dialog %s: %s" % (_object_name(form), exc))
    except Exception as exc:
        _log_once(("check",), "dialog label pass failed: %s" % exc)
    return writes


def process_form(form):
    form_name = _object_name(form)
    spec = data.FORMS.get(form_name)
    if spec is None:
        return 0
    protected = set(data.STATE_WIDGETS.get(form_name, ()))
    writes = 0
    for name, text in spec["texts"].items():
        if name not in protected:
            writes += _apply(form, form_name, name, _write_text, text)
    for name, entries in spec["combos"].items():
        if name not in protected:
            writes += _apply(form, form_name, name, _write_combo, entries)
    for name, tip in spec["tooltips"].items():
        if name not in protected:
            writes += _apply(form, form_name, name, _write_tooltip, tip)
    if spec["scale_fix"]:
        writes += _guarded_step(form_name, "scale field", _fix_scale_field, form, *spec["scale_fix"])
    if spec["weight_presets"]:
        writes += _guarded_step(form_name, "ISO 128 presets row", _ensure_weight_row, form)
    return writes


def format_weight(mm):
    return ("%.2f" % float(mm)).rstrip("0").rstrip(".") + " mm"


# --- widget writers -----------------------------------------------------------------------------


def _apply(form, form_name, name, writer, target):
    try:
        widget = form.findChild(QtWidgets.QWidget, name)
        if widget is None:
            return 0
        return writer(widget, target)
    except Exception as exc:
        _log_once((form_name, name), "left %s in %s unchanged: %s" % (name, form_name, exc))
        return 0


def _write_text(widget, text):
    if isinstance(widget, QtWidgets.QGroupBox):
        if widget.title() != text:
            widget.setTitle(text)
            return 1
        return 0
    if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
        if widget.text() != text:
            widget.setText(text)
            return 1
    return 0


def _write_combo(widget, entries):
    # a different item count means FreeCAD changed the list: leave it as it is
    if not isinstance(widget, QtWidgets.QComboBox) or widget.count() != len(entries):
        return 0
    writes = 0
    for index, entry in enumerate(entries):
        if widget.itemText(index) != entry:
            widget.setItemText(index, entry)
            writes += 1
    return writes


def _write_tooltip(widget, tip):
    current = widget.toolTip()
    if isinstance(tip, Mapping):
        tip = tip.get(current)
        if tip is None:
            return 0
    if current != tip:
        widget.setToolTip(tip)
        return 1
    return 0


def _fix_scale_field(form, combo_name, field_name):
    # FreeCAD enables the field only while the combo shows its own "Custom" text
    combo = form.findChild(QtWidgets.QComboBox, combo_name)
    field = form.findChild(QtWidgets.QWidget, field_name)
    if combo is None or field is None:
        return 0
    if combo.isEnabled() and combo.currentIndex() == CUSTOM_SCALE_INDEX and not field.isEnabled():
        field.setEnabled(True)
        return 1
    return 0


# --- ISO 128 line-thickness presets row --------------------------------------------------------


def _ensure_weight_row(form):
    if form.findChild(QtWidgets.QWidget, constants.OBJ_LINE_WIDTH_PRESETS) is not None:
        return 0
    field = form.findChild(QtWidgets.QWidget, data.WEIGHT_FIELD)
    if field is None:
        return 0
    layout = form.layout()
    if not isinstance(layout, (QtWidgets.QBoxLayout, QtWidgets.QFormLayout)):
        return 0
    row = _build_weight_row(form, field)
    if isinstance(layout, QtWidgets.QBoxLayout):
        layout.insertWidget(min(PRESETS_ROW_POSITION, layout.count()), row)
    else:
        layout.insertRow(min(PRESETS_ROW_POSITION, layout.rowCount()), row)
    return 1


def _build_weight_row(form, field):
    row = QtWidgets.QWidget(form)
    row.setObjectName(constants.OBJ_LINE_WIDTH_PRESETS)
    row_layout = QtWidgets.QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)

    label = QtWidgets.QLabel(data.WEIGHT_LABEL, row)
    label.setObjectName(OBJ_WEIGHT_LABEL)
    combo = QtWidgets.QComboBox(row)
    combo.setObjectName(OBJ_WEIGHT_COMBO)
    combo.addItem(data.PLACEHOLDER)
    for mm in data.WEIGHT_PRESETS_MM:
        combo.addItem(format_weight(mm), mm)
    combo.setCurrentIndex(_preset_index(field))

    row_layout.addWidget(label)
    row_layout.addWidget(combo, 1)
    # "activated" comes from user picks only; setting the initial index must not touch the field
    combo.activated.connect(lambda index: _apply_preset(field, index))
    return row


def _preset_index(field):
    try:
        value = float(field.property(RAW_VALUE_PROPERTY))
    except (TypeError, ValueError):
        return 0
    for index, mm in enumerate(data.WEIGHT_PRESETS_MM, start=1):
        if abs(value - mm) <= WEIGHT_TOLERANCE_MM:
            return index
    return 0


@console.guarded("set the ISO 128 line thickness", level="log")
def _apply_preset(field, index):
    if index <= 0 or index > len(data.WEIGHT_PRESETS_MM) or not fcgui.is_alive(field):
        return
    field.setProperty(RAW_VALUE_PROPERTY, data.WEIGHT_PRESETS_MM[index - 1])


# --- helpers ---------------------------------------------------------------------------------------


def _find_forms(window):
    global _form_pattern
    try:
        if _form_pattern is None:
            names = "|".join(QtCore.QRegularExpression.escape(name) for name in data.FORM_NAMES)
            _form_pattern = QtCore.QRegularExpression("^(?:%s)$" % names)
        return list(window.findChildren(QtWidgets.QWidget, _form_pattern))
    except TypeError:
        forms = []
        for name in data.FORM_NAMES:
            forms.extend(window.findChildren(QtWidgets.QWidget, name))
        return forms


def _guarded_step(form_name, what, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        _log_once((form_name, what), "%s of %s not updated: %s" % (what, form_name, exc))
        return 0


def _object_name(widget):
    try:
        return widget.objectName()
    except Exception:
        return ""


def _log_once(key, text):
    if key not in _logged:
        _logged.add(key)
        console.log(text)
