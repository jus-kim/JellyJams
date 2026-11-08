# JellyJams specification: Quick access and confirmation

Implemented in `quick_access.py` and pure `access_rules.py`; owned by ribbon
visibility. Verification: [status](../status.md).

## Behavior

While JellyJams' ribbon is active, plain **S** opens a command popup at the
pointer. Default results come from the active sketch, drawing, assembly or part
context. Typing searches all available ribbon tools by familiar label and native
command name. All flyout variants are searchable; Sketch/Exit Sketch follows the
current edit state. Results use native icons and command availability. Selection
is preserved and commands dispatch through the same route as ribbon clicks.

Enter activates an enabled current result; Down moves into the result list.
Escape and clicking outside dismiss the popup. A command is revalidated after
the popup releases focus. Document changes invalidate pending dispatch.

Plain **D** brings the current task's confirmation controls to the pointer.
The same controls appear near the top-right of the docked active viewport, to
the left of the navigation cube. Native OK/Cancel buttons and their enabled
state are authoritative. Sketch edit offers **Exit Sketch**, using native Leave
Sketch. No discard-sketch action is invented. Modal dialogs retain ownership.

Confirmation captures the document and native task-form identities and checks
them again at activation. A stale popup cannot confirm a replacement task.
Where the native task wrapper is available, its document owner must match the
active document; a global task from another document offers no confirmation.
Opening a popup does not select geometry or create an undo transaction.

S/D remain text in line edits, spin boxes, text editors, combo boxes and ordinary
type-to-search lists. The native model tree offers the popup unless an inline
editor is active. Modified keys and auto-repeat do not activate these tools.
Key handling is scoped to the main window, its docks and discovered view
windows, never the application. No shortcut preference is written: temporary
ShortcutOverride handling gives JellyJams priority while these controls exist.

Owned controls follow the light/dark palette. No FreeCAD widget stylesheet is
changed. Placement is clamped to the screen. Native controls remain available.
Rebuilding or destroying native task widgets must not leave dangling pointers.

Ribbon show enables one service; hide, leave and quit remove filters, popups,
corner widgets and timers. Existing quit-reapply brings them back after a
cancelled quit. There are no new persistent settings or document properties.

## Acceptance criteria

1. S opens the proper context, including during sketch edit.
2. Search finds native and familiar names, including flyout variants.
3. Disabled commands cannot execute, including after availability changes.
4. Escape/outside dismiss; Enter/Down/list activation work without extra picks.
5. Names, values, equations, combo boxes and list typing retain S/D.
6. Modified keys and auto-repeat never start a popup.
7. Native selection survives opening and dismissing the popup.
8. Corner and D accept/cancel the active feature, following native availability.
9. Stale document/task controls cannot confirm or dispatch against a new target.
10. Sketch offers Exit Sketch and no misleading discard action; modal input owns keys.
11. Repeated show/hide creates no duplicate service; leave/quit clean up completely.
12. Native S/D shortcut parameters stay byte-for-byte equivalent through use and exit.

Undocked/split views and every native dialog type need separate native coverage
before broad parity claims. The popup is a searchable list, not a customizable
icon grid; customization is a future extension.
