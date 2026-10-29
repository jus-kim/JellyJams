# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_NewAssembly (New Assembly) and JellyJams_RotateComponent (Rotate Component).

JellyJams_NewAssembly never nests: it always opens a fresh AssemblyN document and
builds the assembly there. JellyJams_RotateComponent spins a single floating, unmated
component of the active assembly about its own placement origin while the left
mouse button is dragged across the 3D view.
"""

import functools
import math

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

from jellyjams import commands, console, constants, doc_utils, fcgui

ASSEMBLY_BASE_NAME = "Assembly"
CREATE_ASSEMBLY_COMMAND = "Assembly_CreateAssembly"

NEW_ASSEMBLY_TOOLTIP = (
    "Opens a blank document (Assembly1, Assembly2, ...) whose only content is a new "
    "assembly; any open part stays as it is.\n"
    "Adding parts: drag .FCStd files into the window, or use Insert Component."
)
ROTATE_TOOLTIP = (
    "Free spin for one floating component: hold the left button in the 3D view and move "
    "the mouse.\n"
    "Unavailable for fixed or mated components."
)
ROTATE_STATUS_HINT = "Rotate Component  |  left-drag: spin  |  Esc or right-click: exit"

REASON_NO_ASSEMBLY = "Works inside an active assembly: double-click an assembly in the tree first."
REASON_SELECT_ONE = "Select one component of the active assembly, and only one."
REASON_FIXED = '"{component}" is fixed. Float it first if it should turn freely.'
REASON_MATED = (
    '"{component}" is constrained by the mate "{joint}". Free rotation needs a component '
    "without mates."
)

DEGREES_PER_PIXEL = 0.4   # turn per pixel of drag: a full turn takes 900 px
ROTATE_TRANSACTION = "Rotate Component"
WATCH_INTERVAL_MS = 500
RELEASE_GUARD_MS = 2000

CROSS_LINE_WIDTH = 4.0
CROSS_TRANSPARENCY = 0.35
CROSS_MIN_HALF_LENGTH = 5.0
CROSS_SIZE_FACTOR = 0.4
CROSS_DEFAULT_HALF_LENGTH = 20.0
CROSS_PIVOT_FACTOR = 0.08
CROSS_AXES = (  # (direction, RGB color)
    ((1.0, 0.0, 0.0), (0.9, 0.1, 0.1)),
    ((0.0, 1.0, 0.0), (0.1, 0.75, 0.1)),
    ((0.0, 0.0, 1.0), (0.1, 0.3, 0.95)),
)
CROSS_PIVOT_COLOR = (0.85, 0.85, 0.85)

_tool = None
_guard = None


# --- pure helpers ------------------------------------------------------------------


def next_assembly_name(names):
    """First free "AssemblyN" (N = 1, 2, ...) that `names` does not contain."""
    taken = {str(name) for name in (names or ())}
    number = 1
    while "%s%d" % (ASSEMBLY_BASE_NAME, number) in taken:
        number += 1
    return "%s%d" % (ASSEMBLY_BASE_NAME, number)


def drag_rotation(dx, dy):
    """Rotation for a mouse move of (dx, dy) pixels as ((ax, ay, az), degrees).

    Camera coordinates: x to the right, y up. The axis lies in the screen plane at
    right angles to the move. Returns None when the mouse did not move.
    """
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    return ((-dy / length + 0.0, dx / length + 0.0, 0.0), length * DEGREES_PER_PIXEL)


def cross_half_length(diagonal):
    """Half-length in mm of each axis of the cross; `diagonal` may be None when unknown."""
    if diagonal is None or diagonal <= 0:
        return CROSS_DEFAULT_HALF_LENGTH
    return max(CROSS_MIN_HALF_LENGTH, CROSS_SIZE_FACTOR * diagonal)


# --- commands ---------------------------------------------------------------------------


class NewAssemblyCommand(commands.BaseCommand):
    command_id = constants.CMD_NEW_ASSEMBLY
    menu_text = "New Assembly"
    tooltip = NEW_ASSEMBLY_TOOLTIP

    def run(self):
        new_assembly()

    def is_active(self):
        return True


class RotateComponentCommand(commands.BaseCommand):
    command_id = constants.CMD_ROTATE_COMPONENT
    menu_text = "Rotate Component"
    tooltip = ROTATE_TOOLTIP

    def run(self):
        if is_rotating():
            stop_rotate_component()
            return
        assembly, component, reason = rotate_target()
        if reason:
            console.message("Rotate Component: " + reason)
            return
        _start(assembly, component)

    def is_active(self):
        if is_rotating():
            _show_reason(None)
            return True
        _assembly, _component, reason = rotate_target()
        _show_reason(reason)
        return reason is None


def get_commands():
    return {
        constants.CMD_NEW_ASSEMBLY: NewAssemblyCommand(),
        constants.CMD_ROTATE_COMPONENT: RotateComponentCommand(),
    }


# --- New Assembly ---------------------------------------------------------------------


def new_assembly():
    """Open a new AssemblyN document now and add its assembly one event-loop turn later."""
    name = next_assembly_name(_document_names())
    try:
        doc = FreeCAD.newDocument(name)
        if doc.Label != name:
            doc.Label = name
    except Exception as exc:
        console.error("failed to create a document for the new assembly: %s" % exc)
        return
    _make_active_document(doc)
    fcgui.preload_command_modules()
    # Assembly_CreateAssembly needs the 3D view of the new document, which FreeCAD
    # creates only after this call returns.
    fcgui.defer(functools.partial(_create_assembly_in, doc.Name))


def _create_assembly_in(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        console.error(
            "document %s was closed before the assembly could be added to it" % doc_name
        )
        return
    _make_active_document(doc)
    active = FreeCAD.ActiveDocument
    gui_doc = fcgui.active_gui_document()
    if active is None or active.Name != doc_name or gui_doc is None or (
        gui_doc.Document.Name != doc_name
    ):
        console.error(
            "no assembly was created: %s could not be made the active document" % doc_name
        )
        return
    if not fcgui.command_exists(CREATE_ASSEMBLY_COMMAND):
        console.error(
            "no assembly was created: %s is missing because FreeCAD's Assembly module "
            "did not load; the empty document %s is left open"
            % (CREATE_ASSEMBLY_COMMAND, doc_name)
        )
        return
    if not fcgui.run_command(CREATE_ASSEMBLY_COMMAND):
        return
    if not any(doc_utils.is_derived(obj, constants.TYPE_ASSEMBLY) for obj in doc.Objects):
        console.error(
            "%s ran but added no assembly; the empty document %s is left open"
            % (CREATE_ASSEMBLY_COMMAND, doc_name)
        )


def _document_names():
    names = set()
    for key, doc in FreeCAD.listDocuments().items():
        names.add(key)
        for attribute in ("Name", "Label"):
            value = getattr(doc, attribute, "")
            if value:
                names.add(value)
    return names


def _make_active_document(doc):
    with console.guard("switch to the document %s" % doc.Name, level="log"):
        FreeCAD.setActiveDocument(doc.Name)
        FreeCADGui.setActiveDocument(doc.Name)


# --- Rotate Component: availability -------------------------------------------------------


def rotate_target():
    """(assembly, component, reason). A reason of None means the tool can start."""
    assembly = _active_assembly()
    if assembly is None:
        return None, None, REASON_NO_ASSEMBLY
    components = selected_components(assembly)
    if len(components) != 1:
        return assembly, None, REASON_SELECT_ONE
    component = components[0]
    blocker = _rotation_blocker(component)
    if blocker is not None:
        return assembly, None, blocker
    return assembly, component, None


def selected_components(assembly):
    """Components of `assembly` in the selection, each once, in selection order."""
    try:
        import UtilsAssembly
    except Exception:
        return []
    doc_name = _document_name(assembly)
    if doc_name is None:
        return []
    found = {}
    for selection in fcgui.selection_ex("*", 0):
        try:
            root = selection.Object
            subs = [sub for sub in (selection.SubElementNames or ()) if sub]
        except Exception:
            continue
        if not doc_utils.is_alive(root) or _document_name(root) != doc_name:
            continue
        if not subs:
            if _is_tree_component(root, assembly):
                found.setdefault(root.Name, root)
            continue
        for sub in subs:
            component, _relative = UtilsAssembly.getComponentReference(assembly, root, sub)
            if component is not None:
                found.setdefault(component.Name, component)
    return list(found.values())


def _is_tree_component(obj, assembly):
    if not (
        doc_utils.is_derived(obj, constants.TYPE_LINK)
        or doc_utils.is_derived(obj, constants.TYPE_ASSEMBLY_LINK)
    ):
        return False
    return any(_same_object(child, obj) for child in (assembly.Group or []))


def _rotation_blocker(component):
    """Why `component` cannot be turned (fixed or mated), or None."""
    mate = None
    for obj in component.Document.Objects:
        try:
            if hasattr(obj, "ObjectToGround"):
                if _same_object(obj.ObjectToGround, component):
                    return REASON_FIXED.format(component=component.Label)
            elif mate is None and hasattr(obj, "JointType") and _references(obj, component):
                mate = obj
        except Exception:
            continue
    if mate is not None:
        return REASON_MATED.format(component=component.Label, joint=mate.Label)
    return None


def _references(joint, component):
    for prop in ("Reference1", "Reference2"):
        reference = getattr(joint, prop, None)
        if not reference:
            continue
        target = reference[0]
        subs = reference[1] if len(reference) > 1 else ()
        if _same_object(target, component):
            return True
        if isinstance(subs, str):
            subs = (subs,)
        if any(component.Name in str(sub).split(".") for sub in (subs or ())):
            return True
    return False


def _show_reason(reason):
    """Set the ribbon button's tooltip: the base text, plus the reason when one is given."""
    text = ROTATE_TOOLTIP if not reason else "%s\n\n%s" % (ROTATE_TOOLTIP, reason)
    try:
        from jellyjams import ribbon

        button = ribbon.find_button(constants.CMD_ROTATE_COMPONENT)
        if button is not None and fcgui.is_alive(button) and button.toolTip() != text:
            button.setToolTip(text)
    except Exception:
        pass


