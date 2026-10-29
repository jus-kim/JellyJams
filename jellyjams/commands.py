# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""BaseCommand for every JellyJams command, and their one-time registration.

Every module named in PROVIDERS offers get_commands(), which returns
{command_id: instance} for exactly its listed ids and does nothing else.
"""

import importlib

from jellyjams import console, constants, fcgui, paths

PROVIDERS = {
    "jellyjams.diagnostics": (constants.CMD_DIAGNOSTICS,),
    "jellyjams.sketch_tools": (constants.CMD_CENTERLINE, constants.CMD_MIDPOINT_LINE),
    "jellyjams.assembly_commands": (constants.CMD_NEW_ASSEMBLY, constants.CMD_ROTATE_COMPONENT),
    "jellyjams.make_drawing": (constants.CMD_MAKE_DRAWING,),
    "jellyjams.sheet_properties": (constants.CMD_SHEET_PROPERTIES,),
    "jellyjams.sheet_sketch": (
        constants.CMD_SHEET_LINE,
        constants.CMD_SHEET_RECTANGLE,
        constants.CMD_SHEET_CIRCLE,
        constants.CMD_SHEET_ARC,
        constants.CMD_SHEET_POLYGON,
    ),
    "jellyjams.sheet_text": (constants.CMD_NOTE,),
    "jellyjams.insert_picture": (constants.CMD_INSERT_PICTURE,),
    "jellyjams.projected_view": (constants.CMD_PROJECTED_VIEW,),
    "jellyjams.view_scale": (constants.CMD_VIEW_SCALE,),
    "jellyjams.surface_finish": (constants.CMD_SURFACE_FINISH,),
    "jellyjams.weld_symbol": (constants.CMD_WELD_SYMBOL,),
    "jellyjams.line_format": (constants.CMD_LINE_FORMAT,),
    "jellyjams.drawing_export": (constants.CMD_SAVE_PDF, constants.CMD_SAVE_DXF),
    "jellyjams.orientation": (constants.CMD_ORIENTATION, constants.CMD_NORMAL_TO),
}

COMMAND_PREFIX = constants.CMD_PREFIX

_registration_done = False
_registered = []


class BaseCommand:
    """Shared base of the JellyJams commands.

    A subclass fills in the class attributes and overrides run(), plus
    is_active() when needed. The methods FreeCAD calls (GetResources, Activated,
    IsActive) never raise.
    """

    command_id = ""
    menu_text = ""
    tooltip = ""
    icon = None
    accel = ""
    # FreeCAD's CmdType: with none, a command counts as changing the document and is
    # disabled while a sketch or a task dialog is open.
    cmd_type = ""
    active_on_error = False

    def _icon_base(self):
        if self.icon is not None:
            return self.icon
        return constants.COMMAND_ICONS.get(self.command_id, "")

    def GetResources(self):
        try:
            resources = {
                "MenuText": str(self.menu_text or self.command_id),
                "ToolTip": str(self.tooltip or self.menu_text or ""),
                "Pixmap": paths.icon_path(self._icon_base()),
            }
            if self.accel:
                resources["Accel"] = str(self.accel)
            if self.cmd_type:
                resources["CmdType"] = str(self.cmd_type)
            return resources
        except Exception:
            console.log("GetResources failed for %s" % self.command_id)
            return {"MenuText": str(self.command_id), "ToolTip": "", "Pixmap": ""}

    def Activated(self, *args):
        # FreeCAD may pass a sub-command index; JellyJams commands have none and ignore it.
        try:
            self.run()
        except Exception:
            console.error("%s stopped with an error" % (self.menu_text or self.command_id),
                          with_traceback=True)

    def IsActive(self):
        try:
            return bool(self.is_active())
        except Exception:
            return bool(self.active_on_error)

    def run(self):
        """The command's action; subclasses override it."""

    def is_active(self):
        """Whether the command can run right now (default True); subclasses may override."""
        return True


def _provided(module_name, expected):
    """Import a provider and return its {id: instance}, or None after printing why that failed."""
    try:
        module = importlib.import_module(module_name)
        provided = dict(module.get_commands())
    except Exception:
        console.error("loading the commands from %s failed" % module_name, with_traceback=True)
        return None
    missing = [cmd_id for cmd_id in expected if cmd_id not in provided]
    if missing:
        console.warning("%s left out these commands: %s" % (module_name, ", ".join(missing)))
    return provided


def _ordered_ids(provided, expected):
    listed = [cmd_id for cmd_id in expected if cmd_id in provided]
    extra = sorted(cmd_id for cmd_id in provided if cmd_id not in expected)
    return listed + extra


def register_all():
    """Add every JellyJams command to FreeCAD on the first call and return the ids
    added. Later calls return [] and print nothing."""
    global _registration_done
    if _registration_done:
        return []
    module = fcgui.gui()
    if module is None:
        console.error("no commands registered: FreeCADGui is unavailable")
        return []
    _registration_done = True
    try:
        known = set(module.listCommands())
    except Exception:
        known = set()
    added = []
    for module_name, expected in PROVIDERS.items():
        provided = _provided(module_name, expected)
        if provided is None:
            continue
        for cmd_id in _ordered_ids(provided, expected):
            if not str(cmd_id).startswith(COMMAND_PREFIX):
                console.error("skipped %r: JellyJams command ids start with %s" % (cmd_id, COMMAND_PREFIX))
                continue
            if cmd_id in known:
                continue
            try:
                module.addCommand(cmd_id, provided[cmd_id])
            except Exception:
                console.error("registering %s failed" % cmd_id, with_traceback=True)
                continue
            known.add(cmd_id)
            added.append(cmd_id)
    _registered.extend(added)
    console.log("registered %d JellyJams commands with FreeCAD" % len(added))
    return list(added)


def registered_ids():
    """Command ids that register_all() added in this process."""
    return list(_registered)
