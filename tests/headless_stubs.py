# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Stub FreeCAD environment for the JellyJams headless test harness.

Call install() before anything from the jellyjams package is imported. It

* selects Qt's offscreen platform and creates the QApplication,
* puts the repository first on sys.path,
* provides the PySide package: FreeCAD's own shim from <FreeCAD>/Ext when it is
  installed next to the running interpreter, otherwise aliases to PySide6,
* registers in-memory FreeCAD and FreeCADGui modules in sys.modules.

The returned Stubs object records what the code under test did (console output,
commands run, observers, ...) and offers reset helpers for every test.
"""

import atexit
import os
import shutil
import sys
import tempfile
import time
import types

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The interpreter's own FreeCAD install (bin/python.exe -> <FreeCAD>); the PySide
# shim must come from there so that it matches the interpreter's PySide6.
INTERPRETER_FREECAD_DIR = os.path.normpath(os.path.join(os.path.dirname(sys.executable), os.pardir))
DEFAULT_FREECAD_DIR = os.path.normpath("C:/Program Files/FreeCAD 1.1")
FREECAD_DIR = next(
    (path for path in (INTERPRETER_FREECAD_DIR, DEFAULT_FREECAD_DIR)
     if os.path.isdir(os.path.join(path, "data", "Mod", "TechDraw", "Templates"))),
    INTERPRETER_FREECAD_DIR,
)
FREECAD_VERSION = ["1", "1", "4", "20260928 (Git shallow)"]
DEFAULT_WORKBENCH = "PartDesignWorkbench"

# GetContents() order and type names of FreeCAD 1.1 (ParameterGrpPy::getContents).
_PARAM_TYPES = (
    ("String", "String"),
    ("Int", "Integer"),
    ("Float", "Float"),
    ("Bool", "Boolean"),
    ("Unsigned", "Unsigned Long"),
)
_DEFAULTS = {"String": "", "Int": 0, "Float": 0.0, "Bool": False, "Unsigned": 0}

_STUBS = None
# Stubs.active_window when the main window's active window is the active view (the usual case)
FOLLOW_ACTIVE_VIEW = object()


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


def _coerce(suffix, value):
    """Mirror the argument checks of FreeCAD's ParameterGrp setters."""
    if suffix == "String":
        if not isinstance(value, str):
            raise TypeError("SetString() argument 2 must be str, not %s" % type(value).__name__)
        return value
    if suffix == "Float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("SetFloat() argument 2 must be float")
        return float(value)
    if not isinstance(value, int):
        raise TypeError("Set%s() argument 2 must be int, not %s" % (suffix, type(value).__name__))
    if suffix == "Bool":
        return bool(value)
    if suffix == "Unsigned":
        return int(value) & 0xFFFFFFFF
    return int(value)


