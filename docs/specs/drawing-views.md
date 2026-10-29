# JellyJams specification: Drawing views

> **Implemented in:** [`jellyjams/projected_view.py`](../../jellyjams/projected_view.py) (Feature A, projection layout, AutoDistribute rule), [`view_labels.py`](../../jellyjams/view_labels.py) (Feature B), [`view_scale.py`](../../jellyjams/view_scale.py) (Feature C), [`sheet_drag.py`](../../jellyjams/sheet_drag.py) (Feature D and the shared double-click hook), [`zoom_lines.py`](../../jellyjams/zoom_lines.py) (Feature E); shared helpers in [`sheet_pick.py`](../../jellyjams/sheet_pick.py) (on-sheet pick mode) and [`drawing_common.py`](../../jellyjams/drawing_common.py) (scale text); icons [`projected_view.svg`](../../resources/icons/projected_view.svg), [`view_scale.svg`](../../resources/icons/view_scale.svg).
>
> **Status:** see [../status.md](../status.md)

Area: drawing-views
Target: FreeCAD 1.1+ (verified facts are for 1.1.4), JellyJams workbench (`JellyJamsWorkbench`).
Language of all user-visible text: English.

This area covers five features of JellyJams's 2D drawing (TechDraw) mode:

- **A. Projected View**: a SolidWorks-style command that adds an aligned projection next to a view of a Standard 3 View.
- **B. Section and detail view labeling**: letters by drafting convention (A-A, B-B …; Z, Y … with scale), a movable label below the view, and two-way sync between the label and the view.
- **C. Scale picker**: a menu of standard scales for the selected view.
- **D. Click-anywhere view dragging**: drag a view by pressing on any of its edges or faces, not only on its frame.
- **E. Zoom line-width compensation**: thinner lines while zoomed in, shown on screen only.

It also defines the rule that makes Standard 3 View projections stay movable (AutoDistribute off). Features A and D depend on that rule, and the new-drawing feature (another area) uses it too.

---

## 1. Purpose

SolidWorks users expect drawing views to behave like SolidWorks drawing views:

- Projected views are made by clicking next to an existing view.
- Section and detail views get conventional letters (A-A, Z (2:1)) and a caption below them.
- The scale comes from a short list of standard scales.
- A view moves when you drag any part of it.
- Lines stay readable when you zoom in a lot.

TechDraw can do all of these, but with different gestures and defaults. This area adds the SolidWorks behavior while the JellyJams workbench is active. It does so without changing what FreeCAD saves to disk, except for the document properties listed in §8, which are changed on purpose.

---

## 2. Terms and common rules

### 2.1 Terminology mapping (SolidWorks label ↔ FreeCAD object)

| SolidWorks term (shown to the user) | FreeCAD document object |
|---|---|
| Sheet | `TechDraw::DrawPage` |
| Sheet Format / title block | `TechDraw::DrawSVGTemplate` (property `EditableTexts`) |
| Standard 3 View (the group) | `TechDraw::DrawProjGroup` |
| Front/Top/Left/… view of the Standard 3 View (a "projection") | `TechDraw::DrawProjGroupItem` (property `Type`) |
| Model View / Drawing View (single view) | `TechDraw::DrawViewPart` |
| Section View | `TechDraw::DrawViewSection`, `TechDraw::DrawComplexSection` (Aligned Section) |
| Detail View | `TechDraw::DrawViewDetail` |
| Note / text field | `TechDraw::DrawViewAnnotation` |
| Dimension, Balloon | `TechDraw::DrawViewDimension`, `TechDraw::DrawViewBalloon` |

### 2.2 Common definitions

- **JellyJams active**: `FreeCADGui.activeWorkbench().name()` equals `JellyJamsWorkbench`. Every automatic behavior in this area works only while JellyJams is active, unless a section says otherwise.
- **Sheet window**: the active MDI sub-window of the main window's `QMdiArea`, when its widget's Qt class name is `TechDrawGui::MDIViewPage`. Its drawing surface is the `QGraphicsView` child of that widget, and the viewport of that view receives mouse events.
- **Task dialog open**: `FreeCADGui.Control.activeDialog()` is truthy.
- **TechDraw tool running**: the mouse cursor on the sheet window's viewport is anything other than the standard arrow cursor. TechDraw sets its own cursor while a tool is running (dimensioning, placing a balloon, panning, and so on) and puts the arrow back when the tool ends. While a tool is running, nothing in this area may change view properties or redraw views. TechDraw holds pointers to edges at that time, and a redraw crashes FreeCAD. This is a hard safety requirement.
- **Resolution factor (Rez)**: TechDraw scene units per sheet millimetre. Read it as a float from the parameter group `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`, key `Resolution`. Use 10.0 when the key is missing or 0.
- **Sheet coordinates**: millimetres, y pointing up. **Scene coordinates**: TechDraw scene units, y pointing down. To convert from scene to sheet, divide by Rez and negate y.
- **Group-relative coordinates**: the `X`/`Y` of a `DrawProjGroupItem` is relative to its group. The Front view is at (0, 0) and y points up. The group's own `X`/`Y` are sheet coordinates.
- **Effective projection method of a group**: the group's `ProjectionType` when it is `First angle` or `Third angle`. When it is `Default`, use the owning page's `ProjectionType`. If the method is still unknown, use `First angle`.
- **Scale text**: the standard way to write a scale value. It is used by the labels, the scale picker and the title block (the sheet-properties area must use the same format):
  - A value of 1 or more is written `N:1`. A value below 1 is written `1:N`, where N is 1 divided by the value.
  - N is rounded to 2 decimals and written without decimals when it is a whole number. Examples: 2 → `2:1`, 1 → `1:1`, 0.5 → `1:2`, 0.25 → `1:4`, 0.3 → `1:3.33`, 2.5 → `2.5:1`.
  - Zero, negative or non-numeric values give an empty text.
- **Report view messages** from this area start with `JellyJams: `.

---

## 3. Feature A: Projected View (`JellyJams_ProjectedView`)

### 3.1 Command and UI

- Command id: `JellyJams_ProjectedView`. Menu text: **Projected View**. Tooltip: a short English description of what the command produces and of the two-step gesture in §3.3; its wording is left to the implementation.
- Icon: a new, original icon drawn for JellyJams (for example, a small view with an arrow pointing to a second, aligned view). Do not use a bundled third-party icon. The icon file name must not contain "SolidWorks".
- Ribbon placement (owned by the ribbon area): **Drawing** tab, view-layout group, as a large button with the two-line label "Projected / View", between **Model View** (`TechDraw_View`) and the **Section View** flyout (`TechDraw_SectionView`).

