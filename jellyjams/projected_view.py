# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Projected View, where projections sit on the sheet, and keeping Standard 3 Views draggable.

A DrawProjGroup with AutoDistribute switched on re-spaces its projections on
every recompute, so a dragged projection snaps back. With it off, TechDraw
still keeps each projection on its alignment axis. JellyJams therefore turns
AutoDistribute off for new drawings, for already distributed groups in
existing drawings, and before Projected View adds a projection.

Positions are sheet millimetres, y up. A projection's X/Y is measured from
its group, where the Front view sits at (0, 0).

The sheet place of a projection is not stored in a table. It follows from the
direction TechDraw looks along for that projection type and from the
projection method: third angle puts a view on the side it looks from, first
angle on the opposite side, and TechDraw parks the Rear view beyond the
right-hand neighbour of the Front view in both methods.

This module also holds small document helpers shared by the other
drawing-view modules (view_labels, view_scale, sheet_drag).
"""

import contextlib
import math

import FreeCAD

from jellyjams import commands, console, constants, doc_utils, fcgui

FIRST_ANGLE = "First angle"
THIRD_ANGLE = "Third angle"
METHODS = (FIRST_ANGLE, THIRD_ANGLE)
FRONT = "Front"
REAR = "Rear"

PICK_OWNER = "projected_view"
UNDO_NAME = "Projected View"
STATUS_HINT = ("Projected View: click beside the view on the side where the new "
               "projection should go. Right-click or Esc to cancel.")

VIEW_GAP_MM = 15.0
FALLBACK_SIZE_MM = 100.0
_EPS = 1e-9

# The Direction TechDraw assigns to each DrawProjGroupItem type in an unrotated
# group: x points to the model's right, y away from someone looking at the Front
# view, z up.
VIEW_DIRECTIONS = {
    "Front": (0, -1, 0),
    "Rear": (0, 1, 0),
    "Left": (-1, 0, 0),
    "Right": (1, 0, 0),
    "Top": (0, 0, 1),
    "Bottom": (0, 0, -1),
    "FrontTopLeft": (-1, -1, 1),
    "FrontTopRight": (1, -1, 1),
    "FrontBottomLeft": (-1, -1, -1),
    "FrontBottomRight": (1, -1, -1),
}

# Sheet slot of the Rear view: two view steps right of the Front view, level with it.
REAR_SLOT = (2, 0)

# The eight sheet steps a click can mean, counter-clockwise from "right", 45 degrees apart.
_HEADINGS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
_HEADING_SECTOR = math.pi / 4.0


# --- pure placement rules ---------------------------------------------------------


def click_step(dx, dy):
    """The sheet step (sx, sy) a click offset in mm (y up) points along, or None.

    The offset's angle is snapped to the nearest of eight headings, so each
    straight and each diagonal step owns a 45 degree wedge. A zero offset has
    no heading.
    """
    dx, dy = float(dx), float(dy)
    if dx == 0.0 and dy == 0.0:
        return None
    wedge = int(round(math.atan2(dy, dx) / _HEADING_SECTOR)) % len(_HEADINGS)
    return _HEADINGS[wedge]


def _facing(method):
    """+1 when a view sits on the side it looks from (third angle), -1 for the
    opposite side (first angle), 0 for an unknown method."""
    if method == THIRD_ANGLE:
        return 1
    if method == FIRST_ANGLE:
        return -1
    return 0


def sheet_slot(proj_type, method):
    """Where `proj_type` sits around the Front view, in view steps (right, up), or None.

    The Front view is (0, 0); (1, 0) is the next view to its right, (0, 1) the
    next one above it.
    """
    direction = VIEW_DIRECTIONS.get(proj_type)
    facing = _facing(method)
    if direction is None or not facing:
        return None
    across, depth, height = direction
    if depth > 0:
        return REAR_SLOT
    return (facing * across, facing * height)


def projection_toward(ref_type, step, method):
    """The projection type one `step` away from `ref_type` on the sheet, or None.

    None means that no projection type belongs there, for example beyond the
    Rear view or past a corner view.
    """
    start = sheet_slot(ref_type, method)
    if start is None or not step:
        return None
    slot = (start[0] + step[0], start[1] + step[1])
    if slot == REAR_SLOT:
        return REAR
    facing = _facing(method)
    wanted = (facing * slot[0], facing * slot[1])
    for name, (across, depth, height) in VIEW_DIRECTIONS.items():
        if depth <= 0 and (across, height) == wanted:
            return name
    return None


# --- document helpers shared by the drawing-view modules ------------------------


def num(value, default=0.0):
    """A float from a number or a FreeCAD quantity; `default` when that fails."""
    try:
        return float(value)
    except Exception:
        return default


def xy(obj):
    """The X and Y of a drawing view, as floats."""
    return num(getattr(obj, "X", 0.0)), num(getattr(obj, "Y", 0.0))


def parents(obj):
    try:
        return list(obj.InList)
    except Exception:
        return []


def same_object(a, b):
    """True if `a` and `b` refer to the same document object."""
    if a is None or b is None:
        return False
    try:
        return a.Name == b.Name and a.Document.Name == b.Document.Name
    except Exception:
        return False


def page_of(obj):
    """The DrawPage that holds `obj` or its parent, or None."""
    direct = parents(obj)
    for parent in direct:
        if doc_utils.is_derived(parent, constants.TYPE_PAGE):
            return parent
    for parent in direct:
        for grand in parents(parent):
            if doc_utils.is_derived(grand, constants.TYPE_PAGE):
                return grand
    return None


def owning_group(obj):
    """The projection group `obj` is, or the one it is a member of; None otherwise."""
    if doc_utils.is_derived(obj, constants.TYPE_PROJ_GROUP):
        return obj
    for parent in parents(obj):
        if doc_utils.is_derived(parent, constants.TYPE_PROJ_GROUP):
            return parent
    return None


def projections(group):
    """The group's DrawProjGroupItem members, in group order."""
    views = getattr(group, "Views", None) or []
    return [v for v in views if doc_utils.is_derived(v, constants.TYPE_PROJ_ITEM)]