# --- Rotate Component: running tool ----------------------------------------------------------


def is_rotating():
    return _tool is not None


def stop_rotate_component():
    """Finish Rotate Component if it is running; otherwise do nothing."""
    global _tool
    tool, _tool = _tool, None
    if tool is None:
        return
    tool.ending = True
    with console.guard("record the last rotation as an undo step", level="log"):
        tool.finish_drag()
    tool.stop_watch()
    tool.unhook()
    with console.guard("remove the axis cross", level="log"):
        tool.remove_cross()
    with console.guard("re-enable dragging of assembly parts", level="log"):
        tool.restore_movement()
    fcgui.clear_status()
    _remove_guard_when_idle()


def _start(assembly, component):
    global _tool
    try:
        from pivy import coin
    except Exception as exc:
        console.error("Rotate Component cannot start without Coin (pivy): %s" % exc)
        return
    gui_doc = fcgui.active_gui_document()
    view = getattr(gui_doc, "ActiveView", None) if gui_doc is not None else None
    if view is None or not hasattr(view, "addEventCallbackPivy"):
        console.error("Rotate Component cannot start: no 3D view is active")
        return

    tool = _RotateTool(coin, view, assembly, component)
    try:
        tool.hook()
    except Exception as exc:
        tool.unhook()
        console.error("Rotate Component failed to start: %s" % exc, with_traceback=True)
        return
    _tool = tool
    with console.guard("turn off dragging of assembly parts", level="log"):
        tool.block_movement(assembly)
    with console.guard("draw the axis cross", level="log"):
        tool.show_cross(component)
    _install_guard()
    fcgui.status_message(ROTATE_STATUS_HINT, 0)
    tool.start_watch()
    console.message(
        '"%s" now follows left-button drags in the 3D view; Esc, a right-click or the '
        "Rotate Component button ends the tool" % component.Label
    )


