# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Letters, tree names and captions for section and detail views.

Section views are lettered A, B, C ... and detail views Z, Y, X ...; I, O and
Q are skipped. Each new view also gets a caption: a plain TechDraw note placed
under the view and linked back to it through ``CaptionFor``. While JellyJams
is active, the caption follows the view's letter, scale and position, and a
letter typed into the caption is copied back to the view.
"""

import contextlib
import re

import FreeCAD
from PySide import QtCore

from jellyjams import console, constants, doc_utils, fcgui
from jellyjams import projected_view
from jellyjams.projected_view import num, parents, same_object, xy

SECTION_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"
DETAIL_LETTERS = SECTION_LETTERS[::-1]
KIND_SECTION = "section"
KIND_DETAIL = "detail"

UNDO_NAME = "View Label"
LABEL_NAME = "ViewLabel"
LABEL_TOOLTIP = "The drawing view this caption belongs to"
LABEL_TREE_PREFIX = "View Label "

# Caption text uses the 5 mm size of the ISO 3098 height series.
CAPTION_HEIGHT_MM = 5.0
# Distance from the view's outer extent down to the caption's anchor point.
CAPTION_CLEARANCE_MM = 6.0
# Drop below the view's anchor when the view's extent cannot be measured.
CAPTION_FALLBACK_DROP_MM = 25.0
# How often queued views are checked while some are waiting to be labelled.
QUEUE_POLL_MS = 250

_LETTER_PROPS = {KIND_SECTION: "SectionSymbol", KIND_DETAIL: "Reference"}
_AUTO_TREE_PREFIXES = {KIND_SECTION: "Section View ", KIND_DETAIL: "Detail "}
_WATCHED_PROPS = frozenset(("X", "Y", "Text", "SectionSymbol", "Reference", "Scale"))
_RATIO = r"\([ \t]*\d[\d.,]*[ \t]*:[ \t]*\d[\d.,]*[ \t]*\)"
_SCHEME = re.compile(r"([A-Z]{1,2})(?:[ \t]*-[ \t]*[A-Z]{1,2})?(?:[ \t]*" + _RATIO + r")?")
_DIGITS_ONLY = re.compile(r"[0-9]*")

_observer = None
_timer = None
_queue = []         # (document name, object name) of views whose task dialog is still open
_positions = {}     # (document name, view name) -> last seen [x, y]
_syncing = False


# --- pure rules -------------------------------------------------------------------


def next_letter(used, kind):
    """The first free letter for `kind` ("section" | "detail"); then pairs; then "?"."""
    taken = {str(u).strip() for u in (used or ()) if u is not None}
    sequence = DETAIL_LETTERS if kind == KIND_DETAIL else SECTION_LETTERS
    for letter in sequence:
        if letter not in taken:
            return letter
    for first in sequence:
        for second in sequence:
            if first + second not in taken:
                return first + second
    return "?"


def follows_scheme(text):
    """True for a single-line caption in the automatic form, e.g. "A-A", "Z (2:1)", "K"."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        return False
    return _SCHEME.fullmatch(stripped) is not None


def leading_letters(text):
    """The letter(s) a caption in the automatic form starts with, or ""."""
    match = _SCHEME.match(text.strip()) if isinstance(text, str) else None
    return match.group(1) if match else ""


def label_text(kind, letter, scale_text):
    if kind == KIND_SECTION:
        return "%s-%s" % (letter, letter)
    return "%s (%s)" % (letter, scale_text) if scale_text else letter


def tree_label(kind, letter, scale_text):
    if kind == KIND_SECTION:
        return "Section View %s-%s" % (letter, letter)
    if scale_text:
        return "Detail View %s (%s)" % (letter, scale_text)
    return "Detail View %s" % letter


def scale_text_for(value):
    """The ratio text of a scale value (drawing_common.scale_text), or "" on failure."""
    try:
        from jellyjams import drawing_common
        return drawing_common.scale_text(value)
    except Exception as exc:
        console.log("no ratio text for the scale %r: %s" % (value, exc))
        return ""


