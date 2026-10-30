# JellyJams specification: Window layout

> **Implemented in:** [`jellyjams/layout.py`](../../jellyjams/layout.py) (apply, revert, autoload deferral, re-dock passes); [`quit_guard.py`](../../jellyjams/quit_guard.py) (Close-event guard and Cancel re-apply); [`lifecycle.py`](../../jellyjams/lifecycle.py) (step order on enter, leave and quit).
>
> **Status:** see [../status.md](../status.md)

Area: **window-layout**
Target: FreeCAD 1.1+ (verified facts below come from FreeCAD 1.1.4 on Windows, Qt 6.8 / PySide6).
Product context: JellyJams is a FreeCAD workbench (key and class `JellyJamsWorkbench`, menu text "JellyJams") that makes FreeCAD look, feel and operate like SolidWorks. English only.

This document states requirements. It does not prescribe a code structure.

---

## 1. Purpose

When the user enters JellyJams, the FreeCAD main window frame changes to look like a SolidWorks window:

- FreeCAD's many toolbars are removed. Only the small set that matches the SolidWorks quick-access toolbar stays: File, Edit and the workbench selector. The JellyJams ribbon, which plays the role of the SolidWorks **CommandManager**, takes over all other commands. The ribbon belongs to the ribbon area.
- The FreeCAD **Tasks** panel, where the PropertyManager-style feature dialogs appear, and the **Report view** are docked together on the right side of the window. Tasks is on top and Report view is below it, so the 3D view ends in front of them. The model tree, which plays the role of the SolidWorks **FeatureManager design tree**, stays where it is.

When the user leaves JellyJams, or quits FreeCAD while JellyJams is active, the window must go back exactly to the arrangement the user had before. **Stock FreeCAD must never be left altered.** FreeCAD persists its window layout and all parameters when it exits. If those were saved while the JellyJams layout was active, every other workbench (Part Design etc.) would start with hidden toolbars and moved panels. Preventing that is the main job of this area.

---

## 2. User-visible behavior and UI

### 2.1 While JellyJams is active ("layout applied")

**Toolbars**

- Only these main-window toolbars stay visible:
  - toolbars whose Qt `objectName` contains `File`, `Edit` or `Workbench`
  - the match ignores case
  - the match is a containment match, so the workbench selector can never disappear by accident; otherwise the user would have no way out of the layout
  - in stock FreeCAD 1.1 these are the toolbars `File`, `Edit` and `Workbench`
- JellyJams hides every other toolbar that is attached to the main window in a toolbar area and is visible at the moment the layout is applied.
- During the delayed startup/layout checks, it also hides non-kept main-window
  toolbars that FreeCAD has shown or restored late, recording each toolbar only
  once so it is shown again on leave. These checks do nothing after the active
  workbench changes, even before `Deactivated()` arrives, or for an earlier
  activation generation. A toolbar that stays hidden is never changed.
- These toolbars are never touched:
  - toolbars already hidden when the layout is applied and still hidden during
    the delayed checks
  - toolbars that are not attached to a main-window toolbar area, for example toolbars inside a dock or inside a task dialog, which report "no toolbar area" to the main window
- JellyJams contributes no toolbars of its own. Its commands live in the ribbon (dock objectName `JellyJamsCommandManager`) and in a "JellyJams" menu. After entering, the visible main-window toolbars are therefore exactly File, Edit and Workbench.

**Panels (docks)**

- The `Tasks` dock and the `Report view` dock, both identified by exact objectName, must end up:
  - docked, not floating; a panel that was floating is docked again
  - in the right dock area (`Qt.DockWidgetArea.RightDockWidgetArea`)
  - both visible, including a Report view the user had closed
  - stacked vertically, with Tasks above Report view: a vertical split, not tabs
- If only Tasks exists, Tasks alone goes to the right.
- If Tasks cannot be found, no dock is moved. A warning is printed (see 6).
- The model tree dock (`Model`) is not moved, hidden or restyled.
- All other docks are not moved or hidden. Examples: Python console, Selection view, and any foreign dock.

**Look**

