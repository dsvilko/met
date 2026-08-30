#!/usr/bin/env python3
"""
Populate meteorite folders with a "metbul.link" file containing the exact
Meteoritical Bulletin Database page for that meteorite.

Input file format:
    Photos/Achondrites/HED/Diogenite/NWA 14683 (diogenite-olivine) - thin section
    ...

The paths are treated as relative to --root (default: current directory).
Duplicate paths in met.list are processed only once.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_URL = "https://www.lpi.usra.edu/meteor/metbull.cfm"
USER_AGENT = "Mozilla/5.0 (compatible; metbul-link-helper/1.0)"


class LinkParser(HTMLParser):
    """Collect links whose href contains a MetBull meteorite code."""

    def __init__(self) -> None:
        super().__init__()
        self._href: Optional[str] = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href and re.search(r"metbull\.(?:cfm|php)\?[^\"']*code=\d+", href, re.I):
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = html.unescape("".join(self._text)).strip()
            self.links.append((text, self._href))
            self._href = None
            self._text = []


def normalize_name(s: str) -> str:
    """
    Turn a folder basename into a likely meteorite name.

    Examples:
      "NWA 14683 (diogenite-olivine) - thin section" -> "NWA 14683"
      "1749. Krasnojarsk (pallasite) - 70mg"           -> "Krasnojarsk"
      "Another fragment from Timur Kryachko"           -> "Another fragment from Timur Kryachko"
    """
    s = s.strip()

    # Remove the common " - description/weight" suffix.
    s = re.split(r"\s+-\s+", s, maxsplit=1)[0].strip()

    # Remove parenthesized classification/notes.
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()

    # Some folders in the list have a year/catalogue number before the name.
    s = re.sub(r"^\d{3,4}\.\s*", "", s)

    return re.sub(r"\s+", " ", s).strip()


def candidate_names(rel_path: str) -> list[str]:
    """
    Try the leaf folder first, then parent folders.

    This handles entries such as:
        .../Dhofar 007 (...)/Another fragment from Timur Kryachko
    where the meteorite is the parent folder, not the final child folder.
    """
    parts = [p for p in Path(rel_path).parts if p not in ("", ".")]
    # Work backwards, but ignore broad taxonomy/path roots unless they happen
    # to be exact database names (which is still safe because we require one
    # exact match).
    out: list[str] = []
    seen: set[str] = set()

    for part in reversed(parts):
        name = normalize_name(part)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        # Skip obvious non-meteorite path components.
        if name.lower() in {
            "photos", "achondrites", "chondrites", "stony irons",
            "special", "primitive", "evolved", "martian", "lunar",
            "hed", "r", "e", "oc", "irons", "palasites",
        }:
            continue
        out.append(name)

    return out


def fetch_exact(name: str, timeout: int = 30) -> Optional[str]:
    """Return the unique exact-match meteorite URL, or None."""
    params = urlencode({
        "sfor": "names",
        "stype": "exact",
        "sea": name,
    })
    url = f"{BASE_URL}?{params}"

    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        page = resp.read().decode(charset, errors="replace")

    parser = LinkParser()
    parser.feed(page)

    # Keep only links whose visible text is a meteorite name.  An exact search
    # should produce one row; requiring uniqueness prevents accidental matches.
    usable: list[tuple[str, str]] = []
    for text, href in parser.links:
        if not text:
            continue
        abs_url = urljoin(BASE_URL, href)
        usable.append((text, abs_url))

    # Deduplicate identical links.
    dedup: dict[str, str] = {}
    for text, href in usable:
        dedup[href] = text

    if len(dedup) != 1:
        return None

    return next(iter(dedup))


def read_paths(list_file: Path) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []

    with list_file.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Normalize separators so a list made on another OS is usable.
            line = line.replace("\\", "/")
            if line not in seen:
                seen.add(line)
                paths.append(line)

    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "list_file",
        type=Path,
        help="The met.list file containing relative folder paths.",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Directory relative to which paths in met.list are resolved (default: .).",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing metbul.link file.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Find and report matches but do not write files.",
    )
    ap.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between distinct database queries (default: 0.5).",
    )
    args = ap.parse_args()

    list_file = args.list_file
    if not list_file.exists():
        print(f"ERROR: list file not found: {list_file}", file=sys.stderr)
        return 2

    root = args.root.resolve()
    paths = read_paths(list_file)

    print(f"Read {len(paths)} unique paths from {list_file}")
    print(f"Root: {root}")
    if args.dry_run:
        print("DRY RUN: no files will be written")

    # Cache by candidate name: the input has many repeated paths/names.
    cache: dict[str, Optional[str]] = {}
    ok = skipped = notfound = errors = 0
    last_query_time = 0.0

    for i, rel in enumerate(paths, 1):
        folder = (root / Path(rel)).resolve()
        print(f"[{i}/{len(paths)}] {rel}")

        if not folder.is_dir():
            print("    SKIP: path is not a directory")
            skipped += 1
            continue

        outfile = folder / "metbul.link"
        if outfile.exists() and not args.overwrite:
            print("    SKIP: metbul.link already exists (use --overwrite)")
            skipped += 1
            continue

        url: Optional[str] = None
        chosen_name: Optional[str] = None

        for name in candidate_names(rel):
            if name not in cache:
                elapsed = time.monotonic() - last_query_time
                if elapsed < args.delay:
                    time.sleep(args.delay - elapsed)

                try:
                    cache[name] = fetch_exact(name)
                    last_query_time = time.monotonic()
                except (HTTPError, URLError, TimeoutError, OSError) as e:
                    print(f"    ERROR querying {name!r}: {e}")
                    cache[name] = None
                    errors += 1
                    break

            if cache[name]:
                url = cache[name]
                chosen_name = name
                break

        if not url:
            print(
                "    NOT FOUND: no unique exact MetBull match for "
                + " / ".join(candidate_names(rel))
            )
            notfound += 1
            continue

        print(f"    MATCH: {chosen_name} -> {url}")

        if not args.dry_run:
            try:
                outfile.write_text(url + "\n", encoding="utf-8")
            except OSError as e:
                print(f"    ERROR writing {outfile}: {e}")
                errors += 1
                continue

        ok += 1

    print()
    print(
        f"Done. matched={ok}, not_found={notfound}, "
        f"skipped={skipped}, errors={errors}, cached_queries={len(cache)}"
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
