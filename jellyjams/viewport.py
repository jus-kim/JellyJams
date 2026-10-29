# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""3D view background and sketch colors while JellyJams is active.

Before the first write, the current state of every managed View key (its
value, or the fact that it is missing) is saved as JSON under
constants.KEY_VIEW_BACKUP. Leaving the workbench, quitting and the first start
after a crash all restore from that record.
On-disk record format, which must stay stable: {key: [type, existedBefore, previousValue]}.
"""

from jellyjams import console, constants, palette, params

MANAGED_KEYS = [
    ("Gradient", "Bool", True),
    ("RadialGradient", "Bool", False),
    ("UseBackgroundColorMid", "Bool", False),
    ("BackgroundColor2", "Unsigned", palette.packed_rgba(palette.GRADIENT_TOP)),
    ("BackgroundColor3", "Unsigned", palette.packed_rgba(palette.GRADIENT_BOTTOM)),
    ("EditedEdgeColor", "Unsigned", palette.packed_rgba(palette.SKETCH_UNDER_DEFINED)),
    ("FullyConstraintElementColor", "Unsigned", palette.packed_rgba(palette.SKETCH_FULLY_DEFINED)),
    ("FullyConstrainedColor", "Unsigned", palette.packed_rgba(palette.SKETCH_FULLY_DEFINED)),
    ("InvalidSketchColor", "Unsigned", palette.packed_rgba(palette.SKETCH_OVER_DEFINED)),
    ("ConstructionColor", "Unsigned", palette.packed_rgba(palette.SKETCH_CONSTRUCTION)),
    ("FullyConstraintConstructionElementColor", "Unsigned",
     palette.packed_rgba(palette.SKETCH_CONSTRUCTION_DEFINED)),
    ("ConstrainedDimColor", "Unsigned", palette.packed_rgba(palette.DIM_DRIVING)),
    ("NonDrivingConstrDimColor", "Unsigned", palette.packed_rgba(palette.DIM_DRIVEN)),
    ("ConstrainedIcoColor", "Unsigned", palette.packed_rgba(palette.RELATION_SYMBOLS)),
]

_TYPES = ("Bool", "Unsigned")
_TYPE_DEFAULTS = {"Bool": False, "Unsigned": 0}
_UNSIGNED_MAX = 0xFFFFFFFF

_applied = False


def _view_group():
    return params.group(constants.PARAM_VIEW)


def _snapshot(view):
    """{key: [type, existed, value]} describing every managed key right now."""
    record = {}
    for name, suffix, _value in MANAGED_KEYS:
        if params.has_key(view, name, suffix):
            previous = params.get_value(view, suffix, name, _TYPE_DEFAULTS[suffix])
            previous = bool(previous) if suffix == "Bool" else int(previous)
            record[name] = [suffix, True, previous]
        else:
            record[name] = [suffix, False, None]
    return record


def _usable_record():
    """The saved record as a dict, or None when there is none.

    A record that cannot be used is deleted after one warning.
    """
    status, data = params.load_backup(constants.KEY_VIEW_BACKUP)
    if status == "none":
        return None
    if status == "ok" and isinstance(data, dict):
        return data
    reason = data if status == "corrupt" else "not a JSON object"
    console.warning("the saved 3D view color backup was unusable and has been deleted (%s)" % reason)
    params.clear_backup(constants.KEY_VIEW_BACKUP)
    return None


def apply():
    """Save the managed View keys (an already pending record is kept) and write
    the JellyJams colors. Does nothing while applied."""
    global _applied
    if _applied:
        return
    try:
        view = _view_group()
        if _usable_record() is None:
            params.save_backup(constants.KEY_VIEW_BACKUP, _snapshot(view))
        for name, suffix, value in MANAGED_KEYS:
            params.set_value(view, suffix, name, value)
        _applied = True
    except Exception as exc:
        console.warning("setting the 3D view background and sketch colors failed: %s" % exc)


def _entry_problem(entry):
    """What is wrong with one record entry; "" when it can be restored."""
    if not isinstance(entry, (list, tuple)) or len(entry) != 3:
        return "not a [type, existed, value] triple"
    suffix, existed, value = entry
    if suffix not in _TYPES:
        return "type %r is neither Bool nor Unsigned" % (suffix,)
    if not isinstance(existed, bool):
        return "the existed flag must be true or false"
    if not existed:
        return ""
    if suffix == "Bool" and not isinstance(value, bool):
        return "a Bool entry needs true or false"
    if suffix == "Unsigned" and (isinstance(value, bool) or not isinstance(value, int)
                                 or not 0 <= value <= _UNSIGNED_MAX):
        return "an Unsigned entry needs an integer from 0 to 4294967295"
    return ""


def _restore_record(record):
    """Write every usable entry back and return how many were restored.

    A failing write raises before the record is cleared, so it survives for
    another attempt.
    """
    view = _view_group()
    restored = 0
    for name, entry in record.items():
        problem = _entry_problem(entry)
        if problem:
            console.warning("ignored the 3D view color backup entry %r: %s" % (name, problem))
            continue
        suffix, existed, value = entry
        if existed:
            params.set_value(view, suffix, name, value)
        else:
            params.remove_value(view, suffix, name)
        restored += 1
    params.clear_backup(constants.KEY_VIEW_BACKUP)
    return restored


def restore():
    """Put the managed View keys back from the saved record, when there is one."""
    global _applied
    _applied = False
    try:
        record = _usable_record()
        if record is not None:
            _restore_record(record)
    except Exception as exc:
        console.warning("putting back the 3D view background and sketch colors failed: %s" % exc)


def recover():
    """At startup, finish a restore that a crash interrupted."""
    try:
        if not params.backup_pending(constants.KEY_VIEW_BACKUP):
            return
        record = _usable_record()
        if record is not None and _restore_record(record):
            console.message("3D background and sketch colors are back to your settings "
                            "(the last session ended with an unclean exit)")
    except Exception as exc:
        console.warning("putting back the 3D view colors left by a crashed session failed: %s" % exc)


def is_applied():
    return _applied
