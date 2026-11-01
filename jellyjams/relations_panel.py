# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Add Relations panel (SolidWorks-style) for selected sketch entities.

While a sketch is in edit and some of its entities are selected, this panel
sits at the top of the Tasks panel. It shows the selection, the geometric
relations already attached to it, and buttons for the relations FreeCAD can
add. The decisions are made in ``relations_rules``.
"""

import functools

import FreeCADGui
from PySide import QtCore, QtWidgets

from jellyjams import console, constants, doc_utils, fcgui, panel_host, relations_rules

TITLE = "Add Relations"
FALLBACK_TITLE = "Relations"
HINT_TEXT = "No relations can be added to this selection."
DELETE_TEXT = "Delete"
DELETE_TOOLTIP = "Remove the relations selected under Existing Relations"
TRANSACTION_NAME = "Delete Relations"

_host = panel_host.PanelHost(constants.OBJ_PANEL_DOCK, FALLBACK_TITLE)
_observer = None
_enabled = False
_icons = {}


class _RelationsFrame(panel_host.PanelFrame):
    def __init__(self):
        super().__init__(TITLE)
        self.sketch = None
        self.add_heading("Selected Entities")
        self.entities = self.add_list()
        self.add_heading("Existing Relations")
        self.relations = self.add_list(multi_select=True)
        self.delete_button = QtWidgets.QPushButton(DELETE_TEXT, self)
        self.delete_button.setToolTip(DELETE_TOOLTIP)
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(_on_delete_clicked)
        self.layout().addWidget(self.delete_button)
        self.add_heading("Add Relations")
        self.buttons = self.add_button_column()
        self.hint = self.add_hint(HINT_TEXT)


def _refresh_later():
    _scheduler.schedule()


def enable():
    """Watch the selection; only one observer is ever registered."""
    global _observer, _enabled
    try:
        if _observer is None:
            observer = panel_host.SelectionRelay(_refresh_later)
            FreeCADGui.Selection.addObserver(observer)
            _observer = observer
        _enabled = True
        _refresh_later()
    except Exception as exc:
        console.warning("Add Relations panel is not available: %s" % exc)


def disable():
    """Stop watching the selection; hide the panel and its fallback dock."""
    global _observer, _enabled
    _enabled = False
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
    """Rebuild the panel for the current selection, or hide it when it does not apply."""
    shown = False
    with console.guard("update the Add Relations panel", level="warning"):
        shown = _refresh()
    if not shown:
        console.safe_call(_host.hide, what="hide the Add Relations panel", level="log")


_scheduler = panel_host.RefreshScheduler(refresh_now)


def _selected_names(sketch):
    names = []
    for entry in fcgui.selection_ex():
        if panel_host.same_object(getattr(entry, "Object", None), sketch):
            names.extend(getattr(entry, "SubElementNames", ()) or ())
    return names


def _constraints(sketch):
    try:
        return list(sketch.Constraints)
    except Exception:
        return []


def _refresh():
    if not _enabled:
        return False
    sketch = fcgui.sketch_in_edit()
    if sketch is None:
        return False
    entities = relations_rules.parse_selection(sketch, _selected_names(sketch))
    if not entities:
        return False
    frame = _host.ensure(_RelationsFrame)
    if frame is None:
        return False
    _fill(frame, sketch, entities)
    _host.show()
    return True


def _fill(frame, sketch, entities):
    frame.sketch = sketch
    panel_host.fill_list(frame.entities, [(entity.label, None) for entity in entities])
    existing = relations_rules.existing_relations(_constraints(sketch), entities)
    panel_host.fill_list(frame.relations, [("%s (no. %d)" % (name, index + 1), index)
                                           for index, name in existing])
    frame.delete_button.setEnabled(bool(existing))
    offered = relations_rules.offered_relations(entities)
    panel_host.rebuild_buttons(frame.buttons, [_button_entry(label) for label in offered])
    frame.hint.setVisible(not offered)


def _button_entry(label):
    cmd_id = relations_rules.RELATION_COMMANDS[label]
    return (label, _relation_icon(label, cmd_id),
            panel_host.command_tooltip(cmd_id, label),
            functools.partial(_on_relation_clicked, label))


def _relation_icon(label, cmd_id):
    icon = _icons.get(label)
    if icon is None:
        base = constants.RELATION_ICONS.get(label)
        icon = (panel_host.jj_icon(base) if base else None) or panel_host.freecad_icon(cmd_id)
        if icon is not None:
            _icons[label] = icon
    return icon


@console.guarded("apply the chosen relation", level="warning")
def _on_relation_clicked(label, *_args):
    fcgui.run_command(relations_rules.RELATION_COMMANDS[label])
    _refresh_later()


@console.guarded("remove the selected relations", level="warning")
def _on_delete_clicked(*_args):
    frame = _host.frame()
    if frame is None:
        return
    indices = [item.data(QtCore.Qt.ItemDataRole.UserRole)
               for item in frame.relations.selectedItems()]
    order = relations_rules.deletion_order(indices)
    if not order:
        return
    sketch = fcgui.sketch_in_edit()
    if panel_host.same_object(sketch, frame.sketch):
        delete_constraints(sketch, order)
    _refresh_later()


def delete_constraints(sketch, indices):
    """Remove the given constraints in one 'Delete Relations' undo step and re-solve.

    A pending transaction is joined rather than a new one opened, and the
    transaction is committed even if some deletions fail. Returns how many
    constraints were removed.
    """
    order = relations_rules.deletion_order(indices)
    if not order:
        return 0
    deleted = 0
    failures = []
    with doc_utils.transaction(sketch.Document, TRANSACTION_NAME, join_pending=True):
        for index in order:
            try:
                sketch.delConstraint(index)
                deleted += 1
            except Exception as exc:
                failures.append("no. %d (%s)" % (index + 1, exc))
    try:
        sketch.solve()
    except Exception:
        pass
    if failures:
        console.warning("some relations were not removed: %s" % ", ".join(failures))
    return deleted
