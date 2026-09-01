#!/usr/bin/env python3
"""
prepare_full_tree.py

Walks SOURCE_ROOT and replicates its exact directory structure under
DEST_ROOT (directory names are left completely untouched, since
generate_manifest.py parses classification/weight info from them):

  - Images (.jpg/.jpeg/.png) are resized (if over MAX_MEGAPIXELS) and
    re-encoded to AVIF via ImageMagick. Renamed to
    <slugified-parent-folder-name>-<NN>.avif
    The original filename and the parent folder's full (unslugified) name
    are embedded into the output's EXIF (DocumentName / ImageDescription)
    so the info survives even if someone downloads just the image file.

  - Videos (.mp4/.mov/.avi/.mkv/.webm/.m4v) are transcoded via ffmpeg,
    renamed the same way: <slugified-parent-folder-name>-<NN>.mp4
    Original filename + folder name are embedded as MP4 metadata tags
    (comment / title) — the closest video equivalent of EXIF.

  - Everything else (info.txt, links.html, anything unrecognized) is
    copied unchanged, same filename, same folder.

Incremental by default: if a destination file already exists and is at
least as new as the source file, it's skipped. Use --force to reprocess
everything regardless of timestamps.

NOTE on numbering: the -NN suffix is assigned by sorted filename order
within each folder, recomputed fresh each run. If you add or remove a
file from the middle of a folder later, files after it in sort order
may get renumbered (and thus reprocessed) even though they didn't
change. This is a minor inefficiency, not a correctness problem — output
still ends up right — but worth knowing before you assume "skipped"
counts mean "nothing changed."

Usage:
    python3 prepare_full_tree.py --dry-run          # see what would happen
    python3 prepare_full_tree.py                    # run for real
    python3 prepare_full_tree.py --force             # reprocess everything
    python3 prepare_full_tree.py --limit 20          # only first 20 files (testing)
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG — edit these for your machine
# ---------------------------------------------------------------------------
SOURCE_ROOT = Path("Meteorites")             # your existing full-res tree
DEST_ROOT = Path("Full")           # new tree to be built (uploaded later)

MAX_MEGAPIXELS = 30_000_000
IMAGE_FORMAT = "avif"
IMAGE_QUALITY = 50                     # 0-100; test a few and adjust to taste

VIDEO_CODEC = "libsvtav1"
VIDEO_CRF = 30                          # svtav1 scale: ~x265 crf 26 visually
VIDEO_PRESET = 10                       # svtav1 presets are 0-13 (higher = faster)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
# Anything not in either set above (info.txt, links.html, .gif, future
# additions, etc.) is copied through unchanged, original filename kept.

LOG_CSV = Path("full_tree_log.csv")

# ---------------------------------------------------------------------------


def find_im_binary():
    for candidate in ("magick", "convert"):
        if shutil.which(candidate):
            return candidate
    sys.exit("ERROR: could not find ImageMagick ('magick' or 'convert') on PATH.")


def check_avif_support(im_bin):
    try:
        out = subprocess.run(
            [im_bin, "-list", "format"], capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        out = ""
    if "AVIF" not in out.upper():
        print(
            "WARNING: ImageMagick does not appear to list AVIF support "
            "(missing libheif delegate). AVIF encoding will likely fail.\n"
            "Install the delegate, or set IMAGE_FORMAT = 'webp' instead.",
            file=sys.stderr,
        )


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("WARNING: ffmpeg not found on PATH. Video files will be skipped.", file=sys.stderr)
        return False
    return True


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def get_pixel_count(im_bin, path: Path):
    out = subprocess.run(
        [im_bin, "identify", "-format", "%w %h", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    w, h = map(int, out.split())
    return w, h


def is_up_to_date(dst: Path, src_mtime: float, force: bool) -> bool:
    if force:
        return False
    return dst.exists() and dst.stat().st_mtime >= src_mtime


def process_image(im_bin, src: Path, dst: Path, folder_name: str, dry_run: bool) -> str:
    if dry_run:
        return "would-convert"
    cmd = [im_bin, str(src)]
    w, h = get_pixel_count(im_bin, src)
    if w * h > MAX_MEGAPIXELS:
        cmd += ["-resize", f"{MAX_MEGAPIXELS}@"]
    # Embed original filename + folder (meteorite) name into EXIF so the
    # info survives if someone downloads just the image.
    cmd += ["-set", "exif:DocumentName", src.name]
    cmd += ["-set", "exif:ImageDescription", folder_name]
    cmd += ["-quality", str(IMAGE_QUALITY), str(dst)]
    subprocess.run(cmd, check=True)
    os.utime(dst, (src.stat().st_mtime, src.stat().st_mtime))
    return "converted"


def process_video(src: Path, dst: Path, folder_name: str, dry_run: bool) -> str:
    if dry_run:
        return "would-transcode"
    comment = f"original: {src.name} | {folder_name}"
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", VIDEO_CODEC, "-crf", str(VIDEO_CRF), "-preset", str(VIDEO_PRESET),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-metadata", f"title={folder_name}",
        "-metadata", f"comment={comment}",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    os.utime(dst, (src.stat().st_mtime, src.stat().st_mtime))
    return "converted"


def copy_unchanged(src: Path, dst: Path, dry_run: bool) -> str:
    if dry_run:
        return "would-copy"
    shutil.copy2(src, dst)  # copy2 preserves mtime
    return "copied"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Reprocess even if destination is up to date")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without doing it")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N files (testing)")
    parser.add_argument("--source", default=str(SOURCE_ROOT), help="Source tree (default: Meteorites)")
    parser.add_argument("--dest", default=str(DEST_ROOT), help="Destination tree (default: Full)")
    args = parser.parse_args()

    source_root = Path(args.source)
    dest_root = Path(args.dest)

    if not source_root.exists():
        sys.exit(f"ERROR: SOURCE_ROOT '{source_root}' does not exist.")

    im_bin = find_im_binary()
    check_avif_support(im_bin)
    have_ffmpeg = check_ffmpeg()

    rows = []
    counts = {"converted": 0, "transcoded": 0, "copied": 0, "skipped": 0, "error": 0}
    processed = 0

    all_files = sorted(p for p in source_root.rglob("*") if p.is_file())
    if args.limit:
        all_files = all_files[: args.limit]

    # Assign sequential numbers to media files, per source folder.
    folder_counters = defaultdict(int)

    for src in all_files:
        rel_dir = src.parent.relative_to(source_root)
        dst_dir = dest_root / rel_dir
        ext = src.suffix.lower()
        folder_name = src.parent.name  # kept human-readable, unslugified, for EXIF

        if ext in IMAGE_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            folder_key = str(src.parent)
            folder_counters[folder_key] += 1
            idx = folder_counters[folder_key]
            folder_slug = slugify(folder_name) or "media"
            new_ext = IMAGE_FORMAT if ext in IMAGE_EXTENSIONS else "mp4"
            dst = dst_dir / f"{folder_slug}-{idx:02d}.{new_ext}"
        else:
            dst = dst_dir / src.name  # copy-through files keep original name

        src_mtime = src.stat().st_mtime
        if is_up_to_date(dst, src_mtime, args.force):
            counts["skipped"] += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            if ext in IMAGE_EXTENSIONS:
                status = process_image(im_bin, src, dst, folder_name, args.dry_run)
                counts["converted"] += 1
            elif ext in VIDEO_EXTENSIONS:
                if not have_ffmpeg:
                    rows.append([str(src), str(dst), "skipped: no ffmpeg"])
                    counts["skipped"] += 1
                    continue
                status = process_video(src, dst, folder_name, args.dry_run)
                counts["transcoded"] += 1
            else:
                status = copy_unchanged(src, dst, args.dry_run)
                counts["copied"] += 1
        except subprocess.CalledProcessError as e:
            status = f"ERROR: {e}"
            counts["error"] += 1

        rows.append([str(src), str(dst), status])
        processed += 1

    with LOG_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "dest", "status"])
        w.writerows(rows)

    print(f"Processed: {processed}  |  Skipped (up to date): {counts['skipped']}")
    print(f"  converted: {counts['converted']}  transcoded: {counts['transcoded']}  "
          f"copied: {counts['copied']}  errors: {counts['error']}")
    print(f"Full log: {LOG_CSV}")


if __name__ == "__main__":
    main()
