#!/usr/bin/env bash
# Syncs daibang10 to Hetzner VPS (~/downl/daibang10/)
# Strictly isolates from daibang9 and excludes secrets (.env)

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🦅 Syncing daibang10 to Hetzner VPS (~/downl/daibang10/)..."
rsync -avzu \
  --exclude '.env*' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '*.log' \
  --exclude '*state.json' \
  --exclude '.git' \
  -e "ssh -i ~/.ssh/id_ed25519_hetzner" \
  ./ root@5.223.48.224:~/downl/daibang10/

echo "✅ Sync complete. Remote target: ~/downl/daibang10/"
