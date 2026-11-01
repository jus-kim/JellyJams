# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Captions and tooltips for ribbon buttons.

Pure string handling, no FreeCAD and no Qt. Layout captions may contain
forced line breaks; FreeCAD's command texts may contain HTML, '&' mnemonics
and entities. These helpers reduce both to the one-line names and the
tooltips the ribbon displays.
"""

import html
import re

EM_DASH = "—"
SOFT_HYPHEN = "­"
MORE_VARIANTS_HINT = "Pick another tool from the arrow menu."

_LINE_BREAK = re.compile(r"\r\n|\n|\r")
_SOFT_HYPHEN_BREAK = re.compile(SOFT_HYPHEN + r"[ \t]*(?:\r\n|\n|\r)[ \t]*")
_WHITESPACE = re.compile(r"\s+")
_BLOCK_TAG = re.compile(r"<\s*(?:br|/?p|/?div|/?li|/?tr|/?h[1-6]|/?ul|/?ol|/?table)\b[^>]*>", re.I)
_ANY_TAG = re.compile(r"<[^>]*>")
_AMPERSAND = re.compile(r"&&|&(#[0-9]+;|#[xX][0-9a-fA-F]+;|[A-Za-z][A-Za-z0-9]*;)?")
_TRAILING_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)$")
_LITERAL_AMP = "\x00"


def one_line(label):
    """Join the lines of a caption.

    A line ending in "-" followed by a lowercase word is a split word and is
    glued back ("Center-\\nline" -> "Centerline"); before an uppercase word the
    hyphen stays ("Dash-\\nDot" -> "Dash-Dot"); other breaks become a space
    ("Center\\nRectangle" -> "Center Rectangle").
    """
    if not label:
        return ""
    parts = _LINE_BREAK.split(str(label))
    if len(parts) == 1:
        return parts[0]
    result = parts[0].rstrip(" \t")
    last = len(parts) - 1
    for position, part in enumerate(parts[1:], start=1):
        right = part.lstrip(" \t")
        if position < last:
            right = right.rstrip(" \t")
        if not right:
            continue
        if not result:
            result = right
        elif result.endswith("-") and right[0].islower():
            result = result[:-1] + right
        elif result.endswith("-"):
            result = result + right
        else:
            result = result + " " + right
    return result


def tooltip_name(label):
    """Caption as used inside a tooltip: one line, no soft hyphens, single spaces."""
    if not label:
        return ""
    text = _SOFT_HYPHEN_BREAK.sub("", str(label))
    text = one_line(text).replace(SOFT_HYPHEN, "")
    return _WHITESPACE.sub(" ", text).strip()


def _remove_tags(text):
    text = _BLOCK_TAG.sub(" ", text)
    return _ANY_TAG.sub("", text)


def _drop_accelerator(match):
    token = match.group(0)
    if token == "&&":
        return _LITERAL_AMP
    if match.group(1):
        return token
    return ""


def plain_text(text):
    """A FreeCAD menu text reduced to plain words.

    Tags go away, a lone '&' (Qt mnemonic) is dropped while '&&' stands for a
    real ampersand, entities like '&amp;' are decoded, runs of whitespace
    shrink to one space and a trailing '...' or '…' is cut.
    """
    if not text:
        return ""
    value = _remove_tags(str(text))
    value = _AMPERSAND.sub(_drop_accelerator, value)
    value = html.unescape(value).replace(_LITERAL_AMP, "&")
    value = _WHITESPACE.sub(" ", value).strip()
    return _TRAILING_ELLIPSIS.sub("", value).strip()


def description_text(text):
    """A FreeCAD tooltip as plain text, keeping its line structure.

    <br> and closing block tags turn into line breaks; other tags are removed,
    entities decoded and blank lines dropped.
    """
    if not text:
        return ""
    value = re.sub(r"<\s*br\s*/?\s*>", "\n", str(text), flags=re.I)
    value = re.sub(r"<\s*/\s*(?:p|div|li|tr|h[1-6])\s*>", "\n", value, flags=re.I)
    value = html.unescape(_ANY_TAG.sub("", value))
    lines = (_WHITESPACE.sub(" ", line).strip() for line in _LINE_BREAK.split(value))
    return "\n".join(line for line in lines if line)


def _comparable(text):
    value = _WHITESPACE.sub(" ", str(text or "")).strip().casefold()
    if value.endswith("."):
        value = value[:-1].rstrip()
    return value


def same_name(a, b):
    """True when two texts differ at most in case, spacing or one final period."""
    return _comparable(a) == _comparable(b)


def compose_tooltip(label, menu_text, tool_tip):
    """First line '<SW name> — (FreeCAD: <menu text>)', then FreeCAD's description.

    The FreeCAD part is left out when both names match; a description that
    only repeats a name is left out too. Returns None when FreeCAD gives no
    menu text.
    """
    freecad_name = plain_text(menu_text)
    if not freecad_name:
        return None
    sw_name = tooltip_name(label) or freecad_name
    if same_name(sw_name, freecad_name):
        first = sw_name
    else:
        first = "{} {} (FreeCAD: {})".format(sw_name, EM_DASH, freecad_name)
    description = description_text(tool_tip)
    if description and not same_name(description, sw_name) and not same_name(description, freecad_name):
        return first + "\n" + description
    return first


def raw_description(cmd_id, menu_text, tool_tip):
    """Best text FreeCAD has for a command: tooltip, else menu text, else the id."""
    return description_text(tool_tip) or plain_text(menu_text) or str(cmd_id or "")


def button_tooltip(label, cmd_id, menu_text, tool_tip, indexed=False, icon_only=False):
    """Tooltip for a plain button."""
    composed = compose_tooltip(label, menu_text, tool_tip)
    if composed:
        return composed
    if indexed or icon_only:
        name = tooltip_name(label)
        if name:
            return name
    return raw_description(cmd_id, menu_text, tool_tip)


def toggle_tooltip(label, cmd_id, menu_text, tool_tip):
    """Tooltip for the variant a toggle currently shows."""
    return compose_tooltip(label, menu_text, tool_tip) or raw_description(cmd_id, menu_text, tool_tip)


def flyout_tooltip(label, cmd_id, menu_text, tool_tip, title=None, label_shown=True):
    """Tooltip for a flyout, describing its current variant.

    label_shown is True when the button face prints the variant's own label
    (text is visible and the flyout has no fixed title). A title different
    from the label is put in front, and a hint about the arrow menu is added.
    """
    base = compose_tooltip(label, menu_text, tool_tip)
    if not base:
        if label_shown and not title:
            base = raw_description(cmd_id, menu_text, tool_tip)
        else:
            base = tooltip_name(label) or raw_description(cmd_id, menu_text, tool_tip)
    heading = tooltip_name(title)
    if heading and not same_name(heading, tooltip_name(label)):
        base = "{}: {}".format(heading, base)
    return base + "\n" + MORE_VARIANTS_HINT


def mnemonic_safe(text):
    """Double every '&' so Qt prints it instead of treating it as a shortcut marker."""
    return str(text or "").replace("&", "&&")
