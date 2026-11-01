# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_WeldSymbol: ISO 2553 weld symbols that are put on a sheet with two clicks.

A weld symbol is an ordinary TechDraw::DrawViewSymbol. Its SVG is drawn in sheet
millimetres around the kink, the point where the arrow line turns into the reference line,
and the object's X/Y is that kink. The arrowhead's sheet position lives in ArrowheadX and
ArrowheadY and does not move with the symbol. WeldSettings keeps every weld setting as JSON;
the size, length and tail texts are SVG editable texts as well.

The elementary symbols are described once, as small outlines measured in glyph heights
(GLYPHS). A single renderer draws any of them hanging below or standing above a line.

install_watcher() registers a document observer that redraws a weld symbol whenever it is
moved, so its arrow keeps ending on the stored point.
"""

import copy
import json
import math

import FreeCAD

from jellyjams import commands, console, constants, doc_utils, fcgui, surface_finish
from jellyjams.surface_finish import fmt, number, xml_text

SYMBOL_TYPE = constants.TYPE_SYMBOL
PROPERTY_GROUP = constants.PROP_GROUP
NAME_BASE = "WeldSymbol"
LABEL = "Weld Symbol"
UNDO_CREATE = "Weld Symbol"
UNDO_EDIT = "Edit Weld Symbol"
PICK_OWNER = "weld"
KINK_OFFSET = (14.0, 8.0)  # a new kink sits this far right of and above its arrow point, mm

TIP_PROMPT = ("Weld Symbol, step 1 of 2: click the joint the arrowhead should touch. "
              "Esc cancels the placement.")
PLACE_PROMPT = ("Weld Symbol, step 2 of 2: click where the reference line should start. "
                "Esc leaves the symbol where it is.")
NO_SHEET_HINT = "Weld Symbol: open a drawing sheet window to place the symbol by clicking."

# --- stored data ------------------------------------------------------------------------------
#
# WeldSettings holds one JSON object, and the same shape is used in memory:
#
#   {"format": 1,
#    "sides": [<arrow side>, <other side>],
#    "marks": {"peripheral": bool, "site": bool, "dashed_line": bool},
#    "note": "<tail text>"}
#
# Each side is {"symbol": weld type id, "dimension": text left of the glyph, "extent": text
# right of the glyph, "surface": contour id, "treatment": finishing letter}.

FORMAT_VERSION = 1
ARROW_SIDE, OTHER_SIDE = 0, 1
SIDE_INDICES = (ARROW_SIDE, OTHER_SIDE)
SIDE_FIELDS = ("symbol", "dimension", "extent", "surface", "treatment")
MARK_FIELDS = ("peripheral", "site", "dashed_line")
# The SVG's editable texts in document order: the four side texts of TEXT_SLOTS, then the
# tail note. FreeCAD's EditableTexts list follows the same order.
TEXT_SLOTS = ((ARROW_SIDE, "dimension"), (ARROW_SIDE, "extent"),
              (OTHER_SIDE, "dimension"), (OTHER_SIDE, "extent"))
EDITABLE_IDS = ("dim_arrow", "extent_arrow", "dim_other", "extent_other", "note")


def _empty_side():
    return {field: "" for field in SIDE_FIELDS}


DEFAULT_DATA = {
    "format": FORMAT_VERSION,
    "sides": [dict(_empty_side(), symbol="fillet", dimension="a5"), _empty_side()],
    "marks": {field: False for field in MARK_FIELDS},
    "note": "",
}

# Elementary symbols. Butt-joint preparations come first, from the flanged form to the
# curved grooves; then the backing run, the fillet, the lap-joint symbols and surfacing.
# The ids are stored in documents and must never change meaning.
WELD_TYPES = (
    ("", "None on this side"),
    ("butt_flanged", "Flanged butt (raised plate edges)"),
    ("butt_i", "I – square butt"),
    ("butt_v", "V – single-V butt"),
    ("butt_hv", "HV – single-bevel butt"),
    ("butt_y", "Y – single-V butt with root face"),
    ("butt_hy", "HY – single-bevel butt with root face"),
    ("butt_u", "U – single-U butt"),
    ("butt_j", "J – single-J butt"),
    ("backing_run", "Backing run (back weld)"),
    ("fillet", "Fillet"),
    ("lap_plug", "Plug / slot"),
    ("lap_spot", "Spot"),
    ("lap_seam", "Seam"),
    ("surfacing", "Surfacing"),
)
CONTOURS = (("", "None"), ("flat", "Flat (flush)"), ("convex", "Convex"),
            ("concave", "Concave"))
# Finishing method written beyond the contour mark. Only the three established letters
# for chipping, grinding and machining are offered; there is no catch-all letter.
TREATMENTS = (("", "Not specified"), ("C", "Chipping (C)"), ("G", "Grinding (G)"),
              ("M", "Machining (M)"))
# Quick picks for the dimension field: throat thickness a, leg length z, penetration
# depth s, spot or plug diameter d and seam width c. Any other text may be typed instead.
SIZE_PRESETS = ("a3", "a4", "a5", "a6", "a8", "z4", "z6", "z8",
                "s5", "s8", "d5", "d8", "c6")
_CHOICES = {"symbol": WELD_TYPES, "surface": CONTOURS, "treatment": TREATMENTS}

# --- sheet layout, in mm ----------------------------------------------------------------------

TEXT_HEIGHT = 3.5            # ISO 3098 nominal lettering size
GLYPH_HEIGHT = TEXT_HEIGHT   # an elementary symbol is as tall as the lettering
LINE_WIDTH = 0.25            # ISO 128 narrow line of line group 0.5
TEXT_ADVANCE = 0.55          # osifont character advance with headroom, per unit of font size
CAP_RATIO = 0.74             # osifont capital height, per unit of font size
DESCENT_RATIO = 0.25         # room kept below a baseline, per unit of font size
DASH_GAP = 1.0               # spacing of the identification line from the reference line
DASH_LEAD = 1.5              # the identification line starts this far right of the kink
DASH_UNITS = (12, 3)         # ISO 128 dashed line: dash and space, in line widths
REFERENCE_MIN = 16.0
KINK_CLEAR = 2.5             # bare reference line kept next to the kink
TEXT_GAP = 0.8               # size text | glyph | length text
TEXT_CLEARANCE = 0.7         # from a text to the line it belongs to
END_PAD = 2.0                # reference line left over after the outermost glyph or text
CONTOUR_CLEARANCE = 0.5
CONTOUR_OVERHANG = 0.3
CONTOUR_MIN_CHORD = 2.6
CONTOUR_SAG = 0.5
FINISH_RATIO = 0.8           # finishing letter size, per unit of TEXT_HEIGHT
FINISH_CLEARANCE = 0.6
TAIL_ARM = 3.2
TAIL_TEXT_GAP = 0.9
RING_RADIUS = 1.2            # all-around circle
FLAG_STAFF = 5.5
FLAG_LENGTH = 3.2
FLAG_DEPTH = 2.2
FLAG_CLEAR = 0.8             # space between the flag's point and the first glyph or text
ARROW_LENGTH = 2.8
ARROW_ANGLE = 30.0           # included angle of the arrowhead, degrees
MIN_LEADER = 0.6             # no arrow is drawn for a shorter kink-to-point distance
CANVAS_PAD = 1.5
ARC_SAMPLES = 12             # points per arc when measuring a glyph

# --- glyph proportions, in glyph heights ------------------------------------------------------

FLANK_RUN = 0.75             # sideways run of a groove flank per unit of rise
ROOT_FACE = 0.3              # root face stem of the Y, HY, U and J symbols
GROOVE_RADIUS = 0.4          # bottom radius of the U and J grooves
FLANGE_RADIUS = 0.5
SQUARE_HALF_GAP = 0.3
FILLET_RUN = 1.0             # equal legs
SPOT_RADIUS = 0.5
SEAM_RUN = 0.8               # half length of the seam lines
SEAM_SPLIT = 0.2             # seam lines sit this far either side of the circle's center
BEAD_RADIUS = 0.35
BACKING_RADIUS = 0.5
PLUG_HALF = 0.55
PLUG_RISE = 0.4

_WATCHED = frozenset(("X", "Y", constants.PROP_ARROWHEAD_X, constants.PROP_ARROWHEAD_Y, "EditableTexts"))


def _glyph_table():
    """Outlines of the elementary symbols.

    A glyph is a tuple of parts. A part is a circle ("O", cx, cy, r) or a stroke: a start
    point followed by line steps ("L", x, y) and arc steps ("A", cx, cy, r, from, to). x
    runs along the reference line from the glyph's anchor (the upright of a one-sided
    preparation, the middle of any other glyph) and y grows away from the line. Arc angles
    are in degrees, measured from +x toward +y.
    """
    root, groove = ROOT_FACE, GROOVE_RADIUS
    run = FLANK_RUN * (1.0 - root)
    lip = 1.0 - FLANGE_RADIUS
    bead = BEAD_RADIUS
    return {
        "butt_flanged": (
            ((0.0, 0.0), ("L", 0.0, lip)),
            ((0.0, lip), ("A", -FLANGE_RADIUS, lip, FLANGE_RADIUS, 0.0, 90.0)),
            ((0.0, lip), ("A", FLANGE_RADIUS, lip, FLANGE_RADIUS, 180.0, 90.0)),
        ),
        "butt_i": (
            ((-SQUARE_HALF_GAP, 0.0), ("L", -SQUARE_HALF_GAP, 1.0)),
            ((SQUARE_HALF_GAP, 0.0), ("L", SQUARE_HALF_GAP, 1.0)),
        ),
        "butt_v": (((-FLANK_RUN, 1.0), ("L", 0.0, 0.0), ("L", FLANK_RUN, 1.0)),),
        "butt_hv": (((0.0, 1.0), ("L", 0.0, 0.0), ("L", FLANK_RUN, 1.0)),),
        "butt_y": (
            ((0.0, 0.0), ("L", 0.0, root)),
            ((-run, 1.0), ("L", 0.0, root), ("L", run, 1.0)),
        ),
        "butt_hy": (
            ((0.0, 0.0), ("L", 0.0, 1.0)),
            ((0.0, root), ("L", run, 1.0)),
        ),
        "butt_u": (
            ((0.0, 0.0), ("L", 0.0, root)),
            ((-groove, 1.0), ("L", -groove, root + groove),
             ("A", 0.0, root + groove, groove, 180.0, 270.0),
             ("A", 0.0, root + groove, groove, 270.0, 360.0),
             ("L", groove, 1.0)),
        ),
        "butt_j": (
            ((0.0, 0.0), ("L", 0.0, 1.0)),
            ((0.0, root), ("A", 0.0, root + groove, groove, 270.0, 360.0), ("L", groove, 1.0)),
        ),
        "backing_run": (
            ((-BACKING_RADIUS, 0.0), ("A", 0.0, 0.0, BACKING_RADIUS, 180.0, 90.0),
             ("A", 0.0, 0.0, BACKING_RADIUS, 90.0, 0.0)),
        ),
        "fillet": (((0.0, 0.0), ("L", 0.0, 1.0), ("L", FILLET_RUN, 0.0)),),
        "lap_plug": (
            ((-PLUG_HALF, 0.0), ("L", -PLUG_HALF, PLUG_RISE), ("L", PLUG_HALF, PLUG_RISE),
             ("L", PLUG_HALF, 0.0)),
        ),
        "lap_spot": (("O", 0.0, SPOT_RADIUS, SPOT_RADIUS),),
        "lap_seam": (
            ("O", 0.0, SPOT_RADIUS, SPOT_RADIUS),
            ((-SEAM_RUN, SPOT_RADIUS - SEAM_SPLIT), ("L", SEAM_RUN, SPOT_RADIUS - SEAM_SPLIT)),
            ((-SEAM_RUN, SPOT_RADIUS + SEAM_SPLIT), ("L", SEAM_RUN, SPOT_RADIUS + SEAM_SPLIT)),
        ),
        "surfacing": (
            ((-2.0 * bead, 0.0), ("A", -bead, 0.0, bead, 180.0, 90.0),
             ("A", -bead, 0.0, bead, 90.0, 0.0), ("A", bead, 0.0, bead, 180.0, 90.0),
             ("A", bead, 0.0, bead, 90.0, 0.0)),
        ),
    }


GLYPHS = _glyph_table()


# --- data -------------------------------------------------------------------------------------


def _text_or(value, default):
    return value if isinstance(value, str) else default


def _bool_or(value, default):
    return value if isinstance(value, bool) else default


def has_weld(side):
    """True if this side carries a recognized weld type."""
    return bool(side.get("symbol"))


def _stored_object(raw_json):
    """The JSON object in `raw_json`, or {} for empty, malformed or non-object JSON."""
    if not isinstance(raw_json, str) or not raw_json.strip():
        return {}
    try:
        stored = json.loads(raw_json)
    except ValueError:
        return {}
    return stored if isinstance(stored, dict) else {}


def merge_data(raw_json, editable_texts):
    """Complete weld data from the stored JSON and the symbol's EditableTexts.

    Anything absent or of the wrong type keeps the value a new symbol starts with. Unknown
    keys and sides beyond the second are dropped, and a choice this version does not offer
    reads as "". EditableTexts then override by position (TEXT_SLOTS, then the note): a
    side's two texts count only while that side has a weld type, and when the list is
    short the remaining stored values stay as they are.
    """
    data = copy.deepcopy(DEFAULT_DATA)
    stored = _stored_object(raw_json)
    sides = stored.get("sides")
    if isinstance(sides, list):
        for index, values in zip(SIDE_INDICES, sides):
            if not isinstance(values, dict):
                continue
            side = data["sides"][index]
            for field in SIDE_FIELDS:
                if field in values:
                    side[field] = _text_or(values[field], side[field])
    marks = stored.get("marks")
    if isinstance(marks, dict):
        for field in MARK_FIELDS:
            if field in marks:
                data["marks"][field] = _bool_or(marks[field], data["marks"][field])
    if "note" in stored:
        data["note"] = _text_or(stored["note"], data["note"])
    for side in data["sides"]:
        for field, choices in _CHOICES.items():
            if side[field] not in [key for key, _label in choices]:
                side[field] = ""

    try:
        texts = list(editable_texts or [])
    except TypeError:
        texts = []
    for position, (index, field) in enumerate(TEXT_SLOTS):
        side = data["sides"][index]
        if position < len(texts) and has_weld(side):
            side[field] = _text_or(texts[position], side[field])
    if len(texts) > len(TEXT_SLOTS):
        data["note"] = _text_or(texts[len(TEXT_SLOTS)], data["note"])
    return data


def data_json(data):
    """`data` as WeldSettings JSON, keeping non-ASCII characters as they are."""
    return json.dumps(data, ensure_ascii=False, default=str)


# --- drawing ----------------------------------------------------------------------------------


def _arc_point(cx, cy, radius, degrees):
    angle = math.radians(degrees)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _arc_command(radius, large, sweep, x, y):
    """SVG elliptical-arc step with equal radii, ending at (x, y)."""
    return "A %s %s 0 %d %d %s %s" % (fmt(radius), fmt(radius), int(bool(large)),
                                      int(bool(sweep)), fmt(x), fmt(y))


def _outline_points(parts):
    """Points that bound a glyph outline in glyph heights, with arcs sampled."""
    points = []
    for part in parts:
        if part[0] == "O":
            _tag, cx, cy, radius = part
            points += [(cx - radius, cy - radius), (cx + radius, cy + radius)]
            continue
        points.append(part[0])
        for step in part[1:]:
            if step[0] == "L":
                points.append((step[1], step[2]))
                continue
            _tag, cx, cy, radius, start, stop = step
            for index in range(ARC_SAMPLES + 1):
                angle = start + (stop - start) * index / float(ARC_SAMPLES)
                points.append(_arc_point(cx, cy, radius, angle))
    return points


def glyph_extent(symbol):
    """(left, right, depth) of a glyph in mm.

    left and right are measured along the line from the glyph's anchor, depth away from
    the line. An unknown or empty weld type has no extent.
    """
    points = _outline_points(GLYPHS.get(symbol, ()))
    if not points:
        return 0.0, 0.0, 0.0
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    return min(xs) * GLYPH_HEIGHT, max(xs) * GLYPH_HEIGHT, max(ys) * GLYPH_HEIGHT


def _glyph_elements(symbol, anchor_x, line_y, sense):
    """SVG elements of one glyph whose anchor sits at `anchor_x` on the line at `line_y`.

    `sense` is +1 for a glyph hanging below its line and -1 for one standing above it.
    """
    scale = GLYPH_HEIGHT

    def place(x, y):
        return anchor_x + x * scale, line_y + sense * y * scale

    circles, steps = [], []
    for part in GLYPHS.get(symbol, ()):
        if part[0] == "O":
            _tag, cx, cy, radius = part
            x, y = place(cx, cy)
            circles.append('<circle cx="%s" cy="%s" r="%s"/>'
                           % (fmt(x), fmt(y), fmt(radius * scale)))
            continue
        x, y = place(*part[0])
        steps.append("M %s %s" % (fmt(x), fmt(y)))
        for step in part[1:]:
            if step[0] == "L":
                x, y = place(step[1], step[2])
                steps.append("L %s %s" % (fmt(x), fmt(y)))
                continue
            _tag, cx, cy, radius, start, stop = step
            x, y = place(*_arc_point(cx, cy, radius, stop))
            # Mirroring the glyph above the line reverses the turning direction.
            sweep = (stop > start) == (sense > 0)
            steps.append(_arc_command(radius * scale, abs(stop - start) > 180.0, sweep, x, y))
    elements = ['<path d="%s"/>' % " ".join(steps)] if steps else []
    return elements + circles


def _contour_chord(left, right):
    """Left and right end of a contour mark over a glyph spanning left..right (sheet x)."""
    left, right = left - CONTOUR_OVERHANG, right + CONTOUR_OVERHANG
    if right - left < CONTOUR_MIN_CHORD:
        middle = (left + right) / 2.0
        left, right = middle - CONTOUR_MIN_CHORD / 2.0, middle + CONTOUR_MIN_CHORD / 2.0
    return left, right


def _contour_elements(kind, chord, line_y, sense, depth):
    """(elements, reach) of a contour mark beyond a glyph that is `depth` mm deep.

    reach is how far the mark gets from the line. Seen from the line, a convex mark
    bulges away from the glyph and a concave one dips back toward it.
    """
    if kind not in ("flat", "convex", "concave"):
        return [], depth
    left, right = chord
    near = depth + CONTOUR_CLEARANCE
    if kind == "flat":
        y = line_y + sense * near
        return ['<path d="M %s %s L %s %s"/>' % (fmt(left), fmt(y), fmt(right), fmt(y))], near
    width = right - left
    radius = (width * width / 4.0 + CONTOUR_SAG * CONTOUR_SAG) / (2.0 * CONTOUR_SAG)
    convex = kind == "convex"
    y = line_y + sense * (near if convex else near + CONTOUR_SAG)
    sweep = convex != (sense > 0)
    element = '<path d="M %s %s %s"/>' % (fmt(left), fmt(y),
                                          _arc_command(radius, False, sweep, right, y))
    return [element], near + CONTOUR_SAG


def _rows(dashed):
    """{side index: (SVG y of the line it sits on, +1 hanging below or -1 standing above)}.

    The arrow side always hangs below the continuous reference line. When the dashed
    identification line is shown it runs above the reference line and carries the other
    side.
    """
    return {ARROW_SIDE: (0.0, 1.0), OTHER_SIDE: (-DASH_GAP if dashed else 0.0, -1.0)}


def _text_width(text, size=TEXT_HEIGHT):
    return len(text) * TEXT_ADVANCE * size


def _baseline(line_y, sense, offset, size=TEXT_HEIGHT):
    """Baseline of a text whose near edge is `offset` mm from its line, on the `sense` side."""
    if sense > 0:
        return line_y + offset + CAP_RATIO * size
    return line_y - offset


class _Bounds:
    """Running bounding box of what has been drawn, in SVG mm; it always holds the kink."""

    def __init__(self):
        self.left = self.top = self.right = self.bottom = 0.0

    def add(self, x, y):
        self.left, self.right = min(self.left, x), max(self.right, x)
        self.top, self.bottom = min(self.top, y), max(self.bottom, y)

    def add_text(self, x, baseline, anchor, text, size=TEXT_HEIGHT):
        if not text:
            return
        width = _text_width(text, size)
        start = {"start": x, "middle": x - width / 2.0}.get(anchor, x - width)
        self.add(start, baseline - CAP_RATIO * size)
        self.add(start + width, baseline + DESCENT_RATIO * size)


def _editable(name, x, y, anchor, value):
    return ('<text freecad:editable="%s" x="%s" y="%s" text-anchor="%s"><tspan>%s</tspan></text>'
            % (name, fmt(x), fmt(y), anchor, xml_text(value)))


def _layout(data, spans):
    """(column, reference_end): the sheet x of the glyph anchors and the line's far end."""
    lead = KINK_CLEAR
    if data["marks"]["site"]:
        lead = max(lead, FLAG_LENGTH + FLAG_CLEAR)
    column = lead
    for index, (left, _right, _depth) in spans.items():
        size_width = _text_width(data["sides"][index]["dimension"])
        before = size_width + TEXT_GAP if size_width else 0.0
        column = max(column, lead + before - left)

    reference_end = REFERENCE_MIN
    for index, (left, right, _depth) in spans.items():
        side = data["sides"][index]
        edges = [column + right]
        if side["surface"]:
            edges.append(_contour_chord(column + left, column + right)[1])
        if side["treatment"]:
            middle = column + (left + right) / 2.0
            edges.append(middle + _text_width(side["treatment"], TEXT_HEIGHT * FINISH_RATIO) / 2.0)
        length = _text_width(side["extent"])
        if length:
            edges.append(column + right + TEXT_GAP + length)
        reference_end = max(reference_end, max(edges) + END_PAD)
    return column, reference_end