- Applying the layout also applies the JellyJams color scheme and the SolidWorks-like 3D-view background and sketch colors. Those are owned by the theme and view-background areas.
- The color scheme is a stylesheet block on the main window between the markers `/* @jellyjams-stylesheet-open */` and `/* @jellyjams-stylesheet-close */`. That block must be present **exactly once**, however often the layout is applied.
- These are tied to the layout lifecycle so that the quit guard (2.3) and its re-apply also cover them. Applying or removing them twice must be harmless.

### 2.2 After leaving JellyJams (switching to any other workbench)

- Every dock returns to the state it had just before JellyJams was entered:
  - area and position
  - tabbing and splitting
  - floating state
  - visibility
  - for example, Tasks returns to its tab next to the model tree if that is where it was
- Every toolbar that JellyJams hid gets back the visibility it had before entering.
- Every other toolbar keeps its **current** visibility. This matters most for the toolbars of the workbench being switched to, which FreeCAD has already shown (see the verified ordering in 4.4). They must not be hidden.
- The color scheme block is gone. The main-window stylesheet is byte-for-byte what it was before entering.
- The 3D background and sketch colors are back to the user's values. This is owned by the view-background area.
- The JellyJams ribbon dock `JellyJamsCommandManager` is not visible. It must not reappear as a side effect of restoring the window state.

### 2.3 Quitting FreeCAD while JellyJams is active (quit/close guard)

- FreeCAD never calls the workbench's `Deactivated()` on quit, but it saves window layout and parameters on exit.
- JellyJams therefore watches the main window's **Close** event. The moment the user closes the main window (window X, File > Exit, Alt+F4…), JellyJams reverts its changes **before** FreeCAD's own close handling runs, which is before the "Save changes?" prompt appears and before FreeCAD persists anything. JellyJams reverts:
  - window layout (as in 2.2)
  - color scheme and 3D background
  - ribbon hidden
  - user's keyboard shortcuts (owned by the shortcuts area)
  - user's navigation style (owned by the navigation area)
  - user's Assembly, Part Design and TechDraw `SwitchToWB` settings (owned by the assembly area)
- While FreeCAD's modal **"Save changes?"** prompt is open, the user therefore sees stock FreeCAD: stock toolbars, stock panel positions, no ribbon, no JellyJams colors.
- **Save / Don't Save (Discard):** FreeCAD exits and persists the stock state. The next start of FreeCAD shows the user's normal toolbars and panels in every workbench.
- **Cancel:** the close is aborted. Once the prompt has gone, JellyJams re-applies everything it reverted:
  - layout (with a fresh snapshot)
  - color scheme and 3D background
  - navigation style
  - shortcuts
  - ribbon shown
  - Assembly, Part Design and TechDraw `SwitchToWB` overrides
- Re-applying happens only if FreeCAD is still running, the main window is still visible, and JellyJams is still the active workbench.
- JellyJams must **never** re-apply while the prompt (or any other application-modal dialog) is still open. If it did, a subsequent Save/Discard would persist the JellyJams layout.
- The guard never blocks, delays, consumes or alters the close itself. FreeCAD closes or prompts exactly as it would without JellyJams.

### 2.4 Startup with JellyJams as the start-up workbench (autoload deferral)

- FreeCAD can be set to start in JellyJams, through its start-up workbench preference `User parameter:BaseApp/Preferences/General`, string `AutoloadModule` = `JellyJamsWorkbench`.
- In that case FreeCAD activates the workbench **before** it has restored the user's saved window state and **before** the main window is shown.
- A snapshot taken at that moment would capture a bootstrap layout. Leaving JellyJams later would then impose that bootstrap layout over the user's real arrangement.
- Therefore, while the main window is not yet visible, applying the layout must be **deferred**. Nothing is changed, and no snapshot is taken. JellyJams waits until FreeCAD has shown the main window, then applies the layout normally.
- To the user, JellyJams appears right after the window appears.
- After a deferred apply, the ribbon must be shown again if JellyJams still wants it visible. FreeCAD's restore of the saved window state hides docks that were saved hidden, and the ribbon dock is one of them.

---

## 3. Triggers and timing

