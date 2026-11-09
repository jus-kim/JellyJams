# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Fetch pinned CAD reference data into scratch; never execute downloaded code."""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "tests/fixtures/cad_manifest.json"
CACHE = REPO / "scratch/cad_fixtures"
MAX_DOWNLOAD = 32 * 1024 * 1024


def safe_name(value):
    """Only flat, portable cache names; ZIP members are read, never extracted."""
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", value):
        raise ValueError("Unsafe fixture filename: %r" % value)
    if value in (".", ".."):
        raise ValueError("Unsafe fixture filename")
    return value


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not data.get("sources") or not data.get("cases"):
        raise ValueError("Incomplete CAD manifest or unsupported schema")
    names, ids = set(), set()
    for source in data["sources"]:
        if not source["url"].startswith("https://") or not source.get("license"):
            raise ValueError("Fixture needs HTTPS provenance and usage terms")
        for entry in (source, *source["files"]):
            if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
                raise ValueError("Fixture needs a SHA-256 pin")
            if type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= MAX_DOWNLOAD:
                raise ValueError("Invalid fixture byte count")
        for asset in source["files"]:
            name = safe_name(asset["path"])
            if name in names:
                raise ValueError("Duplicate fixture filename: " + name)
            names.add(name)
            member = asset.get("member")
            if member and (PurePosixPath(member).is_absolute() or ".." in PurePosixPath(member).parts):
                raise ValueError("Unsafe ZIP member")
    for case in data["cases"]:
        name = safe_name(case["id"])
        if name in ids or case["file"] not in names:
            raise ValueError("Duplicate case or missing asset: " + name)
        ids.add(name)
        if type(case["solids"]) is not int or case["solids"] < 1 or not case.get("reference"):
            raise ValueError("Missing solid count or dimensional reference")
        for key, length in (("bbox_mm", 6), ("center_mm", 3)):
            if len(case[key]) != length or not all(math.isfinite(v) for v in case[key]):
                raise ValueError("Invalid " + key)
        if any(case["bbox_mm"][i] >= case["bbox_mm"][i + 3] for i in range(3)):
            raise ValueError("Empty fixture bounds")
        for key in ("volume_mm3", "area_mm2"):
            if not math.isfinite(case[key]) or case[key] <= 0:
                raise ValueError("Invalid " + key)
    return data


def verify_bytes(payload, entry):
    if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError("CAD fixture checksum/size mismatch: " + entry.get("path", entry.get("url", "data")))


def verify_cache(cache=CACHE, manifest=None):
    data = manifest if manifest is not None else load_manifest()
    for source in data["sources"]:
        for asset in source["files"]:
            path = Path(cache) / safe_name(asset["path"])
            if not path.is_file():
                raise ValueError("Missing fixture %s; run python tests/cad_fixtures.py fetch" % path)
            verify_bytes(path.read_bytes(), asset)
    return data


def fetch(cache=CACHE, manifest=None, opener=urllib.request.urlopen):
    data = manifest if manifest is not None else load_manifest()
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for source in data["sources"]:
        try:
            verify_cache(cache, {"sources": [source]})
            continue
        except ValueError:
            pass
        request = urllib.request.Request(source["url"], headers={"User-Agent": "JellyJams-CAD-tests/1"})
        with opener(request, timeout=60) as response:
            payload = response.read(MAX_DOWNLOAD + 1)
        verify_bytes(payload, source)
        archive = zipfile.ZipFile(io.BytesIO(payload)) if source.get("archive") == "zip" else None
        staged = []
        try:
            for asset in source["files"]:
                name = safe_name(asset["path"])
                if archive:
                    info = archive.getinfo(asset["member"])
                    if info.file_size != asset["bytes"]:
                        raise ValueError("ZIP member size mismatch: " + name)
                    content = archive.read(info)
                else:
                    content = payload
                verify_bytes(content, asset)
                staged.append((name, content))
            # Publish only after every member passes. An interrupted write cannot
            # become a valid cached fixture, and old reference files stay intact.
            for name, content in staged:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(content)
                    temporary.replace(cache / name)
                finally:
                    if temporary is not None and temporary.exists():
                        temporary.unlink()
        finally:
            if archive:
                archive.close()
    return verify_cache(cache, data)


def close_number(actual, expected, absolute=1e-6, relative=1e-7):
    """Reject NaN/inf and use scale-aware millimetre tolerances."""
    return (math.isfinite(actual) and math.isfinite(expected)
            and abs(actual - expected) <= max(absolute, relative * abs(expected)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify", "catalog"))
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    data = load_manifest()
    if args.action == "fetch":
        fetch(args.cache, data)
    elif args.action == "verify":
        verify_cache(args.cache, data)
    else:
        for case in data["cases"]:
            print("%-24s %s" % (case["id"], case["description"]))
    print("%d pinned CAD cases; cache: %s" % (len(data["cases"]), args.cache))


if __name__ == "__main__":
    main()