def build_svg(data, tip_dx, tip_dy):
    """SVG text of the weld symbol described by `data`.

    (tip_dx, tip_dy) is where the arrow points, measured from the kink in sheet mm with y
    up. The kink is the SVG origin and the canvas is centered on it. The editable texts
    appear in EDITABLE_IDS order.
    """
    data = merge_data(data_json(data) if isinstance(data, dict) else "", None)
    sides, marks = data["sides"], data["marks"]
    spans = {index: glyph_extent(sides[index]["symbol"])
             for index in SIDE_INDICES if has_weld(sides[index])}
    rows = _rows(marks["dashed_line"])
    column, reference_end = _layout(data, spans)
    text_ids = dict(zip(TEXT_SLOTS, EDITABLE_IDS))

    bounds = _Bounds()
    strokes, solids, plain_texts, labels = [], [], [], {}

    strokes.append('<path d="M 0 0 H %s"/>' % fmt(reference_end))
    bounds.add(reference_end, 0.0)
    if marks["dashed_line"]:
        dash, space = (units * LINE_WIDTH for units in DASH_UNITS)
        strokes.append('<path d="M %s %s H %s" stroke-linecap="butt" stroke-dasharray="%s %s"/>'
                       % (fmt(DASH_LEAD), fmt(-DASH_GAP), fmt(reference_end), fmt(dash),
                          fmt(space)))
        bounds.add(DASH_LEAD, -DASH_GAP)

    for index in SIDE_INDICES:
        line_y, sense = rows[index]
        side = sides[index]
        dimension_id = text_ids[(index, "dimension")]
        extent_id = text_ids[(index, "extent")]
        baseline = _baseline(line_y, sense, TEXT_CLEARANCE)
        if index not in spans:
            labels[dimension_id] = (column - TEXT_GAP, baseline, "end", "")
            labels[extent_id] = (column + TEXT_GAP, baseline, "start", "")
            continue
        left, right, depth = spans[index]
        strokes += _glyph_elements(side["symbol"], column, line_y, sense)
        bounds.add(column + left, line_y + sense * depth)
        bounds.add(column + right, line_y)
        reach = depth
        if side["surface"]:
            chord = _contour_chord(column + left, column + right)
            contour, reach = _contour_elements(side["surface"], chord, line_y, sense, depth)
            strokes += contour
            bounds.add(chord[0], line_y + sense * reach)
            bounds.add(chord[1], line_y + sense * reach)
        if side["treatment"]:
            size = TEXT_HEIGHT * FINISH_RATIO
            x = column + (left + right) / 2.0
            y = _baseline(line_y, sense, reach + FINISH_CLEARANCE, size)
            plain_texts.append('<text x="%s" y="%s" text-anchor="middle" font-size="%s">%s</text>'
                               % (fmt(x), fmt(y), fmt(size), xml_text(side["treatment"])))
            bounds.add_text(x, y, "middle", side["treatment"], size)
        labels[dimension_id] = (column + left - TEXT_GAP, baseline, "end", side["dimension"])
        labels[extent_id] = (column + right + TEXT_GAP, baseline, "start", side["extent"])

    tail = data["note"]
    tail_x = reference_end + TAIL_TEXT_GAP
    if tail:
        spread = TAIL_ARM * math.sqrt(0.5)
        strokes.append('<path d="M %s %s L %s 0 L %s %s"/>'
                       % (fmt(reference_end + spread), fmt(-spread), fmt(reference_end),
                          fmt(reference_end + spread), fmt(spread)))
        bounds.add(reference_end + spread, -spread)
        bounds.add(reference_end + spread, spread)
        tail_x = reference_end + spread + TAIL_TEXT_GAP
    labels[EDITABLE_IDS[-1]] = (tail_x, CAP_RATIO * TEXT_HEIGHT / 2.0, "start", tail)

    if marks["peripheral"]:
        strokes.append('<circle cx="0" cy="0" r="%s"/>' % fmt(RING_RADIUS))
        bounds.add(-RING_RADIUS, -RING_RADIUS)
        bounds.add(RING_RADIUS, RING_RADIUS)
    if marks["site"]:
        top = -FLAG_STAFF
        strokes.append('<path d="M 0 0 V %s"/>' % fmt(top))
        solids.append('<path d="M 0 %s L %s %s L 0 %s Z"/>'
                      % (fmt(top), fmt(FLAG_LENGTH), fmt(top + FLAG_DEPTH / 2.0),
                         fmt(top + FLAG_DEPTH)))
        bounds.add(FLAG_LENGTH, top)

    tip_x, tip_y = float(tip_dx), -float(tip_dy)
    bounds.add(tip_x, tip_y)
    leader = math.hypot(tip_x, tip_y)
    if leader >= MIN_LEADER:
        along_x, along_y = tip_x / leader, tip_y / leader
        head = min(ARROW_LENGTH, leader)
        half = head * math.tan(math.radians(ARROW_ANGLE / 2.0))
        base_x, base_y = tip_x - along_x * head, tip_y - along_y * head
        if leader > head:
            strokes.append('<path d="M 0 0 L %s %s"/>' % (fmt(base_x), fmt(base_y)))
        solids.append('<path d="M %s %s L %s %s L %s %s Z"/>'
                      % (fmt(tip_x), fmt(tip_y), fmt(base_x - along_y * half),
                         fmt(base_y + along_x * half), fmt(base_x + along_y * half),
                         fmt(base_y - along_x * half)))

    texts = []
    for name in EDITABLE_IDS:
        x, y, anchor, value = labels[name]
        texts.append(_editable(name, x, y, anchor, value))
        bounds.add_text(x, y, anchor, value)
    texts += plain_texts

    half_width = max(-bounds.left, bounds.right) + CANVAS_PAD
    half_height = max(-bounds.top, bounds.bottom) + CANVAS_PAD
    width, height = 2.0 * half_width, 2.0 * half_height
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="%s" xmlns:freecad="%s" version="1.1" width="%smm" height="%smm" '
        'viewBox="%s %s %s %s">' % (surface_finish.SVG_NS, surface_finish.FREECAD_SVG_NS,
                                    fmt(width), fmt(height), fmt(-half_width),
                                    fmt(-half_height), fmt(width), fmt(height)),
        '  <g fill="none" stroke="#000000" stroke-width="%s" stroke-linecap="round" '
        'stroke-linejoin="round">' % fmt(LINE_WIDTH),
    ]
    out += ["    " + element for element in strokes]
    out.append("  </g>")
    if solids:
        out.append('  <g fill="#000000" stroke="none">')
        out += ["    " + element for element in solids]
        out.append("  </g>")
    out.append('  <g font-family="osifont" font-size="%s" fill="#000000" stroke="none">'
               % fmt(TEXT_HEIGHT))
    out += ["    " + element for element in texts]
    out += ["  </g>", "</svg>", ""]
    return "\n".join(out)