| Event | Effect |
|---|---|
| JellyJams workbench `Activated()` | Apply the layout. This must be the **first** JellyJams UI change in the activation sequence, so the snapshot is taken before the ribbon, theme, navigation or anything else alters the window. If the layout is already applied, nothing happens and no new snapshot is taken. |
| `Activated()` while the main window is not visible | Schedule a deferred apply (see 2.4). Only one deferral may be pending at a time. A further apply request while one is pending does not start another. |
| Deferred-apply poll | About every **200 ms**. Stop polling and apply once the main window is visible. Cancel silently if the active workbench (`FreeCADGui.activeWorkbench().name()`) is no longer `JellyJamsWorkbench`. Give up after about **12 s** (about 60 polls) and print a warning that the layout was not applied because the main window stayed hidden. |
| After the layout is applied | Re-check non-kept toolbar visibility and re-dock Tasks and Report view to the right at about **350 ms, 1200 ms and 3000 ms**, only while the same activation is applied and JellyJams is still the active workbench. Reason: FreeCAD can restore stock toolbars late, and its dock overlay manager rebuilds panel placement after changes and workbench switches. Each newly hidden toolbar is recorded once for exact restore. |
| JellyJams workbench `Deactivated()` | Revert the layout (2.2). This is the **last** JellyJams step in the deactivation sequence, after the ribbon is hidden and navigation, shortcuts, 3D background and theme have been reverted. Any pending deferred apply is cancelled first, even if the layout was never applied. If the layout is not applied, nothing else happens. |
| About **250 ms** after the layout is reverted | Second restore pass: restore the dock arrangement from the snapshot again, and keep **every** toolbar's visibility exactly as it is at that moment. After that pass, hide the ribbon dock if JellyJams does not currently want it visible. Skip the pass entirely if the layout has been applied again in the meantime, for example after a quick switch back into JellyJams. |
| Main window **Close** event | Only while JellyJams is active (between `Activated()` and `Deactivated()`), whether or not the layout is applied yet: restore the Assembly, Part Design and TechDraw `SwitchToWB` settings, hide the ribbon, restore shortcuts and navigation style, revert the look and the layout (if applied), then schedule the re-apply check. Otherwise do nothing. |
| Re-apply check, about **600 ms** after the Close event | If an application-modal dialog is open (`QApplication.activeModalWidget()` is not null), check again about 600 ms later, and repeat for as long as it stays open. Once no modal dialog is open: do nothing if the main window is not visible or the active workbench is not `JellyJamsWorkbench`. Otherwise re-apply layout, look, navigation, shortcuts and ribbon. |

The timings are tuning values. Exact milliseconds are not part of the contract, but these must hold:

- Re-docking must keep working through FreeCAD's delayed overlay rebuilds.
- The second restore pass must land after FreeCAD's roughly 100 ms overlay rebuild.
- The re-apply check must keep deferring for as long as a modal dialog is open.

---

## 4. FreeCAD state read or changed

### 4.1 Main window (Qt)

- `FreeCADGui.getMainWindow()` returns the `QMainWindow`.
- Read:
  - `isVisible()` on the main window, for the deferral and the re-apply check
  - all `QToolBar` children, with their `objectName`, visibility and `toolBarArea()`; the latter equals `Qt.ToolBarArea.NoToolBarArea` for toolbars not attached to the main window
  - all `QDockWidget` children, with their `objectName`
- Snapshot: `QMainWindow.saveState()`, taken once per apply and held **in memory only**.
- Restore: `QMainWindow.restoreState(snapshot)`, with the toolbar-visibility protection described in 5.2.
- Changed:
  - visibility of non-kept toolbars
  - floating state, dock area, visibility and vertical split of the `Tasks` and `Report view` docks, through `addDockWidget(RightDockWidgetArea, …)`, `setFloating(False)` and `splitDockWidget(Tasks, Report view, Qt.Orientation.Vertical)`
- Event filter: one Close-event filter on the main window, installed during the first activation of the workbench in a session (the last activation step). It is never installed twice and stays for the rest of the session. It acts only while JellyJams is active and always lets the event through.

### 4.2 Exact objectNames relied on

| Object | objectName |
|---|---|
| Task panel dock | `Tasks` (FreeCAD 1.1) |
| Report view dock | `Report view` |
| Model tree dock (never touched) | `Model` (older FreeCAD: `Combo View` / `Tree view`) |
| Kept toolbars | `File`, `Edit`, `Workbench` (case-insensitive containment match) |
| JellyJams ribbon dock (owned by ribbon area) | `JellyJamsCommandManager` |

