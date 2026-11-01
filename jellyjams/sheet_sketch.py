# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Shapes on the drawing sheet (JellyJams_*OnSheet), drawn in the sheet sketch.

TechDraw cannot solve constraints, so each sheet gets a plain Sketcher sketch (the "sheet
sketch") that a TechDraw part view (the "sheet sketch view") shows on the sheet at 1:1.
During an edit the sketch also holds the "frame": four blocked construction lines tracing
the sheet outline, so that (x, y) measured from the frame's lower-left corner ends up at
(x, y) mm from the sheet's lower-left corner.

TechDraw puts the centre of a view's geometry at the view's X/Y, and the view can be
dragged, so the placement rule is

    offset = (view X, Y) - centre of the sketch geometry's bounding box

An edit starts with the frame moved to -offset and ends with the view moved to the new
bounding-box centre + offset; shapes already on the sheet therefore stay put. Undo and redo
outside an edit use the same rule, with the offset read back from the frame.
"""

import math

import FreeCAD
import FreeCADGui
from PySide import QtCore

from jellyjams import commands, console, constants, doc_utils, fcgui

SKETCH_STEP = "Sheet Sketch"
SKETCH_NAME = "SheetSketch"
VIEW_NAME = "SheetSketchView"
FALLBACK_SHEET_SIZE = (297.0, 210.0)
TOLERANCE = 1e-6
TOOL_START_MS = 150
REPLACE_DELAY_MS = 300
POLL_MS = 250
UNDO_RETRY_MS = 50
UNDO_RETRIES = 40

LINE_SEGMENT_TYPE = "Part::GeomLineSegment"
FRAME_TOOLTIP = "Index of the first of the four frame lines in the sketch geometry"


def _shape_tooltip(geometry):
    """Tooltip of one shape command: the geometry it makes, then where that geometry lives."""
    return (
        "%s, drawn 1:1 on the sheet. The sheet's own sketch holds the geometry, so "
        "relations and dimensions can constrain it." % geometry
    )


SHAPES = (
    (
        constants.CMD_SHEET_LINE,
        "Line",
        "Sketcher_CreatePolyline",
        _shape_tooltip("Connected straight line segments"),
    ),
    (
        constants.CMD_SHEET_RECTANGLE,
        "Rectangle",
        "Sketcher_CreateRectangle",
        _shape_tooltip("Rectangle from two opposite corners"),
    ),
    (
        constants.CMD_SHEET_CIRCLE,
        "Circle",
        "Sketcher_CreateCircle",
        _shape_tooltip("Circle from a centre and a radius"),
    ),
    (
        constants.CMD_SHEET_ARC,
        "Arc",
        "Sketcher_CreateArc",
        _shape_tooltip("Centerpoint arc (centre, start, end)"),
    ),
    (
        constants.CMD_SHEET_POLYGON,
        "Polygon",
        "Sketcher_CreateRegularPolygon",
        _shape_tooltip("Regular polygon around a centre"),
    ),
)

# (document name, sketch name) -> offset measured when that sheet sketch's edit began.
_sessions = {}
_watcher = None
_polled_key = None
_undo_watcher = None
# (document name, sketch name) -> geometry centre before an undo/redo touched the sketch.
_undo_pending = {}
_UNKNOWN = object()
_UNDO_PROPS = ("Geometry", "Shape")


# --- pure helpers ----------------------------------------------------------------------------


def frame_points(w, h, corner=(0.0, 0.0)):
    """Frame lines as (start, end) pairs, in the order bottom, right, top, left."""
    x, y = float(corner[0]), float(corner[1])
    w, h = float(w), float(h)
    return [
        ((x, y), (x + w, y)),
        ((x + w, y), (x + w, y + h)),
        ((x + w, y + h), (x, y + h)),
        ((x, y + h), (x, y)),
    ]


def _number(value):
    return float(getattr(value, "Value", value))


def _close(a, b):
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


# --- finding the objects -----------------------------------------------------------------------


def _same_object(a, b):
    try:
        return a is not None and b is not None and a.Name == b.Name and a.Document.Name == b.Document.Name
    except Exception:
        return False


def _is_sheet_sketch(obj):
    try:
        return obj.TypeId == constants.TYPE_SKETCH and constants.PROP_HOST_SHEET in obj.PropertiesList
    except Exception:
        return False


def _key(obj):
    return (obj.Document.Name, obj.Name)


def _lookup(key):
    """The sheet sketch with this key; None when the document or the sketch is gone."""
    doc = FreeCAD.listDocuments().get(key[0])
    if doc is None:
        return None
    obj = doc.getObject(key[1])
    return obj if _is_sheet_sketch(obj) else None


def find_sheet_sketch(page):
    """The object in the sheet's document whose HostSheet points at `page`, or None."""
    try:
        objects = list(page.Document.Objects)
    except Exception:
        return None
    for obj in objects:
        if _is_sheet_sketch(obj) and _same_object(getattr(obj, constants.PROP_HOST_SHEET, None), page):
            return obj
    return None


def _page_of_sketch(sketch):
    page = getattr(sketch, constants.PROP_HOST_SHEET, None)
    return page if doc_utils.is_derived(page, constants.TYPE_PAGE) else None


def _find_view(sketch):
    for obj in sketch.Document.Objects:
        try:
            if _same_object(getattr(obj, constants.PROP_SHOWN_SKETCH, None), sketch):
                return obj
        except Exception:
            continue
    return None


def _sheet_sketch_in_edit():
    sketch = fcgui.sketch_in_edit()
    return sketch if _is_sheet_sketch(sketch) else None


def _target_sheet():
    from jellyjams import drawing_common

    return drawing_common.target_sheet(FreeCAD.ActiveDocument)


def _sheet_size(page):
    size = None
    try:
        from jellyjams import drawing_common

        size = drawing_common.sheet_size(page)
    except Exception as exc:
        console.log("sheet size unavailable, using the fallback: %s" % exc)
    if size:
        width, height = float(size[0]), float(size[1])
        if width > 0 and height > 0 and math.isfinite(width) and math.isfinite(height):
            return width, height
    return FALLBACK_SHEET_SIZE


def _document_busy(doc):
    try:
        return bool(getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False))
    except Exception:
        return True


