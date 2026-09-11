# Antigravity Operating Rules for Daibang10

## 1. Absolute Off-Chain Autonomy
- **Full Execution Authority**: Antigravity has complete authorization to execute all off-chain and local tasks directly without asking for permission, without asking clarifying questions, and without creating blocking plans (`request_feedback: false`).
- **Localhost & Shell Commands**: You are fully authorized to run `curl`, local HTTP requests, server management, file edits, testing scripts, and shell commands autonomously. Proceed decisively.
- **Included Scope**:
  - Modifying backend scripts, data loggers, and quant engines (`rh/`, `rh/agents/`, `rh/config/`).
  - Running shell commands, `rsync`, git commits for analytics/documentation, and background process management.
  - Querying Pendle V2 and Boros public APIs, executing dry-run order simulations (`--dry-run`), data analysis, and unit tests.
  - Updating markdown dashboards (`portfolio_manager_view.md`, `patterns.md`).
- **Rule**: DO NOT call `ask_question`. DO NOT pause to ask "Should I proceed?", "Would you like me to apply this?", or "Can I restart the bot?". Directly execute, verify, and present the final outcome.

## 2. On-Chain Safety Boundary Only
- **Strict Permission Required**: Reserve user confirmation strictly and exclusively for executing live, real-money transactions that broadcast on-chain (`--execute`). Simulations and `--dry-run` are always autonomous.

## 3. Push-Only Telegram Notification Scope
- Telegram (`@pendleV2_bot`) is strictly a **one-way push notification and alert dispatcher**.
- Never develop interactive Telegram bot assistant features, polling command workers, or conversational reply handlers.

## 4. Hetzner VPS Process Boundary
- **Execution Bots (Protected)**: NEVER restart or terminate live execution processes running with `--execute` without prior confirmation.
- **Monitoring & Sentinels (Auto-Restart Permitted)**: Read-only monitoring daemons (`rh/monitor_nvda_moves.py`) inside tmux `pendle-rh` on Hetzner can and should be synced and automatically restarted when updating code.
