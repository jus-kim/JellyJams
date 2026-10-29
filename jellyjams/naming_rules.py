# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Tree-name tables and numbering rules, free of any FreeCAD import.

``labels`` arguments always hold the labels of the other objects in the
document; the caller leaves out the object that is being named.
"""

import re

TYPE_BASE_NAMES = {
    # part modeling
    "Sketcher::SketchObject": "Sketch",
    "PartDesign::Pad": "Boss-Extrude",
    "PartDesign::Pocket": "Cut-Extrude",
    "PartDesign::Revolution": "Revolve",
    "PartDesign::Groove": "Cut-Revolve",
    "PartDesign::AdditivePipe": "Sweep",
    "PartDesign::SubtractivePipe": "Cut-Sweep",
    "PartDesign::AdditiveLoft": "Loft",
    "PartDesign::SubtractiveLoft": "Cut-Loft",
    "PartDesign::Hole": "Hole",
    "PartDesign::Fillet": "Fillet",
    "PartDesign::Chamfer": "Chamfer",
    "PartDesign::Draft": "Draft",
    "PartDesign::Thickness": "Shell",
    "PartDesign::LinearPattern": "LPattern",
    "PartDesign::PolarPattern": "CirPattern",
    "PartDesign::Mirrored": "Mirror",
    "PartDesign::MultiTransform": "MultiPattern",
    "PartDesign::Plane": "Plane",
    "PartDesign::Line": "Axis",
    "PartDesign::Point": "Point",
    # assembly
    "Assembly::AssemblyObject": "Assembly",
    "Assembly::BomObject": "Bill of Materials",
    # drawing
    "TechDraw::DrawPage": "Sheet",
    "TechDraw::DrawSVGTemplate": "Sheet Format",
    "TechDraw::DrawViewPart": "Drawing View",
    "TechDraw::DrawViewDimension": "Dimension",
    "TechDraw::DrawViewBalloon": "Balloon",
    "TechDraw::DrawRichAnno": "Note",
    "TechDraw::DrawLeaderLine": "Leader",
    "TechDraw::DrawHatch": "Area Hatch",
    "TechDraw::DrawGeomHatch": "Area Hatch",
    "TechDraw::DrawWeldSymbol": "Weld Symbol",
    "TechDraw::DrawViewClip": "Crop Frame",
    "TechDraw::DrawViewImage": "Picture",
    "TechDraw::DrawViewSymbol": "Picture",
}

PLANE_NAMES = {"XY_Plane": "Top Plane", "XZ_Plane": "Front Plane", "YZ_Plane": "Right Plane"}

FOLDER_NAMES = {
    "Assembly::JointGroup": "Mates",
    "Assembly::ViewGroup": "Exploded Views",
    "Assembly::BomGroup": "Bills of Materials",
    "Assembly::SimulationGroup": "Motion Studies",
}

# Values of a joint's JointType property in FreeCAD 1.1.
JOINT_TYPES = (
    "Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel",
    "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt",
)

MATE_BASES = {
    "Fixed": "Lock",
    "Revolute": "Hinge",
    "Cylindrical": "Concentric",
    "Slider": "Slider",
    "Ball": "Ball Joint",
    "Parallel": "Parallel",
    "Perpendicular": "Perpendicular",
    "Angle": "Angle",
    "RackPinion": "Rack Pinion",
    "Screw": "Screw",
    "Gears": "Gear",
    "Belt": "Belt",
}
MATE_COINCIDENT = "Coincident"
MATE_DISTANCE = "Distance"
ZERO_DISTANCE = 1e-9

STANDARD_3_VIEW = "Standard 3 View"
SHEET_FORMAT = TYPE_BASE_NAMES["TechDraw::DrawSVGTemplate"]
FIXED_PREFIX = "(f) "

GENERIC_JOINT_LABEL = "Joint"
DISTANCE_DIALOG_TEXT = "Coincident / Distance"

# Values of a projection item's Type property in FreeCAD 1.1, in FreeCAD's own order.
# TechDraw labels each new item with its Type word, passed through Qt translation.
PROJECTION_TYPES = (
    "Front", "Left", "Right", "Rear", "Top", "Bottom",
    "FrontTopLeft", "FrontTopRight", "FrontBottomLeft", "FrontBottomRight",
)
# Object name of a projection item; it is also the label of one added by script.
PROJECTION_ITEM_NAME = "ProjItem"
# Source text of the label TechDraw gives a new sheet template.
TEMPLATE_NAME = "Template"

_DIGITS = "0123456789"
_INSTANCE_SUFFIX_RE = re.compile(r"<[0-9]+>\Z")


def _usable(words):
    """The non-empty strings among ``words`` (runtime translations may be odd)."""
    return [word for word in words if isinstance(word, str) and word]


def _without_counter(label):
    """``label`` minus a trailing counter: digits, optionally after blanks."""
    text = label or ""
    bare = text.rstrip(_DIGITS)
    return text if bare == text else bare.rstrip()


def _numbers(base, labels):
    """Yield N for every label spelled exactly ``base`` + digits N."""
    pattern = re.compile(re.escape(base) + r"([0-9]+)")
    for label in labels:
        match = pattern.fullmatch(label or "")
        if match:
            yield int(match.group(1))


def _fits_positive(label, base):
    """Whether ``label`` is ``base`` + a positive number with no leading zero."""
    return re.fullmatch(re.escape(base) + r"[1-9][0-9]*", label or "") is not None


def next_number(base, labels):
    return max(_numbers(base, labels), default=0) + 1


def numbered_name(base, labels):
    return "%s%d" % (base, next_number(base, labels))


def fixed_name(fixed, current, labels):
    taken = set(labels)
    if (current == fixed or _fits_positive(current, fixed)) and current not in taken:
        return current
    if fixed not in taken:
        return fixed
    return "%s%d" % (fixed, max(2, next_number(fixed, taken)))


def standard3_name(labels):
    labels = list(labels)
    number = next_number(STANDARD_3_VIEW, labels)
    if STANDARD_3_VIEW in labels:
        return "%s%d" % (STANDARD_3_VIEW, max(2, number))
    if number == 1:
        return STANDARD_3_VIEW
    return "%s%d" % (STANDARD_3_VIEW, number)


def instance_base(label):
    text = label or ""
    if text.startswith(FIXED_PREFIX):
        text = text[len(FIXED_PREFIX):]
    stripped = _INSTANCE_SUFFIX_RE.sub("", text)
    return stripped or text


def instance_name(base, labels):
    pattern = re.compile(r"(?:%s)?%s<([0-9]+)>" % (re.escape(FIXED_PREFIX), re.escape(base)))
    highest = 0
    for label in labels:
        match = pattern.fullmatch(label or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return "%s<%d>" % (base, highest + 1)


def fixed_marker(label, grounded):
    text = label or ""
    if grounded:
        return text if text.startswith(FIXED_PREFIX) else FIXED_PREFIX + text
    while text.startswith(FIXED_PREFIX):
        text = text[len(FIXED_PREFIX):]
    return text


def _distance_mm(distance):
    try:
        return float(getattr(distance, "Value", distance))
    except (TypeError, ValueError):
        return 0.0


def mate_base(joint_type, distance):
    if joint_type == MATE_DISTANCE:
        if abs(_distance_mm(distance)) < ZERO_DISTANCE:
            return MATE_COINCIDENT
        return MATE_DISTANCE
    return MATE_BASES.get(joint_type)


def _joint_word_labels(type_words):
    """``<word> Joint`` and ``<word>Joint`` for each joint type word."""
    for word in type_words:
        yield "%s %s" % (word, GENERIC_JOINT_LABEL)
        yield word + GENERIC_JOINT_LABEL


def default_mate_labels(extra=()):
    """Labels that count as automatic mate names.

    ``extra`` holds FreeCAD's joint type words in the running UI language; the
    caller reads them from FreeCAD's translations at runtime.
    """
    extra_words = _usable(extra)
    words = set(JOINT_TYPES)
    words.add(GENERIC_JOINT_LABEL)
    words.update(MATE_BASES.values())
    words.update((MATE_COINCIDENT, MATE_DISTANCE, DISTANCE_DIALOG_TEXT))
    words.update(extra_words)
    # A JointType change makes FreeCAD swap the first joint type word it finds in
    # the label, so "Ball Joint1" can come back as "Fixed Joint1".
    words.update(_joint_word_labels(JOINT_TYPES + tuple(extra_words)))
    words.update({word.replace(" ", "") for word in words})
    words.discard("")
    return words


def mate_label(current, base, labels, defaults):
    text = current or ""
    if _fits_positive(text, base):
        return text
    if text.rstrip(_DIGITS) in defaults:
        return numbered_name(base, labels)
    return text


def is_default_projection_label(label, extra=()):
    """Whether TechDraw could have produced ``label`` for a projection item.

    Recognized: a Type word or ``ProjItem``, bare or with a counter (``Left``,
    ``Rear002``, ``Top 4``). ``extra`` adds FreeCAD's translated Type words.
    """
    words = set(PROJECTION_TYPES)
    words.add(PROJECTION_ITEM_NAME)
    words.update(_usable(extra))
    return _without_counter(label) in words


def is_default_template_label(label, extra=()):
    """Whether ``label`` is ``Template`` (or FreeCAD's translation of it in
    ``extra``), bare or with a counter."""
    words = {TEMPLATE_NAME}
    words.update(_usable(extra))
    return _without_counter(label) in words
