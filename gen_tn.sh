#!/usr/bin/env bash

# Exit immediately on unhandled error
set -euo pipefail

SRC_DIR="/home/dsvilko/Pictures/Meteorites"
DST_DIR="./Photos"

# 1. Recreate the directory structure safely
find "$SRC_DIR" -type d | grep -v GIGAPIXEL | grep -v DOWNLOAD | while IFS= read -r dir; do
    rel_path="${dir#"$SRC_DIR"}"
    mkdir -p "$DST_DIR/$rel_path"
done

# 2. Process JPEG images (handles .jpg, .jpeg, .JPG, .JPEG)
find "$SRC_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) | while IFS= read -r file; do
    rel_path="${file#"$SRC_DIR"}"
    target_file="$DST_DIR/$rel_path"

    # Resize to fit within 1000x1000 while preserving aspect ratio
    echo $file
		magick "$file" -resize 1000x1000\> -quality 80 "$target_file"
done