Other JellyJams areas may also need to find the task panel dock. The same identification applies to them: exact `Tasks` on 1.1, with a tolerant containment match as a fallback for other versions.

### 4.3 Workbench and application state read

- `FreeCADGui.activeWorkbench().name()` is compared with `JellyJamsWorkbench`.
- `QApplication.activeModalWidget()` is non-null while FreeCAD's "Save changes?" `QMessageBox`, or any modal dialog, runs its nested event loop. QTimers keep firing inside that loop.

### 4.4 Verified FreeCAD ordering facts (must be designed around)

1. **Workbench switch order.** On a switch away from JellyJams, FreeCAD first shows the next workbench's toolbars, and only about 200 ms later calls JellyJams' `Deactivated()`. The snapshot was taken inside JellyJams, where those toolbars were hidden. A blanket `restoreState()` in `Deactivated()` would therefore hide the new workbench's toolbars. **Restore only what JellyJams changed.**
2. **Overlay manager delay.** FreeCAD's dock overlay manager re-docks panels about 100 ms after changes, and again around workbench switches. Dock placement needs delayed follow-up passes, both after applying and after reverting.
3. **Foreign docks vs. toolbars.** FreeCAD hides and shows the toolbars it manages on every workbench switch. It leaves foreign `QDockWidget`s alone, but its asynchronous state restore can re-show a dock. This is why the ribbon must be re-hidden after restores.
4. **Quit.** FreeCAD never calls `Deactivated()` on quit. It persists the window layout (`MainWindowState`, including toolbar and dock visibility) and all parameters on exit. A Close-event filter on the main window runs **before** FreeCAD's own close handling. If documents are unsaved, the "Save changes?" prompt runs a nested event loop inside that close handling. Cancel aborts the close.
5. **Autoload.** If the workbench is autoloaded at startup, `Activated()` runs before the main window is shown and before FreeCAD restores the saved window state.

### 4.5 Parameters

- The window-layout area itself **reads and writes no parameters**. It stores nothing under `User parameter:BaseApp/Preferences/Mod/JellyJams`.
- Through the quit guard, it triggers restoration of parameters owned by other areas. These must hold their pre-JellyJams values when FreeCAD saves `user.cfg` on exit:

| Group | Key | Owned by |
|---|---|---|
| `User parameter:BaseApp/Preferences/View` | `NavigationStyle` (JellyJams sets `Gui::SolidWorksNavigationStyle`) | navigation area |
| `User parameter:BaseApp/Preferences/Shortcut` | overrides such as `Std_ViewFitAll` (`F`), `Std_Refresh`, `Std_ViewIsometric`, `Std_ViewBoxZoom`, `Std_ViewFront` | shortcuts area |
| `User parameter:BaseApp/Preferences/View` | 3D background and sketch color keys | view-background area |
| `User parameter:BaseApp/Preferences/Mod/JellyJams` | crash-recovery records `OriginalNavigationStyle`, `OriginalShortcuts`, `OriginalViewColors`, which must be empty or absent after an orderly quit | respective areas |

- Any other FreeCAD-persisted override that JellyJams holds while active must be covered in one of two ways. It can be reverted by the quit guard and re-applied on Cancel. Or it must be guaranteed by its owner's startup recovery. Example: the bool `SwitchToWB` in `User parameter:BaseApp/Preferences/Mod/Assembly`, `.../Mod/PartDesign` and `.../Mod/TechDraw/General`, owned by the assembly area.

### 4.6 FreeCAD commands

No FreeCAD command is run by this area. Testers use `FreeCADGui.activateWorkbench("PartDesignWorkbench")` / `FreeCADGui.activateWorkbench("JellyJamsWorkbench")`, or the workbench selector, to enter and leave.

---

## 5. Persistence and restore rules

### 5.1 Snapshot

- A snapshot of the complete main-window state is taken every time the layout goes from "not applied" to "applied", and only then. Re-applying while already applied must not take a new snapshot; otherwise the JellyJams layout would become the restore target.
- The snapshot is taken only while the main window is visible, after FreeCAD has restored the user's saved state (see 2.4).
- The layout counts as **applied as soon as the snapshot exists**, before any toolbar or dock is changed. If any later step fails, leaving and the quit guard can still restore the snapshot.
- The snapshot lives in memory for the session. It is never written to disk.

