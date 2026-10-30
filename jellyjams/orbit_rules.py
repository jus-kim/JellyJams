# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Mouse drag coordinates for equal orbit response on both viewport axes."""


class OrbitDrag:
    """Keep one continuous native coordinate stream across modifier changes."""

    def __init__(self, x, y):
        self.raw = (x, y)
        self.mapped = (x, y)

    def move(self, x, y, width, height, orbit=True):
        dx, dy = x - self.raw[0], y - self.raw[1]
        w, h = max(width - 1, 1), max(height - 1, 1)
        short = min(w, h)
        sx, sy = (w / short, h / short) if orbit else (1.0, 1.0)
        self.raw = (x, y)
        self.mapped = (self.mapped[0] + dx * sx, self.mapped[1] + dy * sy)
        return self.mapped
