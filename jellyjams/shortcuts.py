# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""SolidWorks keyboard shortcuts while JellyJams is the active workbench.

FreeCAD keeps shortcut overrides in ``Preferences/Shortcut``: one String per command id,
holding QKeySequence text. A change takes effect at once, an empty value unbinds the
command, and removing the key brings back the command's built-in shortcut.

Qt triggers neither action when two live actions share a key. So while JellyJams is
active, every other command that currently owns one of the keys in SHORTCUTS is unbound
(FreeCAD 1.1 gives Ctrl+B to Std_ViewBoxZoom, for example). Commands the running FreeCAD
does not have are skipped.

Before the first write, the state of every touched command is saved in the JellyJams group
under ``OriginalShortcuts`` as ``{command: [existed, value]}`` (the 0.1.0 format), so the next
start can undo a session that crashed. A readable backup found at install time is kept
untouched because it holds the user's real settings. If it does not cover every new
override, installation is deferred until that backup has been restored.

None of the public functions raise; problems are reported through ``jellyjams.console``.
"""

from jellyjams import console, constants, params

BACKUP_KEY = constants.KEY_SHORTCUT_BACKUP

SHORTCUTS = [
    ("Std_ViewFitAll", "F"),
    ("Std_ViewZoomOut", "Z"),
    ("Std_ViewZoomIn", "Shift+Z"),
    ("Std_Refresh", "Ctrl+B"),
    ("Std_ViewFront", "Ctrl+1"),
    ("Std_ViewRear", "Ctrl+2"),
    ("Std_ViewLeft", "Ctrl+3"),
    ("Std_ViewRight", "Ctrl+4"),
    ("Std_ViewTop", "Ctrl+5"),
    ("Std_ViewBottom", "Ctrl+6"),
    ("Std_ViewIsometric", "Ctrl+7"),
    ("JellyJams_NormalTo", "Ctrl+8"),
    ("JellyJams_ViewOrientation", "Space"),
]

_installed = False


def install():
    """Apply SHORTCUTS and unbind clashing commands, saving their previous state first.

    Calling it again while it is in effect changes nothing.
    """
    global _installed
    with console.guard("apply the SolidWorks keyboard shortcuts"):
        if _installed and params.backup_pending(BACKUP_KEY):
            return
        group = params.group(constants.PARAM_SHORTCUT)
        available = _available_commands()
        if available is None:
            console.log("could not list FreeCAD's commands; setting every shortcut "
                        "without checking for missing or clashing commands")
            wanted = list(SHORTCUTS)
        else:
            wanted = [(cmd, keys) for cmd, keys in SHORTCUTS if cmd in available]
            missing = [cmd for cmd, _keys in SHORTCUTS if cmd not in available]
            if missing:
                console.log("no shortcut set for %s: not available in this FreeCAD"
                            % ", ".join(missing))
        clashes = _clashing_commands(wanted, available)
        # Clashing commands come first so a key is never owned twice after a write.
        targets = {cmd: "" for cmd in clashes}
        targets.update(wanted)
        if not targets:
            return
        if not _ensure_backup(group, targets):
            return
        failed = _write(group, targets.items())
        if failed:
            console.warning("could not set the shortcut of %s" % "; ".join(failed))
        for cmd, keys in clashes.items():
            console.log("unbound %s (%s) while JellyJams is active, because a SolidWorks "
                        "shortcut uses the same key" % (cmd, keys))
        _installed = True


def uninstall():
    """Put every touched shortcut back exactly and drop the backup.

    Works from the saved backup alone, so it also undoes a leftover one. Without a backup it
    does nothing and prints nothing.
    """
    global _installed
    _installed = False
    with console.guard("restore the keyboard shortcuts"):
        _put_back()


def recover():
    """Startup crash recovery: undo shortcut changes an earlier session left behind."""
    global _installed
    _installed = False
    with console.guard("restore the keyboard shortcuts left over from the previous session",
                       level="warning"):
        if _put_back():
            console.message(
                "restored the keyboard shortcuts that the previous session left changed "
                "(unclean exit)"
            )


def is_installed():
    """True while the shortcuts set by install() are in effect."""
    try:
        return _installed and params.backup_pending(BACKUP_KEY)
    except Exception:
        return False


# --- key sequences and commands ------------------------------------------------------------


def _normalized(keys):
    """Comparable form of a key sequence text ("ctrl+b" and "Ctrl+B" give the same)."""
    text = (keys or "").strip()
    if not text:
        return ""
    try:
        from PySide import QtGui

        sequence = QtGui.QKeySequence(text)
        portable = sequence.toString(QtGui.QKeySequence.SequenceFormat.PortableText)
        if portable:
            text = portable
    except Exception:
        pass
    return "".join(text.split()).lower()


def _gui():
    try:
        import FreeCADGui

        return FreeCADGui
    except Exception:
        return None


def _available_commands():
    """Set of the command ids FreeCAD knows, or None when they cannot be listed."""
    module = _gui()
    if module is None:
        return None
    try:
        return set(module.listCommands())
    except Exception:
        return None


def _clashing_commands(wanted, available):
    """{command: current keys} for commands outside SHORTCUTS that own one of the wanted keys."""
    module = _gui()
    if not available or module is None:
        return {}
    keys = {_normalized(keys) for _cmd, keys in wanted}
    keys.discard("")
    ours = {cmd for cmd, _keys in SHORTCUTS}
    found = {}
    for cmd in sorted(available):
        if cmd in ours:
            continue
        try:
            command = module.Command.get(cmd)
            current = command.getShortcut() if command is not None else ""
        except Exception:
            continue
        if current and _normalized(current) in keys:
            found[cmd] = str(current)
    return found


# --- backup record ---------------------------------------------------------------------------


def _state(group, cmd):
    """[existed, value] of one command's override; value is None when the key is missing."""
    if not params.has_key(group, cmd, "String"):
        return [False, None]
    return [True, params.get_value(group, "String", cmd)]


