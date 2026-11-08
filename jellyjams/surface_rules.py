# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Pure rules for editable surface control grids in geometry schema 1."""

import math


def pole_grid(points, rows, columns):
    """Validate and reshape a U-major flat control grid without changing inputs."""
    if rows < 1 or columns < 1 or len(points) != rows * columns:
        raise ValueError("The number of control points does not match the surface grid")
    values = []
    for point in points:
        value = [float(v) for v in point]
        if len(value) != 3 or not all(math.isfinite(v) for v in value):
            raise ValueError("Control points must have three finite coordinates")
        values.append(value)
    return [values[i * columns:(i + 1) * columns] for i in range(rows)]


def surfaces(definition):
    """Stable, one-based face indices across all solids in schema 1."""
    if definition.get("version") != 1:
        raise ValueError("Unsupported mathematical geometry version")
    index = 0
    for solid in definition["solids"]:
        for face in solid["faces"]:
            index += 1
            yield index, face["surface"]


def edge_match_score(first, last, length, target_first, target_last, target_length):
    """Orientation-independent score for an unchanged edge inside a local scope."""
    direct = max(math.dist(first, target_first), math.dist(last, target_last))
    reverse = max(math.dist(first, target_last), math.dist(last, target_first))
    return min(direct, reverse) + abs(length - target_length) * .0001


def fusion_retains_input(largest_input, largest_output):
    """A union cannot replace an input solid with a tiny isolated tool cell."""
    return (math.isfinite(largest_input) and math.isfinite(largest_output)
            and largest_input >= 0 and largest_output >= 0
            and largest_output >= largest_input - max(1e-6, largest_input * 1e-5))
