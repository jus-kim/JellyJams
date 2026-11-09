# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_SaveAsPDF and JellyJams_SaveAsDXF: write every sheet of the active drawing to disk.

TechDraw exports one sheet per file. For PDF the sheets are written to a private temporary
folder and joined with pdf_merge into a single file; if joining fails, each sheet is saved
as its own PDF next to the chosen file. DXF always gets one file per sheet.
"""

import os
import re
import shutil
import tempfile
import time

import FreeCAD

from jellyjams import commands, console, constants, doc_utils, fcgui, pdf_merge

TEMP_PREFIX = "jellyjams_pdf_"
STALE_TEMP_SECONDS = 24 * 60 * 60
RESULT_MS = 8000
FALLBACK_NAME = "Drawing"
DRAWING_NUMBER_KEY = "drawing_number"

_UNSAFE_RUN = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_KEPT_SHEET_NAME = re.compile(r"Sheet\d+")


# --- file names -------------------------------------------------------------------------------


def sanitize(name):
    """`name` made safe as a file name.

    Each run of \\ / : * ? " < > | turns into one "_", spaces and dots are stripped from both
    ends, and an empty result becomes "Drawing".
    """
    text = _UNSAFE_RUN.sub("_", "" if name is None else str(name)).strip(" .")
    return text or FALLBACK_NAME


def suggested_base(drawing_number, doc_label, doc_name):
    """Base file name: the drawing number, or the document label, or the document name."""
    for candidate in (drawing_number, doc_label, doc_name):
        text = "" if candidate is None else str(candidate).strip()
        if text:
            return sanitize(text)
    return FALLBACK_NAME


def per_sheet_paths(chosen_path, sheet_labels):
    """Output path of each sheet.

    A single sheet uses `chosen_path`. Several sheets use <stem>_<sheet name><extension>,
    where a label of the form "Sheet<n>" is kept as the sheet name and any other label
    becomes "Sheet<position>"; repeated names move on to the next free "Sheet<n>".
    """
    labels = list(sheet_labels)
    if len(labels) <= 1:
        return [chosen_path] * len(labels)
    stem, extension = os.path.splitext(chosen_path)
    used = set()
    paths = []
    for index, label in enumerate(labels, 1):
        name = sanitize(label)
        if not _KEPT_SHEET_NAME.fullmatch(name):
            name = "Sheet%d" % index
        if name in used:
            number = 2
            while "Sheet%d" % number in used:
                number += 1
            name = "Sheet%d" % number
        used.add(name)
        paths.append("%s_%s%s" % (stem, name, extension))
    return paths


def drawing_number(pages):
    """First non-blank drawing_number title-block text over `pages` in order, or ""."""
    for page in pages:
        try:
            texts = page.Template.EditableTexts or {}
            value = str(texts.get(DRAWING_NUMBER_KEY, "") or "").strip()
        except Exception:
            continue
        if value:
            return value
    return ""


def _default_folder(doc):
    file_name = str(getattr(doc, "FileName", "") or "")
    folder = os.path.dirname(file_name) if file_name else ""
    return folder if folder and os.path.isdir(folder) else os.path.expanduser("~")


def _ask_path(doc, pages, title, file_filter, extension):
    """Path picked in a Save dialog with `extension` added if missing; "" on cancel."""
    _QtCore, _QtGui, QtWidgets = fcgui.qt()
    base = suggested_base(drawing_number(pages), getattr(doc, "Label", ""), doc.Name)
    suggestion = os.path.join(_default_folder(doc), base + extension)
    path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
        fcgui.main_window(), title, suggestion, file_filter)
    if not path:
        return ""
    if not path.lower().endswith(extension):
        path += extension
    return path


# --- preparation ------------------------------------------------------------------------------


def _restore_line_widths(doc):
    with console.guard("put back the full line widths before exporting", level="log"):
        from jellyjams import zoom_lines

        zoom_lines.restore_all(doc)


def _pages_with_window(doc):
    """Names of the sheets of `doc` that currently have a page window."""
    names = set()
    try:
        import FreeCADGui

        views = FreeCADGui.getDocument(doc.Name).mdiViewsOfType(constants.CLASS_SHEET_WINDOW)
    except Exception:
        return names
    for view in views:
        try:
            names.add(view.getPage().Name)
        except Exception:
            continue
    return names


def _open_window(page):
    try:
        from jellyjams import drawing_common

        opener = drawing_common.open_sheet_window
    except Exception:
        def opener(sheet):
            sheet.ViewObject.show()
    with console.guard("show the sheet %s" % page.Label, level="log"):
        opener(page)


def _process_events():
    _QtCore, _QtGui, QtWidgets = fcgui.qt()
    with console.guard("let Qt handle pending events", level="log"):
        QtWidgets.QApplication.processEvents()


def _open_missing_windows(doc, pages):
    """Give every sheet a page window, then return to the window that was active.

    TechDraw draws a sheet's content only once a window for it has existed.
    """
    shown = _pages_with_window(doc)
    missing = [page for page in pages if page.Name not in shown]
    if not missing:
        return
    area = fcgui.mdi_area()
    previous = None
    if area is not None:
        previous = area.activeSubWindow() or area.currentSubWindow()
    for page in missing:
        _open_window(page)
    _process_events()
    if area is not None and fcgui.is_alive(previous):
        with console.guard("return to the window that was active", level="log"):
            area.setActiveSubWindow(previous)
    _process_events()


def prepare(doc, pages):
    """Full line widths, a recomputed document and rendered sheets."""
    _restore_line_widths(doc)
    doc.recompute()
    _open_missing_windows(doc, pages)
    _restore_line_widths(doc)


def _report(text):
    console.message(text)
    fcgui.status_message(text, RESULT_MS)


def _file_list(paths):
    folder = os.path.dirname(paths[0]) if paths else ""
    names = ", ".join(os.path.basename(path) for path in paths)
    return "%s (folder %s)" % (names, folder) if folder else names


# --- writing ----------------------------------------------------------------------------------


def _remove_stale_work_folders():
    """Delete day-old work folders that an interrupted export left in the temp directory."""
    cutoff = time.time() - STALE_TEMP_SECONDS
    with console.guard("remove leftover temporary PDF folders", level="log"):
        with os.scandir(tempfile.gettempdir()) as entries:
            for entry in entries:
                if (entry.name.startswith(TEMP_PREFIX) and entry.is_dir(follow_symlinks=False)
                        and entry.stat(follow_symlinks=False).st_mtime < cutoff):
                    shutil.rmtree(entry.path, ignore_errors=True)


def _write_output(path, writer):
    """Publish a nonempty completed file, preserving an existing output on failure."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(path)),
                                         prefix=".jellyjams_export_", suffix=os.path.splitext(path)[1],
                                         delete=False) as handle:
            temporary = handle.name
        writer(temporary)
        if not os.path.getsize(temporary):
            raise OSError("the exporter produced an empty file for %s" % path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def write_pdf(pages, path):
    """Write `pages` into the PDF `path`, or one PDF per sheet when merging fails."""
    import TechDrawGui

    if len(pages) == 1:
        _write_output(path, lambda temporary: TechDrawGui.exportPageAsPdf(pages[0], temporary))
        _report("PDF written (1 sheet): %s" % path)
        return
    _remove_stale_work_folders()
    work = tempfile.mkdtemp(prefix=TEMP_PREFIX)
    try:
        parts = []
        for index, page in enumerate(pages, 1):
            part = os.path.join(work, "sheet%03d.pdf" % index)
            _write_output(part, lambda temporary: TechDrawGui.exportPageAsPdf(page, temporary))
            parts.append(part)
        try:
            pdf_merge.merge(parts, path)
        except Exception as exc:
            console.warning("joining the sheets into one PDF failed (%s), so every sheet "
                            "gets its own PDF file" % exc)
            targets = per_sheet_paths(path, [page.Label for page in pages])
            for part, target in zip(parts, targets):
                _write_output(target, lambda temporary: shutil.copyfile(part, temporary))
            _report("PDF written as one file per sheet: %s" % _file_list(targets))
            return
        _report("PDF written (%d sheets): %s" % (len(pages), path))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def write_dxf(pages, path):
    """Write each sheet to its own DXF file (the chosen path when there is only one)."""
    import TechDraw

    targets = per_sheet_paths(path, [page.Label for page in pages])
    for page, target in zip(pages, targets):
        _write_output(target, lambda temporary: TechDraw.writeDXFPage(page, temporary))
    _report("DXF written: %s" % _file_list(targets))


# --- commands ---------------------------------------------------------------------------------


class _ExportCommand(commands.BaseCommand):
    extension = ""
    dialog_title = ""
    file_filter = ""
    failure = ""

    def write(self, pages, path):
        raise NotImplementedError

    def run(self):
        doc = FreeCAD.ActiveDocument
        if doc is None:
            return
        pages = doc_utils.pages(doc)
        if not pages:
            return
        path = _ask_path(doc, pages, self.dialog_title, self.file_filter, self.extension)
        if not path:
            return
        try:
            prepare(doc, pages)
            self.write(pages, path)
        except Exception as exc:
            console.error("%s failed: %s" % (self.failure, exc), with_traceback=True)

    def is_active(self):
        from jellyjams import drawing_common

        return drawing_common.drawing_tools_enabled()


class ExportPdfCommand(_ExportCommand):
    command_id = constants.CMD_SAVE_PDF
    menu_text = "Save as PDF"
    tooltip = ("Writes every sheet of the drawing into a single PDF file named after the "
               "title block's drawing number.")
    extension = ".pdf"
    dialog_title = "Save as PDF"
    file_filter = "PDF (*.pdf)"
    failure = "Save as PDF"

    def write(self, pages, path):
        write_pdf(pages, path)


class ExportDxfCommand(_ExportCommand):
    command_id = constants.CMD_SAVE_DXF
    menu_text = "Export DXF"
    tooltip = "Writes the drawing to DXF, one file for each sheet."
    extension = ".dxf"
    dialog_title = "Export DXF"
    file_filter = "DXF (*.dxf)"
    failure = "Export DXF"

    def write(self, pages, path):
        write_dxf(pages, path)


def get_commands():
    """Command table of this module: JellyJams_SaveAsPDF and JellyJams_SaveAsDXF."""
    return {
        constants.CMD_SAVE_PDF: ExportPdfCommand(),
        constants.CMD_SAVE_DXF: ExportDxfCommand(),
    }
