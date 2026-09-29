#!/usr/bin/env python3
"""Validate EPUB metadata and rename without overwriting another file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


def tokens(value):
    return set(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))


def component(value, limit):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = value.encode("utf-8")[:limit].decode("utf-8", errors="ignore").strip(" .")
    if not value:
        raise ValueError("Empty filename component")
    return value


def finish(path, title, author, language):
    if path.is_symlink():
        raise ValueError("Expected a regular EPUB, not a symlink")
    path = path.resolve(strict=True)
    if not tokens(title) or not tokens(author) or not language:
        raise ValueError("Expected title, author and language are required")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > 512 * 1024 * 1024:
            raise ValueError("EPUB expanded size exceeds validation limit")
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        if archive.read("mimetype").strip() != b"application/epub+zip":
            raise ValueError("Not an EPUB file")
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        if rootfile is None:
            raise ValueError("Missing package document")
        package = ET.fromstring(archive.read(rootfile.attrib["full-path"]))
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        def values(key):
            return [x.text or "" for x in package.findall(f".//dc:{key}", ns)]
        titles, creators, languages = values("title"), values("creator"), values("language")
        if not any(tokens(title) <= tokens(x) for x in titles):
            raise ValueError("Title metadata does not match the selected book")
        if not tokens(author) <= tokens(" ".join(creators)):
            raise ValueError("Author metadata does not match the selected author")
        requested_language = language.casefold().split("-")[0]
        if not any(x.casefold().split("-")[0] == requested_language for x in languages):
            raise ValueError("Language metadata does not match")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    target = path.with_name(f"{component(title, 150)} ({component(author, 65)}).epub")
    if target != path:
        # Atomic no-clobber creation; source and destination share a directory.
        os.link(path, target)
        path.unlink()
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("Content changed unexpectedly")
    return {"path": str(target), "bytes": target.stat().st_size, "sha256": digest,
            "titles": titles, "creators": creators, "languages": languages, "validated": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    try:
        print(json.dumps(finish(args.path, args.title, args.author, args.language), ensure_ascii=False))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        parser.exit(1, f"Validation or rename failed: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
