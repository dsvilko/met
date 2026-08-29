#!/usr/bin/env python3
"""
Generate manifest.json from the Photos/ directory tree.

Walks the Photos/ hierarchy, finds leaf meteorite folders (those containing
.jpg/.jpeg image files), reads any info.txt descriptions, reads the pixel
dimensions of each image's full-resolution counterpart in Full/ (same
relative path, same filenames), and outputs a manifest.json that the gallery
webpage can consume.

Usage:
    python3 generate_manifest.py
    # produces manifest.json in the current directory
"""

import json
import os
import sys

try:
    from PIL import Image
    # Only image headers are read here (never pixel data), so Pillow's
    # decompression-bomb size guard is irrelevant; disable it to avoid
    # spurious warnings and skipped very large panoramas.
    Image.MAX_IMAGE_PIXELS = None
except ImportError:
    Image = None

PHOTOS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Photos")
FULL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Full")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}

EXIF_ORIENTATION_TAG = 0x0112
# Orientations 5-8 mean the image is stored rotated 90° from how it should
# be displayed, so the stored width/height must be swapped to get the
# dimensions a browser will actually render.
EXIF_SWAP_DIMENSIONS = {5, 6, 7, 8}


def get_image_dimensions(path):
    """Return (width, height) of a JPEG, EXIF-orientation corrected.

    Only the header is read, so this stays fast even for large files.
    Returns None if the file is missing or unreadable.
    """
    try:
        with Image.open(path) as im:
            width, height = im.size
            orientation = im.getexif().get(EXIF_ORIENTATION_TAG, 1)
            if orientation in EXIF_SWAP_DIMENSIONS:
                width, height = height, width
            return width, height
    except Exception as e:
        print(f"Warning: Could not read dimensions of {path}: {e}", file=sys.stderr)
        return None


def is_image(filename):
    """Check if a file is a JPEG image."""
    return os.path.splitext(filename.lower())[1] in IMAGE_EXTENSIONS


def walk_photos(root, full_root):
    """
    Walk the Photos/ tree and return a list of meteorite entries.

    Each entry is:
    {
        "name": "Gadamis 003 (Lunar ferroan anorthosite) - 81mg",
        "path": "Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 ...",
        "categories": ["Achondrites", "Lunar", "ferroan anorthosite"],
        "description": "contents of info.txt or empty string",
        "images": ["filename1.jpeg", "filename2.jpg"],
        "dims": {"filename1.jpeg": [4000, 3000], ...}
    }

    "dims" holds the dimensions of the full-resolution images in Full/
    (keyed by filename, same relative path as in Photos/). Images whose
    full-resolution counterpart is missing or unreadable are simply
    absent from "dims".
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

        # Read dimensions from the full-resolution counterparts in Full/
        dims = {}
        if full_root:
            rel_dir = os.path.relpath(dirpath, root)
            for img in images:
                size = get_image_dimensions(os.path.join(full_root, rel_dir, img))
                if size is not None:
                    dims[img] = [size[0], size[1]]

        meteorites.append({
            "name": name,
            "path": rel_path,
            "categories": categories,
            "description": description,
            "images": images,
            "dims": dims,
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

    full_root = None
    if Image is None:
        print("Warning: Pillow is not installed; image dimensions will be omitted.",
              file=sys.stderr)
    elif not os.path.isdir(FULL_ROOT):
        print(f"Warning: Full directory not found at {FULL_ROOT}; "
              "image dimensions will be omitted.", file=sys.stderr)
    else:
        full_root = FULL_ROOT

    print(f"Scanning {PHOTOS_ROOT} ...")
    meteorites = walk_photos(PHOTOS_ROOT, full_root)
    tree = build_tree(meteorites)

    total_images = sum(len(m["images"]) for m in meteorites)
    total_dims = sum(len(m["dims"]) for m in meteorites)
    print(f"Found {len(meteorites)} meteorites with {total_images} total images.")
    print(f"Read dimensions for {total_dims}/{total_images} full-resolution images.")

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