def projection_type(item):
    return str(getattr(item, "Type", "") or "")


def effective_method(group):
    """First or third angle: from the group, else from its page, else first angle."""
    method = str(getattr(group, "ProjectionType", "") or "")
    if method in METHODS:
        return method
    page = page_of(group)
    if page is None:
        try:
            page = group.findParentPage()
        except Exception:
            page = None
    method = str(getattr(page, "ProjectionType", "") or "") if page is not None else ""
    return method if method in METHODS else FIRST_ANGLE


def _active_transaction():
    """(name, id) of the application's open undo step, or None."""
    try:
        active = FreeCAD.getActiveTransaction()
    except Exception:
        return None
    if not active:
        return None
    try:
        return str(active[0]), int(active[1])
    except Exception:
        return None


def open_undo(doc, name):
    """Start the undo step `name` on `doc`. Returns its id for close_undo().

    The id is 0 when no new step was started, for example because a running
    command already owns one; that step is then left for its owner to close.
    """
    before = _active_transaction()
    doc.openTransaction(name)
    after = _active_transaction()
    return after[1] if after is not None and after != before else 0


def close_undo(doc, step_id, abort=False):
    """Commit (or roll back) a step started with open_undo().

    A document only closes a step in which it recorded a change. A step with no
    changes would otherwise stay open for the whole application and absorb the
    user's next edit, so it is closed here by its id.
    """
    try:
        if abort:
            doc.abortTransaction()
        else:
            doc.commitTransaction()
    finally:
        active = _active_transaction()
        if step_id and active is not None and active[1] == step_id:
            FreeCAD.closeActiveTransaction(bool(abort), step_id)


