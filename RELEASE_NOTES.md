# Nexus AI v1.0.1 — OpenCode Zen native (Muse Spark 1.3 Contributor Free)

**Download:** `NexusAI.exe` below (Windows x64, no install, needs internet).

## New in 1.0.1
- Native OpenCode Zen Responses API: `POST https://opencode.ai/zen/v1/responses`
  model `muse-spark-1.3-contributor-free` (free contributor tier).
- Settings presets: **Use Zen Free** / **Use OpenRouter** one-click.
- Defaults now Zen Free. Custom backend still supports any OpenAI-compatible `/chat/completions`.

## Use your Zen key (secure, local only)
1. Get key at https://opencode.ai/auth
2. Open Nexus AI → Settings → **Use Zen Free** → paste `oc_sk_...` → Save.
3. Key lives in local `settings.json` (gitignored). NEVER commit it or bake into a public exe.
4. If a key was shared publicly, rotate it immediately at opencode.ai/auth.

## Also included (1.0.0)
- Agent scan: `Scan <1-8 urls> + task` → structured report + Export .md
- Internal Browser tab, safe PC Control (confirm + blocklist)
- Free Pollinations pool fallback + offline extractive report when pool is busy.

SHA256: see `NexusAI.exe.sha256.txt`
