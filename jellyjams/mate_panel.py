# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Add Mate panel: SolidWorks-style mate buttons for entities picked in the active assembly.

While an assembly is in edit mode and no task dialog is open, the panel sits
first in the Tasks panel. It shows the picked entities and only the mates that
suit them; a mate button runs the matching FreeCAD Assembly joint command.
Which mates suit which entities is decided in ``mate_rules``.
"""

import functools

import FreeCADGui
from PySide import QtCore

from jellyjams import console, doc_utils, fcgui, mate_rules, panel_host

TITLE = "Add Mate"
RECHECK_MS = 500
ROW_SEPARATOR = " \u2013 "
ELEMENT_TYPES = ("Face", "Edge", "Vertex")

_host = panel_host.PanelHost()
_observer = None
_enabled = False
_timer = None
_last_state = None
_shown = False
_icons = {}


class _MateFrame(panel_host.PanelFrame):
    def __init__(self):
        super().__init__(TITLE)
        self.add_heading("Selected Entities")
        self.entities = self.add_list()
        self.add_heading("Mates")
        self.buttons = self.add_button_column()
        self.hint = self.add_hint()


class _Entity:
    __slots__ = ("kind", "component")

    def __init__(self, kind, component):
        self.kind = kind
        self.component = component

    @property
    def label(self):
        name = _label_of(self.component)
        return self.kind + ROW_SEPARATOR + name if name else self.kind


def _refresh_later():
    _scheduler.schedule()


def enable():
    """Begin watching the selection, the active assembly and open task dialogs."""
    global _observer, _enabled
    try:
        if _observer is None:
            observer = panel_host.SelectionRelay(_refresh_later)
            FreeCADGui.Selection.addObserver(observer)
            _observer = observer
        _enabled = True
        _start_timer()
        _refresh_later()
    except Exception as exc:
        console.warning("the Add Mate panel failed to start: %s" % exc)


def disable():
    """Stop watching, stop the periodic check and hide the panel."""
    global _observer, _enabled, _last_state, _shown
    _enabled = False
    _last_state = None
    _shown = False
    if _timer is not None:
        try:
            _timer.stop()
        except Exception:
            pass
    observer, _observer = _observer, None
    if observer is not None:
        try:
            FreeCADGui.Selection.removeObserver(observer)
        except Exception:
            pass
    try:
        _host.hide()
    except Exception:
        pass


def is_enabled():
    return _enabled


def refresh_now():
    """Fill the panel from the active assembly and the selection; hide it when it does not apply."""
    global _shown
    shown = False
    with console.guard("update the Add Mate panel", level="warning"):
        shown = _refresh()
    _shown = shown
    if not shown:
        console.safe_call(_host.hide, what="hide the Add Mate panel", level="log")


_scheduler = panel_host.RefreshScheduler(refresh_now)


def _start_timer():
    global _timer
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.timeout.connect(_on_timer)
    _timer.setInterval(RECHECK_MS)
    if not _timer.isActive():
        _timer.start()


@console.guarded("run the periodic Add Mate panel check", level="log")
def _on_timer():
    if not _enabled:
        return
    host_lost = _shown and _host.frame() is None
    if host_lost or _state(_assembly_utils()) != _last_state:
        refresh_now()


def _assembly_utils():
    try:
        import UtilsAssembly
    except Exception:
        return None
    return UtilsAssembly


def _active_assembly(utils):
    if utils is None:
        return None
    try:
        return utils.activeAssembly()
    except Exception:
        return None


def _object_key(obj):
    if obj is None:
        return None
    try:
        return (obj.Document.Name, obj.Name)
    except Exception:
        return None


def _state(utils):
    return (_object_key(_active_assembly(utils)), fcgui.task_dialog_open())


def _label_of(obj):
    if obj is None:
        return ""
    try:
        return str(obj.Label)
    except Exception:
        return ""


def _element_type(sub):
    element = str(sub or "").rsplit(".", 1)[-1]
    for name in ELEMENT_TYPES:
        if element.startswith(name) and element[len(name):].isdigit():
            return name
    return None


def _geometry_type(root, sub, element_type):
    try:
        shape = root.getSubObject(sub)
        geometry = shape.Surface if element_type == "Face" else shape.Curve
        return geometry.TypeId
    except Exception:
        return None


def kind_of(root, sub):
    """Row text describing the element that path ``sub`` names below ``root``."""
    element_type = _element_type(sub)
    if element_type is None:
        return mate_rules.kind_from(None, None)
    geometry = None if element_type == "Vertex" else _geometry_type(root, sub, element_type)
    return mate_rules.kind_from(element_type, geometry)


def _component_of(utils, assembly, root, sub):
    """(component, counts); counts is False for an entity outside the assembly."""
    resolve = getattr(utils, "getComponentReference", None) if utils is not None else None
    if resolve is None:
        return None, True
    try:
        component = resolve(assembly, root, sub)[0]
    except Exception:
        return None, False
    return component, component is not None


def _document_name(obj):
    try:
        return obj.Document.Name
    except Exception:
        return None


def _entry_root(entry):
    """The live root object of a selection entry, or None."""
    try:
        root = entry.Object
    except Exception:
        return None
    return root if doc_utils.is_alive(root) else None


def _entry_subs(entry):
    try:
        return list(entry.SubElementNames or ())
    except Exception:
        return []


def _selected_entities(utils, assembly):
    """Entities of the selection inside `assembly`, in selection order."""
    doc_name = _document_name(assembly)
    if doc_name is None:
        return []
    entities = []
    for entry in fcgui.selection_ex("*", 0):
        root = _entry_root(entry)
        # Object names are only unique per document: a root from another document
        # could share a name with a component path and be resolved by mistake.
        if root is None or _document_name(root) != doc_name:
            continue
        for sub in _entry_subs(entry):
            component, counts = _component_of(utils, assembly, root, sub)
            if counts:
                entities.append(_Entity(kind_of(root, sub), component))
    return entities


def _refresh():
    global _last_state
    if not _enabled:
        _last_state = None
        return False
    utils = _assembly_utils()
    assembly = _active_assembly(utils)
    dialog_open = fcgui.task_dialog_open()
    _last_state = (_object_key(assembly), dialog_open)
    if assembly is None or dialog_open:
        return False
    entities = _selected_entities(utils, assembly)
    if not entities:
        return False
    frame = _host.ensure(_MateFrame)
    if frame is None:
        return False
    _fill(frame, entities)
    _host.show()
    return True


def _fill(frame, entities):
    panel_host.fill_list(frame.entities, [(entity.label, None) for entity in entities])
    count = len(entities)
    same = count == 2 and entities[0].component is not None and panel_host.same_object(
        entities[0].component, entities[1].component)
    offered = []
    if count == 2:
        offered = mate_rules.offered_mates(entities[0].kind, entities[1].kind, same)
    panel_host.rebuild_buttons(frame.buttons, [_button_entry(label) for label in offered])
    text = mate_rules.hint(count, same, offered)
    frame.hint.setText(text or "")
    frame.hint.setVisible(bool(text))


def _button_entry(label):
    cmd_id = mate_rules.MATE_COMMANDS[label]
    return (label, _mate_icon(cmd_id), panel_host.command_tooltip(cmd_id, label),
            functools.partial(_on_mate_clicked, label))


def _mate_icon(cmd_id):
    icon = _icons.get(cmd_id)
    if icon is None:
        icon = panel_host.freecad_icon(cmd_id)
        if icon is not None:
            _icons[cmd_id] = icon
    return icon


@console.guarded("start the chosen mate", level="warning")
def _on_mate_clicked(label, *_args):
    fcgui.run_command(mate_rules.MATE_COMMANDS[label])
    _refresh_later()
