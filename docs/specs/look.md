# JellyJams specification: Look

> **Implemented in:** [`jellyjams/palette.py`](../../jellyjams/palette.py) (palette and WCAG contrast helpers), [`theme.py`](../../jellyjams/theme.py) (main-window stylesheet block), [`viewport.py`](../../jellyjams/viewport.py) (3D background and sketch colors, `OriginalViewColors`); startup recovery wired in [`recovery.py`](../../jellyjams/recovery.py); quit handling in [`quit_guard.py`](../../jellyjams/quit_guard.py).
>
> **Status:** see [../status.md](../status.md)

SolidWorks-like widgets, 3D background and sketch colors following FreeCAD's
light/dark theme, with exact restore and crash recovery.

The owned `JellyJamsAppearances` dock uses the same widget palette. Its tree and
thumbnail gallery explicitly use the palette's selection background and text,
including when unfocused, rather than inheriting native grey selection colours.
These rules stay inside the existing main-window stylesheet block and address
only this JellyJams dock; no additional stylesheet or saved preference is used.

Requirement levels: MUST and MUST NOT are mandatory, SHOULD is recommended (deviations need a reason), MAY is optional.

Product context: JellyJams is a FreeCAD 1.1+ workbench (workbench key/class `JellyJamsWorkbench`, MenuText `JellyJams`) that makes FreeCAD look, feel and operate like SolidWorks. This document covers only the **look** area. Activation and deactivation, the main-window close guard, the ribbon and the relations/mate panels belong to other areas. This document states only what the look area needs from them.

---

## 1. Purpose

When JellyJams is the active workbench, its widgets follow FreeCAD's selected
light/dark appearance while using a SolidWorks-style layout:

1. A **theme-aware widget appearance**. The CommandManager-style ribbon, model
   tree, dock titles and JellyJams PropertyManager panels use the light palette
   over a light native theme and the dark palette over a dark native theme, with
   a blue accent. Floating Orientation and Sketch context popups follow the same
   choice. The viewport uses the same native theme choice.
2. A **matching 3D view background**: a vertical gradient, near-white to pale
   blue-grey in light mode and dark blue-grey in dark mode.
3. **Sketch status colors** in sketch edit mode. In light mode:
   - Under Defined geometry is blue.
   - Fully Defined geometry is black.
   - Over Defined or invalid sketches are red.
   - Construction geometry is a lighter blue.
   - Driving dimensions are black and driven (reference) dimensions are grey.
   - Relation symbols are green.

   Dark mode uses the brighter equivalents in 2.2, including green Fully Defined
   geometry and pale dimension text. Native pale cursor coordinates and overlays
   MUST remain readable against the dark viewport.

The look MUST be **non-destructive**:

- It is layered on top of the user's FreeCAD theme and preferences.
- It is removed when the user leaves the workbench or quits FreeCAD.
- After an unclean exit (crash) it is cleaned up at the next FreeCAD start, so FreeCAD in every other workbench looks exactly as the user configured it.

---

## 2. User-visible behavior and UI

### 2.1 What the user sees

| Situation | Widget theme | 3D background and sketch colors |
|---|---|---|
| JellyJams active | Matching light/dark palette on the listed elements (2.3) | Matching gradient and sketch colors from 2.2 |
| Any other workbench | FreeCAD's own theme, untouched | The user's own FreeCAD preferences |
| FreeCAD quit while JellyJams is active | n/a | The user's own values are what FreeCAD saves |
| Next start after a crash while active | n/a | The user's own values, restored automatically at startup |

All changes apply live. No restart is needed in either direction. The gradient and colors appear in every open 3D view as soon as the workbench is activated.

### 2.2 Palette

Every color the look uses MUST come from the selected light/dark tables below,
and the values MUST be exactly these. Hex values are sRGB `#rrggbb`.

**Widget palette**

| Role | Hex | Where it is used |
|---|---|---|
| Window | `#f2f4f6` | Main window background, separators between docks, dock title bars, unselected dock tabs, background of relation/mate lists |
| Panel | `#ffffff` | Model tree background, selected dock tab, drop-down menus opened from ribbon buttons, the Add Relations / Mate panel |
| Ribbon surface | `#fbfcfd` | CommandManager (ribbon) dock, ribbon pages, selected ribbon tab |
| Ribbon tab strip | `#f2f4f6` | The strip that holds the ribbon tabs, unselected ribbon tabs |
| Border | `#c9ced6` | Ribbon bottom line, ribbon group separators, menu and list frames, underline of panel section headings |
| Text | `#1f2328` | Primary text |
| Text secondary | `#5a6572` | Unselected ribbon tabs, unselected dock tabs, dock titles, panel section headings |
| Text disabled | `#9aa4af` | Disabled (greyed-out) ribbon buttons |
| Accent (SolidWorks blue) | `#1a76c4` | Selected-tab indicator line, hover frames, Add Relations / Mate panel frame, hovered dock separator |
| Accent dark | `#115a99` | Frame of a pressed ribbon button |
| Hover | `#e8f2fb` | Fill of a ribbon button, panel button or tree item under the mouse |
| Pressed | `#cfe6f8` | Fill of a pressed ribbon button; hovered drop-down arrow area of a split button |
| Selection | `#cfe6f8` | Selected tree/list/menu item and checked ribbon button (always with dark Text on top) |
| Tree text | `#1f2328` | Model tree item text |

**Dark widget palette** (same roles; defined in `palette.DARK_WIDGET_PALETTE`)

