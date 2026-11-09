# JellyJams specification: Drawing sheet (Make Drawing, Sheet Properties, sheet shapes, Text, Insert Picture)

> **Implemented in:** [`jellyjams/make_drawing.py`](../../jellyjams/make_drawing.py) (section 4), [`sheet_properties.py`](../../jellyjams/sheet_properties.py) (section 5), [`templates.py`](../../jellyjams/templates.py) (section 6), [`sheet_sketch.py`](../../jellyjams/sheet_sketch.py) (section 7), [`sheet_text.py`](../../jellyjams/sheet_text.py) (section 8), [`insert_picture.py`](../../jellyjams/insert_picture.py) (section 9); shared helpers in [`drawing_common.py`](../../jellyjams/drawing_common.py) (target sheet, sheet sizes) and [`sheet_pick.py`](../../jellyjams/sheet_pick.py) (position picking); icons in [`resources/icons/`](../../resources/icons/) (`make_drawing`, `sheet_properties`, `insert_picture`, `sheet_text`, `sheet_line`, `sheet_rectangle`, `sheet_circle`, `sheet_arc`, `sheet_polygon`).
>
> **Status:** see [../status.md](../status.md)

This specification describes what the features do. Target: FreeCAD 1.1+
(facts verified on FreeCAD 1.1.4), PySide6/Qt 6, English only.

Keywords: MUST = required and covered by an acceptance criterion; SHOULD =
expected, tested where marked "(should)".

---

## 1. Purpose

JellyJams makes FreeCAD's TechDraw drawings work the way SolidWorks drawings do.
This area covers the drawing sheet itself:

1. **Make Drawing** (`JellyJams_MakeDrawing`): SolidWorks "Make Drawing from
   Part/Assembly". Creates a separate drawing file for the open part or
   assembly. The file has one sheet, an ISO title block from FreeCAD's own
   installed templates, and a Standard 3 View.
2. **Sheet Properties** (`JellyJams_SheetProperties`): SolidWorks "Sheet Properties".
   Lets the user change the sheet format/size (template), choose the type of
   projection (first or third angle), and fill in the title block.
3. **Shapes** (`JellyJams_LineOnSheet`, `_Rectangle`, `_Circle`, `_Arc`,
   `_Polygon`): draw sketch geometry directly on the sheet, with the full
   relations and dimensions of the Sketcher. Each sheet gets its own hidden
   sketch, the "sheet sketch", which is shown on the sheet 1:1.
4. **Text** (`JellyJams_Note`): click on the sheet and type plain text, with the
   letter height in mm or pt.
5. **Insert Picture** (`JellyJams_InsertPicture`): SolidWorks Insert > Picture. Puts an
   SVG, PNG, JPG or BMP on the sheet, with a panel for position, width and
   rotation.

PROJECT DECISION: JellyJams ships **no**
drawing templates. Every template that JellyJams offers or uses comes from
FreeCAD's installed TechDraw templates, found at runtime. A third-angle variant
of an installed ISO template is derived at runtime (section 6.3). It is never
shipped.

---

## 2. Commands, labels, placement, icons