def _request_stop(tool):
    """Schedule the end of `tool` for the next event-loop turn.

    Removing Coin callbacks from inside one of them is not safe, hence the delay.
    """
    if tool is None or tool.ending:
        return
    tool.ending = True
    fcgui.defer(functools.partial(_stop_if_current, tool))


def _stop_if_current(tool):
    if _tool is tool:
        stop_rotate_component()


class _RotateTool:
    """Everything one Rotate Component run needs: view hooks, axis cross, undo state."""

    def __init__(self, coin, view, assembly, component):
        self.coin = coin
        self.view = view
        self.doc_name = component.Document.Name
        self.assembly_name = assembly.Name
        self.component_name = component.Name
        self.parent_placement = _global_placement(assembly)
        self.parent_rotation_inverse = self.parent_placement.Rotation.inverted()
        self.callbacks = []
        self.scene = None
        self.cross_root = None
        self.cross_transform = None
        self.movement_saved = False
        self.movement_value = None
        self.timer = None
        self.left_down = False
        self.last_position = None
        self.in_transaction = False
        self.ending = False

    # objects ---------------------------------------------------------------

    def document(self):
        try:
            return FreeCAD.getDocument(self.doc_name)
        except Exception:
            return None

    def _object(self, name):
        doc = self.document()
        obj = doc.getObject(name) if doc is not None else None
        return obj if obj is not None and doc_utils.is_alive(obj) else None

    def component(self):
        return self._object(self.component_name)

    def assembly(self):
        return self._object(self.assembly_name)

    # Coin event hooks --------------------------------------------------------

    def hook(self):
        coin = self.coin
        for type_id, handler in (
            (coin.SoMouseButtonEvent.getClassTypeId(), self._on_button),
            (coin.SoLocation2Event.getClassTypeId(), self._on_move),
            (coin.SoKeyboardEvent.getClassTypeId(), self._on_key),
        ):
            handle = self.view.addEventCallbackPivy(type_id, handler)
            self.callbacks.append((type_id, handle))

    def unhook(self):
        callbacks, self.callbacks = self.callbacks, []
        for type_id, handle in callbacks:
            try:
                self.view.removeEventCallbackPivy(type_id, handle)
            except Exception:
                pass

    def _on_button(self, event_callback):
        try:
            coin = self.coin
            event = event_callback.getEvent()
            button = event.getButton()
            pressed = event.getState() == coin.SoButtonEvent.DOWN
            if button == coin.SoMouseButtonEvent.BUTTON1:
                event_callback.setHandled()
                if self.ending:
                    return
                if pressed:
                    self.left_down = True
                    self.last_position = event.getPosition().getValue()
                elif self.left_down:
                    self.left_down = False
                    self.finish_drag()
            elif button == coin.SoMouseButtonEvent.BUTTON2:
                event_callback.setHandled()
                if pressed:
                    _request_stop(self)
        except Exception as exc:
            console.log("Rotate Component: error in a mouse button event: %s" % exc)

    def _on_move(self, event_callback):
        try:
            if not self.left_down or self.ending:
                return
            event_callback.setHandled()
            position = event_callback.getEvent().getPosition().getValue()
            last, self.last_position = self.last_position, position
            if last is None:
                return
            rotation = drag_rotation(position[0] - last[0], position[1] - last[1])
            if rotation is not None:
                self.rotate(*rotation)
        except Exception as exc:
            console.log("Rotate Component: error while dragging: %s" % exc)

    def _on_key(self, event_callback):
        try:
            coin = self.coin
            event = event_callback.getEvent()
            if event.getKey() != coin.SoKeyboardEvent.ESCAPE:
                return
            event_callback.setHandled()
            if event.getState() == coin.SoButtonEvent.DOWN:
                _request_stop(self)
        except Exception as exc:
            console.log("Rotate Component: error in a key event: %s" % exc)

    # rotation ------------------------------------------------------------------

    def rotate(self, axis, angle):
        component = self.component()
        if component is None:
            _request_stop(self)
            return
        camera = self.view.getCameraOrientation()
        world_axis = camera.multVec(FreeCAD.Vector(*axis))
        local_axis = self.parent_rotation_inverse.multVec(world_axis)
        if not self.in_transaction:
            component.Document.openTransaction(ROTATE_TRANSACTION)
            self.in_transaction = True
        placement = component.Placement
        turn = FreeCAD.Rotation(local_axis, angle)
        component.Placement = FreeCAD.Placement(placement.Base, turn.multiply(placement.Rotation))
        self.update_cross(component)

    def finish_drag(self):
        """Recompute and commit the undo step of the drag in progress, if any."""
        self.left_down = False
        if not self.in_transaction:
            return
        self.in_transaction = False
        doc = self.document()
        if doc is None:
            return
        try:
            doc.recompute()
        finally:
            doc.commitTransaction()

    # assembly drag movement ----------------------------------------------------------

    def block_movement(self, assembly):
        view_object = assembly.ViewObject
        if view_object is None or "EnableMovement" not in view_object.PropertiesList:
            return
        self.movement_value = view_object.EnableMovement
        self.movement_saved = True
        view_object.EnableMovement = False

    def restore_movement(self):
        if not self.movement_saved:
            return
        self.movement_saved = False
        assembly = self.assembly()
        if assembly is not None and assembly.ViewObject is not None:
            assembly.ViewObject.EnableMovement = self.movement_value

    # axis cross --------------------------------------------------------------------------

    def show_cross(self, component):
        coin = self.coin
        half = cross_half_length(_diagonal(component))
        root = coin.SoAnnotation()
        transform = coin.SoTransform()
        root.addChild(transform)
        for direction, color in CROSS_AXES:
            root.addChild(_axis_node(coin, direction, color, half))
        root.addChild(_pivot_node(coin, half * CROSS_PIVOT_FACTOR))
        scene = self.view.getSceneGraph()
        scene.addChild(root)
        self.scene, self.cross_root, self.cross_transform = scene, root, transform
        self.update_cross(component)

    def update_cross(self, component):
        if self.cross_transform is None:
            return
        try:
            placement = self.parent_placement.multiply(component.Placement)
            base = placement.Base
            self.cross_transform.translation.setValue(base.x, base.y, base.z)
            self.cross_transform.rotation.setValue(*placement.Rotation.Q)
        except Exception as exc:
            console.log("failed to move the axis cross: %s" % exc)

    def remove_cross(self):
        scene, root = self.scene, self.cross_root
        self.scene = self.cross_root = self.cross_transform = None
        if scene is not None and root is not None:
            scene.removeChild(root)

    # watchdog --------------------------------------------------------------------------------

    def start_watch(self):
        timer = QtCore.QTimer()
        timer.setInterval(WATCH_INTERVAL_MS)
        timer.timeout.connect(self._watch)
        timer.start()
        self.timer = timer

    def stop_watch(self):
        timer, self.timer = self.timer, None
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

    def _watch(self):
        try:
            if _tool is not self or self.ending:
                return
            assembly = self.assembly()
            if (
                self.component() is None
                or assembly is None
                or not _same_object(_active_assembly(), assembly)
            ):
                _request_stop(self)
                return
            _keep_status_hint()
        except Exception as exc:
            console.log("Rotate Component: periodic check failed: %s" % exc)