# --- document side ----------------------------------------------------------------------------

_pending = set()
_busy = set()
_watcher = None


def _key(obj):
    return obj.Document.Name, obj.Name


def _ensure_properties(obj):
    doc_utils.add_property(obj, "App::PropertyString", constants.PROP_SYMBOL_TYPE, PROPERTY_GROUP,
                           "Kind of JellyJams symbol")
    doc_utils.add_property(obj, "App::PropertyString", constants.PROP_WELD_SETTINGS, PROPERTY_GROUP,
                           "Weld settings of both sides, as JSON")
    doc_utils.add_property(obj, "App::PropertyFloat", constants.PROP_ARROWHEAD_X, PROPERTY_GROUP,
                           "Sheet X of the arrowhead point, mm")
    doc_utils.add_property(obj, "App::PropertyFloat", constants.PROP_ARROWHEAD_Y, PROPERTY_GROUP,
                           "Sheet Y of the arrowhead point, mm")


def stored_data(obj):
    """Weld data of `obj`: WeldSettings combined with its current EditableTexts."""
    try:
        texts = list(obj.EditableTexts)
    except Exception:
        texts = []
    return merge_data(getattr(obj, constants.PROP_WELD_SETTINGS, ""), texts)


def tip_offset(obj):
    """Offset from the kink to the arrow point, sheet mm with y up."""
    x, y = number(obj.X), number(obj.Y)
    tip_x = number(getattr(obj, constants.PROP_ARROWHEAD_X, None), x - KINK_OFFSET[0])
    tip_y = number(getattr(obj, constants.PROP_ARROWHEAD_Y, None), y - KINK_OFFSET[1])
    return tip_x - x, tip_y - y