| Role | Hex |
|---|---|
| Window / Ribbon tab strip | `#191919` |
| Panel | `#202020` |
| Ribbon surface | `#242424` |
| Border | `#505050` |
| Text / Tree text | `#f0f0f0` |
| Text secondary | `#c0c6ce` |
| Text disabled | `#858585` |
| Accent / Accent dark | `#66b8ff` |
| Hover | `#303f4d` |
| Pressed / Selection | `#354d63` |

The native menu bar's effective `QPalette.Window` and `WindowText` luminances
choose the mode at apply/open time: a darker background than foreground means
dark. The menu bar is outside JellyJams' styled areas, so applying twice does not
mistake JellyJams' own background for the native theme. If Qt/the native palette
cannot be read, use the light palette. Theme detection reads no preference and
changes no application stylesheet or palette. FreeCAD owns when its theme changes
take effect; JellyJams refreshes the choice on activation and on popup opening.

**Light 3D view and sketch palette** (FreeCAD parameter values in 4.2)

| Role (SolidWorks term) | Hex |
|---|---|
| Viewport gradient, top | `#fdfdfd` (near-white) |
| Viewport gradient, bottom | `#dfe6ec` (pale blue-grey) |
| Under Defined sketch geometry | `#1a76c4` (blue) |
| Fully Defined sketch geometry | `#000000` (black) |
| Over Defined / invalid sketch | `#ff0000` (red) |
| Construction geometry | `#5c6bd1` (lighter blue) |
| Construction geometry, fully defined | `#454a52` (dark grey) |
| Driving dimension | `#000000` (black) |
| Driven (reference) dimension | `#6b7178` (grey) |
| Relation symbols | `#2a8048` (green) |

**Dark 3D view and sketch palette** (`palette.DARK_VIEWPORT_PALETTE`)

| Role | Hex |
|---|---|
| Viewport gradient, top | `#20252b` |
| Viewport gradient, bottom | `#14181d` |
| Under Defined sketch geometry | `#66b8ff` |
| Fully Defined sketch geometry | `#8cff5b` |
| Over Defined / invalid sketch | `#ff7a7a` |
| Construction geometry | `#a6b4ff` |
| Construction geometry, fully defined | `#aeb6c2` |
| Driving dimension | `#f0f0f0` |
| Driven (reference) dimension | `#b9c3cf` |
| Relation symbols | `#7bdb9b` |

`theme.is_dark()` supplies the same native-palette decision to widgets and the
viewport on activation. No color-mode preference is written. Native cursor text
and view overlays retain FreeCAD's own theme colors.

Maintainability requirement: the palette values MUST be defined once and reused everywhere they appear. Changing a palette entry MUST change every element that uses that role. Other JellyJams areas that draw their own floating widgets, such as a create-sketch pop-up, SHOULD take their colors from this palette: Panel for the background, Border for the frame.

### 2.3 Styled elements

Only the elements below are restyled. Each rule MUST be scoped so it reaches nothing else; section 2.4 lists what stays untouched. Pixel dimensions marked "about" are design targets. Colors, line widths and the indicator thickness are exact.

**A. CommandManager (ribbon)**

The ribbon is a dock with objectName `JellyJamsCommandManager` containing a tab widget with objectName `JellyJamsCommandManagerTabs`. The tabs sit below the buttons.

| Element | Normal | Hover | Selected / pressed | Disabled |
|---|---|---|---|---|
| Ribbon dock and every ribbon page | Ribbon surface background | – | – | – |
| Tab-widget pane | Ribbon surface background; no frame except a 1 px Border line along its bottom edge | – | – | – |
| Tab strip | Ribbon tab strip background | – | – | – |
| Ribbon tab | Tab strip background, Text secondary; no frame; a 2 px transparent indicator along the bottom edge; padding about 3 px vertical / 14 px horizontal; minimum width 60 px | Text color becomes Text | Ribbon surface background, Text color, 2 px Accent indicator along the bottom edge | – |
| Ribbon button (any tool button inside `JellyJamsCommandManagerTabs`) | Transparent background, Text color, 1 px transparent frame, 3 px corner radius, padding about 2 px / 4 px, label font 8 pt | Hover fill, 1 px Accent frame | Pressed: Pressed fill and 1 px Accent dark frame. Checked: Selection fill and 1 px Accent frame | Text disabled |
| Split button (tool button in Qt `MenuButtonPopup` mode) | As a ribbon button, but with about 16 px right padding for the arrow; the arrow sub-control has no frame and is about 12 px wide | Arrow area gets the Pressed fill | – | – |
| Drop-down menu opened from a ribbon button | Panel background, Text color, 1 px Border frame; items padded about 4 px top/bottom, 18 px right, 8 px left | – | Highlighted item: Selection fill, Text color | – |
| Group separator (QFrame objectName `JellyJamsGroupDivider`) | Vertical line, 1 px wide, Border color; margins about 4 px top/bottom and 3 px left/right | – | – | – |

**B. JellyJams PropertyManager-style panels**

These are the sketch "Add Relations" panel and the assembly "Mate" panel. Both use the same objectNames: the panel frame `JellyJamsPropertyManager`, title label `JellyJamsPropertyManagerTitle`, section heading label `JellyJamsSectionCaption`, and list `JellyJamsItemList`. Other JellyJams panels, such as drawing sheet properties, MAY reuse `JellyJamsSectionCaption` and then get the same heading look.