### 5.2 Exact restore on leave

- Docks are restored from the snapshot as described in 2.2.
- Toolbar visibility:
  - Only the toolbars that JellyJams itself hid during this apply get their visibility from the snapshot.
  - Every other toolbar keeps the visibility it has at the moment of restore. If restoring the snapshot changed it, it is put back.
  - JellyJams keeps a record of which toolbars it hid for this apply. The record is cleared when the layout is reverted.
- A toolbar that FreeCAD deleted in the meantime is skipped silently.
- The second pass (about 250 ms later) restores docks again. It protects **all** toolbars' current visibility, and then re-hides the ribbon if it is not wanted.
- Consequences, which are intended:
  - Dock rearrangements the user made while inside JellyJams are discarded on leave, because exact restore wins.
  - A kept toolbar (File, Edit, Workbench) that the user hid while inside JellyJams stays hidden after leaving.
  - A toolbar that JellyJams hid and the user re-showed inside JellyJams returns to its pre-entry visibility.
  - Toolbar positions return to the snapshot.

### 5.3 Quit and close

- The quit guard performs the same revert as leaving, including the delayed second pass. It also restores shortcuts and navigation style and hides the ribbon, all before FreeCAD's close handling persists state.
- The result on disk after an orderly quit is indistinguishable from quitting FreeCAD without JellyJams ever having been active in that session.

### 5.4 Cancel re-apply

- Re-applying after Cancel is a fresh apply: a new snapshot (now of the stock arrangement) plus the look, navigation, shortcuts and ribbon.
- The color-scheme block must end up present exactly once.

### 5.5 Crash recovery

- The window-layout area keeps no on-disk state, so no startup recovery is needed for the layout itself. FreeCAD persists the window layout on orderly exit, which the guard covers.
- Parameters changed while JellyJams is active (navigation, shortcuts, 3D background, the Assembly, Part Design and TechDraw `SwitchToWB`) are recovered at the next startup by their owning areas, from the backup records in `Mod/JellyJams`.
- Requirement: after FreeCAD is killed while JellyJams is active, the next start must show the user's normal toolbars and panels in other workbenches.
  - Suppose FreeCAD turns out to persist toolbar or dock visibility at some moment other than orderly exit. Then JellyJams must make sure JellyJams-hidden toolbars are never persisted as the user's state. One way is to revert and re-apply around that moment. Another is to repair at startup.

---

## 6. Edge cases and failure handling

- **Calling apply twice** while applied: no effect, no new snapshot, no second close guard.
- **Calling revert when not applied:** no effect, except that a pending deferred apply is cancelled.
- **Leave while a deferred apply is pending:** the deferral is cancelled and nothing is applied later.
- **Workbench switched away before the window became visible:** the deferral notices and cancels itself.
- **Main window never becomes visible** within about 12 s: give up, print a warning, apply nothing, and change nothing.
- **Deferred apply raises an error:** print an error and leave the window as is. The ribbon re-show is skipped.
- **`Tasks` dock not found:**
  - Print a warning listing the objectNames of all docks present, to help diagnose renamed docks in other FreeCAD versions.
  - Toolbar hiding and the rest of the layout still happen.
  - The Report view is not moved either.
- **`Report view` not found:** Tasks alone is docked right. No warning is required.
- **Panels floating at apply time:** they are docked. On leave they float again, in their original geometry, because of the snapshot.
- **FreeCAD's overlay manager moves the panels back** after apply: the delayed re-dock passes put them right again. Each pass does nothing if the layout has been reverted meanwhile.
- **Quick re-entry** within the 250 ms second-pass window: the second pass must not run, so the new layout is not undone.
- **Color scheme or 3D background fails to apply or remove:** print a warning and continue. The layout itself must not fail because of the look.
- **Errors inside any delayed pass or inside the Close-event handling** are swallowed, and logged where useful. Closing FreeCAD must never be blocked or broken by JellyJams.
- **Close with no unsaved documents:** there is no prompt, and FreeCAD exits after the revert. The re-apply check never fires, or finds the window gone and does nothing.
- **Close while a different modal dialog is open**, or the user leaves the Save-changes prompt open for a long time: re-apply waits until no modal dialog remains.
- **Close cancelled, but by then JellyJams is no longer the active workbench**, or the window is hidden: nothing is re-applied.
- **Deferral gave up or never applied:**
  - The close guard acts whenever JellyJams is active, not only when the layout is applied. If the layout never became applied in a session (for example, the deferral gave up), the guard still reverts the overrides other areas applied in `Activated()` (look, navigation, shortcuts, ribbon, the three `SwitchToWB`); the layout revert then only cancels the pending deferral.
  - Startup recovery remains the fallback for a crash.