### 3.2 Availability (command enabled state)

The command is enabled only when all of these hold:

1. No task dialog is open.
2. No Projected View pick is already in progress.
3. The current selection contains at least one object that belongs to a projection group. That is either a `TechDraw::DrawProjGroup` itself, or an object that has a `TechDraw::DrawProjGroup` among its parents (`InList`).

The **reference view** is the first such object in selection order. If that object is the group itself, the reference view is the group's Front view at (0, 0).

### 3.3 Pick mode

When the command runs:

- If no sheet window is active, nothing else happens and a warning goes to the Report view saying the drawing sheet window was not found.
- Otherwise JellyJams enters **pick mode**:
  - The sheet viewport shows a crosshair cursor.
  - The main window status bar shows the hint "Projected View: click beside the view on the side where the new projection should go. Right-click or Esc to cancel."
- Pick mode accepts exactly one gesture:
  - **Left click**: creates the projection (§3.4 to §3.6). The click is consumed, so TechDraw does not also select anything. Pick mode then ends.
  - **Right click or Esc** (Esc while the sheet window or its viewport has focus): cancels pick mode. The click or key is consumed, and nothing is created.
  - Other mouse buttons (for example middle-button pan) and mouse wheel zoom are not consumed, so the user can pan and zoom while picking.
- When pick mode ends, for any reason, the crosshair cursor is removed, the status bar message is cleared, and every event interception installed for pick mode is removed.
- Pick mode is also cancelled when JellyJams is deactivated (when leaving the workbench).
- End pick mode and create the view after the current mouse event has been fully delivered (deferred to the event loop), not inside the event delivery itself.

### 3.4 Direction of the click

- Convert the click point to sheet coordinates (§2.2), then to coordinates relative to the reference view's group.
- The **offset** is the click point minus the reference view's group-relative position. For a reference view that is the group itself, its position is (0, 0).
- Turn the offset (dx, dy), in millimetres with y up, into a **step**:
  - Take the offset's angle, atan2(dy, dx), and round it to the nearest multiple of 45°.
  - The rounded angle picks one of eight steps: 0° right (1, 0), 45° upper right (1, 1), 90° up (0, 1), 135° upper left (−1, 1), 180° left (−1, 0), 225° lower left (−1, −1), 270° down (0, −1), 315° lower right (1, −1).
  - Every step therefore owns an equal 45° wedge. A click 20° above the horizontal still means straight right; one 25° above it means upper right.
  - A zero offset (a click exactly on the reference point) has no angle, so no projection is made.
- The step is taken from the **reference view**, not from the Front view. For example, in first angle, clicking to the right of the Left view gives the Back view.

### 3.5 Where each projection type sits

The place of a projection is worked out from the direction it is viewed along; JellyJams keeps no per-method table of positions.

