# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Gives new tree objects their SolidWorks names.

A single document observer collects new objects and renames them on the next
event-loop turn, oldest first. Nothing but ``Label`` is written.
"""

import FreeCAD
from PySide import QtCore

from jellyjams import console, constants, doc_utils, fcgui
from jellyjams import naming_rules as rules

POSTPONE_MS = 500

TYPE_PLANE = "App::Plane"
TECHDRAW_PREFIX = "TechDraw::"
REFRESH_PROPERTIES = ("JointType", "Distance")
JOINT_TYPE_PROPERTY = "JointType"
DISTANCE_PROPERTY = "Distance"
GROUND_PROPERTY = "ObjectToGround"
LINK_TARGET_PROPERTY = "LinkedObject"
COMPONENT_TYPES = (constants.TYPE_LINK, constants.TYPE_ASSEMBLY_LINK)

# Qt translation contexts in which FreeCAD translates the default labels it writes.
JOINT_TYPE_CONTEXT = "Assembly"
PROJECTION_TYPE_CONTEXT = "DrawProjGroupItem"
TEMPLATE_CONTEXT = "DrawSVGTemplate"

MARKER_BASES = (
    (constants.PROP_HOST_SHEET, "Sheet Sketch"),
    (constants.PROP_SHOWN_SKETCH, "Sheet Sketch View"),
    (constants.PROP_SHEET_NOTE, "Text"),
)
KIND_BASES = {constants.KIND_SURFACE: "Surface Finish", constants.KIND_WELD: "Weld Symbol"}

_observer = None
_enabled = False
_start_error_reported = False
_queue = []            # [(doc_name, obj_name, type_id)], oldest first
_pending_links = []    # [(doc_name, obj_name)]: components whose LinkedObject was still empty
_refresh_docs = []     # names of documents whose assembly names need a refresh
_pass_pending = False
_ui_words = {}         # translation context -> FreeCAD's words in the UI language


# --- public API --------------------------------------------------------------------------


def enable():
    global _enabled, _observer, _start_error_reported
    if _observer is None:
        observer = _TreeNamingObserver()
        try:
            FreeCAD.addDocumentObserver(observer)
        except Exception as exc:
            if not _start_error_reported:
                _start_error_reported = True
                console.error("FeatureManager tree naming did not start: %s" % exc)
            return
        _observer = observer
    _enabled = True


def disable():
    global _enabled
    _enabled = False


def is_enabled():
    return _enabled and _observer is not None


def refresh_drawing(doc):
    with console.guard("update default labels in the drawing", level="silent"):
        if doc is None or not fcgui.jellyjams_active():
            return
        if getattr(doc, "Restoring", False) or fcgui.techdraw_tool_running():
            return
        for obj in list(doc.Objects):
            with console.guard("update one drawing label", level="silent"):
                type_id = doc_utils.type_id(obj)
                if type_id == constants.TYPE_PROJ_ITEM:
                    _refresh_projection_label(obj)
                elif type_id == constants.TYPE_TEMPLATE:
                    _refresh_template_label(doc, obj)


# --- observer -----------------------------------------------------------------------------


class _TreeNamingObserver:
    """Registered once; does nothing while another workbench is active."""

    def slotCreatedObject(self, obj):
        _on_created(obj)

    def slotChangedObject(self, obj, prop):
        if prop in REFRESH_PROPERTIES:
            _on_refresh_property_changed(obj)
        elif prop == LINK_TARGET_PROPERTY and _pending_links:
            _on_link_target_changed(obj)

    def slotDeletedObject(self, obj):
        _on_deleted(obj)

    def slotDeletedDocument(self, doc):
        _on_document_closed(doc)


def _gate_open():
    return _enabled and fcgui.jellyjams_active()


@console.guarded("note a new object for renaming", level="log")
def _on_created(obj):
    if not _gate_open():
        return
    doc = obj.Document
    if doc is None or getattr(doc, "Restoring", False):
        return
    _request_refresh(doc.Name)
    if not getattr(doc, "Transacting", False):
        _queue.append((doc.Name, obj.Name, obj.TypeId))
    _schedule_pass()


@console.guarded("react to a mate type or distance change", level="log")
def _on_refresh_property_changed(obj):
    if not _gate_open():
        return
    doc = obj.Document
    if doc is None or getattr(doc, "Restoring", False):
        return
    _request_refresh(doc.Name)
    _schedule_pass()


@console.guarded("react to a new link target", level="log")
def _on_link_target_changed(obj):
    if not _gate_open():
        return
    key = _identity(obj)
    if key not in _pending_links:
        return
    doc = obj.Document
    if doc is None or getattr(doc, "Restoring", False) or getattr(doc, "Transacting", False):
        return
    _pending_links.remove(key)
    entry = (key[0], key[1], obj.TypeId)
    if entry not in _queue:
        _queue.append(entry)
    _schedule_pass()


@console.guarded("react to a deleted object", level="log")
def _on_deleted(obj):
    if _pending_links:
        key = _identity(obj)
        if key in _pending_links:
            _pending_links.remove(key)
    if not _gate_open() or GROUND_PROPERTY not in _property_names(obj):
        return
    doc = obj.Document
    if doc is None:
        return
    _request_refresh(doc.Name)
    _schedule_pass()


@console.guarded("react to a closed document", level="log")
def _on_document_closed(doc):
    name = getattr(doc, "Name", None)
    if name and _pending_links:
        _pending_links[:] = [key for key in _pending_links if key[0] != name]


def _request_refresh(doc_name):
    if doc_name not in _refresh_docs:
        _refresh_docs.append(doc_name)


# --- deferred pass ---------------------------------------------------------------------------


def _schedule_pass(ms=0):
    global _pass_pending
    if _pass_pending:
        return
    _pass_pending = True
    try:
        QtCore.QTimer.singleShot(ms, _run_pass)
    except Exception as exc:
        _pass_pending = False
        console.log("rename timer not started: %s" % exc)


def _run_pass():
    global _pass_pending
    _pass_pending = False
    postponed = False
    with console.guard("apply SolidWorks names to new objects", level="log"):
        postponed = _rename_queued()
    with console.guard("update mate and component names", level="log"):
        _refresh_assemblies()
    with console.guard("tidy the list of links without a target", level="log"):
        _drop_missing_pending()
    if postponed:
        _schedule_pass(POSTPONE_MS)


def _rename_queued():
    """Rename queued objects oldest first. Returns True to retry later because a
    TechDraw tool is still running."""
    if not _queue:
        return False
    _queue[:] = [entry for entry in _queue if _lookup(entry[0], entry[1]) is not None]
    if any(entry[2].startswith(TECHDRAW_PREFIX) for entry in _queue):
        if fcgui.techdraw_tool_running():
            return True
    entries = list(_queue)
    del _queue[:]
    for doc_name, obj_name, _type_id in entries:
        _rename_one(doc_name, obj_name)
    return False


def _rename_one(doc_name, obj_name):
    obj = _lookup(doc_name, obj_name)
    if obj is None:
        return
    try:
        target = _target_label(obj, _other_labels(obj.Document, obj))
        if target and target != obj.Label:
            obj.Label = target
        if doc_utils.type_id(obj) in COMPONENT_TYPES:
            _track_link(doc_name, obj_name, obj)
            _request_refresh(doc_name)
    except Exception as exc:
        console.log("skipped naming %s: %s" % (obj_name, exc))


def _track_link(doc_name, obj_name, obj):
    """Remember a component that could not be named yet because it has no target.

    Assembly_InsertNewPart creates its link first and only sets LinkedObject when
    the dialog is accepted; the target change puts the link back in the queue.
    """
    key = (doc_name, obj_name)
    if _linked_object(obj) is None:
        if key not in _pending_links:
            _pending_links.append(key)
    elif key in _pending_links:
        _pending_links.remove(key)


def _drop_missing_pending():
    if _pending_links:
        _pending_links[:] = [key for key in _pending_links if _lookup(*key) is not None]


def _lookup(doc_name, obj_name):
    try:
        doc = FreeCAD.listDocuments().get(doc_name)
        return doc.getObject(obj_name) if doc is not None else None
    except Exception:
        return None


# --- naming of new objects -------------------------------------------------------------------


def _target_label(obj, labels):
    """The SolidWorks label for a new object, or None to leave it alone."""
    type_id = obj.TypeId
    props = _property_names(obj)
    for prop, base in MARKER_BASES:
        if prop in props:
            return rules.numbered_name(base, labels)
    if type_id == constants.TYPE_SYMBOL:
        kind = getattr(obj, constants.PROP_SYMBOL_TYPE, "") if constants.PROP_SYMBOL_TYPE in props else ""
        base = KIND_BASES.get(kind, rules.TYPE_BASE_NAMES[type_id])
        return rules.numbered_name(base, labels)
    base = rules.TYPE_BASE_NAMES.get(type_id)
    if base:
        return rules.numbered_name(base, labels)
    if type_id == TYPE_PLANE:
        fixed = rules.PLANE_NAMES.get(getattr(obj, "Role", None))
        return rules.fixed_name(fixed, obj.Label, labels) if fixed else None
    if type_id in rules.FOLDER_NAMES:
        return rules.fixed_name(rules.FOLDER_NAMES[type_id], obj.Label, labels)
    if type_id == constants.TYPE_PROJ_GROUP:
        return rules.standard3_name(labels)
    if type_id == constants.TYPE_PROJ_ITEM:
        return constants.PROJECTION_VIEW_LABELS.get(getattr(obj, "Type", None))
    if type_id in COMPONENT_TYPES:
        return _component_label(obj, labels)
    return None


def _linked_object(obj):
    linked = getattr(obj, LINK_TARGET_PROPERTY, None)
    if isinstance(linked, (tuple, list)):
        linked = linked[0] if linked else None
    return linked


def _component_label(obj, labels):
    if not _in_assembly(obj):
        return None
    linked = _linked_object(obj)
    if linked is None:
        return None
    linked_doc = linked.Document
    if linked_doc is not None and linked_doc.Name != obj.Document.Name:
        base = linked_doc.Label or linked_doc.Name
    else:
        base = rules.instance_base(linked.Label or linked.Name)
    return rules.instance_name(base, labels)


# --- assembly state mirror (fixed marker + mates) -------------------------------------------


def _refresh_assemblies():
    names = list(_refresh_docs)
    del _refresh_docs[:]
    if not names:
        return
    documents = FreeCAD.listDocuments()
    for name in names:
        doc = documents.get(name)
        if doc is None:
            continue
        with console.guard("update mate and component names in %s" % name, level="log"):
            _refresh_document(doc)


def _refresh_document(doc):
    if getattr(doc, "Restoring", False):
        return
    objects = list(doc.Objects)
    if not any(doc_utils.type_id(obj) == constants.TYPE_ASSEMBLY for obj in objects):
        return
    _mirror_fixed_markers(objects)
    _name_mates(objects)


def _mirror_fixed_markers(objects):
    grounded = set()
    for obj in objects:
        if GROUND_PROPERTY in _property_names(obj):
            target = getattr(obj, GROUND_PROPERTY, None)
            if target is not None:
                grounded.add(_identity(target))
    for obj in objects:
        if doc_utils.type_id(obj) not in COMPONENT_TYPES or not _in_assembly(obj):
            continue
        _write_label(obj, rules.fixed_marker(obj.Label, _identity(obj) in grounded))


def _name_mates(objects):
    defaults = rules.default_mate_labels(_ui_joint_types())
    for obj in objects:
        props = _property_names(obj)
        if JOINT_TYPE_PROPERTY not in props or GROUND_PROPERTY in props:
            continue
        if not any(doc_utils.is_derived(parent, constants.TYPE_JOINT_GROUP)
                   for parent in _in_list(obj)):
            continue
        base = rules.mate_base(getattr(obj, JOINT_TYPE_PROPERTY, None),
                               getattr(obj, DISTANCE_PROPERTY, None))
        if base is None:
            continue
        labels = [other.Label for other in objects if other.Name != obj.Name]
        _write_label(obj, rules.mate_label(obj.Label, base, labels, defaults))


def _ui_joint_types():
    """Joint type words as FreeCAD's joint dialog shows them in the UI language.

    The dialog fills its list from ``JointObject.TranslatedJointTypes`` (built when
    that module was imported), so that list is read as well as Qt's catalog.
    """
    words = list(_ui_translations(JOINT_TYPE_CONTEXT, rules.JOINT_TYPES))
    try:
        import JointObject
        words.extend(str(word) for word in JointObject.TranslatedJointTypes)
    except Exception:
        pass
    return words


def _ui_translations(context, sources):
    """FreeCAD's translation of every text in ``sources`` within ``context``.

    Asked from Qt once per context and kept; empty when Qt cannot answer, which
    leaves only the English defaults recognized.
    """
    words = _ui_words.get(context)
    if words is None:
        try:
            translate = QtCore.QCoreApplication.translate
            words = tuple(str(translate(context, source)) for source in sources)
        except Exception as exc:
            console.log("no %s translations: %s" % (context, exc))
            words = ()
        _ui_words[context] = words
    return words


def _write_label(obj, label):
    try:
        if label != obj.Label:
            obj.Label = label
    except Exception as exc:
        console.log("label of %s left unchanged: %s" % (getattr(obj, "Name", "?"), exc))


# --- existing drawings -----------------------------------------------------------------------


def _refresh_projection_label(obj):
    label = obj.Label
    localized = _ui_translations(PROJECTION_TYPE_CONTEXT, rules.PROJECTION_TYPES)
    if not rules.is_default_projection_label(label, localized):
        return
    target = constants.PROJECTION_VIEW_LABELS.get(getattr(obj, "Type", None))
    if target and not label.startswith(target):
        obj.Label = target


def _refresh_template_label(doc, obj):
    label = obj.Label
    if label.startswith(rules.SHEET_FORMAT):
        return
    localized = _ui_translations(TEMPLATE_CONTEXT, (rules.TEMPLATE_NAME,))
    if not rules.is_default_template_label(label, localized):
        return
    obj.Label = rules.numbered_name(rules.SHEET_FORMAT, _other_labels(doc, obj))


# --- helpers ---------------------------------------------------------------------------------


def _property_names(obj):
    try:
        return set(obj.PropertiesList)
    except Exception:
        return set()


def _in_list(obj):
    try:
        return list(obj.InList)
    except Exception:
        return []


def _in_assembly(obj):
    return any(doc_utils.is_derived(parent, constants.TYPE_ASSEMBLY) for parent in _in_list(obj))


def _identity(obj):
    doc = getattr(obj, "Document", None)
    return (getattr(doc, "Name", ""), obj.Name)


def _other_labels(doc, obj):
    name = obj.Name
    return [other.Label for other in doc.Objects if other.Name != name]
