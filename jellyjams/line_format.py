# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_LineFormat: run FreeCAD's TechDraw_DecorateLine on the selected view edges.

Only TechDraw_DecorateLine is used, because it records the ISO 128 line
number with the style; formatGeometricEdge() does not, so it is avoided.
The relabelling and ISO 128 weight presets inside that dialog are handled
by dialog_terms, not here.
"""

from jellyjams import commands, console, constants, doc_utils, fcgui

DECORATE_COMMAND = "TechDraw_DecorateLine"
HINT = "Line Format: pick one or more edges of a drawing view, then run it again."
HINT_MS = 6000


def _is_drawing_view(obj):
    """True for TechDraw::DrawViewPart and its subtypes."""
    return doc_utils.is_derived(obj, constants.TYPE_VIEW_PART)


def has_view_edge(selection_ex):
    """True if at least one selected sub-element is an edge of a drawing view."""
    for item in selection_ex or []:
        try:
            if not _is_drawing_view(item.Object):
                continue
            if any(str(name).startswith("Edge") for name in item.SubElementNames):
                return True
        except Exception:
            continue
    return False


class LineFormatCommand(commands.BaseCommand):
    command_id = constants.CMD_LINE_FORMAT
    menu_text = "Line Format"
    tooltip = ("Sets line style, thickness and color for the edges you selected "
               "in a drawing view.")

    def run(self):
        if has_view_edge(fcgui.selection_ex()):
            fcgui.run_command(DECORATE_COMMAND)
            return
        fcgui.status_message(HINT, HINT_MS)
        console.message(HINT)

    def is_active(self):
        from jellyjams import drawing_common

        return drawing_common.drawing_tools_enabled()


def get_commands():
    return {constants.CMD_LINE_FORMAT: LineFormatCommand()}
