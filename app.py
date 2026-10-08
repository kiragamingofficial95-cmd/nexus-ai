"""Nexus AI — Claude-style Windows desktop assistant (free-first + Zen BYOK).
Run:  pip install -r requirements.txt && python app.py
Build exe: build_exe.bat (PyInstaller --onefile --windowed)
"""
import json, threading, tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
import datetime

import customtkinter as ctk

from core.llm import LLMClient
from core.webtools import web_fetch, extract_urls
from core.agent import run_scan_task
from core import pctools

SETTINGS_FILE = Path("settings.json")
HISTORY_FILE = Path("history.json")

DEFAULTS = {
    "mode": "free",
    "api_key": "",
    "base_url": "https://opencode.ai/zen/v1",
    "model": "muse-spark-1.3-contributor-free",
    "theme": "light",
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

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ---- Claude palette ----
SIDEBAR = "#ECE8DC"
BG = "#F4F1E9"
CARD = "#FFFFFF"
INK = "#1F1E1D"
MUTED = "#6F6A61"
LINE = "#E0DACA"
ACCENT = "#C15F3C"      # Claude orange
USER_BUBBLE = "#E9E3D3"
SERIF = ("Georgia", 14)
UI_FONT = ("Segoe UI", 13)

WELCOME = ("Hello — I'm Nexus AI, your Claude-class assistant.\n\n"
"I can:\n• Chat + reason (free, no key)\n"
"• Scan websites: paste 1-8 URLs + task, e.g. 'Scan these sites and compare pricing, create summary of observations'\n"
"• Control your PC: screenshot, files, launch apps, run commands (with confirmation)\n"
"• Internal browsing: Browser page, fetch any page\n\nAgent mode is ON — just type your task.")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.llm = self._make_llm()
        self.sessions = self._load_sessions()
        self.current = self.sessions[0]
        self.title("Nexus AI — Claude-class Assistant")
        self.geometry("1280x820")
        self.minsize(1020, 700)
        self.configure(fg_color=BG)
        self._build()

    # ---------- state ----------
    def _make_llm(self):
        s = self.settings
        return LLMClient(mode=s.get("mode", "free"), api_key=s.get("api_key", ""),
                         base_url=s.get("base_url", ""), model=s.get("model", ""))

    def _load_sessions(self):
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text())
                if isinstance(data, list) and data and "messages" in data[0]:
                    return data
                # migrate flat history
                if isinstance(data, list) and data and "role" in data[0]:
                    return [{"id": "s1", "title": "Free SaaS browser control app",
                             "messages": data[-50:]}]
        except Exception:
            pass
        return [{"id": "s1", "title": "Free SaaS browser control app", "messages": []}]

    def _persist(self):
        try:
            HISTORY_FILE.write_text(json.dumps(self.sessions[-20:], indent=2))
        except Exception:
            pass

    # ---------- layout (Claude look) ----------
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nswe")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        self._topbar(main)
        body = ctk.CTkFrame(main, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nswe")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for name in ("chat", "browser", "pc", "settings"):
            f = ctk.CTkFrame(body, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nswe")
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure(0, weight=1)
            self.pages[name] = f
        self._build_chat(self.pages["chat"])
        self._build_browser(self.pages["browser"])
        self._build_pc(self.pages["pc"])
        self._build_settings(self.pages["settings"])
        self.show_page("chat")
        self._render_all()

    def _sidebar(self):
        side = ctk.CTkFrame(self, width=264, fg_color=SIDEBAR, corner_radius=0)
        side.grid(row=0, column=0, sticky="nswe")
        side.grid_propagate(False)
        side.grid_rowconfigure(5, weight=1)

        top = ctk.CTkFrame(side, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(12, 4))
        ctk.CTkLabel(top, text="✕", font=("Segoe UI", 13), text_color=MUTED).pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Claude", font=("Segoe UI", 20, "bold"), text_color=INK).pack(side="left", padx=6)

        nav = ctk.CTkFrame(side, fg_color="transparent")
        nav.pack(fill="x", padx=8)
        for icon, name, page in [("＋", "New", None), ("🗂", "Projects", "browser"),
                                ("♣", "Artifacts", "pc"), ("▤", "Customize", "settings")]:
            b = ctk.CTkButton(nav, text=f"{icon}  {name}", anchor="w", height=34,
                              fg_color="transparent", hover_color="#DCD6C4",
                              text_color=INK, font=("Segoe UI", 13),
                              command=(self.new_chat if page is None else lambda p=page: self.show_page(p)))
            b.pack(fill="x", pady=1)
        self.agent_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(nav, text="Agent mode", variable=self.agent_var,
                      font=("Segoe UI", 12), text_color=MUTED).pack(anchor="w", padx=8, pady=6)

        ctk.CTkLabel(side, text="Pinned", font=("Segoe UI", 12), text_color=MUTED).pack(anchor="w", padx=16, pady=(6, 2))
        ctk.CTkLabel(side, text="◉  Bitcoin wins vs Solana losses analy…", font=("Segoe UI", 12),
                     text_color=INK).pack(anchor="w", padx=16, pady=2)

        hdr = ctk.CTkFrame(side, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(10, 2))
        ctk.CTkLabel(hdr, text="Today", font=("Segoe UI", 12), text_color=MUTED).pack(side="left")
        ctk.CTkLabel(hdr, text="🔍  ⚙", font=("Segoe UI", 12), text_color=MUTED).pack(side="right")
        self.hist_frame = ctk.CTkScrollableFrame(side, fg_color="transparent", height=280)
        self.hist_frame.pack(fill="both", expand=False, padx=8, pady=2)
        ctk.CTkLabel(side, text="Oct 6", font=("Segoe UI", 12), text_color=MUTED).pack(anchor="w", padx=16, pady=(8, 2))
        ctk.CTkLabel(side, text="Evaluating service industry niches", font=("Segoe UI", 12),
                     text_color=INK, wraplength=220, justify="left").pack(anchor="w", padx=16)
        ctk.CTkLabel(side, text="Oct 3", font=("Segoe UI", 12), text_color=MUTED).pack(anchor="w", padx=16, pady=(8, 2))
        ctk.CTkLabel(side, text="Untitled\nScaling Pixel Labs with systems and inf…", font=("Segoe UI", 12),
                     text_color=INK, justify="left").pack(anchor="w", padx=16)

        bot = ctk.CTkFrame(side, fg_color="transparent")
        bot.pack(side="bottom", fill="x", padx=12, pady=12)
        ctk.CTkButton(bot, text="Export report (.md)", fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1, height=34,
                      command=self.export_md).pack(fill="x", pady=4)
        row = ctk.CTkFrame(bot, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="Ⓚ", font=("Segoe UI", 14, "bold"), text_color=INK,
                     fg_color="#D8D2BE", corner_radius=12, width=28, height=28).pack(side="left")
        ctk.CTkLabel(row, text="Kira · Free  ⌄", font=("Segoe UI", 12), text_color=INK).pack(side="left", padx=8)

    def _topbar(self, main):
        bar = ctk.CTkFrame(main, fg_color=BG, height=52, corner_radius=0)
        bar.grid(row=0, column=0, sticky="we")
        bar.grid_columnconfigure(1, weight=1)
        self.title_label = ctk.CTkLabel(bar, text="Free SaaS browser control app  ⌄",
                                        font=("Segoe UI", 13), text_color=INK)
        self.title_label.grid(row=0, column=0, padx=18, pady=10, sticky="w")
        pill = ctk.CTkFrame(bar, fg_color="#E9E2D2", corner_radius=16)
        pill.grid(row=0, column=1, pady=10)
        ctk.CTkLabel(pill, text="Free plan · ", font=("Segoe UI", 12), text_color=MUTED).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(pill, text="Upgrade", font=("Segoe UI", 12, "underline"), text_color="#2B5CE6").pack(side="left")
        ctk.CTkLabel(pill, text="  ✕", font=("Segoe UI", 12), text_color=MUTED).pack(side="left", padx=(0, 12))
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, padx=14)
        ctk.CTkButton(right, text="⧉", width=32, fg_color="transparent", text_color=INK,
                      hover_color="#E7E1D1", command=self.export_md).pack(side="left")
        ctk.CTkButton(right, text="Share", width=70, height=30, fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1, command=self.export_md).pack(side="left", padx=4)
        self.status = ctk.CTkLabel(bar, text="", font=("Segoe UI", 11), text_color=MUTED)
        self.status.grid(row=1, column=0, columnspan=3, sticky="w", padx=18)

    def show_page(self, name):
        self.pages[name].tkraise()
        if name == "chat":
            self.title_label.configure(text=f"{self.current['title']}  ⌄")

    # ---------- chat page ----------
    def _build_chat(self, f):
        f.grid_rowconfigure(0, weight=1)
        self.chat_scroll = ctk.CTkScrollableFrame(f, fg_color=BG)
        self.chat_scroll.grid(row=0, column=0, sticky="nswe")
        self.chat_col = ctk.CTkFrame(self.chat_scroll, fg_color="transparent", width=760)
        self.chat_col.pack(padx=40, pady=10)
        bottom = ctk.CTkFrame(f, fg_color=BG)
        bottom.grid(row=1, column=0, sticky="we")
        box = ctk.CTkFrame(bottom, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=18)
        box.pack(fill="x", padx=120, pady=(6, 2))
        box.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(box, placeholder_text="Reply", height=44, border_width=0,
                                  fg_color="transparent", font=UI_FONT, text_color=INK)
        self.entry.grid(row=0, column=0, sticky="we", padx=14)
        self.entry.bind("<Return>", lambda e: self.send())
        ctk.CTkButton(box, text="↵", width=36, height=32, fg_color="#EFE9D8", text_color=INK,
                      hover_color="#E2DAC4", command=self.send).grid(row=0, column=1, padx=8)
        sub = ctk.CTkFrame(bottom, fg_color="transparent")
        sub.pack(fill="x", padx=120, pady=(0, 8))
        ctk.CTkLabel(sub, text="＋   🎙  ⌄", font=("Segoe UI", 13), text_color=MUTED).pack(side="left")
        ctk.CTkLabel(sub, text="Nexus is AI and can make mistakes.", font=("Segoe UI", 11),
                     text_color=MUTED).pack(side="left", expand=True)
        model = (self.settings.get("model") or "")[:28]
        ctk.CTkLabel(sub, text=f"{model}   High   Manual", font=("Segoe UI", 11),
                     text_color=INK).pack(side="right")

    def _bubble(self, role, text):
        if role == "user":
            wrap = ctk.CTkFrame(self.chat_col, fg_color="transparent")
            wrap.pack(fill="x", pady=8)
            b = ctk.CTkFrame(wrap, fg_color=USER_BUBBLE, corner_radius=14)
            b.pack(side="right", padx=4)
            ctk.CTkLabel(b, text=text, font=UI_FONT, text_color=INK, wraplength=560,
                         justify="left").pack(padx=14, pady=10)
        else:
            wrap = ctk.CTkFrame(self.chat_col, fg_color="transparent")
            wrap.pack(fill="x", pady=8)
            ctk.CTkLabel(wrap, text=text, font=SERIF, text_color=INK, wraplength=700,
                         justify="left").pack(anchor="w", padx=4)
            acts = ctk.CTkFrame(wrap, fg_color="transparent")
            acts.pack(anchor="w", padx=2, pady=(4, 0))
            for icon, fn in [("⧉", lambda t=text: self._copy(t)),
                             ("🔊", lambda: None),
                             ("♡", lambda: None),
                             ("♢", lambda: None),
                             ("↻", lambda t=text: self.retry(t))]:
                ctk.CTkButton(acts, text=icon, width=28, height=24, fg_color="transparent",
                              text_color=MUTED, hover_color="#E7E1D1", command=fn).pack(side="left")
        try:
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _copy(self, t):
        try:
            self.clipboard_clear(); self.clipboard_append(t)
        except Exception:
            pass

    def retry(self, _t=None):
        msgs = self.current["messages"]
        if msgs and msgs[-1]["role"] == "assistant":
            msgs.pop()
            self._render_all()
        if msgs and msgs[-1]["role"] == "user":
            self.set_status("Thinking…")
            import threading as th
            th.Thread(target=self._answer, args=(msgs[-1]["content"],), daemon=True).start()

    def _render_all(self):
        for w in self.chat_col.winfo_children():
            w.destroy()
        msgs = self.current["messages"]
        if not msgs:
            self._bubble("assistant", WELCOME)
        for m in msgs[-30:]:
            self._bubble(m["role"], m["content"])
        self.title_label.configure(text=f"{self.current['title']}  ⌄")
        self._render_hist_list()

    def _render_hist_list(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()
        for s in reversed(self.sessions[-8:]):
            b = ctk.CTkButton(self.hist_frame, text=s["title"][:34], anchor="w", height=30,
                              fg_color="#DCD6C4" if s is self.current else "transparent",
                              hover_color="#DCD6C4", text_color=INK, font=("Segoe UI", 12),
                              command=lambda ss=s: self.switch(ss))
            b.pack(fill="x", pady=1)

    def switch(self, s):
        self.current = s
        self.show_page("chat")
        self._render_all()

    def set_status(self, t):
        self.status.configure(text=t)
        self.update_idletasks()

    def new_chat(self):
        s = {"id": f"s{len(self.sessions)+1}", "title": "Untitled",
             "created": datetime.date.today().isoformat(), "messages": []}
        self.sessions.append(s)
        self.current = s
        self.show_page("chat")
        self._render_all()

    def export_md(self):
        msgs = self.current["messages"]
        if not msgs:
            return messagebox.showinfo("Export", "Nothing to export yet.")
        p = filedialog.asksaveasfilename(defaultextension=".md",
            filetypes=[("Markdown", "*.md")], initialfile="nexus-report.md")
        if not p:
            return
        md = f"# {self.current['title']}\n\n" + "\n\n---\n\n".join(
            f"**{'Nexus' if m['role']=='assistant' else 'You'}:**\n\n{m['content']}" for m in msgs)
        Path(p).write_text(md, encoding="utf-8")
        messagebox.showinfo("Export", f"Saved to {p}")

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        if self.current["title"] in ("Untitled", "Free SaaS browser control app") and len(self.current["messages"]) == 0:
            self.current["title"] = text[:42]
        self.current["messages"].append({"role": "user", "content": text})
        self._bubble("user", text)
        self._render_hist_list()
        self.title_label.configure(text=f"{self.current['title']}  ⌄")
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
                final = f"_Fetched {ok}/{len(pages)} site(s) live._\n\n" + report
            else:
                msgs = [{"role": m["role"], "content": m["content"]}
                        for m in self.current["messages"][-12:]]
                final = self.llm.chat(msgs)
            self.current["messages"].append({"role": "assistant", "content": final})
            self._persist()
            self.after(0, lambda: (self._bubble("assistant", final), self.set_status("")))
        except Exception as e:
            err = (f"Request failed: {e}\n\nTip: Settings → Use Zen Free → paste oc_sk key, Save. "
                   "Free pool needs internet and is rate-limited.")
            self.after(0, lambda: (self._bubble("assistant", err), self.set_status("Error")))

    # ---------- browser ----------
    def _build_browser(self, f):
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=0, column=0, sticky="we", pady=(6, 8), padx=40)
        top.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(top, placeholder_text="https://…", height=40,
                                      fg_color=CARD, border_color=LINE, text_color=INK)
        self.url_entry.grid(row=0, column=0, sticky="we", padx=(0, 8))
        ctk.CTkButton(top, text="Fetch", width=100, fg_color=ACCENT, hover_color="#A94E2E",
                       command=self.browser_fetch).grid(row=0, column=1)
        self.browser_box = ctk.CTkTextbox(f, font=("Segoe UI", 13), wrap="word",
                                           fg_color=CARD, border_color=LINE, border_width=1, text_color=INK)
        self.browser_box.grid(row=1, column=0, sticky="nswe", padx=40, pady=(0, 16))
        self.browser_box.insert("1.0", "Internal browser — enter a URL above and press Fetch.")

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
                     font=("Segoe UI", 13, "bold"), text_color=MUTED).grid(
                     row=0, column=0, columnspan=2, sticky="w", padx=40, pady=(6, 8))
        btns = [("System info", self.pc_info), ("Screenshot", self.pc_shot),
                ("List files (cwd)", self.pc_ls), ("Open app / file…", self.pc_open)]
        for i, (t, cmd) in enumerate(btns):
            ctk.CTkButton(f, text=t, fg_color=CARD, text_color=INK, border_color=LINE,
                          border_width=1, height=40, command=cmd).grid(
                          row=1 + i // 2, column=i % 2, sticky="we", padx=(40 if i % 2 == 0 else 4, 40 if i % 2 else 4), pady=4)
        ctk.CTkLabel(f, text="Run shell command:", font=("Segoe UI", 12),
                     text_color=INK).grid(row=3, column=0, columnspan=2, sticky="w", padx=40, pady=(10, 2))
        self.cmd_entry = ctk.CTkEntry(f, placeholder_text="e.g.  dir  /  ipconfig  /  notepad",
                                       height=40, fg_color=CARD, border_color=LINE, text_color=INK)
        self.cmd_entry.grid(row=4, column=0, columnspan=2, sticky="we", padx=40)
        ctk.CTkButton(f, text="Run (with confirm)", fg_color=ACCENT, hover_color="#A94E2E",
                      height=38, command=self.pc_run).grid(row=5, column=0, columnspan=2,
                      sticky="we", padx=40, pady=8)
        self.pc_out = ctk.CTkTextbox(f, font=("Consolas", 12), wrap="word", height=280,
                                      fg_color=CARD, border_color=LINE, border_width=1, text_color=INK)
        self.pc_out.grid(row=6, column=0, columnspan=2, sticky="nswe", padx=40, pady=(0, 16))
        f.grid_rowconfigure(6, weight=1)

    def _pc_print(self, t):
        self.pc_out.insert("end", t + "\n\n")
        self.pc_out.see("end")

    def pc_info(self):
        import json as j
        self._pc_print(j.dumps(pctools.pc_info(), indent=2))

    def pc_shot(self):
        msg = pctools.screenshot()
        self._pc_print(msg)
        if msg.startswith("Saved") and messagebox.askyesno("Screenshot", "Open the screenshot?"):
            pctools.app_launch(msg.split("Saved ")[1].split(" (")[0])

    def pc_ls(self):
        self._pc_print(pctools.file_list("."))

    def pc_open(self):
        import tkinter.simpledialog as sd
        p = filedialog.askopenfilename() or sd.askstring("Open", "App or path (e.g. notepad, calc):")
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
        wrap = ctk.CTkScrollableFrame(f, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nswe", padx=40, pady=10)
        ctk.CTkLabel(wrap, text="Customize — Model backend", font=("Segoe UI", 15, "bold"),
                     text_color=INK).pack(anchor="w", pady=(4, 6))
        self.mode_var = ctk.StringVar(value=s.get("mode", "free"))
        ctk.CTkRadioButton(wrap, text="FREE — Pollinations, no key (default)",
                           variable=self.mode_var, value="free", text_color=INK).pack(anchor="w", pady=3)
        ctk.CTkRadioButton(wrap, text="CUSTOM — OpenCode Zen / OpenRouter (muse-spark-1.3)",
                           variable=self.mode_var, value="custom", text_color=INK).pack(anchor="w", pady=3)
        self.key_e = ctk.CTkEntry(wrap, placeholder_text="API key oc_sk_... (Custom only)", show="•",
                                  fg_color=CARD, border_color=LINE, text_color=INK)
        self.key_e.pack(fill="x", pady=6)
        self.key_e.insert(0, s.get("api_key", ""))
        self.url_e = ctk.CTkEntry(wrap, placeholder_text="Base URL", fg_color=CARD,
                                  border_color=LINE, text_color=INK)
        self.url_e.pack(fill="x", pady=6)
        self.url_e.insert(0, s.get("base_url", DEFAULTS["base_url"]))
        self.model_e = ctk.CTkEntry(wrap, placeholder_text="Model id", fg_color=CARD,
                                    border_color=LINE, text_color=INK)
        self.model_e.pack(fill="x", pady=6)
        self.model_e.insert(0, s.get("model", DEFAULTS["model"]))
        presets = ctk.CTkFrame(wrap, fg_color="transparent")
        presets.pack(fill="x", pady=4)
        ctk.CTkButton(presets, text="Use Zen Free", width=130, fg_color=CARD, text_color=INK,
                      border_color=ACCENT, border_width=1,
                      command=self.preset_zen).pack(side="left", padx=(0, 6))
        ctk.CTkButton(presets, text="Use OpenRouter", width=130, fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1,
                      command=self.preset_router).pack(side="left")
        ctk.CTkButton(wrap, text="Save", fg_color=ACCENT, hover_color="#A94E2E",
                      command=self.save_cfg).pack(anchor="w", pady=10)
        ctk.CTkLabel(wrap, justify="left", text_color=MUTED, font=("Segoe UI", 11), text=(
            "Zen: Base https://opencode.ai/zen/v1   Model muse-spark-1.3-contributor-free\n"
            "Paste your oc_sk key from https://opencode.ai/auth → Save.\n"
            "Key stays in local settings.json only (gitignored) — never commit or bake into a public exe."
        )).pack(anchor="w", pady=6)

    def preset_zen(self):
        self.mode_var.set("custom")
        self.url_e.delete(0, "end"); self.url_e.insert(0, "https://opencode.ai/zen/v1")
        self.model_e.delete(0, "end"); self.model_e.insert(0, "muse-spark-1.3-contributor-free")

    def preset_router(self):
        self.mode_var.set("custom")
        self.url_e.delete(0, "end"); self.url_e.insert(0, "https://openrouter.ai/api/v1")
        self.model_e.delete(0, "end"); self.model_e.insert(0, "meta/muse-spark-1.3")

    def save_cfg(self):
        self.settings.update(mode=self.mode_var.get(), api_key=self.key_e.get().strip(),
                             base_url=self.url_e.get().strip(), model=self.model_e.get().strip())
        save_settings(self.settings)
        self.llm = self._make_llm()
        messagebox.showinfo("Settings", "Saved.")

if __name__ == "__main__":
    App().mainloop()