def redraw(obj, data=None):
    """Rebuild the SVG of `obj` from `data` (or its stored data) and save that data.

    Properties are only written when they differ. Returns True if anything was written.
    """
    if data is None:
        data = stored_data(obj)
    svg = build_svg(data, *tip_offset(obj))
    text = data_json(data)
    key = _key(obj)
    changed = False
    _busy.add(key)
    try:
        _ensure_properties(obj)
        if not surface_finish.same_svg(obj.Symbol, svg):
            obj.Symbol = svg
            changed = True
        if getattr(obj, constants.PROP_WELD_SETTINGS) != text:
            setattr(obj, constants.PROP_WELD_SETTINGS, text)
            changed = True
    finally:
        _busy.discard(key)
    return changed


def _document_busy(doc):
    return bool(getattr(doc, "Restoring", False) or getattr(doc, "Transacting", False))


def _follow(key):
    """Redraw one weld symbol after it moved (runs on the next event-loop turn)."""
    _pending.discard(key)
    try:
        doc = FreeCAD.getDocument(key[0])
        obj = doc.getObject(key[1])
    except Exception:
        return
    if obj is None or key in _busy or _document_busy(doc):
        return
    if surface_finish.kind_of(obj) != constants.KIND_WELD:
        return
    if redraw(obj):
        with console.guard("refresh the weld symbol", level="silent"):
            obj.recompute()


