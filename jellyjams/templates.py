# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Sheet formats: the ISO TechDraw templates installed with FreeCAD, plus third-angle copies.

No template files are bundled. The catalog reads FreeCAD's ISO folder, and a third-angle
copy of a template is generated on demand in the JellyJams cache folder.
"""

import os
import re
import tempfile

import FreeCAD

from jellyjams import console, constants, params, paths

FIRST_ANGLE = "First angle"
THIRD_ANGLE = "Third angle"
FORMAT_A4_PORTRAIT = "A4 portrait"
FORMAT_A3_LANDSCAPE = "A3 landscape"
NEW_DRAWING_FILES = {
    FORMAT_A4_PORTRAIT: "A4_Portrait_ISO5457_advanced.svg",
    FORMAT_A3_LANDSCAPE: "A3_Landscape_ISO5457_advanced.svg",
}
CATALOG_FIRST = (
    NEW_DRAWING_FILES[FORMAT_A4_PORTRAIT],
    NEW_DRAWING_FILES[FORMAT_A3_LANDSCAPE],
)
DEFAULT_TEMPLATE = "Default_Template_A4_Landscape.svg"
ISO_FOLDER = "ISO"
CACHE_FOLDER = "templates"
VARIANT_SUFFIX = "_third_angle"
SVG_EXTENSION = ".svg"
VARIANT_TEXTS = {
    "ISO5457_advanced": "title block ISO 7200",
    "ISO5457_minimal": "small title block",
    "ISO5457_notitleblock": "no title block",
    "blank": "blank",
    "TD": "TechDraw",
}
FIRST_ANGLE_PREFIX = "first_angle_"
THIRD_ANGLE_PREFIX = "third_angle_"
SYMBOL_PARTS = ("trapezoid", "inner circle", "outer circle", "horizontal", "vertical")

_NAME_RE = re.compile(
    r"^(?P<size>[^_]+)_(?P<orientation>portrait|landscape)(?:_(?P<variant>.+))?$",
    re.IGNORECASE,
)


# --- folders, catalog, names ------------------------------------------------------------


def templates_dir():
    """<FreeCAD resource dir>/Mod/TechDraw/Templates."""
    return os.path.normpath(
        os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Templates")
    )


def _split_svg(file_name):
    """(stem, extension); only ".svg" in any letter case is treated as an extension."""
    stem, extension = os.path.splitext(file_name)
    if extension.lower() == SVG_EXTENSION:
        return stem, extension
    return file_name, ""


def display_name(file_name):
    """Sheet format name shown to the user, such as "A4 portrait – title block ISO 7200"."""
    stem = _split_svg(os.path.basename(str(file_name or "")))[0]
    match = _NAME_RE.match(stem)
    if match is None:
        return stem
    text = "%s %s" % (match.group("size"), match.group("orientation").lower())
    variant = match.group("variant")
    if variant:
        text += " – " + VARIANT_TEXTS.get(variant, variant.replace("_", " "))
    return text


def is_third_angle_variant(path):
    """True when the template's file stem ends with VARIANT_SUFFIX (any letter case)."""
    stem = _split_svg(os.path.basename(str(path or "")))[0]
    return stem.lower().endswith(VARIANT_SUFFIX)


def catalog():
    """[(display name, absolute path)] for FreeCAD's ISO templates, in drawing-sheet 6.1 order."""
    folder = os.path.join(templates_dir(), ISO_FOLDER)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    files = [
        name
        for name in names
        if name.lower().endswith(SVG_EXTENSION)
        and not is_third_angle_variant(name)
        and os.path.isfile(os.path.join(folder, name))
    ]
    first = [name for name in CATALOG_FIRST if name in files]
    rest = sorted(name for name in files if name not in first)
    return [(display_name(name), os.path.join(folder, name)) for name in first + rest]


def new_drawing_template(fmt):
    """Template to use for a new drawing of format `fmt` ("A4 portrait" or "A3 landscape").

    Candidates, first existing one wins: <Templates>/ISO/<file>, <Templates>/<file>, the
    TechDraw TemplateFile preference, <Templates>/Default_Template_A4_Landscape.svg.
    Returns None when none of them exists.
    """
    root = templates_dir()
    candidates = []
    wanted = str(fmt or "").strip().lower()
    for name, file_name in NEW_DRAWING_FILES.items():
        if name.lower() == wanted:
            candidates += [os.path.join(root, ISO_FOLDER, file_name), os.path.join(root, file_name)]
    preferred = params.get_string(constants.PARAM_TECHDRAW_FILES, "TemplateFile", "")
    if preferred:
        candidates.append(preferred)
    candidates.append(os.path.join(root, DEFAULT_TEMPLATE))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    return None


# --- projection method ---------------------------------------------------------------------


def _is_under(path, folder):
    try:
        path = os.path.normcase(os.path.abspath(path))
        folder = os.path.normcase(os.path.abspath(folder))
        return os.path.commonpath([path, folder]) == folder
    except ValueError:
        return False


def _variant_name(file_name):
    stem, extension = _split_svg(file_name)
    return stem + VARIANT_SUFFIX + (extension or SVG_EXTENSION)


