# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Finding icons for the ribbon, the relation/mate panels and the sketch popup.

FreeCAD commands are shown with the icons FreeCAD itself provides, found while
running. JellyJams' own commands use the drawings in resources/icons. No
FreeCAD image is copied into the add-on.
"""

import os

from PySide import QtCore, QtGui

from jellyjams import console, constants, fcgui, paths

RESOURCE_ROOT = ":/icons"
RESOURCE_INDEX_LIMIT = 50000
IMAGE_SUFFIXES = (".svg", ".png", ".xpm", ".jpg", ".jpeg", ".bmp", ".ico")

_index = None   # (stem -> path, casefolded stem -> path); filled on first lookup


def _usable(icon):
    return icon is not None and not icon.isNull()


def _load(path):
    icon = QtGui.QIcon(path)
    return icon if _usable(icon) else None


def jj_icon(base):
    """The add-on icon named `base` (.svg preferred, then .png), or None."""
    if not base:
        return None
    try:
        path = paths.icon_path(base)
        return _load(path) if path else None
    except Exception as exc:
        console.log("icon {} is unreadable: {}".format(base, exc))
        return None


def _stem(name):
    base = str(name).replace("\\", "/").rsplit("/", 1)[-1].strip()
    root, suffix = os.path.splitext(base)
    return root if suffix.lower() in IMAGE_SUFFIXES else base


def _prefer(table, key, path):
    known = table.get(key)
    if known is None or (not known.lower().endswith(".svg") and path.lower().endswith(".svg")):
        table[key] = path


def _build_index():
    exact, folded = {}, {}
    iterator = QtCore.QDirIterator(
        RESOURCE_ROOT,
        QtCore.QDir.Filter.Files,
        QtCore.QDirIterator.IteratorFlag.Subdirectories,
    )
    visited = 0
    # Upper bound on entries visited, in case the resource tree is malformed.
    while visited < RESOURCE_INDEX_LIMIT and iterator.hasNext():
        path = iterator.next()
        visited += 1
        base = path.rsplit("/", 1)[-1]
        root, suffix = os.path.splitext(base)
        if not root or suffix.lower() not in IMAGE_SUFFIXES:
            continue
        _prefer(exact, root, path)
        _prefer(folded, root.casefold(), path)
    return exact, folded


def resource_index():
    """Lookup tables of the icons FreeCAD compiles in under ':/icons', made on first use."""
    global _index
    if _index is None:
        try:
            _index = _build_index()
        except Exception as exc:
            console.log("FreeCAD's built-in icon list is unavailable: {}".format(exc))
            _index = ({}, {})
    return _index


def reset_index():
    global _index
    _index = None


def resource_icon(name):
    """Built-in FreeCAD icon whose file name (without extension) is `name`.

    An exact match wins over one that differs only in case.
    """
    if not name:
        return None
    try:
        stem = _stem(name)
        if not stem:
            return None
        exact, folded = resource_index()
        path = exact.get(stem) or folded.get(stem.casefold())
        return _load(path) if path else None
    except Exception as exc:
        console.log("lookup of built-in icon {} failed: {}".format(name, exc))
        return None


def command_action(cmd_id, index=None):
    """FreeCAD's QAction for a command, or for sub-entry `index` of a group command.

    FreeCAD makes these actions only after the command has been put in a
    toolbar or menu, so the result can be None.
    """
    gui = fcgui.gui()
    if gui is None:
        return None
    try:
        command = gui.Command.get(cmd_id)
        actions = list(command.getAction() or []) if command is not None else []
    except Exception:
        return None
    if index is None:
        return actions[0] if actions else None
    try:
        position = int(index)
    except (TypeError, ValueError):
        return None
    return actions[position] if 0 <= position < len(actions) else None


def _candidate_names(cmd_id, fc_icon):
    names = []
    info = (fcgui.command_info(cmd_id) or {}) if cmd_id else {}
    for name in (fc_icon, info.get("pixmap")):
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return names


def _file_icon(name):
    if name.startswith(":"):
        return _load(name) if QtCore.QFile.exists(name) else None
    if os.path.isabs(name) and os.path.isfile(name):
        return _load(name)
    return None


def _freecad_icon(name):
    gui = fcgui.gui()
    if gui is None:
        return None
    try:
        icon = gui.getIcon(name)
    except Exception:
        return None
    return icon if isinstance(icon, QtGui.QIcon) and _usable(icon) else None


def _find_command_icon(cmd_id, index, jj_icon_name, fc_icon):
    if cmd_id.startswith(constants.CMD_PREFIX):
        icon = jj_icon(jj_icon_name or constants.COMMAND_ICONS.get(cmd_id))
        if icon is not None:
            return icon
    action = command_action(cmd_id, index)
    if action is not None:
        icon = action.icon()
        if _usable(icon):
            return icon
    names = _candidate_names(cmd_id, fc_icon)
    for lookup in (_file_icon, resource_icon, _freecad_icon):
        for name in names:
            icon = lookup(name)
            if icon is not None:
                return icon
    return None


def command_icon(cmd_id, index=None, jj_icon_name=None, fc_icon=None):
    """QIcon for a command's button; an empty QIcon when no source has one.

    Sources, tried in this order:
    1. for JellyJams ids only, the add-on icon `jj_icon_name`
       (constants.COMMAND_ICONS[cmd_id] when not given);
    2. the icon on FreeCAD's QAction for the command (or its sub-entry `index`);
    3. `fc_icon`, then the pixmap FreeCAD lists for the command, if either is
       a path to an existing file;
    4. those names looked up among FreeCAD's ':/icons' resources by file name;
    5. FreeCADGui.getIcon(name), tried last since it can hand back a placeholder.
    """
    icon = None
    try:
        icon = _find_command_icon(str(cmd_id or ""), index, jj_icon_name, fc_icon)
    except Exception as exc:
        console.log("icon search for {} raised an error: {}".format(cmd_id, exc))
    return icon if icon is not None else QtGui.QIcon()
