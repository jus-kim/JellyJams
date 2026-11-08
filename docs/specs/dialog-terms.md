# JellyJams specification: Dialog terms (SolidWorks terminology inside FreeCAD task dialogs)

> **Implemented in:** [`jellyjams/dialog_terms.py`](../../jellyjams/dialog_terms.py) (periodic relabeling service, combo safety rule, scale-field fix, ISO 128 presets row), [`dialog_terms_data.py`](../../jellyjams/dialog_terms_data.py) (the dialog catalog of section 2.3).
>
> **Status:** see [../status.md](../status.md)

Product: JellyJams, a FreeCAD 1.1+ workbench (key/class `JellyJamsWorkbench`,
MenuText "JellyJams") that makes FreeCAD look, feel and operate like
SolidWorks. English only. Reference FreeCAD version for every widget name and
list length below: **FreeCAD 1.1.4**.
The additional control names noted below cover FreeCAD 26.3 RC2.

---

## 1. Purpose

While the JellyJams workbench is active, the task dialogs that FreeCAD itself
opens in the Tasks panel (Pad, Pocket, Revolution, Joint, TechDraw view and
annotation dialogs, ...) must read like their SolidWorks counterparts: e.g. the
Pad dialog shows "Direction 1", "End Condition", "Blind", "Through All",
"Mid Plane" instead of FreeCAD's "Side 1", "Type", "Dimension", "To last",
"Symmetric".

Only the **displayed text** changes. The dialogs remain FreeCAD's own dialogs,
with all of FreeCAD's logic, signals, selection handling, previews, OK/Cancel
behavior and document results unchanged. JellyJams never replaces, re-creates
or re-implements these dialogs.

A widget is relabeled only when the SolidWorks PropertyManager has a standard
term for the same control. Every other widget keeps FreeCAD's text.

One dialog additionally gets a small JellyJams addition: the TechDraw line
decoration dialog (SolidWorks: Line Format) gets a row of ISO 128 standard
line-thickness presets.

---

## 2. User-visible behavior

### 2.1 General rules

- The replacement texts are the terms of the English SolidWorks UI.
- They apply regardless of FreeCAD's UI language (widgets are identified by
  their fixed Qt objectNames from FreeCAD's `.ui` forms, which do not depend on
  the language). With FreeCAD set to e.g. German, the listed widgets still show
  the English SolidWorks terms.
- Text-bearing widgets: for labels, push buttons, check boxes and radio
  buttons the widget's text is replaced; for group boxes the group-box title is
  replaced.
- Combo boxes: only the display text of each entry is replaced, entry by entry,
  by position. The number of entries, their order, the current selection
  (index), item data and enabled state are never changed.
- Tool tips: replaced only for the projection view check boxes of the
  Standard 3 View dialog, and only when FreeCAD's current tool tip is one of
  the texts listed there (FreeCAD rewrites these tool tips when the projection
  type changes, so they are translated by their current text).
- Widgets not listed here keep FreeCAD's texts. The task-box header titles
  (FreeCAD's caption bar of each task box) are out of scope and stay FreeCAD's.
- A widget whose text FreeCAD itself rewrites to signal state is never
  touched (listed per dialog as "must stay FreeCAD's"), even if a catalog
  entry named it.

### 2.2 Safety rule for combo boxes (mandatory)

A combo box is relabeled **only if its current entry count equals exactly the
entry count of that combo in FreeCAD 1.1.4** (the length of the replacement
list given below). If the count differs (e.g. a future FreeCAD version added,
removed or reordered modes), that combo box is left completely untouched:
no entry is relabeled, not even partially. Rationale: leaving FreeCAD's texts
is better than mislabeling a mode. The safety rule applies per combo box; the
other widgets of the same dialog are still relabeled.

Labels, group boxes, buttons and tool tips have no count rule: if the widget
with the listed objectName exists, it is relabeled; if it does not exist, it is
skipped silently.

### 2.3 Dialog catalog

Each dialog is identified by the objectName of its top-level form widget
("form root"), which is the root object name of FreeCAD's `.ui` file. Widgets
are looked up by objectName among the descendants of that form root only.
Compiled forms in newer Qt builds replace `::` with `__` in their objectName
(for example `TechDrawGui__TaskBalloon`). Both spellings identify the same
catalog entry; the alias does not expand matching to unrelated widgets.

Notation: "objectName → text" tables list the widget objectName and the exact
JellyJams text. Combo tables list the position, FreeCAD 1.1.4's entry (for
orientation; not checked) and the exact JellyJams entry. Exact strings below
are normative, including punctuation and case. Only the widgets listed are
changed; everything else in a dialog keeps FreeCAD's text.

