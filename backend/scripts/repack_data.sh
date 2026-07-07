#!/usr/bin/env bash
# Re-encrypt the current data files into the split archive the Docker build reads.
# Reuses the SAME DATA_ENCRYPTION_KEY the app already decrypts with, so nothing on
# Railway has to change, a plain git push redeploys. The key is read from the
# environment and never printed.
#
#   railway run bash scripts/repack_data.sh        # key injected by Railway, never shown
#   DATA_ENCRYPTION_KEY=... bash scripts/repack_data.sh   # or supply it yourself
set -euo pipefail

if [ -z "${DATA_ENCRYPTION_KEY:-}" ]; then
  echo "ERROR: DATA_ENCRYPTION_KEY is not set in the environment." >&2
  echo "Run this through 'railway run' so Railway injects the existing key." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

echo "Packing data files..."
tar -czf data_bundle.tar.gz \
  menus \
  menu_db.json \
  menu_embeddings.npz \
  restaurant_places_data.json \
  restaurant_photos.json \
  restaurant_photo_urls.json \
  name_mapping.json

echo "Encrypting..."
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
  -in data_bundle.tar.gz \
  -out data_bundle.tar.gz.enc \
  -pass "pass:$DATA_ENCRYPTION_KEY"
rm data_bundle.tar.gz

echo "Splitting into 50MB parts (GitHub stays under its 100MB limit)..."
rm -f data_bundle.tar.gz.enc.part_*
split -b 50m data_bundle.tar.gz.enc data_bundle.tar.gz.enc.part_
rm data_bundle.tar.gz.enc

echo "Done. New parts:"
ls -la data_bundle.tar.gz.enc.part_* | awk '{printf "  %.0fMB  %s\n", $5/1048576, $9}'
echo
echo "Sanity check, decrypting the parts back with the same key..."
cat data_bundle.tar.gz.enc.part_* > /tmp/_menuelf_verify.enc
if openssl enc -aes-256-cbc -d -salt -pbkdf2 -iter 100000 \
     -in /tmp/_menuelf_verify.enc -pass "pass:$DATA_ENCRYPTION_KEY" 2>/dev/null \
   | tar -tzf - >/dev/null 2>&1; then
  echo "  OK, the archive decrypts and unpacks cleanly with this key."
else
  echo "  ERROR, the parts did not decrypt with this key. Do NOT commit." >&2
  rm -f /tmp/_menuelf_verify.enc
  exit 1
fi
rm -f /tmp/_menuelf_verify.enc
