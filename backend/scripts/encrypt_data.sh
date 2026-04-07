#!/usr/bin/env bash
# Encrypt restaurant data files into a single encrypted archive.
# Usage: DATA_ENCRYPTION_KEY=<hex-key> bash scripts/encrypt_data.sh
set -euo pipefail

if [ -z "${DATA_ENCRYPTION_KEY:-}" ]; then
  echo "ERROR: DATA_ENCRYPTION_KEY environment variable is not set."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "Packing data files..."
tar -czf "$BACKEND_DIR/data_bundle.tar.gz" \
  -C "$BACKEND_DIR" \
  menus \
  menu_db.json \
  menu_embeddings.npz \
  restaurant_places_data.json \
  restaurant_photos.json \
  restaurant_photo_urls.json \
  name_mapping.json

echo "Encrypting..."
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
  -in "$BACKEND_DIR/data_bundle.tar.gz" \
  -out "$BACKEND_DIR/data_bundle.tar.gz.enc" \
  -pass "pass:$DATA_ENCRYPTION_KEY"

rm "$BACKEND_DIR/data_bundle.tar.gz"

SIZE=$(du -h "$BACKEND_DIR/data_bundle.tar.gz.enc" | cut -f1)
echo "Done. Encrypted archive: backend/data_bundle.tar.gz.enc ($SIZE)"