#### A. Extruded Boss/Base and Extruded Cut (FreeCAD Pad, Pocket)

Form root: `PartDesignGui::TaskPadPocketParameters` (shared by
`PartDesign_Pad` and `PartDesign_Pocket`).

| objectName | JellyJams text |
|---|---|
| `side1Label` | Direction 1 |
| `textLabel1` | End Condition |
| `labelLength` | Depth |
| `labelOffset` | Offset Distance |
| `labelTaperAngle` | Draft Angle |
| `side2Label` | Direction 2 |
| `typeLabel2` | End Condition |
| `labelLength2` | Depth |
| `labelOffset2` | Offset Distance |
| `labelTaperAngle2` | Draft Angle |
| `checkBoxReversed` | Reverse Direction |
| `groupBox` (group box title) | Direction of Extrusion |

Combo `sidesMode` — required count 3:

| # | FreeCAD 1.1.4 | JellyJams |
|---|---|---|
| 0 | One sided | Direction 1 |
| 1 | Two sided | Direction 1 and 2 |
| 2 | Symmetric | Mid Plane |

Combo `changeMode` and combo `changeMode2` (end condition of direction 1 and
direction 2) — required count 5:

| # | FreeCAD 1.1.4 Pad / Pocket | JellyJams |
|---|---|---|
| 0 | Dimension / Dimension | Blind |
| 1 | To last / Through all | Through All |
| 2 | To first / To first | Up To Next |
| 3 | Up to face / Up to face | Up To Surface |
| 4 | Up to shape / Up to shape | Up To Body |

Must stay FreeCAD's: `buttonShapeFace`, `buttonShapeFace2` (FreeCAD switches
their text while picking a face).

#### B. Revolved Boss/Base and Revolved Cut (FreeCAD Revolution, Groove)

Form root: `PartDesignGui::TaskRevolutionParameters` (shared by
`PartDesign_Revolution` and `PartDesign_Groove`).

| objectName | JellyJams text |
|---|---|
| `textLabelMode` | Revolve Type |
| `textLabel1` | Axis of Revolution |
| `labelAngle2` | Direction 2 Angle |
| `checkBoxMidplane` | Mid Plane |
| `checkBoxReversed` | Reverse Direction |

Combo `changeMode` — required count 5:

| # | FreeCAD 1.1.4 | JellyJams |
|---|---|---|
| 0 | Angle | Blind |
| 1 | To last (Revolution) / Through all (Groove) | Through All |
| 2 | To first | Up To Next |
| 3 | Up to face | Up To Surface |
| 4 | Two angles | Two angles |

#### C. Mate (FreeCAD Assembly Joint)

Form root: `TaskAssemblyCreateJoint` (opened by the Assembly joint-creation
commands and when editing a joint).

| objectName | JellyJams text |
|---|---|
| `PushButtonReverse` | Flip Mate Alignment |

Combo `jointType` — required count 13 (FreeCAD 1.1's joint-type order):

| # | FreeCAD 1.1 joint type | JellyJams |
|---|---|---|
| 0 | Fixed | Lock |
| 1 | Revolute | Hinge |
| 2 | Cylindrical | Concentric |
| 3 | Slider | Slider |
| 4 | Ball | Ball |
| 5 | Distance | Coincident / Distance |
| 6 | Parallel | Parallel |
| 7 | Perpendicular | Perpendicular |
| 8 | Angle | Angle |
| 9 | RackPinion | Rack Pinion |
| 10 | Screw | Screw |
| 11 | Gears | Gear |
| 12 | Belt | Belt |

Must stay FreeCAD's: `distanceLabel` (FreeCAD switches it between Distance,
Radius, Pitch, ... depending on the joint type), `offset1Button`,
`offset2Button`.

#### D. Insert Components (FreeCAD Assembly Insert Link)

Form root: `TaskAssemblyInsertLink`.