**Viewing directions.** TechDraw gives each `DrawProjGroupItem.Type` a `Direction`. For an unrotated group (x toward the model's right, y away from someone looking at the Front view, z up) they are (verified on 1.1.4):

| `Type` | Direction (x, y, z) |
|---|---|
| `Front` | (0, −1, 0) |
| `Rear` | (0, 1, 0) |
| `Left` | (−1, 0, 0) |
| `Right` | (1, 0, 0) |
| `Top` | (0, 0, 1) |
| `Bottom` | (0, 0, −1) |
| `FrontTopLeft` | (−1, −1, 1) |
| `FrontTopRight` | (1, −1, 1) |
| `FrontBottomLeft` | (−1, −1, −1) |
| `FrontBottomRight` | (1, −1, −1) |

**Slot.** The slot of a type is its place around the Front view, counted in view steps as (right, up); the Front view's slot is (0, 0). For a type with direction (x, y, z) in the group's effective projection method:

- **Rear** (y > 0): slot (2, 0) in both methods. TechDraw lays the Rear view out one step beyond the side view on the right of the Front view, whatever the method.
- **Third angle**, every other type: slot (x, z). A view lands on the side of the Front view that it looks from.
- **First angle**, every other type: slot (−x, −z). A view lands on the opposite side.

This gives, for example: first angle puts `Top` under the Front view, `Left` to its right and `FrontTopRight` at its lower left; third angle puts `Top` above, `Right` to the right and `FrontTopRight` at the upper right. Those are the same places TechDraw itself uses when `AutoDistribute` is on.

**Finding the new type.**

- The reference view's slot comes from its `Type`. A reference that is the group itself counts as `Front`.
- The wanted slot is the reference slot plus the step (§3.4). The new type is the one whose slot equals it; no two types share a slot.
- If no type has that slot (for example below the Top view in first angle, or to the right of the Rear view), nothing is created. A warning goes to the Report view saying there is no projection in this direction.
- If the new type already exists in the group, nothing is created. An informational message goes to the Report view naming that view by its label.

### 3.6 Placement and result

When a new projection is created:

1. The group's `AutoDistribute` is set to `False` first (§3.7).
2. The projection is added through the group's own `addProjection(<Type>)`.
3. Its group-relative position comes from the click, held to the Front view's axes where its slot (right, up) from §3.5 requires it:
   - `X` = the click's group-relative x when the slot's right part is non-zero, otherwise 0.
   - `Y` = the click's group-relative y when the slot's up part is non-zero, otherwise 0.
   - So `Left`, `Right` and `Rear` stay level with the Front view (`Y` = 0), `Top` and `Bottom` stay on its vertical axis (`X` = 0), and the four corner views go exactly where the user clicked.
4. Its tree `Label` is set from the type:

| Type | Label |
|---|---|
| `Front` | Front View |
| `Top` | Top View |
| `Bottom` | Bottom View |
| `Left` | Left View |
| `Right` | Right View |
| `Rear` | Back View |
| `FrontTopLeft`, `FrontTopRight`, `FrontBottomLeft`, `FrontBottomRight` | Isometric View |

   This mapping is shared with the tree-naming area, which uses it to rename projections in existing drawings. FreeCAD may add a numeric suffix when labels repeat. That is acceptable.
5. All of these document changes form **one undo step named "Projected View"**. The document is recomputed afterwards.

### 3.7 Keeping projections movable (AutoDistribute rule)

TechDraw keeps the projections of a group on their alignment axes while they are dragged, but only when the group's `AutoDistribute` is `False`. With `AutoDistribute` on, TechDraw repositions the projections on every recompute, so dragged views jump back. Requirements:

- **New Standard 3 View created by JellyJams** (requested by the new-drawing area after the group's first recompute):
  - Give every non-Front projection its start position: (right × default horizontal step, up × default vertical step), where (right, up) is its slot for the group's effective method (§3.5).
    - First angle: Top below and Left to the right of the Front view.
    - Third angle: Top above and Right to the right of the Front view.
  - **Default steps** (millimetres):
    - Take the bounding box of the first object in the group's `XSource` that has a shape. If there is none, use `Source`. If neither has a shape, use a 100 × 100 × 100 mm box.
    - Horizontal step = (Lx/2 + Ly/2) × group `Scale` + 15.
    - Vertical step = (Lz/2 + Ly/2) × group `Scale` + 15.
    - The 15 mm is the gap between neighbouring view outlines.
  - Then set `AutoDistribute = False` and recompute.
  - The views are draggable straight away and keep their axis link.
- **Existing drawings**: each time a sheet window becomes the active window while JellyJams is active, which in practice is the moment the ribbon switches to its **Drawing** tab:
  - Look at every `TechDraw::DrawProjGroup` in the active document whose `AutoDistribute` is `True`.
  - Set `AutoDistribute = False` only if the group has at least one non-Front projection and every non-Front projection already has a non-zero `X` or `Y`. That means it has already been distributed. Positions are left unchanged.
  - Leave groups that have only a Front view, or projections still at (0, 0), unchanged.
  - If any group was changed, write one informational Report view message with the count, saying the view groups were made movable and their axes stay linked.
- **Projected View command**: always sets `AutoDistribute = False` on the group before adding a projection (§3.6).
- **Dragging (Feature D)**: if a projection of a group that still has `AutoDistribute = True` is dragged, and the group meets the "already distributed" condition above, set `AutoDistribute = False` inside the same undo step before moving.
- Turning `AutoDistribute` off is a deliberate, saved document change. It is never turned back on automatically.

---

## 4. Feature B: Section and detail view labeling

### 4.1 Scope and trigger

- Applies to newly created `TechDraw::DrawViewSection`, `TechDraw::DrawComplexSection` (together: **section views**) and `TechDraw::DrawViewDetail` (**detail views**). The views can be created by any command, for example the ribbon buttons **Section View** (`TechDraw_SectionView`), **Aligned Section** (`TechDraw_ComplexSection`) and **Detail View** (`TechDraw_DetailView`).
- Watch for object creation with a FreeCAD document observer, registered once when the workbench is first initialized.
- Creations are ignored when any of these is true:
  - JellyJams is not active.
  - The document is restoring (`Restoring`), which covers opening a file.
  - The document is transacting (`Transacting`), which covers undo and redo.
- A newly created view is queued and handled only after FreeCAD's task dialog for that view has closed, and not while a TechDraw tool is running or a view is being dragged (Feature D keeps its own undo step open during a drag). Check the queue about every 250 ms while it is not empty, and stop checking when it is empty. Whatever the user typed in the dialog is respected. If JellyJams is no longer active when the queue is checked, the queued views stay unlabeled.
- If the view was deleted in the meantime (for example the dialog was cancelled), drop it from the queue quietly: log level only, no error dialog.
- All views of one document handled in the same check, their letters, tree names and view labels, and the recompute afterwards form **one undo step named "View Label"**, which is always closed, also when labeling fails. Because FreeCAD records the creation of the view in its own step before that, removing a new section or detail view with Undo takes two steps: first "View Label", then FreeCAD's creation step.

### 4.2 Letter assignment

- The **letter** of a section view is its `SectionSymbol`. The letter of a detail view is its `Reference`. Leading and trailing whitespace is ignored.
- A view **needs a letter** when:
  - Section view: the symbol is empty or `-`.
  - Detail view: the reference is empty or made only of digits. FreeCAD's default reference is `1`.
  - Otherwise the user-entered letter is kept as is.
- **Letter sequences** (I, O and Q are never used, because they are easily confused with 1, 0 and O):
  - Section views: A B C D E F G H J K L M N P R S T U V W X Y Z (23 letters, ascending).
  - Detail views: the same 23 letters in reverse, Z Y X W V U T S R P N M L K J H G F E D C B A.
- **Used letters**: the letters of all section and detail views in the same document. Both kinds share one pool, so a detail never reuses a section's letter and the other way round.
- The assigned letter is the first unused letter in the view's sequence.
  - When all 23 are used, continue with two-letter combinations in sequence order: for sections AA, AB, AC …; for details ZZ, ZY, ZX ….
  - If even those are exhausted, use `?`.
- The letter is written to `SectionSymbol` or `Reference`. TechDraw then shows it on the section line and on the detail circle.

### 4.3 Tree names of section and detail views

When a queued view is handled, its tree `Label` is always set as follows, whether the letter was assigned or kept:

- Section view: `Section View <L>-<L>`, for example `Section View A-A`.
- Detail view: `Detail View <L> (<scale text>)`, for example `Detail View Z (2:1)`. If the scale text is empty, the label is `Detail View <L>`.

Later, when a detail view's `Scale` changes and its label still begins with `Detail ` or `Detail View `, the label is rebuilt with the new scale. Otherwise the label is left alone, because the user renamed it.

### 4.4 The view label (caption below the view)

Each handled section or detail view gets exactly one caption, called the **view label**. It is created only if none exists yet and the view is placed directly on a page (it has a `TechDraw::DrawPage` among its parents).

| Aspect | Requirement |
|---|---|
| Object type | `TechDraw::DrawViewAnnotation` |
| Internal name base | `ViewLabel` (FreeCAD adds suffixes) |
| Link to its view | a dynamic property **`CaptionFor`** of type `App::PropertyLink`, property group **`JellyJams`**, with a tooltip saying which drawing view the caption belongs to. It holds the view. This property is the only way JellyJams recognizes a view label. It is a file-compatibility contract and must stay unchanged across JellyJams versions. |
| Text (`Text`, a string list) | one line. Section view: `<L>-<L>`, for example `A-A`. Detail view: `<L> (<scale text>)`, for example `Z (2:1)`, or just `<L>` when the scale text is empty. |
| `TextSize` | 5.0 mm (a size from the ISO 3098 lettering height series) |
| `Owner` | the view, when the property exists, so the label is listed beneath the view in the model tree |
| Page | added to the view's page |
| Position (after it is added to the page) | `X` = the view's `X`. `Y` = the view's `Y` minus the **caption drop**: the view's half extent × the view's `Scale` + a 6 mm clearance. The half extent of a detail view is its `Radius`. For a section view it is half the largest bounding-box dimension of the first object in the base view's (`BaseView`) `XSource`, or else `Source`. When the half extent cannot be worked out, the drop is 25 mm. |
| Tree `Label` | `View Label <text>`, for example `View Label A-A` |

The view label is an ordinary TechDraw note. The user can select it, drag it, delete it, and edit it by double-clicking (TechDraw's own note dialog).

### 4.5 Synchronization

These rules apply only while JellyJams is active and the document is neither restoring nor transacting. A view still waiting in the queue (§4.1) is not synchronized until it has been handled.

**The auto scheme.** A label text **follows the scheme** when its whole text, ignoring surrounding whitespace, is:

1. one or two capital letters A–Z,
2. optionally followed by a hyphen and one or two capital letters (whitespace allowed around the hyphen),
3. optionally followed by a ratio in parentheses: digits (dots and commas allowed), a colon, digits, with whitespace allowed inside the parentheses.

Examples that follow the scheme: `A-A`, `Z (2:1)`, `Y(5:1)`, `AB-AB`, `K`. Examples that do not: `Detail Y, rotated`, `Section A-A`, or any text with more than one line.

1. **Label text edited by the user, then the view.** When the `Text` of an annotation that has `CaptionFor` changes:
   - If the text follows the scheme and its leading letter(s) differ from the linked view's letter, write the new letter into the view's `SectionSymbol` or `Reference`. Set the view's tree label again as in §4.3. For example, editing a detail label to `Y (5:1)` renames the detail to Y.
   - The label's tree `Label` becomes `View Label <first line of its text>`.
   - Free text (text that does not follow the scheme) is kept, and the view's letter is not changed.
2. **View letter or scale changed, then the label.** When a view's `SectionSymbol`, `Reference` or `Scale` changes:
   - If its view label's current text still follows the scheme, replace the text with the freshly built text (§4.4). For example, changing the scale to 4 gives `Y (4:1)`.
   - If the label holds free text, leave it unchanged.
   - (Detail tree label: see §4.3.)
3. **View moved, then the label.** When a view's `X` or `Y` changes, move its view label by exactly the same displacement. Any offset the user gave the label by moving it is kept.
   - This must also work for views in documents that were reopened from file.
   - The first move after opening must not be lost. Track a last-known position per view, set at label creation and, for existing labels, as soon as the view or label is first seen in the session.
4. A view with no view label (deleted by the user, or never created) is not synchronized, and no label is recreated for it later.

### 4.6 Things this feature must not do

- Do not rename or re-letter views when documents are opened, or on undo or redo.
- Do not overwrite a letter the user typed in FreeCAD's section or detail dialog, except for the placeholder values listed in §4.2.
- Do not create a second label for a view that already has one. A view has a label when an annotation's `CaptionFor` links to it.

---

## 5. Feature C: Scale picker (`JellyJams_ViewScale`)

### 5.1 Command and UI

- Command id: `JellyJams_ViewScale`. Menu text: **Scale**. Tooltip: a brief English line saying which property of the selection the command changes; the exact wording is up to the implementation.
- Icon: a new, original JellyJams icon (for example a ratio glyph such as "1:2" next to a small view). The file name must not contain "SolidWorks".
- Ribbon placement (owned by the ribbon area): **Drawing** tab, view-layout group, the small text button labelled **View Scale** in the stack after **Detail View** (below **Break** and **Crop View**).

### 5.2 Scale target and availability

- The **target** is worked out from the first selected object that gives a target:
  - A projection (`TechDraw::DrawProjGroupItem`) gives its group. All projections of a Standard 3 View always share one scale.
  - A `TechDraw::DrawProjGroup` gives itself.
  - Any other drawing view with a `Scale` property gives itself. This means object types beginning with `TechDraw::DrawView`, plus `TechDraw::DrawComplexSection` and `TechDraw::DrawBrokenView`. It includes single model views, section, aligned section, detail and broken views, images and symbols.
  - **Excluded:** dimensions (`TechDraw::DrawViewDimension`), balloons (`TechDraw::DrawViewBalloon`) and notes (`TechDraw::DrawViewAnnotation`).
- The command is enabled when no task dialog is open and a target exists.

### 5.3 Menu

When the command runs, a popup menu titled **Scale** opens at the current mouse cursor position, with these entries in order:

1. The standard scales (DIN EN ISO 5455): `50:1`, `20:1`, `10:1`, `5:1`, `2:1`, `1:1`, `1:2`, `1:5`, `1:10`, `1:20`, `1:50`, `1:100`.
2. A separator.
3. **Sheet scale**: sets `ScaleType` to `Page`, so the view follows the page scale.
4. **Automatic**: sets `ScaleType` to `Automatic`.
5. **User defined …**: opens a text input dialog titled "Scale". The prompt asks for a scale such as 1:3 or 3:1, and the field is pre-filled with the current state's text.

- The standard-scale entries and the two mode entries are checkable. The entry matching the target's current state is shown checked:
  - `ScaleType` `Page`: Sheet scale.
  - `ScaleType` `Automatic`: Automatic.
  - Otherwise: the standard entry equal to the scale text of the current `Scale`, if there is one.
- Closing the menu without choosing, cancelling the input dialog, or entering text that is not a valid scale does nothing. No undo step is created and there is no error dialog.
- **Valid input**:
  - Either `a:b` with both a and b greater than 0, giving a/b, or a single number greater than 0.
  - A comma counts as a decimal point, and spaces are ignored.
  - Examples: `1:5` = 0.2, `2:1` = 2, `0,5` = 0.5. Invalid: `1:0`, `abc`, `-2`, empty.

### 5.4 Applying the choice

All of the following form **one undo step named "Scale"**:

1. Remember the old `Scale` (1.0 if it is missing or 0) and its scale text.
2. Set `ScaleType` to the chosen mode: `Custom` for a numeric choice, `Page` or `Automatic` for the mode entries. For `Custom`, set `Scale` to the chosen value.
3. Recompute the document. The new scale is the target's `Scale` after the recompute, which matters for `Page` and `Automatic`.
4. **Spacing follows** when the target is a `TechDraw::DrawProjGroup` with `AutoDistribute = False` and the old scale is greater than 0: multiply every projection's `X` and `Y` by new ÷ old, so views neither overlap nor drift apart.
5. **Title block follows** when:
   - the target's page (its direct parent, or its parent's parent, of type `TechDraw::DrawPage`) has a `Template` whose `EditableTexts` contains the key `scale` (the field name used by FreeCAD's ISO templates), and
   - that field's text, ignoring spaces, equals the old scale text, and
   - the old and new scale texts differ.

   In that case, set `EditableTexts["scale"]` to the new scale text. A field holding any other text (for example `M 1:4 (main view)`) is never touched.
6. Write an informational Report view message naming the target's label and the new scale text.
7. Detail view labels (§4.5) and detail tree names (§4.3) update automatically because `Scale` changed.

An exception during the steps is reported to the Report view as an error. The undo step is still closed, so no transaction is left open.

---

## 6. Feature D: Click-anywhere view dragging

### 6.1 Behavior

In TechDraw, a view only moves when the press lands on its empty area or frame. A press on an edge, vertex or face just selects that sub-element, and dragging then moves nothing. JellyJams adds this: **press with the left button on any edge or face of a view and drag, and the whole view moves**, as in SolidWorks.

- When TechDraw itself starts dragging the view (the press hit the view's frame or empty area, so TechDraw's scene has a movable item grabbing the mouse), JellyJams does nothing for that gesture.
- The press is always passed on to TechDraw, so selection behaves normally. A click without a drag only selects.
- A drag starts only after the pointer has moved at least **5 screen pixels** from the press point (Manhattan distance, independent of the zoom level). Smaller movements are passed on unchanged.
- The view that moves is the first object in the selection (made by TechDraw on that press) that is a movable view:
  - a `TechDraw::DrawProjGroupItem`, a `TechDraw::DrawProjGroup`, or any object whose type begins with `TechDraw::DrawView` (model views, section, detail, notes, images, symbols, …), plus `TechDraw::DrawComplexSection` and `TechDraw::DrawBrokenView`;
  - **excluding** dimensions (`TechDraw::DrawViewDimension`) and balloons (`TechDraw::DrawViewBalloon`).
  - If no movable view is selected when the drag threshold is reached (for example the press was on empty sheet, so rubber-band selection must keep working), JellyJams does nothing for that gesture.
- While dragging, mouse-move events are consumed. The view follows the pointer: each scene-unit movement is converted to millimetres using Rez, with y inverted.

**Axis constraints** (the same alignment TechDraw applies itself):

| Dragged object | What moves | Allowed directions |
|---|---|---|
| `Front` projection | the whole group (its `X`/`Y`) | free |
| the group itself | the group | free |
| side projections (slot up part 0: `Left`, `Right`, `Rear`) | the projection | horizontal only |
| top/bottom projections (slot right part 0: `Top`, `Bottom`) | the projection | vertical only |
| corner projections (isometric) | the projection | free |
| a projection whose type has no slot (§3.5), or with no group | the object | free |
| any other view | the view | free |

- An object with `LockPosition = True` is never moved.
- Slots are worked out for the group's effective projection method (§3.5).
- **Releasing the button** ends the drag. The whole drag is **one undo step named "Move View"**, opened when the drag starts and committed on release, followed by a recompute. The release event is consumed. A release with no drag passes through unchanged.
- A press with any button other than the left one cancels any recorded press and passes through.

### 6.2 When dragging must not start

None of the following may record a press or start a drag:

- JellyJams is not active.
- A task dialog is open.
- A TechDraw tool is running (§2.2). This prevents a crash while dimensioning.
- Any JellyJams on-sheet placement mode is running: the Projected View pick (§3.3), and placement modes of other areas such as note or weld-symbol placement.

### 6.3 Attachment

- Every sheet window that becomes active while JellyJams is active gets this behavior. The ribbon area checks the active window about every 450 ms and asks this feature to attach. Attaching to the same window twice must have no effect.
- The behavior stays harmless after leaving the workbench, because of the gate in §6.2.

### 6.4 Shared sheet-mouse hook (interface to other areas)

The same mouse hook on the sheet window also handles **double-clicks** for JellyJams' own symbols. This is specified fully by the annotations area. When:

- JellyJams is active, no TechDraw tool is running, no task dialog is open, and
- the selection contains a `TechDraw::DrawViewSymbol` whose dynamic string property `SymbolType` is `surface` (surface finish) or `weld` (weld symbol),

then the double-click opens that symbol's JellyJams editor, and the event is consumed only if the editor opened. TechDraw's own notes, balloons and weld symbols keep their own double-click behavior.

---

## 7. Feature E: Zoom line-width compensation (screen only)

### 7.1 Behavior

TechDraw draws lines in real millimetres, for example 0.5 mm. When zoomed far in, lines become very thick and vertex dots become large blobs, which makes small edges hard to pick for dimensioning. While JellyJams is active and a sheet window is active:

- **Pixels per millimetre** = the absolute horizontal scale of the sheet view's current transform × Rez.
- **Reduction step** n: if a 0.5 mm reference line is at most 2.5 px wide on screen, n = 0. Otherwise n is the smallest whole number for which 0.5 mm × pixels per mm ÷ 2ⁿ ≤ 2.5 px, capped at 6. The factor is 1/2ⁿ, so the smallest factor is 1/64.
  - Examples (pixels per mm → n): 4 → 0, 5 → 0, 6 → 1, 13 → 2, 48 → 4, 10⁹ → 6.
- At step n, these view-provider properties of every object on the active sheet are shown at their original value × 1/2ⁿ:
  - Dimensions (`TechDraw::DrawViewDimension`), leader lines (`TechDraw::DrawLeaderLine`) and balloons (`TechDraw::DrawViewBalloon`): `LineWidth` only.
  - All other objects: `LineWidth`, `HiddenWidth`, `IsoWidth`, `ExtraWidth`. Only the properties that exist on that object's `ViewObject` are changed.
  - "Objects on the sheet" means the page's `Views`, followed recursively through any object's own `Views` (projections inside groups, contents of clip groups), each object once.
  - The thick-to-thin ratio is kept, because every width scales by the same factor.
  - TechDraw ties vertex dot size to the line width, so the dots shrink as well.
  - Arrow sizes, fonts and other properties are not changed.
- **Settling**: a new step is applied only after the same wanted step has been seen on two checks in a row. Mouse-wheel zooming should not cause a redraw for every wheel notch. The check runs about every 180 ms.
- **Keeping up**: while the step stays the same and is above 0, views and dimensions newly added to the sheet are brought to the current step on the next check.
- **Manual edits survive**: if the user (or another JellyJams feature such as line formatting) changes one of these widths while a reduced step is shown, the changed value counts as the new original, i.e. the shown value ÷ the current factor. Example: at step 2 the user sets 0.175 mm, so the new original is 0.7 mm.
- **Switching sheets**: when the active sheet changes, all widths on the previous sheet are restored before the new sheet is reduced.
- When another kind of window (for example a 3D view) is active, nothing changes. The reduced values stay until one of the restore triggers in §7.2.

### 7.2 Restore triggers (the original widths come back)

These triggers ensure that standard line widths always end up in the file and in all output:

1. **Before every save** of a document, including Save As: a document observer's start-of-save notification (`slotStartSaveDocument`) restores that document's originals before FreeCAD writes the file. Reduction may come back after the save.
2. **While any modal dialog is open** (`QApplication.activeModalWidget()` is not None): file dialogs, print, print preview, PDF export, the "Save changes?" prompt on quit, and so on. Originals are restored within one check interval of the dialog appearing, before any output is produced. This holds whether the dialog was opened from the ribbon, a menu or a shortcut.
3. **JellyJams' own drawing export** (another area) explicitly restores all originals before writing PDF or DXF.
4. **Leaving the JellyJams workbench**: restored on the next check after another workbench becomes active.
5. **Zooming out** until the wanted step is 0.
6. **Closing a document**: its records are forgotten, and nothing is written.

### 7.3 Safety and side effects

- **Never mark documents as modified.** Applying or restoring widths must not leave a document flagged as modified (`*`) unless it already was. A Gui document's `Modified` flag that was false before the change is reset to false afterwards.
- **Do not touch anything while busy.** No change is made in a check while any of these holds (the check is skipped and tried again later):
  - a TechDraw tool is running,
  - any mouse button is pressed,
  - a task dialog is open,
  - the sheet's document has an open transaction (`HasPendingTransaction`).

  This is a crash-prevention requirement: redrawing views while TechDraw is placing a dimension crashes FreeCAD. If the busy test itself fails, treat the state as busy.
- The originals live only in session memory, keyed by document name and object name. They are never written to parameters or to the document.
- Errors inside a check are logged (log level) and never interrupt the user.

---

## 8. FreeCAD state read or changed (exact names)

### 8.1 Commands defined

| Id | Menu text | Feature |
|---|---|---|
| `JellyJams_ProjectedView` | Projected View | A |
| `JellyJams_ViewScale` | Scale | C |

Both are registered when the workbench is first initialized. Their enabled state follows §3.2 and §5.2. FreeCAD commands referenced by the ribbon next to them (not defined here): `TechDraw_View`, `TechDraw_ProjectionGroup`, `TechDraw_SectionView`, `TechDraw_DetailView`, `TechDraw_ComplexSection`, `TechDraw_BrokenView`, `TechDraw_ClipGroup`.

### 8.2 Parameters

- Read only: `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`, float `Resolution` (default 10.0).
- This area writes **no** parameters, under `Mod/JellyJams` or anywhere else.

### 8.3 Document objects and properties

| Object type | Property | Read/Write | Used by |
|---|---|---|---|
| `TechDraw::DrawProjGroup` | `ProjectionType` (`First angle` / `Third angle` / `Default`) | R | A, D |
| | `AutoDistribute` | R/W (set to False only) | A, C, D |
| | `X`, `Y`, `Scale`, `ScaleType`, `Views`, `XSource`, `Source`, `InList`, `LockPosition` | R/W as described | A, C, D |
| | `addProjection(type)` (method) | call | A |
| `TechDraw::DrawProjGroupItem` | `Type`, `X`, `Y`, `Label`, `InList`, `LockPosition` | R/W | A, C, D |
| `TechDraw::DrawPage` | `ProjectionType`, `Template`, `Views`, `addView(obj)` | R / call | A, B, C, E |
| `TechDraw::DrawSVGTemplate` | `EditableTexts` key `scale` | R/W | C |
| `TechDraw::DrawViewSection`, `TechDraw::DrawComplexSection` | `SectionSymbol`, `BaseView`, `Scale`, `X`, `Y`, `Label` | R/W | B |
| `TechDraw::DrawViewDetail` | `Reference`, `Radius`, `Scale`, `X`, `Y`, `Label` | R/W | B |
| `TechDraw::DrawViewAnnotation` (view label) | `Text`, `TextSize`, `Owner`, `X`, `Y`, `Label`, dynamic **`CaptionFor`** (`App::PropertyLink`, group `JellyJams`) | created / R/W | B |
| any scale target | `Scale`, `ScaleType` (`Custom` / `Page` / `Automatic`) | R/W | C |
| any dragged view | `X`, `Y`, `LockPosition` | R/W | D |
| `TechDraw::DrawViewSymbol` | dynamic `SymbolType` (`surface`, `weld`), defined by the annotations area | R | D (double-click) |
| ViewObject of sheet objects | `LineWidth`, `HiddenWidth`, `IsoWidth`, `ExtraWidth` | R/W (transient) | E |
| App document | `Restoring`, `Transacting`, `HasPendingTransaction`, `Objects`, `openTransaction`, `commitTransaction`, `recompute` | R / call | all |
| Gui document | `Modified` | R/W | E |

Tree labels written: `Front View`, `Top View`, `Bottom View`, `Left View`, `Right View`, `Back View`, `Isometric View`, `Section View <L>-<L>`, `Detail View <L> (<scale>)`, `View Label <text>`.

Undo step names: `Projected View`, `Scale`, `Move View`, `View Label`.

### 8.4 GUI state

- Main window status bar: Projected View hint (shown and cleared).
- Mouse cursor on the sheet viewport: crosshair during the Projected View pick.
- Event interception on sheet windows' graphics view and viewport (pick mode, drag, double-click).
- Document observers: object creation and change (Feature B), start of save and document deletion (Feature E).
- Periodic checks: label queue (~250 ms, only while needed), zoom check (~180 ms).
- This area creates no docks and no Qt objects that need a JellyJams objectName.

---

## 9. Persistence and restore rules

- **Intentional document changes**: saved with the user's file and kept after leaving JellyJams. They are undoable where an undo step is listed:
  - letters (`SectionSymbol`, `Reference`) and tree labels,
  - view label annotations with `CaptionFor`,
  - `AutoDistribute = False`,
  - view positions,
  - `Scale` and `ScaleType`,
  - the title block `scale` field.

  Files must still open in plain FreeCAD without JellyJams: the view labels are ordinary notes, and `CaptionFor` shows as an ordinary link property in group "JellyJams".
- **File compatibility**: documents created by any JellyJams version must keep working unchanged in later versions. Existing annotations carrying `CaptionFor` are recognized as view labels, and their links, texts and positions are kept.
- **Transient line widths (Feature E)**:
  - Must never reach a saved file or any output (§7.2).
  - Never persisted, and nothing is recorded in parameters, so there is no exact-restore record and nothing to recover at startup.
  - If FreeCAD crashes while widths are reduced, the file on disk still has the standard widths, because every save restores them first.
  - Known limitation: FreeCAD's own periodic auto-recovery snapshot may not send the start-of-save notification. A recovered document could then contain reduced widths. If FreeCAD exposes a hook before recovery files are written, use it to restore first; otherwise document this limitation.
- **Transient interaction state**: pick mode, drag state, the label queue, last-known view positions and original widths are kept in memory only and discarded on restart.
- **Leaving the workbench**:
  - The Projected View pick is cancelled.
  - Dragging and labeling stop acting (they are gated on the active workbench).
  - Reduced line widths are restored by the next zoom check.
  - Observers and periodic checks may stay installed, but must do nothing outside JellyJams except the restore work in §7.2.
- **Quit**: FreeCAD does not call the workbench's deactivation on quit. The modal "Save changes?" prompt and the start-of-save notification ensure that only standard widths are saved.

---

## 10. Edge cases and failure handling

| Situation | Required behavior |
|---|---|
| Projected View started with no sheet window active | Report view warning. No pick mode, no change. |
| Projected View started from the group object | The reference is the Front view at (0, 0). |
| Click step leads to a slot no projection type has | Warning that no projection exists on that side of the view. Nothing created. |
| Target projection already exists | Message naming the existing view. Nothing created. |
| Group `ProjectionType` is `Default` | Use the page's method (§2.2). |
| Group has no shape source | Default steps use a 100 mm cube. |
| Projection added opposite an existing one (for example adding Right while Left sits at x = 120) | Placed from the click alone (§3.6); the existing view's position is not consulted. |
| Error while creating a projection | Error with details in the Report view. Pick mode is still left. The undo step is closed. |
| Section dialog cancelled (the object is deleted before handling) | Dropped quietly from the queue. |
| Section or detail view not directly on a page (for example inside a clip group) | Letter and tree name are assigned. No view label is created. |
| User typed their own letter (for example `K`) in FreeCAD's dialog | Kept. Tree name and label use `K`. |
| All single letters used | Two-letter combinations, then `?`. |
| User edits a label to free text | The view keeps its letter. Later scale or letter changes no longer overwrite the label. |
| User deletes a view label | Nothing is recreated. No errors on later view changes. |
| User deletes a section or detail view that has a label | No crash. The label stays as a plain note. Its `CaptionFor` link is empty or broken and is ignored. |
| Undo or redo of label or letter changes | The observer ignores changes while the document is transacting. No feedback loops. |
| Opening a file with section or detail views | No letters, labels or tree names change on load. |
| Scale picker with an invalid custom entry | Silently ignored. |
| Scale picker on a group still on `AutoDistribute` | Scale is applied. Spacing is left to TechDraw (no manual spacing scaling). |
| Title block `scale` field holds custom text | Never overwritten. |
| Drag of a view with `LockPosition` | Nothing moves and nothing else is affected. No transaction is left open after release. |
| Press on empty sheet, then drag | Rubber-band selection works normally. No view moves. |
| Press on a view frame or empty area of a view (TechDraw drags it) | JellyJams stays out. TechDraw's own behavior applies. |
| Drag while a TechDraw dimension or balloon tool is running | No drag, no property change. |
| Zoom compensation while a dimension tool is running, a mouse button is held, a task dialog is open, or a transaction is pending | No change until idle. |
| Zoom compensation with several documents and sheets | Only the active sheet is reduced. Switching sheets restores the previous one first. |
| Line widths changed by the user while zoomed in | The new value is treated as the original (§7.1). |
| Document closed while reduced | Records forgotten. No error. |
| Any exception in observers, event hooks or periodic checks | Caught and logged (log level for routine failures, error level for command failures). Never propagates into FreeCAD's event handling. Event hooks pass the event on to TechDraw unchanged if they fail. |

---

## 11. Interfaces with other areas

- **New drawing (`JellyJams_MakeDrawing`)**: after creating and recomputing a Standard 3 View, it asks this area to apply the start layout and `AutoDistribute = False` (§3.7).
- **Ribbon**:
  - Places `JellyJams_ProjectedView` and `JellyJams_ViewScale` on the **Drawing** tab.
  - On the transition into a sheet window, it switches to the Drawing tab and triggers the existing-drawing AutoDistribute rule (§3.7).
  - About every 450 ms while a sheet window is active, it asks Feature D to attach.
  - Refreshes the buttons' enabled state from `IsActive`.
- **Tree naming**:
  - Uses the projection type → label mapping (§3.6) for existing drawings.
  - Must not rename section or detail views or view labels, which this area owns.
  - Must not rename TechDraw objects while a TechDraw tool is running (the same detection rule as §2.2).
- **Sheet properties**: uses the same scale-text format (§2.2) for the title block.
- **Drawing export**: calls the "restore all original widths" service (§7.2 item 3) before writing output.
- **Annotations (notes, weld symbol, surface finish)**:
  - Their placement modes must block dragging (§6.2).
  - Their symbols use `SymbolType` for the double-click hook (§6.4).
  - When the workbench is deactivated, all on-sheet pick modes are ended, including this area's Projected View pick.
- **Line format**: width changes made through it are honored as new originals by Feature E.

---

## 12. Acceptance criteria

Setup for most checks: switch to the JellyJams workbench and open a part, for example a 200 × 80 × 60 mm block. Use **Make Drawing** to create a drawing with a Standard 3 View, or use TechDraw's Standard 3 View command on an ISO template page. "Report view" means FreeCAD's report panel.

**Projected View**

1. With nothing selected, **Projected View** is disabled. After selecting the Front view (or any projection, or the Standard 3 View group) on the sheet, it is enabled.
2. Pressing **Projected View** turns the sheet cursor into a crosshair and shows the hint in the status bar. Pressing Esc restores the cursor, clears the status bar and creates nothing. Repeating with a right click gives the same result.
3. In a first-angle group, select the Front view, start the command and click clearly to the right of it. A projection of type `Left` labelled "Left View" is created. Its `Y` is 0, level with the Front view, and its `X` equals the click position. Exactly one undo step "Projected View" removes it.
4. In a first-angle group, select the Left view and click to its right. A `Rear` projection labelled "Back View" is created level with the Front view (`Y` = 0).
5. In a first-angle group, select the Front view and click diagonally down-left. A `FrontTopRight` projection labelled "Isometric View" is created exactly at the click point.
6. In a third-angle group, select the Front view and click to the right. A `Right` projection ("Right View") is created. Clicking above gives `Top`.
7. Clicking below the Top view in first angle creates nothing, and the Report view warns that there is no projection in this direction.
8. Clicking toward a projection that already exists creates nothing, and the Report view says that view already exists.
9. After Projected View, the group's `AutoDistribute` is `False`. Recomputing the document does not move any projection.
10. Leaving the JellyJams workbench while the crosshair pick is running cancels it: the cursor is restored and the status bar cleared.

**Movable Standard 3 View**

11. A drawing created by **Make Drawing** has `AutoDistribute = False`. The Top and side views are placed on their axes with a visible gap from the Front view, not overlapping it.
12. Open an existing drawing saved with `AutoDistribute = True` and distributed projections, then activate its sheet window in JellyJams. `AutoDistribute` becomes `False`, no projection moves, and the Report view shows the count of groups made movable.

**Section and detail labeling**

13. Create a section view with the ribbon's **Section View** and accept FreeCAD's dialog. Within about a second of the dialog closing, the section's `SectionSymbol` is `A` (unless the user typed another letter), its tree label is "Section View A-A", and a note reading `A-A` (5 mm text) appears below the view. The note's tree label is "View Label A-A", it is listed under the section view, and it has a `CaptionFor` property (group JellyJams) linking to the section view.
14. A second section view gets `B`. With sections A–H already present, the next one gets `J`, never I, O or Q.
15. Create a detail view at scale 2. Its `Reference` becomes `Z` (replacing FreeCAD's default `1`), its tree label is "Detail View Z (2:1)", and its note reads `Z (2:1)`. The note sits below the detail circle area, with Y = view Y − (Radius × 2 + 6 mm). The next detail gets `Y`.
16. A letter typed by hand in FreeCAD's section or detail dialog (for example `K`) is kept, and the label shows `K-K` or `K (…)`.
17. Double-click the detail's note and change the text to `Y (5:1)`. The detail view's `Reference` becomes `Y` and its tree label becomes "Detail View Y (…)" with the current scale. The note's tree label becomes "View Label Y (5:1)".
18. Change the detail view's scale to 4. The note text becomes `Y (4:1)` and the tree label "Detail View Y (4:1)".
19. Change the note text to `Detail Y, rotated`, then change the detail's scale again. The note text is unchanged and the detail keeps `Y`.
20. Drag a section view to a new place. Its note moves by the same displacement. Move the note on its own first, then move the view: the note keeps its custom offset. This also works on the first drag after closing and reopening the file.
21. Opening a file containing section and detail views does not change any letter, tree label or note. Undo and redo of label edits do not trigger extra renames.
22. Creating a section view while the TechDraw workbench (not JellyJams) is active assigns no letter and creates no note.

**Scale picker**

23. With nothing suitable selected (or only a dimension, balloon or note selected), **Scale** is disabled. Selecting any projection, a section, a detail or a single model view enables it.
24. The menu lists 50:1 … 1:100 (12 entries), a separator, Sheet scale, Automatic and User defined …. The entry matching the current state is checked.
25. With a projection selected, choosing `1:4` sets the **group** to `ScaleType = Custom`, `Scale = 0.25`. All projections resize together, and their distances from the Front view scale by the same ratio, so nothing overlaps. One undo step "Scale" reverts everything.
26. If the title block's `scale` field showed the old scale (for example `1:2`), it now shows `1:4`. If it held other text, it is unchanged.
27. Choosing **Sheet scale** on a detail view sets its `ScaleType` to `Page`. Reopening the menu shows Sheet scale checked.
28. **User defined …** with `1:3` gives scale 0.3333 and the detail label `… (1:3)`. With `0,5` it gives 0.5. With `abc` or `1:0` nothing changes and no undo step is added.

**Click-anywhere drag**

29. Press with the left button on a visible edge of the Top view (first angle) and drag diagonally. The Top view moves only vertically and stays aligned with the Front view. Releasing gives exactly one undo step "Move View".
30. Dragging an edge of a side view moves it only horizontally. Dragging an edge of the Front view moves the whole Standard 3 View. Dragging an isometric projection or a single model view by an edge moves it freely.
31. A click on an edge without moving (or moving less than 5 px) only selects the edge. Nothing moves and no undo step is added.
32. Dragging a view by its frame or empty area behaves exactly like plain TechDraw: no extra undo step, no double movement.
33. While the Smart Dimension tool is running, pressing and dragging on edges never moves a view, and FreeCAD does not crash when placing dimensions on a zoomed-in sheet.
34. A view with `LockPosition = True` cannot be dragged by its edges.
35. Rubber-band selection on empty sheet area still works.

**Zoom line widths**

36. Zoom far into a sheet. Visible lines and vertex dots become thinner in steps, and thick and thin lines keep their ratio. Zooming back out restores the original look. The document is never marked modified (`*`) by zooming.
37. While zoomed in, save the document. Then open the saved file in a fresh FreeCAD session, without zooming in, and look at a view's `LineWidth`. It holds the original value, for example 0.5 mm, not the reduced one.
38. While zoomed in, open **File → Print** or export the page to PDF. While the dialog is open the sheet shows standard widths, and the output has standard widths.
39. While zoomed in, switch to the Part Design workbench. The sheet returns to standard widths.
40. While zoomed in at a reduced step, set a view's `LineWidth` to a new value in the Property view, then zoom out completely. The property ends up at the value the user intended at full scale (shown value × 2ⁿ). It is not reverted to the old original.
41. While placing a dimension (tool running, cursor not the arrow), zooming with the wheel causes no line-width change until the tool ends. FreeCAD does not crash.

**General**

42. No parameter under `User parameter:BaseApp/Preferences/Mod/JellyJams` is created or changed by any feature in this area.
43. A drawing saved with JellyJams view labels opens in FreeCAD without JellyJams installed and shows the labels as ordinary notes, with no errors.
44. The icons of `JellyJams_ProjectedView` and `JellyJams_ViewScale` are original JellyJams artwork. No file, identifier or objectName introduced by this area contains "SolidWorks".
