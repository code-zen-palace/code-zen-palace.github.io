#!/usr/bin/env python3
"""Check that every link and image on the published site resolves.

    python3 tools/check_links.py              internal links, files and #anchors
    python3 tools/check_links.py --external   also ask each outside site (HEAD/GET)

Python 3 standard library only. Reads the built HTML in the repo root (not src/)
plus site.webmanifest, the way GitHub Pages serves them: /dir/ is
dir/index.html, and links to https://primekampllc.com/... are checked as files.
"""

import json
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://primekampllc.com"
SKIP_DIRS = {".git", "src", "tools"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key):
                self.links.append(a[key])
        if tag == "meta" and a.get("property", a.get("name", "")) in ("og:image", "twitter:image", "og:url"):
            self.links.append(a.get("content", ""))


def pages():
    for path in sorted(ROOT.rglob("*.html")):
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            yield path


def url_of(path):
    rel = path.relative_to(ROOT).as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return "/" + rel


def target(url_path):
    """The file GitHub Pages would serve for a site path, or None."""
    rel = url_path.lstrip("/")
    candidates = [ROOT / rel] if rel and not rel.endswith("/") else []
    candidates.append(ROOT / rel / "index.html")
    for c in candidates:
        if c.is_file():
            return c
    return None


def main(argv):
    parsed = {}
    for path in pages():
        p = Page()
        p.feed(path.read_text(encoding="utf-8"))
        parsed[path] = p

    problems = []
    external = set()
    checked = 0
    sources = [(path, url_of(path), p.links) for path, p in parsed.items()]
    manifest = ROOT / "site.webmanifest"
    if manifest.exists():
        icons = [i["src"] for i in json.loads(manifest.read_text())["icons"]]
        sources.append((manifest, "/site.webmanifest", icons))

    for path, base, links in sources:
        for link in links:
            if link.startswith(("mailto:", "tel:")):
                continue
            full = urljoin(SITE + base, link)
            parts = urlsplit(full)
            if f"{parts.scheme}://{parts.netloc}" != SITE:
                external.add(full)
                continue
            checked += 1
            file = target(parts.path)
            if file is None:
                problems.append(f"{path.relative_to(ROOT)}: {link} -> missing")
                continue
            if parts.fragment and file in parsed and parts.fragment not in parsed[file].ids:
                problems.append(f"{path.relative_to(ROOT)}: {link} -> no #{parts.fragment}")

    if "--external" in argv:
        for url in sorted(external):
            status = fetch_status(url)
            ok = isinstance(status, int) and status < 400
            print(f"{'ok  ' if ok else 'FAIL'} {status} {url}")
            if not ok:
                problems.append(f"external: {url} -> {status}")

    print(f"{len(parsed)} pages, {checked} internal links checked, {len(external)} external links")
    for problem in problems:
        print("BROKEN", problem)
    return 1 if problems else 0


def fetch_status(url):
    headers = {"User-Agent": "Mozilla/5.0 (link check for primekampllc.com)"}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if method == "GET":
                return error.code
        except Exception as error:  # network trouble: report it, don't crash
            if method == "GET":
                return type(error).__name__
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