@contextlib.contextmanager
def undo_step(doc, name):
    """Run a block as one undo step `name`; the step is committed even if the block raises."""
    step_id = open_undo(doc, name)
    try:
        yield
    finally:
        close_undo(doc, step_id)


def _shape_box(obj):
    shape = getattr(obj, "Shape", None)
    try:
        if shape is None or shape.isNull():
            import Part
            shape = Part.getShape(obj)
        if shape is None or shape.isNull():
            return None
        box = shape.BoundBox
        return box if box.isValid() else None
    except Exception:
        return None


def source_bound_box(view):
    """Bounding box of the first source object with a shape (XSource before Source)."""
    for prop in ("XSource", "Source"):
        for obj in getattr(view, prop, None) or []:
            box = _shape_box(obj)
            if box is not None:
                return box
    return None


def default_steps(group):
    """Default (horizontal, vertical) spacing in mm between neighbouring projections."""
    box = source_bound_box(group)
    if box is None:
        lx = ly = lz = FALLBACK_SIZE_MM
    else:
        lx, ly, lz = box.XLength, box.YLength, box.ZLength
    scale = num(getattr(group, "Scale", 1.0), 1.0)
    return ((lx / 2.0 + ly / 2.0) * scale + VIEW_GAP_MM,
            (lz / 2.0 + ly / 2.0) * scale + VIEW_GAP_MM)


def placed_offset(slot, click_x, click_y):
    """Group-relative (X, Y) for a new projection in `slot`, clicked at (click_x, click_y).

    A view level with the Front view keeps Y = 0, a view straight above or below
    it keeps X = 0; every other coordinate comes from the click.
    """
    across, up = slot
    return (float(click_x) if across else 0.0, float(click_y) if up else 0.0)


def is_distributed(group):
    """True if the group has projections besides Front and none of them sits at (0, 0)."""
    others = [p for p in projections(group) if projection_type(p) != FRONT]
    if not others:
        return False
    return all(abs(x) > _EPS or abs(y) > _EPS for x, y in map(xy, others))


def needs_release(group):
    """True if release_auto_distribute() would change `group`."""
    return bool(getattr(group, "AutoDistribute", False)) and is_distributed(group)


def release_auto_distribute(group):
    """Turn AutoDistribute off on a group that is already spread out. True if changed."""
    if not needs_release(group):
        return False
    group.AutoDistribute = False
    return True


# --- interfaces for make_drawing and the ribbon ---------------------------------


def apply_start_layout(group):
    """Spread a new Standard 3 View along its axes and leave it draggable."""
    with console.guard("arrange the views of the new Standard 3 View", level="warning"):
        method = effective_method(group)
        h_step, v_step = default_steps(group)
        group.AutoDistribute = False
        for item in projections(group):
            slot = sheet_slot(projection_type(item), method)
            if slot is None or slot == (0, 0):
                continue
            item.X = slot[0] * h_step
            item.Y = slot[1] * v_step
        group.Document.recompute()


def _document_busy(doc):
    if getattr(doc, "Restoring", False) or getattr(doc, "Transacting", False):
        return True
    # While a TechDraw tool runs it keeps pointers to view geometry; editing views then can crash.
    return fcgui.task_dialog_open() or fcgui.techdraw_tool_running()


def make_groups_movable(doc):
    """Turn AutoDistribute off on each spread-out group of `doc`; returns how many changed."""
    if doc is None:
        return 0
    try:
        if _document_busy(doc):
            return 0
        objects = list(doc.Objects)
    except Exception:
        return 0
    count = 0
    for obj in objects:
        if not doc_utils.is_derived(obj, constants.TYPE_PROJ_GROUP):
            continue
        with console.guard("unlock the view group %s for dragging" % getattr(obj, "Label", "?"),
                           level="log"):
            if release_auto_distribute(obj):
                count += 1
    if count:
        console.message("%d Standard 3 View group%s can now be dragged; "
                        "their views stay aligned to each other"
                        % (count, "" if count == 1 else "s"))
    return count


