#!/usr/bin/env bash
# Runs Pendle V2 Robinhood Desk Monitor daemon (NVDA, sNET, sNUKE, PFE) in background

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Auto-detect Python interpreter (prefers conda jlab on Hetzner & Mac)
PYTHON_EXEC="python3"
for candidate in "/root/anaconda3/envs/jlab/bin/python" "/Users/tin/miniconda3/envs/jlab/bin/python"; do
    if [ -f "$candidate" ]; then
        PYTHON_EXEC="$candidate"
        break
    fi
done

PID=$(pgrep -f "rh/monitor_nvda_moves.py")
if [ -n "$PID" ]; then
    echo "⚠️ Pendle V2 Desk Monitor is already running (PID: $PID)"
    exit 0
fi

echo "🦅 Launching Pendle V2 Robinhood Desk Monitor daemon..."
nohup $PYTHON_EXEC -u "$DIR/rh/monitor_nvda_moves.py" --loop --interval 60 --heartbeat-interval 3600 >> "$DIR/nvda_monitor.log" 2>&1 &
NEW_PID=$!
echo "✅ Monitor started (PID: $NEW_PID). Startup alert sent to Telegram. Logs at nvda_monitor.log"
