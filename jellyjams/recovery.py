# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Crash repair, run once at every GUI start.

A backup string that is not empty at startup means the last session ended
while JellyJams' settings were still applied. Each area restores its own keys
in a separately guarded step. Nothing is printed when there is nothing to
repair.
"""

import importlib

from jellyjams import console, constants, params


def _navigation_backup_problem(data):
    from jellyjams import navigation

    return navigation._backup_problem(data)


def _shortcut_backup_problem(data):
    if not isinstance(data, dict):
        return "not a JSON object of command id -> [existed, value]"
    for command, entry in data.items():
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or not isinstance(entry[0], bool)
            or not (entry[1] is None or isinstance(entry[1], str))
        ):
            return "bad entry for %s" % command
    return None


def _recover_checked(key, problem_of, description, module_name):
    """Check a JSON backup before its module restores from it.

    A bad backup is deleted with a single warning so it cannot trouble later
    starts.
    """
    state, data = params.load_backup(key)
    if state == "none":
        return
    reason = data if state == "corrupt" else problem_of(data)
    if reason is None:
        importlib.import_module(module_name).recover()
        return
    console.warning(
        "deleted the %s backup left by the last session because it could not be used (%s)"
        % (description, reason)
    )
    params.clear_backup(key, remove=True)


def _recover_viewport():
    importlib.import_module("jellyjams.viewport").recover()


def _recover_navigation():
    _recover_checked(
        constants.KEY_NAV_BACKUP,
        _navigation_backup_problem,
        "navigation style",
        "jellyjams.navigation",
    )


def _recover_shortcuts():
    _recover_checked(
        constants.KEY_SHORTCUT_BACKUP,
        _shortcut_backup_problem,
        "keyboard shortcut",
        "jellyjams.shortcuts",
    )


def _recover_switch_prefs():
    importlib.import_module("jellyjams.switch_prefs").recover()


def _recover_sketch_assist():
    importlib.import_module("jellyjams.sketch_assist").recover()


RECOVERY_STEPS = (
    ("repair the 3D view colors", _recover_viewport),
    ("repair the navigation style", _recover_navigation),
    ("repair the keyboard shortcuts", _recover_shortcuts),
    ("repair the workbench-switch preferences", _recover_switch_prefs),
    ("repair sketch snapping preferences", _recover_sketch_assist),
)


def run_startup_recovery():
    """Undo whatever the last session left applied. Never raises."""
    for what, step in RECOVERY_STEPS:
        with console.guard(what, level="warning"):
            step()