class _ArrowFollower:
    """Watches weld symbols and queues a redraw when their position or arrow point changes."""

    def slotChangedObject(self, obj, prop):
        try:
            if prop not in _WATCHED:
                return
            if surface_finish.kind_of(obj) != constants.KIND_WELD:
                return
            doc = obj.Document
            if getattr(doc, "Restoring", False):
                return
            key = (doc.Name, obj.Name)
            if key in _busy or key in _pending:
                return
            _pending.add(key)
            fcgui.defer(lambda: _follow(key))
        except Exception:
            pass


def install_watcher():
    """Register the observer that keeps weld arrows on their points (once per session)."""
    global _watcher
    if _watcher is not None:
        return
    watcher = _ArrowFollower()
    FreeCAD.addDocumentObserver(watcher)
    _watcher = watcher


def create_symbol(doc, page):
    """Put a default weld symbol on `page`, its arrow ending at the sheet center."""
    tip_x, tip_y = surface_finish.sheet_center(page)
    obj = doc.addObject(SYMBOL_TYPE, NAME_BASE)
    obj.Label = LABEL
    _ensure_properties(obj)
    setattr(obj, constants.PROP_SYMBOL_TYPE, constants.KIND_WELD)
    setattr(obj, constants.PROP_ARROWHEAD_X, tip_x)
    setattr(obj, constants.PROP_ARROWHEAD_Y, tip_y)
    obj.ScaleType = "Custom"
    obj.Scale = 1.0
    data = copy.deepcopy(DEFAULT_DATA)
    setattr(obj, constants.PROP_WELD_SETTINGS, data_json(data))
    obj.Symbol = build_svg(data, -KINK_OFFSET[0], -KINK_OFFSET[1])
    page.addView(obj)
    obj.X, obj.Y = tip_x + KINK_OFFSET[0], tip_y + KINK_OFFSET[1]
    surface_finish.set_stack_order(obj)
    surface_finish.recompute(doc)
    return obj


