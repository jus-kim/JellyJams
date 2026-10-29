# JellyJams specification: Drawing symbols and drawing export

> **Implemented in:** [`jellyjams/surface_finish.py`](../../jellyjams/surface_finish.py) (2.4), [`weld_symbol.py`](../../jellyjams/weld_symbol.py) (2.5, including the arrow-follow watcher), [`drawing_export.py`](../../jellyjams/drawing_export.py) (2.6 to 2.8), [`pdf_merge.py`](../../jellyjams/pdf_merge.py) (2.9), [`line_format.py`](../../jellyjams/line_format.py) (2.10, the command); the line-dialog labels and the ISO 128 presets row live in [`dialog_terms.py`](../../jellyjams/dialog_terms.py); weld pick mode uses [`sheet_pick.py`](../../jellyjams/sheet_pick.py); the double-click hook is in [`sheet_drag.py`](../../jellyjams/sheet_drag.py); icons [`surface_finish.svg`](../../resources/icons/surface_finish.svg), [`weld_symbol.svg`](../../resources/icons/weld_symbol.svg), [`line_format.svg`](../../resources/icons/line_format.svg), [`export_pdf.svg`](../../resources/icons/export_pdf.svg), [`export_dxf.svg`](../../resources/icons/export_dxf.svg).
>
> **Status:** see [../status.md](../status.md)

Area id: `drawing-symbols-export`
Target: FreeCAD 1.1+ (verified against 1.1.4), workbench `JellyJamsWorkbench` (MenuText "JellyJams").
Language: English only. No identifier, objectName, file name or icon file may contain "SolidWorks"; SolidWorks terms in visible labels and tooltips are fine.

This area covers five commands that act on TechDraw drawings:

| Command id | MenuText (ribbon label) | Scope |
|---|---|---|
| `JellyJams_SurfaceFinish` | Surface Finish | ISO 1302 surface texture symbol whose values stay editable after placement |
| `JellyJams_WeldSymbol` | Weld Symbol | ISO 2553 weld symbol, placed by picking points on the sheet; no leader object involved |
| `JellyJams_LineFormat` | Line Format | Style, width, color and visibility of picked drawing lines, plus a row of ISO 128 width presets |
| `JellyJams_SaveAsPDF` | Save as PDF | One PDF file that contains every sheet |
| `JellyJams_SaveAsDXF` | Export DXF (ribbon: Save as DXF) | DXF output, written as one file per sheet |

The key words MUST, SHOULD and MAY are used in their usual sense.

---

## 1. Purpose

Someone arriving from SolidWorks looks for four things on a drawing: annotations that can be reopened and changed, a weld symbol that takes only a couple of picks, a Line Format command for the edges they picked, and a PDF that carries all sheets at once. Stock TechDraw falls short on each:

- `TechDraw_SurfaceFinishSymbols` inserts a fixed graphic; its values are not editable afterwards.
- `TechDraw_WeldSymbol` can only hang off a leader line that already exists.
- The TechDraw Python API writes exactly one sheet per PDF file.
- The line decoration dialog offers no shortcut to the standard ISO 128 widths.

This area closes those gaps with FreeCAD's own document object types only, so a drawing still opens and displays correctly in FreeCAD without JellyJams.

---

## 2. User-visible behavior and UI

### 2.1 Ribbon placement (Drawing tab)

The ribbon itself belongs to the ribbon area. It MUST hold these commands on the **Drawing** tab:

