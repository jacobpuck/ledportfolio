#!/usr/bin/env python3
"""Rewrite local-root links so the archive works as a GitHub Pages project site."""

from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path("static-site")
LOCAL_PATHS = (
    "assets/",
    "about/index.html",
    "bv-case-study/index.html",
    "citrix-case-study/index.html",
    "contact/index.html",
    "home/index.html",
    "index.html",
    "work/index.html",
)


def relative_url(source: Path, target: str) -> str:
    result = os.path.relpath(ROOT / target, start=source.parent).replace(os.sep, "/")
    return result + "/" if target.endswith("/") else result


def rewrite(source: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="surrogateescape")
    for target in LOCAL_PATHS:
        relative = relative_url(source, target)
        text = text.replace(f'"/{target}', f'"{relative}')
        text = text.replace(f"'/{target}", f"'{relative}")
        text = text.replace(f"(/{target}", f"({relative}")
        # ``srcset`` values contain several comma-separated URLs, so only the
        # first is preceded by a quote.  Rewrite any remaining local-root URL
        # too, while leaving absolute URLs such as https://… untouched.  The
        # assets case also normalizes a prior relative path, keeping this tool
        # safe to run repeatedly.
        if target == "assets/":
            pattern = r"(?<![A-Za-z0-9:])(?:\.\.)*/assets/"
        else:
            pattern = rf"(?<![A-Za-z0-9:.])/{re.escape(target)}"
        text = re.sub(pattern, relative, text)
    source.write_text(text, encoding="utf-8", errors="surrogateescape")


def main() -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".mjs"}:
            rewrite(path)


if __name__ == "__main__":
    main()