- **Activation steps are independent.** In `Activated()` and `Deactivated()`, each JellyJams step is guarded on its own, so one failure never prevents the others. The layout apply runs first on activation, and the layout revert runs last on deactivation.
- **Console output** always uses the prefix `JellyJams: `.
  - One log-level line after applying names the toolbars that were hidden and the ones kept, so wrongly matched names stand out.
  - Warnings cover: missing Tasks dock, deferral timeout, and look apply/remove failures.
  - Errors cover: deferred apply failure.
- **Naming.** Identifiers, objectNames and files must not contain "SolidWorks". SolidWorks wording is fine in user-visible text.

---

## 7. Acceptance criteria

Run FreeCAD 1.1 with a throwaway profile (`FreeCAD.exe -u <user.cfg> -s <system.cfg>`). Unless stated otherwise:

- Start in Part Design.
- Note the visible main-window toolbars there. This is the "stock set".
- Note the area, floating state and visibility of the `Tasks` and `Report view` docks.
- Note the main-window stylesheet.

Checks are made at least 3.5 s after each switch, so every delayed re-dock pass has run.

1. **Kept toolbars.** After switching to JellyJams, the visible main-window toolbars (`QToolBar` children of the main window with `isVisible()` true) are exactly `Edit`, `File`, `Workbench`. The workbench selector is usable.
2. **Panel placement.** In JellyJams, the `Tasks` and `Report view` docks:
   - are both visible
   - are not floating
   - report `RightDockWidgetArea` from `dockWidgetArea()`
   - have Tasks' top edge above Report view's top edge, with no tabbing between the two
3. **Placement is stable.** The panel placement from criterion 2 still holds 3 s after entering. It also still holds after creating a Part Design Body and opening a feature dialog, whose PropertyManager-style panel shows in Tasks on the right.
4. **Model tree untouched.** The `Model` dock has the same area, floating state and visibility in JellyJams as before entering.
5. **Floating panel.** Make `Report view` floating in Part Design, then enter JellyJams. It is docked on the right under Tasks. After switching back to Part Design, it is floating again.
6. **Leave restores stock toolbars.** After switching from JellyJams to Part Design, every toolbar of the stock set is visible again. Part Design's own toolbars are visible: none were hidden by the restore.
7. **Leave honors the verified ordering for other workbenches.** Switch from JellyJams to Sketcher, then to Assembly, re-entering JellyJams in between. Each target workbench's own toolbars are visible after the switch, and stay visible after a further 1 s.
8. **Leave restores panels exactly.** After leaving, `Tasks` and `Report view` have the same area, floating state, visibility and tab/split relationship as recorded before entering.
9. **Leave restores the look and hides the ribbon.**
   - After leaving, the main-window stylesheet equals the recorded one exactly. It contains no `@jellyjams-stylesheet-open`.
   - The `JellyJamsCommandManager` dock is not visible, and is still not visible 1 s later.
10. **User-hidden toolbars stay hidden.** Hide a stock toolbar (for example Macro) in Part Design via the toolbar context menu, enter JellyJams, then leave. That toolbar is still hidden.
11. **Dock changes inside JellyJams are discarded.** In JellyJams, open the Python console dock, which was closed before. After leaving, it is closed again.
12. **Idempotent apply.** Run `Activated()` twice, or select JellyJams again while already in it, then leave. Criteria 6, 8 and 9 still pass.
13. **Repeated cycles.** After 3 enter/leave cycles, criteria 1, 2, 6, 8 and 9 still pass. In JellyJams the stylesheet contains `/* @jellyjams-stylesheet-open */` exactly once.
14. **Close guard during the prompt.**
    - In JellyJams, create an unsaved document (for example `Part::Box`), then close the main window.
    - While the "Save changes?" prompt is open, wait at least 1.5 s (well past the 600 ms re-apply delay). Then:
      - the stylesheet has no `@jellyjams-stylesheet-open`
      - `JellyJamsCommandManager` is not visible
      - `User parameter:BaseApp/Preferences/View` / `NavigationStyle` equals its pre-JellyJams value
      - `User parameter:BaseApp/Preferences/Shortcut` / `Std_ViewFitAll` is empty or absent
      - the stock toolbars are visible
    - Repeat with the prompt held open for 10 s: same result.
