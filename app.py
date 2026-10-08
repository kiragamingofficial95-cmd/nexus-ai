"""Nexus AI — Claude-class Windows desktop assistant (free-first).
Run:  pip install -r requirements.txt && python app.py
Build exe: build_exe.bat (PyInstaller --onefile --windowed)
"""
import json, os, re, threading, tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

import customtkinter as ctk
import requests

from core.llm import LLMClient
from core.webtools import web_fetch, web_search, extract_urls
from core.agent import run_scan_task
from core import pctools

SETTINGS_FILE = Path("settings.json")
HISTORY_FILE = Path("history.json")

DEFAULTS = {
    "mode": "free",
    "api_key": "",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "meta/muse-spark-1.3",
    "theme": "dark",
}

def load_settings():
    s = dict(DEFAULTS)
    try:
        if SETTINGS_FILE.exists():
            s.update(json.loads(SETTINGS_FILE.read_text()))
    except Exception:
        pass
    return s

def save_settings(s):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    except Exception:
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#7c5cff"
ACCENT2 = "#22d3ee"
BG = "#0b0e17"

class ChatBubble(ctk.CTkFrame):
    def __init__(self, master, role, text):
        color = "#1a2138" if role == "assistant" else "#2b1f4d"
        border = ACCENT2 if role == "assistant" else ACCENT
        super().__init__(master, fg_color=color, border_color=border,
                         border_width=1, corner_radius=12)
        who = "NEXUS AI  •  Muse Spark 1.3 class" if role == "assistant" else "YOU"
        lbl = ctk.CTkLabel(self, text=who, font=("Segoe UI", 10, "bold"),
                           text_color="#9aa4c7")
        lbl.pack(anchor="w", padx=12, pady=(8, 0))
        box = ctk.CTkTextbox(self, wrap="word", font=("Segoe UI", 13),
                             fg_color="transparent", activate_scrollbars=False)
        box.pack(fill="x", padx=8, pady=(2, 8))
        box.insert("1.0", text)
        lines = max(3, min(28, len(text) // 70 + text.count("\n") + 2))
        box.configure(height=lines * 22, state="disabled")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.llm = self._make_llm()
        self.history = []  # [{role, content}]
        try:
            if HISTORY_FILE.exists():
                self.history = json.loads(HISTORY_FILE.read_text())[-50:]
        except Exception:
            pass
        self.title("Nexus AI — Free Claude-class Assistant")
        self.geometry("1220x800")
        self.minsize(1000, 680)
        self.configure(fg_color=BG)
        self._build()

    def _make_llm(self):
        s = self.settings
        return LLMClient(mode=s.get("mode", "free"), api_key=s.get("api_key", ""),
                         base_url=s.get("base_url", ""), model=s.get("model", ""))

    # ---------- layout ----------
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, width=230, fg_color="#0f1426", corner_radius=0)
        side.grid(row=0, column=0, sticky="nswe")
        side.grid_propagate(False)

        logo = ctk.CTkLabel(side, text="⬢  NEXUS AI", font=("Segoe UI", 22, "bold"),
                            text_color="white")
        logo.pack(pady=(22, 2), padx=16, anchor="w")
        sub = ctk.CTkLabel(side, text="Free  •  Muse Spark 1.3 class\nPC Control + Web Research",
                           font=("Segoe UI", 11), text_color="#8b93b8", justify="left")
        sub.pack(padx=16, anchor="w", pady=(0, 16))

        for name in ["Chat", "Browser", "PC Control", "Settings"]:
            b = ctk.CTkButton(side, text=name, anchor="w", height=38,
                              fg_color="transparent", hover_color="#1c2444",
                              text_color="#cfd6f2", font=("Segoe UI", 13, "bold"),
                              command=lambda n=name: self.tabs.set(n))
            b.pack(fill="x", padx=12, pady=3)

        side_btn = ctk.CTkFrame(side, fg_color="transparent")
        side_btn.pack(side="bottom", fill="x", padx=12, pady=14)
        ctk.CTkButton(side_btn, text="＋  New chat", fg_color=ACCENT,
                      hover_color="#6a4de0", command=self.new_chat).pack(fill="x", pady=3)
        ctk.CTkButton(side_btn, text="Export report (.md)", fg_color="#16203a",
                      border_color=ACCENT, border_width=1,
                      command=self.export_md).pack(fill="x", pady=3)
        self.agent_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(side_btn, text="Agent mode (auto scan + tools)",
                      variable=self.agent_var).pack(pady=8)

        self.tabs = ctk.CTkTabview(self, fg_color=BG, segmented_button_fg_color="#121832",
                                   segmented_button_selected_color=ACCENT)
        self.tabs.grid(row=0, column=1, sticky="nswe", padx=12, pady=12)
        for t in ["Chat", "Browser", "PC Control", "Settings"]:
            self.tabs.add(t)
        self._build_chat(self.tabs.tab("Chat"))
        self._build_browser(self.tabs.tab("Browser"))
        self._build_pc(self.tabs.tab("PC Control"))
        self._build_settings(self.tabs.tab("Settings"))

        self.status = ctk.CTkLabel(self, text="Ready  •  Free mode, no key needed",
                                   font=("Segoe UI", 11), text_color="#7f8aa8")
        self.status.grid(row=1, column=1, sticky="w", padx=18, pady=(0, 8))
        self._render_history()

    # ---------- chat ----------
    def _build_chat(self, f):
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)
        self.chat_scroll = ctk.CTkScrollableFrame(f, fg_color="#0d1224")
        self.chat_scroll.grid(row=0, column=0, sticky="nswe", pady=(0, 8))
        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="we")
        bottom.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(bottom, placeholder_text="Ask anything…  Try:  Scan https://example.com and https://… then summarize with observations",
                                  height=46, font=("Segoe UI", 13))
        self.entry.grid(row=0, column=0, sticky="we", padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.send())
        ctk.CTkButton(bottom, text="Send ➤", width=110, height=46, fg_color=ACCENT,
                      hover_color="#6a4de0", font=("Segoe UI", 13, "bold"),
                      command=self.send).grid(row=0, column=1)

    def add_msg(self, role, text):
        ChatBubble(self.chat_scroll, role, text).pack(fill="x", padx=10, pady=6)
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _render_history(self):
        for m in self.history[-20:]:
            self.add_msg(m["role"], m["content"])
        if not self.history:
            self.add_msg("assistant", "Hello — I'm **Nexus AI**, your free Claude-class assistant.\n\nI can:\n• Chat + reason (free, no key)\n• **Scan websites**: paste 1-8 URLs + task, e.g. 'Scan these sites and compare pricing, create summary of observations'\n• **Control your PC**: screenshot, files, launch apps, run commands (with confirmation)\n• **Internal browsing**: open the Browser tab, fetch any page\n\nAgent mode is ON — just type your task.")

    def set_status(self, t):
        self.status.configure(text=t)
        self.update_idletasks()

    def new_chat(self):
        self.history = []
        for w in self.chat_scroll.winfo_children():
            w.destroy()
        self._render_history()

    def export_md(self):
        if not self.history:
            return messagebox.showinfo("Export", "Nothing to export yet.")
        p = filedialog.asksaveasfilename(defaultextension=".md",
            filetypes=[("Markdown", "*.md")], initialfile="nexus-report.md")
        if not p:
            return
        md = "# Nexus AI report\n\n" + "\n\n---\n\n".join(
            f"**{'Nexus' if m['role']=='assistant' else 'You'}:**\n\n{m['content']}" for m in self.history)
        Path(p).write_text(md, encoding="utf-8")
        messagebox.showinfo("Export", f"Saved to {p}")

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.history.append({"role": "user", "content": text})
        self.add_msg("user", text)
        self.set_status("Thinking…")
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def _answer(self, text):
        try:
            urls = extract_urls(text)
            agent_on = self.agent_var.get()
            looks_like_scan = bool(urls) or any(
                k in text.lower() for k in ["scan", "summar", "compar", "research", "observ", "websites", "sites"])
            if agent_on and looks_like_scan and (urls or len(text) > 30):
                self.set_status("Agent: scanning live websites…")
                report, pages = run_scan_task(text, self.llm, progress=self.set_status)
                ok = sum(1 for p in pages if not p["error"])
                header = f"_Fetched {ok}/{len(pages)} site(s) live._\n\n"
                final = header + report
            else:
                # normal chat (+ light tool awareness for PC questions)
                msgs = [{"role": m["role"], "content": m["content"]} for m in self.history[-12:]]
                final = self.llm.chat(msgs)
            self.history.append({"role": "assistant", "content": final})
            try:
                HISTORY_FILE.write_text(json.dumps(self.history[-50:], indent=2))
            except Exception:
                pass
            self.after(0, lambda: (self.add_msg("assistant", final), self.set_status("Ready")))
        except Exception as e:
            err = f"Request failed: {e}\n\nTip: free mode uses Pollinations (needs internet). For Muse Spark 1.3, go to Settings → Custom → paste OpenRouter/OpenCode key."
            self.after(0, lambda: (self.add_msg("assistant", err), self.set_status("Error")))

    # ---------- browser ----------
    def _build_browser(self, f):
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=0, column=0, sticky="we", pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(top, placeholder_text="https://…", height=40)
        self.url_entry.grid(row=0, column=0, sticky="we", padx=(0, 8))
        ctk.CTkButton(top, text="Fetch", width=100, fg_color=ACCENT2, text_color="black",
                       command=self.browser_fetch).grid(row=0, column=1)
        self.browser_box = ctk.CTkTextbox(f, font=("Segoe UI", 13), wrap="word")
        self.browser_box.grid(row=1, column=0, sticky="nswe")
        self.browser_box.insert("1.0", "Internal browser — enter a URL above and press Fetch.\nNo key needed. Pages are cleaned to readable text.")

    def browser_fetch(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.browser_box.delete("1.0", "end")
        self.browser_box.insert("end", f"Fetching {url} …\n")
        def work():
            d = web_fetch(url)
            txt = f"# {d['title']}\n{d['url']}\n\n{d['text'] or 'ERROR: '+d['error']}\n"
            if d["links"]:
                txt += "\n## Links\n" + "\n".join("• " + l for l in d["links"][:20])
            self.after(0, lambda: (self.browser_box.delete("1.0", "end"),
                                   self.browser_box.insert("1.0", txt)))
        threading.Thread(target=work, daemon=True).start()

    # ---------- PC ----------
    def _build_pc(self, f):
        f.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(f, text="PC Control — every command asks for confirmation",
                     font=("Segoe UI", 13, "bold"), text_color="#9aa4c7").grid(
                     row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        btns = [
            ("System info", self.pc_info),
            ("Screenshot", self.pc_shot),
            ("List files (cwd)", self.pc_ls),
            ("Open app / file…", self.pc_open),
        ]
        for i, (t, cmd) in enumerate(btns):
            ctk.CTkButton(f, text=t, fg_color="#16203a", border_color=ACCENT,
                          border_width=1, height=40, command=cmd).grid(
                          row=1 + i // 2, column=i % 2, sticky="we", padx=4, pady=4)
        ctk.CTkLabel(f, text="Run shell command:", font=("Segoe UI", 12)).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.cmd_entry = ctk.CTkEntry(f, placeholder_text="e.g.  dir  /  ipconfig  /  notepad",
                                       height=40)
        self.cmd_entry.grid(row=4, column=0, columnspan=2, sticky="we")
        ctk.CTkButton(f, text="Run (with confirm)", fg_color=ACCENT, height=38,
                      command=self.pc_run).grid(row=5, column=0, columnspan=2,
                                                sticky="we", pady=8)
        self.pc_out = ctk.CTkTextbox(f, font=("Consolas", 12), wrap="word", height=280)
        self.pc_out.grid(row=6, column=0, columnspan=2, sticky="nswe")
        f.grid_rowconfigure(6, weight=1)

    def _pc_print(self, t):
        self.pc_out.insert("end", t + "\n\n")
        self.pc_out.see("end")

    def pc_info(self):
        self._pc_print(json.dumps(pctools.pc_info(), indent=2))

    def pc_shot(self):
        msg = pctools.screenshot()
        self._pc_print(msg)
        if msg.startswith("Saved"):
            if messagebox.askyesno("Screenshot", "Open the screenshot?"):
                pctools.app_launch(msg.split("Saved ")[1].split(" (")[0])

    def pc_ls(self):
        self._pc_print(pctools.file_list("."))

    def pc_open(self):
        p = filedialog.askopenfilename() or tk.simpledialog.askstring("Open", "App or path (e.g. notepad, calc):")
        if p and messagebox.askyesno("Confirm", f"Launch?\n{p}"):
            self._pc_print(pctools.app_launch(p))

    def pc_run(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        if not messagebox.askyesno("Confirm shell", f"Run?\n\n{cmd}"):
            return
        self._pc_print(f"$ {cmd}\n" + pctools.shell_run(cmd))

    # ---------- settings ----------
    def _build_settings(self, f):
        s = self.settings
        ctk.CTkLabel(f, text="Model backend", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(4, 6))
        self.mode_var = ctk.StringVar(value=s.get("mode", "free"))
        ctk.CTkRadioButton(f, text="FREE — Pollinations, no key (default)",
                           variable=self.mode_var, value="free").pack(anchor="w", pady=3)
        ctk.CTkRadioButton(f, text="CUSTOM — any OpenAI-compatible (OpenRouter / OpenCode Zen → muse-spark-1.3)",
                           variable=self.mode_var, value="custom").pack(anchor="w", pady=3)
        self.key_e = ctk.CTkEntry(f, placeholder_text="API key (only for Custom)", show="•")
        self.key_e.pack(fill="x", pady=6)
        self.key_e.insert(0, s.get("api_key", ""))
        self.url_e = ctk.CTkEntry(f, placeholder_text="Base URL")
        self.url_e.pack(fill="x", pady=6)
        self.url_e.insert(0, s.get("base_url", DEFAULTS["base_url"]))
        self.model_e = ctk.CTkEntry(f, placeholder_text="Model id")
        self.model_e.pack(fill="x", pady=6)
        self.model_e.insert(0, s.get("model", DEFAULTS["model"]))
        ctk.CTkButton(f, text="Save", fg_color=ACCENT, command=self.save_cfg).pack(anchor="w", pady=10)
        ctk.CTkLabel(f, justify="left", text_color="#8b93b8", font=("Segoe UI", 11), text=(
            "FREE mode: no signup, rate-limited shared pool — perfect for demo/SaaS trial.\n"
            "For true Muse Spark 1.3:\n"
            " 1) Get a key from OpenRouter or OpenCode Zen (free tier includes muse-spark-1.3)\n"
            " 2) Base URL: https://openrouter.ai/api/v1  (or your OpenCode endpoint)\n"
            " 3) Model: meta/muse-spark-1.3  or  opencode/muse-spark-1.3-contributor-free\n"
            "Honest note: no app can legally bundle unlimited free Claude/Muse — BYOK is the production pattern."
        )).pack(anchor="w", pady=6)

    def save_cfg(self):
        self.settings.update(mode=self.mode_var.get(), api_key=self.key_e.get().strip(),
                             base_url=self.url_e.get().strip(), model=self.model_e.get().strip())
        save_settings(self.settings)
        self.llm = self._make_llm()
        self.set_status(("Custom backend saved" if self.settings["mode"] == "custom" else "Free mode active"))
        messagebox.showinfo("Settings", "Saved.")

if __name__ == "__main__":
    import tkinter.simpledialog  # noqa
    App().mainloop()
