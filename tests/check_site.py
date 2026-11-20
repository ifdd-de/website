#!/usr/bin/env python3
"""Static checks of the ifdd.de website. Standard library only.

Usage: python tests/check_site.py [REPO_DIR]

Checks every HTML file in site/ and legal.example/:

- it parses, declares <html lang>, <meta charset> and a <title>;
- pages below site/de/ are German, all other pages English (404.html too);
- no <script>, <iframe>, <object>, <embed> or <form>, no inline event
  handlers, no style attributes;
- every resource (stylesheet, icon, image) is local: nothing is loaded from
  another host;
- every local link and resource resolves to a file, with the legal pages
  /impressum/ and /datenschutz/ taken from legal.example/; fragments must
  exist as an id in the target;
- English and German pages exist with the same paths, and each links to its
  counterpart in the other language;
- the stylesheets load nothing from another host.

Exit code 0 if everything passes, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "form"}
# <link rel=...> values that load something into the page.
RESOURCE_RELS = {"stylesheet", "icon", "apple-touch-icon", "manifest", "preload", "prefetch", "modulepreload"}
# Served by nginx from legal/; checked against legal.example/.
LEGAL = {"/impressum/": "impressum.html", "/datenschutz/": "datenschutz.html"}
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)|@import\s+['"]([^'"]+)['"]""")


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.charset = False
        self.title = False
        self.ids: set[str] = set()
        self.links: list[tuple[str, str, str]] = []  # (kind, url, hreflang)
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "meta" and "charset" in a:
            self.charset = True
        if tag == "title":
            self.title = True
        if "id" in a:
            self.ids.add(a["id"])
        if tag in FORBIDDEN_TAGS:
            self.errors.append(f"forbidden element <{tag}>")
        for name in a:
            if name.startswith("on"):
                self.errors.append(f"inline event handler {name}= on <{tag}>")
            if name == "style":
                self.errors.append(f"style attribute on <{tag}>")
        if tag == "a" and "href" in a:
            self.links.append(("link", a["href"], a.get("hreflang", "")))
        elif tag == "link" and "href" in a:
            rels = set(a.get("rel", "").lower().split())
            kind = "resource" if rels & RESOURCE_RELS else "meta"
            self.links.append((kind, a["href"], a.get("hreflang", "")))
        elif tag in {"img", "audio", "video", "track"} and "src" in a:
            self.links.append(("resource", a["src"], ""))
        elif tag == "source" and "srcset" in a:
            for part in a["srcset"].split(","):
                if part.strip():
                    self.links.append(("resource", part.strip().split()[0], ""))


def is_remote(url: str) -> bool:
    parts = urlsplit(url)
    return bool(parts.scheme) or url.startswith("//")


class Site:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.site = repo / "site"
        self.legal = repo / "legal.example"
        self.errors: list[str] = []
        self.pages: dict[Path, Page] = {}

    def err(self, where: Path, msg: str) -> None:
        self.errors.append(f"{where.relative_to(self.repo)}: {msg}")

    def url_path(self, file: Path) -> str:
        """URL path under which nginx serves a file."""
        if file.parent == self.legal:
            return "/" + file.stem + "/"
        rel = file.relative_to(self.site).as_posix()
        if rel.endswith("index.html"):
            return "/" + rel[: -len("index.html")]
        return "/" + rel

    def resolve(self, base_url: str, url: str) -> tuple[Path | None, str]:
        """Map a local URL to the file nginx would serve, plus its fragment."""
        parts = urlsplit(url)
        path = parts.path
        if not path:
            path = base_url
        elif not path.startswith("/"):
            base_dir = base_url if base_url.endswith("/") else base_url.rsplit("/", 1)[0] + "/"
            path = base_dir + path
        # normalise . and ..
        stack: list[str] = []
        for seg in path.split("/")[1:]:
            if seg == "..":
                if not stack:
                    return None, parts.fragment
                stack.pop()
            elif seg != ".":
                stack.append(seg)
        norm = "/" + "/".join(stack)
        if norm in LEGAL:
            target = self.legal / LEGAL[norm]
            return (target if target.is_file() else None), parts.fragment
        target = self.site / norm.lstrip("/")
        if norm.endswith("/"):
            target = target / "index.html"
        return (target if target.is_file() else None), parts.fragment

    def load(self) -> None:
        files = sorted(self.site.rglob("*.html")) + sorted(self.legal.glob("*.html"))
        if not files:
            self.errors.append("no HTML files found")
        for f in files:
            p = Page()
            try:
                p.feed(f.read_text(encoding="utf-8"))
                p.close()
            except Exception as exc:  # noqa: BLE001 - report any parser failure
                self.err(f, f"does not parse: {exc}")
                continue
            self.pages[f] = p

    def check_pages(self) -> None:
        for f, p in self.pages.items():
            for e in p.errors:
                self.err(f, e)
            german = f.parent == self.legal or f.is_relative_to(self.site / "de")
            want = "de" if german else "en"
            if p.lang != want:
                self.err(f, f'<html lang="{p.lang}">, expected "{want}"')
            if not p.charset:
                self.err(f, "no <meta charset>")
            if not p.title:
                self.err(f, "no <title>")
            base = self.url_path(f)
            for kind, url, _ in p.links:
                if url.startswith("mailto:"):
                    continue
                if is_remote(url):
                    if kind == "resource":
                        self.err(f, f"external resource {url}")
                    continue
                target, frag = self.resolve(base, url)
                if target is None:
                    self.err(f, f"broken link {url}")
                    continue
                if frag:
                    tp = self.pages.get(target)
                    if tp is None or frag not in tp.ids:
                        self.err(f, f"missing anchor #{frag} in {url}")

    def check_languages(self) -> None:
        de_root = self.site / "de"
        en = {f.relative_to(self.site) for f in self.site.rglob("index.html") if not f.is_relative_to(de_root)}
        de = {f.relative_to(de_root) for f in de_root.rglob("index.html")} if de_root.is_dir() else set()
        for rel in sorted(en - de):
            self.errors.append(f"site/{rel.as_posix()}: no German counterpart site/de/{rel.as_posix()}")
        for rel in sorted(de - en):
            self.errors.append(f"site/de/{rel.as_posix()}: no English counterpart site/{rel.as_posix()}")
        for rel in sorted(en & de):
            pairs = ((self.site / rel, de_root / rel, "de"), (de_root / rel, self.site / rel, "en"))
            for src, dst, lang in pairs:
                p = self.pages.get(src)
                if p is None:
                    continue
                base = self.url_path(src)
                if not any(
                    kind == "link" and hl == lang and not is_remote(url) and self.resolve(base, url)[0] == dst
                    for kind, url, hl in p.links
                ):
                    self.err(src, f'no link with hreflang="{lang}" to {dst.relative_to(self.repo)}')

    def check_css(self) -> None:
        for css in sorted(self.site.rglob("*.css")):
            for m in CSS_URL.finditer(css.read_text(encoding="utf-8")):
                url = m.group(1) or m.group(2)
                if is_remote(url) and not url.startswith("data:"):
                    self.err(css, f"external resource {url}")

    def run(self) -> int:
        if not self.site.is_dir():
            print(f"site/ not found in {self.repo}", file=sys.stderr)
            return 1
        self.load()
        self.check_pages()
        self.check_languages()
        self.check_css()
        for e in self.errors:
            print(e, file=sys.stderr)
        print(f"{len(self.pages)} pages checked, {len(self.errors)} problem(s)")
        return 1 if self.errors else 0


def main(argv: list[str]) -> int:
    repo = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    return Site(repo.resolve()).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