15. **Cancel re-applies.** Press Cancel in the prompt from criterion 14. Within 2.5 s:
    - the stylesheet contains the theme block exactly once
    - `JellyJamsCommandManager` is visible
    - `NavigationStyle` is `Gui::SolidWorksNavigationStyle`
    - `Std_ViewFitAll` is `F`
    - criteria 1 and 2 hold

    Then close the dirty document without saving and switch to Part Design. The stock set is visible and the theme is gone.
16. **Discard persists stock.** Repeat criterion 14, then press Discard (Don't Save). FreeCAD exits. In the saved `user.cfg`:
    - `NavigationStyle` is not `Gui::SolidWorksNavigationStyle`, and equals the pre-JellyJams value
    - there are no JellyJams overrides for `Std_ViewFitAll`, `Std_Refresh`, `Std_ViewIsometric` or `Std_ViewBoxZoom` under `BaseApp/Preferences/Shortcut`, unless the user had them before
    - `OriginalNavigationStyle`, `OriginalShortcuts` and `OriginalViewColors` under `BaseApp/Preferences/Mod/JellyJams` are empty or absent
17. **Relaunch after quit.** Relaunch with the profile from criterion 16 and open Part Design:
    - every toolbar of the stock set recorded before criterion 16 is visible
    - `JellyJamsCommandManager` is not visible
    - `Tasks` and `Report view` are in their pre-JellyJams places
18. **Quit without prompt.** In JellyJams with no unsaved documents, quit FreeCAD. It exits normally with no errors in the Report view. Criterion 17 holds on relaunch.
19. **Autoload.** Set `User parameter:BaseApp/Preferences/General` / `AutoloadModule` = `JellyJamsWorkbench` and restart FreeCAD. About 6 s after start:
    - the active workbench is `JellyJamsWorkbench`
    - criteria 1 and 2 hold
    - `JellyJamsCommandManager` is visible

    Then switch to Part Design:
    - more than 3 toolbars are visible, matching the user's saved Part Design arrangement
    - the theme block is gone
    - the panels are in the user's **saved** arrangement from the previous session, for example a Report view the user had closed is closed again, not a default bootstrap layout
20. **Tasks dock missing.**
    - Before entering, rename the `Tasks` dock's objectName from the Python console.
    - Entering JellyJams raises no exception, criterion 1 still holds, and a `JellyJams: ` warning lists the dock objectNames found.
    - Leaving still restores per criterion 6.
    - Restore the objectName afterwards.
21. **Toolbars inside panels untouched.** Add a `QToolBar` inside a dock's content widget, not added to the main window as a toolbar, from the Python console, and leave it visible. It stays visible in JellyJams and after leaving.
22. **Quick switch back.** Leave JellyJams and re-enter it within about 150 ms, for example from a script. 4 s later criteria 1, 2 and the ribbon visibility hold. The delayed restore pass did not undo the new layout.
23. **Crash.** Kill the FreeCAD process (Task Manager) while JellyJams is active, then restart with the same profile and open Part Design:
    - stock toolbars are visible
    - panels are in their pre-JellyJams places
    - no theme block
    - `JellyJamsCommandManager` not visible
    - `NavigationStyle` and shortcuts are back to the user's values
24. **Deferral cancellation (harness-level).** With a main window that is not yet visible, request apply and then revert, or switch the active workbench away. When the window becomes visible, no layout, snapshot or look is applied, and no ribbon is shown by this area.
25. **Deferral timeout (harness-level).** With a main window that never becomes visible, a single `JellyJams: ` warning about the layout not being applied appears after about 12 s. Nothing in the window was changed.