# --- geometry ----------------------------------------------------------------------------------


def _geometry_center(sketch):
    """Bounding-box centre of the sketch's real (non-construction) geometry; None if empty."""
    try:
        shape = sketch.Shape
        if shape.isNull():
            return None
        box = shape.BoundBox
        if not box.isValid():
            return None
    except Exception:
        return None
    return ((box.XMin + box.XMax) / 2.0, (box.YMin + box.YMax) / 2.0)


def _fresh_center(sketch):
    """_geometry_center() after bringing a touched sketch up to date."""
    if "Touched" in sketch.State:
        sketch.Document.recompute()
    return _geometry_center(sketch)


def _offset(sketch, view):
    if view is None:
        return (0.0, 0.0)
    center = _geometry_center(sketch)
    if center is None:
        return (0.0, 0.0)
    return (_number(view.X) - center[0], _number(view.Y) - center[1])


def _is_construction(sketch, index):
    try:
        return bool(sketch.getConstruction(index))
    except Exception:
        return bool(sketch.GeometryFacadeList[index].Construction)


def _frame_at(sketch, index, geometry):
    """((x, y), w, h) when the four construction lines from `index` on form a frame, else None."""
    if not isinstance(index, int) or index < 0 or index + 4 > len(geometry):
        return None
    segments = []
    for k in range(4):
        geo = geometry[index + k]
        if getattr(geo, "TypeId", "") != LINE_SEGMENT_TYPE or not _is_construction(sketch, index + k):
            return None
        segments.append(((geo.StartPoint.x, geo.StartPoint.y), (geo.EndPoint.x, geo.EndPoint.y)))
    corner = segments[0][0]
    width = segments[0][1][0] - corner[0]
    height = segments[1][1][1] - segments[1][0][1]
    if width <= TOLERANCE or height <= TOLERANCE:
        return None
    expected = frame_points(width, height, corner)
    for (start, end), (want_start, want_end) in zip(segments, expected):
        if not (_close(start, want_start) and _close(end, want_end)):
            return None
    return corner, width, height


def _find_frame(sketch):
    """(index, frame) of a verified frame, trying the recorded index before searching."""
    geometry = sketch.Geometry
    recorded = getattr(sketch, constants.PROP_BORDER_INDEX, -1)
    frame = _frame_at(sketch, recorded, geometry)
    if frame is not None:
        return recorded, frame
    for index in range(len(geometry) - 3):
        frame = _frame_at(sketch, index, geometry)
        if frame is not None:
            return index, frame
    return -1, None


