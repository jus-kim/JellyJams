# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Helpers for all drawing commands: scale notation, finding the target sheet, sheet size."""

import math

import FreeCAD

from jellyjams import console, constants, doc_utils, fcgui

DEFAULT_SHEET_CENTER = (105.0, 148.5)


# --- scale text ---------------------------------------------------------------------------


def _ratio_number(value):
    text = "%.2f" % round(value, 2)
    return text.rstrip("0").rstrip(".")


def scale_text(value):
    """A scale in colon notation, e.g. 2 -> "2:1", 0.5 -> "1:2", 0.3 -> "1:3.33".

    Returns "" for zero, negative, infinite or non-numeric input.
    """
    if isinstance(value, bool):
        return ""
    try:
        number = float(getattr(value, "Value", value))
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number) or number <= 0:
        return ""
    if number >= 1:
        return _ratio_number(number) + ":1"
    return "1:" + _ratio_number(1.0 / number)


def _positive_number(text):
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def parse_scale(text):
    """Value of a scale written as "a:b" or as a number; None unless valid and positive.

    Whitespace is ignored and a comma works as decimal point: "1:5" -> 0.2, "0,5" -> 0.5.
    """
    if text is None:
        return None
    compact = "".join(str(text).split()).replace(",", ".")
    if not compact:
        return None
    parts = compact.split(":")
    if len(parts) == 1:
        return _positive_number(parts[0])
    if len(parts) != 2:
        return None
    numerator = _positive_number(parts[0])
    denominator = _positive_number(parts[1])
    if numerator is None or denominator is None:
        return None
    return _positive_number(numerator / denominator)


# --- sheets -------------------------------------------------------------------------------


def _is_page(obj):
    return obj is not None and doc_utils.is_derived(obj, constants.TYPE_PAGE)


def has_page(doc):
    """True when `doc` holds at least one TechDraw page (sheet)."""
    if doc is None:
        return False
    try:
        return bool(doc_utils.pages(doc))
    except Exception:
        return False


def drawing_tools_enabled():
    """True if the active document has a sheet and no task dialog is open; never raises."""
    try:
        return has_page(FreeCAD.ActiveDocument) and not fcgui.task_dialog_open()
    except Exception:
        return False


def _page_from_active_view():
    try:
        view = fcgui.gui().activeView()
        page = view.getPage()
    except Exception:
        return None
    return page if _is_page(page) else None


def _page_from_window_title(window):
    """The sheet named by the window title "<label>[*]" or "<document> : <label>[*]"."""
    try:
        title = str(window.windowTitle()).replace("[*]", "").strip()
        doc = FreeCAD.ActiveDocument
        candidates = doc_utils.pages(doc) if doc is not None else []
    except Exception:
        return None
    matches = []
    for page in candidates:
        label = str(getattr(page, "Label", ""))
        if label and (title == label or title.endswith(" : " + label)):
            matches.append(page)
    return matches[0] if len(matches) == 1 else None


def page_of_active_window():
    """The DrawPage displayed by the active sheet window, or None."""
    window = fcgui.active_sheet_window()
    if window is None:
        return None
    page = _page_from_active_view()
    if page is None:
        page = _page_from_window_title(window)
    return page


def _same_document(obj, doc):
    try:
        return obj.Document.Name == doc.Name
    except Exception:
        return False


def owning_page(obj):
    """The sheet holding `obj`: a DrawPage parent, or the DrawPage of one of its parents."""
    if obj is None:
        return None
    try:
        page = doc_utils.parent_page(obj)
        if page is not None:
            return page
        for parent in list(getattr(obj, "InList", None) or []):
            page = doc_utils.parent_page(parent)
            if page is not None:
                return page
    except Exception:
        return None
    return None


def target_sheet(doc=None, use_active_window=True):
    """The sheet a drawing command works on (drawing-sheet section 3), or None.

    Checked in this order: the active sheet window's sheet (if `use_active_window`), a
    selected sheet, the sheet of a selected object, the document's first sheet.
    """
    try:
        if doc is None:
            doc = FreeCAD.ActiveDocument
        if use_active_window:
            page = page_of_active_window()
            if page is not None and (doc is None or _same_document(page, doc)):
                return page
        if doc is None:
            return None
        selected = fcgui.selection(doc.Name)
        for obj in selected:
            if _is_page(obj):
                return obj
        for obj in selected:
            page = owning_page(obj)
            if page is not None:
                return page
        pages = doc_utils.pages(doc)
        return pages[0] if pages else None
    except Exception as exc:
        console.log("target sheet lookup failed: %s" % exc)
        return None


def _length(value):
    try:
        return float(getattr(value, "Value", value))
    except (TypeError, ValueError):
        return None


def sheet_size(page):
    """Template (width, height) of the sheet in mm; None unless both are positive."""
    try:
        template = page.Template
    except Exception:
        return None
    if template is None:
        return None
    width = _length(getattr(template, "Width", None))
    height = _length(getattr(template, "Height", None))
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return (width, height)


def sheet_center(page, default=DEFAULT_SHEET_CENTER):
    """Middle of the sheet in mm, or `default` when the sheet size is unknown."""
    size = sheet_size(page)
    if size is None:
        return (float(default[0]), float(default[1]))
    return (size[0] / 2.0, size[1] / 2.0)


def open_sheet_window(page):
    """Open or raise the sheet without TechDraw's SwitchToWB-gated double-click."""
    with console.guard("show the sheet window", level="log"):
        page.ViewObject.show()
