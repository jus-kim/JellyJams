# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Join PDF files into one, with nothing but the Python standard library.

Only plain PDFs are accepted: a single classic ``xref`` table with one trailer, no
incremental updates, no cross-reference streams and no encryption. Qt's PDF writer, which
TechDraw uses for page export, writes exactly that. Any other input raises UnsupportedPdf
before the output file is touched.

In the result, object 1 is a fresh catalog and object 2 a fresh page tree listing every page
of every input in order. All other used objects follow from number 3 on, and stream bytes
are copied unchanged.
"""

import os
import re

__all__ = ["UnsupportedPdf", "merge"]


class UnsupportedPdf(Exception):
    """Raised for an input whose structure this module cannot handle or is damaged."""


_WHITESPACE = b" \t\r\n\x0c\x00"
_DELIMITERS = b"()<>[]{}/%"
_INHERITABLE = (b"/Resources", b"/MediaBox", b"/CropBox", b"/Rotate")
_TAIL_WINDOW = 2048
_MIN_VERSION = (1, 4)

_STARTXREF = re.compile(rb"startxref\s+(\d+)\s*%%EOF")
_VERSION = re.compile(rb"%PDF-(\d+)\.(\d+)")
_OBJ_HEADER = re.compile(rb"[\s\x00]*(\d+)[\s\x00]+(\d+)[\s\x00]+obj")
_SUBSECTION = re.compile(rb"[\s\x00]*(\d+)[ \t]+(\d+)")
_XREF_ENTRY = re.compile(rb"[\s\x00]*(\d+)[ \t]+(\d+)[ \t]+([nf])")
_ENDSTREAM = re.compile(rb"[\s\x00]*endstream")
_ENDOBJ = re.compile(rb"[\s\x00]*endobj")


# --- tokenizer --------------------------------------------------------------------------------


class _Token:
    __slots__ = ("kind", "start", "stop", "text")

    def __init__(self, kind, start, stop, text):
        self.kind = kind  # "<<" ">>" "[" "]" "{" "}" "name" "int" "word" "string"
        self.start = start
        self.stop = stop
        self.text = text


def _skip_whitespace(data, pos, end):
    while pos < end and data[pos] in _WHITESPACE:
        pos += 1
    return pos


def _literal_string_end(data, pos, end):
    """Position right after the literal string whose "(" is at `pos`."""
    depth = 0
    while pos < end:
        char = data[pos]
        if char == 0x5C:  # a backslash protects the byte after it
            pos += 2
            continue
        if char == 0x28:
            depth += 1
        elif char == 0x29:
            depth -= 1
            if depth == 0:
                return pos + 1
        pos += 1
    raise UnsupportedPdf("a literal string is never closed")


def _tokenize(data, pos=0, end=None, stop_words=()):
    """Split data[pos:end] into tokens, stopping before the first keyword in `stop_words`.

    Returns (tokens, the stop keyword's token or None). Comments are left out.
    """
    if end is None:
        end = len(data)
    tokens = []
    while True:
        pos = _skip_whitespace(data, pos, end)
        if pos >= end:
            return tokens, None
        char = data[pos]
        if char == 0x25:  # % comment
            while pos < end and data[pos] not in b"\r\n":
                pos += 1
            continue
        if char == 0x28:
            stop = _literal_string_end(data, pos, end)
            tokens.append(_Token("string", pos, stop, data[pos:stop]))
            pos = stop
            continue
        if char == 0x3C:
            if data[pos + 1 : pos + 2] == b"<":
                tokens.append(_Token("<<", pos, pos + 2, b"<<"))
                pos += 2
                continue
            stop = data.find(b">", pos)
            if stop < 0 or stop >= end:
                raise UnsupportedPdf("a hex string is never closed")
            tokens.append(_Token("string", pos, stop + 1, data[pos : stop + 1]))
            pos = stop + 1
            continue
        if char == 0x3E:
            if data[pos + 1 : pos + 2] != b">":
                raise UnsupportedPdf("a single '>' outside a hex string")
            tokens.append(_Token(">>", pos, pos + 2, b">>"))
            pos += 2
            continue
        if char in b"[]{}":
            text = bytes((char,))
            tokens.append(_Token(text.decode("ascii"), pos, pos + 1, text))
            pos += 1
            continue
        start = pos
        if char == 0x2F:  # name
            pos += 1
        while pos < end and data[pos] not in _WHITESPACE and data[pos] not in _DELIMITERS:
            pos += 1
        if pos == start:
            raise UnsupportedPdf("character %r is not valid here" % bytes((char,)))
        text = data[start:pos]
        if text[:1] == b"/":
            kind = "name"
        elif text.isdigit():
            kind = "int"
        else:
            kind = "word"
        token = _Token(kind, start, pos, text)
        if kind == "word" and text in stop_words:
            return tokens, token
        tokens.append(token)


def _is_reference(tokens, index):
    """True if the three tokens starting at `index` form an indirect reference "n g R"."""
    return (
        index + 2 < len(tokens)
        and tokens[index].kind == "int"
        and tokens[index + 1].kind == "int"
        and tokens[index + 2].kind == "word"
        and tokens[index + 2].text == b"R"
    )


def _value_end(tokens, index):
    """Token index right after the value that begins at tokens[index]."""
    if index >= len(tokens):
        raise UnsupportedPdf("a dictionary key has no value")
    kind = tokens[index].kind
    if kind in ("<<", "["):
        closing = ">>" if kind == "<<" else "]"
        depth = 0
        for position in range(index, len(tokens)):
            if tokens[position].kind == kind:
                depth += 1
            elif tokens[position].kind == closing:
                depth -= 1
                if depth == 0:
                    return position + 1
        raise UnsupportedPdf("%s is opened but never closed" % kind)
    if _is_reference(tokens, index):
        return index + 3
    return index + 1


def _dictionary(tokens, index=0):
    """Outermost entries of the dictionary whose "<<" is tokens[index].

    Maps each key to (key token index, first value token index, index after the value).
    """
    if index >= len(tokens) or tokens[index].kind != "<<":
        return None
    entries = {}
    position = index + 1
    while position < len(tokens) and tokens[position].kind != ">>":
        key = tokens[position]
        if key.kind != "name":
            raise UnsupportedPdf("a dictionary key is not a name")
        value_end = _value_end(tokens, position + 1)
        entries[key.text] = (position, position + 1, value_end)
        position = value_end
    if position >= len(tokens):
        raise UnsupportedPdf("a dictionary is never closed")
    return entries


def _rewrite_references(fragment, mapping):
    """`fragment` with each reference found in `mapping` replaced by "<new number> 0 R"."""
    tokens, _stop = _tokenize(fragment)
    pieces = []
    last = 0
    index = 0
    while index < len(tokens):
        if _is_reference(tokens, index):
            key = (int(tokens[index].text), int(tokens[index + 1].text))
            if key in mapping:
                pieces.append(fragment[last : tokens[index].start])
                pieces.append(b"%d 0 R" % mapping[key])
                last = tokens[index + 2].stop
            index += 3
            continue
        index += 1
    pieces.append(fragment[last:])
    return b"".join(pieces)


# --- reading ---------------------------------------------------------------------------------


class _Object:
    __slots__ = ("number", "generation", "head", "tokens", "entries", "tail", "type")

    def __init__(self, number, generation, head, tokens, tail):
        self.number = number
        self.generation = generation
        self.head = head  # the bytes after "n g obj", up to "stream" or "endobj"
        self.tokens = tokens  # tokens of head; positions count from the start of head
        self.tail = tail  # b"stream ... endstream" plus trailing whitespace, unchanged; or b""
        self.entries = _dictionary(tokens) if tokens else None
        self.type = self.value_of(b"/Type")

    def value_bytes(self, key):
        """The unparsed bytes of the outer dictionary's value for `key`, or None."""
        if not self.entries or key not in self.entries:
            return None
        _key, first, stop = self.entries[key]
        return self.head[self.tokens[first].start : self.tokens[stop - 1].stop]

    def value_of(self, key):
        raw = self.value_bytes(key)
        return raw.strip() if raw is not None else None

    def reference(self, key):
        """(number, generation) if the value for `key` is a reference; otherwise None."""
        if not self.entries or key not in self.entries:
            return None
        _key, first, stop = self.entries[key]
        if stop - first == 3 and _is_reference(self.tokens, first):
            return int(self.tokens[first].text), int(self.tokens[first + 1].text)
        return None


class _PdfFile:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as handle:
            self.data = handle.read()
        self.version = self._read_version()
        self.xref_offset = self._read_startxref()
        self.entries = self._read_xref_table()
        self.objects = {}
        for number in sorted(self.entries):
            offset, generation = self.entries[number]
            self.objects[number] = self._read_object(number, generation, offset)

    def _fail(self, reason):
        raise UnsupportedPdf("%s: %s" % (os.path.basename(self.path), reason))

    def _read_version(self):
        match = _VERSION.search(self.data, 0, 1024)
        if not match:
            return _MIN_VERSION
        return int(match.group(1)), int(match.group(2))

    def _read_startxref(self):
        data = self.data
        index = data.rfind(b"startxref", max(0, len(data) - _TAIL_WINDOW))
        match = _STARTXREF.match(data, index) if index >= 0 else None
        if not match:
            self._fail("the file does not end with 'startxref <offset> %EOF'")
        offset = int(match.group(1))
        if offset >= len(data):
            self._fail("startxref points past the end of the file")
        return offset

    def _read_xref_table(self):
        data = self.data
        position = _skip_whitespace(data, self.xref_offset, len(data))
        if not data.startswith(b"xref", position):
            self._fail("startxref leads to something other than an 'xref' table "
                       "(cross-reference streams cannot be merged)")
        position += 4
        entries = {}
        while True:
            position = _skip_whitespace(data, position, len(data))
            if data.startswith(b"trailer", position):
                break
            header = _SUBSECTION.match(data, position)
            if not header:
                self._fail("the cross-reference table cannot be read")
            first, count = int(header.group(1)), int(header.group(2))
            position = header.end()
            for number in range(first, first + count):
                entry = _XREF_ENTRY.match(data, position)
                if not entry:
                    self._fail("the cross-reference row of object %d cannot be read" % number)
                position = entry.end()
                if entry.group(3) == b"n" and number > 0:
                    entries[number] = (int(entry.group(1)), int(entry.group(2)))
        self._check_trailer(position + len(b"trailer"))
        return entries

    def _check_trailer(self, position):
        tokens, _stop = _tokenize(self.data, position, stop_words=(b"startxref",))
        entries = _dictionary(tokens)
        if entries is None:
            self._fail("the trailer has no dictionary")
        if b"/Prev" in entries:
            self._fail("the file was saved incrementally (/Prev in the trailer)")
        if b"/XRefStm" in entries:
            self._fail("the file also uses a cross-reference stream (/XRefStm)")
        if b"/Encrypt" in entries:
            self._fail("the file is encrypted")

    def _read_object(self, number, generation, offset):
        data = self.data
        header = _OBJ_HEADER.match(data, offset)
        if (
            not header
            or int(header.group(1)) != number
            or int(header.group(2)) != generation
        ):
            self._fail("object %d %d is not where the cross-reference table says"
                       % (number, generation))
        body = header.end()
        tokens, stop = _tokenize(data, body, stop_words=(b"stream", b"endobj"))
        if stop is None:
            self._fail("object %d is missing its endobj" % number)
        head = data[body : stop.start]
        local = [
            _Token(token.kind, token.start - body, token.stop - body, token.text)
            for token in tokens
        ]
        tail = b""
        if stop.text == b"stream":
            tail = self._stream_tail(number, generation, local, stop)
        return _Object(number, generation, head, local, tail)

    def _stream_tail(self, number, generation, tokens, keyword):
        data = self.data
        start = keyword.stop
        if data.startswith(b"\r\n", start):
            start += 2
        elif data[start : start + 1] in (b"\n", b"\r"):
            start += 1
        end_of_data = None
        length = self._stream_length(tokens)
        if length is not None:
            match = _ENDSTREAM.match(data, start + length)
            if match:
                end_of_data = match.end()
        if end_of_data is None:
            found = data.find(b"endstream", start)
            if found < 0:
                self._fail("the stream of object %d is missing its endstream" % number)
            end_of_data = found + len(b"endstream")
        closing = _ENDOBJ.match(data, end_of_data)
        if not closing:
            self._fail("object %d %d has no endobj after its stream" % (number, generation))
        return data[keyword.start : closing.end() - len(b"endobj")]

    def _stream_length(self, tokens):
        entries = _dictionary(tokens)
        if not entries or b"/Length" not in entries:
            return None
        _key, first, stop = entries[b"/Length"]
        if stop - first == 1 and tokens[first].kind == "int":
            return int(tokens[first].text)
        if stop - first == 3 and _is_reference(tokens, first):
            target = int(tokens[first].text)
            if target not in self.entries:
                return None
            offset, _generation = self.entries[target]
            header = _OBJ_HEADER.match(self.data, offset)
            if not header or int(header.group(1)) != target:
                return None
            value, stop_word = _tokenize(self.data, header.end(), stop_words=(b"endobj",))
            if stop_word is not None and len(value) == 1 and value[0].kind == "int":
                return int(value[0].text)
        return None


# --- writing ---------------------------------------------------------------------------------


def _inherited(pdf, page, key):
    """The unparsed value of inheritable `key` from the nearest page-tree ancestor, or None."""
    seen = set()
    reference = page.reference(b"/Parent")
    while reference is not None and reference[0] not in seen:
        seen.add(reference[0])
        node = pdf.objects.get(reference[0])
        if node is None or node.type != b"/Pages":
            return None
        raw = node.value_bytes(key)
        if raw is not None:
            return raw
        reference = node.reference(b"/Parent")
    return None


def _page_head(pdf, page, mapping):
    """The page dictionary pointed at /Parent 2 0 R, inherited values copied in, renumbered."""
    head = page.head
    if page.entries is None:
        raise UnsupportedPdf("%s: page object %d has no dictionary"
                             % (os.path.basename(pdf.path), page.number))
    additions = [b"/Parent 2 0 R"]
    for key in _INHERITABLE:
        if key in page.entries:
            continue
        raw = _inherited(pdf, page, key)
        if raw is not None:
            additions.append(key + b" " + _rewrite_references(raw, mapping))
        elif key == b"/MediaBox":
            raise UnsupportedPdf("%s: page object %d gives no /MediaBox"
                                 % (os.path.basename(pdf.path), page.number))
    if b"/Parent" in page.entries:
        key_index, _first, stop = page.entries[b"/Parent"]
        head = head[: page.tokens[key_index].start] + head[page.tokens[stop - 1].stop :]
    head = _rewrite_references(head, mapping)
    opening = head.index(b"<<") + 2
    return head[:opening] + b" " + b" ".join(additions) + head[opening:]


def _object_bytes(number, head, tail):
    if not head[:1] or head[:1] not in _WHITESPACE:
        head = b"\n" + head
    body = head + tail
    if body[-1:] not in _WHITESPACE:
        body += b"\n"
    return b"%d 0 obj" % number + body + b"endobj\n"


def _xref_table(size, offsets):
    free = [number for number in range(1, size) if number not in offsets]
    rows = [b"xref\n0 %d\n" % size]
    rows.append(b"%010d 65535 f\r\n" % (free[0] if free else 0))
    following = dict(zip(free, free[1:] + [0]))
    for number in range(1, size):
        if number in offsets:
            rows.append(b"%010d 00000 n\r\n" % offsets[number])
        else:
            rows.append(b"%010d 00000 f\r\n" % following[number])
    return b"".join(rows)


def _build(files):
    next_number = 3
    kids = []
    bodies = []
    for pdf in files:
        mapping = {}
        for number in sorted(pdf.objects):
            obj = pdf.objects[number]
            mapping[(number, obj.generation)] = next_number
            next_number += 1
        for number in sorted(pdf.objects):
            obj = pdf.objects[number]
            new_number = mapping[(number, obj.generation)]
            if obj.type in (b"/Catalog", b"/Pages"):
                continue
            if obj.type == b"/Page":
                head = _page_head(pdf, obj, mapping)
                kids.append(new_number)
            else:
                head = _rewrite_references(obj.head, mapping)
            bodies.append((new_number, head, obj.tail))
    if not kids:
        raise UnsupportedPdf("the input files contain no pages")

    version = max([_MIN_VERSION] + [pdf.version for pdf in files])
    out = bytearray(b"%%PDF-%d.%d\n%%\xe2\xe3\xcf\xd3\n" % version)
    offsets = {}

    def emit(number, head, tail=b""):
        offsets[number] = len(out)
        out.extend(_object_bytes(number, head, tail))

    emit(1, b"\n<< /Type /Catalog /Pages 2 0 R >>\n")
    kid_refs = b" ".join(b"%d 0 R" % number for number in kids)
    emit(2, b"\n<< /Type /Pages /Kids [ %s ] /Count %d >>\n" % (kid_refs, len(kids)))
    for number, head, tail in bodies:
        emit(number, head, tail)

    xref_offset = len(out)
    out.extend(_xref_table(next_number, offsets))
    out.extend(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
               % (next_number, xref_offset))
    return bytes(out), len(kids)


def merge(inputs, output):
    """Write the pages of `inputs`, in order, into one PDF at `output`; returns the page count.

    UnsupportedPdf is raised for any input this module cannot read, and no file is written.
    """
    files = [_PdfFile(os.fspath(path)) for path in inputs]
    data, page_count = _build(files)
    output = os.fspath(output)
    partial = output + ".part"
    try:
        with open(partial, "wb") as handle:
            handle.write(data)
        os.replace(partial, output)
    finally:
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
    return page_count