def _axis_node(coin, direction, color, half):
    separator = coin.SoSeparator()
    light = coin.SoLightModel()
    light.model.setValue(coin.SoLightModel.BASE_COLOR)
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(CROSS_LINE_WIDTH)
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.transparency.setValue(CROSS_TRANSPARENCY)
    x, y, z = (half * value for value in direction)
    points = coin.SoCoordinate3()
    points.point.setValues(0, 2, [[-x, -y, -z], [x, y, z]])
    line = coin.SoLineSet()
    line.numVertices.setValue(2)
    for node in (light, style, material, points, line):
        separator.addChild(node)
    return separator


def _pivot_node(coin, radius):
    separator = coin.SoSeparator()
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*CROSS_PIVOT_COLOR)
    material.transparency.setValue(CROSS_TRANSPARENCY)
    sphere = coin.SoSphere()
    sphere.radius.setValue(radius)
    separator.addChild(material)
    separator.addChild(sphere)
    return separator


def _keep_status_hint():
    window = fcgui.main_window()
    if window is not None and not window.statusBar().currentMessage():
        fcgui.status_message(ROTATE_STATUS_HINT, 0)


# --- Esc / right-click guard -----------------------------------------------------------------
#
# FreeCAD's navigation style handles Esc and the right button before any Coin
# callback runs. The press and its release are therefore taken at Qt level;
# otherwise the release opens a context menu or ends assembly edit mode.

