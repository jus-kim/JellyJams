# Changelog

## Unreleased

- Adopt the MIT License for JellyJams code and original icons; update SPDX
  headers, package metadata, contributor guidance and documentation.

## 0.1.0 — 2026-10-28

First release.

- CommandManager-style ribbon with five tabs: Features, Sketch, Evaluate,
  Assembly, Drawing.
- SolidWorks tool names on buttons; SolidWorks tree naming (Boss-Extrude1,
  Sketch1, Top/Front/Right Plane, Assembly1, Mates, Coincident1…).
- Light SolidWorks-like theme and viewport colors, applied non-destructively.
- SolidWorks navigation style and keyboard shortcuts while the workbench is
  active: F, Z/Shift+Z, Ctrl+B, Ctrl+1…7, Ctrl+8 (Normal To) and Space
  (Orientation panel). FreeCAD commands that use one of these keys (Box Zoom,
  Hide/Show) get it back on leave.
- Orientation panel on Space, like the SolidWorks Orientation dialog: Normal
  To, a remembered view, Zoom to Fit, the standard views around Front and
  Isometric/Trimetric/Dimetric at the pointer; pin, Esc/Space, closes on a
  click elsewhere; its buttons can be reached with Tab and pressed with Space;
  readable under dark FreeCAD themes. With the pointer over the 3D view or the
  model tree, Space always opens the panel; elsewhere a focused button, check
  box or drop-down list in a dialog (also a floating one, or a dock opened
  later), or a list whose items are ticked or typed into, keeps Space.
  Toolbar, status-bar and ribbon controls never take Space.
- Normal To on Ctrl+8 and on the Evaluate tab: looks straight at one selected
  face, edge, plane or sketch (faces, edges and datums through FreeCAD's own
  Align to Selection; a whole sketch along its plane, also through a link), or
  at the sketch plane while a sketch is edited with nothing selected; says in
  the status bar and next to the pointer when there is nothing to look at.
  Space and Ctrl+8 also work while a sketch or a feature dialog is open and in
  an undocked or fullscreen 3D view, which keeps the keyboard when the panel
  closes; with the Start page or a drawing in front they do nothing. Both are
  in the JellyJams menu.
- Sketch first: Extruded Boss/Base, Extruded Cut, Revolved Boss/Base, Revolved
  Cut and Hole Wizard open a new sketch when there is no profile to use, and
  the feature starts when that sketch is exited. The cut features do so only
  in a body that already holds a solid feature; before that Extruded Cut and
  Revolved Cut get FreeCAD's own message and Hole Wizard a status-bar message
  instead of a failing Hole. With several bodies and none active, FreeCAD asks
  which body to use. Opening a sketch or editing a feature stays in JellyJams.
- Add-Relations and Add-Mate panels, create-sketch-on-face icon,
  feature-from-open-sketch gesture, SW-style drawing tools (projected views,
  view labels/scales, sheet properties, shapes/text on sheet, surface finish
  and weld symbols, multi-sheet PDF / DXF export).
- Clean restore of the stock FreeCAD UI on deactivate, quit (including the
  "switch to workbench" settings of Assembly, Part Design and TechDraw), and
  after a crash (startup recovery); an unreadable crash backup is discarded
  with one warning.
- Diagnostics command (JellyJams menu) with copyable environment details.
- Original icons for the workbench and JellyJams' own commands; FreeCAD's own
  command icons and installed ISO TechDraw templates are used at runtime, so
  no third-party assets are bundled.
