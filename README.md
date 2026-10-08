# ⬢ Nexus AI — Free Claude-class Windows Assistant

> Production-grade desktop AI: chat, **agent web-scan → summary of observations**, internal browsing, safe PC control.
> Free-first (no key) + BYOK for true **Muse Spark 1.3** via OpenRouter / OpenCode Zen.

![platform](https://img.shields.io/badge/platform-Windows-0078D6)
![python](https://img.shields.io/badge/python-3.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![exe](https://img.shields.io/badge/dist-NexusAI.exe-7c5cff)

## ✨ What it does

- **Chat + reasoning** — dark, Claude-style SaaS UI (CustomTkinter). Free, no signup.
- **Agent scan task** — paste 1–8 URLs + instruction, e.g:
  `Scan https://example.com and https://httpbin.org/html, compare them, create summary of observations`
  → fetches live, builds structured Markdown report: Summary, Per-site observations, Comparison table, Risks/caveats, Action items, Sources. Export to `.md`.
- **Internal browsing** — Browser tab: fetch + clean reader view (title, text, links). No key.
- **PC control (safe)** — System info, screenshot, file list, launch app/file, run shell command. Every launch/shell asks for confirmation. Destructive patterns (`format`, `rm -rf /`, etc.) are blocked in `core/pctools.py`.
- **BYOK pro tier** — Settings tab: switch Free → Custom (any OpenAI-compatible). Pre-filled for OpenRouter + Muse Spark 1.3.

## 🧠 Powered by Muse 1.3?

Honest pattern (the only legal SaaS pattern):

| Tier | Backend | Key? | Notes |
|------|---------|------|-------|
| Free (default) | Pollinations `openai` pool | No | Shared, rate-limited, great for trial/demo |
| Pro (Zen) | `muse-spark-1.3-contributor-free` via `https://opencode.ai/zen/v1/responses` | Yes, yours (`oc_sk_...`) | True Muse-class quality, free contributor tier |
| Pro (alt) | `meta/muse-spark-1.3` via OpenRouter | Yes | Same pattern, other gateway |

No app can bundle unlimited free Claude/Muse — free shared pool + BYOK is the $1M SaaS pattern. Get a key from https://opencode.ai/auth (free tier includes muse-spark-1.3-contributor-free), then in-app: Settings → Use Zen Free → paste key → Save. Key stays in local `settings.json` (gitignored) — never commit it or bake it into a public exe. If a key was ever pasted publicly, rotate it immediately.

## 🚀 Quickstart

### Option A — run the .exe (recommended)
1. Go to **Releases** → download `NexusAI.exe` (Windows x64, ~26MB, no install).
2. Double-click. No admin needed. Needs internet for AI + web fetch.

### Option B — run from source
```bat
pip install -r requirements.txt
python app.py
```

### Build the .exe yourself
```bat
build_exe.bat
:: output: dist\NexusAI.exe
:: PyInstaller --onefile --windowed, collects customtkinter
```

## 🗂 Project layout

```
nexus-ai/
  app.py              # UI: Chat / Browser / PC Control / Settings (CustomTkinter)
  core/
    llm.py            # LLMClient: free POST + legacy GET fallback + custom backend
    agent.py          # run_scan_task(): URLs → fetch → structured report (+ offline fallback)
    webtools.py       # web_search (DDG, no key), web_fetch (requests+bs4), scan_websites
    pctools.py        # pc_info, screenshot (PIL), file ops, shell_run (blocklist), app_launch
  requirements.txt
  build_exe.bat
  NexusAI.spec
```

## 🛡 Safety

- Shell/launch always show a confirm dialog.
- `BLOCKED` list in `pctools.py` refuses destructive commands.
- Browser fetch uses timeout + `User-Agent`, strips scripts/styles.
- Keys stored only in local `settings.json`, never sent except to your configured backend.

## ⚙ Requirements

- Windows 10/11 x64, Python 3.12 (source only), internet.
- Deps: `customtkinter, requests, beautifulsoup4, lxml, pillow, psutil, pyinstaller`.

## 🗺 Roadmap

- [ ] Streaming tokens, stop button
- [ ] Multi-tab browser history + screenshots in-report
- [ ] Voice input, global hotkey
- [ ] Auto-updater, signed installer

## 📄 License

MIT — see `LICENSE`. Free for personal + commercial. You are responsible for API costs on BYOK and for commands you confirm.
