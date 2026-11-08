# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Enable native drawing aids on sketch entry, with exact session restoration.

Snapping preferences have a crash-recoverable backup. Autoconstraints belongs
to the individual sketch view provider: restore it before document saves so
the temporary override never becomes part of the user's file.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

from jellyjams import console, constants, doc_utils, fcgui, params

SNAP_KEYS = (constants.KEY_SKETCH_SNAP, constants.KEY_SKETCH_SNAP_OBJECTS)
POLL_MS = 150
_enabled = False
_observer = None
_timer = None
_view = None
_original_auto = None
_saving = False
_save_auto = None
_autosaver = None
_save_filter = None


def _backup():
    state, data = params.load_backup(constants.KEY_SKETCH_ASSIST_BACKUP)
    if state == "none":
        return None
    valid = (state == "ok" and isinstance(data, dict) and set(data) == set(SNAP_KEYS)
             and all(isinstance(entry, list) and len(entry) == 2
                     and isinstance(entry[0], bool)
                     and (isinstance(entry[1], bool) if entry[0] else entry[1] is None)
                     for entry in data.values()))
    if not valid:
        console.warning("deleted a damaged sketch snapping backup; preferences were left unchanged")
        params.clear_backup(constants.KEY_SKETCH_ASSIST_BACKUP, remove=True)
        return None
    return data


def _apply_snapping():
    group = params.group(constants.PARAM_SKETCH_SNAP)
    if _backup() is None:
        data = {}
        for key in SNAP_KEYS:
            existed = params.has_key(group, key, "Bool")
            data[key] = [existed, group.GetBool(key) if existed else None]
        params.save_backup(constants.KEY_SKETCH_ASSIST_BACKUP, data)
    for key in SNAP_KEYS:
        group.SetBool(key, True)


@console.guarded("put back sketch snapping preferences", level="warning")
def recover(announce=True):
    """Restore only the persisted preferences, including keys originally absent."""
    data = _backup()
    if data is None:
        return
    group = params.group(constants.PARAM_SKETCH_SNAP)
    for key, (existed, value) in data.items():
        if existed:
            group.SetBool(key, value)
        else:
            group.RemBool(key)
    params.clear_backup(constants.KEY_SKETCH_ASSIST_BACKUP, remove=True)
    if announce:
        console.message("put back sketch snapping preferences left by an unclean exit")


def _set_auto(value):
    # A drawing aid alone must not make a saved model dirty. Scope NoModify to
    # this write and preserve any status already attached by FreeCAD/add-ons.
    getter = getattr(_view, "getPropertyStatus", None)
    mark = getter is not None and "NoModify" not in getter(constants.PROP_AUTO_CONSTRAINTS)
    if mark:
        _view.setPropertyStatus(constants.PROP_AUTO_CONSTRAINTS, "NoModify")
    try:
        setattr(_view, constants.PROP_AUTO_CONSTRAINTS, value)
    finally:
        if mark:
            _view.setPropertyStatus(constants.PROP_AUTO_CONSTRAINTS, "-NoModify")


def _restore_auto():
    if _view is not None and _original_auto is not None:
        # The native view provider can already be deleted on document closure.
        try:
            obj = _view.Object
        except (RuntimeError, ReferenceError):
            return True
        if doc_utils.is_alive(obj):
            try:
                _set_auto(_original_auto)
            except Exception as exc:
                console.warning("could not restore the sketch's automatic constraints: %s" % exc)
                return False
    return True


def _end():
    global _view, _original_auto, _saving, _save_auto
    restored = _restore_auto()
    recover(announce=False)
    if restored:
        _view = None
        _original_auto = None
    _saving = False
    _save_auto = None


def _begin(view):
    global _view, _original_auto
    if not _enabled or not fcgui.jellyjams_active():
        return
    if not doc_utils.is_derived(getattr(view, "Object", None), constants.TYPE_SKETCH):
        return
    if _view is view:
        return
    _end()
    # Do not overwrite a still-pending backup if a previous restore failed.
    if _view is not None or params.backup_pending(constants.KEY_SKETCH_ASSIST_BACKUP):
        return
    _view = view
    _original_auto = bool(getattr(view, constants.PROP_AUTO_CONSTRAINTS))
    _apply_snapping()
    _set_auto(True)