def _base_of_variant(path):
    """First-angle original of a third-angle variant, looked up beside it, then in FreeCAD's
    folders."""
    folder, file_name = os.path.split(path)
    stem, extension = _split_svg(file_name)
    base_name = stem[: -len(VARIANT_SUFFIX)] + (extension or SVG_EXTENSION)
    root = templates_dir()
    for candidate in (
        os.path.join(folder, base_name),
        os.path.join(root, ISO_FOLDER, base_name),
        os.path.join(root, base_name),
    ):
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    return None


def resolve_for_method(path, method):
    """Template matching projection `method` for the template `path` (drawing-sheet 6.3).

    Third angle: a "<stem>_third_angle.svg" next to the original if present, otherwise a
    generated copy of a FreeCAD template, otherwise the original. First angle: the original
    of a third-angle variant, otherwise `path` itself.
    """
    if not path:
        return path
    if method == FIRST_ANGLE:
        if is_third_angle_variant(path):
            return _base_of_variant(path) or path
        return path
    if method != THIRD_ANGLE:
        return path
    base = path
    if is_third_angle_variant(path):
        base = _base_of_variant(path)
        if base is None:
            return path
    sibling = os.path.join(os.path.dirname(base), _variant_name(os.path.basename(base)))
    if os.path.isfile(sibling):
        return os.path.normpath(sibling)
    if _is_under(base, templates_dir()):
        derived = derive_third_angle(base)
        if derived:
            return derived
    return base


def derive_third_angle(base_path):
    """Generate the third-angle copy of `base_path` in <user data>/JellyJams/templates/.

    Returns the copy's path. Returns None if the template has no first-angle symbol, or,
    after a warning, if the file cannot be read or the copy cannot be written.
    """
    try:
        with open(base_path, "r", encoding="utf-8", newline="") as handle:
            original = handle.read()
    except (OSError, UnicodeError) as exc:
        console.warning(
            "reading the template %s failed (%s), so it stays first angle without a "
            "third-angle copy" % (base_path, exc)
        )
        return None
    derived = transform_symbol(original)
    if derived is None:
        return None
    try:
        folder = paths.user_cache_dir(CACHE_FOLDER)
        target = os.path.join(folder, _variant_name(os.path.basename(base_path)))
        if _file_text(target) != derived:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                                 dir=folder, prefix=".jellyjams_template_",
                                                 suffix=".tmp", delete=False) as handle:
                    temporary = handle.name
                    handle.write(derived)
                os.replace(temporary, target)
            finally:
                if temporary is not None and os.path.exists(temporary):
                    try:
                        os.remove(temporary)
                    except OSError:
                        pass
        return target
    except Exception as exc:
        console.warning(
            "saving the third-angle copy of %s failed (%s); the sheet keeps the first-angle "
            "template" % (os.path.basename(base_path), exc)
        )
        return None


def _file_text(path):
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeError):
        return None


# --- SVG symbol transformation (pure text) ------------------------------------------------

_TAG_RE = re.compile(
    r"<(?P<name>[A-Za-z_][\w:.-]*)"
    r"(?P<attrs>(?:\s+[^\s=/>]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*/?>"
)
_ATTR_RE = re.compile(r"(?P<name>[^\s=/>]+)\s*=\s*(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)')")
_PATH_TOKEN_RE = re.compile(
    r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
)
_PATH_SEPARATORS = " ,\t\r\n\f"
_PARAMETER_COUNTS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}
# Parameter positions that are x coordinates when a command is absolute.
_X_POSITIONS = {
    "M": (0,), "L": (0,), "T": (0,), "H": (0,), "V": (),
    "C": (0, 2, 4), "S": (0, 2), "Q": (0, 2), "A": (5,), "Z": (),
}


def _format_number(value):
    text = ("%.6f" % value).rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _start_tags(text):
    """Yield (match, {attribute: (value, (start, end))}) for each start tag in `text`."""
    for tag in _TAG_RE.finditer(text):
        offset = tag.start("attrs")
        attributes = {}
        for attribute in _ATTR_RE.finditer(tag.group("attrs")):
            group = "dq" if attribute.group("dq") is not None else "sq"
            start, end = attribute.span(group)
            span = (offset + start, offset + end)
            attributes[attribute.group("name")] = (attribute.group(group), span)
        yield tag, attributes


def _parse_path(data):
    """Segments [(command, [(number, (start, end)), ...])] of SVG path data.

    Implicit command repeats become separate segments. None for malformed path data.
    """
    tokens = []
    position = 0
    for match in _PATH_TOKEN_RE.finditer(data):
        if data[position:match.start()].strip(_PATH_SEPARATORS):
            return None
        tokens.append((match.group(), match.span()))
        position = match.end()
    if data[position:].strip(_PATH_SEPARATORS):
        return None
    segments = []
    command = None
    index = 0
    while index < len(tokens):
        token = tokens[index][0]
        if token.isalpha():
            command = token
            index += 1
            if command in "Zz":
                segments.append((command, []))
                continue
        elif command is None or command in "Zz":
            return None
        count = _PARAMETER_COUNTS[command.upper()]
        group = tokens[index:index + count]
        if len(group) < count or any(item[0].isalpha() for item in group):
            return None
        segments.append((command, [(float(item[0]), item[1]) for item in group]))
        index += count
        if command == "M":
            command = "L"
        elif command == "m":
            command = "l"
    return segments


