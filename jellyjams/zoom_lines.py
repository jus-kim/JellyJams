# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Thinner sheet lines while zoomed in (on screen only).

With JellyJams active and a sheet window zoomed in far, every line width on that sheet is
divided by 2^n so that edges remain easy to pick. The real widths are kept in memory per
document and object name. They are written back before each save, while a modal dialog is
open, when the user leaves JellyJams or zooms out again, and on request (restore_all, used
by the export commands). None of this marks a document as modified.
"""

import contextlib
import math
import time

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui

CHECK_MS = 180            # zoom poll interval; a new step needs two equal readings
REFERENCE_WIDTH_MM = 0.5
MAX_LINE_PX = 2.5         # widest on-screen width allowed for the reference line
MAX_STEP = 6              # deepest reduction: widths divided by 2^6 = 64
VALUE_TOLERANCE = 1e-7
SAVE_GUARD_S = 60.0

ALL_WIDTHS = ("LineWidth", "HiddenWidth", "IsoWidth", "ExtraWidth")
LINE_WIDTH_ONLY = ("LineWidth",)
LINE_WIDTH_ONLY_TYPES = (constants.TYPE_DIMENSION, constants.TYPE_LEADER, constants.TYPE_BALLOON)

_timer = None
_observer = None
# document name -> object name -> property -> [original, shown, factor]
_records = {}
_reduced = None  # (document name, page name) of the sheet currently shown reduced
_last_reading = None  # (document name, page name, step) seen by the previous check
_saving = {}  # document name -> monotonic time its save started


def reduction_step(px_per_mm):
    """Smallest n (at most MAX_STEP) for which the reference line, divided by 2^n, is no
    wider on screen than MAX_LINE_PX."""
    try:
        width = REFERENCE_WIDTH_MM * abs(float(px_per_mm))
    except (TypeError, ValueError):
        return 0
    step = 0
    while width > MAX_LINE_PX + 1e-9 and step < MAX_STEP:
        width /= 2.0
        step += 1
    return step


# --- reading and writing widths -------------------------------------------------------------


def _width_properties(obj):
    try:
        if any(obj.isDerivedFrom(kind) for kind in LINE_WIDTH_ONLY_TYPES):
            return LINE_WIDTH_ONLY
    except Exception:
        pass
    return ALL_WIDTHS


def _read(view_object, prop):
    value = getattr(view_object, prop)
    return float(getattr(value, "Value", value))


def _sheet_objects(page):
    """All views of the page, including views nested in other views' Views, without repeats."""
    seen = set()
    result = []
    pending = list(getattr(page, "Views", None) or [])
    while pending:
        obj = pending.pop(0)
        try:
            name = obj.Name
        except Exception:
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(obj)
        pending.extend(getattr(obj, "Views", None) or [])
    return result


@contextlib.contextmanager
def _unmodified(doc):
    """Clear the GUI document's Modified flag again if it was clear before the block."""
    gui_document = None
    was_modified = True
    try:
        gui_document = FreeCADGui.getDocument(doc.Name)
        was_modified = bool(gui_document.Modified)
    except Exception:
        gui_document = None
    try:
        yield
    finally:
        if gui_document is not None and not was_modified:
            with console.guard("reset the document's modified flag", level="log"):
                if gui_document.Modified:
                    gui_document.Modified = False


def _apply(page, step):
    """Display each width on the page as real width / 2^step, recording real widths first."""
    factor = 0.5**step
    doc = page.Document
    records = _records.setdefault(doc.Name, {})
    with _unmodified(doc):
        for obj in _sheet_objects(page):
            with console.guard("thin the lines of %s" % obj.Name, level="log"):
                view_object = obj.ViewObject
                if view_object is None:
                    continue
                available = view_object.PropertiesList
                object_records = records.setdefault(obj.Name, {})
                for prop in _width_properties(obj):
                    if prop not in available:
                        continue
                    current = _read(view_object, prop)
                    record = object_records.get(prop)
                    if record is None:
                        original = current
                    elif abs(current - record[1]) > VALUE_TOLERANCE:
                        # Edited while thinned: treat the new value as already divided.
                        original = current / record[2]
                    else:
                        original = record[0]
                    shown = original * factor
                    if abs(current - shown) > VALUE_TOLERANCE:
                        setattr(view_object, prop, shown)
                    object_records[prop] = [original, shown, factor]
                if not object_records:
                    del records[obj.Name]


def _restore_document(doc):
    """Put the recorded real widths of `doc` back and drop its records."""
    global _reduced
    records = _records.pop(doc.Name, {})
    if _reduced is not None and _reduced[0] == doc.Name:
        _reduced = None
    if not records:
        return
    with _unmodified(doc):
        for obj_name, object_records in records.items():
            with console.guard("put back the line widths of %s" % obj_name, level="log"):
                obj = doc.getObject(obj_name)
                view_object = obj.ViewObject if obj is not None else None
                if view_object is None:
                    continue
                for prop, (original, shown, factor) in object_records.items():
                    current = _read(view_object, prop)
                    if abs(current - shown) > VALUE_TOLERANCE:
                        original = current / factor
                    if abs(current - original) > VALUE_TOLERANCE:
                        setattr(view_object, prop, original)


