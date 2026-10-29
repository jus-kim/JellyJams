# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Stay in JellyJams when FreeCAD would change workbench on its own.

Three FreeCAD modules change to their own workbench when a Bool ``SwitchToWB``
in their preferences is true or missing:

* Assembly, when an assembly is activated;
* Part Design, when a body becomes active again (for example on leaving a
  sketch);
* TechDraw, when a drawing page is double-clicked.

JellyJams sets all three to false while it is the active workbench. Before the
first write, each user value goes into its own JellyJams parameter
(``TARGETS``):

* ``"1"``      the key existed and was true,
* ``"0"``      the key existed and was false,
* ``"absent"`` there was no key; restoring deletes it again.

FreeCAD saves those parameters with all others, so after a crash :func:`recover`
can put the user's values back at the next start.
"""

from jellyjams import console, constants, params

SWITCH_KEY = "SwitchToWB"

# (FreeCAD preference group, JellyJams backup key, name used in messages)
TARGETS = (
    (constants.PARAM_ASSEMBLY, constants.KEY_ASSEMBLY_BACKUP, "Assembly"),
    (constants.PARAM_PARTDESIGN, constants.KEY_PARTDESIGN_BACKUP, "Part Design"),
    (constants.PARAM_TECHDRAW_GENERAL, constants.KEY_TECHDRAW_BACKUP, "TechDraw"),
)

RECORD_TRUE = "1"
RECORD_FALSE = "0"
RECORD_ABSENT = "absent"
VALID_RECORDS = (RECORD_TRUE, RECORD_FALSE, RECORD_ABSENT)

_applied = False


def apply():
    """Back up each SwitchToWB unless a backup already exists, then set it to false."""
    global _applied
    for group_path, backup_key, name in TARGETS:
        try:
            group = params.group(group_path)
            record = _pending_record(backup_key)
            if record and record not in VALID_RECORDS:
                _discard_corrupt(backup_key, record, name)
                record = ""
            if not record:
                params.own().SetString(backup_key, _current_state(group))
            group.SetBool(SWITCH_KEY, False)
        except Exception as exc:
            console.warning("failed to turn off the %s workbench switch: %s" % (name, exc))
    _applied = True


def restore():
    """Return every SwitchToWB to its backed-up state; without a backup, change nothing."""
    _restore(announce=False)


def recover():
    """At startup, apply backups that an abnormal end of the last session left behind."""
    _restore(announce=True)


def is_applied():
    """True while the switches are overridden and at least one backup is pending."""
    try:
        return _applied and any(_pending_record(key) for _group, key, _name in TARGETS)
    except Exception:
        return False


def _pending_record(backup_key):
    return (params.own().GetString(backup_key, "") or "").strip()


def _current_state(group):
    if SWITCH_KEY not in (group.GetBools() or []):
        return RECORD_ABSENT
    return RECORD_TRUE if group.GetBool(SWITCH_KEY, True) else RECORD_FALSE


def _discard_corrupt(backup_key, record, name):
    console.warning(
        "deleted a damaged backup of the %s workbench switch (%r) and left the preference unchanged"
        % (name, record)
    )
    params.own().RemString(backup_key)


def _restore(announce):
    global _applied
    _applied = False
    for group_path, backup_key, name in TARGETS:
        try:
            record = _pending_record(backup_key)
            if not record:
                continue
            if record not in VALID_RECORDS:
                _discard_corrupt(backup_key, record, name)
                continue
            group = params.group(group_path)
            if record == RECORD_ABSENT:
                group.RemBool(SWITCH_KEY)
            else:
                group.SetBool(SWITCH_KEY, record == RECORD_TRUE)
            params.own().RemString(backup_key)
            if announce:
                console.message(
                    "put back the %s workbench switch saved before the last session ended without cleanup"
                    % name
                )
        except Exception as exc:
            console.warning("failed to put back the %s workbench switch: %s" % (name, exc))