# --- task panel -------------------------------------------------------------------------------


def _sheet_pick():
    from jellyjams import sheet_pick

    return sheet_pick


class _SideControls:
    """The rows that describe the weld on one side of the joint."""

    def __init__(self, title, parent, on_change):
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        self.box = QtWidgets.QGroupBox(title, parent)
        rows = QtWidgets.QFormLayout(self.box)
        self.symbol = self._choice_combo(WELD_TYPES)
        rows.addRow("Symbol", self.symbol)
        self.surface = self._choice_combo(CONTOURS)
        rows.addRow("Contour", self.surface)
        self.treatment = self._choice_combo(TREATMENTS)
        rows.addRow("Finish method", self.treatment)
        self.dimension = QtWidgets.QComboBox(self.box)
        self.dimension.setEditable(True)
        self.dimension.addItems(list(SIZE_PRESETS))
        self.dimension.setToolTip("Written left of the symbol. Start with a (throat), z (leg), "
                                  "s (penetration), d (diameter) or c (width); leave the field "
                                  "empty for no size.")
        rows.addRow("Size", self.dimension)
        self.extent = QtWidgets.QLineEdit(self.box)
        self.extent.setPlaceholderText("l, or n × l (e), e.g. 3 × 50 (150)")
        rows.addRow("Length", self.extent)
        for combo in (self.symbol, self.surface, self.treatment):
            combo.currentIndexChanged.connect(on_change)
        self.dimension.editTextChanged.connect(on_change)
        self.extent.textChanged.connect(on_change)

    def _choice_combo(self, choices):
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        combo = QtWidgets.QComboBox(self.box)
        for key, label in choices:
            combo.addItem(label, key)
        return combo

    @staticmethod
    def _select(combo, key):
        combo.setCurrentIndex(max(combo.findData(key), 0))

    def load(self, side):
        self._select(self.symbol, side["symbol"])
        self._select(self.surface, side["surface"])
        self._select(self.treatment, side["treatment"])
        self.dimension.setEditText(side["dimension"])
        self.extent.setText(side["extent"])

    def values(self):
        return {
            "symbol": self.symbol.currentData() or "",
            "dimension": self.dimension.currentText().strip(),
            "extent": self.extent.text().strip(),
            "surface": self.surface.currentData() or "",
            "treatment": self.treatment.currentData() or "",
        }


