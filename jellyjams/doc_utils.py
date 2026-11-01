# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Document helpers shared by all areas: object checks, root and model objects, undo steps."""

import contextlib

from jellyjams import console, constants

CONTAINER_TYPES = (
    constants.TYPE_PART,
    constants.TYPE_BODY,
    constants.TYPE_ASSEMBLY,
    constants.TYPE_GROUP,
)
MODEL_PRIORITY = (
    constants.TYPE_ASSEMBLY,
    constants.TYPE_PART,
    constants.TYPE_BODY,
    constants.TYPE_PART_FEATURE,
)

# Sketches and other flat profiles derive from Part::Feature, but they are not models.
PROFILE_2D_TYPE = "Part::Part2DObject"

# A Part/Body origin owns its axes and planes, so they never count as root objects.
_ORIGIN_TYPES = ("App::LocalCoordinateSystem", "App::Origin")


def is_alive(obj):
    """True while `obj` is a document object that has not been deleted."""
    if obj is None:
        return False
    try:
        obj.Name
        return True
    except Exception:
        return False


def type_id(obj):
    """The TypeId of `obj`; "" when it is None, deleted or unreadable."""
    try:
        return str(obj.TypeId)
    except Exception:
        return ""


def is_derived(obj, type_id):
    """True when `obj` is of type `type_id` or a subtype; False on any failure."""
    try:
        return bool(obj.isDerivedFrom(type_id))
    except Exception:
        return False


def _holds(parent, obj):
    """True when `obj` is a member of `parent`, not merely referenced by it."""
    try:
        name = obj.Name
        for member in getattr(parent, "Group", None) or []:
            if getattr(member, "Name", None) == name:
                return True
    except Exception:
        pass
    try:
        return bool(parent.hasObject(obj))
    except Exception:
        return False


def is_contained(obj):
    """True when a Part, Body, Assembly or group listed in obj.InList has `obj` as a member."""
    try:
        parents = list(obj.InList)
    except Exception:
        return False
    for parent in parents:
        if any(is_derived(parent, kind) for kind in CONTAINER_TYPES + _ORIGIN_TYPES) and _holds(
            parent, obj
        ):
            return True
    return False


def root_objects(doc):
    """The objects of `doc` that sit in no container, in document order."""
    try:
        objects = list(doc.Objects)
    except Exception:
        return []
    return [obj for obj in objects if not is_contained(obj)]


def _in_tier(obj, kind):
    if not is_derived(obj, kind):
        return False
    if kind == constants.TYPE_PART_FEATURE and is_derived(obj, PROFILE_2D_TYPE):
        return False
    return True


def primary_model_objects(doc):
    """Every root object of the highest-ranked MODEL_PRIORITY type found in `doc`.

    Subtypes count. In the Part::Feature tier, 2D profiles (Part::Part2DObject) are
    skipped. Assembly drop and Make Drawing both rely on this one rule.
    """
    roots = root_objects(doc)
    for kind in MODEL_PRIORITY:
        found = [obj for obj in roots if _in_tier(obj, kind)]
        if found:
            return found
    return []


def pages(doc):
    """The TechDraw pages of `doc`, in document order."""
    try:
        objects = list(doc.Objects)
    except Exception:
        return []
    return [obj for obj in objects if is_derived(obj, constants.TYPE_PAGE)]


def parent_page(obj):
    """The first TechDraw page in obj.InList, or None."""
    try:
        for parent in obj.InList:
            if is_derived(parent, constants.TYPE_PAGE):
                return parent
    except Exception:
        pass
    return None


def add_property(obj, prop_type, name, group=constants.PROP_GROUP, tooltip=""):
    """Create property `name` on `obj` when it does not exist yet. True if it was created."""
    if name in obj.PropertiesList:
        return False
    obj.addProperty(prop_type, name, group, tooltip)
    return True


def _has_pending_transaction(doc):
    try:
        return bool(doc.HasPendingTransaction)
    except Exception:
        return False


def _active_transaction_id():
    """Id of FreeCAD's application-wide active transaction, or 0 when there is none."""
    try:
        import FreeCAD

        active = FreeCAD.getActiveTransaction()
        return int(active[1]) if active else 0
    except Exception:
        return 0


def _close(doc, abort, opened_id=0):
    """Commit or abort the document step, then release the application transaction.

    FreeCAD creates the document step only when something changes. A step without
    changes is therefore not closed by commitTransaction()/abortTransaction(), and
    the application-wide transaction would stay open; it is closed explicitly here.
    """
    try:
        if abort:
            doc.abortTransaction()
        else:
            doc.commitTransaction()
    finally:
        if opened_id and _active_transaction_id() == opened_id:
            try:
                import FreeCAD

                FreeCAD.closeActiveTransaction(bool(abort), opened_id)
            except Exception as exc:
                console.log("failed to close transaction %d: %s" % (opened_id, exc))


@contextlib.contextmanager
def transaction(doc, name, join_pending=False, abort_on_error=False):
    """Run the `with` block as one undo step called `name`.

    With join_pending and a step already pending in `doc`, yields False and neither
    opens nor closes anything. Otherwise opens the step, yields True and commits it
    when the block ends. If the block raises, the step is aborted (abort_on_error) or
    committed, and the exception propagates.
    """
    if doc is None or (join_pending and _has_pending_transaction(doc)):
        yield False
        return
    before = _active_transaction_id()
    doc.openTransaction(name)
    opened = _active_transaction_id()
    if opened == before:
        # No new id: the step joined a transaction someone else opened and will close.
        opened = 0
    try:
        yield True
    except BaseException:
        with console.guard("finish the undo step %r" % name, level="log"):
            _close(doc, abort_on_error, opened)
        raise
    _close(doc, False, opened)
