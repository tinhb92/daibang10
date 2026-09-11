#!/usr/bin/env bash
# Quick attach script for Pendle Robinhood Desk tmux session on Hetzner

KEY_PATH="$HOME/.ssh/id_ed25519_hetzner"
SERVER="root@5.223.48.224"
SESSION="pendle-rh"

if [ ! -f "$KEY_PATH" ]; then
    echo "❌ SSH key not found at $KEY_PATH"
    exit 1
fi

echo "🦅 Connecting to Hetzner ($SERVER) -> tmux session: $SESSION..."
ssh -i "$KEY_PATH" -t "$SERVER" "tmux a -t $SESSION"