class WeldSymbolPanel:
    """Task panel for one weld symbol: edits show at once, placement is done on the sheet."""

    title = "Weld Symbol"

    def __init__(self, obj, undo):
        self.obj = obj
        self.doc = obj.Document
        self.undo = undo
        self._loading = True
        self._closed = False
        self._pick_step = 0
        self.form = self._build()
        self._load()
        self._loading = False

    def _build(self):
        _QtCore, _QtGui, QtWidgets = fcgui.qt()
        form = QtWidgets.QWidget()
        form.setObjectName(constants.OBJ_WELD_SYMBOL)
        form.setWindowTitle(self.title)
        layout = QtWidgets.QVBoxLayout(form)

        # One control group per side, in SIDE_INDICES order (arrow side first).
        self.side_controls = (
            _SideControls("Weld on the arrow side", form, self._changed),
            _SideControls("Weld on the other side", form, self._changed),
        )
        for controls in self.side_controls:
            layout.addWidget(controls.box)

        marks = QtWidgets.QGroupBox("Marks and tail", form)
        marks_layout = QtWidgets.QFormLayout(marks)
        self.mark_checks = {
            "peripheral": QtWidgets.QCheckBox("Weld all around (circle at the kink)", marks),
            "site": QtWidgets.QCheckBox("Field / site weld (flag)", marks),
            "dashed_line": QtWidgets.QCheckBox(
                "Identification line (dashed, carries the other side)", marks),
        }
        for field in MARK_FIELDS:
            check = self.mark_checks[field]
            marks_layout.addRow(check)
            check.toggled.connect(self._changed)
        self.note_edit = QtWidgets.QLineEdit(marks)
        self.note_edit.setPlaceholderText("process number or reference, e.g. 135 / ISO 5817-B")
        self.note_edit.textChanged.connect(self._changed)
        marks_layout.addRow("Tail", self.note_edit)
        layout.addWidget(marks)

        self.tip_button = QtWidgets.QPushButton("Re-pick arrow point and position …", form)
        self.tip_button.clicked.connect(self._restart_pick)
        layout.addWidget(self.tip_button)

        hint = QtWidgets.QLabel(
            "Dragging the symbol leaves its arrowhead on the picked point. Double-click the "
            "symbol on the sheet whenever you want this panel back.", form)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)
        return form

    def _load(self):
        data = stored_data(self.obj)
        for controls, side in zip(self.side_controls, data["sides"]):
            controls.load(side)
        for field in MARK_FIELDS:
            self.mark_checks[field].setChecked(data["marks"][field])
        self.note_edit.setText(data["note"])

    def collect(self):
        """What the panel currently shows, as weld data."""
        data = {
            "format": FORMAT_VERSION,
            "sides": [controls.values() for controls in self.side_controls],
            "marks": {field: self.mark_checks[field].isChecked() for field in MARK_FIELDS},
            "note": self.note_edit.text().strip(),
        }
        return merge_data(data_json(data), None)

    def _changed(self, *_args):
        if self._loading or self._closed:
            return
        self.apply()

    def apply(self):
        """Redraw the symbol from the panel and recompute; errors only go to the log."""
        try:
            if not doc_utils.is_alive(self.obj):
                return
            redraw(self.obj, self.collect())
            self.doc.recompute()
        except Exception as exc:
            console.log("weld symbol preview not updated: %s" % exc)

    # --- on-sheet placement

    def start_pick(self):
        """On the active sheet window, take a click for the arrow point, then one for the kink."""
        if self._closed:
            return False
        window = fcgui.active_sheet_window()
        if window is None:
            fcgui.status_message(NO_SHEET_HINT, 6000)
            return False
        try:
            sheet_pick = _sheet_pick()
            self._pick_step = 0
            return bool(sheet_pick.start(window, self._picked, self._pick_ended,
                                         status=TIP_PROMPT, owner=PICK_OWNER))
        except Exception as exc:
            console.log("weld symbol placement did not start: %s" % exc)
            return False

    def _restart_pick(self, *_args):
        self.start_pick()

    def _picked(self, x, y):
        try:
            obj = self.obj
            if self._closed or not doc_utils.is_alive(obj):
                return False
            if self._pick_step == 0:
                setattr(obj, constants.PROP_ARROWHEAD_X, float(x))
                setattr(obj, constants.PROP_ARROWHEAD_Y, float(y))
                obj.X, obj.Y = float(x) + KINK_OFFSET[0], float(y) + KINK_OFFSET[1]
                self.apply()
                self._pick_step = 1
                _sheet_pick().set_status(PLACE_PROMPT)
                return True
            obj.X, obj.Y = float(x), float(y)
            self.apply()
            return False
        except Exception as exc:
            console.log("weld symbol click not applied: %s" % exc)
            return False

    def _pick_ended(self, *_args):
        self._pick_step = 0

    def _end_pick(self):
        with console.guard("stop placing the weld symbol", level="log"):
            _sheet_pick().cancel(PICK_OWNER)

    # --- task dialog protocol

    def accept(self):
        if not self._closed:
            self._end_pick()
            self.apply()
            self._closed = True
            self.undo.close(abort=False)
        return True

    def reject(self):
        if not self._closed:
            self._end_pick()
            self._closed = True
            self.undo.close(abort=True)
            surface_finish.recompute(self.doc)
        return True