_GUARD_TYPES = (
    QtCore.QEvent.Type.MouseButtonPress,
    QtCore.QEvent.Type.MouseButtonDblClick,
    QtCore.QEvent.Type.MouseButtonRelease,
    QtCore.QEvent.Type.ContextMenu,
    QtCore.QEvent.Type.KeyPress,
    QtCore.QEvent.Type.KeyRelease,
)


class _EndGuard(QtCore.QObject):
    """Qt filter: Esc or a right-click in a 3D view ends the tool; the release is eaten too."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.swallow_right = False
        self.swallow_escape = False

    def eventFilter(self, watched, event):
        try:
            kind = event.type()
            if kind not in _GUARD_TYPES or self is not _guard or not _in_3d_view(watched):
                return False
            return self._handle(kind, event)
        except Exception:
            return False

    def _handle(self, kind, event):
        types = QtCore.QEvent.Type
        if kind == types.ContextMenu:
            return _tool is not None or self.swallow_right
        if kind in (types.MouseButtonPress, types.MouseButtonDblClick):
            if event.button() != QtCore.Qt.MouseButton.RightButton or _tool is None:
                return False
            self.swallow_right = True
            _request_stop(_tool)
            return True
        if kind == types.MouseButtonRelease:
            if event.button() != QtCore.Qt.MouseButton.RightButton or not self.swallow_right:
                return False
            self.swallow_right = False
            _remove_guard_when_idle()
            return True
        if event.key() != QtCore.Qt.Key.Key_Escape:
            return False
        if kind == types.KeyPress:
            if _tool is None:
                return False
            if not event.isAutoRepeat():
                self.swallow_escape = True
                _request_stop(_tool)
            return True
        if not self.swallow_escape:
            return False
        if not event.isAutoRepeat():
            self.swallow_escape = False
            _remove_guard_when_idle()
        return True


def _in_3d_view(obj):
    widget = obj if obj is not None and obj.isWidgetType() else None
    while widget is not None:
        if widget.metaObject().className() == constants.CLASS_VIEW3D:
            return True
        widget = widget.parentWidget()
    return False


def _install_guard():
    global _guard
    if _guard is not None:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    guard = _EndGuard(app)
    app.installEventFilter(guard)
    _guard = guard


def _remove_guard_when_idle():
    """Drop the guard after the tool has ended and every swallowed key/button is released."""
    guard = _guard
    if guard is None or _tool is not None:
        return
    if guard.swallow_right or guard.swallow_escape:
        fcgui.defer(_drop_guard, RELEASE_GUARD_MS)
    else:
        fcgui.defer(_drop_guard)


def _drop_guard():
    global _guard
    if _tool is not None:
        return
    guard, _guard = _guard, None
    if guard is None:
        return
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None and fcgui.is_alive(guard):
            app.removeEventFilter(guard)
            guard.deleteLater()
    except Exception:
        pass


# --- shared helpers --------------------------------------------------------------------------------


def _active_assembly():
    try:
        import UtilsAssembly

        return UtilsAssembly.activeAssembly()
    except Exception:
        return None


def _document_name(obj):
    try:
        return obj.Document.Name
    except Exception:
        return None


def _same_object(a, b):
    try:
        return a is not None and b is not None and (
            a.Document.Name == b.Document.Name and a.Name == b.Name
        )
    except Exception:
        return False


def _global_placement(obj):
    for getter in (lambda: obj.getGlobalPlacement(), lambda: obj.Placement):
        try:
            return FreeCAD.Placement(getter())
        except Exception:
            continue
    return FreeCAD.Placement()


def _diagonal(obj):
    try:
        import Part

        box = Part.getShape(obj).BoundBox
        return box.DiagonalLength if box.isValid() else None
    except Exception:
        return None
