# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Where JellyJams lives on disk: the add-on folder, its icons and the per-user cache folder."""

import os
import sys
import tempfile

from jellyjams import constants

ICON_EXTENSIONS = (".svg", ".png")


def _is_addon_root(folder):
    return os.path.isfile(os.path.join(folder, "InitGui.py")) and os.path.isfile(
        os.path.join(folder, "jellyjams", "__init__.py")
    )


def addon_dir():
    """Folder that contains InitGui.py and the jellyjams package, or None.

    Uses abspath on purpose, not realpath: for a symlinked or junctioned add-on
    the result is the path FreeCAD loaded, not the link target.
    """
    try:
        import jellyjams

        root = os.path.dirname(os.path.dirname(os.path.abspath(jellyjams.__file__)))
        if os.path.isfile(os.path.join(root, "InitGui.py")):
            return root
    except Exception:
        pass
    for entry in list(sys.path):
        try:
            folder = os.path.abspath(entry or os.curdir)
            if _is_addon_root(folder):
                return folder
        except Exception:
            continue
    return None


def icons_dir():
    """<add-on>/resources/icons when that folder exists, otherwise None."""
    try:
        root = addon_dir()
        if not root:
            return None
        folder = os.path.join(root, "resources", "icons")
        return folder if os.path.isdir(folder) else None
    except Exception:
        return None


def icon_path(base):
    """Absolute path of icon `base`, trying .svg before .png; "" if no non-empty file exists."""
    try:
        if not base:
            return ""
        folder = icons_dir()
        if not folder:
            return ""
        for extension in ICON_EXTENSIONS:
            candidate = os.path.join(folder, base + extension)
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return candidate
    except Exception:
        pass
    return ""


def is_link(path):
    """True when `path` is, or sits below, a symlink or junction. Never raises."""
    try:
        if not path:
            return False
        if os.path.islink(path):
            return True
        real = os.path.normcase(os.path.realpath(path))
        return real != os.path.normcase(os.path.abspath(path))
    except Exception:
        return False


def user_cache_dir(*parts):
    """<FreeCAD user data>/JellyJams/<parts...>; the folder is created if needed."""
    try:
        import FreeCAD

        base = FreeCAD.getUserAppDataDir()
    except Exception:
        base = tempfile.gettempdir()
    folder = os.path.join(base, constants.ADDON_NAME, *parts)
    os.makedirs(folder, exist_ok=True)
    return folder
