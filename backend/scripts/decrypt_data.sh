#!/usr/bin/env bash
# Decrypt restaurant data files from the encrypted archive.
# Usage: DATA_ENCRYPTION_KEY=<hex-key> bash scripts/decrypt_data.sh
set -euo pipefail

if [ -z "${DATA_ENCRYPTION_KEY:-}" ]; then
  echo "ERROR: DATA_ENCRYPTION_KEY environment variable is not set."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ARCHIVE="$BACKEND_DIR/data_bundle.tar.gz.enc"

# Reassemble split parts if the single archive doesn't exist
if [ ! -f "$ARCHIVE" ] && ls "$BACKEND_DIR"/data_bundle.tar.gz.enc.part_* >/dev/null 2>&1; then
  echo "Reassembling archive from parts..."
  cat "$BACKEND_DIR"/data_bundle.tar.gz.enc.part_* > "$ARCHIVE"
fi

if [ ! -f "$ARCHIVE" ]; then
  echo "ERROR: Encrypted archive not found at $ARCHIVE"
  exit 1
fi

echo "Decrypting data..."
openssl enc -aes-256-cbc -d -salt -pbkdf2 -iter 100000 \
  -in "$ARCHIVE" \
  -out "$BACKEND_DIR/data_bundle.tar.gz" \
  -pass "pass:$DATA_ENCRYPTION_KEY"

echo "Extracting..."
tar -xzf "$BACKEND_DIR/data_bundle.tar.gz" -C "$BACKEND_DIR"
rm "$BACKEND_DIR/data_bundle.tar.gz" "$ARCHIVE"

echo "Done. Data files restored to backend/."
