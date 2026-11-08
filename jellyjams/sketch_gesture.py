# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Connect profile features and sketches the way SolidWorks does.

``ribbon.run_entry`` passes every press that has no sub-command index to
``try_run`` first. Two cases are taken over:

* A sketch is open: it is closed the same way "Exit Sketch" closes it, then
  selected, and the feature command runs with it as the profile.
* There is nothing to use as a profile (nothing selected and no free sketch in
  the active body, or only planes / flat faces selected) and the feature is in
  ``constants.SKETCH_FIRST_FEATURES``: a new sketch is started instead (FreeCAD
  asks for a plane unless one is selected), and when that sketch is closed with
  geometry in it, the feature command runs with it as the profile.
"""

import time

from jellyjams import console, constants, doc_utils, fcgui

LEAVE_SKETCH = "Sketcher_LeaveSketch"

SETTLE_MS = 50            # first check after leaving the sketch (50 ms works on 1.1.4)
POLL_MS = 25              # re-check interval while the sketch is still closing
SETTLE_CAP_MS = 1000      # stop waiting and start the feature regardless
PENDING_TIMEOUT_S = 3.0   # pending state expires, so a lost timer cannot block presses

WATCH_MS = 150            # sketch-first: how often the plane pick / sketch edit is checked
PICK_GRACE_S = 1.5        # sketch-first: time FreeCAD gets to open its plane picker

PICKING, EDITING = "picking", "editing"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
CONTAINER_TYPES = ("PartDesign::Body", "App::Origin", "App::Part", "App::DocumentObjectGroup")
# Features that need a solid to cut into. FreeCAD itself refuses the first two, with its own
# message, while the body has none; Hole has no such check.
SUBTRACTIVE_FEATURES = ("PartDesign_Pocket", "PartDesign_Groove", "PartDesign_Hole")
REFUSED_BY_FREECAD = ("PartDesign_Pocket", "PartDesign_Groove")
NEEDS_SOLID_MS = 6000

_pending_since = None
_intent = None            # sketch-first state, see advance()


def is_profile_feature(cmd_id):
    """True when `cmd_id` is a feature that uses a preselected sketch as its profile."""
    return cmd_id in constants.PROFILE_FEATURES


def is_pending():
    """True while a feature start is queued behind a closing sketch."""
    if _pending_since is None:
        return False
    return (time.monotonic() - _pending_since) < PENDING_TIMEOUT_S


def try_run(cmd_id):
    """Handle a ribbon press of `cmd_id` when it is a profile feature and a sketch is open.

    Returns True when the press was taken over (a repeat press while a start
    is already queued counts too). False tells the caller to run the command
    itself.
    """
    global _pending_since, _intent
    try:
        if not is_profile_feature(cmd_id):
            return False
        if is_pending():
            return True
        sketch = fcgui.sketch_in_edit()
        if sketch is None:
            if _intent is not None and _intent["state"] == PICKING:
                if not fcgui.task_dialog_open():
                    _drop_intent()   # the plane picker was cancelled or never opened
                elif cmd_id in constants.SKETCH_FIRST_FEATURES:
                    if _nothing_to_cut(cmd_id, _active_doc()):
                        return _refuse_without_solid(cmd_id)
                    _intent["cmd"] = cmd_id   # FreeCAD's plane picker is open: just retarget
                    _show_hint(cmd_id)
                    return True
                else:
                    return False
            return _maybe_start_sketch_first(cmd_id)
        _drop_intent()   # an explicit press while sketching wins over a queued sketch-first
        gui = fcgui.gui()
        if gui is None:
            return False
        try:
            gui.runCommand(LEAVE_SKETCH)
        except Exception as exc:
            console.warning(
                "%s will run without closing the sketch first: %s failed (%s)"
                % (cmd_id, LEAVE_SKETCH, exc)
            )
            return False
        _pending_since = time.monotonic()
        _schedule(cmd_id, sketch, SETTLE_MS, 0)
        return True
    except Exception as exc:
        _pending_since = None
        console.log("sketch-to-feature handoff not used for %s: %s" % (cmd_id, exc))
        return False


def _schedule(cmd_id, sketch, delay_ms, waited_ms):
    fcgui.defer(lambda: _continue(cmd_id, sketch, waited_ms + delay_ms), delay_ms)


def _sketch_still_closing():
    return fcgui.sketch_in_edit() is not None or fcgui.task_dialog_open()


def _continue(cmd_id, sketch, waited_ms):
    try:
        if _sketch_still_closing() and waited_ms < SETTLE_CAP_MS:
            _schedule(cmd_id, sketch, POLL_MS, waited_ms)
            return
    except Exception:
        pass
    _start_feature(cmd_id, sketch)


def _start_feature(cmd_id, sketch):
    global _pending_since
    try:
        gui = fcgui.gui()
        try:
            if not doc_utils.is_alive(sketch):
                raise RuntimeError("the sketch has been deleted")
            gui.Selection.clearSelection()
            gui.Selection.addSelection(sketch)
        except Exception as exc:
            console.warning("starting %s without the sketch preselected: %s" % (cmd_id, exc))
        try:
            gui.runCommand(cmd_id)
        except Exception as exc:
            console.error("%s failed to start: %s" % (cmd_id, exc))
    finally:
        _pending_since = None


# --- sketch first -------------------------------------------------------------------------

def needs_new_sketch(cmd_id, selection_kinds, free_sketches):
    """Decide whether a press of `cmd_id` should begin with a new sketch.

    `selection_kinds` holds one entry per selected item: "plane" (datum or origin
    plane), "flat_face" (planar face of a solid), "sketch" or "other".
    `free_sketches` counts sketches FreeCAD could take as the profile without a
    selection (in the active body, not used by a feature, with at least one wire).
    """
    if cmd_id not in constants.SKETCH_FIRST_FEATURES:
        return False
    if selection_kinds:
        return all(kind in ("plane", "flat_face") for kind in selection_kinds)
    return free_sketches == 0


def advance(intent, editing_name, dialog_open, new_sketch_names, now):
    """One step of the sketch-first state machine. Returns (intent, action).

    `intent` is None or {"cmd", "state", "sketch", "since"}. `editing_name` is the
    name of the sketch in edit (or None), `new_sketch_names` the sketches created
    since the press. Actions: None (keep waiting), "start" (run the feature on
    intent["sketch"]), "drop" (give up quietly).
    """
    if intent is None:
        return None, None
    if intent["state"] == PICKING:
        if editing_name is not None and editing_name in new_sketch_names:
            moved = dict(intent, state=EDITING, sketch=editing_name, since=now)
            return moved, None
        if dialog_open or editing_name is not None:
            return intent, None
        if now - intent["since"] < PICK_GRACE_S:
            return intent, None
        return None, "drop"
    if editing_name == intent["sketch"] or (editing_name is None and dialog_open):
        return intent, None
    if editing_name is not None:
        return None, "drop"   # the user went on to edit a different sketch
    return None, "start"


def _is_sketch(obj):
    try:
        return obj.isDerivedFrom("Part::Part2DObject")
    except Exception:
        return False


def _drop_intent():
    global _intent
    if _intent is not None:
        _intent = None
        fcgui.clear_status()


def _show_hint(cmd_id):
    name = (fcgui.command_info(cmd_id).get("menuText") or cmd_id).replace("&", "")
    fcgui.status_message(
        "New sketch for %s: pick a plane or a flat face, draw the profile, then exit the sketch." % name)


def _target_body(doc):
    """The body a profile feature works in: the active one, or the only one (FreeCAD
    activates a lone body by itself)."""
    try:
        body = fcgui.active_gui_document().ActiveView.getActiveObject(constants.ACTIVE_BODY_KEY)
        if body is not None:
            return body
    except Exception:
        pass
    bodies = [o for o in doc.Objects if doc_utils.is_derived(o, "PartDesign::Body")]
    return bodies[0] if len(bodies) == 1 else None


def _has_solid(body):
    """FreeCAD's own test for a body with something to cut: it holds a Part Design feature
    (datum planes, lines and points are not features)."""
    try:
        return any(obj.isDerivedFrom("PartDesign::Feature") for obj in body.Group)
    except Exception:
        return False


def _active_doc():
    return getattr(fcgui.active_gui_document(), "Document", None)


def _nothing_to_cut(cmd_id, doc):
    """True for a cutting feature while the target body is known and has no solid yet; such
    a press never starts or takes over a sketch-first. Without a known body FreeCAD asks
    which body to work in, so that is left to it."""
    if cmd_id not in SUBTRACTIVE_FEATURES:
        return False
    body = _target_body(doc) if doc is not None else None
    return body is not None and not _has_solid(body)


def _refuse_without_solid(cmd_id):
    """Turn down a cutting feature in a body with nothing to cut. Pocket and Groove go to
    FreeCAD, which refuses them with its own message (returns False); for the rest JellyJams
    explains and takes the press (returns True)."""
    if cmd_id in REFUSED_BY_FREECAD:
        return False
    name = (fcgui.command_info(cmd_id).get("menuText") or cmd_id).replace("&", "")
    text = "%s needs a solid to cut into: create a boss or base feature first." % name
    fcgui.status_message(text, NEEDS_SOLID_MS)
    console.warning(text)
    return True


def _after_insert_point(body):
    """Names of the body's objects that come after the next solid feature following its Tip;
    FreeCAD does not offer those as profiles."""
    try:
        group = list(body.Group)
        tip = body.Tip
        start = group.index(tip) + 1 if tip in group else len(group)
        for index in range(start, len(group)):
            obj = group[index]
            if obj.isDerivedFrom("PartDesign::Feature") and not _is_sketch(obj):
                return {o.Name for o in group[index:]}
    except Exception:
        pass
    return set()


def _free_sketch_count(doc, body):
    """Sketches FreeCAD's profile features would accept without a selection."""
    hidden = _after_insert_point(body) if body is not None else set()
    count = 0
    for obj in doc.Objects:
        if not _is_sketch(obj) or obj.Name in hidden:
            continue
        try:
            if body is not None and not body.hasObject(obj):
                continue
            users = [o for o in obj.InList
                     if o.isDerivedFrom("PartDesign::Feature") and not o.isDerivedFrom("PartDesign::Body")]
            if users or obj.Shape.isNull() or not obj.Shape.Wires:
                continue
        except Exception:
            continue
        count += 1
    return count