- **Annotation group**: after the Smart Dimension and Note flyouts comes a small-button text stack. It holds **Balloon** (FreeCAD's `TechDraw_Balloon`), **Surface Finish** (`JellyJams_SurfaceFinish`) and **Weld Symbol** (`JellyJams_WeldSymbol`), in that order.
- **Sheet sketch group**: after the icon stack of sheet shapes comes a large button **Line Format** (`JellyJams_LineFormat`), labeled on two lines as "Line" / "Format".
- **Output group** (last group of the Drawing tab): large buttons **Save as PDF** (`JellyJams_SaveAsPDF`, two lines "Save as" / "PDF") and **Save as DXF** (`JellyJams_SaveAsDXF`, two lines "Save as" / "DXF").

Icons: all five are JellyJams-only commands. Each one MUST use a new original icon drawn for this project: a surface finish check mark, a weld symbol (arrow with reference line and fillet triangle), a line with style and thickness swatches, a PDF page and a DXF page. The command's `Pixmap` resource and the ribbon button use the same icon. Third-party icons MUST NOT be bundled.

### 2.2 Command resources and enablement

The tooltip text itself lives in the command class named in the third column; this spec only fixes what it has to tell the user.

| Command | MenuText | Tooltip must convey (source) | Enabled (IsActive) when |
|---|---|---|---|
| `JellyJams_SurfaceFinish` | Surface Finish | The standard (ISO 1302); that ready-made roughness values are offered; that the symbol is edited by double-clicking it on the sheet. (`SurfaceFinishCommand.tooltip`) | There is an active document, it contains at least one `TechDraw::DrawPage`, and no task dialog is open. |
| `JellyJams_WeldSymbol` | Weld Symbol | The standard (ISO 2553); that no leader line is needed; the two picks in their order (welded joint, then reference-line position); that a double-click edits it. (`WeldSymbolCommand.tooltip`) | Same as above. |
| `JellyJams_LineFormat` | Line Format | Which properties it changes (style, width, color) and that edges in a drawing view must be picked beforehand. (`LineFormatCommand.tooltip`) | Same as above. |
| `JellyJams_SaveAsPDF` | Save as PDF | That every sheet ends up in a single PDF and where the default file name comes from (the title block's drawing number). (`ExportPdfCommand.tooltip`) | There is an active document, it contains at least one `TechDraw::DrawPage`, and no task dialog is open. |
| `JellyJams_SaveAsDXF` | Export DXF | The DXF format and the one-file-per-sheet rule. (`ExportDxfCommand.tooltip`) | Same as `JellyJams_SaveAsPDF`. |

IsActive MUST never raise. If anything goes wrong while checking, the command is disabled.

### 2.3 Which sheet a symbol goes on

A new surface finish or weld symbol goes on the "target sheet":

1. If the current selection contains a `TechDraw::DrawPage`, that sheet is the target.
2. Otherwise, if a selected object has a `TechDraw::DrawPage` among its direct parents (`InList`), that sheet is the target.
3. Otherwise the target is the first `TechDraw::DrawPage` in the document's object order.

### 2.4 Surface Finish (ISO 1302)

#### 2.4.1 Creating a new symbol

Click **Surface Finish** with no surface finish symbol selected:

- A new `TechDraw::DrawViewSymbol` is added to the target sheet. Its internal Name base is `SurfaceFinish`. Its initial Label is "Surface Finish"; the tree-naming area later renames it SolidWorks-style ("Surface Finish1", ...).
- Default content:
  - the basic symbol (any manufacturing process allowed, stored key `any`)
  - not all-around
  - field **a** = "Rz 16"
  - all other fields empty
  - rotation 0°
- Position on the sheet, in mm:
  - If a selected object has X/Y coordinates (a drawing view) and is not itself a surface finish symbol, the symbol goes 25 mm right of and 15 mm above that object's X/Y.
  - Otherwise it goes at the sheet center: half the template's Width and Height, or 105 × 148.5 when the sheet has no template or sizes.
- `ScaleType` is set to `Custom`, so the symbol is not scaled with the sheet scale.
- The symbol's view provider `StackOrder` is set to 110, so it draws above the drawing views (the same z-level FreeCAD uses for dimensions).
- The whole creation, plus all edits made before the panel is closed with OK, is one undo step named "Surface Finish".
- The Surface Finish task panel then opens (2.4.3).

#### 2.4.2 Editing an existing symbol

Each of these opens the task panel for an existing surface finish symbol:

- Select the symbol, then click **Surface Finish**. If several are selected, the first in selection order is edited.
- Double-click the symbol on the sheet. This works while the JellyJams workbench is active, no task dialog is open, and no TechDraw tool is running (for example dimensioning or balloon placement). The double-click is consumed. Double-clicks on FreeCAD's own TechDraw objects are left to TechDraw.

An edit session is one undo step named "Edit Surface Finish".

The texts can also be changed without the panel, directly in the property editor under Data › `EditableTexts` (standard FreeCAD behavior for SVG symbols). The panel reads its text fields back from `EditableTexts` each time it opens.

#### 2.4.3 Task panel

- Root widget objectName: `JellyJamsSurfaceFinishForm`. Window title: "Surface Finish". The panel is a form layout with one row per item below, in this order. Row label and entry texts are the strings in `surface_finish.py` (`SurfaceFinishPanel._build`, `SURFACE_TYPES`, `LAY_CHOICES`); the spec fixes keys, values and behavior.

| Row | Control | Content |
|---|---|---|
| Symbol type | non-editable combo | Entries from `SURFACE_TYPES`, keys in this order: `any` (basic symbol, any process), `required` (material removal required), `prohibited` (material removal not allowed). Each entry text must make the process requirement clear. |
| All around | check box, no row label | all-around flag; its text must make clear that it applies to every surface around the outline |
| Field a: parameter and value | editable combo | Quick choices `QUICK_VALUES`, in order: Rz 4, Rz 6.3, Rz 16, Rz 25, Rz 63, Ra 0.8, Ra 1.6, Ra 3.2, Ra 6.3, Ra 12.5. Free text is allowed, and the tooltip must say so. |
| Field b: second requirement | line edit | free text |
| Field c: manufacturing method | line edit | free text; the placeholder shows one example method |
| Field d: surface lay | editable combo | Entries from `LAY_CHOICES`: an empty entry, then the ISO 1302 lay characters `=`, `⊥`, `X`, `M`, `C`, `R`, `P`, each followed by a short explanation of that lay. Picking an entry puts ONLY the lay character (or nothing) into the field, never the explanation. If the field text equals a whole entry text, its character is used. |
| Field e: machining allowance (mm) | line edit | free text; the placeholder shows one example value |
| Rotation (degrees) | editable combo | Choices 0, 90, 180, 270, free numbers allowed. A comma counts as the decimal separator. Text that is not a number means 0. Shown with no trailing zeros (for example "90", "12.5"). |
| Hint | word-wrapped label, no row label | Must tell the user both ways to change the symbol later: double-clicking it on the sheet, and editing its texts in the property editor (Data › EditableTexts). |

- **Live preview**: every change in any control is applied to the symbol at once and the document is recomputed. A failure while applying is logged (log level) and never shown as a popup.
- **OK**: applies the current values once more, commits the undo step and closes the panel.
- **Cancel**: rolls back the undo step and closes the panel, then recomputes. A newly created symbol disappears completely. An edited symbol returns exactly to its earlier state.
- The panel MUST NOT open while another task dialog is open.

#### 2.4.4 Symbol appearance

The symbol is an SVG stored in the object's `Symbol` property. It MUST be drawn in the same coordinate system FreeCAD's own surface finish symbol uses: 1 SVG unit = 1 px, 18 px text in the `osifont` font, black strokes 1 unit wide, no fill. Inserted at the same scale, it then looks the same size as FreeCAD's own symbol.

- **Basic symbol (`any`)**: the ISO 1302 check mark. A short leg comes down from the left to the root point, which touches the surface. A long leg (about 2.5 times as long) rises from the root to the upper right. Both legs are at about 60° to the horizontal. From the top of the long leg a horizontal line runs to the right.
- **`required`**: adds a horizontal bar from the top of the short leg across to the long leg, which closes the V into a triangle.
- **`prohibited`**: adds a circle inscribed in the V, radius about 9 units.
- **All around**: adds a small circle, radius about 6 units, at the corner where the long leg meets the horizontal line. The texts below and above the line then shift right by about 5 units, and the line gets that much longer.
- **Horizontal line length**: adapts to the text. It is at least 30 units, or longer to fit the widest of fields a, b and c (estimated at about 9.25 units per character at 18 px), plus about 8 units of margin.
- **Text positions** (ISO 1302 "additional information" layout):
  - **a** (parameter and value, e.g. "Rz 16"): just below the horizontal line, starting right of the corner.
  - **b** (second requirement): below a.
  - **c** (manufacturing method): above the horizontal line.
  - **d** (surface lay): to the lower right of the root point.
  - **e** (machining allowance): left of the short leg, right-aligned against it.
- **Canvas**: the SVG canvas (width, height, viewBox) MUST cover all geometry and all texts. It grows to the left when e has text, and to the right as the line gets longer.
- **Editable texts**: every field (a, b, c, d, e) is ALWAYS an editable text in the SVG, even when empty, so it can be filled in later in the property editor:
  - each field is a `<text>` element carrying a `freecad:editable` attribute, with the value inside a `<tspan>`
  - the `freecad` prefix is bound to the namespace URI `https://www.freecad.org/wiki/index.php?title=Svg_Namespace`
  - the editable ids are exactly `a`, `b`, `c`, `d`, `e`
  - they MUST appear in the document in exactly this order, because FreeCAD's `EditableTexts` list follows the document order and JellyJams maps it back by position
- Text values MUST be XML-escaped, so `<`, `>` and `&` in user text are safe.
- Rotation is the object's `Rotation` property (degrees). It is not part of the SVG.

### 2.5 Weld Symbol (ISO 2553)

#### 2.5.1 Creating a new symbol: the SolidWorks-style workflow

Click **Weld Symbol** with no weld symbol selected:

1. A new `TechDraw::DrawViewSymbol` is added to the target sheet:
   - internal Name base `WeldSymbol`, initial Label "Weld Symbol" (the tree-naming area later turns it into "Weld Symbol1", ...)
   - `ScaleType` = `Custom` and `Scale` = 1.0, so the symbol always prints at 1:1 in mm
   - view provider `StackOrder` = 110
   - the arrow point starts at the sheet center (as in 2.4.1)
   - the kink (where the arrow line turns into the reference line) starts 14 mm to the right of and 8 mm above the arrow point (`KINK_OFFSET`)
   - default weld data (`DEFAULT_DATA`): a fillet (`fillet`) on the arrow side with throat thickness "a5", nothing on the other side, no marks (all-around, field weld and identification line off) and an empty tail note
2. The creation is one undo step named "Weld Symbol". Every panel edit and placement click up to OK is part of it.
3. The Weld Symbol task panel opens (2.5.3).
4. If the active MDI window is a TechDraw page window (`TechDrawGui::MDIViewPage`), **pick mode** starts on that window:
   - Over the sheet the cursor becomes a crosshair.
   - The status bar shows the first prompt (`TIP_PROMPT`). It must say that this is the first of two steps, ask for the joint the arrowhead should touch, and mention that Esc cancels.
   - **First left click**: the arrow point jumps to the clicked sheet position (mm), and the kink to arrow point + (14 mm right, 8 mm up). The symbol is redrawn and the document recomputed straight away. The status bar switches to the second prompt (`PLACE_PROMPT`): second of two steps, click where the reference line should start, Esc keeps the symbol where it is.
   - **Second left click**: the kink moves to the clicked position and the symbol is redrawn with the arrow still ending exactly on the arrow point. Pick mode ends.
   - **Esc or a right click** at any moment ends pick mode and leaves the symbol unchanged.
   - While pick mode runs, left presses, releases and double-clicks on the sheet belong to pick mode alone: no selection happens and the JellyJams one-click view dragging does not start. Other buttons (the middle button for panning, for example) and the wheel behave as usual.
   - When pick mode ends, crosshair and status message are removed.
   - Without an active page window, pick mode is not started; the panel still opens and the symbol keeps its default position.
5. Pick mode coordinates: a click is converted from the page window's scene coordinates to sheet millimeters:
   - sheet x = scene x / Rez
   - sheet y = −(scene y) / Rez (the scene's y axis points down, the sheet's points up)
   - Rez is the float `Resolution` in parameter group `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`, default 10.0
6. Pick mode also ends when the panel closes (OK or Cancel), when another pick mode starts (there is never more than one), and when the JellyJams workbench is deactivated.

#### 2.5.2 Editing an existing symbol

Same entry points as for the surface finish:

- Select a weld symbol and click **Weld Symbol**, or double-click it on the sheet (conditions as in 2.4.2).
- The panel then runs inside an undo step named "Edit Weld Symbol".
- Pick mode is NOT started automatically when editing.

#### 2.5.3 Task panel

Root widget objectName: `JellyJamsWeldSymbolForm`. Window title: "Weld Symbol". Visible texts are the strings in `weld_symbol.py` (`_SideControls`, `WeldSymbolPanel._build` and the choice tables); this section fixes structure, keys and what each text has to tell the user. The panel is a vertical stack:

1. **Group box for the arrow side** ("Weld on the arrow side") and 2. **group box for the other side** ("Weld on the other side"). Each holds these form rows, in this order:

   | Row label | Control | Content |
   |---|---|---|
   | Symbol | non-editable combo | `WELD_TYPES`. Stored ids in list order: `""` (no weld), `butt_flanged`, `butt_i`, `butt_v`, `butt_hv`, `butt_y`, `butt_hy`, `butt_u`, `butt_j`, `backing_run`, `fillet`, `lap_plug`, `lap_spot`, `lap_seam`, `surfacing`. Butt-joint preparations come first (flanged edges, then the straight-sided grooves, then the curved ones), followed by the backing run, the fillet, the lap-joint symbols and surfacing. The entry texts of the groove preparations begin with their letter designation (I, V, HV, Y, HY, U, J). |
   | Contour | non-editable combo | `CONTOURS`, ids `""`, `flat`, `convex`, `concave` |
   | Finish method | non-editable combo | `TREATMENTS`, ids `""`, `C`, `G`, `M`; every entry shows the process together with its letter. No catch-all "other finish" letter is offered, because there is no established letter for one. |
   | Size | editable combo | Presets `SIZE_PRESETS`, in order: a3, a4, a5, a6, a8, z4, z6, z8, s5, s8, d5, d8, c6. There is no blank preset: an empty field means no size. Any text may be typed. The tooltip must say that the size is written left of the symbol, list the size letters it may start with (a, z, s, d, c) and explain that an empty field means no size. |
   | Length | line edit | free text; the placeholder shows the ISO 2553 length notation (single length, or number × length with the spacing in brackets) with an example |

3. **Group box for marks and tail** ("Marks and tail"):
   - three check boxes, one each for all-around, field (site) weld and the identification line. Each text must name the mark it adds: the circle at the kink, the flag, and the dashed line that carries the other side.
   - a "Tail" line edit; its placeholder gives an example welding process number and an example quality level
4. **Push button** ("Re-pick arrow point and position …"): restarts pick mode at the first click (arrow point). Its changes belong to the panel's open undo step.
5. **Hint** (word-wrapped label). It must convey two facts: dragging the symbol leaves the arrowhead on its point, and a double-click on the symbol brings the panel back.

- On opening, every control shows the stored data (2.5.6). A stored key missing from a combo's list shows as that combo's first ("none") entry.
- **Live preview**: every change redraws the symbol right away, stores the data and recomputes. Failures go to the log at log level, never to a popup.
- **OK**: ends pick mode, applies once more, commits, closes.
- **Cancel**: ends pick mode, rolls back the undo step (a new symbol disappears), recomputes, closes.
- The panel MUST NOT open while another task dialog is open. If the panel cannot open right after a creation, the creation MUST be rolled back, so no half-created symbol is left with a pending undo step.

#### 2.5.4 Arrow follows when the symbol is moved

Whenever a weld symbol's `X` or `Y` changes, the symbol MUST be redrawn so the arrow line still ends exactly at the stored arrow point (`ArrowheadX`, `ArrowheadY`). The arrow point itself never moves. It makes no difference how the move happened: dragging on the sheet, typing in the property editor, a script, or pick mode.

- The redraw runs right after the change (deferred to the next event-loop turn), never re-entrantly. At most one redraw per object is pending; a change caused by the redraw itself MUST NOT trigger another one.
- The redraw first takes over any texts the user changed in `EditableTexts` (see 2.5.6), so property-editor edits survive a move.
- The redraw SHOULD be skipped while the document is restoring (loading) or in an undo/redo, and when the new SVG would be identical. A redraw that changes nothing MUST NOT mark the document modified or disturb the redo stack.
- The redraw SHOULD also run when `ArrowheadX` or `ArrowheadY` changes.
- The document watcher is installed once, when the workbench first initializes in a session. It stays active for the rest of the session even after switching to another workbench, so the data stays consistent. Installing it is idempotent.

#### 2.5.5 Weld symbol appearance

The SVG is stored in `Symbol`. All numbers below are the module constants in `weld_symbol.py`.

**Units, canvas and line style**

- 1 SVG unit = 1 mm; the SVG `width`/`height` carry the `mm` unit.
- The SVG origin (0,0) is the **kink**. The object's `X`/`Y` is the kink's sheet position.
- The canvas (viewBox) MUST be symmetric around the kink, so the kink stays put whatever the arrow length or the texts. It is built from the bounding box of everything drawn, including the arrow point and the estimated text boxes: half-width = the larger horizontal distance of that box from the kink, half-height = the larger vertical distance, each plus 1.5 mm.
- Text boxes are estimated for osifont: 0.55 × font size per character, capital height 0.74 × font size, 0.25 × font size below the baseline.
- The arrow point's offset from the kink in SVG coordinates (y pointing down) is (tipX − X, −(tipY − Y)).
- Strokes are black, 0.25 mm wide (ISO 128 narrow line), with round caps and joins, unfilled. Text is `osifont` at 3.5 mm (ISO 3098 nominal size).

**Reference line and identification line**

- **Reference line**: continuous and horizontal, from the kink to the right. It is at least 16 mm long; otherwise it ends 2 mm past the furthest of: a glyph's right edge, the end of a contour mark, a finishing letter, a length text.
- **Identification line** (only when enabled): dashed, parallel to the reference line and 1 mm **above** it on the sheet. It starts 1.5 mm right of the kink and ends with the reference line. Its pattern is the ISO 128 dashed line: dashes of 12 line widths (3 mm) separated by gaps of 3 line widths (0.75 mm), with butt caps. With the option off, no dashed line exists in the SVG.

**Which side each glyph goes on**

- The **arrow-side** glyph always hangs **below** the continuous reference line.
- The **other-side** glyph stands **above**: on the reference line when the identification line is off, on the dashed identification line when it is on.

**Glyph column and texts**

- Every glyph has an anchor: the upright of a one-sided preparation (`butt_hv`, `butt_hy`, `butt_j`, `fillet`), the middle of every other glyph. Both sides share one anchor column.
- Next to the kink a stretch of bare reference line is kept free: 2.5 mm, or 4 mm (flag length + 0.8 mm) when the field-weld flag is shown.
- The column is the leftmost position at which, on every side with a weld, the glyph's left edge stays clear of that free stretch, with room in between for the size text plus a 0.8 mm gap when there is one.
- The **size** text is right-aligned, ending 0.8 mm left of its glyph's left edge. The **length** text is left-aligned, starting 0.8 mm right of its glyph's right edge.
- Texts sit on their glyph's side of the line with 0.7 mm clearance: below the line the capital tops are 0.7 mm under it, above the line the baseline is 0.7 mm over it.
- A side without a weld type shows empty size and length texts, but both editable elements still exist.

**Glyphs** (unit g = 3.5 mm, the lettering height; x along the line from the anchor, y away from the line; outlines only, never filled; defined once in `GLYPHS`)

| Id | Outline |
|---|---|
| butt_flanged | A stem from the line to 0.5g, then two quarter circles of radius 0.5g that leave its top and curl outward to ±0.5g, ending parallel to the line at height g |
| butt_i | Two uprights of height g, at −0.3g and +0.3g |
| butt_v | Two flanks from one point on the line out to ±0.75g at height g (flank run 0.75 per unit of rise) |
| butt_hv | An upright of height g at the anchor, plus a flank from its foot to 0.75g at height g |
| butt_y | A root stem up to 0.3g, then a V from the stem top out to ±0.525g at height g |
| butt_hy | An upright of height g, plus a flank from 0.3g up the upright out to 0.525g at height g |
| butt_u | A root stem up to 0.3g, then a bowl: a half circle of radius 0.4g whose point nearest the line is the stem top, continued by straight sides at ±0.4g up to height g |
| butt_j | An upright of height g; from 0.3g up the upright, a quarter circle of radius 0.4g turns away from it and continues straight up at 0.4g to height g |
| backing_run | A half circle of radius 0.5g standing on the line |
| fillet | An upright of height g at the anchor and a hypotenuse from its top back to the line at 1.0g (equal legs) |
| lap_plug | A rectangle 1.1g wide and 0.4g high, open toward the line |
| lap_spot | A circle of radius 0.5g touching the line |
| lap_seam | The spot circle plus two lines parallel to the reference line, 0.2g either side of the circle's center, each 1.6g long and centered on it |
| surfacing | Two adjacent half circles of radius 0.35g standing on the line, 1.4g wide in total |

**Contour, finishing, tail and kink marks**

- **Contour** (only on a side with a weld type): a mark 0.5 mm beyond the glyph's far edge. Its chord spans the glyph plus 0.3 mm on each side, widened symmetrically to at least 2.6 mm.
  - flat: a straight line
  - convex: a circular arc with 0.5 mm rise, bulging away from the glyph
  - concave: a circular arc with 0.5 mm rise whose ends sit 0.5 mm further out, so it dips back toward the glyph
- **Finishing letter** (only on a side with a weld type and a chosen letter):
  - plain text at 0.8 × 3.5 mm, centered on the middle of the glyph, 0.6 mm beyond the contour mark (or beyond the glyph when there is no contour)
  - not an editable text
  - meanings: C = chipping, G = grinding, M = machining (the only letters offered)
- **Tail**:
  - Only for a non-empty tail note, a fork is drawn at the right end of the reference line: two 3.2 mm lines at ±45° (a 90° opening).
  - The tail text starts 0.9 mm past the fork tips (0.9 mm past the line end while the note is empty) and is vertically centered on the reference line.
  - The tail editable text element always exists, even when empty.
- **All around**: a circle of radius 1.2 mm centered on the kink.
- **Field weld**: a staff 5.5 mm straight up from the kink carrying, at its top, a filled triangular flag that points right, 3.2 mm long and 2.2 mm deep.
- **Arrow**: a straight line from the kink toward the arrow point, finished by a filled closed arrowhead 2.8 mm long with a 30° included angle whose point is exactly the arrow point. When the kink and the arrow point are less than 0.6 mm apart, no arrow is drawn; when they are closer than the arrowhead length, only a shortened head is drawn.

**Editable texts**

- Editable text ids, in exactly this document order: `dim_arrow`, `extent_arrow`, `dim_other`, `extent_other`, `note` (`EDITABLE_IDS`). Each is a `<text>` with `freecad:editable` and a `<tspan>`, in the same namespace as in 2.4.4.
- No other element may carry `freecad:editable`.
- All texts MUST be XML-escaped.

#### 2.5.6 Stored weld data and how it is read back

The full weld state lives in the string property `WeldSettings` as one JSON object (UTF-8; non-ASCII characters such as "×" may be stored literally). For example, a new symbol stores:

```json
{"format": 1,
 "sides": [{"symbol": "fillet", "dimension": "a5", "extent": "", "surface": "", "treatment": ""},
           {"symbol": "", "dimension": "", "extent": "", "surface": "", "treatment": ""}],
 "marks": {"peripheral": false, "site": false, "dashed_line": false},
 "note": ""}
```

| Key | Type | Meaning |
|---|---|---|
| `format` | integer | Layout version of this object, currently 1. Always written; a reader of this version does not depend on it. |
| `sides` | array of 2 objects | Index 0 is the arrow side, index 1 the other side. Each object holds `symbol` (weld type id from 2.5.3, `""` = none), `dimension` (size text, left of the glyph), `extent` (length text, right of the glyph), `surface` (contour id `""`/`flat`/`convex`/`concave`) and `treatment` (finishing letter `""`/`C`/`G`/`M`). |
| `marks` | object | Booleans `peripheral` (weld all around), `site` (field weld flag) and `dashed_line` (identification line shown). |
| `note` | string | Tail note. |

The weld type ids are part of the file contract: an existing id never changes meaning, and an id this version does not know is read as `""`. The same holds for the contour ids and finishing letters.

Reading rules (file compatibility, MUST):

- Whatever is absent or has the wrong type, at any level, takes the value a new symbol starts with (2.5.1). Unknown keys, and array entries after the second, are ignored.
- Empty JSON, invalid JSON, or JSON whose top level is not an object means all defaults.
- The `EditableTexts` list then overrides the stored strings by position, in the order of 2.5.5:
  - the fifth entry (`note`) always replaces the tail note;
  - the first four (`dim_arrow`, `extent_arrow`, `dim_other`, `extent_other`) replace a side's `dimension` or `extent` only while that side has a weld type;
  - a position missing from a shorter list leaves the stored value alone.
- Every redraw writes the merged, complete object back to `WeldSettings`, including `format`.

### 2.6 Save as PDF (`JellyJams_SaveAsPDF`)

Clicking **Save as PDF** with a drawing document active:

1. The sheets are all `TechDraw::DrawPage` objects of the active document, in document object order (the order they appear in the model tree).
2. A native Save dialog opens:
   - title "Save as PDF", filter "PDF (*.pdf)", parent = FreeCAD's main window
   - the suggested path follows 2.8
   - if the user cancels, nothing happens
   - if the chosen name does not end in `.pdf` (case-insensitive), `.pdf` is appended
3. Before writing, the drawing is prepared:
   - All on-screen line-width reductions made by the zoom-line feature are reverted, so the output uses the standard line widths.
   - The document is recomputed.
   - Every sheet that has never had a page window open in this session gets one opened, because TechDraw renders a sheet only after its window has existed. Afterwards the MDI window that was active before is re-activated, and pending GUI events are processed.
4. With **one sheet**, it is written directly to the chosen file using FreeCAD's `TechDrawGui.exportPageAsPdf(page, path)`.
5. With **several sheets**:
   - Each sheet is written with `TechDrawGui.exportPageAsPdf` into a private temporary folder in the system temp directory, whose name starts with `jellyjams_pdf_`.
   - The per-sheet PDFs are then merged, in sheet order, into the single chosen file (2.9).
   - If the merge fails for any reason, a warning goes to the Report view saying the sheets were not merged and why. Each per-sheet PDF is then copied next to the chosen file under the per-sheet names of 2.8.
   - The temporary folder is ALWAYS deleted afterwards, on success or failure.
6. A success message goes to the Report view (prefixed "JellyJams: ") and to the status bar for about 8 seconds. It says one of:
   - the PDF was saved with 1 sheet, plus the path
   - the PDF was saved with N sheets, plus the path
   - the PDF was saved as separate files, listing their file names
7. Any other failure (for example the export call raises) goes to the Report view as an error with the technical details. There is no popup.

### 2.7 Export DXF (`JellyJams_SaveAsDXF`)

- Same sheet list, preparation and suggested path as PDF.
- Dialog title "Export DXF", filter "DXF (*.dxf)", `.dxf` appended when missing (case-insensitive).
- DXF has no sheets. One sheet is written to the chosen file. With several sheets, ONE FILE PER SHEET is written using the per-sheet names of 2.8, and the chosen file name itself is not written.
- Each file is written with FreeCAD's `TechDraw.writeDXFPage(page, path)`.
- Success message (Report view + status bar for about 8 s): DXF saved, listing the written file names.
- Failures go to the Report view as errors, with no popup.

### 2.8 File naming rules (PDF and DXF)

**Suggested file in the Save dialog**

- **Folder**: the folder of the document's saved file. If the document has never been saved, the user's home folder.
- **Base name**: the drawing number from the title block. That is the value of the template editable text `drawing_number` (the key FreeCAD's ISO and ASME templates use) from the first sheet, in sheet order, whose template has a non-empty value after trimming spaces. If no sheet has one, the document `Label` is used, then the document `Name`, then "Drawing".
- **Sanitizing**: every run of the characters `\ / : * ? " < > |` and of control characters becomes one `_`. Spaces inside the name stay. Leading and trailing spaces and dots are removed. If nothing is left, "Drawing" is used.
- **Extension**: `.pdf` or `.dxf`.
- Example: drawing number "DWG-0042/B" gives `DWG-0042_B.pdf`.

**Per-sheet file names (only when there is more than one sheet)**

- Take the chosen path without its extension (the extension is stripped case-insensitively) as the stem.
- For sheet number i (1-based, sheet order), take its `Label` and sanitize it as above.
  - If the sanitized label is exactly "Sheet" followed by digits (for example `Sheet3`), it is kept as the sheet name. The match is case-sensitive and covers the whole label.
  - Otherwise the sheet name is `Sheet<i>`.
- If that sheet name is already used by an earlier sheet in this export, it becomes `Sheet2`, `Sheet3`, ..., the first one not used yet. Two sheets never overwrite each other's file.
- File = stem + `_` + sheet name + extension. Examples:
  - `T.pdf` with sheets labeled "Sheet1", "Sheet2" gives `T_Sheet1.pdf`, `T_Sheet2.pdf`.
  - `T.dxf` with sheets "My Sheet", "Sheet1" gives `T_Sheet1.dxf`, `T_Sheet2.dxf`.
  - One sheet gives exactly the chosen path.
- Existing per-sheet files are overwritten without asking. Only the main file name gets the Save dialog's overwrite confirmation.

### 2.9 Merging PDFs without third-party libraries

The merge MUST use only the Python standard library. It works on the classic PDF structure with a cross-reference table. That is the structure Qt's PDF writer, and therefore TechDraw's page export, always produces.

**Input acceptance.** An input file MUST be rejected with a clear "unsupported PDF" error, which triggers the separate-files fallback of 2.6, when:

- no `startxref … %%EOF` is found near the end of the file (last 2 KiB)
- the `startxref` offset does not point at an `xref` keyword (for example a PDF 1.5+ cross-reference stream)
- there is no `trailer`
- the trailer contains `/Prev` (an incrementally updated file)
- any object listed as in use cannot be found as `N G obj … endobj` at its offset
- after all inputs are read, no page objects were found

**Output structure.**

- **Header**: `%PDF-<v>`, where v is the highest version among the inputs and never below 1.4. It is followed by a binary-marker comment line.
- **Object 1**: a new `/Type /Catalog` whose `/Pages` is `2 0 R`.
- **Object 2**: a new `/Type /Pages` page tree. Its `/Kids` lists every page object of every input, in input order and, within a file, in the order of their original object numbers. Its `/Count` is the number of pages.
- **All other objects**: every in-use object of every input, renumbered one after another from 3 upward (file by file, ascending original numbers), all with generation 0. In each object's dictionary part, before any `stream` keyword, every indirect reference `n g R` to an object of the same file is rewritten to the new number. References to unknown objects stay unchanged.
- Each input's old Catalog and old page-tree (`/Type /Pages`) objects are dropped. Their numbers show up as free entries in the new cross-reference table.
- Every `/Type /Page` object gets `/Parent 2 0 R`.
- Stream data is copied byte for byte, never altered.
- **Robustness (SHOULD)**: inheritable page attributes (`/MediaBox`, `/Resources`, `/CropBox`, `/Rotate`) found on a dropped page-tree node SHOULD be carried onto pages that lack them. If that is not possible, the input SHOULD be rejected rather than produce pages without a size.
- **Cross-reference and trailer**: a classic `xref` table (one subsection starting at 0, free entry for object 0, 10-digit offsets), then a trailer with `/Size` and `/Root 1 0 R`, `startxref` and `%%EOF`.
- The merge reports the number of pages written. The result MUST open in common PDF viewers with every sheet in order and each page at its own size, for example an A4 portrait sheet followed by an A3 landscape sheet.

### 2.10 Line Format (`JellyJams_LineFormat`) and ISO 128 thickness presets

**The command**

- Clicking **Line Format** checks the selection. If it contains at least one edge sub-element (a sub-element name starting with `Edge`) of a drawing view, FreeCAD's own command `TechDraw_DecorateLine` runs, which opens FreeCAD's line decoration task dialog for the selected lines.
  - A "drawing view" is a `TechDraw::DrawViewPart` or any type derived from it: `TechDraw::DrawProjGroupItem`, `TechDraw::DrawViewSection`, `TechDraw::DrawViewDetail`, `TechDraw::DrawComplexSection`, `TechDraw::DrawBrokenView`.
  - Vertices alone, and "edges" of non-view objects (for example the page), do not count.
- With no qualifying edge selected, no dialog and no error popup appear. Instead:
  - a status-bar hint is shown for about 6 seconds (`line_format.HINT`); it must explain that edges of a drawing view have to be picked before the command is run
  - the same text goes to the Report view as a message, prefixed "JellyJams: "
- JellyJams MUST NOT set line appearance itself through `DrawViewPart.formatGeometricEdge()`. That API sets only the old Qt pen style and cannot store an ISO 128 line number (`LineFormat.LineNumber`). FreeCAD's dialog stores the style correctly. Selection rules for edges from several views are FreeCAD's.

**SolidWorks terms in the dialog**

While the JellyJams workbench is active, the dialog-terms area relabels FreeCAD's line decoration form (root widget objectName `TechDrawGui::TaskLineDecor`) through FreeCAD's .ui objectNames:

| Widget | New text |
|---|---|
| `label_15` | Line thickness |
| `label_14` | Line color |
| `label_6` | Line style |
| `label` | Hide/Show Edges |
| combo `cb_Visible` | Hide, Show (only if it has exactly 2 entries) |

All other widgets of the dialog keep FreeCAD's text ([dialog-terms](dialog-terms.md) 2.3 Q).

**ISO 128 thickness presets row** (this area's addition to that dialog)

- Whenever a `TechDrawGui::TaskLineDecor` form is open while the JellyJams workbench is active, one extra row is inserted directly below the dialog's field grid, at position 1 of the form's top-level layout. This holds whether the dialog was opened through `JellyJams_LineFormat` or through FreeCAD's own menu or command. The row is inserted only if the dialog's thickness spin box (objectName `dsb_Weight`, a `Gui::QuantitySpinBox`) exists, and never twice.
- Row widget objectName: `JellyJamsLineWidthPresets`. It holds a label "ISO 128 preset" and a combo that takes the remaining width.
- Combo entries, in order: "–" (no choice), then the ISO 128-2 line thicknesses 0.13 mm, 0.18 mm, 0.25 mm, 0.35 mm, 0.5 mm, 0.7 mm, 1 mm.
  - Text format: period decimal, at most two decimals, no trailing zeros, then " mm" (so 1.0 shows as "1 mm").
- Initial entry: the one whose value equals the spin box's current value. The current value is read from its Qt property `rawValue`, matched within 1e-6. With no exact match, "–".
- When the user picks a thickness (user activation only, not programmatic changes), the spin box's Qt property `rawValue` is set to that value. FreeCAD's dialog takes it over at once, so the lines change live, exactly as if the value had been typed. Picking "–" changes nothing.
- The row lives only as long as that dialog instance. Nothing is persisted.

---

## 3. Triggers and timing

| Event | Effect |
|---|---|
| Workbench first initialized in the session | The five commands are registered (once; repeat calls are harmless). The weld-symbol document watcher (2.5.4) is installed once. |
| Workbench deactivated | Any running weld pick mode ends (cursor and status message restored). The double-click edit hook and the line-dialog presets stop applying, because they are gated on the JellyJams workbench being active. |
| `JellyJams_SurfaceFinish` / `JellyJams_WeldSymbol` activated | Edit the selected symbol of that kind, or else create one on the target sheet (2.3) and open the panel. Weld creation then starts pick mode. |
| Any panel control changed | Immediate redraw and recompute (live preview). |
| Panel OK / Cancel | Commit / roll back the open undo step and close. Weld pick mode ends. |
| Left click on the sheet in weld pick mode | 1st click: arrow point. 2nd click: kink, which ends pick mode. |
| Esc / right click in weld pick mode | Pick mode ends, and the symbol stays as it is. |
| Weld symbol `X`/`Y` changed (any source) | Deferred redraw so the arrow ends at the fixed arrow point. |
| Double-click on a JellyJams symbol on the sheet (JellyJams workbench active, no task dialog, no TechDraw tool running) | Opens that symbol's panel in edit mode; the event is consumed. |
| A `TechDrawGui::TaskLineDecor` dialog is open while the JellyJams workbench is active | Within about half a second, the SolidWorks labels are applied and the ISO 128 presets row is inserted (once). |
| `JellyJams_SaveAsPDF` / `JellyJams_SaveAsDXF` activated | Save dialog, then preparation (line widths reverted, recompute, unopened sheets opened), then writing and a report. |

---

## 4. FreeCAD state read or changed

### 4.1 Document objects created

| What | Type | Name base | Initial Label |
|---|---|---|---|
| Surface finish symbol | `TechDraw::DrawViewSymbol` | `SurfaceFinish` | Surface Finish |
| Weld symbol | `TechDraw::DrawViewSymbol` | `WeldSymbol` | Weld Symbol |

Both are added to their sheet with `DrawPage.addView(...)`.

FreeCAD properties set on these objects:

- `Symbol` (the SVG text)
- `X` and `Y` in sheet mm (the surface finish position, or the weld kink)
- `Rotation` (surface finish only)
- `ScaleType` = `Custom`
- `Scale` = 1.0 (weld)
- `ViewObject.StackOrder` = 110

FreeCAD properties read:

- `EditableTexts` (string list, filled by FreeCAD from the SVG's editable texts)
- `Rotation`, `X`, `Y`
- the sheet's `Template` and its `Width`, `Height` and `EditableTexts` (key `drawing_number`)
- each object's `InList`, `TypeId` and `Label`

### 4.2 Custom properties stored in users' documents (file-compatibility contract; names and values exact)

| Property | FreeCAD type | Group | On | Values |
|---|---|---|---|---|
| `SymbolType` | `App::PropertyString` | JellyJams | both | `surface` for surface finish, `weld` for weld symbol. This is the marker other areas use: tree naming labels these objects "Surface Finish<n>" / "Weld Symbol<n>", the image tools skip objects carrying it, and the double-click hook routes on it. |
| `MaterialRemoval` | `App::PropertyString` | JellyJams | surface | `any` (default), `required`, `prohibited`. An unknown value is drawn and shown as `any`. |
| `AllAroundOutline` | `App::PropertyBool` | JellyJams | surface | all-around flag |
| `WeldSettings` | `App::PropertyString` | JellyJams | weld | JSON as in 2.5.6 |
| `ArrowheadX` | `App::PropertyFloat` | JellyJams | weld | arrow tip x on the sheet, mm |
| `ArrowheadY` | `App::PropertyFloat` | JellyJams | weld | arrow tip y on the sheet, mm (y up) |

The SVG editable-text ids (`a`..`e`, and `dim_arrow`, `extent_arrow`, `dim_other`, `extent_other`, `note`) and their order are also part of this contract, because they end up in the saved `Symbol` and `EditableTexts`.

Properties are added only if missing, so reopening a saved file never duplicates them. The surface finish's texts live only in the SVG/`EditableTexts`; there is no JSON copy.

### 4.3 FreeCAD commands, APIs, widgets and parameters used

- Commands run: `TechDraw_DecorateLine`.
- APIs:
  - `TechDrawGui.exportPageAsPdf(page, path)`
  - `TechDraw.writeDXFPage(page, path)`
  - `FreeCAD.addDocumentObserver` (slot for changed objects)
  - `FreeCADGui.Control.showDialog`, `activeDialog` and `closeDialog`
  - document transactions (`openTransaction`, `commitTransaction`, `abortTransaction`)
  - `ViewObject.doubleClicked()` on a page to open its window
  - the Gui document's MDI views of type `TechDrawGui::MDIViewPage` (and `getPage()`), to see which sheets already have a window
- Widgets:
  - the active page window is recognized by the class name `TechDrawGui::MDIViewPage` of the active `QMdiArea` subwindow's widget; its `QGraphicsView` child is used for pick mode
  - FreeCAD dialog widgets: `TechDrawGui::TaskLineDecor` (form root), `dsb_Weight` (Qt property `rawValue`), plus the label and combo objectNames in 2.10
- Parameters read (never written): `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`, float `Resolution`, default 10.0.
- Undo step names: "Surface Finish", "Edit Surface Finish", "Weld Symbol", "Edit Weld Symbol".
- Status bar of the main window: weld pick-mode prompts (shown until pick mode ends), export results (about 8 s), the Line Format hint (about 6 s).
- Report view: all messages prefixed "JellyJams: ".
- Task panel objectNames: `JellyJamsSurfaceFinishForm`, `JellyJamsWeldSymbolForm`. Inserted dialog row objectName: `JellyJamsLineWidthPresets`.
- No parameter under `User parameter:BaseApp/Preferences/Mod/JellyJams` is used by this area, and no FreeCAD preference is changed.

---

## 5. Persistence and restore rules

- **Documents**: all symbol state lives in the FreeCAD document (4.2) and is saved with it.
  - A drawing saved with JellyJams opens in plain FreeCAD: the symbols are ordinary `TechDraw::DrawViewSymbol` objects with valid SVG, and their texts can be edited in `EditableTexts`.
  - Without JellyJams, a moved weld symbol does not redraw its arrow. The next time it moves or is edited with JellyJams active in the session, the arrow is redrawn correctly from `ArrowheadX`/`ArrowheadY`.
- **Exact restore**: this area changes no FreeCAD preferences, so there is nothing to snapshot or restore and no crash recovery is needed.
  - Temporary changes are limited to: the crosshair cursor and status message during pick mode (cleared when it ends or when the workbench is left), and the extra row and labels inside an open FreeCAD line dialog (gone when the dialog closes).
  - Export temporarily asks the zoom-line feature to revert on-screen line widths. That feature owns those values and their restore.
- **Undo**: creation and editing are each exactly one undo step (names in 4.3). Cancel leaves no trace.
- **Temporary files**: the multi-sheet PDF work folder is always removed after the export. A folder left behind by a crash (prefix `jellyjams_pdf_` in the system temp directory) is harmless; such folders older than one day are removed at the next PDF export.

---

## 6. Edge cases and failure handling

1. **No sheet in the document**: all five commands are disabled. A command activated anyway (for example by a script) does nothing.
2. **A task dialog is already open**: the commands are disabled; the double-click does nothing; a symbol panel never stacks on another dialog.
3. **Selection contains several symbols**: the command edits the first symbol of its own kind. A selected surface finish does not make the weld command edit it; a new weld symbol is created on that symbol's sheet instead.
4. **Template missing or without size**: the sheet center falls back to 105 × 148.5 mm (A4 portrait).
5. **No page window active when a weld symbol is created**: no pick mode. The symbol sits at its default place and the panel is open. The user can activate the page window and use the panel's re-pick button (2.5.3, item 4).
6. **The user switches windows during pick mode**: pick mode stays tied to the page window where it started. It ends with Esc or right click there, with OK/Cancel, or when the workbench is left.
7. **Arrow point and kink at the same place** (under 0.6 mm apart): no arrow is drawn and nothing fails.
8. **A weld side without a weld type**: no glyph, contour, finishing letter, size or length is drawn for that side. The two editable texts for that side stay present but empty, and values typed into them in the property editor are ignored until a weld type is chosen.
9. **The tail note is filled in through `EditableTexts`**: the text shows at once (FreeCAD rewrites the SVG text). The fork appears at the next redraw (move, panel). JellyJams MAY redraw immediately.
10. **Bad JSON in `WeldSettings`** (hand-edited file): fall back to defaults merged with `EditableTexts`. Never raise.
11. **Rotation field with non-numeric text**: treated as 0°. A comma decimal is accepted.
12. **Special characters in texts** (`<`, `&`, `"`, `⊥`, `×`): stored and shown correctly; the SVG stays valid.
13. **The redraw while moving fails** (for example a deleted object): swallowed silently. The re-entry guard is always released.
14. **Export with unsaved document**: the suggested folder is the user's home folder.
15. **Drawing number contains path characters** (`/`, `\`, `:` ...): they are replaced by `_` (2.8).
16. **Sheet labels collide in a multi-sheet export** (for example "My Sheet" as sheet 1 and "Sheet1" as sheet 2): the second gets the next free `Sheet<k>` name, so no file overwrites another.
17. **The chosen file name already ends in `.PDF`/`.DXF`** (any case): no extension is added.
18. **PDF merge not possible** (unsupported structure, for example a future Qt version writing xref streams): separate per-sheet PDFs next to the chosen file, a warning in the Report view, and a status-bar result naming the separate files.
19. **Export call raises** (for example a sheet that cannot render, or a write-protected folder): an error with details in the Report view and no popup. Files already written stay; the temporary folder is still removed.
20. **Sheets never opened in this session**: their page windows are opened before export so they render. The user's previously active window is brought back afterwards.
21. **Zoomed-in sheet with thinned lines on screen**: export always uses the standard line widths (2.6, step 3).
22. **Line Format with only vertices selected, or with edges of a non-view object**: status-bar hint only; FreeCAD's dialog is not opened.
23. **A FreeCAD version whose line dialog has no `dsb_Weight`**: no presets row and no error. Relabeling skips missing widgets, and leaves combos whose entry count differs from the expected one unchanged.
24. **The JellyJams workbench is not active**: the double-click edit and the dialog presets/terms do not apply. The commands themselves still work if run from elsewhere, and the weld arrow-follow watcher stays active once installed.

---

## 7. Acceptance criteria

Setup for all tests: FreeCAD 1.1.x with JellyJams installed and the JellyJams workbench active. Open a part, use the Drawing tab to make a drawing on an ISO template, and have at least one drawing view on the sheet.

**Ribbon and enablement**

1. The Drawing tab shows "Balloon", "Surface Finish" and "Weld Symbol" as a text stack in the annotation group, and a large "Line Format" button in the sheet-sketch group. Its last group shows "Save as PDF" and "Save as DXF". Each JellyJams button has its own new icon.
2. In a document without any TechDraw sheet, all five buttons are disabled. With a sheet, they are enabled. While any task dialog is open (for example a sketch), they are disabled.
3. `FreeCADGui.listCommands()` contains `JellyJams_SurfaceFinish`, `JellyJams_WeldSymbol`, `JellyJams_LineFormat`, `JellyJams_SaveAsPDF` and `JellyJams_SaveAsDXF`.

**Surface Finish**

4. Select a drawing view and click Surface Finish. A symbol appears about 25 mm right of and 15 mm above the view's position, showing the basic check mark and "Rz 16". A task panel with objectName `JellyJamsSurfaceFinishForm` opens.
5. In the tree, the new object is a `TechDraw::DrawViewSymbol` with `SymbolType` = `surface`, `MaterialRemoval` = `any` and `AllAroundOutline` = false. Its `ScaleType` is `Custom`. `EditableTexts` has 5 entries, the first being "Rz 16".
6. Switching the symbol-type combo to the `required` entry closes the V with a bar at once. The `prohibited` entry shows a circle in the V instead. Ticking all-around adds a small circle at the corner.
7. The field a combo offers Rz 4, Rz 16 and Rz 63, among others. Choosing Rz 63 updates the sheet at once. Typing a long text lengthens the horizontal line so the text fits.
8. Picking the `C` lay entry in field d puts only "C" into the field, and "C" appears lower right of the root.
9. Entering rotation "90" rotates the symbol, and the object's `Rotation` becomes 90.
10. Cancel right after creating removes the symbol completely. A new symbol confirmed with OK is removed by a single Undo ("Surface Finish").
11. Double-clicking the confirmed symbol on the sheet reopens the panel showing its current values. Changing a value and pressing Cancel restores the earlier look exactly.
12. Edit field c in the property editor (Data › EditableTexts, 3rd entry), then reopen the panel. The panel shows the new text.
13. Save the file, close it and reopen it in FreeCAD without the JellyJams workbench activated. The symbol shows correctly and its texts are still editable in EditableTexts.
14. At the same insertion scale, a JellyJams surface finish symbol and one from FreeCAD's own TechDraw_SurfaceFinishSymbols are about the same size.

**Weld Symbol**

15. With the page window active, click Weld Symbol. A panel with objectName `JellyJamsWeldSymbolForm` opens, the cursor over the sheet is a crosshair, and the status bar shows the first-step prompt asking for the arrow point.
16. Click an edge. The arrowhead's point lands exactly at the click, and the symbol jumps to about 14 mm right of and 8 mm above it. The status bar now shows the second-step prompt asking for the reference-line position.
17. Click elsewhere. The reference line's left end (the kink) lands at the click, the arrow still points exactly at the first click, and the crosshair disappears. Clicking on the sheet now selects things normally again.
18. The default symbol shows a fillet triangle hanging under the reference line (arrow side), its upright on the left and "a5" left of it.
19. In the other-side group, choose the `butt_v` symbol with size "s5": a V appears above the line. Tick the identification-line check box: a dashed line appears just above the solid line, the V moves up onto the dashed line, and the arrow-side fillet stays under the solid line. Untick it, and no dashed line remains.
20. Tick all-around: a circle appears at the kink. Tick field weld: a flag on a staff appears at the kink and the glyphs and size texts move right to clear it. Enter tail "111": a fork appears at the right end with "111" after it. Clear the tail, and the fork disappears.
21. For the arrow side, choose contour `convex` and finish method `G`: an arc bulging away from the fillet and the letter G beyond it appear under the fillet.
22. Press OK, then drag the symbol to another place on the sheet. The arrowhead stays on the original edge point and the arrow line follows. Changing `X` in the property editor has the same effect. `ArrowheadX`/`ArrowheadY` do not change.
23. Change the arrow-side size to "a7" through Data › EditableTexts (1st entry), then move the symbol slightly. "a7" stays, and in `WeldSettings` the first entry of `sides` now has `"dimension": "a7"`.
24. Double-click the weld symbol, press the re-pick button and click a new edge, then a new symbol position. The arrow now points at the new edge. Cancel restores the previous arrow point and position.25. Press Esc during pick mode. Pick mode ends, the symbol stays where it is, and the status message clears.
26. Start pick mode, then switch to another workbench. The crosshair disappears and clicks on the sheet no longer place the arrow.
27. The weld object has `SymbolType` = `weld` and `ScaleType` = `Custom` with `Scale` = 1. Its `WeldSettings` is a valid JSON object with exactly the keys `format` (value 1), `sides` (two objects), `marks` and `note`. `EditableTexts` has exactly 5 entries, in the order arrow size, arrow length, other size, other length, tail.
28. Saving, closing and reopening keeps every weld symbol exactly as it was. Opening the panel shows the stored choices. Any of the fourteen weld types chosen for both sides at once is drawn mirrored about the reference line (for example `fillet` twice gives two triangles sharing their upright) and survives the round trip.
29. Cancel right after creating a weld symbol, even after both placement clicks, removes it completely. A single Undo after OK removes a created symbol.

**Line Format**

30. With nothing selected, click Line Format. No dialog and no popup appear; the status bar shows a hint to select lines first.
31. Select only a vertex of a view and click Line Format. The behavior is the same as in criterion 30.
32. Select two edges of a view and click Line Format. FreeCAD's line decoration dialog opens with the labels Line thickness, Line color, Line style and Hide/Show Edges, and the visibility choices Hide/Show.
33. The dialog shows a row "ISO 128 preset" right below the fields, with a combo listing –, 0.13 mm, 0.18 mm, 0.25 mm, 0.35 mm, 0.5 mm, 0.7 mm, 1 mm. A widget with objectName `JellyJamsLineWidthPresets` exists exactly once.
34. When the line thickness field is 0.5, the combo starts on "0.5 mm". When it holds a non-standard value such as 0.42, it starts on "–".
35. Picking "0.7 mm" sets the thickness field to 0.7 and the selected lines thicken on the sheet at once. Picking "–" leaves the value alone. OK stores the change, and the lines keep their ISO line style after saving and reopening.

**Save as PDF / Export DXF**

36. Fill the title block's drawing number with "DWG-0042/B", save the document in a folder, and click Save as PDF. The dialog suggests `DWG-0042_B.pdf` in the document's folder.
37. Clear the drawing number. The suggestion becomes the document label plus `.pdf`. For a never-saved document, the folder is the home folder.
38. Typing the name "out" with no extension writes `out.pdf`.
39. With one sheet, the PDF has one page matching the sheet. The status bar and the Report view report one sheet and the path.
40. Add a second sheet with a different size (for example A3 landscape) and click Save as PDF. ONE file holds both sheets in tree order, each page at its own size. The message reports 2 sheets. No temporary `jellyjams_pdf_*` folder remains in the system temp directory.
41. While zoomed far into a sheet (lines thinned on screen), Save as PDF produces standard line widths in the PDF.
42. Open a document whose second sheet was never opened in this session and save it as PDF. Both pages have content, and the previously active window is active again afterwards.
43. With two sheets labeled "Sheet1" and "Sheet2", Export DXF to `T.dxf` writes `T_Sheet1.dxf` and `T_Sheet2.dxf` and no `T.dxf`. With sheets labeled "My Sheet" and "Sheet1", it writes `T_Sheet1.dxf` and `T_Sheet2.dxf` (no overwrite). With one sheet, it writes exactly `T.dxf`. Each file opens in a DXF viewer.
44. Separate-files fallback: when merging fails, for example in a test that feeds an xref-stream PDF, the sheets end up as `<name>_Sheet1.pdf`, `<name>_Sheet2.pdf` next to the chosen path, a warning appears in the Report view, and the status bar lists the separate files.
45. Merging two Qt-written single-page PDFs produces a file whose catalog is object 1 and whose page tree is object 2 with `/Count 2`. Both pages have `/Parent 2 0 R`, the page content of the first input comes before the second, and the stream bytes are unchanged. The file opens without repair warnings in at least two different PDF viewers.
46. Merging rejects a PDF that has a `/Prev` trailer entry or a cross-reference stream, with an "unsupported" error. It never writes a broken file.
47. No popup dialog appears for any export error. Errors appear in the Report view prefixed "JellyJams: ".
