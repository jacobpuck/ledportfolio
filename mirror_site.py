#!/usr/bin/env python3
"""Create a local, self-contained archive of Lauren Puckett's public site.

Run from this repository root.  The script intentionally limits downloads to
Squarespace's rendering/CDN hosts and Adobe Typekit hosts referenced by the
public pages.  Third-party destination links remain links, rather than being
crawled.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ORIGIN = "https://www.laurenpuckettportfolio.com"
SITE_HOST = "www.laurenpuckettportfolio.com"
ASSET_HOSTS = {
    "assets.squarespace.com",
    "definitions.sqspcdn.com",
    "images.squarespace-cdn.com",
    "p.typekit.net",
    "static1.squarespace.com",
    "use.typekit.net",
}
OUTPUT = Path("static-site")
TIMEOUT = 45
MAX_ASSETS = 3000
USER_AGENT = "LaurenPortfolioPersonalArchive/1.0 (owner-authorized backup)"
URL_RE = re.compile(r"(?:(?:https?:)?//[^\s\"'<>`\\]+|/(?!/)[^\s\"'<>`\\]+)")
EXTERNAL_URL_RE = re.compile(
    r"(?:(?:https?:)?//(?:assets\.squarespace\.com|definitions\.sqspcdn\.com|"
    r"images\.squarespace-cdn\.com|p\.typekit\.net|static1\.squarespace\.com|"
    r"use\.typekit\.net)[^\s\"'<>`\\]+)",
    re.I,
)
EXT_RE = re.compile(r"\.(?:css|js|mjs|png|jpe?g|gif|webp|svg|ico|avif|pdf|woff2?|ttf|otf|mp4|webm|mp3|json)(?:$|[?#])", re.I)


def clean_url(value: str, base: str) -> str | None:
    value = value.split("&quot;", 1)[0].split("\\\"", 1)[0]
    value = value.replace("&amp;", "&").replace("\\/", "/").rstrip(".,;)")
    if value.startswith("//"):
        value = "https:" + value
    elif value.startswith("/"):
        value = urljoin(base, value)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


def asset_path(url: str) -> Path:
    parsed = urlsplit(url)
    decoded = unquote(parsed.path.lstrip("/")) or "index"
    safe_parts = [quote(part, safe="._-+=@() ") for part in decoded.split("/")]
    target = Path("assets") / parsed.netloc / Path(*safe_parts)
    if target.suffix == "" and not decoded.endswith("/"):
        target = target.with_suffix(".bin")
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode()).hexdigest()[:12]
        target = target.with_name(f"{target.stem}--q{digest}{target.suffix}")
    return target


def page_path(url: str) -> Path:
    path = unquote(urlsplit(url).path).strip("/")
    return Path("index.html") if not path else Path(path) / "index.html"


def local_ref(url: str, page_urls: set[str]) -> str | None:
    parsed = urlsplit(url)
    without_query = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if parsed.netloc == SITE_HOST and without_query in page_urls:
        return "/" + page_path(without_query).as_posix()
    if parsed.netloc in ASSET_HOSTS or (parsed.netloc == SITE_HOST and EXT_RE.search(url)):
        return "/" + asset_path(url).as_posix()
    return None


def request(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=TIMEOUT) as response:
        return response.read(), response.headers.get_content_type()


def rewrite(content: str, base: str, page_urls: set[str], external_only: bool = False) -> tuple[str, set[str]]:
    found: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        absolute = clean_url(raw, base)
        if not absolute:
            return raw
        parsed = urlsplit(absolute)
        is_page = parsed.netloc == SITE_HOST and urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")) in page_urls
        is_asset = (
            parsed.netloc in ASSET_HOSTS
            or (parsed.netloc == SITE_HOST and bool(EXT_RE.search(absolute)))
        )
        if is_page or is_asset:
            found.add(absolute)
            return local_ref(absolute, page_urls) or raw
        return raw

    matcher = EXTERNAL_URL_RE if external_only else URL_RE
    return matcher.sub(replace, content), found


def sitemap_pages() -> set[str]:
    xml, _ = request(f"{ORIGIN}/sitemap.xml")
    root = ET.fromstring(xml)
    pages = set()
    for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        loc = node.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc:
            url = clean_url(loc, ORIGIN)
            if url and urlsplit(url).netloc == SITE_HOST:
                pages.add(url)
    pages.add(ORIGIN + "/")
    return pages


def write_file(relative: Path, data: bytes) -> None:
    destination = OUTPUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    pages = sitemap_pages()
    queued = deque(sorted(pages))
    assets: set[str] = set()
    errors: list[dict[str, str]] = []
    page_results: list[dict[str, str]] = []
    while queued:
        url = queued.popleft()
        try:
            data, _ = request(url)
            text = data.decode("utf-8", errors="replace")
            rewritten, discovered = rewrite(text, url, pages)
            write_file(page_path(url), rewritten.encode("utf-8"))
            assets.update(
                item for item in discovered
                if urlsplit(item).netloc in ASSET_HOSTS
                or (urlsplit(item).netloc == SITE_HOST and EXT_RE.search(item))
            )
            page_results.append({"url": url, "file": page_path(url).as_posix()})
            print(f"page  {url}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append({"url": url, "error": str(exc)})
            print(f"ERROR page {url}: {exc}", file=sys.stderr)

    pending = deque(sorted(assets))
    downloaded: list[dict[str, str]] = []
    seen: set[str] = set()
    while pending and len(seen) < MAX_ASSETS:
        url = pending.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            data, content_type = request(url)
            relative = asset_path(url)
            if content_type in {"text/css", "application/javascript", "text/javascript"} or relative.suffix.lower() in {".css", ".js", ".mjs"}:
                text = data.decode("utf-8", errors="replace")
                rewritten, discovered = rewrite(text, url, pages, external_only=True)
                data = rewritten.encode("utf-8")
                for item in discovered:
                    if (urlsplit(item).netloc in ASSET_HOSTS or urlsplit(item).netloc == SITE_HOST) and item not in seen:
                        pending.append(item)
            write_file(relative, data)
            downloaded.append({"url": url, "file": relative.as_posix(), "bytes": str(len(data))})
            print(f"asset {url}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append({"url": url, "error": str(exc)})
            print(f"ERROR asset {url}: {exc}", file=sys.stderr)
        time.sleep(0.02)

    report = {
        "source": ORIGIN,
        "pages": page_results,
        "assets": downloaded,
        "errors": errors,
        "asset_limit_reached": len(seen) >= MAX_ASSETS and bool(pending),
    }
    (OUTPUT / "crawl-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUTPUT / "README.md").write_text(
        "# Lauren Puckett Portfolio — local archive\n\n"
        "This is a static snapshot of the public Squarespace site. Serve this folder "
        "from its parent directory with:\n\n"
        "```sh\npython3 -m http.server 8000 --directory static-site\n```\n\n"
        "Then visit `http://localhost:8000/`. `crawl-report.json` records every "
        "download and any resources that could not be retrieved.\n"
    )
    (OUTPUT / ".nojekyll").write_text("")
    print(json.dumps({"pages": len(page_results), "assets": len(downloaded), "errors": len(errors)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