def _add_frame(sketch, width, height, corner):
    import Part
    import Sketcher

    first = None
    for (x0, y0), (x1, y1) in frame_points(width, height, corner):
        line = Part.LineSegment(FreeCAD.Vector(x0, y0, 0), FreeCAD.Vector(x1, y1, 0))
        index = sketch.addGeometry(line, True)
        sketch.addConstraint(Sketcher.Constraint("Block", index))
        if first is None:
            first = index
    setattr(sketch, constants.PROP_BORDER_INDEX, first)


def _ensure_frame(sketch, width, height, corner):
    """Put the frame at `corner` with the sheet's size. Returns True if the sketch changed."""
    changed = doc_utils.add_property(
        sketch,
        "App::PropertyInteger",
        constants.PROP_BORDER_INDEX,
        tooltip=FRAME_TOOLTIP,
    )
    index, frame = _find_frame(sketch)
    if frame is not None:
        frame_corner, frame_width, frame_height = frame
        if (
            _close(frame_corner, corner)
            and abs(frame_width - width) <= TOLERANCE
            and abs(frame_height - height) <= TOLERANCE
        ):
            if getattr(sketch, constants.PROP_BORDER_INDEX) != index:
                setattr(sketch, constants.PROP_BORDER_INDEX, index)
                changed = True
            return changed
        # Deletes only the verified frame lines; their Block constraints disappear with them.
        sketch.delGeometries(list(range(index, index + 4)))
    _add_frame(sketch, width, height, corner)
    return True


# --- creating and repairing ---------------------------------------------------------------------


def _create_sketch(doc, page, width, height):
    sketch = doc.addObject(constants.TYPE_SKETCH, SKETCH_NAME)
    doc_utils.add_property(
        sketch,
        "App::PropertyLinkHidden",
        constants.PROP_HOST_SHEET,
        tooltip="Sheet that owns this sketch",
    )
    setattr(sketch, constants.PROP_HOST_SHEET, page)
    doc_utils.add_property(
        sketch,
        "App::PropertyInteger",
        constants.PROP_BORDER_INDEX,
        tooltip=FRAME_TOOLTIP,
    )
    sketch.MapMode = "Deactivated"
    sketch.Placement = FreeCAD.Placement()
    _add_frame(sketch, width, height, (0.0, 0.0))
    return sketch


def _create_view(doc, page, sketch, width, height):
    view = doc.addObject(constants.TYPE_VIEW_PART, VIEW_NAME)
    doc_utils.add_property(
        view,
        "App::PropertyLinkHidden",
        constants.PROP_SHOWN_SKETCH,
        tooltip="Sheet sketch displayed by this view",
    )
    setattr(view, constants.PROP_SHOWN_SKETCH, sketch)
    page.addView(view)
    view.Source = [sketch]
    view.Direction = FreeCAD.Vector(0, 0, 1)
    view.XDirection = FreeCAD.Vector(1, 0, 0)
    view.ScaleType = "Custom"
    view.Scale = 1.0
    center = _geometry_center(sketch)
    if center is None:
        view.X, view.Y = width / 2.0, height / 2.0
    else:
        # A replacement view goes where the frame says the existing shapes belong.
        _index, frame = _find_frame(sketch)
        corner = frame[0] if frame is not None else (0.0, 0.0)
        view.X, view.Y = center[0] - corner[0], center[1] - corner[1]
    view.LockPosition = False
    return view


def _prepare(page):
    """Find or create the sheet sketch and its view, then align the frame (one undo step).

    Returns (sketch, offset).
    """
    doc = page.Document
    width, height = _sheet_size(page)
    with doc_utils.transaction(doc, SKETCH_STEP, abort_on_error=True):
        changed = False
        sketch = find_sheet_sketch(page)
        if sketch is None:
            sketch = _create_sketch(doc, page, width, height)
            changed = True
        view = _find_view(sketch)
        if view is None:
            view = _create_view(doc, page, sketch, width, height)
            changed = True
        elif view.LockPosition:
            view.LockPosition = False
            changed = True
        offset = _offset(sketch, view)
        changed = _ensure_frame(sketch, width, height, (-offset[0], -offset[1])) or changed
        if changed:
            doc.recompute()
    return sketch, offset


# --- edit ------------------------------------------------------------------------------------


def _has_3d_view(doc):
    try:
        return bool(FreeCADGui.getDocument(doc.Name).mdiViewsOfType(constants.CLASS_VIEW3D))
    except Exception:
        area = fcgui.mdi_area()
        if area is None:
            return False
        return any(
            sub.widget() is not None and sub.widget().metaObject().className() == constants.CLASS_VIEW3D
            for sub in area.subWindowList()
        )