def _forget(doc_name):
    global _reduced
    _records.pop(doc_name, None)
    _saving.pop(doc_name, None)
    if _reduced is not None and _reduced[0] == doc_name:
        _reduced = None


# --- busy and idle ---------------------------------------------------------------------------


def _saving_now(doc_name):
    started = _saving.get(doc_name)
    if started is None:
        return False
    if time.monotonic() - started > SAVE_GUARD_S:
        _saving.pop(doc_name, None)
        return False
    return True


def _busy():
    """True when touching line widths now could interfere with FreeCAD (or on any error)."""
    try:
        if fcgui.techdraw_tool_running(on_error=True):
            return True
        if fcgui.task_dialog_open():
            return True
        return QtWidgets.QApplication.mouseButtons() != QtCore.Qt.MouseButton.NoButton
    except Exception:
        return True


def _document_busy(doc):
    try:
        return bool(doc.HasPendingTransaction or doc.Transacting or doc.Restoring) or _saving_now(doc.Name)
    except Exception:
        return True


def _restore_idle_documents():
    """Put widths back in every document that is not busy; True once nothing is thinned."""
    if not _records:
        return True
    if _busy():
        return False
    documents = FreeCAD.listDocuments()
    complete = True
    for doc_name in list(_records):
        doc = documents.get(doc_name)
        if doc is None:
            _forget(doc_name)
        elif _document_busy(doc):
            complete = False
        else:
            _restore_document(doc)
    return complete


# --- the periodic check --------------------------------------------------------------------------


def _page_of(window):
    try:
        from jellyjams import drawing_common

        page = drawing_common.page_of_active_window()
        if page is not None:
            return page
    except Exception as exc:
        console.log("sheet of the active window not found: %s" % exc)
    try:
        return FreeCADGui.activeView().getPage()
    except Exception:
        return None


def _pixels_per_mm(window):
    view = fcgui.sheet_graphics_view(window)
    if view is None:
        return None
    transform = view.transform()
    return math.hypot(transform.m11(), transform.m12()) * fcgui.rez()


@console.guarded("update the zoom-dependent line widths", level="log")
def _check():
    global _last_reading, _reduced
    if QtWidgets.QApplication.activeModalWidget() is not None or not fcgui.jellyjams_active():
        _last_reading = None
        _restore_idle_documents()
        return
    window = fcgui.active_sheet_window()
    page = _page_of(window) if window is not None else None
    ppm = _pixels_per_mm(window) if page is not None else None
    if ppm is None:
        _last_reading = None
        return
    key = (page.Document.Name, page.Name)
    reading = key + (reduction_step(ppm),)
    settled = reading == _last_reading
    _last_reading = reading
    if not settled or _busy() or _document_busy(page.Document):
        return
    if _reduced not in (None, key) and not _restore_idle_documents():
        return
    step = reading[2]
    if step == 0:
        if key[0] in _records:
            _restore_document(page.Document)
        return
    _apply(page, step)
    _reduced = key


# --- restore triggers from FreeCAD ---------------------------------------------------------------


class _DocumentObserver:
    @console.guarded("put back the real line widths before saving", level="error")
    def slotStartSaveDocument(self, doc, file_name):
        _saving[doc.Name] = time.monotonic()
        restore_all(doc)

    @console.guarded("clear the saving state", level="log")
    def slotFinishSaveDocument(self, doc, file_name):
        _saving.pop(doc.Name, None)

    @console.guarded("drop the line width records of a closed document", level="log")
    def slotDeletedDocument(self, doc):
        _forget(doc.Name)


# --- public API --------------------------------------------------------------------------------


def start():
    """Start the zoom timer and the save/close observer; later calls do nothing."""
    global _timer, _observer
    if _observer is None:
        observer = _DocumentObserver()
        FreeCAD.addDocumentObserver(observer)
        _observer = observer
    if _timer is None:
        timer = QtCore.QTimer()
        timer.setInterval(CHECK_MS)
        timer.timeout.connect(_check)
        timer.start()
        _timer = timer


def stop():
    """Stop the timer and the observer, then put every real width back."""
    global _timer, _observer, _last_reading
    if _timer is not None:
        with console.guard("stop the zoom timer", level="log"):
            _timer.stop()
        _timer = None
    if _observer is not None:
        with console.guard("unregister the line width document observer", level="log"):
            FreeCAD.removeDocumentObserver(_observer)
        _observer = None
    _last_reading = None
    restore_all()


def restore_all(doc=None):
    """Put the real widths back immediately, in `doc` only or in all documents."""
    if doc is not None:
        _restore_document(doc)
        return
    documents = FreeCAD.listDocuments()
    for doc_name in list(_records):
        target = documents.get(doc_name)
        if target is None:
            _forget(doc_name)
        else:
            _restore_document(target)