| objectName | JellyJams text |
|---|---|
| `openFileButton` | Browse... |

No combos.

#### E. Standard 3 View / Projected Views (FreeCAD TechDraw projection group)

Form root: `TechDrawGui::TaskProjGroup` (opened by `TechDraw_ProjectionGroup`
and when editing a projection group).

| objectName | JellyJams text |
|---|---|
| `directionGroupbox` (group box title) | Orientation |
| `secondaryProjGroupbox` (group box title) | Projected Views |
| `label_7` | Type of projection |

Combo `cmbScaleType` — required count 3: (0) Page -> **Sheet scale**,
(1) Automatic -> **Automatic**, (2) Custom -> **Custom**. "Custom" stays
"Custom" because FreeCAD compares the section dialogs' text with it (2.4).

Combo `projection` — required count 3: (0) First angle -> **First angle**,
(1) Third angle -> **Third angle**, (2) Page -> **Sheet**.

Tool tips of the ten view check boxes `chkView0` … `chkView9` (no count
rule). A tool tip is replaced only when FreeCAD's current tool tip is one of
these texts; any other tool tip (for example `Front`, `Top`, `Left`) stays
FreeCAD's:

| FreeCAD's current tool tip | JellyJams tool tip |
|---|---|
| `FrontTopLeft` or `LeftFrontTop` | Isometric (front top left) |
| `FrontTopRight` or `RightFrontTop` | Isometric (front top right) |
| `FrontBottomLeft` or `LeftFrontBottom` | Isometric (front bottom left) |
| `FrontBottomRight` or `RightFrontBottom` | Isometric (front bottom right) |
| `Rear` | Back |

Must stay FreeCAD's: `lePrimary`.

#### F. Section View

Form root: `TechDrawGui::TaskSectionView` (opened by `TechDraw_SectionView`).

| objectName | JellyJams text |
|---|---|
| `label_2` | Label |
| `pbUpdateNow` | Rebuild |

Combo `cmbScaleType` — required count 3: Sheet scale / Automatic / Custom (as E).

Scale-field fix (see 2.4): scale type combo `cmbScaleType`, number field `sbScale`.

Must stay FreeCAD's: `lPendingUpdates`.

#### G. Detail View

Form root: `TechDrawGui::TaskDetail` (opened by `TechDraw_DetailView`).

| objectName | JellyJams text |
|---|---|
| `label_7` | Label |

Combo `cbScaleType` — required count 3: Sheet scale / Automatic / Custom.
No scale-field fix for this dialog.

Must stay FreeCAD's: `pbDragger`.

#### H. Aligned Section (FreeCAD complex section)

Form root: `TechDrawGui::TaskComplexSection` (opened by `TechDraw_ComplexSection`).

| objectName | JellyJams text |
|---|---|
| `label_2` | Label |
| `pbUpdateNow` | Rebuild |

Combo `cmbScaleType` — required count 3: Sheet scale / Automatic / Custom.

Scale-field fix (see 2.4): combo `cmbScaleType`, number field `sbScale`.

Must stay FreeCAD's: `lPendingUpdates`.

#### I. Dimension properties (FreeCAD TechDraw dimension edit dialog)

Form root: `TechDrawGui::TaskDimension` (opened when editing a TechDraw dimension).

| objectName | JellyJams text |
|---|---|
| `gbTolerancing` (group box title) | Primary Value |
| `cbArbitrary` | Override value |
| `label_9` | Unit Precision |
| `cbReference` | Add Parentheses |
| `gbFormatting` (group box title) | Tolerance/Precision |
| `cbEqualTolerance` | Symmetric |
| `cbTheoreticallyExact` | Basic |
| `label_2` | Maximum Variation |
| `label_8` | Minimum Variation |

No combos.

#### J. Balloon

Form root: `TechDrawGui::TaskBalloon` (opened when editing a balloon).

| objectName | JellyJams text |
|---|---|
| `label` | Balloon text |
| `label_3` | Style |
| `label_4` | Arrow style |
| `label_9` | Leader |
| `label_8` | Leader thickness |
| `label_6` | Bent leader length |

