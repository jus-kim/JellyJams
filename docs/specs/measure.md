# Measure

| Field | Value |
|---|---|
| Implemented in | `jellyjams/measure.py`, ribbon dispatch in `ribbon.py`, colours in `palette.py` |
| Status | [Implementation and verification](../status.md) |

## References and measurement catalog

The official [Measure tool help](https://help.solidworks.com/2023/english/SolidWorks/sldworks/HIDD_MEASURE.htm),
[measurement result members](https://help.solidworks.com/2018/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMeasure_members.html),
and [current Measure tool help](https://help.solidworks.com/2027/english/SolidWorks/sldworks/HIDD_MEASURE.htm)
define the reference inventory below. The screenshots supplied by the user define
the white rectangular label/value presentation. This is a capability comparison,
not a claim that JellyJams reproduces every SolidWorks measurement option.

| Quantity / mode in the reference inventory | JellyJams behavior |
|---|---|
| Length; total length | Edge/wire length; sum of selected edges/wires |
| Arc length; chord length | Circular arc length and endpoint chord |
| Radius; diameter | Circular edges, cylindrical and spherical faces |
| Circle centre; point X/Y/Z | World-space coordinates |
| Area; perimeter; total area | Face properties and selected-face totals; also total perimeter |
| Distance | Minimum separation of finite geometry in clearance mode |
| Centre distance | Circular centres, cylinder axes and spherical centres by default |
| Spherical centre distance | Spherical faces use their sphere centres |
| Angle | Lines, planes, line/plane, cylinder axes; three vertices |
| dX/dY/dZ | Optional components of the current distance endpoints |
| Arc/circle minimum distance | Clearance mode uses original edges/faces |
| Arc/circle maximum distance | Not implemented |
| Custom arc/circle references | Not implemented; the two references cannot be configured independently |
| Point-to-point | Two vertices supported; arbitrary clicked surface points not implemented |
| Projected distance; normal distance | Not implemented as independent projection modes |
| Projected surface area | Not implemented |
| Relative coordinate system; coordinate-system rotation | World coordinates only; custom systems/rotation not implemented |

Volume is additionally shown for a selected solid/body with solid geometry; this
is a JellyJams extension, not a claim that Volume belongs to the reference
`IMeasure` result set. History, sensors, copying and custom units/precision are
separate tool controls, not additional measurement quantities. They are not
implemented here; values follow FreeCAD's unit schema and precision.

## Required behavior

1. The Evaluate ribbon's `Std_Measure` entry opens this temporary task. Native
   Tools-menu Measure remains unchanged. Do not override native Measure settings.
   The ribbon button is checkable and highlighted with Selection fill and an
   Accent border for the entire active session, including with no picks. Keep it
   enabled while active so it can always stop the tool, even when native Measure
   becomes disabled during a task. Clicking it again stops the session and
   removes all owned measurements immediately. Checked state follows the actual
   session, not the last click: external/task close, leave and failed activation
   must leave it unchecked. Reopening works with any existing preselection.
2. Plain successive clicks accumulate geometry. Keep unresolved root/path pairs
   so two edges on one object and placed links remain distinct. Use existing
   preselection. Defer selection restoration until native notification completes.
   Retain chronological pick order across ordinary replacement and additive clicks,
   so mixing the two does not change the three-point angle's middle vertex.
3. Resolve world geometry using `Part.getShape(root, path, needSubElement=True)`.
   A single line/curve/wire shows Length. A circular edge shows Radius, Diameter
   and Center, plus Circumference for a full circle or Arc length, Chord length
   and swept Angle for an arc. Partial circular STEP edges still have centres.
4. A vertex shows X/Y/Z. A face shows Area and its actual boundary Perimeter;
   exclude periodic seam edges. Omit a zero perimeter, including a closed sphere's
   artificial seam. Cylindrical/spherical faces also show Radius and Diameter;
   a spherical face shows Center. A whole face-bearing shape shows Area, plus
   Volume when it contains solids. Do not substitute a bounding-box estimate.
5. For two picks, **Centers / axes** is the default reference. Circular edges
   become centre vertices, cylindrical faces finite axis segments over their V
   range, and spherical faces centre vertices. Other shapes retain their finite
   geometry. **Nearest surfaces (clearance)** uses the original shapes instead.
   Calculate both with `distToShape`; label a converted-reference result
   **Center distance**, otherwise **Distance**. The dimension endpoints must be
   the actual measured points, not points on the rim when measuring its centre.
6. Where directions are well defined, include Angle: two lines, two planar faces,
   a line and plane, or a cylindrical axis and another line/plane/axis. Pair
   angles use the smaller unoriented angle (0–90 degrees); this deliberately
   omits supplementary/reflex choices. Do not infer a tangent angle on arbitrary
   curved surfaces. Three vertices measure 0–180 degrees at the second vertex;
   repeated/coincident vertices give a clear unsupported-selection result.
7. **Show XYZ distances**, initially off, adds absolute dX/dY/dZ between measured
   endpoints. Two or more edges/wires add Total length; two or more faces add
   Total area and Total perimeter. Larger mixed selections have no guessed
   distance. Unsupported selections remove the old result and show an inline
   explanation plus Report-view output.
8. A callout is an opaque **white rectangle**, with a one-pixel **black outline**,
   **black text**, and a black vertical divider between labels and values. Labels
   include a colon. Use the installed UI font at 18 screen pixels, regular weight,
   padding and rows sized from font metrics so coordinates and units fit.
   The task's separate result remains bold for readability.
9. Paint the card with Qt into an RGBA image and render it using Coin `SoImage`
   under an unpickable `SoAnnotation`. It remains upright and constant in pixel
   size, above all model geometry. Use a leader from an on-geometry anchor (or
   the measured span's midpoint) to the card. Black lines have a thin white
   underlay for dark backgrounds. No raster assets are bundled.
10. Clicking empty space, removing all picks, or Clear removes the rows, card,
    leader and distance span. Removing one pick replaces a distance callout with
    the remaining feature's size callout. Closing/reopening, external task close,
    leave/quit and document/view changes dispose of the observer/timer/scene node.
    Results never create document objects or persistent preferences.
    Use the main window's actual front view for lifetime checks, so the Start
    page also ends the session even if FreeCAD retains its last document view.
    A retired task's pending timer must not stop a newer session. Clear cached
    scene/image data even when the old native view has already been deleted.
    On hosts with document-specific task dialogs, close the measurement owner's
    dialog when switching documents, leaving the new document's task untouched.
    If the owner was deleted, its native dialog is already gone. Retain the
    no-argument close operation on older hosts that have one global task panel,
    including after the measurement owner's document was deleted.

## Acceptance cases

- A 17.05 mm line shows `Length: 17.05 mm`. A 90-degree circular arc of radius
  1.25 mm shows Radius, Diameter, Center, Arc length, Chord length and Angle.
- A 10 × 5 mm face shows 50 mm² Area and 30 mm Perimeter. A full cylinder's
  perimeter excludes its longitudinal seam; a full sphere has no fake perimeter.
- Perpendicular straight edges give a 90-degree angle; three vertices with a
  right angle at the second point also give 90 degrees. Multiple edges/faces
  show totals. Current FreeCAD units may render 100 mm² as 1 cm².
- For `moddoMOUISE_A1 Part 2.stp`, solid 202's Edge1066 or cylindrical Face1799
  with Edge1015 gives **1.500 mm** centre/axis distance and **0.925 mm** clearance.
  The hole radius is 0.575 mm. Its axis points down from
  `(184.331627927, -129.148101334, 5.306402814)` over V `[-1.04263952, 0]`.
- Native screenshots must show the complete white/black callout on the supplied
  PCB in an oblique view. Headless checks cover card colours, text bounds and
  measurement dispatch; `gui_measure.py` covers the native kernel and rendering.

The supplied STEP file remains an optional local fixture, never committed.