def _selection_kinds():
    kinds = []
    for item in fcgui.selection_ex() or ():
        obj = getattr(item, "Object", None)
        subs = [s for s in (getattr(item, "SubElementNames", None) or ()) if s]
        if obj is None:
            continue
        if not subs and any(doc_utils.is_derived(obj, t) for t in CONTAINER_TYPES):
            kinds.append("container")   # e.g. the Body that the Body button leaves selected
        elif any(doc_utils.is_derived(obj, t) for t in PLANE_TYPES):
            kinds.append("plane")
        elif _is_sketch(obj):
            kinds.append("sketch")
        elif subs and all(s.startswith("Face") and _is_flat_face(obj, s) for s in subs):
            kinds.append("flat_face")
        else:
            kinds.append("other")
    return kinds


def _is_flat_face(obj, sub):
    try:
        face = obj.Shape.getElement(sub)
        return face.findPlane() is not None
    except Exception:
        return False


def _sketch_names(doc):
    return {o.Name for o in doc.Objects if _is_sketch(o)}


def _maybe_start_sketch_first(cmd_id):
    global _intent
    if fcgui.task_dialog_open():
        return False
    doc = _active_doc()
    if doc is None:
        return False
    kinds = _selection_kinds()
    if kinds and all(kind == "container" for kind in kinds):
        # A selected body or group is no profile; FreeCAD would reject it, so drop it.
        fcgui.gui().Selection.clearSelection()
        kinds = []
    body = _target_body(doc)
    if cmd_id in SUBTRACTIVE_FEATURES and body is None:
        return False   # FreeCAD asks which body to cut into
    if _nothing_to_cut(cmd_id, doc):
        return _refuse_without_solid(cmd_id)
    if not needs_new_sketch(cmd_id, kinds, _free_sketch_count(doc, body)):
        return False
    started = {"cmd": cmd_id, "state": PICKING, "sketch": None, "since": time.monotonic(),
               "doc": doc.Name, "before": _sketch_names(doc)}
    _intent = started
    _show_hint(cmd_id)
    if not fcgui.run_command(constants.NEW_SKETCH_COMMAND):
        _intent = None
        fcgui.clear_status()
        return False
    fcgui.defer(lambda: _watch(started), WATCH_MS)
    return True