FreeCAD 26.3 equivalents: `lText` -> Balloon text, `lBShape` -> Style,
`lSymbol` -> Arrow style, `lWidth` -> Leader thickness, `lKink` -> Bent leader
length, and the checkable group `gbLeader` -> Leader. The group's checked state
is unchanged. The older `comboLineVisible` is absent on that host.

Combo `comboBubbleShape` — required count 8:
(0) Circular -> **Circular**, (1) None -> **None**, (2) Triangle -> **Triangle**,
(3) Inspection -> **Inspection**, (4) Hexagon -> **Hexagon**, (5) Square ->
**Box**, (6) Rectangle -> **Rectangle**, (7) Line -> **Underline**.

Combo `comboLineVisible` — required count 2: (0) -> **No Leader**,
(1) -> **Leader**.

#### K. Note (FreeCAD rich text annotation)

Form root: `TechDrawGui::TaskRichAnno`.

| objectName | JellyJams text |
|---|---|
| `label_3` | Border |
| `label_4` | Line color |
| `label_5` | Line thickness |
| `label_6` | Line style |

FreeCAD 26.3 equivalents: the checkable `gbFrame` group -> Border,
`label_colorThickness` -> Line color, `label_frameThickness` -> Line thickness,
and `label_patternThickness` -> Line style. Checked state is unchanged.

Combo `cFrameStyle` — required count 6: (0) NoLine -> **None**,
(1) Continuous -> **Solid**, (2) Dash -> **Dashed**, (3) Dot -> **Dot**,
(4) DashDot -> **DashDot**, (5) DashDotDot -> **DashDotDot**.

#### L. Leader line

Form root: `TechDrawGui::TaskLeaderLine` (opened by `TechDraw_LeaderLine`).

| objectName | JellyJams text |
|---|---|
| `label` | Line color |
| `label_5` | Line thickness |
| `label_6` | Line style |

Combo `cboxStyle` — required count 6: (0) No line -> **No line**,
(1) Continuous -> **Solid**, (2) Dash -> **Dashed**, (3) Dot -> **Dot**,
(4) DashDot -> **DashDot**, (5) DashDotDot -> **DashDotDot**.

Must stay FreeCAD's: `pbTracker` (FreeCAD rewrites its text to show the
pick/edit state).

#### M. Area Hatch (FreeCAD TechDraw Hatch)

Form root: `TechDrawGui::TaskHatch` (opened by `TechDraw_Hatch`).

| objectName | JellyJams text |
|---|---|
| `label` | Pattern |
| `label_2` | Scale |
| `label_4` | Angle |

No combos.

#### N. Centerline

Form root: `TechDrawGui::TaskCenterLine`.

| objectName | JellyJams text |
|---|---|
| `label` | Line color |
| `label_5` | Line thickness |
| `label_6` | Line style |

No combos.

#### O. Weld Symbol

Form root: `TaskWeldingSymbol` (no namespace prefix).

| objectName | JellyJams text |
|---|---|
| `cbFieldWeld` | Field/Site |
| `cbAltWeld` | Stagger |

Must stay FreeCAD's: `pbArrowSymbol`, `pbOtherSymbol` (FreeCAD writes the
chosen symbol's name into these buttons). No combos.

#### P. Surface Finish

Form root: `TechDrawGui::TaskSurfaceFinishSymbols`.

| objectName | JellyJams text |
|---|---|
| `lbAngle` | Angle |

#### Q. Line Format (FreeCAD TechDraw line decoration)

