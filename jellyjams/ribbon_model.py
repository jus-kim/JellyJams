# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Match the ribbon layout with the commands FreeCAD actually has.

Pure module, no FreeCAD and no Qt. resolve() swaps in fallback ids, leaves
out what FreeCAD lacks and returns the model that ribbon_widgets draws.
"""

from jellyjams import ribbon_layout as layout
from jellyjams import ribbon_text


def entry_id(cmd, index=None):
    """Id of a ribbon entry: the command id, plus "#<index>" for a sub-entry."""
    return cmd if index is None else "{}#{}".format(cmd, index)


def object_name(prefix, entry_id):
    """Qt objectName for an entry: `prefix` plus the entry id, with the "#" before a
    sub-entry index turned into "-" so the name stays usable in a stylesheet selector."""
    return prefix + entry_id.replace("#", "-")


class RButton:
    """A command that made it onto the ribbon (button, flyout variant or toggle variant)."""

    def __init__(self, entry_id, cmd, index, label, jj_icon=None, fc_icon=None, substituted_from=None):
        self.entry_id = entry_id
        self.cmd = cmd
        self.index = index
        self.label = label
        self.one_line = ribbon_text.one_line(label)
        self.jj_icon = jj_icon
        self.fc_icon = fc_icon
        self.substituted_from = substituted_from

    def __repr__(self):
        return "RButton({})".format(self.entry_id)


class RFlyout:
    def __init__(self, flyout_id, variants, title=None):
        self.flyout_id = flyout_id
        self.variants = list(variants)
        self.title = title

    def __repr__(self):
        return "RFlyout({})".format(self.flyout_id)


class RToggle:
    def __init__(self, variants):
        self.variants = list(variants)

    def __repr__(self):
        return "RToggle({})".format([v.entry_id for v in self.variants])


class RStack:
    def __init__(self, style, cells):
        self.style = style
        self.cells = list(cells)


class RGroup:
    def __init__(self, name, items):
        self.name = name
        self.items = list(items)


class RTab:
    def __init__(self, title, groups):
        self.title = title
        self.groups = list(groups)


class Resolved:
    """The resolved ribbon, with the ids that were left out or replaced."""

    def __init__(self, tabs, skipped, substitutions):
        self.tabs = list(tabs)
        self.skipped = list(skipped)
        self.substitutions = list(substitutions)

    def items(self):
        """Buttons, flyouts and toggles in ribbon order; stacks are opened up."""
        for tab in self.tabs:
            for group in tab.groups:
                for item in group.items:
                    if isinstance(item, RStack):
                        yield from item.cells
                    else:
                        yield item

    def tab(self, title):
        for tab in self.tabs:
            if tab.title == title:
                return tab
        return None

    def plain_ids(self):
        return [item.entry_id for item in self.items() if isinstance(item, RButton)]

    def flyouts(self):
        return [(item.flyout_id, [v.entry_id for v in item.variants])
                for item in self.items() if isinstance(item, RFlyout)]

    def toggles(self):
        return [[v.entry_id for v in item.variants]
                for item in self.items() if isinstance(item, RToggle)]

    def all_ids(self):
        ids = self.plain_ids()
        for _flyout_id, variants in self.flyouts():
            ids.extend(variants)
        for variants in self.toggles():
            ids.extend(variants)
        return ids

    def separators(self, tab_title):
        tab = self.tab(tab_title)
        if tab is None:
            return 0
        return max(0, len(tab.groups) - 1)


class _Resolver:
    def __init__(self, available):
        self.available = set(available)
        self.skipped = []
        self.substitutions = []

    def _skip(self, cmd):
        missing = entry_id(cmd.cmd, cmd.index)
        if missing not in self.skipped:
            self.skipped.append(missing)

    def button(self, cmd):
        used = cmd.cmd
        if used not in self.available:
            used = next((fb for fb in cmd.fallbacks if fb in self.available), None)
            if used is None:
                self._skip(cmd)
                return None
            self.substitutions.append((cmd.cmd, used))
        return RButton(
            entry_id(used, cmd.index), used, cmd.index, cmd.label,
            jj_icon=cmd.jj_icon, fc_icon=cmd.fc_icon,
            substituted_from=None if used == cmd.cmd else cmd.cmd,
        )

    def flyout(self, flyout):
        variants = [b for b in (self.button(v) for v in flyout.variants) if b is not None]
        if not variants:
            return None
        return RFlyout(variants[0].entry_id, variants, flyout.title)

    def toggle(self, toggle):
        variants = [b for b in (self.button(toggle.normal), self.button(toggle.editing)) if b is not None]
        if len(variants) == 2:
            return RToggle(variants)
        return variants[0] if variants else None

    def stack(self, stack):
        cells = [c for c in (self.entry(e) for e in stack.entries) if c is not None]
        return RStack(stack.style, cells) if cells else None

    def entry(self, entry):
        if isinstance(entry, layout.Cmd):
            return self.button(entry)
        if isinstance(entry, layout.Flyout):
            return self.flyout(entry)
        if isinstance(entry, layout.Toggle):
            return self.toggle(entry)
        if isinstance(entry, layout.Stack):
            return self.stack(entry)
        raise TypeError("not a ribbon layout entry: {!r}".format(entry))

    def group(self, group):
        items = [i for i in (self.entry(e) for e in group.entries) if i is not None]
        return RGroup(group.name, items) if items else None

    def tab(self, tab):
        groups = [g for g in (self.group(g) for g in tab.groups) if g is not None]
        return RTab(tab.title, groups)


def resolve(tabs, available):
    """Build the ribbon model for `tabs`, given the set of registered command ids.

    A command missing from `available` is replaced by its first available
    fallback, or else left out and listed in `skipped`. A flyout keeps the
    variants that remain and takes its id from the first of them; a toggle
    with only one remaining variant becomes a plain button. Stacks and groups
    that end up empty disappear.
    """
    resolver = _Resolver(available)
    resolved_tabs = [resolver.tab(tab) for tab in tabs]
    return Resolved(resolved_tabs, resolver.skipped, resolver.substitutions)
