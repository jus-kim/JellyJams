# JellyJams specification: Orientation panel and Normal To

> **Implemented in:** [`jellyjams/orientation.py`](../../jellyjams/orientation.py) (commands `JellyJams_ViewOrientation` and `JellyJams_NormalTo`, the panel, the Space filter); [`commands.py`](../../jellyjams/commands.py) (`BaseCommand.cmd_type`, FreeCAD's `CmdType`); [`shortcuts.py`](../../jellyjams/shortcuts.py) (`Space` and `Ctrl+8` in `SHORTCUTS`); [`lifecycle.py`](../../jellyjams/lifecycle.py) (the JellyJams menu entries, the activation step and the deactivation step); [`ribbon_layout.py`](../../jellyjams/ribbon_layout.py) (Normal To on the Evaluate tab); icons [`orientation.svg`](../../resources/icons/orientation.svg), [`normal_to.svg`](../../resources/icons/normal_to.svg), [`view_save.svg`](../../resources/icons/view_save.svg), [`view_restore.svg`](../../resources/icons/view_restore.svg).
>
> **Status:** see [../status.md](../status.md)

Area: **orientation**. Target: FreeCAD 1.1+ (verified facts are for 1.1.4 on Windows).
Product context: JellyJams is a FreeCAD workbench (key and class `JellyJamsWorkbench`, MenuText
`JellyJams`) that makes FreeCAD look, feel and operate like SolidWorks. All user-visible text is
English. Report-view messages written by JellyJams start with the prefix `JellyJams: `.

The words MUST, MUST NOT, SHOULD and MAY are used in their usual normative sense.

---

## 1. Purpose

In SolidWorks, pressing the Spacebar in the graphics area opens the **Orientation** dialog: a
small window at the pointer with the standard views, Normal To and the user's saved views. One
click turns the model; the dialog closes again unless it is pinned. `Ctrl+8` is Normal To: it
looks straight at the selected face, edge, plane or sketch, and in a sketch with nothing
selected it looks straight at the sketch plane.

FreeCAD has every view command this needs, but spread over menus and a toolbar, and Space hides
or shows the selection (`Std_ToggleVisibility`). This area gives JellyJams the Orientation panel
on Space and Normal To on `Ctrl+8`, using only FreeCAD's own view commands, and only while
JellyJams is the active workbench. Both work while a sketch or another task dialog is open.

---

## 2. User-visible behavior and UI

### 2.1 The commands

| Resource | View Orientation | Normal To |
|---|---|---|
| Command id | `JellyJams_ViewOrientation` (`constants.CMD_ORIENTATION`) | `JellyJams_NormalTo` (`constants.CMD_NORMAL_TO`) |
| MenuText | `View Orientation` | `Normal To` |
| ToolTip (intent) | Opens the Orientation panel at the pointer: standard views, Normal To and saved views (Space). | Looks straight at the selected face, edge, plane or sketch; in a sketch with nothing selected, at the sketch plane (Ctrl+8). |
| Pixmap | the original icon `resources/icons/orientation.svg` (`constants.COMMAND_ICONS`) | the original icon `resources/icons/normal_to.svg` |
| Accel | none: the key comes from the shortcut table (2.4), so it is restored exactly on leave | none, for the same reason |
| CmdType | `Alter3DView` | `Alter3DView` |
| Active | while the window in front is a 3D view (below) | the same |
| Where | the **JellyJams** menu (first item) and the `Space` key while JellyJams is active | the **JellyJams** menu (second item), the panel's first tool button, the Evaluate tab's **Normal To** button and `Ctrl+8` while JellyJams is active |

View Orientation has no ribbon button; the standard views are on the Evaluate tab. Normal To is
on the Evaluate tab (group View Orientation, text stack, first entry; objectName
`JellyJamsButton-JellyJams_NormalTo`), where it takes the place of FreeCAD's
`Std_AlignToSelection`, which has no ribbon button ([ribbon-content](ribbon-content.md) 2.5,
Tab 3). The Sketch tab's Normal To stays FreeCAD's `Sketcher_ViewSketch`.

**Availability in sketches and task dialogs.** FreeCAD treats a Python command that declares no
`CmdType` as one that changes the document, the 3D view and the selection, and disables it
whenever the open task dialog does not allow document changes; every default task dialog does
that, the sketch editor's included ([freecad-facts](../freecad-facts.md)). Both commands only
move the camera, so they declare `CmdType` `Alter3DView` (`BaseCommand.cmd_type`, emitted by
`GetResources` only when set) and stay available while a sketch or any other task dialog is open
([decisions.md](../decisions.md) D-18).

**Active state.** Both commands are active while the window in front is a 3D view
(`orientation.view3d_active`): the view `orientation._active_view()` returns is not None and has
`getCameraNode`. That view is the main window's active window,
`FreeCADGui.getMainWindow().getActiveWindow()` (FreeCAD's `MainWindow::activeWindow`), the
window FreeCAD's own view commands act on. It follows a 3D view docked in the MDI area,
undocked into a window of its own, fullscreen or split, and stays so while another top-level
window (the panel itself, for example) has the keyboard. The MDI area is not asked: an undocked
or fullscreen 3D view is no longer in it ([freecad-facts](../freecad-facts.md)). With the Start
page, a drawing sheet or a spreadsheet in front, or no window at all, both commands are inactive
and their keys do nothing. `FreeCADGui.activeView()` does not decide this: it keeps returning
the document's last 3D view while the Start page or a drawing is in front. Only when the main
window has no `getActiveWindow` (an older FreeCAD) is `FreeCADGui.activeView()` used instead.
When the lookup raises, both commands are inactive.

Running View Orientation **toggles** the panel: it opens it at the pointer when it is closed and
closes it when it is open. Running Normal To runs the command of 2.6.

### 2.2 The panel

- A frameless tool window (`Qt::Tool` with `Qt::FramelessWindowHint`) whose parent is FreeCAD's
  main window, Qt objectName **`JellyJamsOrientation`**. It floats above FreeCAD's main window.
- It is built the first time it opens and reused for the rest of the session. If its widget has
  been deleted meanwhile, it is built again on the next open.
- **Colors:** it carries its own stylesheet with palette colors ([look](look.md)), and every state
  names both its text color and its background:

  | Element | Text | Background |
  |---|---|---|
  | Panel | | `PANEL`, with a 1 px `BORDER` frame |
  | Title and labels | `TEXT` | transparent |
  | Tool buttons | `TEXT` | transparent |
  | Tool buttons, hover | `TEXT` | `HOVER`, `BORDER` frame |
  | Tool buttons, pressed or checked (Pin) | `TEXT` | `PRESSED`, `BORDER` frame |
  | Tool buttons, keyboard focus | | `ACCENT` frame |
  | Tool buttons, disabled | `TEXT_DISABLED` | transparent |

  The panel follows the native light/dark widget palette from [look](look.md).
  Its own stylesheet supplies readable foreground/background pairs in either mode
  and is refreshed whenever the panel opens. FreeCAD's widgets are not styled.
- **Placement:** its top-left corner is 12 px right of and 12 px below the pointer
  (`CURSOR_OFFSET_PX`). If the panel would leave the available area of the screen under the
  pointer (the primary screen when no screen is under it), it is moved back inside, so the whole
  panel is always visible.

From top to bottom:

1. **Header:** the title `Orientation` on the left; on the right a checkable **Pin** button
   (tooltip "Keep this panel open after choosing a view or clicking elsewhere") and a close
   button `✕` (tooltip "Close (Esc)"). Pin is unchecked when FreeCAD starts and then keeps its
   state for the rest of the session, also when the panel is closed and opened again.
2. **Tools row**, left to right:

   | Button | Command | Tooltip label |
   |---|---|---|
   | Normal To | `JellyJams_NormalTo` (2.6) | Normal To |
   | Remember this view | `Std_ViewSaveCamera` | Remember this view |
   | Go back to the remembered view | `Std_ViewRestoreCamera` | Go back to the remembered view |
   | Zoom to Fit | `Std_ViewFitAll` | Zoom to Fit |

3. A thin horizontal rule.
4. **Standard views** as an unfolded box around Front (grid row, column), with a column of
   axonometric views to its right:

   |   | column 0 | column 1 | column 2 | column 3 |   | axonometric |
   |---|---|---|---|---|---|---|
   | **row 0** | | Top `Std_ViewTop` | | | | Isometric `Std_ViewIsometric` |
   | **row 1** | Left `Std_ViewLeft` | Front `Std_ViewFront` | Right `Std_ViewRight` | Back `Std_ViewRear` | | Trimetric `Std_ViewTrimetric` |
   | **row 2** | | Bottom `Std_ViewBottom` | | | | Dimetric `Std_ViewDimetric` |

   The six other grid cells stay empty.

**View buttons** (all 13 above):

- 30 × 30 px, icon 24 px, no text; objectName `JellyJamsOrientation_<command id>` (for example
  `JellyJamsOrientation_Std_ViewTop`, `JellyJamsOrientation_JellyJams_NormalTo`).
- Icon: the command's icon, found at runtime like a ribbon button's
  ([ribbon-engine](ribbon-engine.md) 2.7): `normal_to.svg` for Normal To, FreeCAD's own icon for
  the others. FreeCAD 1.1 ships no icon for `Std_ViewSaveCamera` and `Std_ViewRestoreCamera`; for
  those two only, and only when FreeCAD gives no icon, the original icons `view_save.svg` and
  `view_restore.svg` are used (`orientation.FALLBACK_ICONS`).
- Tooltip: the label of the tables above, followed by ` (<keys>)` when the command currently has a
  keyboard shortcut (for example `Top (Ctrl+5)`, `Normal To (Ctrl+8)`).
- **Enabled state**, set again every time the panel opens: a button is enabled when FreeCAD has
  the command and `FreeCADGui.Command.get(<id>).isActive()` is true; a check that raises counts
  as active. Normal To is enabled whenever the command exists, so that it can say what is
  missing (2.3). A disabled button keeps its place in the layout.

### 2.3 Behavior

- **Click on a view button:** unless the panel is pinned, the panel closes first; then the
  command runs (`FreeCADGui.runCommand(<id>)`), so the view changes exactly as when the command is
  chosen from FreeCAD's View menu. With Pin checked the panel stays open and several views can be
  tried in a row.
- **The Normal To button** behaves like every other view button: unless the panel is pinned, the
  panel closes first; then `JellyJams_NormalTo` runs (2.6). With nothing to look at (nothing
  selected outside a sketch, two or more picks, a whole body or feature) Normal To shows its
  hint next to the pointer and in the status bar, with the unpinned panel already gone and the
  keyboard back where it was; the user selects one face, edge, plane or sketch and presses
  `Ctrl+8` or opens the panel again.
- **Close button**, **Esc** and **Space** (while the panel has the keyboard focus) close the panel
  without running a view command. Other keys leave it open. Repeated key presses of a held Esc or
  Space are ignored, so the Space that opened the panel cannot close it again by repeating.
- **Space on a focused button inside the panel** (reached with Tab) clicks that button instead of
  closing the panel, wherever the pointer is. The panel applies the rules of 2.4 to its own
  buttons without the pointer rule (rule 1): it opens beside the pointer, which usually stays
  over the 3D view, so with that rule Space could never reach a panel button.
- **Click outside:** when another window becomes active (FreeCAD's main window, a dialog or
  another program), an unpinned panel closes itself one event-loop turn later. A pinned panel
  stays open. In detail:
  - Every opening starts a new **generation** (`_generation`), stamps the opening time
    (`_opened_at`, `time.monotonic()`) and forgets that the panel had the keyboard
    (`_seen_active`).
  - The panel watches its own activation (`changeEvent`, `ActivationChange`). Becoming active
    notes that it has had the keyboard since this opening. Losing the keyboard while it is open
    schedules a check for the current generation one event-loop turn later
    (`_close_if_left(generation)`).
  - The check does nothing when the generation is no longer the one it was scheduled for (a
    check left over from an earlier opening never closes a newer one), when the panel is closed,
    when it has not had the keyboard since this opening (nothing was clicked away from), or when
    it is the active window again.
  - Otherwise it first remembers the FreeCAD window that took the keyboard
    (`QApplication.activeWindow()`, when there is one) as the window to hand the keyboard back to
    (`_return_to`), so a pinned panel that stays open across window switches returns the keyboard
    to the window the user was last in. A pinned panel then stays open.
  - Within `OPEN_SETTLE_S` (0.3 s) of opening, with a FreeCAD window active, the deactivation is
    the opening settling (a menu or a pop-up closing right after Space, for example), not a click
    elsewhere: the panel stays open and takes the keyboard back (`activateWindow()`), so Esc
    still closes it and the next click elsewhere is noticed and closes it. With no FreeCAD window
    active (another program took the keyboard) the panel closes instead, without pulling FreeCAD
    to the front.
  - Later than that, the check closes the panel.
  - A check that fails writes a log-level message and closes nothing.
- **Where the keyboard goes on closing.** When the panel opens it remembers the window that had
  the keyboard (`QApplication.activeWindow()`, kept in `_return_to`; never the panel itself, which
  is remembered as none), and the click-outside check updates it whenever another FreeCAD window
  takes the keyboard from the open panel. Closing gives the keyboard back only when the panel had it at that
  moment: to that window if it still exists and is visible, otherwise to FreeCAD's main window.
  An undocked or fullscreen 3D view therefore keeps the keyboard and stays in front, and the next
  Space reaches it again; closing after a click into another program does not bring FreeCAD to
  the front.
- Pressing Space again in FreeCAD while the panel is open closes it (the command toggles).
- The panel keeps no state besides the Pin button: nothing is written to parameters or
  documents. The remembered view belongs to FreeCAD (`Std_ViewSaveCamera`), not to JellyJams.

### 2.4 Keyboard

These entries of the SolidWorks shortcut table ([core](core.md) A5 and 4.8) belong to this area:

| Key | Command | Note |
|---|---|---|
| `Space` | `JellyJams_ViewOrientation` | FreeCAD 1.1 gives Space to `Std_ToggleVisibility` (Hide/Show). That command is unbound while JellyJams is active and gets Space back on leave, on quit and after a crash, through the same exact restore as every other clashing command ([decisions.md](../decisions.md) D-06). If the user has moved Hide/Show to another key, it is not touched. |
| `Ctrl+8` | `JellyJams_NormalTo` | Normal To (2.6). FreeCAD's `Std_AlignToSelection` keeps its own key; if the user had given it `Ctrl+8`, it is unbound while JellyJams is active and gets the key back exactly, like any clashing command. |

FreeCAD creates a command's `QAction`, and with it a working shortcut, only for commands that
are placed in a menu or toolbar; a ribbon button does not create one. Both commands are therefore
listed in the JellyJams menu ([core](core.md) 4.2). If a command does not exist (for example
because its registration failed), its key is not set and Hide/Show keeps Space.

**Who gets Space.** Space is a window-wide shortcut, so Qt would open the panel even while a
focused control wants the key. Between activation step A6 and deactivation step D12
([core](core.md) 4.4, 4.5) an event filter watches the shortcut override Qt sends before it runs
a shortcut. For a plain Space (no modifier) it asks `orientation.keeps_space(focus, pointer)`,
with `focus` the widget with the keyboard focus (`QApplication.focusWidget()`) and `pointer` the
widget under the mouse pointer (`QApplication.widgetAt(QCursor.pos())`). When that is true it
accepts the override and the focused widget gets the key; otherwise Space opens the panel. The
rules, in this order:

1. **Pointer over the model.** With the pointer over a 3D view (Qt class `Gui::View3DInventor`),
   a 3D viewer (`Gui::View3DInventorViewer`, the parent of the OpenGL drawing area in every 3D
   view: docked, undocked, fullscreen or split), a split 3D view (`Gui::AbstractSplitView`:
   FreeCAD's `SplitView3DInventor` declares no Qt class of its own) or FreeCAD's model tree
   (`Gui::TreeWidget`), or over any widget inside one of them (its parents are searched, at most
   40 levels), Space is **always** for the panel, whatever has the keyboard
   (`SPACE_FOR_PANEL_CLASSES`, in that order). A check box clicked a moment ago keeps the
   keyboard focus; without this rule a Space pressed while the user looks at the model would flip
   that check box unnoticed.
2. **Toolbars, status bar, ribbon.** A focused control inside a `QToolBar`, the `QStatusBar` or
   the ribbon dock (objectName `JellyJamsCommandManager`, `constants.OBJ_RIBBON`) never keeps
   Space. FreeCAD's workbench selector (`Gui::WorkbenchComboBox`) and the status bar's buttons
   keep the focus after a click; Space there would open the workbench list or the button's menu.
3. **Buttons and combo boxes** keep Space: every `QAbstractButton` (push, tool, check and radio
   buttons), which Space clicks or toggles, and every `QComboBox`, which Space opens.
4. **Item views** (`QAbstractItemView`: lists, trees, tables) keep Space only when Space does
   something in them: the current item can be checked by the user (`ItemIsUserCheckable`), or the
   view starts editing on any key (its edit triggers include `AnyKeyPressed`, as a table's do by
   default). A plain list, FreeCAD's property editor and a tree whose items are neither checkable
   nor typed into give Space to the panel. FreeCAD's model tree never keeps it. If the view
   cannot say what its current item is, it does not keep Space.
5. Every other widget lets Space open the panel. Line edits, spin boxes and text editors accept
   the override themselves (Qt gives typed text precedence over shortcuts), so Space types a
   space there without the filter, wherever the pointer is.

Space with a modifier and every other key pass the filter untouched. The panel applies the same
rules to its own buttons, without rule 1: a focused panel button keeps Space wherever the pointer
is (`_hand_space_to_focus(event, use_pointer=False)` in the panel's `event()`, 2.3).

**Where the filter sits.** One filter object (a child of the main window) is installed at
activation on FreeCAD's main window **and on every `QDockWidget` the main window holds at that
moment** (the list is kept in `orientation._filtered`). A dock that floats is a window of its
own, and Qt passes key events only up to the widget's window, so the shortcut overrides of a
floating task panel never reach the main window ([freecad-facts](../freecad-facts.md)). Deleted
docks are skipped. There is exactly one filter, however often JellyJams is activated; it is never
installed on the application, so it sees only the events of those windows that their widgets pass
up unhandled ([decisions.md](../decisions.md) D-18).

**Docks made later.** While JellyJams is active, `orientation._focus_changed(old, new)` is
connected to `QApplication.focusChanged`. When a widget takes the keyboard focus, its parents are
searched (at most 40 levels) for the nearest `QDockWidget`; if there is one and it is not in
`_filtered` yet, the filter is installed on it and it is added, once. A dock created after
activation (by another add-on, or a floating dock opened later) is thus covered as soon as one
of its controls can receive Space. Focus on any other widget (the main window's own widgets, a
dialog, another top-level window) adds nothing, and so does a focus change after `uninstall()`.

**Key repeat.** FreeCAD's actions repeat a held shortcut. The View Orientation action's repeat is
switched off on activation (A6) and again every time the command runs, so a held Space opens the
panel once instead of making it flicker. Before FreeCAD has made the action there is nothing to
switch off. The action belongs to JellyJams' own command, so it is left that way on leave.

### 2.5 Lifecycle

- **Entering JellyJams:** the shortcuts area binds `Space` and `Ctrl+8` (A5); then the Space
  filter is installed on the main window and its docks, `QApplication.focusChanged` is connected
  for docks made later, and key repeat is switched off (A6). The panel is built on its first use.
- **Leaving JellyJams:** deactivation step D12, after tree naming is paused and before the ribbon
  is hidden ([core](core.md) 4.5), closes the panel, disconnects `focusChanged`, and removes the
  Space filter from every widget it was installed on that still exists (docks added later
  included), then deletes it. Then the shortcuts are restored (D14): Space belongs to Hide/Show
  again and neither JellyJams command has a key.
- **Quit:** nothing to do for the panel or the filter: the panel is a tool window, not a dock or
  toolbar, so it is not part of the window state FreeCAD saves, and the filter lives in memory
  only. The shortcuts are restored by the quit guard like all others ([core](core.md) 6.6).
- **Crash:** the shortcut backup `OriginalShortcuts` restores Space and `Ctrl+8` at the next
  start ([core](core.md) 7). The panel and the filter have no persistent state.
- `close()` and `uninstall()` are safe at any time, also when the panel was never opened or the
  filter never installed. `install()` is safe to repeat.

### 2.6 Normal To

`orientation.normal_to_target()` decides from the selection (`Selection.getSelectionEx()`) and
the object in edit. It returns `("command", <id>)` (run that FreeCAD command), `("sketch",
<object>)` (look straight at that whole sketch, below) or None (nothing to look at).

**Sketch rule.** While a sketch is open for editing and nothing is selected, or only the sketch's
own elements are (its edges and vertices, or the sketch itself: same document name and object
name), Normal To runs `Sketcher_ViewSketch`, the view of the sketch plane.

**One-pick rule.** Otherwise exactly **one** pick is needed. The picks are counted over the
selection items: an item with sub-elements counts once per non-empty sub-element name (two faces
of one box are two picks), an item without sub-elements (or with only empty names) counts once.
They are counted twice, on the resolved selection and on the selection as picked
(`getSelectionEx("", 0)`), and both must not hold more than one: the same sketch picked under two
link instances is one entry once resolved but two places on screen, so it is two picks.
With one pick:

| The pick | Result |
|---|---|
| **Any sub-element**: a face (flat or curved), an edge (straight, circular, B-spline, ...), a vertex | `Std_AlignToSelection`: FreeCAD decides whether and how it aligns. It handles curved faces (a cylinder's side), straight B-spline edges and planar curves too ([freecad-facts](../freecad-facts.md)). The sub-element's shape is not read. |
| A whole object derived from `Part::Part2DObject` (a sketch or another 2D object; `SKETCH_TYPES`) | the **sketch** itself: `("sketch", <object>)`, looked at along its plane (below) |
| A whole object derived from `App::Plane` (an origin plane), `App::Line` (an origin axis) or `Part::Datum` (a datum plane, line or point) (`DATUM_TYPES`) | `Std_AlignToSelection`: FreeCAD aligns to these itself, also when they are reached through a link |
| Any other whole object whose `Shape` is not null, holds no solid, and is exactly one face, or has no face and exactly one edge (a Part plane, a circle, a single-face binder) | `Std_AlignToSelection` |
| Any other whole object: a body, a feature, a part, a box, a sphere (one face, but a solid), a shell of several faces, a wire of several edges, an origin point, an object without a shape or whose type or shape cannot be read | none |

With two or more picks (two faces, a face and an edge, a sketch and a face, two sketches, two
planes) or nothing selected outside a sketch, also while another object (for example a Pad) is
in edit, there is nothing to look at. These rules apply in a sketch too, when the selection holds
anything besides the sketch's own elements: one face of another object (flat or curved) runs
`Std_AlignToSelection`, a whole other sketch is looked at along its plane, and the sketch's own
edge together with another face is two picks.

**Looking at a sketch.** For a whole sketch or other 2D object, `normal_to()` turns the view in
front itself (`orientation._look_at_sketch`): `_active_view().setCameraOrientation(q)`, with
`_active_view()` the main window's active window (2.1). The rotation `q` comes from
`_sketch_rotation(obj)`, which follows the path the sketch was picked through:

- It reads the selection as picked, not resolved: `Selection.getSelectionEx("", 0)` gives each
  pick as its top-level object and the path below it (a sketch picked below a link in the tree
  is `Link` with the path `Sketch.`).
- When that holds exactly one item with at most one non-empty path, the rotation is
  `FreeCAD.GeoFeature.getGlobalPlacementOf(obj, <item's object>, <path or "">).Rotation`: the
  placements along that path, links and assembly components included.
- Otherwise (nothing, several items, several paths), or when that call raises (a log-level
  message `Normal To used the sketch's own placement: <reason>`), the rotation is
  `obj.getGlobalPlacement().Rotation`. That includes every body or part the sketch sits in, but
  no link.

A sketch in a body turned 30° about Z, shown through an `App::Link` turned 90° about X (a link's
placement replaces the linked body's), is therefore looked at as the link shows it (Q (0.707, 0,
0, 0.707)), not along the body's own 30°. `normal_to()` returns True; when there is no view in
front, the sketch has no placement or the view refuses, it writes a Report-view warning
`Normal To could not turn the view to <label>: <reason>` and returns False (no hint: there was
something to look at). `Std_AlignToSelection` is not used for whole sketches, because it usually
does nothing for them ([freecad-facts](../freecad-facts.md)).

**Nothing to look at.** `normal_to()` runs no command, shows
`Normal To: select one face, edge, plane or sketch first.` (`NORMAL_TO_HINT`) in FreeCAD's status
bar for 4 s (`HINT_MS`) at once and as a tool tip at the pointer 150 ms later
(`TOOLTIP_DELAY_MS`; `QToolTip.showText(QCursor.pos(), ...)`; a tool tip that cannot be shown
changes nothing else), and returns False. The tool tip waits because Qt hides any tool tip when a
window gains or loses the keyboard, and the panel's Normal To button hands the keyboard back as
it closes. FreeCAD's
`Std_AlignToSelection` alone would do nothing at all, and say nothing, with an empty selection or
with two picks, and it has no sketch rule. The panel's Normal To button closes an unpinned panel
before it runs (2.3), so the hint appears with the panel gone.

FreeCAD's `Std_AlignToSelection` itself is not changed: it keeps its own key. It has no ribbon
button: the Evaluate tab's Normal To is `JellyJams_NormalTo` (2.1).

---

## 3. FreeCAD state read or changed

- **Commands run:** `JellyJams_NormalTo` (its panel button), `Sketcher_ViewSketch` and
  `Std_AlignToSelection` (through Normal To), `Std_ViewSaveCamera`, `Std_ViewRestoreCamera`,
  `Std_ViewFitAll`, `Std_ViewTop`, `Std_ViewLeft`, `Std_ViewFront`, `Std_ViewRight`,
  `Std_ViewRear`, `Std_ViewBottom`, `Std_ViewIsometric`, `Std_ViewTrimetric`, `Std_ViewDimetric`
  (through `FreeCADGui.runCommand`).
- **Camera changed directly:** `setCameraOrientation(q)` on the main window's active window
  (`orientation._active_view()`) when Normal To looks at a whole sketch or 2D object (2.6).
- **Keyboard:** `activateWindow()` on the panel when it opens and when it loses the keyboard
  within the settle time, and on closing (only when the panel had the keyboard) on the window
  that had it before (`_return_to`) or on the main window (2.3).
- **Read:** `FreeCADGui.listCommands()` and `FreeCADGui.Command.get(id).isActive()` (button
  state), `FreeCADGui.Command.get(id).getShortcut()` (tooltips),
  `FreeCADGui.Command.get(id).getAction()` (key repeat), the commands' icons (2.2),
  `FreeCADGui.getMainWindow().getActiveWindow()` (`FreeCADGui.activeView()` only without it) and
  whether it has `getCameraNode` (active state), `FreeCADGui.Selection.getSelectionEx()`
  (`DocumentName`, `ObjectName`, `SubElementNames`, `Object` with `isDerivedFrom`, `Shape`
  (`isNull()`, `Solids`, `Faces`, `Edges`) and `Label`), `Selection.getSelectionEx("", 0)`
  (`Object`, `SubElementNames`), `FreeCAD.GeoFeature.getGlobalPlacementOf(...)` and
  `getGlobalPlacement()` (their `Rotation.Q`), and `FreeCADGui.ActiveDocument.getInEdit()`
  (Normal To), `QApplication.focusWidget()`, `QApplication.widgetAt(QCursor.pos())`, each
  widget's Qt class name, object name and parents, and an item view's current index flags and
  edit triggers (Space filter), the main window's `QDockWidget` children and the newly focused
  widget's parents (`QApplication.focusChanged`; where the filter sits),
  `QApplication.activeWindow()` when the panel opens and when it loses the keyboard, the pointer
  position and the screen geometry.
- **Status bar and tool tip:** the Normal To hint, in the status bar for 4 s and as a tool tip at
  the pointer.
- **Report view:** a warning when Normal To cannot turn the view to a whole sketch (2.6);
  log-level messages when the sketch's own placement is used instead of the selection path, and
  for errors while closing, filtering, adding a dock made later or switching off key repeat.
- **Parameters:** written only by the shortcuts area: `Preferences/Shortcut`
  `JellyJams_ViewOrientation` = `Space`, `JellyJams_NormalTo` = `Ctrl+8`, and an empty
  `Std_ToggleVisibility` while it clashes, all recorded in `OriginalShortcuts` first and restored
  exactly.
- **Qt objects:** the panel `JellyJamsOrientation` (a child of the main window) and its buttons
  `JellyJamsOrientation_<command id>`; the Space filter (a child of the main window, installed as
  the event filter of the main window and of each of its docks between A6 and D12, docks made
  later included); the connection of `QApplication.focusChanged` to `_focus_changed` (A6 to
  D12); the `autoRepeat` flag of View Orientation's `QAction`.
- **Documents:** nothing is read or written.

---

## 4. SolidWorks features that are not available

| SolidWorks | In JellyJams |
|---|---|
| Viewport layouts: Single View, Two View (horizontal / vertical), Four View | Not offered. FreeCAD 1.1 has no command that splits one 3D view into several viewports. FreeCAD's own "Create new view" (`Std_ViewCreate`) and "Tile" (`Std_TileWindows`) give separate 3D view windows instead; JellyJams does not change them. |
| View Selector (the orientation cube shown in the graphics area from the dialog) | Not offered. FreeCAD's own navigation cube in the 3D view stays available and unchanged. |
| New View (named custom views) and Update Standard Views | Not offered. The panel has FreeCAD's Remember / Go back pair (`Std_ViewSaveCamera` / `Std_ViewRestoreCamera`) instead. |
| Link Views | Not offered. |

---

## 5. Edge cases

| Situation | Required handling |
|---|---|
| The window in front is no 3D view (no document, the Start page, a drawing sheet or a spreadsheet), or the lookup raises | Both commands are inactive; Space and `Ctrl+8` do nothing, also while `FreeCADGui.activeView()` still returns the document's last 3D view. |
| The 3D view is undocked, fullscreen or split | Both commands stay active: the main window's active window follows the 3D view, though the MDI area no longer shows it. |
| The main window has no `getActiveWindow` (an older FreeCAD) | `FreeCADGui.activeView()` decides instead. |
| A sketch or another task dialog is open | Both commands stay available (`CmdType` `Alter3DView`). |
| Normal To with nothing selected outside a sketch | No command runs; the hint shows in the status bar for 4 s and as a tool tip at the pointer. |
| Normal To with two picks (two faces, a face and an edge, a sketch and a face, two planes) | Nothing to look at: the hint, no command (FreeCAD's Align to selection would do nothing). |
| Normal To with one curved face, one circular or B-spline edge, or one vertex | `Std_AlignToSelection` runs: FreeCAD decides (it aligns to a cylinder's side, for example). |
| Normal To with a whole body, feature, box or other solid selected | Nothing to look at: the hint. |
| Normal To with a whole sketch selected | The view in front turns along the sketch's placement on the path it was picked through (through a link too); no FreeCAD command runs. |
| Normal To with a whole sketch whose unresolved selection has several items or paths, or whose path cannot be followed | The view turns along the sketch's own global placement (a log-level message when following the path failed). |
| Normal To with a whole origin plane or axis, or a datum plane, line or point selected | `Std_AlignToSelection` runs: FreeCAD aligns to it, through links too. |
| Normal To with a whole object that is one face or one edge (a Part plane, a circle) | `Std_AlignToSelection` runs. |
| Normal To on a whole sketch while the view cannot be turned (no view in front, no placement, an error) | Report-view warning; no hint; returns False. |
| Normal To with a sub-element whose shape cannot be read | `Std_AlignToSelection` runs: the shape is never read. |
| Normal To in a sketch with another object's face selected | `Std_AlignToSelection` (the face wins over the sketch plane). |
| Normal To in a sketch with its own edge and another face selected | Two picks: the hint. |
| The panel's Normal To button with nothing to look at | The unpinned panel closes first; then the hint shows. A pinned panel stays open. |
| The hint's tool tip cannot be shown | The status-bar hint still shows; nothing else changes. |
| Space while a button, check box or combo box has the keyboard focus and the pointer is over a task panel, a dialog or any other place outside the 3D view and the model tree | That control gets Space; the panel does not open. |
| Space while a check box clicked a moment ago still has the focus, with the pointer over the 3D view or the model tree | The panel opens; the check box is not changed. |
| Space while a plain list, the property editor or a tree without checkable items has the focus | The panel opens. |
| Space while a list whose current item is checkable, or a table that edits on typing, has the focus (pointer outside the 3D view and the model tree) | That view gets Space. |
| Space after a click on the workbench selector, a toolbar button, a status-bar button or a ribbon button (they keep the focus) | The panel opens; the control does not get Space. |
| Space in a floating task panel with a focused check box | The check box gets Space: the floating dock has the filter too. |
| A dock is created after JellyJams was activated (docked or floating) | It gets the Space filter the first time one of its widgets takes the focus, once; its focused controls then keep Space like those of any other dock. |
| Focus moves to a widget outside every dock (the main window, a dialog, another window) | No filter is added. |
| Focus changes after JellyJams was left | Nothing is added: the focus watch is disconnected. |
| Space with the pointer over a split 3D view or over the drawing area of any 3D view (docked, undocked, fullscreen) | The panel opens, whatever has the focus. |
| Space on a panel button reached with Tab, the pointer still over the 3D view beside the panel | The button gets Space: the view is applied. |
| Space while the model tree, the 3D view or an empty part of a task panel has the focus | The panel opens. |
| A deactivation of the panel within 0.3 s of opening it (a menu closing, for example) | Not a click elsewhere: the panel stays open and takes the keyboard back, so Esc closes it and a later click elsewhere closes it. |
| The panel closes after it was opened from an undocked or fullscreen 3D view | The keyboard goes back to that view, which stays in front; if it has been closed or hidden meanwhile, to the main window. |
| The panel closes after the user clicked into another program | The keyboard is not taken back; that program stays in front. |
| A check for an earlier opening runs after the panel was opened again | It does nothing; only the check of the current opening can close the panel. |
| The panel never had the keyboard since it opened | Losing it does not close the panel. |
| Space held down | The panel opens once; repeated presses neither re-run the command nor close the panel. |
| A view command is missing in this FreeCAD build | Its button is disabled; the others work. |
| FreeCAD reports a view command as inactive | Its button is disabled until the panel opens again while the command is active. |
| FreeCAD has no icon for a view command | The button has no icon, except for the two cameras (fallback icons). |
| Pointer at a screen edge or corner | The panel is moved inside the screen's available area. |
| The user clicks another window (the panel is unpinned / pinned) | The panel closes / stays open. |
| The panel's widget was deleted | It is built again on the next open. |
| The user leaves JellyJams with the panel open (pinned or not) | The panel closes and the Space filter is removed (2.5). |
| JellyJams is activated again without leaving | Still one Space filter. |
| `close()` or `uninstall()` is called before the panel ever opened | Nothing happens; nothing is printed. |
| An error while closing, filtering, adding a dock made later or switching off key repeat | Log-level message only; nothing is raised. |
| Hide/Show was moved to another key by the user | It keeps that key; only Space is taken. |

---

## 6. Acceptance criteria

Unless stated otherwise: FreeCAD 1.1.x with a throwaway configuration, JellyJams active, a
document with one `Part::Box`, the 3D view focused. `tests/gui_orientation.py` checks the
criteria marked **G**; `Test24Orientation`, `Test12NavigationShortcuts`, `Test05Commands`,
`Test06Lifecycle` and `Test13RibbonModel` / `Test13RibbonBuild` (the Evaluate tab's Normal To)
check the logic headlessly (see [../status.md](../status.md)).

1. **G** While JellyJams is active, `Gui.Command.get("JellyJams_ViewOrientation").getShortcut()`
   is `Space` and `Gui.Command.get("JellyJams_NormalTo").getShortcut()` is `Ctrl+8`;
   `Std_AlignToSelection` keeps the key it had before.
2. **G** While JellyJams is active, `Std_ToggleVisibility` has no shortcut (it had `Space`
   before, in a profile without user overrides).
3. **G** Pressing Space in the 3D view opens a visible top-level widget with objectName
   `JellyJamsOrientation` near the pointer.
4. **G** The panel holds exactly 13 buttons whose objectNames start with `JellyJamsOrientation_`,
   one per command of 2.2, Normal To first.
5. The standard views sit in the grid positions of 2.2 (Top above Front, Bottom below, Left,
   Right and Back to its right in one row) and Isometric, Trimetric, Dimetric in one column.
6. **G** With the panel unpinned, clicking Top sets the view direction to (0, 0, −1) and closes
   the panel.
7. **G** With Pin checked, clicking Front applies the front view and the panel stays open.
8. **G** Esc closes the panel. Space while the panel has the keyboard focus closes it too; the
   close button closes it; none of these runs a view command.
9. Running `JellyJams_ViewOrientation` while the panel is open closes it.
10. Both commands are inactive with no document open, with the Start page in front and with a
    drawing sheet in front, and active in a 3D view, also while a sketch is being edited and
    while another task dialog (for example a Pad's) is open: `Space` opens the panel and `Ctrl+8`
    works there. They stay active with the 3D view undocked or fullscreen (criterion 31).
11. The Remember and Go back buttons show the JellyJams icons when FreeCAD has none for
    `Std_ViewSaveCamera` / `Std_ViewRestoreCamera`; Normal To shows `normal_to.svg`; every other
    button shows FreeCAD's icon.
12. Tooltips name the view and its current key, for example `Top (Ctrl+5)` and
    `Normal To (Ctrl+8)`.
13. A view command missing from FreeCAD gives a disabled button; clicking it does nothing. A
    command FreeCAD reports as inactive is disabled when the panel opens; Normal To is enabled
    whenever it exists.
14. With the pointer in a screen corner, the whole panel is on screen.
15. **G** With the panel open, switching to Part Design closes it.
16. **G** After leaving JellyJams, `Std_ToggleVisibility` has its key from before again and
    `JellyJams_ViewOrientation` has no key; `JellyJams_NormalTo` has none either.
17. After a quit with JellyJams active, the saved `user.cfg` holds no `Preferences/Shortcut`
    entry for `JellyJams_ViewOrientation`, `JellyJams_NormalTo`, `Std_AlignToSelection` or
    `Std_ToggleVisibility` (`tests/check_saved_cfg.py`, `no_jj_shortcut_overrides`).
18. After a crash with JellyJams active, the next start restores Space to Hide/Show and removes
    the `Ctrl+8` and View Orientation keys ([core](core.md) AC 27).
19. The JellyJams menu lists **View Orientation**, **Normal To** and **Diagnostics**, in that
    order, while JellyJams is active.
20. With a user who moved Hide/Show to `H`, entering and leaving JellyJams leaves `H` on Hide/Show.
21. After leaving JellyJams, `Preferences/Shortcut` holds no entry for `JellyJams_ViewOrientation`,
    `JellyJams_NormalTo` or `Std_ToggleVisibility` unless the user had one before (then it has the
    user's value again), and `Std_AlignToSelection` has the user's value or none.
22. With one flat face of the box selected, `Ctrl+8` turns the view to look straight at it
    (`Std_AlignToSelection`); the same with one straight edge selected. Every single face, edge
    or vertex goes to `Std_AlignToSelection`.
23. In a sketch with nothing selected, `Ctrl+8` turns the view to look straight at the sketch plane
    (`Sketcher_ViewSketch`); the same with only edges of that sketch selected. With one face of
    another object selected in the sketch, it runs `Std_AlignToSelection` for that face.
24. **G** With nothing selected outside a sketch, `Ctrl+8` changes nothing, the status bar shows
    `Normal To: select one face, edge, plane or sketch first.` for about 4 s, and the same text
    appears as a tool tip at the pointer. The panel's Normal To button closes the unpinned panel
    first and then shows the same hint; a pinned panel stays open.
25. In a task panel, with a check box focused and the pointer over the task panel, Space toggles
    the check box and the panel does not open; the same holds for a focused push button or combo
    box, and for a list whose current item is checkable. With the pointer over the model tree,
    Space opens the panel whatever has the focus. `Shift+Space` and other keys are not affected.
26. After leaving JellyJams, neither FreeCAD's main window nor any of its docks has a JellyJams
    event filter left: a focused check box in a dock gets Space as in plain FreeCAD.
27. Holding Space in the 3D view opens the panel once; it does not flicker, and the held key does
    not close it again.
28. With the panel unpinned, clicking another window (FreeCAD's main window or another program)
    more than 0.3 s after it opened closes it; with Pin checked it stays open. After a click into
    another program, that program stays in front.
29. With FreeCAD Dark or a dark system palette, the panel's title and buttons show
    light text on a dark panel in every state (normal, hover, checked, disabled).
    With FreeCAD Light, they show dark text on a light panel. The active palette
    supplies every state explicitly; reopening refreshes its light/dark choice.
30. **G** Tab to a view button in the panel and press Space, with the pointer still over the 3D
    view beside the panel: that view is applied and the unpinned panel closes. The same with the
    pointer over the panel.
31. **G** Undock the 3D view: both commands stay enabled, Space with the pointer over the undocked
    view opens the panel, and `Ctrl+8` works there. Docked again, the same holds. A fullscreen 3D
    view behaves the same way. (A split view made with `FreeCADGui.createViewer` is not a 3D view
    for these commands: its window has no `getCameraNode`, and FreeCAD's own view commands are
    inactive there too.)
32. **G** With two flat faces selected, `Ctrl+8` changes nothing and the status bar shows the hint
    of 24.
33. **G** With a whole sketch selected in the tree and no sketch open, `Ctrl+8` turns the view to
    look straight at the sketch plane without running a FreeCAD command; with an origin plane (for
    example XZ) selected, `Std_AlignToSelection` runs and the view looks straight at that plane.
34. **G** With a Pad's task dialog open, click its "Reversed" check box, move the pointer over the
    3D view and press Space: the panel opens and "Reversed" is unchanged. With the pointer over
    the task panel, Space toggles "Reversed".
35. **G** Float the Tasks dock, focus a check box in it and, with the pointer over it, press Space:
    the check box toggles and the panel does not open.
36. **G** Choose a workbench in the workbench selector (it keeps the focus) and press Space with
    the pointer over the 3D view: the panel opens and the selector's list does not.
37. **G** The Evaluate tab's Normal To button (`JellyJamsButton-JellyJams_NormalTo`) runs
    `JellyJams_NormalTo`: with one flat face selected the view turns to it. The ribbon has no
    button for `Std_AlignToSelection`.
38. **G** When the panel loses the keyboard within 0.3 s of opening (a menu closing right after
    Space, for example), it stays open and takes the keyboard back; a click elsewhere after that
    closes it.
39. With a face and an edge, or a whole body selected, `Ctrl+8` changes nothing and shows
    the hint of 24. With one curved face (the side of a cylinder), a whole datum line or a whole
    origin axis selected, it runs `Std_AlignToSelection` and the view ends where FreeCAD's own
    Align to Selection puts it. With a datum plane selected, or a sketch in a body that was moved,
    it looks straight at that plane.
40. Space after a click on a status-bar button or on a ribbon button opens the panel; the button
    does not get Space. With the property editor or a plain list focused, Space opens the panel
    too.
41. Opening the panel again before the check of an earlier click elsewhere has run never lets
    that check close the new panel; a panel that never had the keyboard since it opened is not
    closed by losing it.
42. With a whole sketch selected and a 3D view that refuses the new orientation (an error from
    `setCameraOrientation`), `Ctrl+8` writes one Report-view warning naming the object and shows
    no hint.
43. **G** With the Start page in front and a document's 3D view behind it, both commands are
    inactive and Space does nothing, although `FreeCADGui.activeView()` still returns that 3D
    view: availability follows the main window's active window.
44. **G** Select a sketch through an `App::Link` (the link turned 90° about X, the linked body
    turned 30° about Z) and press `Ctrl+8`: the view looks straight at the sketch as the link
    shows it (camera orientation Q (0.707, 0, 0, 0.707)), not along the sketch's own global
    placement.
45. With a whole object selected whose shape is one face (a Part plane) or one edge (a Part
    circle), `Ctrl+8` runs `Std_AlignToSelection`; with a whole solid of one face (a sphere) it
    shows the hint.
46. **G** A floating dock created after JellyJams was activated gets the Space filter once one of
    its widgets has the focus: a focused check box in it, with the pointer over it, toggles with
    Space and the panel does not open.
47. **G** Undock the 3D view, open the panel there with Space and close it with Esc, or with a
    click on Top: the undocked view has the keyboard again and stays in front, not the main
    window.
48. **G** Click the panel's Normal To button with nothing selected: the unpinned panel closes,
    the view does not change, and the status bar shows the hint of 24.
49. **G** In the case of 48 the hint also appears as a tool tip at the pointer once the panel has
    closed, and it is still showing 300 ms later.
50. With the same sketch picked under two link instances (two places on screen, one object once
    resolved), `Ctrl+8` changes nothing and shows the hint of 24.
51. With the panel pinned, click into another FreeCAD window (an undocked 3D view, for example),
    then on a view button of the panel, then press Esc: the keyboard goes to the window clicked
    into, not to the window that was active when the panel opened. When another program takes the
    keyboard within 0.3 s of opening, the unpinned panel closes and FreeCAD is not brought to the
    front.
