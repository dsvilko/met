#!/usr/bin/env python3
"""
Generate manifest.json from the Photos/ directory tree.

Walks the Photos/ hierarchy, finds leaf meteorite folders (those containing
.avif/.gif image files), reads any info.txt descriptions, links.html
(link HTML, kept separate) and tags files (one tag per line, normalized
to lowercase), reads the pixel
dimensions of each image's full-resolution counterpart in Full/ (same
relative path, same filenames), and outputs a manifest.json that the gallery
webpage can consume.

Dimensions are read with Pillow when possible. AVIF is only supported by
Pillow when it is built against libavif; otherwise all AVIF dimensions are
read in one batch via ImageMagick (`magick identify -ping`), which decodes
only the file headers and is therefore very fast.

Usage:
    python3 generate_manifest.py
    # produces manifest.json in the current directory
"""

import json
import os
import shutil
import subprocess
import sys

try:
    from PIL import Image, features
    # Only image headers are read here (never pixel data), so Pillow's
    # decompression-bomb size guard is irrelevant; disable it to avoid
    # spurious warnings and skipped very large panoramas.
    Image.MAX_IMAGE_PIXELS = None
except ImportError:
    Image = None

# Pillow can only parse AVIF when built against libavif (or with the
# pillow-avif-plugin installed); otherwise we fall back to ImageMagick.
PILLOW_HAS_AVIF = Image is not None and features.check("avif")

PHOTOS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Photos")
FULL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Full")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")

IMAGE_EXTENSIONS = {".avif", ".gif"}

EXIF_ORIENTATION_TAG = 0x0112
# Orientations 5-8 mean the image is stored rotated 90° from how it should
# be displayed, so the stored width/height must be swapped to get the
# dimensions a browser will actually render.
EXIF_SWAP_DIMENSIONS = {5, 6, 7, 8}

# Dimensions of full-resolution AVIF files (which stock Pillow builds cannot
# parse), read in one batch with ImageMagick and cached: absolute path ->
# (width, height), EXIF orientation already applied.
_avif_dims = {}


def _identify_command():
    """Return the ImageMagick identify command, or None if unavailable."""
    for candidate in (["magick", "identify"], ["identify"]):
        if shutil.which(candidate[0]):
            return candidate
    return None


def preload_avif_dims(full_root):
    """Read dimensions of every AVIF under full_root using ImageMagick.

    `identify -ping` decodes only the file header, so a single invocation
    covers the whole tree in about a second. Results are cached in
    _avif_dims, keyed by absolute path, with EXIF orientation applied.
    """
    cmd = _identify_command()
    if cmd is None:
        print("Warning: ImageMagick ('magick identify') not found; "
              "AVIF dimensions will be omitted.", file=sys.stderr)
        return
    avif_paths = []
    for dirpath, _dirnames, filenames in os.walk(full_root):
        avif_paths.extend(
            os.path.join(dirpath, f) for f in filenames
            if os.path.splitext(f.lower())[1] == ".avif")
    if not avif_paths:
        return
    # One "<w> <h> <orientation> <path>" line per file; %d/%f reconstruct
    # the path exactly as it was passed in. An absent EXIF orientation
    # yields an empty field, treated as 1 (normal) below.
    format_str = "%w %h %[EXIF:Orientation] %d/%f\n"
    try:
        proc = subprocess.run(
            cmd + ["-ping", "-quiet", "-format", format_str, "--", *avif_paths],
            capture_output=True, text=True)
    except OSError as e:
        print(f"Warning: could not run {cmd[0]}: {e}; "
              "AVIF dimensions will be omitted.", file=sys.stderr)
        return
    if proc.returncode != 0:
        print(f"Warning: {cmd[0]} identify exited with status "
              f"{proc.returncode}; some AVIF dimensions may be missing.",
              file=sys.stderr)
    for line in proc.stdout.splitlines():
        try:
            w_str, h_str, o_str, path = line.split(" ", 3)
            width, height = int(w_str), int(h_str)
            orientation = int(o_str) if o_str else 1
        except ValueError:
            continue
        if orientation in EXIF_SWAP_DIMENSIONS:
            width, height = height, width
        _avif_dims[path] = (width, height)


