# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Original appearance library and colour validation, independent of FreeCAD/Qt."""

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class Appearance:
    name: str
    color: str
    finish: str = "High Gloss"
    transparency: int = 0


# Native Phong lighting: (specular intensity, normalized shininess).
FINISHES = {
    "High Gloss": (0.85, 0.85),
    "Satin": (0.40, 0.35),
    "Matte": (0.08, 0.08),
    "Polished": (0.95, 0.95),
    "Metallic": (0.75, 0.65),
    "Clear": (0.90, 0.90),
}
COLORS = (
    ("White", "#f2f2ee"), ("Cream", "#e8d9b9"),
    ("Light Grey", "#b4b9be"), ("Dark Grey", "#535960"),
    ("Black", "#20252b"), ("Red", "#c93838"),
    ("Blue", "#245ac9"), ("Green", "#299654"),
    ("Yellow", "#ebc532"), ("Orange", "#e97d28"),
    ("Purple", "#8859b8"), ("Teal", "#239c9b"),
)
METALS = (
    ("Aluminium", "#c4cbd2"), ("Steel", "#939da7"),
    ("Dark Steel", "#525c68"), ("Brass", "#bd9d51"),
    ("Copper", "#bb7755"), ("Gold", "#dfbd62"),
)
LIBRARY = {
    ("Plastic", finish): tuple(Appearance(name + " " + finish.lower() + " plastic",
                                         color, finish, 65 if finish == "Clear" else 0)
                               for name, color in COLORS)
    for finish in ("High Gloss", "Satin", "Matte", "Clear")
}
LIBRARY.update({
    ("Metal", finish): tuple(Appearance(name + " " + finish.lower(), color, finish)
                              for name, color in METALS)
    for finish in ("Polished", "Metallic", "Matte")
})
LIBRARY.update({
    ("Paint", finish): tuple(Appearance(name + " " + finish.lower() + " paint", color, finish)
                              for name, color in COLORS)
    for finish in ("High Gloss", "Satin", "Matte")
})


def rgb(color):
    """Strict #RRGGBB input as three normalized channels."""
    if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
        raise ValueError("Enter a colour as #RRGGBB, for example #245AC9.")
    return tuple(int(color[index:index + 2], 16) / 255.0 for index in (1, 3, 5))


def material_values(appearance):
    """Validate the entire edit before opening a document transaction."""
    color = rgb(appearance.color)
    if appearance.finish not in FINISHES:
        raise ValueError("Choose a finish from the list.")
    amount = float(appearance.transparency)
    if not math.isfinite(amount) or not 0 <= amount <= 100:
        raise ValueError("Transparency must be between 0 and 100 percent.")
    specular, shininess = FINISHES[appearance.finish]
    return color, specular, shininess, amount / 100.0


def face_index(name, count):
    """Zero-based face index, or None for an invalid/out-of-range face name."""
    match = re.fullmatch(r"Face([1-9][0-9]*)", str(name))
    index = int(match.group(1)) - 1 if match else -1
    return index if 0 <= index < count else None