# --- document helpers -----------------------------------------------------------------


def view_kind(obj):
    """"section", "detail" or None."""
    if doc_utils.is_derived(obj, constants.TYPE_VIEW_DETAIL):
        return KIND_DETAIL
    if doc_utils.is_derived(obj, constants.TYPE_VIEW_SECTION):
        return KIND_SECTION
    return None


def letter_of(view, kind):
    return str(getattr(view, _LETTER_PROPS[kind], "") or "").strip()


def _needs_letter(kind, letter):
    if kind == KIND_SECTION:
        return letter in ("", "-")
    return _DIGITS_ONLY.fullmatch(letter) is not None


def _used_letters(doc):
    used = []
    for obj in doc.Objects:
        kind = view_kind(obj)
        if kind is not None:
            used.append(letter_of(obj, kind))
    return used


def _view_scale_text(view, kind):
    return scale_text_for(getattr(view, "Scale", 1.0)) if kind == KIND_DETAIL else ""


def find_label(view):
    """The note whose CaptionFor points at `view`, or None."""
    for obj in parents(view):
        if (doc_utils.is_derived(obj, constants.TYPE_ANNOTATION)
                and same_object(getattr(obj, constants.PROP_CAPTION_FOR, None), view)):
            return obj
    return None


def _labelled_view(label):
    view = getattr(label, constants.PROP_CAPTION_FOR, None)
    return view if doc_utils.is_alive(view) and view_kind(view) is not None else None


def _text_of(label):
    return "\n".join(str(line) for line in (getattr(label, "Text", None) or []))


def _label_tree_name(text):
    lines = text.strip().splitlines()
    return (LABEL_TREE_PREFIX + (lines[0] if lines else "")).strip()


def _caption_drop(view, kind):
    """How far below the view's anchor its caption goes, in sheet mm."""
    scale = num(getattr(view, "Scale", 1.0), 1.0)
    if kind == KIND_DETAIL:
        radius = num(getattr(view, "Radius", None), None)
        if radius is None:
            return CAPTION_FALLBACK_DROP_MM
        half_extent = radius
    else:
        base = getattr(view, "BaseView", None)
        box = projected_view.source_bound_box(base) if base is not None else None
        if box is None:
            return CAPTION_FALLBACK_DROP_MM
        half_extent = max(box.XLength, box.YLength, box.ZLength) / 2.0
    return half_extent * scale + CAPTION_CLEARANCE_MM


def _key(obj):
    return (obj.Document.Name, obj.Name)


def _document_busy(doc):
    return bool(getattr(doc, "Restoring", False) or getattr(doc, "Transacting", False))


def _sync_allowed(view):
    """Sync only while JellyJams is active, outside load/undo/redo, and after first labelling."""
    if _key(view) in _queue or _document_busy(view.Document):
        return False
    return fcgui.jellyjams_active()


@contextlib.contextmanager
def _own_changes():
    """Mark the writes inside the block as ours, so the observer does not react to them."""
    global _syncing
    previous = _syncing
    _syncing = True
    try:
        yield
    finally:
        _syncing = previous


def _set_if_changed(obj, prop, value):
    if getattr(obj, prop, None) != value:
        setattr(obj, prop, value)


def _remember(view):
    _positions[_key(view)] = list(xy(view))


# --- labelling a new view ---------------------------------------------------------------