def _is_absolute(segments, index):
    command = segments[index][0]
    # SVG rule: a lowercase "m" that opens a path still gives absolute coordinates.
    return command.isupper() or (index == 0 and command == "m")


def _path_x_range(segments):
    """Smallest and largest x over the segment end points; None for an empty path."""
    xs = []
    x = y = start_x = start_y = 0.0
    for index, (command, parameters) in enumerate(segments):
        values = [value for value, _span in parameters]
        relative = not _is_absolute(segments, index)
        kind = command.upper()
        if kind == "Z":
            x, y = start_x, start_y
            continue
        if kind == "H":
            x = values[0] + (x if relative else 0.0)
        elif kind == "V":
            y = values[0] + (y if relative else 0.0)
        else:
            x, y = values[-2] + (x if relative else 0.0), values[-1] + (y if relative else 0.0)
        if kind == "M":
            start_x, start_y = x, y
        xs.append(x)
    return (min(xs), max(xs)) if xs else None


def _shift_path_edits(segments, dx, offset):
    """Replacements adding `dx` to each absolute x value; spans are moved by `offset`."""
    edits = []
    for index, (command, parameters) in enumerate(segments):
        if not _is_absolute(segments, index):
            continue
        for position in _X_POSITIONS[command.upper()]:
            value, (start, end) = parameters[position]
            edits.append(((offset + start, offset + end), _format_number(value + dx)))
    return edits


def _symbol_elements(svg_text):
    """{part: (tag name, attributes)} for the five first-angle symbol parts; None if incomplete."""
    found = {}
    for tag, attributes in _start_tags(svg_text):
        element_id = attributes.get("id", ("", None))[0]
        if not element_id.startswith(FIRST_ANGLE_PREFIX):
            continue
        part = element_id[len(FIRST_ANGLE_PREFIX):]
        if part in SYMBOL_PARTS and part not in found:
            found[part] = (tag.group("name").split(":")[-1], attributes)
    if len(found) != len(SYMBOL_PARTS):
        return None
    if any("transform" in attributes for _name, attributes in found.values()):
        return None
    return found


def _number_attribute(attributes, name):
    try:
        return float(attributes[name][0])
    except (KeyError, ValueError):
        return None


def transform_symbol(svg_text):
    """SVG text of the template with its projection symbol turned into third angle.

    The circles and the vertical centre line swap sides with the trapezoid: they go to the
    left, the trapezoid goes to the right without being mirrored. The symbol occupies the
    same area as before and the horizontal centre line does not move. Every id starting
    with "first_angle_" is renamed to start with "third_angle_"; nothing else changes.
    Returns None if the five first_angle_ parts are absent or have an unexpected form.
    """
    if not svg_text:
        return None
    elements = _symbol_elements(svg_text)
    if elements is None:
        return None
    trapezoid_tag, trapezoid = elements["trapezoid"]
    vertical_tag, vertical = elements["vertical"]
    outer_tag, outer = elements["outer circle"]
    inner_tag, inner = elements["inner circle"]
    if (trapezoid_tag, vertical_tag, outer_tag, inner_tag) != ("path", "path", "circle", "circle"):
        return None
    trapezoid_path = _parse_path(trapezoid.get("d", ("", None))[0])
    vertical_path = _parse_path(vertical.get("d", ("", None))[0])
    centre = _number_attribute(outer, "cx")
    inner_centre = _number_attribute(inner, "cx")
    radius = max(_number_attribute(outer, "r") or 0.0, _number_attribute(inner, "r") or 0.0)
    if not trapezoid_path or not vertical_path or centre is None or inner_centre is None:
        return None
    x_range = _path_x_range(trapezoid_path)
    if x_range is None or radius <= 0:
        return None
    left = min(x_range[0], centre - radius)
    right = max(x_range[1], centre + radius)
    shift_end_view = (left + radius) - centre
    shift_side_view = (right - (x_range[1] - x_range[0])) - x_range[0]

    edits = _shift_path_edits(trapezoid_path, shift_side_view, trapezoid["d"][1][0])
    edits += _shift_path_edits(vertical_path, shift_end_view, vertical["d"][1][0])
    for circle, circle_centre in ((outer, centre), (inner, inner_centre)):
        edits.append((circle["cx"][1], _format_number(circle_centre + shift_end_view)))
    for _tag, attributes in _start_tags(svg_text):
        element_id, span = attributes.get("id", ("", None))
        if element_id.startswith(FIRST_ANGLE_PREFIX):
            edits.append((span, THIRD_ANGLE_PREFIX + element_id[len(FIRST_ANGLE_PREFIX):]))

    result = svg_text
    for (start, end), replacement in sorted(edits, key=lambda edit: edit[0][0], reverse=True):
        result = result[:start] + replacement + result[end:]
    return result