| Command id | MenuText | Ribbon (owned by the ribbon area) | Enabled when |
|---|---|---|---|
| `JellyJams_MakeDrawing` | Make Drawing | Drawing tab, Sheet group, large button `Make⏎Drawing`. A second button for the same command sits in the Assembly tab and runs it with index 1. | An active document exists, it contains drawable model objects (section 4.1), and it is not itself a drawing, meaning it contains no `TechDraw::DrawPage`. |
| `JellyJams_SheetProperties` | Sheet Properties | Drawing tab, Sheet group, small text button "Sheet Properties" | The active document contains at least one `TechDraw::DrawPage` AND no task dialog is open (`FreeCADGui.Control.activeDialog()` is false). |
| `JellyJams_InsertPicture` | Insert Picture | Drawing tab, Sheet group, small text button "Insert Picture" | Same as Sheet Properties. |
| `JellyJams_LineOnSheet` | Line | Drawing tab, Sheet sketch group: an icon-only stack with "Line", "Corner Rectangle", "Circle", "Centerpoint Arc" and "Polygon", in that order | Same as Sheet Properties; in addition, the five shape commands stay enabled while the target sheet's own sheet sketch is in edit, so the user can switch tools inside that edit. |
| `JellyJams_CornerRectangleOnSheet` | Rectangle | same stack ("Corner Rectangle") | same |
| `JellyJams_CircleOnSheet` | Circle | same stack ("Circle") | same |
| `JellyJams_CenterpointArcOnSheet` | Arc | same stack ("Centerpoint Arc") | same |
| `JellyJams_PolygonOnSheet` | Polygon | same stack ("Polygon") | same |
| `JellyJams_Note` | Text | Drawing tab, Annotation group: the default variant "Note" of the Note flyout (next to FreeCAD's "Rich Text Note") | Same as Sheet Properties. |

- Every command MUST behave the same whether it is run with no argument or
  with an index argument, for example `FreeCADGui.runCommand("JellyJams_MakeDrawing", 1)`.
- Every command has a tooltip of one short paragraph in SolidWorks
  vocabulary. It describes the outcome for the user, not the steps inside the
  command, and when a selection switches the command from creating to editing,
  the tooltip mentions that too. What each tooltip has to get across:

  | Command | Points the tooltip covers |
  |---|---|
  | `JellyJams_MakeDrawing` | the result is its own document, linked to the model; what its first sheet already contains |
  | `JellyJams_SheetProperties` | the three things the panel can change (section 5) |
  | Shape commands | the kind of geometry; that it is drawn at 1:1; that sketch relations and dimensions apply |
  | `JellyJams_Note` | how a text is placed; that a selected text of this area is edited instead; the cancel key |
  | `JellyJams_InsertPicture` | the accepted file types; what the panel controls; that a selected picture is edited instead |

- Icons: all of these are JellyJams-only commands. Each one gets a NEW,
  original icon drawn for this project, and its `Pixmap` points to that icon.
  JellyJams MUST NOT bundle FreeCAD or third-party icon files for them.
  Suggested motifs:
  - Make Drawing: a sheet showing three small views.
  - Sheet Properties: a sheet with a highlighted title block.
  - Insert Picture: a sheet with a landscape picture.
  - Text: a sheet with a letter "A".
  - The five Shapes: a line, rectangle, circle, arc or hexagon on a sheet
    corner.

  Icon file names and identifiers MUST NOT contain "SolidWorks".

---

## 3. Shared rule: which sheet a command acts on ("target sheet")

When a command needs a sheet, the target sheet is the first match in this
order:

1. **The sheet in the active window.** This applies when the active MDI window
   is a TechDraw page window (widget class `TechDrawGui::MDIViewPage`); the
   sheet is the `TechDraw::DrawPage` that window shows.
2. **A selected sheet.** Either a selected object that is a
   `TechDraw::DrawPage`, or the `DrawPage` among the parents (`InList`) of a
   selected object.
3. **The first `TechDraw::DrawPage`** in the active document.

If none of these exists, the command does nothing.

---

## 4. Make Drawing (`JellyJams_MakeDrawing`)

### 4.1 What gets drawn ("model objects")

The command considers only top-level objects in the active document.
Top-level means an object that is not contained in an `App::Part`,
`PartDesign::Body`, `Assembly::AssemblyObject` or `App::DocumentObjectGroup`.
Among these, it takes ALL objects of the first kind present, in this priority
order:

1. `Assembly::AssemblyObject`
2. `App::Part`
3. `PartDesign::Body`
4. `Part::Feature`, including derived types such as a Part primitive, but not
   2D profiles (`Part::Part2DObject` and its subtypes, such as sketches)

So an assembly document draws the assembly, a document with one body draws
the body, and so on. A document that holds only sketches has nothing to draw,
so the command is disabled there. The drag-and-drop insertion of the assembly
area uses the same rule.

### 4.2 User-visible flow

1. **No model objects.** An information message box titled "Make Drawing"
   says that no part or assembly was found. Nothing is created.
2. **Model document never saved** (it has no file name). An information box
   explains that the part or assembly must be saved first, because the drawing
   refers to its file. FreeCAD's `Std_SaveAs` then runs. If the document is
   still unsaved afterwards (the user cancelled), the command stops.
3. **Sheet format.** A selection dialog titled "Make Drawing" asks
   "Sheet format (title block ISO 7200):". It offers exactly two items in this
   order: `A4 portrait` and `A3 landscape`.
   - The preselected item is `A3 landscape` if the largest bounding-box edge
     (X, Y or Z length) of any model object is 120 mm or more. Otherwise it
     is `A4 portrait`. The threshold is a judgement value, not taken from a
     standard: larger parts get the larger sheet so the automatic view scale
     stays closer to 1:1.
   - Cancel stops the command.
4. **Location.** A Save dialog titled "Save drawing as" uses the filter
   "FreeCAD file (*.FCStd)".
   - The suggested path is `<folder of the model file>/<model document Label>_Drawing.FCStd`.
     If the model has no folder, the user's home folder is used instead.
   - If the chosen name does not end in `.fcstd` (case-insensitive),
     `.FCStd` is appended.
   - If the chosen path is the file of a document that is already open (the
     model itself included; paths compared after normalization,
     case-insensitively), an error naming that document goes to the Report
     view and nothing is created.
   - Cancel stops the command.
5. **The drawing document.**
   - It is a NEW, separate document.
   - Its Label is the file name without extension.
   - Its internal Name is that same stem with every character that is not an
     ASCII letter, digit or underscore replaced by `_`. An empty result
     becomes `Drawing`.
   - It MUST be saved to the chosen path BEFORE any view references the model.
     FreeCAD refuses cross-document links whose owner document has never
     been saved.
6. **Content.** The drawing document contains these objects:
   - one `TechDraw::DrawSVGTemplate`. Its `Template` is the file chosen in
     section 6.2 for the selected format and the default projection.
   - one `TechDraw::DrawPage`, with:
     - `Template` = that template object
     - `ProjectionType` = the default projection
     - `Label` = `Sheet1`
   - one `TechDraw::DrawProjGroup` on that page, with:
     - `ProjectionType` = the default projection, set explicitly rather than
       left at "Default"
     - `XSource` = the model objects
     - `ScaleType` = `Automatic`
     - `Label` = `Standard 3 View`
     - Projections:
       - Third angle: `Front`, `Top`, `Right`. The top view sits above the
         front view and the right view to its right, like the SolidWorks
         Standard 3 View.
       - First angle: `Front`, `Top`, `Left`. The top view sits below the
         front view and the left view to its right.
   - The **default projection for new drawings is `Third angle`**.
7. **Layout.** After the first recompute, the projection group gets a clean
   initial layout: the views do not overlap and are spaced according to the
   part size. The group is then made individually draggable while the views
   stay aligned, which means `DrawProjGroup.AutoDistribute` = `False`. The
   projected-views area owns this behavior; this area only calls it.
8. **Title block.** The title block is prefilled from the model (section
   5.4). FreeCAD's stock ISO templates arrive filled with sample placeholder
   texts (for example a fictitious author and approver, "DN", "AAA", "ST1",
   and a sample material). A new drawing MUST NOT show them:
   - every title-block field that JellyJams can derive gets the derived value;
   - every other field is set to the empty string.
9. **Finish.**
   - The drawing is recomputed and saved again, so the file contains the
     views.
   - It becomes the active document, and its sheet window opens in front, as
     if the sheet were double-clicked in the tree.
     The opener MUST use `page.ViewObject.show()` directly. In FreeCAD 1.1.4,
     `doubleClicked()` does not open a page while TechDraw's `SwitchToWB` is
     false, which JellyJams requires while active. Opening the sheet MUST NOT
     change the active workbench or temporarily change that preference.
   - The Report view gets one message containing the path and the format.
10. Any exception during steps 5 to 9 is reported in the Report view as an
    error. The command then ends without further dialogs.

---

## 5. Sheet Properties (`JellyJams_SheetProperties`)

### 5.1 Opening

- Running the command opens a panel in FreeCAD's Tasks area
  (`FreeCADGui.Control.showDialog`) for the target sheet (section 3).
- If the target sheet has no template object, nothing happens.
- Panel widget objectName: `JellyJamsSheetPropertiesForm`. Window title:
  "Sheet Properties".
- Section headings in the panel are bold labels with objectName
  `JellyJamsSectionCaption`, the shared JellyJams panel heading style that the
  theme area styles.

### 5.2 Panel contents, top to bottom

1. **Heading "Sheet Format/Size"**
   - A drop-down list of sheet formats (the template catalog, section 6.1).
     It is preselected to the sheet's current template:
     - If the current template is a third-angle variant (section 6.3), the
       list shows it under its base template.
     - If the current template is not in the catalog, an extra entry
       `Custom: <file name>` is inserted at the top and selected.
   - A **"Browse…"** button. Its tooltip says it lets the user choose their
     own SVG template, for example a company title block.
     - It opens a file dialog filtered to "Drawing template (*.svg)". The
       dialog starts in the folder of the current template, or else in
       FreeCAD's Templates folder.
     - After a file is chosen, it appears as the selected
       `Custom: <file name>` entry.
2. **Heading "Type of projection"**
   - Two exclusive choices: **First angle** and **Third angle**. Their tooltip
     explains first angle (ISO/European) versus third angle (American), and
     that the symbol in the title block follows the choice where possible.
   - The preselected choice is the sheet's current method:
     - Take the first `TechDraw::DrawProjGroup` on the sheet. If its
       `ProjectionType` is `Third angle` or `First angle`, that value is used.
       Any other value (`Default`) means "same as the page".
     - Without such a group, the page's own `ProjectionType` is used.
3. **Heading "Title Block"**
   - A **"Fill from Model"** button. Its tooltip says it fills in title,
     drawing number, material, scale, author and date. Clicking it writes the
     derived values (section 5.4) into the matching fields in the panel and
     OVERWRITES what those fields contain. Nothing is applied to the document
     until OK.
   - One single-line text field per editable text of the CURRENT template
     (`DrawSVGTemplate.EditableTexts` keys), prefilled with the current
     values. Each field has a readable label (section 5.3). Fields appear in
     the order of the table in 5.3. Keys that are not in the table follow
     alphabetically.

Changing the format list, the projection choice or any field does nothing to
the document until **OK**.

### 5.3 Field labels (template key → label)

| Key | Label | Key | Label |
|---|---|---|---|
| `title` | Title | `approval_person` | Approved by |
| `supplementary_title_1` | Supplementary title 1 | `date_of_issue` | Date of issue |
| `supplementary_title_2` | Supplementary title 2 | `revision_index` | Revision |
| `drawing_number` | Drawing number | `sheet_number` | Sheet |
| `part_material` | Material | `document_type` | Document type |
| `scale` | Scale | `document_status` | Document status |
| `unit` | Unit | `responsible_department` | Responsible department |
| `general_tolerances` | General tolerances | `language_code` | Language |
| `creator` | Drawn by | `legal_owner_1` … `legal_owner_4` | Legal owner (line 1) … (line 4) |

The table order is the panel order: left column top to bottom, then right
column top to bottom. Any unknown key is labeled with the key itself,
underscores replaced by spaces and the first letter capitalized.

### 5.4 Derived title-block values ("from the model")

The **source object** is the first entry of `XSource`, or else of `Source`, of
the first view on the sheet that has a position (`X`/`Y`) and a non-empty
source. Derived values apply only to keys the template actually has. A value
is left out when it cannot be determined.

| Key | Value |
|---|---|
| `title` | Label of the source object's document, or else the source object's Label |
| `part_material` | Name of the source object's `ShapeMaterial`, or else its `Material` (a string, or an object with `Name`). Left out if empty. |
| `drawing_number` | Label of the drawing document |
| `scale` | Scale of the first view on the sheet as text, using colon notation with no spaces: 0.5 → `1:2`, 2 → `2:1`, 1 → `1:1`, 0.4 → `1:2.5`. Rounded to 2 decimals, with no trailing `.0`. Left out if the scale is ≤ 0 or unreadable. |
| `creator` | FreeCAD parameter `User parameter:BaseApp/Preferences/Document`, string `prefAuthor`. If empty, the operating-system login name. Left out if both are empty. |
| `date_of_issue` | Today, as ISO 8601 `YYYY-MM-DD` |
| `language_code` | `EN` |
| `unit` | `mm` |

### 5.5 OK and Cancel

**OK** applies everything as ONE undo step named "Sheet Properties", then
closes the panel:

1. **Projection.** The page's `ProjectionType` and the `ProjectionType` of
   every `TechDraw::DrawProjGroup` on the sheet are set to the chosen method.
2. **Template file.** The effective template is the format chosen in the list,
   resolved for the chosen method (section 6.3).
3. **If the effective template differs from the current one** (paths compared
   after normalization):
   - Before switching, collect the title-block entries: current
     `EditableTexts`, overlaid with the panel's field values. FreeCAD clears
     all entries when `DrawSVGTemplate.Template` changes.
   - After switching, every editable text of the NEW template gets the
     collected value for its key, or the empty string if there is none. The
     new template's sample placeholders therefore never appear.
   - Every view placed directly on the sheet keeps its relative position. Its
     `X` is scaled by new width ÷ old width and its `Y` by new height ÷ old
     height. This applies only when both sizes are valid and greater than 0.
     Projection-group members keep their offsets relative to their group.
4. **If the template is unchanged**, every editable text gets the panel's
   value for its key. Keys without a field get the empty string.
5. The document is recomputed.
6. If something fails, the error goes to the Report view. The undo step still
   closes cleanly and the panel still closes.

**Cancel** closes the panel and changes nothing.

---

## 6. Templates (shared by Make Drawing and Sheet Properties)

`<Templates>` = `<FreeCAD.getResourceDir()>/Mod/TechDraw/Templates`.

### 6.1 Template catalog (the Sheet Format/Size list)

- **Source:** the `*.svg` files directly in `<Templates>/ISO/`. The
  sub-folders `localized/` and `titleblocks/` are excluded, keeping the
  product English-only. ASME and other templates are reachable through
  Browse….
- Third-angle variant files (file stem ending `_third_angle`) are never listed.
- **Order:**
  1. `A4_Portrait_ISO5457_advanced.svg`
  2. `A3_Landscape_ISO5457_advanced.svg`
  3. all remaining files, sorted by file name
- **Display name** for files named `<size>_<Portrait|Landscape>[_<variant>]`
  is `<size> <portrait|landscape> – <variant text>`, with these variant
  texts:

  | Variant | Text |
  |---|---|
  | `ISO5457_advanced` | title block ISO 7200 |
  | `ISO5457_minimal` | small title block |
  | `ISO5457_notitleblock` | no title block |
  | `blank` | blank |
  | `TD` | TechDraw |
  | anything else | the variant with underscores shown as spaces |

  With no variant, only `<size> <orientation>` is shown. Any other file name
  shows its stem.
- If the ISO folder is missing, the list contains only the current template,
  as a `Custom:` entry.

### 6.2 Template for a new drawing

For `A4 portrait` the file is `A4_Portrait_ISO5457_advanced.svg`; for
`A3 landscape` it is `A3_Landscape_ISO5457_advanced.svg`. The first existing
path wins:

1. `<Templates>/ISO/<file>`
2. `<Templates>/<file>`
3. FreeCAD parameter `User parameter:BaseApp/Preferences/Mod/TechDraw/Files`,
   string `TemplateFile`, if that file exists
4. `<Templates>/Default_Template_A4_Landscape.svg`

The result is then resolved for the projection method (6.3).

### 6.3 Projection symbol: third-angle variants

FreeCAD's ISO templates (`*_ISO5457_advanced/minimal.svg`) contain a
**first-angle** projection symbol made of five SVG elements whose ids begin
with `first_angle_`:

- a trapezoid
- an inner circle and an outer circle
- a horizontal centre line and a vertical centre line

JellyJams' default is third angle, so the sheet MUST show the correct symbol.

- **Variant name.** The third-angle variant of a template `<stem>.svg` is
  `<stem>_third_angle.svg`.
- **Resolving for Third angle**, first match wins:
  1. A file `<stem>_third_angle.svg` that sits next to the base template is used. This
     lets users supply their own third-angle company templates.
  2. Otherwise, if the base template lies under `<Templates>` and contains
     the five `first_angle_` elements, JellyJams derives the variant at
     runtime into `<FreeCAD.getUserAppDataDir()>/JellyJams/templates/<stem>_third_angle.svg`.
     The variant is created or refreshed whenever it is needed. Writes use a
     unique temporary file in the cache folder and replace the destination only
     after completion. Failed writes preserve an existing variant, remove their
     own temporary file, and leave unrelated `.tmp` files untouched. Derived
     content:
     - identical to the original except for the symbol;
     - the end view (both circles and the vertical centre line) moves to the
       LEFT of the side view;
     - the trapezoid moves to the right and keeps its orientation, so its
       narrow end now faces the circles;
     - the symbol keeps its overall footprint, and the horizontal centre line
       stays unchanged;
     - the element ids use the prefix `third_angle_` instead of
       `first_angle_`.
  3. Otherwise the base template is used unchanged. This covers templates
     without that symbol (blank, no title block) and custom templates that
     have a fixed symbol.
- **Resolving for First angle**, the base template is used:
  - For a template whose stem ends in `_third_angle`, the base is the same name
    without `_third_angle` in the same folder if that file exists. Otherwise it is the
    FreeCAD ISO template of that name.
  - If no base can be found, the template stays as it is.
- **Failures.** If deriving fails (for example the folder is not writable),
  the base template is used and a warning goes to the Report view.
- **Storage.** `DrawSVGTemplate` embeds the template in the document
  (`PageResult`, a FileIncluded property). A drawing therefore keeps showing
  the correct sheet on machines where the derived file or the original
  template path does not exist.

---

## 7. Shapes on the sheet: the sheet sketch (`JellyJams_*OnSheet`)

### 7.1 Concept

TechDraw has no constraint solver, so drawing on the sheet happens in a normal
Sketcher sketch that belongs to the sheet: the **sheet sketch**.

- A TechDraw view shows the sheet sketch on the sheet at scale 1:1. This is
  the **sheet sketch view**.
- While the sketch is in edit, a **sheet frame** is shown inside it. The frame
  is the outline of the sheet as four blocked construction lines, so the user
  can see and snap to where on the sheet they are drawing.
- A point drawn at (x, y) relative to the frame's lower-left corner appears on
  the sheet at (x, y) mm from the sheet's lower-left corner.

| Command | Sketcher tool started |
|---|---|
| `JellyJams_LineOnSheet` | `Sketcher_CreatePolyline` |
| `JellyJams_CornerRectangleOnSheet` | `Sketcher_CreateRectangle` |
| `JellyJams_CircleOnSheet` | `Sketcher_CreateCircle` |
| `JellyJams_CenterpointArcOnSheet` | `Sketcher_CreateArc` |
| `JellyJams_PolygonOnSheet` | `Sketcher_CreateRegularPolygon` |

### 7.2 Behavior when a shape command runs

1. **Target sheet.** Determined by section 3.
2. **Find or create the sheet sketch.** The sheet sketch is the object in the
   sheet's document whose `HostSheet` property links to that sheet.
   There is at most one per sheet. If it does not exist, it is created as ONE
   undo step named "Sheet Sketch" (7.3).
3. **Already in edit.** If the sheet sketch is already being edited, the
   command only starts the Sketcher tool. It does not create a second sketch
   and does not reopen the edit.
4. **Align the frame with the sheet** (7.4).
5. **3D window.** If the document has no 3D view window (MDI class
   `Gui::View3DInventor`), one is opened with FreeCAD's `Std_ViewCreate`.
   A drawing file normally has none.
6. **Edit.** The sheet sketch enters edit mode. The ribbon area switches to
   its Sketch tab while a sketch is in edit.
7. **Start the tool.** About 150 ms after edit mode starts, the active view
   zooms to fit (`ViewFit`). While editing, the frame counts toward the fit,
   so the whole sheet is visible. Then the Sketcher tool for the shape starts.
   The user now draws with the Sketcher and can add relations and dimensions
   freely.
8. **On Exit Sketch** (the edit ends by any means), within about 0.5 s:
   - the sheet sketch view is re-placed so the drawing lands where it was
     drawn relative to the frame (7.4);
   - the document is recomputed if anything moved;
   - the sheet window is brought to the front, as if the sheet were
     double-clicked in the tree.

   This happens even if the user switched workbenches during the edit.
9. **(should)** Editing the sheet sketch by other means, such as
   double-clicking it in the tree, behaves the same: the frame is aligned when
   the edit starts and the view is re-placed after it ends.

### 7.3 Created objects

**Sheet sketch:** a `Sketcher::SketchObject`, internal name base `SheetSketch`.

- Not attached: `MapMode` = `Deactivated`, identity placement (XY plane).
- Dynamic property `HostSheet`: type `App::PropertyLinkHidden`, group
  `JellyJams`. Value: the sheet (`TechDraw::DrawPage`).
- Dynamic property `BorderLineIndex`: type `App::PropertyInteger`, group
  `JellyJams`. Value: the geometry index of the first of the four frame lines.
- Geometry: the sheet frame. Four construction line segments at consecutive
  indices, in this order:
  - bottom (0,0)→(W,0)
  - right (W,0)→(W,H)
  - top (W,H)→(0,H)
  - left (0,H)→(0,0)

  Each line has a `Block` constraint. W and H are the template's
  `Width`/`Height` in mm. If those are invalid or not greater than 0, the
  fallback is 297 × 210.

**Sheet sketch view:** a `TechDraw::DrawViewPart`, internal name base
`SheetSketchView`, added to the sheet.

- Dynamic property `ShownSketch`: type `App::PropertyLinkHidden`,
  group `JellyJams`. Value: the sheet sketch.
- `Source` = [sheet sketch], `Direction` = (0,0,1), `XDirection` = (1,0,0).
- `ScaleType` = `Custom`, `Scale` = 1.0.
- `X`, `Y` = sheet centre (W/2, H/2) while the sketch is empty.
- `LockPosition` = False, so the user can drag the whole drawing on the sheet.

**No dependency cycle (MUST).** The sheet already depends on the view
(`Views`), and the view depends on the sketch (`Source`). The back-references
(sketch → sheet, view → sketch) MUST therefore be hidden links
(`App::PropertyLinkHidden`), which do not take part in FreeCAD's dependency
graph. An ordinary link from the sketch to the sheet would close a cycle, and
the sketch and view would stay touched forever. Required results:

- the sheet does not appear in the sketch's `OutList`;
- after `recompute()` every object of the drawing is `Up-to-date` (no
  `Touched` state);
- the Report view shows no cyclic-dependency message;
- reopening the saved file shows no object needing a recompute.

The frame lines are construction geometry. They are not part of the sketch's
`Shape`, so they never appear on the sheet or in PDF/DXF output.

Tree labels: the naming area labels the sheet sketch `Sheet Sketch1`, `Sheet
Sketch2` … and the view `Sheet Sketch View1` …. It recognizes them by the
`HostSheet` / `ShownSketch` properties.

### 7.4 Keeping the frame and the view in step (the drawing is movable)

TechDraw centers a view's geometry, meaning the centre of its bounding box,
on the view's `X`/`Y`. The user may also drag the sheet sketch view anywhere
on the sheet. Requirements:

- **Offset.** offset = (view `X`, `Y`) − (centre of the bounding box of the
  sketch's real geometry, from the sketch `Shape`). The offset is 0 when the
  sketch is empty or the view is missing.
- **When an edit starts**, the frame is moved so its lower-left corner sits at
  −offset in sketch coordinates. The frame then matches where the drawing
  actually sits on the sheet. The frame is replaced (old four lines and their
  Block constraints removed, four new blocked lines appended,
  `BorderLineIndex` updated) only when its corner position or its size (current
  sheet W×H) changed by more than 1e-6 mm. Otherwise the sketch is left
  untouched.
- **When the edit ends**, the view's `X`/`Y` are set to the new
  bounding-box centre + the offset measured when the edit started. If the
  sketch is empty, the view does not move.
- **Net effect.** Dragging the drawing on the sheet and then adding shapes
  never makes existing shapes jump.
- **Undo and redo outside an edit.** When an undo or redo changes a sheet
  sketch's geometry while it is not in edit, the sheet sketch view is
  re-placed by the same rule, with the offset taken from the frame. Nothing
  moves when the real geometry kept its centre, when the sketch is empty, or
  when the frame cannot be found.
- **Safety.** JellyJams MUST only delete frame geometry it can verify: four
  consecutive construction lines at the recorded index whose direction
  vectors are (W,0), (0,H), (−W,0), (0,−H), within 1e-6. If the recorded
  index does not point at such a frame, because the user deleted or edited
  frame lines:
  - it searches the sketch for such a quadruple;
  - if one is found, it records that index;
  - otherwise it adds a fresh frame.

  User geometry is never deleted.
- **Incomplete sheet sketches:**
  - **No `BorderLineIndex` property.** The property is added (type and group as
    above). The frame is detected with the same quadruple search, or added if
    none is found.
  - **View has `LockPosition` = True.** It is set to False.
- **Missing view.** If the sheet sketch exists but its view is gone, a new
  sheet sketch view is created (as in 7.3) when the next shape command runs.

---

## 8. Text on the sheet (`JellyJams_Note`)

### 8.1 Command behavior

- **Editing.** If the selection contains a **JellyJams text** (a
  `TechDraw::DrawViewAnnotation` that has the property `SheetNote`), the text
  dialog opens for it (8.3).
- **Placing.** Otherwise the command enters **position picking** on the
  target sheet. Picking requires the active MDI window to be a sheet window
  (`TechDrawGui::MDIViewPage`). If it is not, the status bar tells the user to
  click into the sheet window first and then press Text, and nothing else
  happens.

### 8.2 Position picking

- **Start.** Starting picking ends any picking already in progress. While it
  runs:
  - the cursor over the sheet is a crosshair;
  - the main window's status bar tells the user to click a position on the
    sheet and that Esc cancels.
- **Left click on the sheet.**
  - The clicked point becomes sheet coordinates in mm: x = sceneX ÷ Rez,
    y = −sceneY ÷ Rez. The TechDraw scene's y axis points down; the sheet's
    points up.
  - Rez is FreeCAD parameter `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`,
    float `Resolution`, default 10 when absent or 0.
  - The click is consumed: no selection change and no sheet drag.
  - Picking ends: cursor restored, status message cleared.
  - Then, after the click event has finished processing (never inside the
    mouse event), the text dialog opens for a new text at that point.
- **Esc or right click.** Picking ends and no dialog opens. The event is
  consumed.
- **Other mouse buttons and events** pass through to TechDraw unchanged.
- **Leaving the workbench.** Deactivating the JellyJams workbench ends any
  running picking, restoring the cursor and the status bar.

### 8.3 Text dialog

A modal dialog titled "Text", parented to the main window, with:

- **"Text:"** — a single-line field. The two-character sequence backslash + n
  splits the text into lines.
- **"Height:"** — a number field (range 0.5–500, 2 decimals) plus a unit
  drop-down with `mm` and `pt` (1 pt = 25.4/72 mm). Switching the unit
  converts the displayed number, so the physical height stays the same.
- **"Standard height (ISO 3098):"** — a drop-down. Its first entry is `–`,
  followed by 2.5, 3.5, 5, 7, 10, 14 and 20 mm. Picking an entry sets the
  height field, converted to the current unit.
- OK and Cancel.

Prefill:

- **New text:** empty text. The height is the last-used height in the
  last-used unit. Without history, 3.5 mm.
- **Editing:** the text's lines joined with backslash + n. The height is the
  object's `TextSize`, shown in the last-used unit.

On OK:

- If the text is empty or only whitespace, or the height is ≤ 0, nothing is
  created or changed. Editing never deletes a text.
- Otherwise the height (in mm) and the unit are remembered in the parameters
  (8.5).
- **New text:** ONE undo step named "Text" creates a
  `TechDraw::DrawViewAnnotation` (internal name base `Text`) with:
  - dynamic property `SheetNote` (`App::PropertyBool`, group `JellyJams`) =
    True;
  - `Text` = the lines;
  - `TextSize` = the height in mm;
  - it is added to the sheet at `X`, `Y` = the clicked point.

  The document is recomputed. If creation fails, the undo step is aborted,
  nothing remains, and the error goes to the Report view.
- **Editing:** ONE undo step named "Text" sets `Text` and `TextSize`, then
  the document is recomputed.

Cancel does nothing.

The text remains a normal TechDraw view, movable by dragging. The naming area
labels JellyJams texts `Text1`, `Text2` … in the tree, recognizing them by the
`SheetNote` property.

### 8.4 Plain TechDraw annotations

Annotations without `SheetNote`, such as section view labels, are not JellyJams
texts. Selecting one does not turn the command into an edit.

### 8.5 Parameters

Group `User parameter:BaseApp/Preferences/Mod/JellyJams`:

- **Float `LastNoteHeight`** — last-used letter height in mm. Default 3.5 when
  absent or 0.
- **String `LastNoteUnit`** — `mm` or `pt`. Default `mm`; any other value counts
  as `mm`.

---

## 9. Insert Picture (`JellyJams_InsertPicture`)

### 9.1 Command behavior

**Editing an existing picture.** The selection contains a **picture** when it
has a `TechDraw::DrawViewImage`, or a `TechDraw::DrawViewSymbol` WITHOUT a
non-empty `SymbolType` property. A non-empty `SymbolType` marks JellyJams' own
symbols (for example `surface`, `weld`); they have their own dialogs and are
not pictures. If the selection contains a picture:

- the picture panel opens for it (9.3);
- an undo step named "Edit Picture" opens and stays open until the panel
  closes.

**Inserting a new picture.** Otherwise, for the target sheet:

1. An open-file dialog titled "Insert Picture" appears.
   - It starts in the folder of the drawing file, or else the home folder.
   - Filters: "Pictures (*.svg *.png *.jpg *.jpeg *.bmp)", "SVG (*.svg)",
     "PNG / JPG (*.png *.jpg *.jpeg)".
   - Cancel does nothing.
2. The file is read first. With any extension other than those below, an
   unreadable file, or an SVG that is not UTF-8, the error goes to the Report
   view and nothing happens: no undo step is opened.
3. An undo step named "Insert Picture" opens and stays open until the panel
   closes (a persistent application transaction, because FreeCAD would
   otherwise close it when the command returns). The picture is created
   according to its file extension (case-insensitive):
   - **`.svg`:** `TechDraw::DrawViewSymbol` with `Symbol` = the file content,
     read as UTF-8. It stays vector graphics and is sharp in the PDF.
   - **`.png`, `.jpg`, `.jpeg`, `.bmp`:** `TechDraw::DrawViewImage` with
     `ImageFile` = the path. FreeCAD embeds the file in the document
     (`ImageIncluded`).
   - If creating the object fails, the undo step is aborted, nothing
     remains, and the error goes to the Report view.
4. Settings for the new picture:
   - internal name base `Picture`;
   - `ScaleType` = `Custom`;
   - `Scale` = the initial scale (9.2);
   - added to the sheet at `X`, `Y` = sheet centre.
5. The document is recomputed and the picture panel opens.

The naming area labels pictures `Picture1`, `Picture2` … in the tree.

### 9.2 Size model

TechDraw stores only a scale. JellyJams works with the width in mm.

- **Natural size** is the width × height in mm at `Scale` 1, matching how
  TechDraw renders the picture. Rez is the TechDraw parameter from 8.2.
  - **Bitmap:** pixel width ÷ Rez × pixel height ÷ Rez, using the size read
    from the image file.
  - **SVG,** read from the root `<svg>` element's `width`, `height` and
    `viewBox`:
    - height in `mm` and a viewBox present: the viewBox width × height;
    - width or height missing but a viewBox present: viewBox ÷ Rez;
    - width or height in `%`: viewBox ÷ Rez (unknown without a viewBox);
    - otherwise: width and height converted to px, then ÷ Rez.

      | Unit | px |
      |---|---|
      | none or `px` | 1 |
      | `pt` | 96/72 |
      | `pc` | 16 |
      | `in` | 96 |
      | `cm` | 96/2.54 |
      | `mm` | 96/25.4 |
  - When no rule applies, the natural size is **unknown**.
- **Width:** width = natural width × `Scale`. Setting a width sets
  `Scale` = width ÷ natural width. The height always follows the aspect ratio.
- **Initial scale for a new picture:** the original size, but no wider than
  a quarter of the sheet width: `Scale` = min(1, 0.25 × sheet width ÷ natural
  width). It is 1 when the natural size is unknown.

### 9.3 Picture panel

A panel in the Tasks area with objectName `JellyJamsPictureForm` and window title
"Insert Picture". It contains:

| Field | Range and format |
|---|---|
| **Position X** (centre) | mm, −2000…2000, 1 decimal |
| **Position Y** (centre) | mm, −2000…2000, 1 decimal |
| **Width** | mm, 0.1…5000, 1 decimal. Disabled when the natural size is unknown. |
| **Height** | read-only text: the computed height in mm with a note that it follows the aspect ratio, or `–` when unknown |
| **Rotation** | degrees, −360…360, 1 decimal |

Both position fields refer to the picture's centre and are measured from the
sheet's lower-left corner; the two spin boxes carry a tooltip stating this.

Live behavior:

- **Field edits apply immediately.** Changing any field sets the picture's
  `X`, `Y`, `Scale` (from the width) and `Rotation`, then recomputes.
- **The picture is the source of truth.** About every 0.2 s the panel reads
  the picture's current values. Any field that differs by more than 0.05 is
  updated to the picture's value without writing back. This keeps the panel
  in step when the user drags the picture with the mouse.
- **OK** does NOT write the field values onto the picture. It takes a final
  reading from the picture (so a just-finished drag is kept), commits the
  undo step and closes. A newly inserted picture plus all changes form one
  undo step.
- **Cancel** aborts the undo step. A newly inserted picture disappears; edits
  to an existing picture are rolled back. The document is recomputed and the
  panel closes.
- **Undo step closed early.** Another FreeCAD action, such as TechDraw's own
  drag of the picture, can commit the open undo step before the panel closes.
  Cancel then removes a newly inserted picture directly, or writes the
  previous `X`, `Y`, `Scale` and `Rotation` of an edited picture back, so the
  sheet still ends as before; the undo history then holds separate steps.
- **Picture deleted while the panel is open.** Syncing quietly stops failing
  and no error dialogs appear.

---

## 10. FreeCAD state read or changed (summary)

**Parameters read (never written):**

- `User parameter:BaseApp/Preferences/Mod/TechDraw/Rez`, Float `Resolution`
  (default 10)
- `User parameter:BaseApp/Preferences/Mod/TechDraw/Files`, String
  `TemplateFile`
- `User parameter:BaseApp/Preferences/Document`, String `prefAuthor`

**Parameters written (JellyJams' own):**
`User parameter:BaseApp/Preferences/Mod/JellyJams`, Float `LastNoteHeight` and
String `LastNoteUnit`.

**FreeCAD commands run:**

- `Std_SaveAs`
- `Std_ViewCreate`
- `Sketcher_CreatePolyline`, `Sketcher_CreateRectangle`,
  `Sketcher_CreateCircle`, `Sketcher_CreateArc`,
  `Sketcher_CreateRegularPolygon`
- the view message `ViewFit`

**Document object types created:**

- `TechDraw::DrawSVGTemplate`
- `TechDraw::DrawPage`
- `TechDraw::DrawProjGroup`
- `TechDraw::DrawViewPart`
- `TechDraw::DrawViewAnnotation`
- `TechDraw::DrawViewImage`
- `TechDraw::DrawViewSymbol`
- `Sketcher::SketchObject`

**FreeCAD properties set:**

| Object | Properties |
|---|---|
| Template | `Template`, `EditableTexts` |
| Page | `Template`, `ProjectionType`, `Label` |
| Projection group | `ProjectionType`, `XSource`, `ScaleType`, `Label`, `AutoDistribute` (via the projected-views area) |
| Any view | `X`, `Y`, `Scale`, `ScaleType`, `Rotation`, `LockPosition` |
| Part view | `Source`, `Direction`, `XDirection` |
| Annotation | `Text`, `TextSize` |
| Symbol | `Symbol` |
| Image | `ImageFile` |
| Sketch | `MapMode`, geometry, `Block` constraints |

**JellyJams properties stored in users' documents** (file-compatibility
contract; exact names, types and group `JellyJams`):

| Property | Type | On | Meaning |
|---|---|---|---|
| `HostSheet` | `App::PropertyLinkHidden` | sheet sketch (`Sketcher::SketchObject`) | the sheet it belongs to |
| `ShownSketch` | `App::PropertyLinkHidden` | sheet sketch view (`TechDraw::DrawViewPart`) | the sheet sketch it shows |
| `BorderLineIndex` | `App::PropertyInteger` | sheet sketch | geometry index of the first of the four frame lines |
| `SheetNote` | `App::PropertyBool` | `TechDraw::DrawViewAnnotation` | marks a JellyJams text (True) |
| `SymbolType` | (owned by the drawing-symbols area) | `TechDraw::DrawViewSymbol` | read only here: non-empty means "not a picture" |

**Files written outside documents:** derived third-angle templates in
`<FreeCAD.getUserAppDataDir()>/JellyJams/templates/`.

**Qt objectNames:** `JellyJamsSheetPropertiesForm` (panel), `JellyJamsPictureForm` (panel),
`JellyJamsSectionCaption` (section headings).

**Undo step names:**

- "Sheet Properties"
- "Sheet Sketch"
- "Text"
- "Insert Picture"
- "Edit Picture"

---

## 11. Persistence and restore

- This area changes **no FreeCAD preference**, so it needs no exact-restore
  record. It MUST NOT change TechDraw, Sketcher or Document preferences.
- `LastNoteHeight` and `LastNoteUnit` are ordinary JellyJams preferences. They persist
  across sessions and are not restored on workbench exit.
- All document content uses dynamic properties and standard FreeCAD types.
  Drawings made with JellyJams open, display and recompute correctly in plain
  FreeCAD without JellyJams installed. The properties in the `JellyJams`
  group are simply carried along.
- Templates and pictures are embedded in the FCStd (`PageResult`,
  `ImageIncluded`). Moving or deleting the original files, or the derived
  template cache, does not break saved drawings. The derived-template folder
  can be deleted at any time; files are recreated on demand.
- **Runtime-only state** is never persisted: the position-picking mode, the
  watcher for the end of a sheet-sketch edit, and the picture panel's sync.
  - On workbench deactivation, picking ends and the cursor and status bar are
    restored.
  - On a crash nothing needs recovery. The next shape command re-aligns the
    frame with the view's actual position (7.4).
- **Loading documents** (`Restoring`) and undo/redo never create or modify
  sheet sketches, texts or pictures.

---

## 12. Edge cases and failure handling

- **Make Drawing:**
  - Run from a drawing document: disabled.
  - Run with a never-saved model: Save As is offered first.
  - The model's file has no folder: the suggestion falls back to home.
  - A file name with spaces or non-ASCII characters: the Label keeps the
    name; the internal Name is sanitized.
  - Any failure after the document was created: the error is reported, and
    the half-made document stays open for inspection.
- **Templates missing:** the fallback chain in 6.2 applies. If even the
  default template is missing, the error is reported and the drawing is not
  completed.
- **Template change in Sheet Properties:**
  - title-block values carry over for keys both templates share;
  - keys that exist only in the new template become empty, never sample
    placeholders;
  - views keep their relative position.
- **Custom template (Browse…) with a fixed symbol:** switching the method
  changes the views and the page, not the symbol, unless a sibling
  `<stem>_third_angle.svg` exists.
- **Sheet Properties OK with nothing changed:** the title block is written
  as-is. This is harmless.
- **Sheet sketch:**
  - Shape command while a different object is in edit: FreeCAD's own edit
    handling applies (the command is disabled while a task dialog is open).
  - Document closed during the edit: the end-of-edit handling silently does
    nothing.
  - Sheet sketch or sheet deleted during the edit: same, silently nothing.
  - Errors starting a Sketcher tool: reported in the Report view; the sketch
    stays in edit.
- **Multiple sheets in one document:** each sheet has its own sheet sketch,
  identified by `HostSheet`. Commands act on the target sheet (section
  3).
- **Text:**
  - The active window is not a sheet: a status-bar hint only.
  - Picking is started twice: the first picking ends cleanly.
  - Esc or a right click while picking: nothing is created.
  - A dialog with an empty text: nothing is created.
- **Insert Picture:**
  - Unsupported extension, unreadable file, or an SVG that is not UTF-8: the
    error is reported and nothing is inserted.
  - Picture dimensions cannot be determined: the Width field is disabled and
    the scale stays 1.
  - Sheet without a valid template size: the picture is not centered, but
    stays at its default position.
- **A task dialog is already open:** Sheet Properties, Insert Picture, Text
  and the Shapes are disabled. Exception: while the target sheet's own sheet
  sketch is in edit, the shape commands stay enabled and only start their
  tool (7.2 step 3).
- **All errors:** reported to the Report view with a "JellyJams:" prefix.
  Expected situations (a user cancel, a missing optional value) are silent.

---

## 13. Acceptance criteria

Setup: FreeCAD 1.1 with JellyJams; the JellyJams workbench is active unless
stated otherwise.

**Make Drawing**

1. Ribbon Drawing tab: the first group shows "Make Drawing" and a text stack
   with "Sheet Properties", "Add Sheet" and "Insert Picture". The sheet-sketch
   group shows the five shape buttons (Line, Corner Rectangle, Circle,
   Centerpoint Arc, Polygon) as icons. The Annotation group's Note flyout runs
   `JellyJams_Note` by default. The icons of these JellyJams commands are
   originals, not FreeCAD icons.
2. With a new part (PartDesign Body with a 40×30×20 mm Pad) never saved,
   Make Drawing shows the save-first message and opens Save As. Cancelling it
   ends the command with no new document.
3. With that part saved as `Shaft.FCStd` (Label "Shaft"), Make Drawing offers
   "A4 portrait" and "A3 landscape", with "A4 portrait" preselected. With a
   part whose largest dimension is 220 mm, "A3 landscape" is preselected.
4. The save dialog suggests `<same folder>/Shaft_Drawing.FCStd`. Choosing
   `Shaft Drawing` with no extension creates `Shaft Drawing.FCStd`; the
   document Label is `Shaft Drawing` and its internal Name is
   `Shaft_Drawing`.
5. The new drawing contains exactly one `DrawSVGTemplate`, one `DrawPage`
   (Label `Sheet1`) and one `DrawProjGroup` (Label `Standard 3 View`). Its
   `XSource` is the Body. The views are Front, Top and Right in third-angle
   arrangement (Top above Front, Right to its right), `ScaleType`
   `Automatic`, and `AutoDistribute` False. The page and group
   `ProjectionType` are `Third angle`.
6. The template is FreeCAD's `A4_Portrait_ISO5457_advanced.svg` resolved to
   third angle. `Template` points to
   `<UserAppData>/JellyJams/templates/A4_Portrait_ISO5457_advanced_third_angle.svg`.
   That file exists, contains no `first_angle_` ids, contains the
   `third_angle_` ids, and the sheet shows circles LEFT of the trapezoid with
   the trapezoid's narrow end facing them.
7. The title block shows:
   - Title "Shaft", Drawing number "Shaft Drawing", Scale in colon notation
     (e.g. "1:2"), Date of issue = today as YYYY-MM-DD, Language "EN";
   - Drawn by = the author from FreeCAD's Document preferences, or the OS
     login name;
   - none of FreeCAD's sample texts (the fictitious author and approver
     names of the stock templates, DN, AAA, ST1, ST2, RD, the sample
     material). Fields without a derived value are empty.
8. The drawing file was saved before the views were linked: no "Owner
   document not saved" error appears in the Report view. After the command
   the file on disk contains the views (reopening it shows them). The
   drawing is the active document and its sheet window is in front.
9. With the drawing active, Make Drawing is disabled.
   `FreeCADGui.runCommand("JellyJams_MakeDrawing", 1)` from a part behaves exactly
   like the Drawing-tab button.
10. Cancelling the format dialog or the save dialog creates no document.

**Sheet Properties**

11. In the drawing, Sheet Properties opens a Tasks panel (objectName
    `JellyJamsSheetPropertiesForm`) with "Sheet Format/Size", "Type of projection" and
    "Title Block" sections, in that order.
12. The format list starts with "A4 portrait – title block ISO 7200", then
    "A3 landscape – title block ISO 7200", then the other files of
    `<Templates>/ISO/` by file name. It has no entry from `localized/` or
    `titleblocks/` and no `_third_angle` entry. For the drawing from criterion 6, the
    selected entry is "A4 portrait – title block ISO 7200".
13. "Type of projection" shows Third angle selected. Choosing First angle and
    pressing OK:
    - sets page and group `ProjectionType` to `First angle`;
    - points the template back at FreeCAD's original
      `A4_Portrait_ISO5457_advanced.svg`;
    - shows the first-angle symbol;
    - creates one undo step "Sheet Properties". Undo restores everything.
14. Title-block fields appear in the documented order with the documented
    labels (e.g. `creator` as "Drawn by"). Editing "Title" to "Shaft
    housing" and pressing OK updates the title block; Cancel discards edits.
15. Switching the format to "A3 landscape – title block ISO 7200" and pressing
    OK:
    - keeps every title-block value whose key exists in both templates;
    - leaves no sample placeholder;
    - moves each top-level view so its relative position on the sheet is
      unchanged (a view at X=105 on A4 portrait moves to X=210 on A3
      landscape; Y is unchanged because both heights are 297 mm).
16. "Fill from Model" overwrites Title, Drawing number, Material (when the
    body has a material), Scale, Drawn by, Date of issue and Language in the
    panel. The document changes only after OK.
17. "Browse…" accepts any SVG. The panel then shows `Custom: <file name>`
    selected, and OK switches the sheet to it. A sheet whose template is not
    in the catalog opens with `Custom: <file name>` preselected.
18. With a task dialog open (for example a part sketch in edit), Sheet
    Properties, Insert Picture, Text and all Shapes are disabled. While the
    sheet's own sheet sketch is in edit, the Shapes stay enabled.

**Shapes / sheet sketch**

19. On an A3 landscape sheet (420×297), choosing Circle in the Drawing tab's
    sheet-sketch group has these results:
    - a 3D window opens if the drawing had none;
    - a sketch enters edit and is zoomed so the whole sheet frame is visible;
    - the Circle tool is active;
    - the tree shows "Sheet Sketch1" and "Sheet Sketch View1";
    - the sketch has 4 construction lines (0,0)-(420,0), (420,0)-(420,297),
      (420,297)-(0,297), (0,297)-(0,0), each with a Block constraint;
    - `BorderLineIndex` = the index of the first line.
20. The sketch has `HostSheet` (`App::PropertyLinkHidden`, group
    JellyJams) linking to the page. The view has `ShownSketch`
    (`App::PropertyLinkHidden`) linking to the sketch, plus `Scale` 1.0,
    `ScaleType` Custom, `Direction` (0,0,1) and `LockPosition` False.
21. Drawing a circle centered at (100, 50) with r=10 and pressing Exit Sketch
    puts, within about half a second, a circle on the sheet centered 100 mm
    from the left edge and 50 mm from the bottom edge (view X=100, Y=50). The
    sheet window comes to the front. The frame lines are not visible on the
    sheet.
22. **No cycle:** after `App.ActiveDocument.recompute()` every object reports
    `State == ['Up-to-date']`. The page is not in the sketch's `OutList`, and
    the Report view shows no cyclic-dependency message. Saving, closing and
    reopening shows no object marked for recompute.
23. Dragging "Sheet Sketch View1" on the sheet by (+50, +30) mm and then
    choosing Line in the sheet-sketch group has these results:
    - the frame in the sketch now starts at (−50, −30), so the circle sits at
      (150, 80) relative to the frame's lower-left corner, which matches its
      position on the sheet;
    - after drawing a line and Exit Sketch, the circle is still at
      (150, 80) mm on the sheet and the new line appears where it was drawn
      relative to the frame.
24. Running a shape command while the sheet sketch is already in edit (via
    `FreeCADGui.runCommand`) starts only the tool. There is no second sheet
    sketch and no reopening.
25. A second sheet in the same document gets its own sheet sketch when a
    shape is drawn while that sheet's window is active.
26. Undo right after the first shape command removes the sheet sketch and its
    view in one step ("Sheet Sketch").
27. Deleting the sheet sketch's frame lines manually and running a shape
    command again deletes no user geometry. A new blocked frame is added and
    `BorderLineIndex` points at it.
28. (should) Double-clicking "Sheet Sketch1" in the tree, adding a line and
    exiting re-places the view the same way as criterion 21 or 23.

**Text**

29. With the sheet window active, pressing Text gives a crosshair cursor over
    the sheet and the status-bar hint. Clicking at a point 120 mm from the
    left and 80 mm from the bottom opens the "Text" dialog. Entering
    "Deburr all holes" with 5 mm and OK creates a `DrawViewAnnotation` labeled
    `Text1` with:
    - `SheetNote` True (`App::PropertyBool`, group JellyJams);
    - `Text` ["Deburr all holes"];
    - `TextSize` 5 mm;
    - X=120, Y=80.

    There is exactly one undo step "Text".
30. Entering `Line 1\nLine 2` produces `Text` ["Line 1", "Line 2"].
31. Pressing Text, then Esc (or a right click) on the sheet: no dialog, no
    object, cursor restored. Pressing Text, clicking, and OK with an empty
    text: no object.
32. The next new-text dialog is prefilled with 5 mm. Switching the unit to pt
    shows ≈14.17. Choosing "Standard height" 7 mm while in pt shows ≈19.84.
33. Selecting `Text1` and pressing Text opens the dialog prefilled with its
    text and height. Changing it to "changed" at 10 pt and OK sets `Text`
    ["changed"] and `TextSize` ≈3.528 mm. The parameters `Mod/JellyJams`
    `LastNoteHeight` ≈3.528 and `LastNoteUnit` "pt" are stored.
34. Pressing Text while a 3D window (not a sheet) is active shows only the
    status-bar hint.
35. Pressing Text and then switching to another workbench ends picking: the
    cursor over the sheet is normal and clicks select as usual.

**Insert Picture**

36. Inserting an SVG whose root has `width="64mm" height="24mm" viewBox="0 0 64 24"`
    onto an A3 landscape sheet creates a `DrawViewSymbol` labeled `Picture1`
    with:
    - the file content in `Symbol`;
    - `ScaleType` Custom, `Scale` 1.0;
    - X=210, Y=148.5.

    The panel (objectName `JellyJamsPictureForm`) shows Width 64.0 mm and Height
    24.0 mm.
37. Inserting a 2000×1000 px JPG (Rez 10) creates a `DrawViewImage` with
    `ImageFile` set and `Scale` 0.525, which is 25 % of 420 mm ÷ 200 mm. The
    image is embedded: after saving, moving the JPG away and reopening still
    shows it.
38. In the panel, setting Width 100 makes the picture 100 mm wide (`Scale`
    2.0 for the SVG above) and Height reads 40.0 mm. Setting X=30, Y=40 and
    Rotation 90 moves and rotates the picture immediately.
39. Dragging the picture with the mouse while the panel is open updates
    Position X/Y within about 0.2 s. Pressing OK leaves the picture where it
    was dragged, not at the older field values.
40. Cancel on a newly inserted picture removes it. Cancel on an edited
    existing picture restores its previous position, size and rotation. OK
    after inserting creates exactly one undo step "Insert Picture".
41. Selecting a picture and pressing Insert Picture opens the panel for that
    picture, with no file dialog. Selecting a JellyJams surface-finish or
    weld symbol (non-empty `SymbolType`) and pressing Insert Picture opens the
    file dialog instead, so the symbol is not treated as a picture.
42. Choosing a `.pdf` (by typing the name) inserts nothing and reports an
    error in the Report view.

**General**

43. A drawing made with JellyJams opens and recomputes without errors in
    FreeCAD with JellyJams uninstalled. The sheet sketch view, texts and
    pictures display normally.
44. Using every feature in this area leaves the FreeCAD parameter groups
    `Preferences/Mod/TechDraw`, `Preferences/Mod/Sketcher` and
    `Preferences/Document` unchanged. Only `Preferences/Mod/JellyJams`
    `LastNoteHeight` / `LastNoteUnit` are written.
45. No file, identifier, objectName or icon name in this area contains
    "SolidWorks". No template SVG ships with JellyJams.
