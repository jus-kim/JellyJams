# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Helpers around FreeCAD.ParamGet: typed get/set/remove, key presence and the
JSON crash backups.

Suffixes match FreeCAD's method names (GetBool, SetUnsigned, RemString, ...);
CONTENTS_TYPE_NAMES maps each one to the type name GetContents() reports.
"""

import json

from jellyjams import constants

TYPE_SUFFIXES = ("Bool", "Int", "Unsigned", "Float", "String")
CONTENTS_TYPE_NAMES = {
    "Bool": "Boolean",
    "Int": "Integer",
    "Unsigned": "Unsigned Long",
    "Float": "Float",
    "String": "String",
}


def _check_suffix(suffix):
    if suffix not in TYPE_SUFFIXES:
        raise ValueError("parameter type %r is not one of %s" % (suffix, ", ".join(TYPE_SUFFIXES)))


def group(path):
    """The parameter group at `path` (FreeCAD.ParamGet)."""
    import FreeCAD

    return FreeCAD.ParamGet(path)


def own():
    """The JellyJams parameter group."""
    return group(constants.PARAM_ROOT)


def contents(grp):
    """grp.GetContents() as a list of (type, name, value); [] if empty or unreadable."""
    try:
        return list(grp.GetContents() or [])
    except Exception:
        return []


def has_key(grp, name, suffix):
    """True when `grp` holds an entry named `name` whose type matches `suffix`."""
    _check_suffix(suffix)
    type_name = CONTENTS_TYPE_NAMES[suffix]
    try:
        entries = grp.GetContents()
    except Exception:
        try:
            return name in (getattr(grp, "Get%ss" % suffix)() or [])
        except Exception:
            return False
    for entry in entries or []:
        try:
            if entry[0] == type_name and entry[1] == name:
                return True
        except Exception:
            continue
    return False


def get_value(grp, suffix, name, default=None):
    """grp.Get<suffix>(name[, default]); with `default` None, FreeCAD picks the default."""
    _check_suffix(suffix)
    getter = getattr(grp, "Get" + suffix)
    if default is None:
        return getter(name)
    return getter(name, default)


def set_value(grp, suffix, name, value):
    """grp.Set<suffix>(name, value)."""
    _check_suffix(suffix)
    getattr(grp, "Set" + suffix)(name, value)


def remove_value(grp, suffix, name):
    """grp.Rem<suffix>(name)."""
    _check_suffix(suffix)
    getattr(grp, "Rem" + suffix)(name)


def get_bool(path, name, default):
    """Bool value at path/name; `default` if it is missing or cannot be read. Never raises."""
    try:
        return bool(group(path).GetBool(name, bool(default)))
    except Exception:
        return default


def get_float(path, name, default):
    """Float value at path/name; `default` if it is missing or cannot be read. Never raises."""
    try:
        return float(group(path).GetFloat(name, float(default)))
    except Exception:
        return default


def get_string(path, name, default=""):
    """String value at path/name; `default` if it is missing or cannot be read. Never raises."""
    try:
        return str(group(path).GetString(name, str(default)))
    except Exception:
        return default


# --- crash-backup strings in the JellyJams group -----------------------------------------


def backup_pending(key):
    """True when the backup string `key` holds anything. Never raises."""
    try:
        return bool(own().GetString(key, ""))
    except Exception:
        return False


def load_backup(key):
    """("none", None) | ("ok", parsed JSON) | ("corrupt", reason). Never raises."""
    try:
        raw = own().GetString(key, "")
    except Exception as exc:
        return ("corrupt", "reading the parameter failed: %s" % exc)
    if not raw:
        return ("none", None)
    try:
        return ("ok", json.loads(raw))
    except Exception as exc:
        return ("corrupt", "not valid JSON: %s" % exc)


def save_backup(key, data):
    """Write `data` as plain JSON, the format every JellyJams release reads."""
    own().SetString(key, json.dumps(data))


def clear_backup(key, remove=False):
    """Mark the backup as finished: set it to "" or delete the key; both read as no backup."""
    grp = own()
    if remove:
        grp.RemString(key)
    else:
        grp.SetString(key, "")