def get_image_dimensions(path):
    """Return (width, height) of an image, EXIF-orientation corrected.

    AVIF dimensions come from the ImageMagick cache (stock Pillow builds
    cannot parse AVIF); everything else goes through Pillow, reading only
    the header so this stays fast even for large files.
    Returns None if the file is missing or unreadable.
    """
    if path.lower().endswith(".avif") and not PILLOW_HAS_AVIF:
        return _avif_dims.get(os.path.abspath(path))
    try:
        with Image.open(path) as im:
            width, height = im.size
            orientation = im.getexif().get(EXIF_ORIENTATION_TAG, 1)
            if orientation in EXIF_SWAP_DIMENSIONS:
                width, height = height, width
            return width, height
    except FileNotFoundError:
        # The full-resolution counterpart simply does not exist (e.g. GIFs
        # are thumbnails only); the image is left out of "dims" silently.
        return None
    except Exception as e:
        print(f"Warning: Could not read dimensions of {path}: {e}", file=sys.stderr)
        return None


def is_image(filename):
    """Check if a file is a supported image (AVIF or GIF)."""
    return os.path.splitext(filename.lower())[1] in IMAGE_EXTENSIONS


def walk_photos(root, full_root):
    """
    Walk the Photos/ tree and return a list of meteorite entries.

    A folder is a meteorite folder when it contains image files or an
    info.txt; folders with neither are pure categories. Image-less
    meteorite folders (pure parents) get an empty "images" list.

    Each entry is:
    {
        "name": "Gadamis 003 (Lunar ferroan anorthosite) - 81mg",
        "path": "Photos/Achondrites/Lunar/ferroan anorthosite/Gadamis 003 ...",
        "categories": ["Achondrites", "Lunar", "ferroan anorthosite"],
        "description": "contents of info.txt or empty string",
        "links": "contents of links.html (raw HTML) or empty string",
        "tags": ["historical", ...]  (omitted when the folder has no tags file),
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

        # A folder is a meteorite folder if it holds photos OR an info.txt.
        # Image-less meteorite folders exist: pure parents whose photos
        # live only in their sub-folders (e.g. a fall with several named
        # specimens); folders with neither stay pure categories.
        info_path = os.path.join(dirpath, "info.txt")
        has_info = os.path.isfile(info_path)
        if not images and not has_info:
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
        if has_info:
            try:
                with open(info_path, "r", encoding="utf-8", errors="replace") as f:
                    description = f.read().strip()
            except Exception as e:
                print(f"Warning: Could not read {info_path}: {e}", file=sys.stderr)

        # Read links.html if present (raw HTML, rendered as-is by the gallery)
        links = ""
        links_path = os.path.join(dirpath, "links.html")
        if os.path.isfile(links_path):
            try:
                with open(links_path, "r", encoding="utf-8", errors="replace") as f:
                    # Fix outdated domain in old links.html files
                    links = f.read().strip().replace("meteoritestudies.com",
                                                     "meteoritestudies2.com")
            except Exception as e:
                print(f"Warning: Could not read {links_path}: {e}", file=sys.stderr)

        # Read tags if present (one tag per line; blank lines skipped,
        # normalized to lowercase so 'Historical' and 'historical' merge,
        # deduplicated preserving first occurrence)
        tags = []
        tags_path = os.path.join(dirpath, "tags")
        if os.path.isfile(tags_path):
            try:
                with open(tags_path, "r", encoding="utf-8", errors="replace") as f:
                    tags = list(dict.fromkeys(
                        line.strip().lower() for line in f if line.strip()))
            except Exception as e:
                print(f"Warning: Could not read {tags_path}: {e}", file=sys.stderr)

        # Read dimensions from the full-resolution counterparts in Full/
        dims = {}
        if full_root:
            rel_dir = os.path.relpath(dirpath, root)
            for img in images:
                size = get_image_dimensions(os.path.join(full_root, rel_dir, img))
                if size is not None:
                    dims[img] = [size[0], size[1]]

        # Sort images by megapixels, largest first. Images whose full-res
        # dimensions are unknown sort last (stable, so alphabetical order
        # is preserved within each group).
        images.sort(key=lambda img: dims.get(img, [0, 0])[0] * dims.get(img, [0, 0])[1], reverse=True)

        entry = {
            "name": name,
            "path": rel_path,
            "categories": categories,
            "description": description,
            "links": links,
            "images": images,
            "dims": dims,
        }
        # Omit the key entirely for untagged meteorites to keep the
        # manifest lean
        if tags:
            entry["tags"] = tags
        meteorites.append(entry)

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
        if not PILLOW_HAS_AVIF:
            # Stock Pillow cannot read AVIF; gather AVIF dimensions with
            # ImageMagick up front.
            preload_avif_dims(FULL_ROOT)

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
