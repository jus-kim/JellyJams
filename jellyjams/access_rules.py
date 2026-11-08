# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Pure command-search and per-document tab rules."""

import re

from jellyjams import constants


def words(value):
    return re.findall(r"[a-z0-9]+", str(value).casefold())


def matches(query, label, command):
    """Match unordered words, including native command names such as Pad."""
    haystack = " ".join(words(label + " " + command))
    return all(word in haystack for word in words(query))


class ContextMemory:
    """Remember a deliberate tab independently for each document and mode."""

    def __init__(self):
        self.key = None
        self.tabs = {}
        self.sketch_returns = {}

    def choose(self, document, mode, current):
        key = (document, mode)
        if key == self.key:
            return None
        if self.key is not None:
            self.tabs.pop(self.key, None)
            self.tabs[self.key] = current
        if mode == constants.TAB_SKETCH:
            # Entering sketch edit can replace a drawing window with a 3D view.
            # Preserve its prior tab even when leaving changes the view mode.
            previous = next((tab for (doc, kind), tab in reversed(self.tabs.items())
                             if doc == document and kind != constants.TAB_SKETCH),
                            constants.TAB_FEATURES)
            self.sketch_returns.setdefault(document, previous)
            wanted = constants.TAB_SKETCH
        elif document in self.sketch_returns:
            wanted = self.sketch_returns.pop(document)
            self.tabs[key] = wanted
        else:
            wanted = self.tabs.get(key, mode)
        self.key = key
        if len(self.tabs) > 128:
            self.tabs.pop(next(iter(self.tabs)))
        if len(self.sketch_returns) > 128:
            self.sketch_returns.pop(next(iter(self.sketch_returns)))
        return wanted