class _Observer:
    @console.guarded("enable sketch drawing aids", level="warning")
    def slotInEdit(self, view):
        _begin(view)

    @console.guarded("restore sketch drawing aids", level="warning")
    def slotResetEdit(self, view):
        if _view is view:
            _end()

    @console.guarded("restore sketch settings before saving", level="warning")
    def slotStartSaveDocument(self, doc, file_name):
        global _saving, _save_auto
        if not _saving and _view is not None and _view.Object.Document is doc:
            _save_auto = bool(getattr(_view, constants.PROP_AUTO_CONSTRAINTS))
            _saving = True
            _restore_auto()

    @console.guarded("resume sketch settings after saving", level="warning")
    def slotFinishSaveDocument(self, doc, file_name):
        global _saving, _save_auto
        if _saving and _view is not None and _view.Object.Document is doc:
            _saving = False
            _set_auto(_save_auto)
            _save_auto = None

    @console.guarded("drop drawing aids for a closed document", level="warning")
    def slotDeletedDocument(self, doc):
        if _view is not None:
            try:
                matches = _view.Object.Document is doc
            except (RuntimeError, ReferenceError):
                matches = True
            if matches:
                _end()


class _RecoverySaveFilter(QtCore.QObject):
    """AutoSaver serializes directly, without the normal document-save signals."""

    def eventFilter(self, watched, event):
        try:
            if (_enabled and _view is not None and not _saving
                    and event.type() == QtCore.QEvent.Type.Timer):
                view = _view
                doc = view.Object.Document
                _observer.slotStartSaveDocument(doc, "")

                def resume():
                    # A callback from a retired edit must never affect the next one.
                    if _enabled and _view is view and _observer is not None:
                        _observer.slotFinishSaveDocument(doc, "")

                fcgui.defer(resume)
        except Exception as exc:
            console.warning("could not protect sketch settings during a recovery save: %s" % exc)
        return False


def _watch_recovery_saves():
    global _autosaver, _save_filter
    if _autosaver is not None:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for obj in app.findChildren(QtCore.QObject):
        if obj.metaObject().className().replace("__", "::") == constants.CLASS_AUTO_SAVER:
            _save_filter = _RecoverySaveFilter()
            obj.installEventFilter(_save_filter)
            _autosaver = obj
            return


@console.guarded("watch the current sketch drawing aids", level="warning")
def _poll():
    if not _enabled:
        return
    _watch_recovery_saves()
    sketch = fcgui.sketch_in_edit()
    if sketch is None or not fcgui.jellyjams_active():
        _end()
    elif not _saving:
        _begin(sketch.ViewObject)


@console.guarded("start automatic sketch drawing aids", level="warning")
def enable():
    """Watch edit/save boundaries and handle a sketch already in edit. Idempotent."""
    global _enabled, _observer, _timer
    if not _enabled:
        observer = _Observer()
        # Save observation is required before changing a saved view property.
        FreeCAD.addDocumentObserver(observer)
        _observer = observer
        try:
            FreeCADGui.addDocumentObserver(observer)
        except Exception:
            # Older hosts without GUI observers use the same edit polling fallback
            # as sheet_sketch. App save callbacks remain installed.
            pass
        _enabled = True
        _timer = QtCore.QTimer()
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(_poll)
        _timer.start()
    _poll()


@console.guarded("stop automatic sketch drawing aids", level="warning")
def disable():
    """Stop callbacks and restore before leave/quit; enable resumes after Cancel."""
    global _enabled, _observer, _timer, _autosaver, _save_filter
    _enabled = False
    if _autosaver is not None:
        with console.guard("remove the sketch recovery-save filter", level="warning"):
            if fcgui.is_alive(_autosaver):
                _autosaver.removeEventFilter(_save_filter)
        _autosaver = None
        _save_filter = None
    if _timer is not None:
        with console.guard("stop the sketch drawing aids timer", level="warning"):
            _timer.stop()
            _timer.deleteLater()
        _timer = None
    if _observer is not None:
        try:
            FreeCADGui.removeDocumentObserver(_observer)
        except Exception:
            pass
        with console.guard("remove the sketch drawing aids save observer", level="warning"):
            FreeCAD.removeDocumentObserver(_observer)
        _observer = None
    _end()