def _ensure_3d_view(doc):
    if not _has_3d_view(doc):
        fcgui.run_command("Std_ViewCreate")


def _set_edit(sketch):
    try:
        FreeCADGui.getDocument(sketch.Document.Name).setEdit(sketch.Name)
    except Exception as exc:
        console.log("edit mode for %s did not start: %s" % (sketch.Name, exc))
    return _same_object(fcgui.object_in_edit(), sketch)


def _fit_and_start(key, tool):
    sketch = _sheet_sketch_in_edit()
    if sketch is None or _key(sketch) != key:
        return
    FreeCADGui.SendMsgToActiveView("ViewFit")
    fcgui.run_command(tool)


def _start_shape(tool):
    if _sheet_sketch_in_edit() is not None:
        fcgui.run_command(tool)
        return
    page = _target_sheet()
    if page is None:
        return
    install_watcher()
    sketch, offset = _prepare(page)
    _ensure_3d_view(page.Document)
    key = _key(sketch)
    _sessions[key] = offset
    if not _set_edit(sketch):
        _sessions.pop(key, None)
        console.warning("the sheet sketch did not enter edit mode")
        return
    fcgui.defer(lambda: _fit_and_start(key, tool), TOOL_START_MS)


# --- end-of-edit watcher ------------------------------------------------------------------------


def _align_in_edit(key, offset):
    """Align the frame for an edit started outside JellyJams (a tree double-click, say)."""
    sketch = _lookup(key)
    page = _page_of_sketch(sketch) if sketch is not None else None
    if page is None:
        return
    width, height = _sheet_size(page)
    with doc_utils.transaction(sketch.Document, SKETCH_STEP, join_pending=True, abort_on_error=True):
        view = _find_view(sketch)
        if view is not None and view.LockPosition:
            view.LockPosition = False
        _ensure_frame(sketch, width, height, (-offset[0], -offset[1]))


def _move_view(view, center, offset):
    """Set the view to `center` + `offset`, recomputing only when it actually moves."""
    x, y = center[0] + offset[0], center[1] + offset[1]
    if abs(_number(view.X) - x) > TOLERANCE or abs(_number(view.Y) - y) > TOLERANCE:
        view.X, view.Y = x, y
        view.Document.recompute()


def _after_edit(key, offset):
    sketch = _lookup(key)
    page = _page_of_sketch(sketch) if sketch is not None else None
    if page is None:
        return
    view = _find_view(sketch)
    if view is not None and offset is not None:
        with console.guard("move the sheet sketch view after the edit", level="log"):
            center = _fresh_center(sketch)
            if center is not None:
                _move_view(view, center, offset)
    from jellyjams import drawing_common

    drawing_common.open_sheet_window(page)


def _edit_started(obj):
    if not _is_sheet_sketch(obj):
        return
    key = _key(obj)
    if key in _sessions:
        return
    offset = _offset(obj, _find_view(obj))
    _sessions[key] = offset
    fcgui.defer(lambda: _align_in_edit(key, offset))


def _edit_ended(key):
    offset = _sessions.pop(key, None)
    fcgui.defer(lambda: _after_edit(key, offset), REPLACE_DELAY_MS)


class _EditObserver:
    """FreeCADGui document observer: reports every edit start and end, whoever caused it."""

    @console.guarded("react to a sheet sketch entering edit mode", level="log")
    def slotInEdit(self, view_provider):
        _edit_started(getattr(view_provider, "Object", None))

    @console.guarded("react to a sheet sketch leaving edit mode", level="log")
    def slotResetEdit(self, view_provider):
        obj = getattr(view_provider, "Object", None)
        if _is_sheet_sketch(obj):
            _edit_ended(_key(obj))


@console.guarded("poll for sheet sketch edits", level="log")
def _poll():
    """Edit tracking by polling, for a FreeCADGui without document observers."""
    global _polled_key
    current = fcgui.object_in_edit()
    key = _key(current) if _is_sheet_sketch(current) else None
    if key == _polled_key:
        return
    if _polled_key is not None:
        _edit_ended(_polled_key)
    _polled_key = key
    if key is not None:
        _edit_started(current)


# --- undo / redo outside an edit -------------------------------------------------------------------


