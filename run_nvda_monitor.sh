#!/usr/bin/env bash
# Runs NVDA Big Move & Order Fill Monitor in background

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="/Users/tin/miniconda3/envs/jlab/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="python3"
fi

PID=$(pgrep -f "rh/monitor_nvda_moves.py")
if [ -n "$PID" ]; then
    echo "⚠️ NVDA Monitor is already running (PID: $PID)"
    exit 0
fi

echo "🦅 Launching NVDA Market Big Move Monitor daemon..."
nohup $PYTHON_EXEC -u "$DIR/rh/monitor_nvda_moves.py" --loop --interval 60 >> "$DIR/nvda_monitor.log" 2>&1 &
NEW_PID=$!
echo "✅ Monitor started (PID: $NEW_PID). Logs at nvda_monitor.log"
