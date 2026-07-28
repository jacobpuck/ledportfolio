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

# Squarespace paths that need an archive equivalent.  A Pages *project* site
# lives below /ledportfolio/, so these cannot stay site-root URLs.
ROUTE_ALIASES = {
    "/": "index.html",
    "/bv-case-study-1": "citrix-case-study/index.html",
}


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
        # first is preceded by a quote. Rewrite every local reference, whether
        # it starts at the archive root or is already a relative URL; this
        # keeps repeated runs from accumulating extra ``..`` segments.
        pattern = rf"(?<![A-Za-z0-9:])(?:\.\.)*/{re.escape(target)}"
        text = re.sub(pattern, relative, text)

    for original, target in ROUTE_ALIASES.items():
        relative = relative_url(source, target)
        text = text.replace(f'href="{original}"', f'href="{relative}"')
        # The carousel stores its destination in an HTML-escaped JSON payload
        # as well as on the visible anchor.
        text = text.replace(
            f'&quot;buttonLink&quot;: &quot;{original}&quot;',
            f'&quot;buttonLink&quot;: &quot;{relative}&quot;',
        )

    # This portfolio has no static shopping cart.  The cart control is hidden
    # in the copied Squarespace markup; keep it from pointing to a Pages 404.
    text = text.replace('href="/cart"', 'href="#page"')

    # Squarespace's carousel cards leave their <img> elements without a src
    # and depend on its application runtime to populate them.  That runtime
    # is not portable to a static Pages archive, so retain the exact local
    # asset by promoting data-src to src where needed.
    def add_image_src(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r"(?<![-\w])src\s*=", tag, flags=re.IGNORECASE):
            return tag
        data_src = re.search(r'\bdata-src\s*=\s*"([^"]+)"', tag, flags=re.IGNORECASE)
        if not data_src:
            return tag
        ending = "/>" if tag.endswith("/>") else ">"
        return tag[: -len(ending)] + f' src="{data_src.group(1)}"{ending}'

    text = re.sub(
        r'<img\b[^>]*\bdata-src\s*=\s*"[^"]+"[^>]*>',
        add_image_src,
        text,
        flags=re.IGNORECASE,
    )
    source.write_text(text, encoding="utf-8", errors="surrogateescape")


def main() -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".css"}:
            rewrite(path)


if __name__ == "__main__":
    main()