class ParamGroup:
    """In-memory stand-in for FreeCAD's ParameterGrp."""

    def __init__(self, registry, path):
        self._registry = registry
        self._path = path
        self._values = {suffix: {} for suffix, _name in _PARAM_TYPES}
        self._children = {}

    def __repr__(self):
        return "<ParamGroup %s>" % self._path

    def _clear(self):
        for values in self._values.values():
            values.clear()
        self._children.clear()
        for name in [key for key in self.__dict__ if not key.startswith("_")]:
            del self.__dict__[name]

    def _get(self, suffix, name, default):
        if not isinstance(name, str):
            raise TypeError("parameter name must be str")
        values = self._values[suffix]
        if name in values:
            return values[name]
        return _DEFAULTS[suffix] if default is None else default

    def _set(self, suffix, name, value):
        if not isinstance(name, str):
            raise TypeError("parameter name must be str")
        self._values[suffix][name] = _coerce(suffix, value)

    def _rem(self, suffix, name):
        self._values[suffix].pop(name, None)

    def _names(self, suffix, filter_text=None):
        names = list(self._values[suffix])
        if filter_text:
            names = [name for name in names if filter_text in name]
        return names

    # typed access -----------------------------------------------------------
    def GetBool(self, name, default=None):
        return self._get("Bool", name, default)

    def SetBool(self, name, value):
        self._set("Bool", name, value)

    def RemBool(self, name):
        self._rem("Bool", name)

    def GetBools(self, filter_text=None):
        return self._names("Bool", filter_text)

    def GetInt(self, name, default=None):
        return self._get("Int", name, default)

    def SetInt(self, name, value):
        self._set("Int", name, value)

    def RemInt(self, name):
        self._rem("Int", name)

    def GetInts(self, filter_text=None):
        return self._names("Int", filter_text)

    def GetUnsigned(self, name, default=None):
        return self._get("Unsigned", name, default)

    def SetUnsigned(self, name, value):
        self._set("Unsigned", name, value)

    def RemUnsigned(self, name):
        self._rem("Unsigned", name)

    def GetUnsigneds(self, filter_text=None):
        return self._names("Unsigned", filter_text)

    def GetFloat(self, name, default=None):
        return self._get("Float", name, default)

    def SetFloat(self, name, value):
        self._set("Float", name, value)

    def RemFloat(self, name):
        self._rem("Float", name)

    def GetFloats(self, filter_text=None):
        return self._names("Float", filter_text)

    def GetString(self, name, default=None):
        return self._get("String", name, default)

    def SetString(self, name, value):
        self._set("String", name, value)

    def RemString(self, name):
        self._rem("String", name)

    def GetStrings(self, filter_text=None):
        return self._names("String", filter_text)

    def GetContents(self):
        # FreeCAD returns None (not an empty list) for an empty group.
        if self.IsEmpty():
            return None
        contents = []
        for suffix, type_name in _PARAM_TYPES:
            for name, value in self._values[suffix].items():
                contents.append((type_name, name, value))
        return contents

    # groups -------------------------------------------------------------------
    def GetGroup(self, name):
        if not isinstance(name, str) or not name:
            raise ValueError("invalid group name")
        child = self._children.get(name)
        if child is None:
            path = self._path.rstrip("/") + "/" + name if not self._path.endswith(":") else self._path + name
            child = self._registry.setdefault(path, ParamGroup(self._registry, path))
            self._children[name] = child
        return child

    def HasGroup(self, name):
        return name in self._children

    def RemGroup(self, name):
        child = self._children.pop(name, None)
        if child is not None:
            child._clear()

    def GetGroups(self):
        return list(self._children)

    def GetGroupName(self):
        return self._path.rsplit("/", 1)[-1].rsplit(":", 1)[-1]

    def IsEmpty(self):
        return not self._children and not any(self._values.values())

    def Clear(self):
        for values in self._values.values():
            values.clear()
        self._children.clear()

    def Attach(self, _observer):
        pass

    def Detach(self, _observer):
        pass

    def Notify(self, _name):
        pass


class ParamTree:
    def __init__(self):
        self.registry = {}

    def get(self, path):
        if not isinstance(path, str) or ":" not in path:
            raise ValueError("ParamGet: invalid path %r" % (path,))
        root_name, rest = path.split(":", 1)
        root_key = root_name + ":"
        node = self.registry.setdefault(root_key, ParamGroup(self.registry, root_key))
        for part in rest.split("/"):
            if part:
                node = node.GetGroup(part)
        return node

    def reset(self):
        for group in self.registry.values():
            group._clear()


# --------------------------------------------------------------------------
# Small FreeCAD types
# --------------------------------------------------------------------------