| Element | Look |
|---|---|
| Panel frame | Panel background, 1 px Accent frame, 3 px corner radius |
| Labels inside the panel | Text color |
| Title label | Bold, about 2 px bottom padding |
| Section heading label | Text secondary, 1 px Border line underneath, about 4 px top padding |
| List | Window background, Text color, 1 px Border frame. Selected item: Selection fill, Text color |
| Tool buttons inside the panel | Text color, left-aligned label, padding about 2 px / 4 px, 1 px transparent frame, 3 px radius. Hover: Hover fill and 1 px Accent frame |

**C. Main window and docks (all FreeCAD docks: Model, Tasks, Report view, ...)**

| Element | Look |
|---|---|
| Main window background | Window |
| Separators between docks | Window color, about 4 px thick. Hover: Accent |
| Dock title text | Text |
| Dock title bar | Window background, Text secondary, padding about 3 px / 6 px, left-aligned |
| Tabs of tabified docks (tab bars directly owned by the main window, such as "Model / Tasks") | Window background, Text secondary, no frame, 2 px transparent indicator along the top edge, padding about 4 px / 12 px. Hover: Text color. Selected: Panel background, Text color, 2 px Accent indicator along the top edge |

FreeCAD 1.1's `Gui::OverlayTitleBar` child widgets MUST receive Window background
and Text secondary foreground through the main-window stylesheet as well. Styling
only `QDockWidget::title` leaves these custom title painters with the user's dark
theme foreground, which can be unreadable on the light background. No stylesheet
is assigned to a FreeCAD-owned child widget.

**D. FeatureManager-style model tree** (tree views inside the FreeCAD dock with objectName `Model`)

| Element | Look |
|---|---|
| Tree | Panel background, Tree text color, no frame; selection colors Selection (background) and Text (foreground) |
| Item under the mouse | Hover fill |
| Selected item | Selection fill, Text color. This is dark text on a light selection, never white text |

### 2.4 Not restyled (MUST stay exactly as FreeCAD's theme draws them)

- FreeCAD toolbars, menu bar, main menus and status bar.
- Property editor contents, Report view text and Python console.
- Dialogs, including Preferences, and task-panel contents. The exception is the JellyJams panels in 2.3 B.
- The 3D view widget itself. Its background is a FreeCAD setting, see 2.5.
- The stylesheet of any individual widget. JellyJams MUST NOT call `setStyleSheet` on the model tree, on docks, or on any other FreeCAD-owned widget. All styling goes through the one main-window stylesheet block (4.1).

**Theme independence:** every element in 2.3 that gets a text color MUST also get,
from the same block, the background that the text sits on. Each role uses the
selected light/dark palette. Elements outside that scope retain FreeCAD's native
theme, including menus, property contents, console and Start page. A light
JellyJams ribbon/tree/dock surface over a native dark theme is a bug. Floating
JellyJams widgets explicitly set both text and background colors in their own
stylesheets and refresh those colors when reopened.

### 2.5 3D view background

While active, every 3D view shows a **linear, top-to-bottom, two-color gradient**:
`#fdfdfd` to `#dfe6ec` in light mode, `#20252b` to `#14181d` in dark mode. There
is no middle color and no radial gradient. The parameter writes are in 4.2.

### 2.6 Sketch colors (sketch edit mode)

In light mode, a sketch open for editing uses these status colors. In dark mode,
each role uses its dark equivalent in 2.2 against the matching dark background:

| What the user sees | Color |
|---|---|
| Under Defined geometry (edges still free to move) | Blue `#1a76c4` |
| Fully Defined elements, and the whole sketch once fully defined | Black `#000000` |
| Over Defined / conflicting / invalid sketch | Red `#ff0000` |
| Construction geometry | Lighter blue `#5c6bd1` |
| Construction geometry that is fully defined | Dark grey `#454a52` |
| Driving dimension values | Black `#000000` |
| Driven (reference) dimensions | Grey `#6b7178` |
| Relation (constraint) symbols | Green `#2a8048` |

These colors take effect immediately for a sketch already in edit mode, or at the latest when the next sketch is opened for editing. Sketch display outside edit mode is not changed.

### 2.7 Contrast requirement (WCAG 2.x)

Contrast is measured with the W3C WCAG 2.x definitions:

- **Relative luminance** (W3C, https://www.w3.org/TR/WCAG22/#dfn-relative-luminance):
  - Normalize each 8-bit sRGB channel to the range 0–1.
  - Linearize each channel: values ≤ 0.04045 are divided by 12.92. Larger values become ((value + 0.055) / 1.055) raised to the power 2.4.
  - L = 0.2126·R + 0.7152·G + 0.0722·B.
  - WCAG 2.0/2.1 printed the threshold as 0.03928. No 8-bit channel value falls between the two thresholds, so both give identical results for this palette.
- **Contrast ratio** (W3C, https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio): (L1 + 0.05) / (L2 + 0.05), where L1 is the lighter color. The range is 1:1 to 21:1.

Requirements:

1. **Text** (SC 1.4.3 Contrast (Minimum), https://www.w3.org/TR/WCAG22/#contrast-minimum): every text color in 2.3 MUST reach at least **4.5:1** against every background it appears on. All JellyJams theme text is normal-size (ribbon labels are 8 pt), so the 3:1 large-text allowance does not apply.
2. **Disabled text** (Text disabled) is exempt. SC 1.4.3 excludes inactive UI components. It MUST still be visibly lighter than Text.
3. **Non-text indicators** (SC 1.4.11 Non-text Contrast, https://www.w3.org/TR/WCAG22/#non-text-contrast) MUST reach at least **3:1** against the adjacent background. These are the Accent selected-tab indicator, the Accent hover frames, the Accent panel frame and the Accent dark pressed frame. Purely decorative Border lines are exempt.
4. **Sketch colors** in 2.6 SHOULD reach at least **3:1** against both gradient end colors. The current palette meets this.
   Dark-mode driving and reference dimension text MUST reach **4.5:1** against both ends.
5. The project's automated tests MUST compute these ratios from the palette using the W3C formula above, and fail when any pair in 1, 3 or 4 falls below its threshold. That way a later palette tweak cannot silently break legibility.

Reference values for the current palette:

| Foreground on background | Ratio | Required |
|---|---|---|
| Text `#1f2328` on Panel `#ffffff` | 15.80 | 4.5 |
| Text on Ribbon surface `#fbfcfd` | 15.38 | 4.5 |
| Text on Window / Tab strip `#f2f4f6` | 14.33 | 4.5 |
| Text on Hover `#e8f2fb` | 13.94 | 4.5 |
| Text on Selection / Pressed `#cfe6f8` | 12.28 | 4.5 |
| Text secondary `#5a6572` on Panel | 5.93 | 4.5 |
| Text secondary on Ribbon surface | 5.78 | 4.5 |
| Text secondary on Window / Tab strip | 5.38 | 4.5 |
| Accent `#1a76c4` on Panel / Ribbon surface | 4.74 / 4.61 | 3.0 |
| Accent on Window / Tab strip | 4.30 | 3.0 |
| Accent on Hover | 4.18 | 3.0 |
| Accent dark `#115a99` on Pressed | 5.54 | 3.0 |
| Text disabled `#9aa4af` on Ribbon surface | 2.46 | exempt |
| Sketch colors on gradient top / bottom (worst: Over Defined `#ff0000`) | 3.93 / 3.17 | 3.0 |

---

## 3. Triggers and timing

| Event | Look behavior |
|---|---|
| FreeCAD starts (the addon's `InitGui.py` runs), whether or not JellyJams will be activated | **Startup crash recovery** (5.4) runs once. It MUST finish before the first activation of the workbench in that session. That includes autoload, which FreeCAD performs after all `InitGui.py` files have run. |
| JellyJams workbench activated (FreeCAD calls the workbench's `Activated()`) | Apply the widget theme (4.1), then apply the 3D view and sketch parameters (4.2). Each of the two is independent: if one fails, the other still happens, and the rest of activation continues (ribbon, navigation, shortcuts, ...). Within activation, the window-layout snapshot of the layout area comes **before** the theme is applied. |
| JellyJams autoloaded at startup (`Activated()` runs before the main window is shown) | Applying immediately is allowed. Once the main window is shown, exactly one JellyJams block MUST be present and the gradient MUST be visible. A deferred re-apply by the layout area MUST NOT add a second block or a second backup. |
| Activation repeated while already active | No effect: no second block, no new backup, no parameter rewrite. |
| User switches to another workbench (FreeCAD calls `Deactivated()`) | Restore the 3D view and sketch parameters (5.2), then remove the widget theme (5.1), then let the layout area restore the window. Each step is independently guarded. |
| Main window Close event while active (quit), handled by the shared close guard **before** FreeCAD's own close handling | Remove the theme and restore the parameters **before** FreeCAD persists its parameters, so `user.cfg` receives the user's own values. FreeCAD never calls `Deactivated()` on quit. |
| Quit cancelled ("Save changes?" → Cancel) | While the modal prompt is open (`QApplication.activeModalWidget()` is non-null), the look MUST stay removed. Timers keep firing inside the prompt's nested event loop. Once no modal widget is open, the main window is still visible and JellyJams is still the active workbench, the look is applied again: theme block plus parameters plus a fresh backup. The guard re-checks about every 0.4 s. |
| Quit confirmed (Save / Discard) | The look stays removed. FreeCAD saves the user's original values. |
| Crash or forced kill while active | Nothing can run. The next start cleans up (5.4). |

---

## 4. FreeCAD state read or changed

### 4.1 Main-window stylesheet

- Read and written **only** through `FreeCADGui.getMainWindow().styleSheet()` and `.setStyleSheet(...)`. This layers on top of FreeCAD's application-wide theme and reverts cleanly.
- MUST NOT call `QApplication.setStyleSheet` (`QtWidgets.QApplication.instance().setStyleSheet`).
- MUST NOT write any parameter of `User parameter:BaseApp/Preferences/MainWindow`, in particular `StyleSheet`, `Theme` and `OverlayActiveStyleSheet`. Changing them needs a restart and would persist.
- **JellyJams block.** All JellyJams rules form one contiguous block, delimited by the exact marker comments `/* @jellyjams-stylesheet-open */` and `/* @jellyjams-stylesheet-close */`. Each marker is on its own line, the begin marker before the rules and the end marker after them. The block is **appended after** whatever the main-window sheet held before, which is called the *base sheet*. The base sheet's own rules therefore stay in effect, and JellyJams rules override only what they name.
- While active, the sheet MUST contain exactly one begin marker and exactly one end marker. It MUST start with the base sheet unchanged.
- The rules MUST be valid Qt Style Sheet syntax:
  - every selector has one balanced brace pair, with no nesting;
  - every declaration is `property: value`;
  - every color is `#rgb`, `#rrggbb` or `#aarrggbb`;
  - no unreplaced template placeholders remain.

  An automated test MUST check this.
- The stylesheet is in-memory only. FreeCAD does not persist it, so nothing about it is stored on disk.

### 4.2 3D view and sketch parameters

Parameter group: `User parameter:BaseApp/Preferences/View` (`FreeCAD.ParamGet(...)`). The 3D view and the Sketcher react to these keys live.

Exactly these 14 keys are written while active, with exactly these types and values. Colors are FreeCAD packed unsigned 32-bit RGBA, `0xRRGGBBAA`, alpha always `0xFF`.

| Key | Type (ParamGet setter / remover) | Value | Meaning |
|---|---|---|---|
| `Gradient` | Bool (`SetBool` / `RemBool`) | `True` | Linear gradient on |
| `RadialGradient` | Bool | `False` | Not radial |
| `UseBackgroundColorMid` | Bool | `False` | Two-color gradient, no middle color |
| `BackgroundColor2` | Unsigned (`SetUnsigned` / `RemUnsigned`) | `0xFDFDFDFF` = 4261281279 | Gradient top `#fdfdfd` |
| `BackgroundColor3` | Unsigned | `0xDFE6ECFF` = 3756453119 | Gradient bottom `#dfe6ec` |
| `EditedEdgeColor` | Unsigned | `0x1A76C4FF` = 443991295 | Under Defined geometry, blue |
| `FullyConstraintElementColor` | Unsigned | `0x000000FF` = 255 | Fully Defined element, black |
| `FullyConstrainedColor` | Unsigned | `0x000000FF` = 255 | Fully Defined sketch, black |
| `InvalidSketchColor` | Unsigned | `0xFF0000FF` = 4278190335 | Over Defined / invalid sketch, red |
| `ConstructionColor` | Unsigned | `0x5C6BD1FF` = 1550569983 | Construction geometry, lighter blue |
| `FullyConstraintConstructionElementColor` | Unsigned | `0x454A52FF` = 1162498815 | Fully defined construction geometry, dark grey |
| `ConstrainedDimColor` | Unsigned | `0x000000FF` = 255 | Driving dimension, black |
| `NonDrivingConstrDimColor` | Unsigned | `0x6B7178FF` = 1802598655 | Driven (reference) dimension, grey |
| `ConstrainedIcoColor` | Unsigned | `0x2A8048FF` = 713050367 | Relation symbols, green |

The key names were confirmed present in the FreeCAD 1.1.4 binaries. The `Gradient`/`RadialGradient`/`UseBackgroundColorMid`/`BackgroundColor2..4` keys are in `FreeCADGui.dll`; the sketch keys are in `SketcherGui.pyd`. FreeCAD's 3D view gives `Gradient` precedence over the preference page's `Simple` radio button. It uses `BackgroundColor2` as the gradient top and `BackgroundColor3` as the gradient bottom.

**Never touched** in this group by the look area: `Simple`, `BackgroundColor`, `BackgroundColor4`, `SketchEdgeColor`, `ExprBasedConstrDimColor`, `DeactivatedConstrDimColor` and every other key not in the table. `NavigationStyle` lives in the same group but belongs to the navigation area, which has its own independent backup. The look area MUST neither read-modify nor restore it.

Reading prior state: to tell "absent" from "present", use `ParameterGrp.GetContents()`, which lists `(type, name, value)` for every entry in the group. A key counts as present only if an entry with that name **and the type JellyJams writes** exists.

The table above gives light-mode values. In dark mode the same 14 keys and types
are written; the three Bool values stay unchanged and each Unsigned color uses
the corresponding dark role in 2.2, packed as `0xRRGGBBFF`. `managed_keys(dark)`
builds the values; the light-mode `MANAGED_KEYS` retains the stable backup key set.

### 4.3 JellyJams parameter

Group `User parameter:BaseApp/Preferences/Mod/JellyJams`:

| Key | Type | Content |
|---|---|---|
| `OriginalViewColors` | String | Empty or absent means no pending backup. Non-empty means a JSON backup record (format in 5.2). This name is part of the on-disk contract: a record written by any JellyJams version before a crash MUST still be recovered by a later version. |

### 4.4 Qt objectNames this area relies on

These are defined by other areas and MUST match exactly:

- `JellyJamsCommandManager`: the QDockWidget hosting the CommandManager ribbon.
- `JellyJamsCommandManagerTabs`: the QTabWidget inside it.
- `JellyJamsGroupDivider`: the QFrame separators between ribbon groups.
- `JellyJamsPropertyManager`: the QFrame of the Add Relations panel and the Mate panel.
- `JellyJamsPropertyManagerTitle`, `JellyJamsSectionCaption`: QLabels.
- `JellyJamsItemList`: QListWidgets.
- FreeCAD's own model-tree dock: objectName `Model`.

If an object with one of these names does not exist, its rules simply match nothing. That is not an error.

### 4.5 Console output

All look-area messages go to the FreeCAD Report view (`FreeCAD.Console`) and start with `JellyJams: `.

| Situation | Level | Intent |
|---|---|---|
| Applying the theme failed | Error | Theme could not be applied, with the reason |
| Removing the theme failed | Error | Theme could not be removed, with the reason |
| Applying the 3D parameters failed | Warning | 3D background could not be applied, with the reason |
| Restoring the 3D parameters failed | Warning | 3D background could not be reset, with the reason |
| Startup recovery restored a backup | Message | 3D background reset after an unclean exit. The text MUST contain "3D background" and "unclean exit" |
| Startup recovery failed | Warning | Reason given; startup continues |
| Clean startup (no backup) | – | No recovery message at all |

---

## 5. Persistence and restore rules

### 5.1 Stylesheet: exact restore

1. When applying, JellyJams first reads the current main-window sheet. If that sheet already contains a JellyJams block, the block is cut out first; the result is the base sheet. Such a stale block can be left by an earlier failed removal, or by a re-imported copy of the addon in the same session.
   - A complete stale block is everything from the begin marker through the end marker. Trailing whitespace left at the end of the remainder MAY be trimmed.
   - If a begin marker exists **without** a matching end marker, the block is truncated. Everything from the begin marker to the end of the sheet is dropped.
2. Removal when nothing else has touched the sheet: the result MUST be **byte-identical** to the sheet as it was immediately before activation, and no marker may remain.
3. Removal after something else changed the main-window sheet while JellyJams was active:
   - The JellyJams block MUST be removed and no marker may remain.
   - Content outside the block that another party added MUST survive.
   - If the block is no longer present at all, for example because the sheet was replaced wholesale, the current sheet MUST be left unchanged.
4. If JellyJams has no record of the base sheet, for example because its in-memory state was lost, removal strips the block from the current sheet.
5. Removal when the theme is not applied is a no-op. Repeated activate/leave cycles MUST never accumulate blocks or alter the base sheet.

### 5.2 3D view and sketch parameters: exact restore with a persisted backup

**Apply:**

If a pending record lacks any managed key, contains an invalid entry for one, or
records the wrong type, leave all current colors unchanged and warn. Keep the
record intact for recovery. Parameter read failures also preserve the record and
settings; they are not evidence that a key is absent or the JSON is corrupt.

1. If `OriginalViewColors` is already non-empty, it MUST NOT be overwritten. That happens when an earlier session crashed and recovery could not run or failed; the stored record holds the user's true originals. Otherwise, record the prior state of each of the 14 managed keys (present with its value, or absent) and **persist** the record in `OriginalViewColors` **before** changing any managed key.
2. Write the 14 values from 4.2.
3. A second apply while already applied does nothing.

**Restore** (on leave and on quit):

1. If `OriginalViewColors` is empty or absent, change nothing. This also covers leaving after startup recovery already ran.
2. Otherwise, for every key in the record:
   - if it was present, set it back to the recorded value with the recorded type;
   - if it was absent, **remove** it with the matching remover (`RemBool` / `RemUnsigned`). It MUST NOT be set to a "default" value.
3. Only after all keys are restored, clear the record: set `OriginalViewColors` to the empty string, or remove it. Both mean "no pending backup". If restore fails partway, the record MUST stay, so the next start can finish the job.
4. Restore uses the persisted record even if this session never applied anything. A record left by an earlier session is honored on the next leave.

Result after restore: `GetContents()` of the View group lists the same managed keys, with the same types and values, as before activation. All other keys are unaffected.

**Backup record format** (on-disk contract, stable across JellyJams versions). The record is a JSON object:

- Each member name is a managed key name.
- Each member value is a 3-element array: `[type, existedBefore, previousValue]`.
  - `type` is the string `"Bool"` or `"Unsigned"`, matching the FreeCAD `Set…`/`Rem…` method suffix.
  - `existedBefore` is a JSON boolean.
  - `previousValue` is the old value, or `null` when the key was absent.

Example value: `{"Gradient": ["Bool", false, null], "BackgroundColor2": ["Unsigned", true, 3048605951]}`.

JellyJams MUST write this format and MUST accept it when reading.

Known consequence: if the user edits one of the 14 managed settings in Edit → Preferences while JellyJams is active, leaving the workbench resets that setting to its pre-activation value. This is intended. The Preferences page may also show JellyJams' values while active.

### 5.3 Quit

On the main-window Close event, before FreeCAD's own handling and before parameters are persisted, the look is fully removed (5.1, 5.2). The `user.cfg` written at exit therefore contains:

- the user's original View values, with absent keys still absent;
- no non-empty `OriginalViewColors`.

The stylesheet needs no persistence handling.

### 5.4 Startup crash recovery

At every FreeCAD start, during the addon's `InitGui.py` execution and after workbench registration, the look area checks `OriginalViewColors`.

- If it is non-empty, perform the restore from 5.2, then print the recovery message (4.5).
- This MUST happen even if JellyJams is never activated in that session.
- It MUST be independently guarded. A failure here MUST NOT prevent:
  - workbench registration;
  - the other areas' startup recovery (navigation, shortcuts, assembly setting);
  - FreeCAD startup.

---

## 6. Edge cases and failure handling

| Case | Required behavior |
|---|---|
| `getMainWindow()`, `styleSheet()` or `setStyleSheet()` raises | Logged as an error (4.5). The exception never propagates out of activation or deactivation. The 3D parameters and all other activation steps still run. |
| Writing a View parameter raises partway | Logged as a warning. The backup was persisted first, so leaving or the next start can still restore. The workbench stays usable. |
| Restore raises partway | Logged as a warning. The in-memory "applied" state is cleared anyway, so a later apply works. The persisted record is kept for the next leave or startup. |
| `OriginalViewColors` holds unparsable JSON | A warning is logged and the record is cleared, so the user is not stuck with a warning on every start and a blocked apply. No View key is changed. Startup and registration continue. |
| One record entry is malformed (unknown type, wrong arity) | That entry is skipped with a warning. All other entries are restored. The record is then cleared. |
| Backup exists at activation (recovery failed earlier) | The existing record is kept, not overwritten. Values are applied. The next restore returns to the true originals. |
| Key absent before activation | Removed again on restore, never set to a default. |
| Key present with a non-default user value, such as a custom alpha | Restored bit-exactly. |
| Workbench activated twice, or deactivated without having been activated | No duplicate block or backup; no change. |
| Addon present twice under `Mod/` (development symlink), or module re-imported | A stale block is stripped on apply (5.1). There is never more than one block. |
| User's FreeCAD theme is dark | The 2.3 elements and JellyJams popups use the dark widget palette. Native menus, Start page, task contents and editors remain under FreeCAD's dark theme. |
| FreeCAD build lacks one of the sketch keys | Setting an unused key is harmless. It is still recorded and restored exactly. |
| Navigation area changes `NavigationStyle` in the same group | No interaction. Each area backs up and restores only its own keys under its own backup key. |
| Two FreeCAD instances share one `user.cfg` | Out of scope. The last instance to exit writes the file. |

---

## 7. Acceptance criteria

Unless a criterion says otherwise, use these steps:

1. Run FreeCAD 1.1+ with a throwaway config: `FreeCAD.exe -u <scratch>\test_user.cfg -s <scratch>\test_system.cfg`.
2. Start in Part Design.
3. Before activating JellyJams, record:
   - `S0` = `FreeCADGui.getMainWindow().styleSheet()`;
   - `V0` = `GetContents()` of `User parameter:BaseApp/Preferences/View`;
   - `A0` = `QApplication.instance().styleSheet()`;
   - `M0` = `GetContents()` of `User parameter:BaseApp/Preferences/MainWindow`.

"Activate" means `FreeCADGui.activateWorkbench("JellyJamsWorkbench")`, or selecting JellyJams in the workbench selector. "Leave" means activating `PartDesignWorkbench`. Wait about 2 s after each switch.

Criteria 3–8, 16–17 and 19 give light-mode values. Under FreeCAD Dark, substitute
the matching roles in 2.2; criterion 42 checks both modes on a real sketch.

**Theme**

1. After Activate, the main-window sheet contains `/* @jellyjams-stylesheet-open */` exactly once and `/* @jellyjams-stylesheet-close */` exactly once, and it starts with `S0`.
2. After Activate, the application sheet still equals `A0` and the MainWindow parameter group still equals `M0`.
3. With JellyJams active, grab the `JellyJamsCommandManager` dock (`QWidget.grab()`) and sample pixels:
   - ribbon page background is `#fbfcfd`;
   - tab strip background is `#f2f4f6`;
   - the selected tab shows a 2 px `#1a76c4` line along its bottom edge and dark `#1f2328` text;
   - unselected tab text is `#5a6572`;
   - group separators are 1 px `#c9ced6`.
4. Hovering a ribbon button shows a `#e8f2fb` fill with a 1 px `#1a76c4` frame. Pressing it shows `#cfe6f8` with a 1 px `#115a99` frame. A disabled ribbon button (for example a sketch tool with no document open) shows `#9aa4af` text.
5. A split button's drop-down menu has a white background, a 1 px `#c9ced6` frame and dark text. Its highlighted item is `#cfe6f8` with dark text.
6. The model tree (dock `Model`):
   - background is white;
   - a hovered item is `#e8f2fb`;
   - a selected item is `#cfe6f8` with dark `#1f2328` text, not white text;
   - the tree view widget's own `styleSheet()` is unchanged from before activation.
7. Dock title bars and unselected dock tabs are `#f2f4f6` with `#5a6572` text. The selected dock tab is white with a 2 px `#1a76c4` line along its top edge. Hovering the separator between two docks turns it `#1a76c4`.
8. In a sketch, the Add Relations panel (and, in an assembly, the Mate panel) has:
   - a white background with a 1 px `#1a76c4` frame and 3 px rounded corners;
   - a bold title;
   - grey `#5a6572` section headings with a `#c9ced6` underline;
   - lists on `#f2f4f6` with a `#c9ced6` frame and `#cfe6f8` selection.
9. FreeCAD's toolbars, menu bar, property editor, Report view text and the Preferences dialog look the same as in Part Design.
10. After Leave, the main-window sheet is byte-identical to `S0` and contains no marker.
11. Activate and Leave 10 times in a row. After each Activate there is exactly one block. After each Leave the sheet equals `S0`.
12. Run the activation path twice without leaving, for example by calling the workbench's `Activated()` again. There is still exactly one block, and `OriginalViewColors` is unchanged by the second call.
13. Stale block: before Activate, set the main-window sheet to `S0` plus a hand-made block (begin marker, any rule, end marker). After Activate there is exactly one block. After Leave the sheet equals `S0`, apart from at most trailing whitespace.
14. Truncated stale block: like 13 but with only a begin marker and no end marker. After Activate there is exactly one complete block. After Leave no marker remains.
15. Foreign change while active: with JellyJams active, append a harmless rule (for example an empty `QLabel` rule) to the main-window sheet, then Leave. No marker remains and the added rule is still present.

**3D view and sketch colors**

16. After Activate, the View group holds exactly the 14 typed values in 4.2: `Gradient` = True, `RadialGradient` = False, `UseBackgroundColorMid` = False, `BackgroundColor2` = 4261281279, `BackgroundColor3` = 3756453119, `EditedEdgeColor` = 443991295, `FullyConstraintElementColor` = 255, `FullyConstrainedColor` = 255, `InvalidSketchColor` = 4278190335, `ConstructionColor` = 1550569983, `FullyConstraintConstructionElementColor` = 1162498815, `ConstrainedDimColor` = 255, `NonDrivingConstrDimColor` = 1802598655, `ConstrainedIcoColor` = 713050367. No other View key differs from `V0` (ignoring `NavigationStyle`, which the navigation area owns).
17. With a document open, `FreeCADGui.ActiveDocument.ActiveView.saveImage(path, 400, 300, "Current")` after Activate gives a top row of about `#fdfdfd` and a bottom row of about `#dfe6ec` (±3 per channel), changing smoothly from top to bottom. No restart is needed.
18. While active, `OriginalViewColors` in `User parameter:BaseApp/Preferences/Mod/JellyJams` is a non-empty JSON object in the 5.2 format. It has one entry per managed key, and its `existedBefore` flags match `V0`.
19. In a sketch in edit mode with JellyJams active:
    - an unconstrained line is blue `#1a76c4`;
    - fully constraining it turns it black;
    - adding a conflicting constraint turns the sketch red `#ff0000`;
    - a construction line is `#5c6bd1`;
    - a driving dimension is black and a reference (driven) dimension is grey `#6b7178`;
    - constraint symbols are green `#2a8048`.
20. After Leave, `GetContents()` of the View group equals `V0` for every managed key: same presence, type and value. `OriginalViewColors` is empty or absent.
21. Absent keys: before Activate, remove `Gradient`, `RadialGradient` and `UseBackgroundColorMid` (`RemBool`) and `BackgroundColor2` and `InvalidSketchColor` (`RemUnsigned`). Activate, then Leave. Those keys are absent again, not set to defaults.
22. Custom values: before Activate, set `BackgroundColor2` to 123456 and `Gradient` to False. After Activate and Leave they are exactly 123456 and False again.

**Quit and cancel**

23. Activate, then quit FreeCAD with no unsaved documents. In the saved `test_user.cfg` (inspect the XML):
    - the View group's managed keys equal `V0`;
    - `OriginalViewColors` is empty or absent;
    - no JellyJams color values remain.
24. Activate, create an unsaved document, then quit. While the "Save changes?" prompt is open, including for at least 1.5 s:
    - the main-window sheet has no JellyJams marker;
    - the managed View keys equal `V0`.
25. Continuing 24, press Cancel. Within about 1 s after the prompt closes, the sheet has exactly one JellyJams block again, the 14 values are back, and the backup is non-empty.
26. Continuing 24 with Discard instead of Cancel, the saved `user.cfg` meets criterion 23.

**Crash recovery**

27. Activate, run `FreeCAD.saveParameter()` (this writes `user.cfg` while active), then kill the FreeCAD process (`taskkill /F`). The saved `user.cfg` contains JellyJams values and a non-empty `OriginalViewColors`.
28. Start FreeCAD again with the same config and stay in Part Design:
    - the View group's managed keys equal `V0`;
    - `OriginalViewColors` is empty or absent;
    - the Report view shows one message-level `JellyJams: ` line containing "3D background" and "unclean exit".
29. A normal start with no pending backup prints no recovery message.
30. Hand-written record: write `{"Gradient": ["Bool", false, null]}` into `OriginalViewColors` and set `Gradient` to True, then restart. `Gradient` is absent and the record is cleared.
31. Corrupt record: set `OriginalViewColors` to `not json`, then restart. A `JellyJams: ` warning is logged. The workbench still registers and activates normally, the record is cleared, and no View key changed during startup.
32. Leftover backup at activation: with JellyJams not active, write a valid record into `OriginalViewColors` without restarting, as if startup recovery had failed. For example, record `BackgroundColor2` as present with value 123456. Then Activate. The record is not replaced, and Leave restores the record's values (`BackgroundColor2` = 123456).

**Autoload**

33. Set `AutoloadModule` = `JellyJamsWorkbench` in `User parameter:BaseApp/Preferences/General` and restart. Once the main window is visible, the sheet contains exactly one block and the 3D view shows the gradient. Switching to Part Design removes both.

**Failure isolation (automated, headless with stubs)**

34. With a stub main window whose `setStyleSheet` raises, activation logs a `JellyJams: ` error. No exception escapes, the 3D parameters are still applied, and the other activation steps still run.
35. With a stub parameter group whose setter raises on the 5th key, activation logs a warning and the backup record already exists. A subsequent Leave restores the keys that had been changed and clears the record.

**Palette and contrast (automated)**

36. The palette values equal the hex values in 2.2 exactly, case-insensitive.
37. The generated JellyJams rule block passes the syntax checks in 4.1.
38. Every text pair in 2.7 requirement 1 is at least 4.5:1, every non-text pair in requirement 3 is at least 3:1, and every sketch color is at least 3:1 against both gradient ends. All ratios are computed with the W3C relative-luminance formula. The test fails if any pair falls below its threshold.
39. No identifier, objectName, file name or parameter key introduced by this area contains "SolidWorks", in any letter case.
40. With native FreeCAD Dark and FreeCAD Light in separate throwaway profiles,
    the ribbon surface/text, dock titles, Orientation panel and Sketch context popup
    use the matching widget palette. The application stylesheet, native menu colors
    and Theme/StyleSheet preferences remain unchanged during activation and after
    leaving; the main-window stylesheet is restored byte-for-byte.
41. Applying repeatedly under dark, light and dark again never duplicates the
    theme block or changes the original restore target. Dark text/background pairs
    meet 4.5:1 and accent/surface pairs meet 3:1. No mode is persisted by JellyJams.
42. In separate native Dark and Light scratch profiles, open a real sketch with
    unconstrained, blocked and construction lines, a driving dimension and a
    reference dimension. The rendered image MUST contain the matching geometry
    and dimension colors, and background samples MUST match the selected mode.
    After leaving, all 14 managed keys MUST have their original presence/type/value.
    Headless dark-mode apply/restore and fresh-module crash recovery MUST also
    restore custom values and remove originally absent keys exactly.
