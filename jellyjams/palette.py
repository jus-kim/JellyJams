# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams colors and the WCAG 2.x contrast math that checks them.

The widget theme, the 3D view, the sketch colors and JellyJams' own pop-ups
all take their colors from this module and nowhere else. Plain Python only:
no FreeCAD or Qt imports.
"""

from types import SimpleNamespace

# --- widget palette ---------------------------------------------------------

WINDOW = "#f2f4f6"
PANEL = "#ffffff"
RIBBON_SURFACE = "#fbfcfd"
TAB_STRIP = "#f2f4f6"
BORDER = "#c9ced6"
TEXT = "#1f2328"
TEXT_SECONDARY = "#5a6572"
TEXT_DISABLED = "#9aa4af"
ACCENT = "#1a76c4"
ACCENT_DARK = "#115a99"
HOVER = "#e8f2fb"
PRESSED = "#cfe6f8"
SELECTION = "#cfe6f8"
TREE_TEXT = "#1f2328"

# --- 3D view and sketch palette ------------------------------------------------

GRADIENT_TOP = "#fdfdfd"
GRADIENT_BOTTOM = "#dfe6ec"
# SolidWorks convention: blue under defined, black fully defined, red over defined.
SKETCH_UNDER_DEFINED = "#1a76c4"
SKETCH_FULLY_DEFINED = "#000000"
SKETCH_OVER_DEFINED = "#ff0000"
SKETCH_CONSTRUCTION = "#5c6bd1"
SKETCH_CONSTRUCTION_DEFINED = "#454a52"
DIM_DRIVING = "#000000"
DIM_DRIVEN = "#6b7178"
RELATION_SYMBOLS = "#2a8048"
MEASURE_BACKGROUND = "#ffffff"
MEASURE_FOREGROUND = "#000000"

WIDGET_PALETTE = {
    "window": WINDOW,
    "panel": PANEL,
    "ribbon_surface": RIBBON_SURFACE,
    "tab_strip": TAB_STRIP,
    "border": BORDER,
    "text": TEXT,
    "text_secondary": TEXT_SECONDARY,
    "text_disabled": TEXT_DISABLED,
    "accent": ACCENT,
    "accent_dark": ACCENT_DARK,
    "hover": HOVER,
    "pressed": PRESSED,
    "selection": SELECTION,
    "tree_text": TREE_TEXT,
}

# Dark widget colors follow FreeCAD's dark surfaces while retaining the blue accent.
# Viewport/sketch colors have their own matching light/dark palettes.
DARK_WIDGET_PALETTE = {
    "window": "#191919",
    "panel": "#202020",
    "ribbon_surface": "#242424",
    "tab_strip": "#191919",
    "border": "#505050",
    "text": "#f0f0f0",
    "text_secondary": "#c0c6ce",
    "text_disabled": "#858585",
    "accent": "#66b8ff",
    "accent_dark": "#66b8ff",
    "hover": "#303f4d",
    "pressed": "#354d63",
    "selection": "#354d63",
    "tree_text": "#f0f0f0",
}


def widget_colors(dark=False):
    """A widget-only palette with the same uppercase role names as this module."""
    colors = DARK_WIDGET_PALETTE if dark else WIDGET_PALETTE
    return SimpleNamespace(**{name.upper(): value for name, value in colors.items()})

VIEWPORT_PALETTE = {
    "gradient_top": GRADIENT_TOP,
    "gradient_bottom": GRADIENT_BOTTOM,
    "under_defined": SKETCH_UNDER_DEFINED,
    "fully_defined": SKETCH_FULLY_DEFINED,
    "over_defined": SKETCH_OVER_DEFINED,
    "construction": SKETCH_CONSTRUCTION,
    "construction_defined": SKETCH_CONSTRUCTION_DEFINED,
    "driving_dimension": DIM_DRIVING,
    "driven_dimension": DIM_DRIVEN,
    "relation_symbols": RELATION_SYMBOLS,
}

DARK_VIEWPORT_PALETTE = {
    "gradient_top": "#20252b",
    "gradient_bottom": "#14181d",
    "under_defined": "#66b8ff",
    "fully_defined": "#8cff5b",
    "over_defined": "#ff7a7a",
    "construction": "#a6b4ff",
    "construction_defined": "#aeb6c2",
    "driving_dimension": "#f0f0f0",
    "driven_dimension": "#b9c3cf",
    "relation_symbols": "#7bdb9b",
}


def viewport_colors(dark=False):
    """Matching background and sketch drawing colors, including dimension text."""
    colors = DARK_VIEWPORT_PALETTE if dark else VIEWPORT_PALETTE
    return SimpleNamespace(**{name.upper(): value for name, value in colors.items()})

# --- contrast requirements (WCAG 2.x) ---------------------------------------------

# Text color on the background the theme puts behind it: 4.5:1 minimum.
TEXT_PAIRS = [
    (TEXT, PANEL),
    (TEXT, RIBBON_SURFACE),
    (TEXT, WINDOW),
    (TEXT, TAB_STRIP),
    (TEXT, HOVER),
    (TEXT, SELECTION),
    (TEXT, PRESSED),
    (TREE_TEXT, PANEL),
    (TREE_TEXT, HOVER),
    (TEXT_SECONDARY, PANEL),
    (TEXT_SECONDARY, RIBBON_SURFACE),
    (TEXT_SECONDARY, WINDOW),
    (TEXT_SECONDARY, TAB_STRIP),
]

# Indicator lines and frames on the background beside them: 3:1 minimum.
NONTEXT_PAIRS = [
    (ACCENT, PANEL),
    (ACCENT, RIBBON_SURFACE),
    (ACCENT, WINDOW),
    (ACCENT, TAB_STRIP),
    (ACCENT, HOVER),
    (ACCENT_DARK, PRESSED),
]

# Sketch colors: aim for 3:1 against both ends of the view gradient.
SKETCH_COLORS = [
    SKETCH_UNDER_DEFINED,
    SKETCH_FULLY_DEFINED,
    SKETCH_OVER_DEFINED,
    SKETCH_CONSTRUCTION,
    SKETCH_CONSTRUCTION_DEFINED,
    DIM_DRIVING,
    DIM_DRIVEN,
    RELATION_SYMBOLS,
]


def _channels(hex_color):
    """Red, green and blue (0-255) of a '#rrggbb' or '#rgb' string."""
    digits = str(hex_color).strip().lstrip("#")
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    if len(digits) != 6:
        raise ValueError("expected a #rrggbb or #rgb color, got %r" % (hex_color,))
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


def _linearize(channel):
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    """Relative luminance by the W3C formula: 0.0 for black up to 1.0 for white."""
    red, green, blue = (_linearize(ch) for ch in _channels(hex_color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(a, b):
    """W3C contrast ratio of two colors (1.0 to 21.0); argument order does not matter."""
    lum_a = relative_luminance(a)
    lum_b = relative_luminance(b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def packed_rgba(hex_color):
    """The color as FreeCAD stores it: unsigned 0xRRGGBBAA, fully opaque."""
    red, green, blue = _channels(hex_color)
    return (red << 24) | (green << 16) | (blue << 8) | 0xFF