Form root: `TechDrawGui::TaskLineDecor` (opened by `TechDraw_DecorateLine`,
which is also what JellyJams' ribbon command `JellyJams_LineFormat` opens).

| objectName | JellyJams text |
|---|---|
| `label_15` | Line thickness |
| `label_14` | Line color |
| `label_6` | Line style |
| `label` | Hide/Show Edges |

Combo `cb_Visible` — required count 2: (0) -> **Hide**, (1) -> **Show**.
In FreeCAD 26.3, `cb_Visible` is a checkbox: its label becomes **Show Edges**,
with its checked state unchanged. It is not processed as a combo box.

Plus the line-weight presets row, section 2.5.

### 2.4 Scale-field fix (Section View, Aligned Section)

FreeCAD's Section View and complex-section dialogs decide whether the custom
scale number field is editable by comparing the displayed text of the scale
type combo with the word "Custom". That comparison is fragile (it fails with
a non-English UI). JellyJams therefore enforces, in the Section View
(`TechDrawGui::TaskSectionView`) and Aligned Section
(`TechDrawGui::TaskComplexSection`) dialogs only:

- If the scale type combo `cmbScaleType` is enabled and its current index is
  2 (Custom), and the number field `sbScale` is disabled, JellyJams enables
  `sbScale`.
- In every other situation it does nothing (it never disables the field and
  never changes the combo).
- If either widget is missing, nothing happens.

The "Custom" entry text itself is kept as "Custom" so FreeCAD's own comparison
continues to work in English.

### 2.5 Line-weight presets in the Line Format dialog

When the `TechDrawGui::TaskLineDecor` form is open and JellyJams processes it,
JellyJams adds one extra row to the form, in addition to the relabeling:

- Row widget objectName: **`JellyJamsLineWidthPresets`** (its label and drop-down are
  named `JellyJamsLineWidthPresetsLabel` and `JellyJamsLineWidthPresetsCombo`).
- Contents, left to right: a label reading **ISO 128 preset** and a drop-down
  that takes the remaining width.
- Drop-down entries, in this order: **–** (placeholder, U+2013), **0.13 mm**,
  **0.18 mm**, **0.25 mm**, **0.35 mm**, **0.5 mm**, **0.7 mm**, **1 mm**
  (ISO 128-2 line thicknesses in millimetres; period as decimal separator
  regardless of locale; trailing zeros and a trailing decimal point dropped).
- Placement: inserted at position 1 of the form root's top-level layout (after
  its first item, i.e. directly below the dialog's field grid). Box layouts
  and form layouts are supported.
- Precondition: the dialog's thickness field (objectName `dsb_Weight`, a
  FreeCAD `Gui::QuantitySpinBox`) exists. If it does not, no row is added.
  If the form has no box or form layout at its top level, no row is added
  (never leave an unplaced, overlapping widget).
- Exactly once per dialog instance: if the form already contains a child named
  `JellyJamsLineWidthPresets`, nothing is added. A newly opened dialog (new form) gets
  its own single row.
- Initial selection: the entry whose value equals the thickness field's
  current value (tolerance 1e-6 mm); otherwise, or if the value cannot be
  read, the placeholder. Creating the row and setting this initial selection
  must not change the thickness field.
- When the user picks an ISO entry, the thickness field is set to that value
  in millimetres through the spin box's Qt property `rawValue`, so that
  FreeCAD's dialog takes the value immediately exactly as if typed (the line
  preview on the sheet updates live, and OK applies it as usual). Picking the
  placeholder changes nothing. Re-picking the already selected entry sets the
  value again (harmless).
- The drop-down is not required to follow later manual edits of the thickness
  field.
- The row appears in any `TechDrawGui::TaskLineDecor` dialog opened while
  JellyJams is active, whether opened through `JellyJams_LineFormat` or directly
  through `TechDraw_DecorateLine`.

---

## 3. Triggers and timing

- **Start**: when the JellyJams workbench is activated (its `Activated()`),
  the dialog-terms service starts. Starting is idempotent: activating again
  while it already runs must not create a second watcher or double the work.
- **Stop**: when the JellyJams workbench is deactivated (its `Deactivated()`),
  the service stops. Dialogs opened after that show FreeCAD's own texts.
  Already relabeled widgets in a dialog that is still open when leaving are
  not required to be reverted; they disappear naturally when FreeCAD closes
  that dialog (FreeCAD builds a fresh form on every open). Reverting is
  allowed but not required.
- **Re-activation**: a dialog that was opened outside JellyJams and is still
  open when the user switches to JellyJams is relabeled within one interval.
- **Check interval**: while the service runs, a check happens every
  **250 ms** on the GUI thread. Consequences that must hold:
  - A newly opened dialog shows the SolidWorks terms within about 0.25 s
    (tester threshold: within 1 s).
  - If FreeCAD rewrites a listed text while the dialog is open (e.g. when the
    user switches a mode and FreeCAD resets labels, combo entries or the
    projection tool tips), the SolidWorks term is restored within one
    interval.
- **Gate**: each check first makes sure JellyJams is the active workbench,
  then asks FreeCAD whether a task dialog is active
  (`FreeCADGui.Control.activeDialog()`). If none is active, the check ends
  immediately without scanning any widgets (must be cheap: no widget-tree
  search when no dialog is open).
