#!/usr/bin/env bash
# Stops NVDA Big Move Monitor daemon

PID=$(pgrep -f "rh/monitor_nvda_moves.py")
if [ -z "$PID" ]; then
    echo "⚪ No NVDA Monitor process found."
else
    echo "🛑 Stopping NVDA Monitor (PID: $PID)..."
    kill $PID
    echo "✅ Stopped."
fi