def _create_label(view, page, kind, letter, scale_text):
    doc = view.Document
    text = label_text(kind, letter, scale_text)
    label = doc.addObject(constants.TYPE_ANNOTATION, LABEL_NAME)
    doc_utils.add_property(label, "App::PropertyLink", constants.PROP_CAPTION_FOR,
                           constants.PROP_GROUP, LABEL_TOOLTIP)
    setattr(label, constants.PROP_CAPTION_FOR, view)
    label.Text = [text]
    label.TextSize = CAPTION_HEIGHT_MM
    if "Owner" in label.PropertiesList:
        label.Owner = view
    page.addView(label)
    view_x, view_y = xy(view)
    label.X = view_x
    label.Y = view_y - _caption_drop(view, kind)
    label.Label = LABEL_TREE_PREFIX + text
    return label


def _label_new_view(view):
    kind = view_kind(view)
    with _own_changes():
        letter = letter_of(view, kind)
        if _needs_letter(kind, letter):
            letter = next_letter(_used_letters(view.Document), kind)
            setattr(view, _LETTER_PROPS[kind], letter)
        scale_text = _view_scale_text(view, kind)
        view.Label = tree_label(kind, letter, scale_text)
        if find_label(view) is None:
            page = doc_utils.parent_page(view)
            if page is not None:
                _create_label(view, page, kind, letter, scale_text)
        _remember(view)


def _label_document(doc, views):
    """Label the queued views of one document; everything goes into one "View Label" step."""
    with console.guard("label the new views in %s" % doc.Name, level="log"):
        with projected_view.undo_step(doc, UNDO_NAME):
            for view in views:
                with console.guard("label the view %s" % view.Name, level="log"):
                    _label_new_view(view)
            with console.guard("recompute the drawing after labelling", level="log"):
                doc.recompute()


def _resolve(doc_name, obj_name):
    try:
        return FreeCAD.getDocument(doc_name).getObject(obj_name)
    except Exception:
        return None


def _view_drag_running():
    """True while sheet_drag holds its own "Move View" step open."""
    try:
        from jellyjams import sheet_drag
        return bool(sheet_drag.is_dragging())
    except Exception:
        return False


def _stop_timer():
    if _timer is not None and fcgui.is_alive(_timer):
        _timer.stop()


def _start_timer():
    global _timer
    if _timer is None or not fcgui.is_alive(_timer):
        _timer = QtCore.QTimer()
        _timer.setInterval(QUEUE_POLL_MS)
        _timer.timeout.connect(_process_queue)
    if not _timer.isActive():
        _timer.start()


@console.guarded("label new section and detail views", level="log")
def _process_queue():
    if not _queue:
        _stop_timer()
        return
    if not fcgui.jellyjams_active():
        console.log("JellyJams is no longer active; %d queued section/detail view(s) "
                    "stay unlabelled" % len(_queue))
        del _queue[:]
        _stop_timer()
        return
    if fcgui.task_dialog_open() or fcgui.techdraw_tool_running() or _view_drag_running():
        return
    pending = list(_queue)
    del _queue[:]
    by_document = {}
    for doc_name, obj_name in pending:
        view = _resolve(doc_name, obj_name)
        if view is None or view_kind(view) is None:
            console.log("%s was deleted before it could be labelled" % obj_name)
            continue
        if _document_busy(view.Document):
            _queue.append((doc_name, obj_name))
            continue
        by_document.setdefault(doc_name, (view.Document, []))[1].append(view)
    for doc, views in by_document.values():
        _label_document(doc, views)
    if not _queue:
        _stop_timer()


# --- synchronization ---------------------------------------------------------------------


def _on_view_moved(view, prop):
    key = _key(view)
    old = _positions.get(key)
    new = list(xy(view))
    _positions[key] = new
    if old is None or not _sync_allowed(view):
        return
    axis = 0 if prop == "X" else 1
    delta = new[axis] - old[axis]
    if abs(delta) < 1e-9:
        return
    label = find_label(view)
    if label is None:
        return
    with _own_changes():
        setattr(label, prop, num(getattr(label, prop, 0.0)) + delta)