class Vector:
    """Minimal FreeCAD.Vector."""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, Vector):
            x, y, z = x.x, x.y, x.z
        elif isinstance(x, (tuple, list)):
            x, y, z = (list(x) + [0.0, 0.0, 0.0])[:3]
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __getitem__(self, index):
        return (self.x, self.y, self.z)[index]

    def __len__(self):
        return 3

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, factor):
        if isinstance(factor, Vector):
            return self.dot(factor)
        return Vector(self.x * factor, self.y * factor, self.z * factor)

    __rmul__ = __mul__

    def __neg__(self):
        return Vector(-self.x, -self.y, -self.z)

    def __eq__(self, other):
        try:
            return all(abs(a - b) < 1e-7 for a, b in zip(self, other)) and len(other) == 3
        except TypeError:
            return NotImplemented

    def __hash__(self):
        return hash((round(self.x, 7), round(self.y, 7), round(self.z, 7)))

    def __repr__(self):
        return "Vector (%s, %s, %s)" % (self.x, self.y, self.z)

    @property
    def Length(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        return Vector(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def normalize(self):
        length = self.Length
        if length == 0:
            raise ValueError("Cannot normalize null vector")
        self.x, self.y, self.z = self.x / length, self.y / length, self.z / length
        return self


class _Console:
    def __init__(self, stubs):
        self._stubs = stubs

    def PrintMessage(self, text):
        self._stubs._record("message", text)

    def PrintWarning(self, text):
        self._stubs._record("warning", text)

    def PrintError(self, text):
        self._stubs._record("error", text)

    def PrintLog(self, text):
        self._stubs._record("log", text)

    def PrintCritical(self, text):
        self._stubs._record("error", text)

    def PrintNotification(self, text):
        self._stubs._record("message", text)

    def PrintDeveloperWarning(self, text):
        self._stubs._record("warning", text)

    def PrintDeveloperError(self, text):
        self._stubs._record("error", text)


# --------------------------------------------------------------------------
# FreeCADGui pieces
# --------------------------------------------------------------------------


class Workbench:
    """Stand-in for FreeCADGui.Workbench (the Python base class)."""

    MenuText = ""
    ToolTip = ""
    Icon = ""

    def __init__(self):
        self.__dict__.setdefault("_menus", [])
        self.__dict__.setdefault("_toolbars", [])

    def _ensure(self):
        self.__dict__.setdefault("_menus", [])
        self.__dict__.setdefault("_toolbars", [])

    def Initialize(self):
        pass

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def ContextMenu(self, _recipient):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def appendMenu(self, name, commands):
        self._ensure()
        self._menus.append((name, list(commands)))

    def removeMenu(self, name):
        self._ensure()
        self._menus = [entry for entry in self._menus if entry[0] != name]

    def appendToolbar(self, name, commands):
        self._ensure()
        self._toolbars.append((name, list(commands)))

    def removeToolbar(self, name):
        self._ensure()
        self._toolbars = [entry for entry in self._toolbars if entry[0] != name]

    def appendContextMenu(self, name, commands):
        pass

    def appendCommandbar(self, name, commands):
        pass

    def reloadActive(self):
        pass

    def name(self):
        return type(self).__name__


class _ActiveWorkbench:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def __repr__(self):
        return "<ActiveWorkbench %s>" % self._name


class StubCommand:
    """What FreeCADGui.Command.get(id) returns."""

    def __init__(self, stubs, cmd_id):
        self._stubs = stubs
        self._id = cmd_id

    def _python(self):
        return self._stubs.registered.get(self._id)

    def getInfo(self):
        python = self._python()
        if python is not None:
            resources = python.GetResources() or {}
            return {
                "name": self._id,
                "menuText": resources.get("MenuText", ""),
                "toolTip": resources.get("ToolTip", ""),
                "whatsThis": resources.get("WhatsThis", ""),
                "statusTip": resources.get("StatusTip", ""),
                "pixmap": resources.get("Pixmap", ""),
                "shortcut": resources.get("Accel", ""),
            }
        info = {
            "name": self._id,
            "menuText": self._id.split("_", 1)[-1],
            "toolTip": "",
            "whatsThis": "",
            "statusTip": "",
            "pixmap": "",
            "shortcut": "",
        }
        info.update(self._stubs.command_info.get(self._id, {}))
        return info

    def getAction(self):
        return list(self._stubs.command_actions.get(self._id, ()))

    def isActive(self):
        python = self._python()
        if python is not None and hasattr(python, "IsActive"):
            return bool(python.IsActive())
        state = self._stubs.command_active.get(self._id, True)
        if isinstance(state, BaseException):
            raise state
        return bool(state)

    def getShortcut(self):
        override = self._stubs.params.get("User parameter:BaseApp/Preferences/Shortcut")
        if self._id in override.GetStrings():
            return override.GetString(self._id)
        return self._stubs.command_shortcuts.get(self._id, "")

    def setShortcut(self, keys):
        self._stubs.command_shortcuts[self._id] = keys
        return True

    def resetShortcut(self):
        return True

    def run(self, index=0):
        self._stubs.gui.runCommand(self._id, index)


# --------------------------------------------------------------------------
# The harness object
# --------------------------------------------------------------------------


class Stubs:
    """Handle on the stub environment; one instance per process."""

    def __init__(self, qt_core, qt_gui, qt_widgets):
        self.repo = REPO_DIR
        self.freecad_dir = FREECAD_DIR
        self.QtCore, self.QtGui, self.QtWidgets = qt_core, qt_gui, qt_widgets
        self.params = ParamTree()
        self.user_dir = tempfile.mkdtemp(prefix="jj_headless_user_")
        atexit.register(shutil.rmtree, self.user_dir, True)
        # FreeCAD returns both directories with native separators and a trailing one.
        data_dir = os.path.join(FREECAD_DIR, "data")
        if os.path.isdir(os.path.join(data_dir, "Mod", "TechDraw", "Templates")):
            self.resource_dir = data_dir + os.sep
        else:
            self.resource_dir = tempfile.mkdtemp(prefix="jj_headless_res_") + os.sep
            atexit.register(shutil.rmtree, self.resource_dir, True)
        self.echo = bool(os.environ.get("JELLYJAMS_ECHO_CONSOLE"))
        self.records = []
        self.run_calls = []
        self.run_errors = {}
        self.registered = {}
        self.duplicate_commands = []
        self.available = []
        self.command_info = {}
        self.command_active = {}
        self.command_shortcuts = {}
        self.command_actions = {}
        self.workbenches = {}
        self.active_workbench = DEFAULT_WORKBENCH
        self.doc_observers = []
        self.selection = []
        self.selection_ex = []
        self.unresolved_selection_ex = None   # None: getSelectionEx("", 0) gives selection_ex
        self.selection_observers = []
        self.selection_calls = []
        self.placement_calls = []
        self.active_dialog = None
        self.active_view = None
        self.active_window = FOLLOW_ACTIVE_VIEW
        self.view_messages = []
        self.closed_windows = []
        self._old_windows = []
        self.qapp = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["jellyjams-headless"])
        self.app = self._make_app_module()
        self.gui = self._make_gui_module()
        self.app.Gui = self.gui
        self.main_window = None
        self.new_main_window()

    # recording ---------------------------------------------------------------
    def _record(self, level, text):
        text = text if isinstance(text, str) else str(text)
        self.records.append((level, text))
        if self.echo:
            sys.__stderr__.write("[%s] %s" % (level, text if text.endswith("\n") else text + "\n"))

    def console_lines(self, level=None):
        """Texts printed through FreeCAD.Console, optionally only one level
        ('message', 'warning', 'error', 'log')."""
        return [text for lvl, text in self.records if level is None or lvl == level]

    # module factories ----------------------------------------------------------
    def _make_app_module(self):
        stubs = self
        app = types.ModuleType("FreeCAD")
        app.__doc__ = "JellyJams headless stub of the FreeCAD module"
        app.GuiUp = 1
        app.Console = _Console(self)
        app.Vector = Vector
        app.ActiveDocument = None

        def ParamGet(path):
            return stubs.params.get(path)

        def Version():
            return list(FREECAD_VERSION)

        def getUserAppDataDir():
            return stubs.user_dir + os.sep

        def getResourceDir():
            return stubs.resource_dir

        def getHomePath():
            return FREECAD_DIR + os.sep

        def addDocumentObserver(observer):
            stubs.doc_observers.append(observer)

        def removeDocumentObserver(observer):
            if observer in stubs.doc_observers:
                stubs.doc_observers.remove(observer)

        def listDocuments():
            return {}

        def getDocument(name):
            raise NameError("Unknown document '%s'" % name)

        def activeDocument():
            return app.ActiveDocument

        def saveParameter(*_args):
            pass

        for function in (ParamGet, Version, getUserAppDataDir, getResourceDir, getHomePath,
                         addDocumentObserver, removeDocumentObserver, listDocuments,
                         getDocument, activeDocument, saveParameter):
            setattr(app, function.__name__, function)

        def getGlobalPlacementOf(target, root, subname):
            # FreeCAD multiplies the placements along the path from `root`; without a link on
            # the path that is the target's own global placement.
            stubs.placement_calls.append((target, root, subname))
            return target.getGlobalPlacement()

        app.GeoFeature = types.SimpleNamespace(getGlobalPlacementOf=getGlobalPlacementOf)
        return app

    def _make_gui_module(self):
        stubs = self
        gui = types.ModuleType("FreeCADGui")
        gui.__doc__ = "JellyJams headless stub of the FreeCADGui module"
        gui.Workbench = Workbench
        gui.ActiveDocument = None

        def addWorkbench(workbench):
            name = type(workbench).__name__
            if name in stubs.workbenches:
                raise KeyError("'%s' already exists." % name)
            stubs.workbenches[name] = workbench

        def listWorkbenches():
            return dict(stubs.workbenches)

        def getWorkbench(name):
            if name not in stubs.workbenches:
                raise KeyError("No such workbench '%s'" % name)
            return stubs.workbenches[name]

        def activeWorkbench():
            return _ActiveWorkbench(stubs.active_workbench)

        def activateWorkbench(name):
            stubs.active_workbench = name
            return True

        def addCommand(cmd_id, command, *_args):
            if cmd_id in stubs.registered:
                stubs.duplicate_commands.append(cmd_id)
                return
            stubs.registered[cmd_id] = command

        def listCommands():
            ids = list(stubs.available)
            ids.extend(cmd for cmd in stubs.registered if cmd not in stubs.available)
            return ids

        def runCommand(cmd_id, index=None):
            stubs.run_calls.append((cmd_id, index))
            error = stubs.run_errors.get(cmd_id)
            if error is not None:
                raise error

        def getMainWindow():
            return stubs.main_window

        def getIcon(_name):
            return stubs.QtGui.QIcon()

        def SendMsgToActiveView(message, *_args):
            stubs.view_messages.append(message)
            return False

        def activeView():
            # FreeCAD's active MDI view: None, a 3D view (it has getCameraNode) or any other view.
            view = stubs.active_view
            if isinstance(view, BaseException):
                raise view
            return view

        def activeDocument():
            return gui.ActiveDocument

        def getDocument(name):
            raise NameError("Unknown document '%s'" % name)

        def setActiveDocument(_doc):
            pass

        def updateGui():
            stubs.qapp.processEvents()

        def _noop(*_args, **_kwargs):
            return None

        for function in (addWorkbench, listWorkbenches, getWorkbench, activeWorkbench,
                         activateWorkbench, addCommand, listCommands, runCommand,
                         getMainWindow, getIcon, SendMsgToActiveView, activeView,
                         activeDocument, getDocument, setActiveDocument, updateGui):
            setattr(gui, function.__name__, function)
        for name in ("addIconPath", "addLanguagePath", "addPreferencePage", "doCommand",
                     "doCommandGui", "addModule"):
            setattr(gui, name, _noop)

        class _CommandApi:
            @staticmethod
            def get(cmd_id):
                if cmd_id in stubs.registered or cmd_id in stubs.available:
                    return StubCommand(stubs, cmd_id)
                return None

            @staticmethod
            def listAll():
                return listCommands()

        gui.Command = _CommandApi

        def getSelection(*args):
            stubs.selection_calls.append(("getSelection", args))
            return list(stubs.selection)

        def getSelectionEx(*args, **kwargs):
            # getSelectionEx(docName="", resolve=1, single=False); with resolve 0 FreeCAD gives
            # each pick as its top-level object and the path below it.
            stubs.selection_calls.append(("getSelectionEx", args))
            resolve = args[1] if len(args) > 1 else kwargs.get("resolve", 1)
            if not resolve and stubs.unresolved_selection_ex is not None:
                return list(stubs.unresolved_selection_ex)
            return list(stubs.selection_ex)

        def addObserver(observer, *_args):
            stubs.selection_observers.append(observer)

        def removeObserver(observer):
            if observer in stubs.selection_observers:
                stubs.selection_observers.remove(observer)

        def clearSelection(*_args):
            stubs.selection_calls.append(("clearSelection", _args))
            stubs.selection.clear()
            stubs.selection_ex.clear()
            stubs.unresolved_selection_ex = None

        def addSelection(*args):
            stubs.selection_calls.append(("addSelection", args))
            if args and not isinstance(args[0], str):
                stubs.selection.append(args[0])

        gui.Selection = types.SimpleNamespace(
            getSelection=getSelection, getSelectionEx=getSelectionEx,
            addObserver=addObserver, removeObserver=removeObserver,
            clearSelection=clearSelection, addSelection=addSelection,
        )

        def activeDialog():
            return stubs.active_dialog

        def showDialog(dialog):
            stubs.active_dialog = dialog
            return dialog

        def closeDialog():
            stubs.active_dialog = None

        gui.Control = types.SimpleNamespace(
            activeDialog=activeDialog, showDialog=showDialog, closeDialog=closeDialog,
        )
        return gui

    # main window ------------------------------------------------------------------
    def new_main_window(self, visible=True, cls=None):
        """Create a fresh offscreen main window and make it FreeCAD's main window.
        Earlier windows are hidden but kept alive, so references held by the code
        under test never point to deleted C++ objects."""
        QtWidgets, QtCore = self.QtWidgets, self.QtCore
        if self.main_window is not None:
            self.main_window.hide()
            self._old_windows.append(self.main_window)
        window = (cls or make_main_window_class(QtWidgets))()
        window._stubs = self
        window.setObjectName("JellyJamsHeadlessMainWindow")
        window.setWindowTitle("JellyJams headless")
        mdi = QtWidgets.QMdiArea(window)
        mdi.setObjectName("JellyJamsHeadlessMdiArea")
        window.setCentralWidget(mdi)
        window.statusBar()
        window.resize(1280, 800)
        if visible:
            window.show()
        self.main_window = window
        self.qapp.processEvents()
        return window

    def set_main_window(self, window):
        if self.main_window is not None and self.main_window is not window:
            self.main_window.hide()
            self._old_windows.append(self.main_window)
        self.main_window = window
        return window

    # state helpers -------------------------------------------------------------------
    def reset(self, visible=True):
        """Fresh state for one test: parameters, console, recorded calls, active
        workbench, command lists, selection, dialogs and a new main window."""
        self.params.reset()
        self.records.clear()
        self.run_calls.clear()
        self.run_errors.clear()
        self.registered.clear()
        self.duplicate_commands.clear()
        self.available.clear()
        self.command_info.clear()
        self.command_active.clear()
        self.command_shortcuts.clear()
        self.command_actions.clear()
        self.workbenches.clear()
        self.active_workbench = DEFAULT_WORKBENCH
        self.doc_observers.clear()
        self.selection.clear()
        self.selection_ex.clear()
        self.unresolved_selection_ex = None
        self.selection_observers.clear()
        self.selection_calls.clear()
        self.placement_calls.clear()
        self.active_dialog = None
        self.active_view = None
        self.active_window = FOLLOW_ACTIVE_VIEW
        self.view_messages.clear()
        self.closed_windows.clear()
        self.app.ActiveDocument = None
        self.gui.ActiveDocument = None
        self.new_main_window(visible=visible)

    def set_active_workbench(self, name):
        self.active_workbench = name

    def set_commands(self, ids, info=None, shortcuts=None):
        """Replace the list of FreeCAD commands that exist (besides registered
        Python commands). info: {id: getInfo() overrides}; shortcuts: {id: keys}."""
        self.available[:] = list(dict.fromkeys(ids))
        if info:
            self.command_info.update(info)
        if shortcuts:
            self.command_shortcuts.update(shortcuts)

    def set_command_active(self, cmd_id, state):
        """state: bool, or an exception instance that isActive() raises."""
        self.command_active[cmd_id] = state

    def set_command_actions(self, cmd_id, actions):
        """The QActions Command.get(cmd_id).getAction() returns (FreeCAD makes them only for
        commands placed in a menu or toolbar; the stub has none unless given here)."""
        self.command_actions[cmd_id] = list(actions)

    def set_active_dialog(self, value):
        self.active_dialog = value

    def set_active_view(self, view):
        """What FreeCADGui.activeView() returns: None, a view object, or an exception it raises.
        The main window's getActiveWindow() returns the same, unless set_active_window() says
        otherwise."""
        self.active_view = view

    def set_active_window(self, window=FOLLOW_ACTIVE_VIEW):
        """What the main window's getActiveWindow() returns: the MDI view in front (None, a view
        object, or an exception it raises). Without an argument it follows the active view again."""
        self.active_window = window

    # event loop helpers ---------------------------------------------------------------------
    def pump(self, ms=0):
        """Process Qt events (timers included) for about `ms` milliseconds."""
        flags = self.QtCore.QEventLoop.ProcessEventsFlag.AllEvents
        end = time.monotonic() + ms / 1000.0
        while True:
            self.qapp.processEvents(flags, 20)
            if time.monotonic() >= end:
                break
            time.sleep(0.005)

    def wait_until(self, predicate, timeout_ms=2000, step_ms=10):
        end = time.monotonic() + timeout_ms / 1000.0
        while True:
            if predicate():
                return True
            if time.monotonic() >= end:
                return bool(predicate())
            self.pump(step_ms)


def make_main_window_class(QtWidgets):
    """QMainWindow whose close can be accepted (Save/Discard) or refused (Cancel), with the
    getActiveWindow() that FreeCAD 1.1 adds to its main window."""

    class StubMainWindow(QtWidgets.QMainWindow):
        accept_close = True

        def getActiveWindow(self):
            # MainWindow::activeWindow: the MDI view in front, docked, undocked or fullscreen.
            stubs = getattr(self, "_stubs", None)
            if stubs is None:
                return None
            window = stubs.active_window
            if window is FOLLOW_ACTIVE_VIEW:
                window = stubs.active_view
            if isinstance(window, BaseException):
                raise window
            return window

        def closeEvent(self, event):
            stubs = getattr(self, "_stubs", None)
            if stubs is not None:
                stubs.closed_windows.append(self)
            if self.accept_close:
                event.accept()
            else:
                event.ignore()

    return StubMainWindow


# --------------------------------------------------------------------------
# install
# --------------------------------------------------------------------------


def _install_pyside():
    ext_dir = os.path.join(INTERPRETER_FREECAD_DIR, "Ext")
    if os.path.isdir(os.path.join(ext_dir, "PySide")):
        if ext_dir not in sys.path:
            sys.path.insert(1, ext_dir)
        import PySide.QtCore  # noqa: F401  (FreeCAD's shim)
        import PySide.QtGui  # noqa: F401
        import PySide.QtWidgets  # noqa: F401
        import PySide.QtSvg  # noqa: F401
        return "FreeCAD PySide shim"
    import PySide6
    from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

    package = types.ModuleType("PySide")
    package.__path__ = []
    package.__version__ = PySide6.__version__
    package.__version_info__ = PySide6.__version_info__
    for name, module in (("QtCore", QtCore), ("QtGui", QtGui), ("QtWidgets", QtWidgets), ("QtSvg", QtSvg)):
        setattr(package, name, module)
        sys.modules["PySide." + name] = module
    sys.modules["PySide"] = package
    return "PySide6 aliases"


def install():
    """Install the stub environment once per process and return the Stubs."""
    global _STUBS
    if _STUBS is not None:
        return _STUBS
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # The 26.3 Windows bundle locates plugins relative to FreeCAD.exe, but
    # python.exe reports bin/lib/qt6/plugins. Supply the installed directory.
    plugins = os.path.join(INTERPRETER_FREECAD_DIR, "lib", "qt6", "plugins")
    if os.path.isdir(plugins):
        os.environ.setdefault("QT_PLUGIN_PATH", plugins)
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", os.path.join(plugins, "platforms"))
    if REPO_DIR in sys.path:
        sys.path.remove(REPO_DIR)
    sys.path.insert(0, REPO_DIR)
    for name in list(sys.modules):
        if name == "jellyjams" or name.startswith("jellyjams."):
            raise RuntimeError("headless_stubs.install() must run before jellyjams is imported")
    pyside_source = _install_pyside()
    from PySide import QtCore, QtGui, QtWidgets

    stubs = Stubs(QtCore, QtGui, QtWidgets)
    stubs.pyside_source = pyside_source
    sys.modules["FreeCAD"] = stubs.app
    sys.modules["FreeCADGui"] = stubs.gui
    _STUBS = stubs
    return stubs