# --- Projected View command ---------------------------------------------------------


def _reference_from_selection():
    """(group, reference view) from the first selected member of a projection group.

    The reference is None when the group itself is selected; it then stands
    for the Front view at (0, 0).
    """
    for obj in fcgui.selection():
        if doc_utils.is_derived(obj, constants.TYPE_PROJ_GROUP):
            return obj, None
        for parent in parents(obj):
            if doc_utils.is_derived(parent, constants.TYPE_PROJ_GROUP):
                return parent, obj
    return None


def _pick_running():
    try:
        from jellyjams import sheet_pick
        return bool(sheet_pick.is_active(PICK_OWNER))
    except Exception:
        return False


def _item_of_type(group, proj_type):
    for item in projections(group):
        if projection_type(item) == proj_type:
            return item
    return None


def create_projection(group, reference, x_mm, y_mm):
    """Add the projection that lies from `reference` toward the sheet point (x_mm, y_mm).

    Returns the new DrawProjGroupItem, or None if nothing was added.
    """
    method = effective_method(group)
    group_x, group_y = xy(group)
    click_x, click_y = x_mm - group_x, y_mm - group_y
    if reference is None or same_object(reference, group):
        ref_type, (ref_x, ref_y) = FRONT, (0.0, 0.0)
    else:
        ref_type, (ref_x, ref_y) = projection_type(reference), xy(reference)

    new_type = projection_toward(ref_type, click_step(click_x - ref_x, click_y - ref_y), method)
    if new_type is None:
        console.warning("Projected View: no projection exists on that side of the view")
        return None
    existing = _item_of_type(group, new_type)
    if existing is not None:
        console.message("Projected View: this Standard 3 View already has %s" % existing.Label)
        return None

    x, y = placed_offset(sheet_slot(new_type, method), click_x, click_y)
    doc = group.Document
    with undo_step(doc, UNDO_NAME):
        group.AutoDistribute = False
        item = group.addProjection(new_type)
        item.X = x
        item.Y = y
        item.Label = constants.PROJECTION_VIEW_LABELS.get(new_type, new_type)
        doc.recompute()
    return item


def _create_at(doc_name, group_name, reference_name, x_mm, y_mm):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        doc = None
    group = doc.getObject(group_name) if doc is not None else None
    reference = doc.getObject(reference_name) if group is not None and reference_name else None
    if group is None or (reference_name and reference is None):
        console.warning("Projected View: the view you selected was deleted in the meantime")
        return
    create_projection(group, reference, x_mm, y_mm)


class ProjectedViewCommand(commands.BaseCommand):
    command_id = constants.CMD_PROJECTED_VIEW
    menu_text = "Projected View"
    tooltip = ("Projects a further view from a view of a Standard 3 View. Pick the source "
               "view first, then click the sheet where the new view should appear; it lines "
               "up with its source according to the drawing's projection method.")

    def is_active(self):
        if fcgui.task_dialog_open() or _pick_running():
            return False
        return _reference_from_selection() is not None

    def run(self):
        window = fcgui.active_sheet_window()
        if window is None:
            console.warning("Projected View: no drawing sheet window is active")
            return
        reference = _reference_from_selection()
        if reference is None:
            console.warning("Projected View: the selection has no view of a Standard 3 View")
            return
        group, view = reference
        doc_name, group_name = group.Document.Name, group.Name
        view_name = view.Name if view is not None else ""

        def on_click(x_mm, y_mm):
            with console.guard("add the projected view"):
                _create_at(doc_name, group_name, view_name, x_mm, y_mm)
            return False

        with console.guard("start picking a spot for the projected view"):
            from jellyjams import sheet_pick
            if not sheet_pick.start(window, on_click, status=STATUS_HINT, owner=PICK_OWNER):
                console.warning("Projected View: no drawing sheet window is active")


def get_commands():
    return {constants.CMD_PROJECTED_VIEW: ProjectedViewCommand()}
