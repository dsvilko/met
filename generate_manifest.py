#!/usr/bin/env python3
"""
Generate manifest.json from the Photos/ directory tree.

Walks the Photos/ hierarchy, finds leaf meteorite folders (those containing
.jpg/.jpeg image files), reads any info.txt descriptions, and outputs a
manifest.json that the gallery webpage can consume.

Usage:
    python3 generate_manifest.py
    # produces manifest.json in the current directory
"""

import json
import os
import sys

PHOTOS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Photos")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}


def is_image(filename):
    """Check if a file is a JPEG image."""
    return os.path.splitext(filename.lower())[1] in IMAGE_EXTENSIONS


def walk_photos(root):
    """
    Walk the Photos/ tree and return a list of meteorite entries.

    Each entry is:
    {
        "name": "Gadamis 003 (Lunar ferroan anorthosite) - 81mg",
        "path": "Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 ...",
        "categories": ["Achondrites", "Lunar", "ferroan anorthosite"],
        "description": "contents of info.txt or empty string",
        "images": ["filename1.jpeg", "filename2.jpg"]
    }
    """
    meteorites = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Find image files in this directory
        images = sorted(f for f in filenames if is_image(f))

        if not images:
            continue

        # This is a leaf meteorite folder
        rel_path = os.path.relpath(dirpath, os.path.dirname(root))
        # Categories: everything between "Photos" and the meteorite folder name
        parts = rel_path.split(os.sep)
        # parts[0] = "Photos", parts[1:-1] = categories, parts[-1] = meteorite name
        categories = parts[1:-1] if len(parts) > 2 else []
        name = parts[-1] if len(parts) > 1 else parts[0]

        # Read info.txt if present
        description = ""
        info_path = os.path.join(dirpath, "info.txt")
        if os.path.isfile(info_path):
            try:
                with open(info_path, "r", encoding="utf-8", errors="replace") as f:
                    description = f.read().strip()
            except Exception as e:
                print(f"Warning: Could not read {info_path}: {e}", file=sys.stderr)

        meteorites.append({
            "name": name,
            "path": rel_path,
            "categories": categories,
            "description": description,
            "images": images,
        })

    return meteorites


def build_tree(meteorites):
    """
    Build a nested category tree from the flat list of meteorites.

    Returns:
    {
        "children": {
            "Achondrites": {
                "children": {
                    "Lunar": { ... }
                },
                "meteorites": []
            }
        },
        "meteorites": []
    }
    """
    tree = {"children": {}, "meteorites": []}

    for met in meteorites:
        node = tree
        for cat in met["categories"]:
            if cat not in node["children"]:
                node["children"][cat] = {"children": {}, "meteorites": []}
            node = node["children"][cat]
        node["meteorites"].append(met["name"])

    return tree


def main():
    if not os.path.isdir(PHOTOS_ROOT):
        print(f"Error: Photos directory not found at {PHOTOS_ROOT}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {PHOTOS_ROOT} ...")
    meteorites = walk_photos(PHOTOS_ROOT)
    tree = build_tree(meteorites)

    total_images = sum(len(m["images"]) for m in meteorites)
    print(f"Found {len(meteorites)} meteorites with {total_images} total images.")

    manifest = {
        "generated": True,
        "root": "Photos",
        "totalMeteorites": len(meteorites),
        "totalImages": total_images,
        "meteorites": meteorites,
        "tree": tree,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
