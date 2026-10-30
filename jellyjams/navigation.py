# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""SolidWorks mouse navigation while JellyJams is the active workbench.

FreeCAD stores the navigation style as the String ``NavigationStyle`` in
``Preferences/View`` and switches every open 3D view as soon as it changes.

Before the first write, the user's own setting is saved in the JellyJams group under
``OriginalNavigationStyle`` as ``{"existed": bool, "value": str or null}`` (the 0.1.0
format), so the next start can undo a session that crashed. A readable backup found at install time is
kept untouched: it holds the user's real setting from a session that ended before JellyJams
could restore it.

None of the public functions raise; problems are reported through ``jellyjams.console``.
"""

from jellyjams import console, constants, params

BACKUP_KEY = constants.KEY_NAV_BACKUP
STYLE_KEY = "NavigationStyle"
SW_STYLE = "Gui::SolidWorksNavigationStyle"

_installed = False


def install():
    """Switch FreeCAD to SolidWorks navigation, saving the user's setting first.

    Calling it again while it is in effect changes nothing.
    """
    global _installed
    with console.guard("switch to SolidWorks mouse navigation"):
        if _installed and params.backup_pending(BACKUP_KEY):
            return
        view = params.group(constants.PARAM_VIEW)
        if not _ensure_backup(view):
            return
        if _current(view) != (True, SW_STYLE):
            params.set_value(view, "String", STYLE_KEY, SW_STYLE)
        _installed = True
        from jellyjams import orbit

        orbit.install()


def uninstall():
    """Put the user's navigation style back exactly and drop the backup.

    Works from the saved backup alone, so it also undoes a leftover one. Without a backup it
    does nothing and prints nothing.
    """
    global _installed
    _installed = False
    _stop_orbit()
    with console.guard("restore the navigation style"):
        _put_back()


def recover():
    """Startup crash recovery: undo a navigation style change an earlier session left behind."""
    global _installed
    _installed = False
    _stop_orbit()
    with console.guard("restore the navigation style left over from the previous session",
                       level="warning"):
        if _put_back():
            console.message(
                "restored the navigation style that the previous session left changed "
                "(unclean exit)"
            )


def is_installed():
    """True while the SolidWorks style set by install() is in effect."""
    try:
        return _installed and params.backup_pending(BACKUP_KEY)
    except Exception:
        return False


# --- helpers ---------------------------------------------------------------------------


def _stop_orbit():
    with console.guard("stop balanced middle-button orbiting"):
        from jellyjams import orbit

        orbit.uninstall()


def _current(view):
    """(existed, value) of NavigationStyle; value is None when the key is missing."""
    if not params.has_key(view, STYLE_KEY, "String"):
        return (False, None)
    return (True, params.get_value(view, "String", STYLE_KEY))


def _backup_problem(data):
    """None when `data` is a usable backup record, else a short reason."""
    if not isinstance(data, dict) or "existed" not in data:
        return "expected an object with an 'existed' member"
    value = data.get("value")
    if value is not None and not isinstance(value, str):
        return "the saved value is not text"
    return None


def _read_backup():
    """("none", None) | ("ok", record) | ("bad", reason)."""
    state, data = params.load_backup(BACKUP_KEY)
    if state == "none":
        return ("none", None)
    if state == "corrupt":
        return ("bad", data)
    problem = _backup_problem(data)
    if problem is not None:
        return ("bad", problem)
    return ("ok", data)


def _ensure_backup(view):
    """Make sure a usable backup exists before NavigationStyle is written.

    Returns False when the current setting could not be saved; the caller must then leave
    the style alone, because it could not be restored exactly.
    """
    state, detail = _read_backup()
    if state == "ok":
        return True
    if state == "bad":
        console.warning(
            "replaced an unreadable navigation style backup (%s) with the current setting"
            % detail
        )
    existed, value = _current(view)
    try:
        params.save_backup(BACKUP_KEY, {"existed": existed, "value": value})
    except Exception as exc:
        console.warning(
            "kept the current navigation style: it could not be saved before the change (%s)"
            % exc
        )
        return False
    return True


def _put_back():
    """Apply the saved record and remove it. True when a record was restored."""
    state, detail = _read_backup()
    if state == "none":
        return False
    if state == "bad":
        console.warning(
            "discarded an unreadable navigation style backup (%s); the style was left as it is"
            % detail
        )
        params.clear_backup(BACKUP_KEY, remove=True)
        return False
    view = params.group(constants.PARAM_VIEW)
    value = detail.get("value")
    if detail.get("existed") and value is not None:
        if _current(view) != (True, value):
            params.set_value(view, "String", STYLE_KEY, value)
    elif params.has_key(view, STYLE_KEY, "String"):
        params.remove_value(view, "String", STYLE_KEY)
    params.clear_backup(BACKUP_KEY, remove=True)
    return True