def _on_view_changed(view, kind, prop):
    if prop not in (_LETTER_PROPS[kind], "Scale") or not _sync_allowed(view):
        return
    letter = letter_of(view, kind)
    if not letter:
        return
    scale_text = _view_scale_text(view, kind)
    with _own_changes():
        if str(view.Label).startswith(_AUTO_TREE_PREFIXES[kind]):
            _set_if_changed(view, "Label", tree_label(kind, letter, scale_text))
        label = find_label(view)
        if label is not None and follows_scheme(_text_of(label)):
            text = label_text(kind, letter, scale_text)
            if _text_of(label) != text:
                label.Text = [text]
            _set_if_changed(label, "Label", _label_tree_name(text))


def _after_section_letter_change(key):
    view = _resolve(*key)
    if view is not None and view_kind(view) == KIND_SECTION and _sync_allowed(view):
        _on_view_changed(view, KIND_SECTION, _LETTER_PROPS[KIND_SECTION])


def _on_label_edited(label):
    view = _labelled_view(label)
    if view is None or not _sync_allowed(view):
        return
    kind = view_kind(view)
    text = _text_of(label)
    with _own_changes():
        if follows_scheme(text):
            letter = leading_letters(text)
            if letter and letter != letter_of(view, kind):
                setattr(view, _LETTER_PROPS[kind], letter)
                _set_if_changed(view, "Label",
                                tree_label(kind, letter, _view_scale_text(view, kind)))
        _set_if_changed(label, "Label", _label_tree_name(text))


class _LabelObserver:
    """Queues new section/detail views and keeps their captions in step."""

    @console.guarded("queue a new section or detail view", level="log")
    def slotCreatedObject(self, obj):
        if view_kind(obj) is None or _document_busy(obj.Document):
            return
        if not fcgui.jellyjams_active():
            return
        key = _key(obj)
        if key not in _queue:
            _queue.append(key)
        _start_timer()

    @console.guarded("note the position of a section or detail view", level="log")
    def slotBeforeChangeObject(self, obj, prop):
        if prop in ("X", "Y") and view_kind(obj) is not None:
            _remember(obj)
        elif (prop == _LETTER_PROPS[KIND_SECTION] and not _syncing
                and view_kind(obj) == KIND_SECTION and _sync_allowed(obj)):
            # A section view sends no slotChangedObject for SectionSymbol, so check after the write.
            key = _key(obj)
            fcgui.defer(lambda: _after_section_letter_change(key))

    @console.guarded("update a view caption", level="log")
    def slotChangedObject(self, obj, prop):
        if prop not in _WATCHED_PROPS or _syncing:
            return
        kind = view_kind(obj)
        if kind is not None:
            if prop in ("X", "Y"):
                _on_view_moved(obj, prop)
            else:
                _on_view_changed(obj, kind, prop)
        elif prop == "Text" and constants.PROP_CAPTION_FOR in getattr(obj, "PropertiesList", ()):
            _on_label_edited(obj)

    @console.guarded("drop a deleted view from the position list", level="log")
    def slotDeletedObject(self, obj):
        _positions.pop(_key(obj), None)

    @console.guarded("drop a closed document from the position list", level="log")
    def slotDeletedDocument(self, doc):
        for key in [k for k in _positions if k[0] == doc.Name]:
            del _positions[key]


def _scan_open_documents():
    """Note where the captioned views of already open documents are."""
    try:
        documents = list(FreeCAD.listDocuments().values())
    except Exception:
        return
    for doc in documents:
        for obj in getattr(doc, "Objects", []):
            if constants.PROP_CAPTION_FOR not in getattr(obj, "PropertiesList", ()):
                continue
            view = _labelled_view(obj)
            if view is not None and _key(view) not in _positions:
                _remember(view)


def install():
    """Register the document observer for view captions (once per session)."""
    global _observer
    if _observer is not None:
        return
    observer = _LabelObserver()
    FreeCAD.addDocumentObserver(observer)
    _observer = observer
    with console.guard("note the positions of existing view captions", level="log"):
        _scan_open_documents()
