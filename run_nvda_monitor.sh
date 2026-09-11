#!/usr/bin/env bash
# Runs NVDA Big Move & Order Fill Monitor in background

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
    echo "⚠️ NVDA Monitor is already running (PID: $PID)"
    exit 0
fi

echo "🦅 Launching NVDA Market Big Move Monitor daemon..."
nohup $PYTHON_EXEC -u "$DIR/rh/monitor_nvda_moves.py" --loop --interval 60 >> "$DIR/nvda_monitor.log" 2>&1 &
NEW_PID=$!
echo "✅ Monitor started (PID: $NEW_PID). Logs at nvda_monitor.log"