def _entry_ok(entry):
    return (
        isinstance(entry, (list, tuple))
        and len(entry) == 2
        and isinstance(entry[0], bool)
        and (entry[1] is None or isinstance(entry[1], str))
    )


def _read_backup():
    """("none", None) | ("ok", record dict) | ("bad", reason)."""
    state, data = params.load_backup(BACKUP_KEY)
    if state == "none":
        return ("none", None)
    if state == "corrupt":
        return ("bad", data)
    if not isinstance(data, dict):
        return ("bad", "expected an object mapping command ids to [existed, value]")
    return ("ok", data)


def _ensure_backup(group, targets):
    """Make sure every command in `targets` can be restored before anything is written.

    Returns False when the current state could not be saved; the caller must then write
    nothing, because the change could not be undone exactly.
    """
    state, detail = _read_backup()
    if state == "ok":
        if any(not _entry_ok(detail.get(cmd)) for cmd in targets):
            console.warning("kept the current keyboard shortcuts: the pending backup "
                            "does not cover every target; it must be restored first")
            return False
        return True
    if state == "bad":
        console.warning(
            "replaced an unreadable keyboard shortcut backup (%s) with the current shortcuts"
            % detail
        )
    record = {cmd: _state(group, cmd) for cmd in targets}
    try:
        params.save_backup(BACKUP_KEY, record)
    except Exception as exc:
        console.warning(
            "kept the current keyboard shortcuts: they could not be saved before the change (%s)"
            % exc
        )
        return False
    return True


# --- writing and restoring --------------------------------------------------------------------


def _write(group, pairs):
    """Set each (command, keys) pair; returns "command (reason)" texts for the failures."""
    failed = []
    for cmd, keys in pairs:
        try:
            if _state(group, cmd) != [True, keys]:
                params.set_value(group, "String", cmd, keys)
        except Exception as exc:
            failed.append("%s (%s)" % (cmd, exc))
    return failed


def _restore_entries(group, entries):
    """Bring each command back to its saved [existed, value]; returns the failures."""
    ours = {cmd for cmd, _keys in SHORTCUTS}
    # SHORTCUTS commands give their keys up before the unbound commands get them back.
    order = [cmd for cmd in entries if cmd in ours] + [cmd for cmd in entries if cmd not in ours]
    failed = []
    for cmd in order:
        existed, value = entries[cmd]
        try:
            if existed:
                text = value if isinstance(value, str) else ""
                if _state(group, cmd) != [True, text]:
                    params.set_value(group, "String", cmd, text)
            elif params.has_key(group, cmd, "String"):
                params.remove_value(group, "String", cmd)
        except Exception as exc:
            failed.append("%s (%s)" % (cmd, exc))
    return failed


def _put_back():
    """Restore the saved record, then remove it.

    Returns True when a persisted record with at least one entry was restored completely.
    """
    state, detail = _read_backup()
    entries = {}
    persisted = False
    if state == "bad":
        console.warning(
            "discarded an unreadable keyboard shortcut backup (%s); the shortcuts were left "
            "as they are" % detail
        )
        params.clear_backup(BACKUP_KEY, remove=True)
    elif state == "ok":
        persisted = True
        skipped = []
        for cmd, entry in detail.items():
            if _entry_ok(entry):
                entries[cmd] = entry
            else:
                skipped.append(str(cmd))
        if skipped:
            console.warning("ignored unreadable shortcut backup entries for %s"
                            % ", ".join(skipped))
    if not entries and not persisted:
        return False
    failed = _restore_entries(params.group(constants.PARAM_SHORTCUT), entries)
    if failed:
        if persisted:
            console.warning("could not put back the shortcut of %s; the backup is kept so "
                            "the next start can try again" % "; ".join(failed))
        else:
            console.warning("could not put back the shortcut of %s" % "; ".join(failed))
        return False
    if persisted:
        params.clear_backup(BACKUP_KEY, remove=True)
    return persisted and bool(entries)
