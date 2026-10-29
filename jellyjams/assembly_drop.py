# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Turn .FCStd files dragged in from the file manager into assembly components.

While JellyJams is active, a catcher object listens to every drag event of the
Qt application. A drag that carries local .FCStd files is claimed when some
assembly can receive it; the drop itself only queues a job. On the next turn of
the event loop the job links the model of each file into that assembly, all as
one "Insert Component" undo step. When no assembly qualifies, FreeCAD gets the
drop untouched and opens the files as usual.
"""

import functools
import os

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

from jellyjams import console, constants, doc_utils, fcgui

FCSTD_EXTENSION = ".fcstd"
TRANSACTION_NAME = "Insert Component"
COMPONENT_SPACING_MM = 20.0
SAVE_FILTER = "FreeCAD file (*.FCStd)"
SAVE_TITLE = "Save the assembly to a file so the inserted components can be linked"
FALLBACK_FILE_STEM = "Assembly"

_DRAG_EVENTS = (
    QtCore.QEvent.Type.DragEnter,
    QtCore.QEvent.Type.DragMove,
    QtCore.QEvent.Type.Drop,
)

_catcher = None


# --- switching the catcher on and off ----------------------------------------------


def enable():
    """Hook the catcher into the Qt application. Calling it again changes nothing."""
    global _catcher
    if _catcher is not None:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        console.log("dropping files onto an assembly is unavailable: no Qt application")
        return
    catcher = _DropCatcher(app)
    app.installEventFilter(catcher)
    _catcher = catcher


def disable():
    """Unhook the catcher. Safe to call when it is not hooked in."""
    global _catcher
    catcher, _catcher = _catcher, None
    if catcher is None:
        return
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None and fcgui.is_alive(catcher):
            app.removeEventFilter(catcher)
            catcher.deleteLater()
    except Exception as exc:
        console.log("the file drop catcher could not be unhooked: %s" % exc)


def is_enabled():
    return _catcher is not None


# --- pure helpers --------------------------------------------------------------------


def filter_fcstd(paths):
    """The entries of `paths` that name .FCStd files, matched in any letter case.

    Order is preserved; anything that is not a string is skipped.
    """
    return [
        path for path in (paths or ())
        if isinstance(path, str) and path.lower().endswith(FCSTD_EXTENSION)
    ]


def is_portal_path(path):
    """True when `path` points into a sandbox document portal (/run/user/<uid>/doc/...)."""
    text = str(path or "").replace("\\", "/")
    return "/run/user/" in text and "/doc/" in text


# --- choosing the receiving assembly -------------------------------------------------


def target_assembly():
    """The assembly a drop goes into, or None (assembly spec, section 3.3).

    The sources are tried in order and the first one that yields an assembly wins.
    """
    for source in (_assembly_in_edit, _assembly_of_active_view, _single_top_assembly):
        found = source()
        if found is not None:
            return found
    return None


def _assembly_in_edit():
    try:
        import UtilsAssembly

        return UtilsAssembly.activeAssembly()
    except Exception:
        return None


def _assembly_of_active_view():
    gui_doc = fcgui.active_gui_document()
    try:
        found = gui_doc.ActiveView.getActiveObject("assembly") if gui_doc else None
    except Exception:
        return None
    return found if found is not None and _is_assembly(found) else None


def _single_top_assembly():
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    tops = [obj for obj in doc.Objects if _is_assembly(obj) and not _nested_in_assembly(obj)]
    return tops[0] if len(tops) == 1 else None


def _is_assembly(obj):
    return doc_utils.is_derived(obj, constants.TYPE_ASSEMBLY)


def _nested_in_assembly(obj):
    return any(_is_assembly(parent) for parent in (obj.InList or []))


# --- the catcher ---------------------------------------------------------------------


class _DropCatcher(QtCore.QObject):
    """Application-wide event filter that claims qualifying .FCStd drags."""

    def eventFilter(self, watched, event):
        try:
            kind = event.type()
            # A catcher that disable() is taking out may still be called by Qt.
            if kind not in _DRAG_EVENTS or self is not _catcher or not fcgui.jellyjams_active():
                return False
            return _claim(event, kind == QtCore.QEvent.Type.Drop)
        except Exception as exc:
            console.log("a file drag could not be handled: %s" % exc)
            return False


def _claim(event, is_drop):
    """True when JellyJams takes the drag event; a claimed Drop also queues the job."""
    files = filter_fcstd(_dragged_local_files(event))
    if not files:
        return False
    assembly = target_assembly()
    if assembly is None:
        if is_drop:
            console.message(
                "the dropped file(s) are left to FreeCAD: there is no single assembly "
                "that could receive them"
            )
        return False
    event.acceptProposedAction()
    if is_drop:
        console.message('queued %d dropped file(s) for "%s"' % (len(files), assembly.Label))
        fcgui.defer(
            functools.partial(_run_drop_job, files, assembly.Document.Name, assembly.Name)
        )
    return True


def _dragged_local_files(event):
    mime = event.mimeData()
    if mime is None or not mime.hasUrls():
        return []
    return [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]


# --- the drop job ----------------------------------------------------------------------


@console.guarded("insert the dropped files into the assembly")
def _run_drop_job(paths, doc_name, assembly_name):
    """Deferred entry point: look the assembly up again by name and run the job."""
    job = _DropJob.find(paths, doc_name, assembly_name)
    if job is None:
        console.warning("the assembly that should receive the drop is gone; nothing was added")
        return
    job.run()


class _DropJob:
    """Everything one drop needs: the files, the receiving assembly, the results."""

    def __init__(self, paths, doc, assembly):
        self.paths = list(paths)
        self.doc = doc
        self.assembly = assembly
        self.added_labels = []

    @classmethod
    def find(cls, paths, doc_name, assembly_name):
        try:
            doc = FreeCAD.getDocument(doc_name)
            assembly = doc.getObject(assembly_name)
        except Exception:
            return None
        return None if assembly is None else cls(paths, doc, assembly)

    def run(self):
        self._warn_about_portal_paths()
        if not _has_file_location(self.doc, self.paths[0]):
            console.warning(
                'no component was added: "%s" has to be saved to a file first'
                % self.assembly.Label
            )
            return
        self._focus()
        if not _enter_edit(self.assembly):
            console.message(
                "a task dialog is open, so the assembly was not activated; double-click "
                "it afterwards to move the new components"
            )
        with doc_utils.transaction(self.doc, TRANSACTION_NAME):
            for path in self.paths:
                with console.guard("insert %s" % path):
                    self._take_file(path)
        with console.guard("finish inserting the dropped files", level="log"):
            self._focus()
            self.doc.recompute()
            if self.added_labels:
                _enter_edit(self.assembly)
        self._report()

    def _warn_about_portal_paths(self):
        for path in self.paths:
            if is_portal_path(path):
                console.warning(
                    "%s comes through the sandbox document portal; the link to it may break "
                    'once FreeCAD restarts. "Insert Component" creates a lasting link.' % path
                )

    def _report(self):
        names = ", ".join('"%s"' % label for label in self.added_labels)
        console.message(
            '"%s" received %d new component(s)%s'
            % (self.assembly.Label, len(self.added_labels), (": " + names) if names else "")
        )

    def _focus(self):
        _make_current(self.doc)

    def _take_file(self, path):
        """Link the model objects of one file; a hidden copy is closed if unused."""
        source, opened_now = self._source_for(path)
        if source is None:
            return
        count_before = len(self.added_labels)
        try:
            models = doc_utils.primary_model_objects(source)
            if not models:
                console.warning(
                    "%s was skipped: no assembly, part, body or solid sits at its top level"
                    % os.path.basename(path)
                )
            for model in models:
                link = self._link(model, path)
                if link is not None:
                    self.added_labels.append(link.Label)
        finally:
            if opened_now and len(self.added_labels) == count_before:
                with console.guard("close %s" % os.path.basename(path), level="log"):
                    FreeCAD.closeDocument(source.Name)
                self._focus()

    def _source_for(self, path):
        """(document, opened_now): reuse an open copy of `path`, else load it hidden."""
        already_open = _open_document_for(path)
        if already_open is not None:
            return already_open, False
        try:
            loaded = FreeCAD.openDocument(path, True)
        except Exception as exc:
            console.error("%s could not be loaded: %s" % (path, exc))
            loaded = None
        self._focus()
        return loaded, loaded is not None

    def _link(self, model, path):
        """Create the link component for `model`; None once a failure is reported."""
        siblings = _components_of(self.assembly)
        needs_ground = not _has_ground(self.assembly)
        link_type = (
            constants.TYPE_ASSEMBLY_LINK if _is_assembly(model) else constants.TYPE_LINK
        )
        link = self.assembly.newObject(link_type, model.Label)
        try:
            if _same_doc_object(model, self.assembly):
                raise ValueError("an assembly cannot contain itself")
            link.LinkedObject = model
        except Exception as exc:
            with console.guard("remove the unfinished component", level="log"):
                self.doc.removeObject(link.Name)
            console.error(
                'could not link "%s" from %s: %s'
                % (model.Label, os.path.basename(path), exc)
            )
            return None
        # newObject() can garble labels outside ASCII, so the label is written again.
        link.Label = model.Label
        link.recompute()
        with console.guard('move "%s" clear of the other components' % model.Label, level="log"):
            _shift_clear_of(link, siblings)
        if needs_ground:
            _fix_in_place(link)
        return link


# --- placing and fixing components ----------------------------------------------------


def _components_of(assembly):
    """Links and assembly links that are already members of `assembly`."""
    return [
        obj for obj in (assembly.Group or [])
        if doc_utils.is_derived(obj, constants.TYPE_LINK)
        or doc_utils.is_derived(obj, constants.TYPE_ASSEMBLY_LINK)
    ]


def _has_ground(assembly):
    """True when something in the assembly's own document already fixes a component."""
    home = assembly.Document.Name
    for obj in assembly.OutListRecursive:
        try:
            if obj.Document.Name == home and hasattr(obj, "ObjectToGround"):
                return True
        except Exception:
            continue
    return False


