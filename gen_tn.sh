#!/usr/bin/env bash

# Exit immediately on unhandled error
set -euo pipefail

SRC_DIR="/home/dsvilko/Pictures/Meteorites"
DST_DIR="./Photos"

# 1. Recreate the directory structure safely
find -L "$SRC_DIR" -type d | grep -v GIGAPIXEL | grep -v DOWNLOAD | while IFS= read -r dir; do
    rel_path="${dir#"$SRC_DIR"}"
    mkdir -p "$DST_DIR/$rel_path"
done

# 2. Process JPEG images (handles .jpg, .jpeg, .JPG, .JPEG)
find -L "$SRC_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) | grep -v GIGAPIXEL | grep -v DOWNLOAD | while IFS= read -r file; do
    rel_path="${file#"$SRC_DIR"}"
    target_file="$DST_DIR/$rel_path"

    # Skip if thumbnail already exists
    [ -f "$target_file" ] && continue

    # Resize to fit within 1000x1000 while preserving aspect ratio
    echo "$file"
    magick "$file" -resize 1000x1000\> -quality 80 "$target_file"
done

# 3. Process videos (mp4/mkv) -> looping 3-second GIF thumbnails, max 300x300
find -L "$SRC_DIR" -type f \( -iname "*.mp4" -o -iname "*.mkv" \) | grep -v GIGAPIXEL | grep -v DOWNLOAD | while IFS= read -r file; do
    rel_path="${file#"$SRC_DIR"}"
    target_file="$DST_DIR/${rel_path%.*}.gif"

    # Skip if thumbnail already exists
    [ -f "$target_file" ] && continue

    echo "$file"
    # -nostdin: ffmpeg must not consume the find pipe feeding the while loop
    ffmpeg -nostdin -hide_banner -loglevel error -t 3 -i "$file" \
        -filter_complex "[0:v]fps=10,scale=w='min(iw,300)':h='min(ih,300)':force_original_aspect_ratio=decrease:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
        -loop 0 "$target_file"
done