def _changed_by_undo(obj, prop):
    """True for a Geometry/Shape change of a sheet sketch while its document undoes or redoes."""
    if prop not in _UNDO_PROPS or not _is_sheet_sketch(obj):
        return False
    try:
        return bool(getattr(obj.Document, "Transacting", False))
    except Exception:
        return False


def _queue_after_undo(obj, measure):
    """Schedule _after_undo() once per burst; `measure` records the centre before the change."""
    key = _key(obj)
    if key in _undo_pending:
        return
    _undo_pending[key] = _geometry_center(obj) if measure else _UNKNOWN
    fcgui.defer(lambda: _after_undo(key, 0))


def _after_undo(key, attempt):
    """Re-place the sheet sketch view once an undo/redo that changed the sketch has finished.

    The view goes to the geometry centre minus the frame corner, which is the end-of-edit
    rule with the offset taken from the frame. Nothing moves when the real geometry kept
    its centre (only the frame changed), when the sketch is empty or in edit, or when the
    frame cannot be found.
    """
    sketch = _lookup(key)
    if sketch is None:
        _undo_pending.pop(key, None)
        return
    if _document_busy(sketch.Document) or fcgui.techdraw_tool_running(on_error=False):
        if attempt < UNDO_RETRIES:
            fcgui.defer(lambda: _after_undo(key, attempt + 1), UNDO_RETRY_MS)
        else:
            _undo_pending.pop(key, None)
        return
    center_before = _undo_pending.pop(key, _UNKNOWN)
    if key in _sessions or _same_object(fcgui.object_in_edit(), sketch):
        return
    view = _find_view(sketch)
    if view is None:
        return
    _index, frame = _find_frame(sketch)
    if frame is None:
        return
    center = _fresh_center(sketch)
    if center is None:
        return
    if center_before is not _UNKNOWN and center_before is not None and _close(center_before, center):
        return
    corner = frame[0]
    _move_view(view, center, (-corner[0], -corner[1]))


class _UndoObserver:
    """FreeCAD document observer: notices undo/redo changing a sheet sketch's geometry."""

    @console.guarded("note a sheet sketch change from undo/redo", level="log")
    def slotBeforeChangeObject(self, obj, prop):
        if _changed_by_undo(obj, prop):
            _queue_after_undo(obj, measure=True)

    @console.guarded("follow a sheet sketch change from undo/redo", level="log")
    def slotChangedObject(self, obj, prop):
        if _changed_by_undo(obj, prop):
            _queue_after_undo(obj, measure=False)


# --- installation ------------------------------------------------------------------------------


def _install_edit_watcher():
    global _watcher
    if _watcher is not None:
        return
    add_observer = getattr(FreeCADGui, "addDocumentObserver", None)
    if add_observer is not None:
        try:
            observer = _EditObserver()
            add_observer(observer)
            _watcher = observer
            return
        except Exception as exc:
            console.log("sheet sketch edits are tracked by polling: %s" % exc)
    timer = QtCore.QTimer()
    timer.setInterval(POLL_MS)
    timer.timeout.connect(_poll)
    timer.start()
    _watcher = timer


def _install_undo_watcher():
    global _undo_watcher
    if _undo_watcher is not None:
        return
    try:
        observer = _UndoObserver()
        FreeCAD.addDocumentObserver(observer)
        _undo_watcher = observer
    except Exception as exc:
        console.log("undo/redo in sheet sketches is not tracked: %s" % exc)


def install_watcher():
    """Track sheet sketch edits and undo/redo for the rest of the session (idempotent)."""
    _install_edit_watcher()
    _install_undo_watcher()


# --- commands ----------------------------------------------------------------------------------


class ShapeOnSheetCommand(commands.BaseCommand):
    """Opens the target sheet's sheet sketch and starts one Sketcher tool in it."""

    tool = ""

    def __init__(self, command_id, menu_text, tool, tooltip):
        self.command_id = command_id
        self.menu_text = menu_text
        self.tool = tool
        self.tooltip = tooltip

    def is_active(self):
        # Editing the sheet sketch counts as an open task dialog, yet switching to another
        # shape tool inside that edit has to stay possible.
        if _sheet_sketch_in_edit() is not None:
            return True
        from jellyjams import drawing_common

        return drawing_common.drawing_tools_enabled()

    def run(self):
        _start_shape(self.tool)


def get_commands():
    """Command table of this module: the five JellyJams_*OnSheet commands."""
    return {
        command_id: ShapeOnSheetCommand(command_id, menu_text, tool, tooltip)
        for command_id, menu_text, tool, tooltip in SHAPES
    }
