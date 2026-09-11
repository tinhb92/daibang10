#!/usr/bin/env bash
# Stops Pendle V2 Robinhood Desk Monitor daemon and dispatches Telegram notification

PID=$(pgrep -f "rh/monitor_nvda_moves.py")
if [ -z "$PID" ]; then
    echo "⚪ No Pendle V2 Desk Monitor process found."
else
    echo "🛑 Stopping Pendle V2 Desk Monitor (PID: $PID)..."
    kill -15 $PID
    sleep 2
    echo "✅ Monitor stopped. Shutdown alert sent to Telegram."
fi