def _attachment_has_plane(intent, doc):
    candidates = [obj for obj in doc.Objects if _is_sketch(obj) and obj.Name not in intent["before"]]
    if len(candidates) != 1:
        return False
    sketch = candidates[0]
    support = list(getattr(sketch, "AttachmentSupport", ()) or ())
    if len(support) != 1 or str(getattr(sketch, "MapMode", "Deactivated")) == "Deactivated":
        return False
    obj, subs = support[0]
    subs = [sub for sub in subs if sub]
    if len(subs) > 1:
        return False
    if subs:
        # retType=1 asks for the document object, rather than its geometric
        # Python representation (the default), along an Origin support path.
        try:
            obj = obj.getSubObject(subs[0], 1)
        except Exception:
            return False
    return any(doc_utils.is_derived(obj, kind) for kind in PLANE_TYPES)


def _confirm_plane_pick(intent, doc):
    """Confirm one plane selected in this sketch-first's native picker.

    Older list clicks require a second activation; 26's attachment editor also
    waits for confirmation after selecting a plane. The existing watcher runs
    after the click has returned to FreeCAD and presses the native OK button.
    """
    if (intent is not _intent or intent["state"] != PICKING
            or _active_doc() is not doc or fcgui.sketch_in_edit() is not None):
        return False
    from PySide import QtCore, QtWidgets

    panel = fcgui.task_panel()
    if panel is None:
        return False
    # Older hosts put the native button box beside TaskPanel, rather than
    # inside it. Only the active panel's visible task dock is searched.
    button_scope = fcgui.task_dock() or panel
    for form in panel.findChildren(QtWidgets.QWidget):
        names = (form.metaObject().className().replace("__", "::"), form.objectName().replace("__", "::"))
        if not form.isVisibleTo(panel):
            continue
        if constants.CLASS_FEATURE_PICK in names:
            choices = form.findChild(QtWidgets.QListWidget, constants.OBJ_FEATURE_PICK_LIST)
            selected = choices.selectedItems() if choices is not None else []
            if len(selected) != 1 or selected[0].isHidden():
                continue
            obj = doc.getObject(str(selected[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""))
            if (not any(doc_utils.is_derived(obj, kind) for kind in PLANE_TYPES)
                    or not selected[0].flags() & QtCore.Qt.ItemFlag.ItemIsEnabled):
                continue
        elif constants.CLASS_TASK_ATTACHER in names:
            if not _attachment_has_plane(intent, doc):
                continue
        else:
            continue
        for box in button_scope.findChildren(QtWidgets.QDialogButtonBox):
            button = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
            if button is not None and button.isVisibleTo(button_scope) and button.isEnabled():
                button.click()
                return True
    return False


def _watch(expected=None):
    """Follow one sketch-first until it starts its feature or is dropped. `expected` is the
    intent this chain of checks belongs to; a chain whose intent was replaced stops."""
    global _intent
    intent = _intent
    if intent is None or (expected is not None and intent is not expected):
        return
    try:
        import FreeCAD

        doc = FreeCAD.getDocument(intent["doc"]) if intent["doc"] in FreeCAD.listDocuments() else None
        if doc is None or not fcgui.jellyjams_active():
            console.log("sketch-first for %s cancelled: %s" % (
                intent["cmd"], "document closed" if doc is None
                else "workbench is now " + str(fcgui.active_workbench_name())))
            _intent = None
            fcgui.clear_status()
            return
        sketch = fcgui.sketch_in_edit()
        editing = sketch.Name if sketch is not None and sketch.Document == doc else None
        if editing is None and intent["state"] == PICKING:
            # A picker mismatch/failure must not stop watching sketch entry,
            # cancellation or later feature creation.
            with console.guard("confirm the selected sketch plane", level="log"):
                _confirm_plane_pick(intent, doc)
        created = _sketch_names(doc) - intent["before"]
        state, action = advance(intent, editing, fcgui.task_dialog_open(), created, time.monotonic())
        if _intent is not intent:
            return   # a newer press replaced this sketch-first while it waited
        _intent = state
        if action is None:
            fcgui.defer(lambda: _watch(state), WATCH_MS)
            return
        fcgui.clear_status()
        if action == "start":
            finished = doc.getObject(intent["sketch"])
            if finished is not None and len(getattr(finished, "Geometry", ()) or ()) > 0:
                _start_feature(intent["cmd"], finished)
    except Exception as exc:
        _drop_intent()
        console.log("sketch-first for a profile feature stopped: %s" % exc)
