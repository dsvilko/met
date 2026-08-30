#!/usr/bin/env python3
"""
link_meteorites.py

Reads a tab-separated file of meteorite names + links (lnks.tab) and, for
each entry, finds the matching meteorite folder(s) under a photo collection
root and writes a links.html file into each one containing those links.

Usage:
    python3 link_meteorites.py [--root PHOTOS_ROOT] [--lnks LNKS_TAB] [--dry-run]

Defaults:
    --root   .          (current directory; point this at your "Photos" folder,
                          or its parent - it is scanned recursively either way)
    --lnks   lnks.tab

What it does:
    1. Walks --root recursively and treats *every* directory as a candidate
       "meteorite folder" (this correctly handles cases where a meteorite has
       its own sub-folders for extra fragments/specimens).
    2. For each candidate folder, derives a "clean name" from its directory
       name by stripping a leading catalogue number (e.g. "1400. Elbogen" ->
       "Elbogen") and cutting off the first classification/weight suffix
       (e.g. "Elbogen (iron, IID) - micro" -> "Elbogen").
    3. For each line in lnks.tab, derives a comparable name (stripping a
       trailing parenthetical qualifier like "(paired)" or "(p)"), and looks
       for folders whose clean name matches, ignoring case, accents, and
       hyphen/space differences.
    4. If no exact match is found, it also tries a conservative fuzzy match
       (handles small typos like "Bechar 006" vs "Bachar 006" or "d'Orbigny"
       vs "d'Orbigney"). To stay safe with catalogue numbers, fuzzy matching
       only ever compares names whose digit sequences are identical (e.g.
       both contain "006") -- so "NWA 12345" can never be fuzzy-matched to
       "NWA 12354", since those are different meteorites, but "Bechar 006"
       can still be matched to "Bachar 006".
    5. Every folder that matched one or more lnks.tab rows gets a links.html
       file (overwritten each run) listing the (deduplicated) links.
    6. Prints a report of exact matches, fuzzy matches, and rows that could
       not be matched to any folder, so those can be checked/fixed by hand.
"""
import argparse
import os
import re
import sys
import unicodedata
import difflib
from html import escape


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def norm(s: str, loose: bool = False) -> str:
    s = strip_accents(s).lower().replace("'", "")
    if loose:
        s = s.replace('-', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def digits_of(s: str):
    return re.findall(r'\d+', s)


def clean_folder_name(basename: str) -> str:
    """Strip a leading catalogue number ("1400. ") and cut at the first
    classification/weight suffix introduced by " (", " - " or ",")."""
    b = re.sub(r'^\d+\.\s*', '', basename)
    idxs = [b.find(p) for p in (' (', ' - ', ',') if b.find(p) != -1]
    name = b[:min(idxs)] if idxs else b
    return name.strip()


def clean_lnks_name(name: str) -> str:
    """Strip a trailing parenthetical qualifier, e.g. "NWA 011 (paired)" ->
    "NWA 011", "Travis County (a)" -> "Travis County"."""
    name = name.strip()
    m = re.match(r'^(.*?)\s*\([^)]*\)\s*$', name)
    return m.group(1).strip() if m else name


FUZZY_CUTOFF = 0.82
MIN_FUZZY_LEN = 6


def build_folder_index(root):
    """Return a list of dicts describing every directory under root."""
    folders = []
    for dirpath, dirnames, filenames in os.walk(root):
        basename = os.path.basename(dirpath.rstrip(os.sep))
        if not basename:
            continue
        cname = clean_folder_name(basename)
        n = norm(cname)
        if not n:
            continue
        folders.append({
            'path': dirpath,
            'basename': basename,
            'clean': cname,
            'n': n,
            'nl': norm(cname, loose=True),
            'digits': digits_of(n),
        })
    return folders


def find_matches(name, folders):
    """Return (matched_folder_dicts, tag) where tag is EXACT / FUZZY / NONE."""
    base = clean_lnks_name(name)
    n, nl = norm(base), norm(base, loose=True)
    nf, nlf = norm(name), norm(name, loose=True)

    matches = [fo for fo in folders if fo['n'] in (n, nf) or fo['nl'] in (nl, nlf)]
    if matches:
        return matches, 'EXACT'

    if len(n) >= MIN_FUZZY_LEN:
        my_digits = digits_of(n)
        pool = [fo for fo in folders if fo['digits'] == my_digits]
        pool_names = sorted({fo['n'] for fo in pool})
        close = difflib.get_close_matches(n, pool_names, n=1, cutoff=FUZZY_CUTOFF)
        if close:
            return [fo for fo in pool if fo['n'] == close[0]], 'FUZZY'

    return [], 'NONE'


def parse_lnks(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for raw in f:
            raw = raw.rstrip('\n')
            if not raw.strip():
                continue
            parts = raw.split('\t')
            name = parts[0].strip()
            links = [p.strip() for p in parts[1:] if p.strip()]
            rows.append((name, links))
    return rows


def write_links_html(folder_path, name_to_links, dry_run=False):
    """name_to_links: dict of {meteorite_name: [link_html, ...]} that map to
    this folder (usually just one name, but could be more than one in a
    genuine collision)."""
    lines = [ ]
		#lines = [
    #    '<!DOCTYPE html>',
    #    '<html><head><meta charset="utf-8"><title>Links</title></head><body>',
    #]
    for name, links in name_to_links.items():
        #lines.append(f'<h3>{escape(name)}</h3>')
        #lines.append('<ul>')
        for link in links:
            lines.append(f'{link} ')
        #lines.append('</ul>')
    #lines.append('</body></html>')
    content = '\n'.join(lines) + '\n'

    out_path = os.path.join(folder_path, 'links.html')
    if dry_run:
        print(f'  [dry-run] would write {out_path}')
    else:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='Root directory to scan for meteorite folders (default: current directory)')
    ap.add_argument('--lnks', default='lnks.tab', help='Path to the lnks.tab file (default: lnks.tab)')
    ap.add_argument('--dry-run', action='store_true', help="Don't write any files, just show what would happen")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.exit(f'Error: root directory not found: {args.root}')
    if not os.path.isfile(args.lnks):
        sys.exit(f'Error: lnks.tab not found: {args.lnks}')

    folders = build_folder_index(args.root)
    rows = parse_lnks(args.lnks)

    # folder_path -> {meteorite_name: [links]}
    folder_writes = {}
    exact_ct = fuzzy_ct = none_ct = 0
    fuzzy_report = []
    none_report = []

    for name, links in rows:
        if not links:
            continue
        matched, tag = find_matches(name, folders)
        if tag == 'EXACT':
            exact_ct += 1
        elif tag == 'FUZZY':
            fuzzy_ct += 1
            fuzzy_report.append((name, [m['path'] for m in matched]))
        else:
            none_ct += 1
            none_report.append(name)
            continue

        for fo in matched:
            d = folder_writes.setdefault(fo['path'], {})
            existing = d.setdefault(name, [])
            for link in links:
                if link not in existing:
                    existing.append(link)

    print(f'Scanned {len(folders)} folders under "{args.root}".')
    print(f'Processed {len(rows)} lnks.tab rows.')
    print(f'  exact matches : {exact_ct}')
    print(f'  fuzzy matches : {fuzzy_ct}')
    print(f'  no match      : {none_ct}')
    print()

    if fuzzy_report:
        print('Fuzzy matches (double-check these):')
        for name, paths in fuzzy_report:
            for p in paths:
                print(f'  {name!r:25s} -> {p}')
        print()

    if none_report:
        print('No matching folder found for:')
        for name in none_report:
            print(f'  {name!r}')
        print()

    print(f'Writing links.html into {len(folder_writes)} folder(s)...')
    for folder_path, name_to_links in folder_writes.items():
        write_links_html(folder_path, name_to_links, dry_run=args.dry_run)
    print('Done.')


if __name__ == '__main__':
    main()
