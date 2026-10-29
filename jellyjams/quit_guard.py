# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Stop FreeCAD from saving JellyJams' settings as part of quitting.

Quitting never runs Deactivated, yet FreeCAD still writes its parameters and
the main-window layout while the window shuts down. A watcher object sits in
the main window's event stream: when a Close arrives, before FreeCAD acts on
it, JellyJams is taken down. The watcher then polls until the outcome is known.
If the user backs out at the "Save changes?" prompt, the window stays open and
JellyJams is brought back, but only after no modal dialog is left on screen.
"""

from PySide import QtCore, QtWidgets

from jellyjams import console, constants, fcgui, lifecycle

# Read again for every poll that gets scheduled, so a test can shorten it.
POLL_MS = constants.QUIT_PROMPT_POLL_MS

_watcher = None


class _QuitWatcher(QtCore.QObject):
    """Event filter owned by the main window. It lets every event pass on.

    `awaiting_outcome` is True from a Close that took JellyJams down until a
    poll finds that no modal dialog is open any more.
    """

    def __init__(self, window):
        super().__init__(window)
        self.awaiting_outcome = False
        self.probe_failure_reported = False

    def eventFilter(self, watched, event):
        try:
            if event.type() == QtCore.QEvent.Type.Close:
                self._quit_requested()
        except Exception as exc:
            console.log("quit watcher: a Close event could not be handled: %s" % exc)
        return False

    def _quit_requested(self):
        if self.awaiting_outcome or not lifecycle.is_active():
            return
        self.awaiting_outcome = True
        try:
            lifecycle.revert_for_quit()
        finally:
            self._poll_later()

    def _poll_later(self):
        try:
            QtCore.QTimer.singleShot(int(POLL_MS), self._poll)
        except Exception as exc:
            self.awaiting_outcome = False
            console.log("quit watcher: the next poll could not be scheduled: %s" % exc)

    def _poll(self):
        """One look at the window after a Close; repeats while a prompt may be up."""
        try:
            if self._prompt_may_be_open():
                self._poll_later()
                return
            self.awaiting_outcome = False
            if _quit_was_cancelled():
                lifecycle.reapply_after_cancel()
        except Exception as exc:
            self.awaiting_outcome = False
            console.log("quit watcher: a poll after Close failed: %s" % exc)

    def _prompt_may_be_open(self):
        """False only when Qt confirms that no application-modal widget exists.

        An unanswerable query counts as "open": bringing JellyJams back under the
        prompt would let a later Save or Discard write JellyJams' state to disk.
        """
        try:
            return QtWidgets.QApplication.activeModalWidget() is not None
        except Exception as exc:
            if not self.probe_failure_reported:
                self.probe_failure_reported = True
                console.log("quit watcher: cannot tell whether a dialog is open: %s" % exc)
            return True


def install() -> None:
    """Attach the watcher to the main window; later calls in the session do nothing."""
    global _watcher
    with console.guard("attach the quit watcher"):
        if is_installed():
            return
        window = fcgui.main_window()
        if window is None:
            console.log("quit watcher not attached: FreeCAD has no main window yet")
            return
        watcher = _QuitWatcher(window)
        window.installEventFilter(watcher)
        _watcher = watcher


def is_installed() -> bool:
    """True while the watcher is alive and attached to the current main window."""
    try:
        if _watcher is None or not fcgui.is_alive(_watcher):
            return False
        window = fcgui.main_window()
        return window is None or _same_qobject(_watcher.parent(), window)
    except Exception:
        return False


def awaiting_quit_outcome() -> bool:
    """True between a Close that took JellyJams down and the poll that settles it."""
    watcher = _watcher
    return watcher is not None and bool(watcher.awaiting_outcome)


def _quit_was_cancelled() -> bool:
    """The main window is still on screen and JellyJams is still the workbench in use."""
    return _main_window_shown() and fcgui.jellyjams_active() and lifecycle.is_active()


def _main_window_shown() -> bool:
    window = fcgui.main_window()
    if window is None or not fcgui.is_alive(window):
        return False
    try:
        return bool(window.isVisible())
    except Exception:
        return False


def _same_qobject(first, second) -> bool:
    if first is second:
        return True
    if first is None or second is None:
        return False
    try:
        import shiboken6

        return shiboken6.getCppPointer(first)[0] == shiboken6.getCppPointer(second)[0]
    except Exception:
        return False
