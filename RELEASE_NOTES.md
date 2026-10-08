# Nexus AI v1.0.0 — Free Claude-class Windows Assistant

**Download:** `NexusAI.exe` below (Windows x64, ~26MB, no install, no admin).

## What it does
- Chat + reasoning (free, no key) — dark SaaS UI
- Agent task: `Scan <urls> + instruction` → live fetch → structured report (summary, per-site, comparison table, risks, actions, sources) + Export .md
- Internal Browser tab (fetch + reader view)
- Safe PC Control: sysinfo, screenshot, files, launch, shell (always confirms, blocklist for destructive cmds)
- Settings → Free (Pollinations pool) or Custom BYOK for true Muse Spark 1.3 (`meta/muse-spark-1.3` via OpenRouter / `opencode/muse-spark-1.3-contributor-free` via OpenCode Zen)

## Run
1. Download `NexusAI.exe` → double-click (needs internet).
2. Or source: `pip install -r requirements.txt && python app.py`

## Notes
- Free pool is shared/rate-limited; long scans fall back to extractive report when pool is busy.
- Keys stay in local `settings.json`.
- MIT license. You are responsible for BYOK costs + commands you confirm.

SHA256: see `NexusAI.exe.sha256.txt`