- **Scope of search**: when a dialog is active, all widgets anywhere under the
  FreeCAD main window (`FreeCADGui.getMainWindow()`) whose objectName equals
  one of the form-root names of section 2.3 are processed; there can be more
  than one matching form at a time and each is processed. This must work
  whether the Tasks panel is docked, floating, combined with the model tree, or
  shown in FreeCAD's overlay mode.
- **No needless writes**: a text, entry or tool tip is written only if it
  differs from the target. A second pass over an already relabeled dialog
  changes nothing (no flicker, no repaint storms, an open combo drop-down list
  is not disturbed or closed by the periodic check).

---

## 4. FreeCAD state read or changed

Read:
- `FreeCADGui.activeWorkbench().name()` — whether JellyJams is active.
- `FreeCADGui.Control.activeDialog()` — whether any task dialog is open.
- `FreeCADGui.getMainWindow()` and its descendant widgets, by objectName.
- Widget texts / titles / tool tips / combo entry texts and counts, combo
  current index and enabled state, `sbScale` enabled state, `dsb_Weight` Qt
  property `rawValue`.

Changed (transient GUI state only, inside FreeCAD's dialogs):
- Text of labels/buttons/check boxes/radio buttons, titles of group boxes,
  display text of combo entries, tool tips of `chkView0`..`chkView9`.
- `sbScale` enabled state (section 2.4).
- A child widget `JellyJamsLineWidthPresets` added to the `TechDrawGui::TaskLineDecor`
  form; when the user picks a preset, the `rawValue` property of `dsb_Weight`.

Not touched by this area:
- No FreeCAD parameters (nothing under `User parameter:BaseApp/Preferences`,
  nothing under `User parameter:BaseApp/Preferences/Mod/JellyJams`).
- No document objects or properties; no custom properties in users' files.
- No FreeCAD commands are registered or run by this area (the `JellyJams_LineFormat`
  command that opens `TechDraw_DecorateLine` belongs to the line-format area).
- No docks, toolbars or stylesheets.

Public names used (exact): form roots `PartDesignGui::TaskPadPocketParameters`,
`PartDesignGui::TaskRevolutionParameters`, `TaskAssemblyCreateJoint`,
`TaskAssemblyInsertLink`, `TechDrawGui::TaskProjGroup`,
`TechDrawGui::TaskSectionView`, `TechDrawGui::TaskDetail`,
`TechDrawGui::TaskComplexSection`, `TechDrawGui::TaskDimension`,
`TechDrawGui::TaskBalloon`, `TechDrawGui::TaskRichAnno`,
`TechDrawGui::TaskLeaderLine`, `TechDrawGui::TaskHatch`,
`TechDrawGui::TaskCenterLine`, `TaskWeldingSymbol`,
`TechDrawGui::TaskSurfaceFinishSymbols`, `TechDrawGui::TaskLineDecor`; widget
objectNames as listed in 2.3; JellyJams objectName `JellyJamsLineWidthPresets`.

---

## 5. Persistence and restore

- Nothing is persisted. All changes live only in the widgets of currently open
  FreeCAD dialogs and vanish when those dialogs close.
- Therefore no exact-restore record, no crash-recovery step at startup and no
  quit handling are needed for this area. A crash or quit while a relabeled
  dialog is open leaves no trace in `user.cfg` or in any document.
- The FreeCAD document produced by a dialog is identical to what FreeCAD
  produces without JellyJams for the same user choices (relabeling never
  changes indices, values or properties). The only document-affecting action
  is the user's explicit pick of a thickness preset, which is equivalent to
  typing that value into FreeCAD's thickness field.

---

## 6. Edge cases and failure handling

- **Different FreeCAD version**: a combo with an unexpected entry count stays
  entirely FreeCAD's (section 2.2). A missing widget or missing form root is
  skipped silently. Other widgets of the same dialog are still processed.
- **Unknown projection tool tip**: a `chkView*` tool tip that is not in the
  table of 2.3 E stays FreeCAD's.
- **Widget-level errors** (e.g. a widget being destroyed while processed, a
  widget of an unexpected type): skip that widget, continue with the rest of
  the dialog and with other dialogs.
- **Check-level errors**: never raised into FreeCAD, never shown as a popup,
  never written as a warning/error during normal operation; at most written to
  FreeCAD's console at Log level (`FreeCAD.Console.PrintLog`), which is hidden
  by default, and only once per widget or dialog.
- **Start failure**: if the service cannot be started, a warning is written to
  the Report view saying that task dialogs keep FreeCAD's labels, and the rest
  of the workbench activation continues normally.
- **State-signalling widgets** (section 2.3, "must stay FreeCAD's") are never
  written, so FreeCAD's state feedback remains readable.
- **Relabeling does not change behavior**: the current selection of every
  combo stays the same index; FreeCAD's mode-dependent show/hide of widgets
  continues to work (e.g. choosing "Direction 1 and 2" in the Pad dialog still
  reveals FreeCAD's direction-2 controls).
- **Line presets**: missing `dsb_Weight` or missing layout -> no row; reading
  the current thickness fails -> placeholder preselected; never a second row in
  the same dialog.
- **Scale fix**: never disables anything; does nothing for other scale types.
- **Leaving the workbench while a dialog is open**: no error; the dialog keeps
  working; see section 3.

---

## 7. Acceptance criteria

Unless stated otherwise: FreeCAD 1.1.4 (English UI), JellyJams workbench
active, a new document. "Within 1 s" means visible within one second after the
dialog appears.

1. Sketch a closed profile in a PartDesign Body and run `PartDesign_Pad`.
   Within 1 s the Tasks panel shows "Direction 1", "End Condition", "Depth",
   "Offset Distance", "Draft Angle", "Reverse Direction", and the group box
   title "Direction of Extrusion" (each where FreeCAD shows that widget). The
   label in front of the sides drop-down keeps FreeCAD's text.
2. In the same dialog the end-condition drop-down (`changeMode`) lists exactly
   Blind, Through All, Up To Next, Up To Surface, Up To Body; the sides
   drop-down (`sidesMode`) lists Direction 1, Direction 1 and 2, Mid Plane.
3. Choosing "Direction 1 and 2" shows FreeCAD's second-direction controls, now
   labeled "Direction 2", "End Condition", "Depth"; `changeMode2` lists the
   same five end conditions. Choosing "Mid Plane" produces a symmetric pad.
   OK creates the same Pad (same property values, e.g. `Type`, `Length`) as
   FreeCAD does without JellyJams for the same choices.
4. `PartDesign_Pocket` shows the same terms; its end-condition position 1
   reads "Through All" and selecting it yields FreeCAD's "Through all" pocket.
5. `PartDesign_Revolution` and `PartDesign_Groove` show "Revolve Type",
   "Axis of Revolution", "Mid Plane", "Reverse Direction", and the
   end-condition list Blind, Through All, Up To Next, Up To Surface,
   Two angles; selecting "Two angles" reveals FreeCAD's second angle,
   labeled "Direction 2 Angle".
6. With the end-condition drop-down list expanded for 5 s, the list neither
   flickers nor closes, and the selected entry does not change.
7. Mode-change resilience: switching end conditions back and forth in an open
   Pad dialog never leaves a listed widget showing FreeCAD's original text for
   longer than 1 s.
8. Safety rule: switch to the PartDesign workbench, open a Pad dialog (FreeCAD
   texts visible), and in the Python console append one extra item to the
   combo box named `changeMode` inside the form
   `PartDesignGui::TaskPadPocketParameters`. Switch to JellyJams with the
   dialog still open. Within 1 s the labels and `sidesMode` show SolidWorks
   terms, while all six entries of `changeMode` (FreeCAD's five plus the
   added one) keep their texts unchanged.
9. Leaving: with JellyJams active, switch to PartDesign, then open a Pad
   dialog: FreeCAD's original texts ("Side 1", "Dimension", ...) are shown and
   stay unchanged for at least 5 s.
10. Re-entering: switch back to JellyJams (twice in a row if possible); the
    next Pad dialog shows SolidWorks terms; no duplicated rows, no errors in
    the Report view.
11. Assembly: in an assembly, create a joint. The joint-type drop-down lists
    Lock, Hinge, Concentric, Slider, Ball, Coincident / Distance, Parallel,
    Perpendicular, Angle, Rack Pinion, Screw, Gear, Belt; the reverse button
    reads "Flip Mate Alignment". Changing the joint type still changes the
    distance label the way FreeCAD does, i.e. `distanceLabel` is never
    overwritten. The created joint is of the type matching the selected
    position.
12. The Assembly Insert Link dialog shows the button "Browse...".
13. TechDraw: on a page, run `TechDraw_ProjectionGroup` for a body. The dialog
    shows "Type of projection", "Projected Views", "Orientation"; scale type
    lists Sheet scale, Automatic, Custom; projection lists First angle,
    Third angle, Sheet. Hovering the isometric view check boxes shows tool
    tips such as "Isometric (front top left)", the rear view box shows
    "Back", and the other boxes keep FreeCAD's tool tips. After changing the
    projection type, the isometric tool tips are translated again within one
    interval.
14. `TechDraw_SectionView`: labels "Label" and the button "Rebuild".
    Selecting scale type "Custom" makes the scale number field editable;
    selecting "Sheet scale" never enables it through JellyJams.
15. `TechDraw_DetailView` shows "Label" and scale types Sheet scale,
    Automatic, Custom.
16. `TechDraw_ComplexSection` shows "Label" and "Rebuild"; the "Custom" scale
    type makes the scale field editable.
17. Editing a dimension shows "Primary Value", "Override value", "Unit
    Precision", "Add Parentheses", "Tolerance/Precision", "Symmetric",
    "Basic", "Maximum Variation" and "Minimum Variation".
18. Editing a balloon shows "Balloon text", "Style", "Arrow style", "Leader",
    "Leader thickness", "Bent leader length", and shapes Circular, None,
    Triangle, Inspection, Hexagon, Box, Rectangle, Underline; the leader
    visibility list reads No Leader, Leader.
19. Rich text annotation: "Border", "Line color", "Line thickness", "Line
    style"; frame list None, Solid, Dashed, Dot, DashDot, DashDotDot. Leader
    line: "Line color", "Line thickness", "Line style"; style list No line,
    Solid, Dashed, Dot, DashDot, DashDotDot; the pick/edit button keeps
    FreeCAD's changing text.
20. Hatch shows "Pattern", "Scale", "Angle"; Centerline shows "Line color",
    "Line thickness", "Line style"; Weld symbol shows "Field/Site" and
    "Stagger", while the arrow-side/other-side symbol buttons keep the symbol
    names FreeCAD writes into them; Surface finish shows "Angle".
21. Line Format: select an edge in a view and run `TechDraw_DecorateLine`
    (or `JellyJams_LineFormat`). Labels read "Line thickness", "Line color", "Line
    style", "Hide/Show Edges"; the visibility list reads Hide, Show. Directly
    below the field grid there is exactly one row "ISO 128 preset" with
    entries –, 0.13 mm, 0.18 mm, 0.25 mm, 0.35 mm, 0.5 mm, 0.7 mm, 1 mm.
    Python check: the form contains exactly one child with objectName
    `JellyJamsLineWidthPresets`, also after waiting 5 s.
22. In that dialog, the preset is preselected to the entry equal to the
    current thickness (or – if none matches). Picking "0.7 mm" sets the
    thickness field to 0.7 mm immediately and the sheet preview updates;
    picking – changes nothing. OK applies 0.7 mm to the edge exactly as if
    typed. Opening the dialog without picking a preset and pressing OK leaves
    the thickness unchanged.
23. Closing and reopening the Line Format dialog again shows exactly one
    presets row.
24. Language independence: set FreeCAD's UI language to a non-English
    language, restart, activate JellyJams, open a Pad dialog: the listed
    widgets show the English SolidWorks terms.
25. No persistence: after exercising criteria 1-23 and quitting, `user.cfg`
    contains no new or changed keys caused by this area (in particular none
    under `User parameter:BaseApp/Preferences/Mod/JellyJams`), and saved
    documents contain no JellyJams properties caused by this area.
26. Quiet operation: during criteria 1-23 the Report view shows no JellyJams
    warnings or errors attributable to dialog terms, and no popups appear.
27. Idle cost: with JellyJams active and no task dialog open, the main window
    is not scanned (verifiable by instrumentation: no widget lookups occur
    while `FreeCADGui.Control.activeDialog()` is false).