def _shift_clear_of(link, siblings):
    """Slide `link` along +X so it starts COMPONENT_SPACING_MM past every sibling."""
    if not siblings:
        return
    right_edge = _right_edge(siblings)
    own_box = _shape_box(link)
    if right_edge is None or own_box is None:
        return
    placement = link.Placement
    offset = right_edge + COMPONENT_SPACING_MM - own_box.XMin
    placement.Base = placement.Base + FreeCAD.Vector(offset, 0, 0)
    link.Placement = placement


def _right_edge(objects):
    """Largest XMax over the shapes of `objects`; None if any box is missing."""
    edge = None
    for obj in objects:
        box = _shape_box(obj)
        if box is None:
            return None
        edge = box.XMax if edge is None else max(edge, box.XMax)
    return edge


def _shape_box(obj):
    try:
        import Part

        box = Part.getShape(obj).BoundBox
    except Exception:
        return None
    return box if box.isValid() else None


def _fix_in_place(link):
    try:
        import CommandCreateJoint

        joint = CommandCreateJoint.createGroundedJoint(link)
    except Exception as exc:
        console.warning('"%s" could not be fixed in place: %s' % (link.Label, exc))
        return
    if joint is None:
        console.warning(
            '"%s" was left free: an assembly has to be active to fix a component' % link.Label
        )


