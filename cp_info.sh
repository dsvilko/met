#!/usr/bin/env bash

set -euo pipefail

SRC_DIR="/home/dsvilko/Pictures/Meteorites"
DST_DIR="./Photos"

# 1. Recreate directory structure
find "$SRC_DIR" -type d | while IFS= read -r dir; do
    rel_path="${dir#"$SRC_DIR"}"
    mkdir -p "$DST_DIR/$rel_path"
done

# 2. Process JPEGs and copy info.txt files safely
find "$SRC_DIR" -type f \( -iname "info.txt" \) | while IFS= read -r file; do
    rel_path="${file#"$SRC_DIR"}"
    target_file="$DST_DIR/$rel_path"

    cp "$file" "$target_file"
done