def open_editor(obj):
    """Show the panel for an existing weld symbol, without placement clicks. Returns False
    when it stays closed: a task dialog is already open, or `obj` is not a JellyJams weld."""
    try:
        if fcgui.task_dialog_open() or surface_finish.kind_of(obj) != constants.KIND_WELD:
            return False
        panel = surface_finish.open_in_undo_step(obj.Document, UNDO_EDIT, lambda: obj,
                                                 WeldSymbolPanel)
        return panel is not None
    except Exception as exc:
        console.error("weld symbol editor failed: %s" % exc, with_traceback=True)
        return False


def create_and_edit(doc, page):
    """Add a weld symbol, show its panel and begin placement, all in one undo step.

    The new symbol is rolled back if the panel cannot be shown. True if the panel is showing.
    """
    panel = surface_finish.open_in_undo_step(doc, UNDO_CREATE, lambda: create_symbol(doc, page),
                                             WeldSymbolPanel)
    if panel is None:
        return False
    if fcgui.active_sheet_window() is not None:
        panel.start_pick()
    return True


# --- command ----------------------------------------------------------------------------------


class WeldSymbolCommand(commands.BaseCommand):
    command_id = constants.CMD_WELD_SYMBOL
    menu_text = "Weld Symbol"
    tooltip = ("ISO 2553 weld symbol without a leader line. Pick the welded joint, then the "
               "spot for the reference line; double-click the symbol later to change it.")

    def run(self):
        doc = FreeCAD.ActiveDocument
        if doc is None or fcgui.task_dialog_open():
            return
        existing = surface_finish.selected_symbol(constants.KIND_WELD)
        if existing is not None:
            open_editor(existing)
            return
        page = surface_finish.target_sheet(doc)
        if page is None:
            return
        create_and_edit(doc, page)

    def is_active(self):
        return surface_finish.drawing_tools_enabled()


def get_commands():
    return {constants.CMD_WELD_SYMBOL: WeldSymbolCommand()}