# --- documents and edit mode --------------------------------------------------------------


def _has_file_location(doc, hint_path):
    """True once `doc` is stored in a file; if it is not, offer Save As first."""
    if doc.FileName:
        return True
    stem = doc.Label or doc.Name or FALLBACK_FILE_STEM
    proposal = os.path.join(os.path.dirname(hint_path), stem + ".FCStd")
    chosen, _picked_filter = QtWidgets.QFileDialog.getSaveFileName(
        fcgui.main_window(), SAVE_TITLE, proposal, SAVE_FILTER
    )
    if not chosen:
        return False
    if not chosen.lower().endswith(FCSTD_EXTENSION):
        chosen += ".FCStd"
    with console.guard("save the assembly as %s" % chosen):
        doc.saveAs(chosen)
    return bool(doc.FileName)


def _open_document_for(path):
    """The open document whose file is `path`, or None."""
    key = _path_key(path)
    for open_doc in FreeCAD.listDocuments().values():
        file_name = getattr(open_doc, "FileName", "")
        if file_name and _path_key(file_name) == key:
            return open_doc
    return None


def _enter_edit(assembly):
    """Put `assembly` in edit mode; False when an open task dialog prevents it."""
    if _same_doc_object(_assembly_in_edit(), assembly):
        return True
    if fcgui.task_dialog_open():
        return False
    with console.guard('activate the assembly "%s"' % assembly.Label, level="warning"):
        FreeCADGui.getDocument(assembly.Document.Name).setEdit(assembly)
    return True


def _make_current(doc):
    with console.guard("make %s the active document" % doc.Name, level="log"):
        FreeCAD.setActiveDocument(doc.Name)
        FreeCADGui.setActiveDocument(doc.Name)


def _same_doc_object(first, second):
    try:
        return first is not None and second is not None and (
            first.Document.Name == second.Document.Name and first.Name == second.Name
        )
    except Exception:
        return False


def _path_key(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))
