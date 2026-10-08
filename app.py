"""Nexus AI v1.0.4 — premium Claude-style desktop assistant (free-first + Zen BYOK)."""
import json, re, threading, time
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
DIAG_FILE = Path("last_error.txt")

DEFAULTS = {"mode": "free", "api_key": "", "base_url": "https://opencode.ai/zen/v1",
            "model": "muse-spark-1.3", "theme": "light"}

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

SIDEBAR = "#EAE6D9"
BG = "#F6F3EB"
CARD = "#FFFFFF"
INK = "#201F1E"
MUTED = "#75705F"
LINE = "#DED8C6"
ACCENT = "#C15F3C"
ACCENT_H = "#A94E2E"
USER_BUBBLE = "#EAE3D2"
GREEN = "#1F9D55"

WELCOME = ("Hello — I'm Nexus AI.\n\nI can chat, **scan websites into structured reports**, "
"browse internally, and control your PC safely.\n\nTry: `Scan https://example.com and summarize observations`.\nAgent mode is ON.")

def md_plain(t):
    t = re.sub(r"```.*?```", lambda m: "\n" + m.group(0).replace("```", "") + "\n", t, flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    return t


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.llm = self._make_llm()
        self.sessions = self._load_sessions()
        self.current = self.sessions[0]
        self.thinking = None
        self.title("Nexus AI — Claude-class Assistant")
        self.geometry("1320x860")
        self.minsize(1060, 720)
        self.configure(fg_color=BG)
        self._build()

    def _make_llm(self):
        s = self.settings
        return LLMClient(mode=s.get("mode", "free"), api_key=s.get("api_key", ""),
                         base_url=s.get("base_url", ""), model=s.get("model", ""))

    def _load_sessions(self):
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text())
                if data and isinstance(data[0], dict) and "messages" in data[0]:
                    return data
                if data and "role" in data[0]:
                    return [{"id": "s1", "title": "Free SaaS browser control app", "messages": data[-50:]}]
        except Exception:
            pass
        return [{"id": "s1", "title": "Free SaaS browser control app", "messages": []}]

    def _persist(self):
        try:
            HISTORY_FILE.write_text(json.dumps(self.sessions[-20:], indent=2))
        except Exception:
            pass

    # ================= shell =================
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
        side = ctk.CTkFrame(self, width=276, fg_color=SIDEBAR, corner_radius=0)
        side.grid(row=0, column=0, sticky="nswe")
        side.grid_propagate(False)
        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(14, 6))
        ctk.CTkLabel(head, text="✦", font=("Segoe UI", 18, "bold"), text_color=ACCENT,
                     fg_color="#DCD4BD", corner_radius=14, width=32, height=32).pack(side="left")
        ctk.CTkLabel(head, text="Nexus", font=("Georgia", 21, "bold"), text_color=INK).pack(side="left", padx=8)
        ctk.CTkLabel(head, text="Claude-class", font=("Segoe UI", 10), text_color=MUTED).pack(side="left")

        self.search_e = ctk.CTkEntry(side, placeholder_text="Search chats…", height=34,
                                     fg_color=CARD, border_color=LINE, text_color=INK)
        self.search_e.pack(fill="x", padx=12, pady=4)
        self.search_e.bind("<KeyRelease>", lambda e: self._render_hist_list())

        nav = ctk.CTkFrame(side, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=4)
        self.nav_btns = {}
        for icon, name, page in [("＋", "New chat", None), ("◈", "Browser", "browser"),
                                ("❖", "PC Control", "pc"), ("⚙", "Customize", "settings"),
                                ("💬", "Chat", "chat")]:
            b = ctk.CTkButton(nav, text=f"{icon}   {name}", anchor="w", height=36,
                              fg_color="transparent", hover_color="#D8D2BE",
                              text_color=INK, font=("Segoe UI", 13, "bold"),
                              command=(self.new_chat if page is None else lambda p=page: self.show_page(p)))
            b.pack(fill="x", pady=1)
            self.nav_btns[name] = b
        self.agent_var = ctk.BooleanVar(value=True)
        row = ctk.CTkFrame(side, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=12)
        row.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row, text="Agent mode", font=("Segoe UI", 12, "bold"), text_color=INK).pack(side="left", padx=12, pady=8)
        ctk.CTkSwitch(row, text="", variable=self.agent_var).pack(side="right", padx=12)

        ctk.CTkLabel(side, text="TODAY", font=("Segoe UI", 10, "bold"), text_color=MUTED).pack(anchor="w", padx=16, pady=(6, 2))
        self.hist_frame = ctk.CTkScrollableFrame(side, fg_color="transparent", height=300)
        self.hist_frame.pack(fill="both", expand=False, padx=6)
        bot = ctk.CTkFrame(side, fg_color="transparent")
        bot.pack(side="bottom", fill="x", padx=12, pady=12)
        ctk.CTkButton(bot, text="⤓  Export report (.md)", fg_color=INK, hover_color="#333",
                      text_color="white", height=36, command=self.export_md).pack(fill="x", pady=4)
        me = ctk.CTkFrame(bot, fg_color="transparent")
        me.pack(fill="x", pady=4)
        ctk.CTkLabel(me, text="K", font=("Segoe UI", 13, "bold"), text_color="white",
                     fg_color="#5B4DBC", corner_radius=14, width=30, height=30).pack(side="left")
        ctk.CTkLabel(me, text="Kira · Free", font=("Segoe UI", 12, "bold"), text_color=INK).pack(side="left", padx=8)
        dot = "🟢" if self.settings.get("mode") == "custom" and self.settings.get("api_key") else "⚪"
        ctk.CTkLabel(me, text=f"{dot} {self.settings.get('model','')[:22]}", font=("Segoe UI", 10),
                     text_color=MUTED).pack(side="left")

    def _topbar(self, main):
        bar = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        bar.grid(row=0, column=0, sticky="we")
        bar.grid_columnconfigure(1, weight=1)
        self.title_label = ctk.CTkLabel(bar, text="Free SaaS browser control app  ⌄",
                                        font=("Georgia", 14, "bold"), text_color=INK)
        self.title_label.grid(row=0, column=0, padx=20, pady=(12, 0), sticky="w")
        pill = ctk.CTkFrame(bar, fg_color="#E7DFC9", corner_radius=16)
        pill.grid(row=0, column=1, pady=(12, 0))
        ctk.CTkLabel(pill, text="Free plan · ", font=("Segoe UI", 12), text_color=MUTED).pack(side="left", padx=(14, 0), pady=6)
        ctk.CTkButton(pill, text="Upgrade", font=("Segoe UI", 12, "bold"), fg_color="transparent",
                      text_color="#2B5CE6", hover_color="#D8D0B6", width=60,
                      command=lambda: self.show_page("settings")).pack(side="left", pady=2)
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, padx=16, pady=(12, 0))
        self.conn_dot = ctk.CTkLabel(right, text="●", font=("Segoe UI", 12),
                                     text_color=GREEN if self.settings.get("api_key") else MUTED)
        self.conn_dot.pack(side="left", padx=4)
        ctk.CTkButton(right, text="Share", width=76, height=32, fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1, command=self.export_md).pack(side="left")
        self.status = ctk.CTkLabel(bar, text="", font=("Segoe UI", 11), text_color=MUTED)
        self.status.grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 4))
        ctk.CTkFrame(bar, fg_color=LINE, height=1).grid(row=2, column=0, columnspan=3, sticky="we", padx=20)

    def show_page(self, name):
        self.pages[name].tkraise()
        for k, b in self.nav_btns.items():
            on = ((name == "chat" and k == "Chat") or (name == "browser" and k == "Browser") or
                  (name == "pc" and k == "PC Control") or (name == "settings" and k == "Customize"))
            b.configure(fg_color="#D8D2BE" if on else "transparent")
        if name == "chat":
            self.title_label.configure(text=f"{self.current['title']}  ⌄")

    # ================= chat =================
    def _build_chat(self, f):
        f.grid_rowconfigure(0, weight=1)
        self.chat_scroll = ctk.CTkScrollableFrame(f, fg_color=BG)
        self.chat_scroll.grid(row=0, column=0, sticky="nswe")
        self.chat_col = ctk.CTkFrame(self.chat_scroll, fg_color="transparent", width=780)
        self.chat_col.pack(padx=30, pady=12)
        bottom = ctk.CTkFrame(f, fg_color=BG)
        bottom.grid(row=1, column=0, sticky="we")
        box = ctk.CTkFrame(bottom, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=20)
        box.pack(fill="x", padx=130, pady=(8, 2))
        box.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(box, placeholder_text="Reply — ask, paste URLs to scan, or type /help",
                                  height=48, border_width=0, fg_color="transparent",
                                  font=("Segoe UI", 13), text_color=INK)
        self.entry.grid(row=0, column=0, sticky="we", padx=16)
        self.entry.bind("<Return>", lambda e: self.send())
        self.send_btn = ctk.CTkButton(box, text="↑", width=38, height=38, corner_radius=19,
                                      fg_color=ACCENT, hover_color=ACCENT_H, text_color="white",
                                      font=("Segoe UI", 16, "bold"), command=self.send)
        self.send_btn.grid(row=0, column=1, padx=8, pady=5)
        sub = ctk.CTkFrame(bottom, fg_color="transparent")
        sub.pack(fill="x", padx=130, pady=(0, 10))
        ctk.CTkLabel(sub, text="＋     🎙", font=("Segoe UI", 14), text_color=MUTED).pack(side="left")
        ctk.CTkLabel(sub, text="Nexus is AI and can make mistakes.", font=("Segoe UI", 11),
                     text_color=MUTED).pack(side="left", expand=True)
        self.model_label = ctk.CTkLabel(sub, text=f"{self.settings.get('model','')[:30]} · High · Manual",
                                        font=("Segoe UI", 11, "bold"), text_color=INK)
        self.model_label.pack(side="right")

    def _msg_card(self, role, text):
        if role == "user":
            wrap = ctk.CTkFrame(self.chat_col, fg_color="transparent")
            wrap.pack(fill="x", pady=8)
            me = ctk.CTkFrame(wrap, fg_color="transparent")
            me.pack(anchor="e", padx=4)
            ctk.CTkLabel(me, text="You", font=("Segoe UI", 11, "bold"), text_color=MUTED).pack(side="right", padx=8)
            ctk.CTkLabel(me, text="K", font=("Segoe UI", 10, "bold"), text_color="white",
                         fg_color="#5B4DBC", corner_radius=11, width=24, height=24).pack(side="right")
            b = ctk.CTkFrame(wrap, fg_color=USER_BUBBLE, corner_radius=16)
            b.pack(anchor="e", padx=4, pady=(4, 0))
            ctk.CTkLabel(b, text=md_plain(text), font=("Segoe UI", 13), text_color=INK,
                         wraplength=560, justify="left").pack(padx=16, pady=12)
            return
        card = ctk.CTkFrame(self.chat_col, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=16)
        card.pack(fill="x", pady=8)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(head, text="✦", font=("Segoe UI", 12, "bold"), text_color="white",
                     fg_color=ACCENT, corner_radius=11, width=24, height=24).pack(side="left")
        ctk.CTkLabel(head, text="Nexus", font=("Segoe UI", 12, "bold"), text_color=INK).pack(side="left", padx=8)
        ctk.CTkLabel(head, text=datetime.datetime.now().strftime("%H:%M"), font=("Segoe UI", 10),
                     text_color=MUTED).pack(side="left")
        ctk.CTkLabel(head, text="Muse Spark 1.3", font=("Segoe UI", 10), text_color=MUTED,
                     fg_color="#F0EAD8", corner_radius=8).pack(side="right", padx=4, ipadx=6)
        body = ctk.CTkTextbox(card, wrap="word", font=("Georgia", 14), text_color=INK,
                              fg_color="transparent", activate_scrollbars=False)
        body.pack(fill="x", padx=8, pady=(4, 2))
        body.insert("1.0", md_plain(text))
        h = max(60, min(520, (len(text) // 72 + text.count("\n") + 2) * 23))
        body.configure(height=h, state="disabled")
        acts = ctk.CTkFrame(card, fg_color="transparent")
        acts.pack(anchor="w", padx=10, pady=(0, 10))
        for icon, tip, fn in [("⧉", "Copy", lambda t=text: self._copy(t)),
                              ("↻", "Retry", lambda: self.retry()),
                              ("👍", "Good", lambda: self.set_status("Thanks for the feedback")),
                              ("👎", "Bad", lambda: self.set_status("Noted — try /help for tips"))]:
            ctk.CTkButton(acts, text=icon, width=32, height=26, fg_color="transparent",
                          text_color=MUTED, hover_color="#F0EAD8", command=fn).pack(side="left", padx=1)
        try:
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _copy(self, t):
        try:
            self.clipboard_clear(); self.clipboard_append(t); self.set_status("Copied")
        except Exception:
            pass

    def _thinking_on(self):
        self._thinking_off()
        self.thinking = ctk.CTkLabel(self.chat_col, text="✦  Thinking ●●●",
                                     font=("Segoe UI", 12, "bold"), text_color=ACCENT)
        self.thinking.pack(anchor="w", padx=6, pady=6)
        self._pulse()

    def _pulse(self):
        if self.thinking is None or not self.thinking.winfo_exists():
            return
        txt = self.thinking.cget("text")
        dots = (txt.count("●") % 3) + 1
        self.thinking.configure(text="✦  Thinking " + "●" * dots)
        self.after(450, self._pulse)

    def _thinking_off(self):
        try:
            if self.thinking is not None and self.thinking.winfo_exists():
                self.thinking.destroy()
        except Exception:
            pass
        self.thinking = None

    def _render_all(self):
        for w in self.chat_col.winfo_children():
            w.destroy()
        msgs = self.current["messages"]
        if not msgs:
            self._msg_card("assistant", WELCOME)
        for m in msgs[-30:]:
            self._msg_card(m["role"], m["content"])
        self.title_label.configure(text=f"{self.current['title']}  ⌄")
        self._render_hist_list()

    def _render_hist_list(self):
        q = (self.search_e.get().strip().lower() if hasattr(self, "search_e") else "")
        for w in self.hist_frame.winfo_children():
            w.destroy()
        items = [s for s in reversed(self.sessions[-12:]) if q in s["title"].lower()]
        for s in items or self.sessions[-1:]:
            active = s is self.current
            b = ctk.CTkButton(self.hist_frame, text=("▍ " if active else "　") + s["title"][:36],
                              anchor="w", height=34, corner_radius=10,
                              fg_color="#D8D2BE" if active else "transparent",
                              hover_color="#D8D2BE", text_color=INK,
                              font=("Segoe UI", 12, "bold" if active else "normal"),
                              command=lambda ss=s: self.switch(ss))
            b.pack(fill="x", pady=1)

    def switch(self, s):
        self.current = s
        self.show_page("chat")
        self._render_all()

    def set_status(self, t):
        self.status.configure(text=t or "")
        self.update_idletasks()

    def new_chat(self):
        s = {"id": f"s{len(self.sessions)+1}", "title": "Untitled", "messages": []}
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
        if text == "/help":
            self.entry.delete(0, "end")
            return self._msg_card("assistant",
                "Commands:\n• Paste 1-8 URLs + task to scan\n• Browser page: fetch any URL\n• PC page: sysinfo / screenshot / shell (confirms)\n• Settings → Test connection to diagnose Zen key")
        self.entry.delete(0, "end")
        if len(self.current["messages"]) == 0:
            self.current["title"] = text[:42]
        self.current["messages"].append({"role": "user", "content": text})
        self._msg_card("user", text)
        self._render_hist_list()
        self.title_label.configure(text=f"{self.current['title']}  ⌄")
        self._thinking_on()
        self.set_status("Thinking…")
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def retry(self):
        msgs = self.current["messages"]
        if msgs and msgs[-1]["role"] == "assistant":
            msgs.pop()
            self._render_all()
        if msgs and msgs[-1]["role"] == "user":
            self._thinking_on()
            threading.Thread(target=self._answer, args=(msgs[-1]["content"],), daemon=True).start()

    def _answer(self, text):
        t0 = time.time()
        try:
            urls = extract_urls(text)
            agent_on = self.agent_var.get()
            looks_like_scan = bool(urls) or any(
                k in text.lower() for k in ["scan", "summar", "compar", "research", "observ", "websites", "sites"])
            if agent_on and looks_like_scan and (urls or len(text) > 30):
                self.set_status("Agent: scanning live websites…")
                try:
                    report, pages = run_scan_task(text, self.llm, progress=self.set_status)
                except Exception as e1:
                    if "FreeTierError" in str(e1):
                        self.set_status("Zen free blocked — scan continues on FREE pool…")
                        from core.llm import LLMClient as _C
                        report, pages = run_scan_task(text, _C(), progress=self.set_status)
                        report = ("_Note: Zen free-tier blocked over API, scan summarized by FREE pool._\n\n" + report)
                    else:
                        raise
                ok = sum(1 for p in pages if not p["error"])
                final = f"_Fetched {ok}/{len(pages)} site(s) live._\n\n" + report
            else:
                msgs = [{"role": m["role"], "content": m["content"]} for m in self.current["messages"][-12:]]
                try:
                    final = self.llm.chat(msgs)
                except Exception as e1:
                    if "FreeTierError" in str(e1):
                        self.set_status("Zen free blocked — falling back to FREE pool…")
                        from core.llm import LLMClient as _C
                        final = ("_Note: Zen free-tier blocked over API (FreeTierError), answered by FREE pool instead. "
                                 "For Muse Spark over API you need credits + model muse-spark-1.3._\n\n" + _C().chat(msgs))
                    else:
                        raise
            self.current["messages"].append({"role": "assistant", "content": final})
            self._persist()
            dt = time.time() - t0
            self.after(0, lambda: (self._thinking_off(), self._msg_card("assistant", final),
                                   self.set_status(f"Done in {dt:.1f}s · {self.settings.get('model','')}")))
        except Exception as e:
            try:
                DIAG_FILE.write_text(str(e)[:2000])
            except Exception:
                pass
            err = (f"Request failed: {e}\n\nFix:\n1) Zen paid needs credits → model muse-spark-1.3\n"
                   "2) No credits? Settings → mode FREE → Save (Pollinations pool, no key)\n"
                   "3) FreeTierError = free model is OpenCode-client-only, not a bug in Nexus.")
            self.after(0, lambda: (self._thinking_off(), self._msg_card("assistant", err),
                                   self.set_status("Error — see Settings → Last error")))

    # ================= browser =================
    def _build_browser(self, f):
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=0, column=0, sticky="we", pady=(10, 8), padx=44)
        top.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(top, placeholder_text="https://…  — internal reader", height=44,
                                      fg_color=CARD, border_color=LINE, text_color=INK, corner_radius=14)
        self.url_entry.grid(row=0, column=0, sticky="we", padx=(0, 8))
        ctk.CTkButton(top, text="Fetch", width=110, height=44, corner_radius=14, fg_color=INK,
                       hover_color="#333", command=self.browser_fetch).grid(row=0, column=1)
        self.browser_box = ctk.CTkTextbox(f, font=("Georgia", 14), wrap="word", fg_color=CARD,
                                          border_color=LINE, border_width=1, text_color=INK, corner_radius=16)
        self.browser_box.grid(row=1, column=0, sticky="nswe", padx=44, pady=(0, 16))
        self.browser_box.insert("1.0", "Internal browser — enter a URL above and press Fetch.\nCleaned reader text, no key needed.")

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
            self.after(0, lambda: (self.browser_box.delete("1.0", "end"), self.browser_box.insert("1.0", txt)))
        threading.Thread(target=work, daemon=True).start()

    # ================= PC =================
    def _build_pc(self, f):
        f.grid_columnconfigure((0, 1), weight=1)
        hdr = ctk.CTkFrame(f, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=16)
        hdr.grid(row=0, column=0, columnspan=2, sticky="we", padx=44, pady=(10, 8))
        ctk.CTkLabel(hdr, text="🖥  PC Control", font=("Segoe UI", 14, "bold"), text_color=INK).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(hdr, text="every shell/launch asks for confirmation", font=("Segoe UI", 11),
                     text_color=MUTED).pack(side="left")
        btns = [("System info", self.pc_info), ("Screenshot", self.pc_shot),
                ("List files", self.pc_ls), ("Open app / file…", self.pc_open)]
        for i, (t, cmd) in enumerate(btns):
            ctk.CTkButton(f, text=t, fg_color=CARD, text_color=INK, border_color=LINE,
                          border_width=1, corner_radius=14, height=46, font=("Segoe UI", 13, "bold"),
                          command=cmd).grid(row=1 + i // 2, column=i % 2, sticky="we",
                          padx=(44 if i % 2 == 0 else 4, 44 if i % 2 else 4), pady=4)
        self.cmd_entry = ctk.CTkEntry(f, placeholder_text="Run shell:  dir  /  ipconfig  /  notepad",
                                       height=44, fg_color=CARD, border_color=LINE, text_color=INK, corner_radius=14)
        self.cmd_entry.grid(row=3, column=0, columnspan=2, sticky="we", padx=44, pady=(8, 4))
        ctk.CTkButton(f, text="▶  Run (with confirm)", fg_color=ACCENT, hover_color=ACCENT_H,
                      height=42, corner_radius=14, command=self.pc_run).grid(
                      row=4, column=0, columnspan=2, sticky="we", padx=44, pady=4)
        self.pc_out = ctk.CTkTextbox(f, font=("Consolas", 12), wrap="word", height=260,
                                      fg_color="#20211F", text_color="#EDE8D8", corner_radius=16)
        self.pc_out.grid(row=5, column=0, columnspan=2, sticky="nswe", padx=44, pady=(4, 16))
        f.grid_rowconfigure(5, weight=1)

    def _pc_print(self, t):
        self.pc_out.insert("end", t + "\n\n")
        self.pc_out.see("end")

    def pc_info(self):
        self._pc_print(json.dumps(pctools.pc_info(), indent=2))

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

    # ================= settings =================
    def _build_settings(self, f):
        wrap = ctk.CTkScrollableFrame(f, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nswe", padx=44, pady=10)
        card = ctk.CTkFrame(wrap, fg_color=CARD, border_color=LINE, border_width=1, corner_radius=16)
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(card, text="Model backend", font=("Georgia", 16, "bold"), text_color=INK).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(card, text="Free pool or your own Zen key. Key never leaves this PC except to your backend.",
                     font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w", padx=18)
        self.mode_var = ctk.StringVar(value=self.settings.get("mode", "free"))
        ctk.CTkRadioButton(card, text="FREE — Pollinations pool, no key", variable=self.mode_var,
                           value="free", text_color=INK).pack(anchor="w", padx=18, pady=3)
        ctk.CTkRadioButton(card, text="CUSTOM — OpenCode Zen / OpenRouter", variable=self.mode_var,
                           value="custom", text_color=INK).pack(anchor="w", padx=18, pady=3)
        self.key_e = ctk.CTkEntry(card, placeholder_text="API key oc_sk_... (Custom only)", show="•",
                                  fg_color=BG, border_color=LINE, text_color=INK, height=40, corner_radius=12)
        self.key_e.pack(fill="x", padx=18, pady=6)
        self.key_e.insert(0, self.settings.get("api_key", ""))
        self.show_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(card, text="Show key", variable=self.show_var,
                      command=self._toggle_key).pack(anchor="w", padx=18)
        self.url_e = ctk.CTkEntry(card, fg_color=BG, border_color=LINE, text_color=INK, height=40, corner_radius=12)
        self.url_e.pack(fill="x", padx=18, pady=6)
        self.url_e.insert(0, self.settings.get("base_url", DEFAULTS["base_url"]))
        self.model_e = ctk.CTkEntry(card, fg_color=BG, border_color=LINE, text_color=INK, height=40, corner_radius=12)
        self.model_e.pack(fill="x", padx=18, pady=6)
        self.model_e.insert(0, self.settings.get("model", DEFAULTS["model"]))
        prow = ctk.CTkFrame(card, fg_color="transparent")
        prow.pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(prow, text="Use Zen Free", width=130, height=36, fg_color=INK, hover_color="#333",
                      command=self.preset_zen).pack(side="left", padx=(0, 6))
        ctk.CTkButton(prow, text="Use OpenRouter", width=130, height=36, fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1, command=self.preset_router).pack(side="left")
        brow = ctk.CTkFrame(card, fg_color="transparent")
        brow.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkButton(brow, text="Save", width=120, height=38, fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self.save_cfg).pack(side="left", padx=(0, 8))
        ctk.CTkButton(brow, text="Test connection", width=150, height=38, fg_color=CARD, text_color=INK,
                      border_color=LINE, border_width=1, command=self.test_conn).pack(side="left")
        self.diag = ctk.CTkTextbox(wrap, font=("Consolas", 11), wrap="word", height=130,
                                   fg_color="#20211F", text_color="#EDE8D8", corner_radius=12)
        self.diag.pack(fill="x", pady=6)
        self.diag.insert("1.0", self._diag_text())
        ctk.CTkLabel(wrap, justify="left", text_color=MUTED, font=("Segoe UI", 11), text=(
            "Zen: Base https://opencode.ai/zen/v1 · Model muse-spark-1.3 (paid, needs credits) · key from https://opencode.ai/auth\n"
            "Free contributor models are OpenCode-client-only (FreeTierError over raw API). No credits? Use FREE mode."
        )).pack(anchor="w", pady=4)

    def _toggle_key(self):
        self.key_e.configure(show="" if self.show_var.get() else "•")

    def _diag_text(self):
        try:
            if DIAG_FILE.exists():
                return "Last error:\n" + DIAG_FILE.read_text()[:1500]
        except Exception:
            pass
        return "Diagnostics ready. Press Test connection."

    def preset_zen(self):
        self.mode_var.set("custom")
        self.url_e.delete(0, "end"); self.url_e.insert(0, "https://opencode.ai/zen/v1")
        self.model_e.delete(0, "end"); self.model_e.insert(0, "muse-spark-1.3")

    def preset_router(self):
        self.mode_var.set("custom")
        self.url_e.delete(0, "end"); self.url_e.insert(0, "https://openrouter.ai/api/v1")
        self.model_e.delete(0, "end"); self.model_e.insert(0, "meta/muse-spark-1.3")

    def save_cfg(self):
        self.settings.update(mode=self.mode_var.get(), api_key=self.key_e.get().strip(),
                             base_url=self.url_e.get().strip(), model=self.model_e.get().strip())
        save_settings(self.settings)
        self.llm = self._make_llm()
        self.model_label.configure(text=f"{self.settings.get('model','')[:30]} · High · Manual")
        self.conn_dot.configure(text_color=GREEN if self.settings.get("api_key") else MUTED)
        messagebox.showinfo("Settings", "Saved.")

    def test_conn(self):
        self.save_cfg_silent()
        self.diag.delete("1.0", "end")
        self.diag.insert("end", "Testing…\n")
        def work():
            try:
                t0 = time.time()
                out = self.llm.chat([{"role": "user", "content": "Reply with OK"}], timeout=40)
                msg = f"OK ({time.time()-t0:.1f}s): {out[:300]}"
            except Exception as e:
                msg = f"FAILED: {e}"
                try:
                    DIAG_FILE.write_text(str(e)[:2000])
                except Exception:
                    pass
            self.after(0, lambda: (self.diag.delete("1.0", "end"), self.diag.insert("1.0", msg)))
        threading.Thread(target=work, daemon=True).start()

    def save_cfg_silent(self):
        self.settings.update(mode=self.mode_var.get(), api_key=self.key_e.get().strip(),
                             base_url=self.url_e.get().strip(), model=self.model_e.get().strip())
        save_settings(self.settings)
        self.llm = self._make_llm()

if __name__ == "__main__":
    App().mainloop()
