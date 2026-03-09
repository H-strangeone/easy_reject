"""
app.py  –  JobTracker  —  Gmail Job Application Tracker
Multi-account | OA details | Referral tracking | Interview links | Smart dates
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import webbrowser
from datetime import datetime

import database as db

# ──────────────────────────────────────────────────────────────────────────────
#  PALETTE
# ──────────────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#0D1117",
    "card":      "#161B22",
    "card2":     "#1C2128",
    "hover":     "#21262D",
    "accent":    "#58A6FF",
    "green":     "#3FB950",
    "red":       "#F78166",
    "yellow":    "#E3B341",
    "purple":    "#BC8CFF",
    "teal":      "#39D353",
    "text":      "#E6EDF3",
    "sub":       "#8B949E",
    "dim":       "#484F58",
    "border":    "#30363D",
}

STATUS_COLOR = {
    "Applied":           C["accent"],
    "In Progress":       C["green"],
    "Rejected":          C["red"],
    "Offer Received":    C["yellow"],
    "Withdrawn":         C["dim"],
    "Referred":          C["purple"],
    "Job Opportunity":   C["teal"],
}

STAGE_OPTIONS = [
    "Applied", "Applied - Waiting", "Referred",
    "OA Received", "OA Submitted", "OA Passed", "OA Failed",
    "Stage 1 - Interview", "Stage 2 - Interview", "Stage 2 - HR Interview",
    "Stage 3 - Final Interview",
    "Offer Received", "Rejected", "Withdrawn",
    "Job Opportunity",
]
STATUS_OPTIONS = ["Applied", "In Progress", "Rejected", "Offer Received",
                  "Withdrawn", "Job Opportunity"]


# ──────────────────────────────────────────────────────────────────────────────
#  WIDGETS
# ──────────────────────────────────────────────────────────────────────────────

class Btn(tk.Canvas):
    """Rounded button canvas widget."""
    def __init__(self, parent, text, cmd=None,
                 bg=None, fg=None, w=120, h=30, r=5, fs=10, **kw):
        bg  = bg or C["accent"]
        fg  = fg or C["bg"]
        pbg = parent.cget("bg") if hasattr(parent, "cget") else C["bg"]
        super().__init__(parent, width=w, height=h, bg=pbg,
                         highlightthickness=0, **kw)
        self._bg, self._fg, self._r = bg, fg, r
        self._text, self._fs, self._cmd = text, fs, cmd
        self._hover = self._lighten(bg)
        self._draw(bg)
        self.bind("<Enter>",    lambda e: self._draw(self._hover))
        self.bind("<Leave>",    lambda e: self._draw(self._bg))
        self.bind("<Button-1>", lambda e: cmd() if cmd else None)

    def _lighten(self, h):
        r = min(255, int(h[1:3],16)+25)
        g = min(255, int(h[3:5],16)+25)
        b = min(255, int(h[5:7],16)+25)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw(self, col):
        self.delete("all")
        w, h, r = self.winfo_reqwidth(), self.winfo_reqheight(), self._r
        self.create_arc(0,   0,   2*r, 2*r, start=90,  extent=90, fill=col, outline=col)
        self.create_arc(w-2*r,0,  w,   2*r, start=0,   extent=90, fill=col, outline=col)
        self.create_arc(0,   h-2*r,2*r,h,   start=180, extent=90, fill=col, outline=col)
        self.create_arc(w-2*r,h-2*r,w, h,   start=270, extent=90, fill=col, outline=col)
        self.create_rectangle(r,0,w-r,h, fill=col, outline=col)
        self.create_rectangle(0,r,w,h-r, fill=col, outline=col)
        self.create_text(w//2, h//2, text=self._text, fill=self._fg,
                         font=("Segoe UI", self._fs, "bold"))

    def update_text(self, text):
        self._text = text
        self._draw(self._bg)


class LinkLabel(tk.Label):
    """Clickable hyperlink label."""
    def __init__(self, parent, text, url, **kw):
        super().__init__(parent, text=text, fg=C["accent"],
                         font=("Segoe UI", 9, "underline"),
                         cursor="hand2", **kw)
        self.bind("<Button-1>", lambda e: webbrowser.open(url))


def sep(parent, color=None, orient="h", **kw):
    color = color or C["border"]
    if orient == "h":
        return tk.Frame(parent, bg=color, height=1, **kw)
    return tk.Frame(parent, bg=color, width=1, **kw)


def lbl(parent, text, size=10, bold=False, color=None, **kw):
    color = color or C["text"]
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, font=("Segoe UI", size, weight),
                    bg=parent.cget("bg"), fg=color, **kw)


def entry(parent, var, w=28, **kw):
    return tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                    bg=C["card2"], fg=C["text"], insertbackground=C["accent"],
                    relief="flat", width=w, **kw)


# ──────────────────────────────────────────────────────────────────────────────
#  JOB DETAIL WINDOW
# ──────────────────────────────────────────────────────────────────────────────

class JobDetailWindow(tk.Toplevel):
    def __init__(self, parent, job_id, on_update=None):
        super().__init__(parent)
        self.job_id    = job_id
        self.on_update = on_update
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.geometry("760x680")
        self._build()

    def _build(self):
        job = db.get_job_by_id(self.job_id)
        if not job:
            self.destroy(); return
        self.title(f"{job['company']}  —  {job['role']}")

        # ── Header ──────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["card"], pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text=job["company"], font=("Segoe UI", 18, "bold"),
                 bg=C["card"], fg=C["text"]).pack(side="left", padx=20)
        sc = STATUS_COLOR.get(job["status"], C["dim"])
        tk.Label(hdr, text=f"  {job['status']}  ", font=("Segoe UI", 10, "bold"),
                 bg=sc, fg=C["bg"]).pack(side="left", padx=6)
        tk.Label(hdr, text=job["stage"], font=("Segoe UI", 10),
                 bg=C["card"], fg=C["sub"]).pack(side="left", padx=6)

        # ── Tabs ─────────────────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)
        self._style_notebook(nb)

        tab_info      = tk.Frame(nb, bg=C["bg"])
        tab_oa        = tk.Frame(nb, bg=C["bg"])
        tab_interview = tk.Frame(nb, bg=C["bg"])
        tab_referral  = tk.Frame(nb, bg=C["bg"])
        tab_timeline  = tk.Frame(nb, bg=C["bg"])
        tab_rawmail   = tk.Frame(nb, bg=C["bg"])

        nb.add(tab_info,      text="  📋 Info  ")
        nb.add(tab_oa,        text="  🧪 OA / Test  ")
        nb.add(tab_interview, text="  🎤 Interview  ")
        nb.add(tab_referral,  text="  👥 Referral  ")
        nb.add(tab_timeline,  text="  📅 Timeline  ")
        nb.add(tab_rawmail,   text="  📧 Emails  ")

        self._build_info_tab(tab_info, job)
        self._build_oa_tab(tab_oa, job)
        self._build_interview_tab(tab_interview, job)
        self._build_referral_tab(tab_referral, job)
        self._build_timeline_tab(tab_timeline, job)
        self._build_rawmail_tab(tab_rawmail, job)

        # ── Bottom save bar ──────────────────────────────────────────────
        bar = tk.Frame(self, bg=C["card"], pady=10)
        bar.pack(fill="x", side="bottom")
        Btn(bar, "💾 Save All", cmd=self._save_all,
            bg=C["green"], fg=C["bg"], w=120, h=30).pack(side="left", padx=16)
        Btn(bar, "Close", cmd=self.destroy,
            bg=C["card2"], fg=C["text"], w=80, h=30).pack(side="left", padx=4)
        self._job = job

    def _style_notebook(self, nb):
        style = ttk.Style()
        style.configure("TNotebook",        background=C["bg"],  borderwidth=0)
        style.configure("TNotebook.Tab",    background=C["card2"], foreground=C["sub"],
                         padding=[10, 6], font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", C["card"])],
                  foreground=[("selected", C["text"])])

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=("Segoe UI", 11, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor="w", padx=20, pady=(14, 4))
        sep(parent).pack(fill="x", padx=20)

    def _row(self, parent, label, value, link=False, url=None):
        f = tk.Frame(parent, bg=C["bg"])
        f.pack(fill="x", padx=24, pady=3)
        tk.Label(f, text=label, font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"], width=22, anchor="w").pack(side="left")
        if link and url:
            LinkLabel(f, str(value or "—"), url, bg=C["bg"]).pack(side="left", padx=4)
        else:
            tk.Label(f, text=str(value or "—"), font=("Segoe UI", 9),
                     bg=C["bg"], fg=C["text"], anchor="w",
                     wraplength=440).pack(side="left", padx=4)

    def _build_info_tab(self, tab, job):
        self._section(tab, "Application Details")
        self._row(tab, "Company",        job["company"])
        self._row(tab, "Role",           job["role"])
        self._row(tab, "Gmail Account",  job["gmail_account"])
        self._row(tab, "Applied Date",   job["applied_date"])
        self._row(tab, "Last Updated",   job["last_updated"])
        self._row(tab, "Email Subject",  job["email_subject"])
        if job.get("job_url"):
            self._row(tab, "Job / Mail URL", job["job_url"], link=True, url=job["job_url"])
        else:
            self._row(tab, "Job / Mail URL", "—")

        if job.get("important_dates"):
            self._section(tab, "Important Dates")
            for d in job["important_dates"].split(","):
                d = d.strip()
                if d:
                    tk.Label(tab, text=f"  📅  {d}", font=("Segoe UI", 10),
                             bg=C["bg"], fg=C["yellow"]).pack(anchor="w", padx=24, pady=1)

        self._section(tab, "Notes")
        self.notes_txt = tk.Text(tab, height=5, font=("Segoe UI", 10),
                                 bg=C["card2"], fg=C["text"],
                                 insertbackground=C["accent"], relief="flat",
                                 padx=8, pady=6)
        self.notes_txt.pack(fill="x", padx=20, pady=4)
        self.notes_txt.insert("1.0", job.get("notes") or "")

        self._section(tab, "Status & Stage")
        f = tk.Frame(tab, bg=C["bg"]); f.pack(fill="x", padx=20, pady=4)
        tk.Label(f, text="Status:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"]).pack(side="left")
        self.status_var = tk.StringVar(value=job["status"])
        ttk.Combobox(f, textvariable=self.status_var, values=STATUS_OPTIONS,
                     width=18, font=("Segoe UI", 9), state="readonly").pack(side="left", padx=8)
        tk.Label(f, text="Stage:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"]).pack(side="left", padx=(16, 0))
        self.stage_var = tk.StringVar(value=job["stage"])
        ttk.Combobox(f, textvariable=self.stage_var, values=STAGE_OPTIONS,
                     width=26, font=("Segoe UI", 9), state="readonly").pack(side="left", padx=8)

    def _build_oa_tab(self, tab, job):
        self._section(tab, "Online Assessment / Test Details")

        has_oa = any([job.get("oa_platform"), job.get("oa_link"),
                      job.get("oa_deadline"), job.get("oa_details")])

        if not has_oa:
            tk.Label(tab, text="No OA/assessment email detected yet.\nThis section updates automatically when a test invite is received.",
                     font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"],
                     justify="center").pack(pady=40)

        if job.get("oa_platform"):
            f = tk.Frame(tab, bg=C["card2"], padx=12, pady=10)
            f.pack(fill="x", padx=20, pady=8)
            tk.Label(f, text="🧪  Platform", font=("Segoe UI", 9, "bold"),
                     bg=C["card2"], fg=C["sub"]).pack(anchor="w")
            tk.Label(f, text=job["oa_platform"], font=("Segoe UI", 14, "bold"),
                     bg=C["card2"], fg=C["teal"]).pack(anchor="w", pady=2)

        info_rows = [
            ("Deadline / Date",  job.get("oa_deadline")),
            ("Duration",         job.get("oa_duration")),
            ("Details",          job.get("oa_details")),
        ]
        for label, val in info_rows:
            if val:
                self._row(tab, label, val)

        if job.get("oa_link"):
            self._section(tab, "Assessment Link")
            lf = tk.Frame(tab, bg=C["card2"], padx=12, pady=10)
            lf.pack(fill="x", padx=20, pady=4)
            url = job["oa_link"]
            tk.Label(lf, text=url[:80] + ("…" if len(url)>80 else ""),
                     font=("Segoe UI", 9), bg=C["card2"], fg=C["sub"],
                     wraplength=480, justify="left").pack(anchor="w")
            Btn(lf, "🔗 Open Assessment Link", cmd=lambda u=url: webbrowser.open(u),
                bg=C["teal"], fg=C["bg"], w=200, h=28, fs=9).pack(anchor="w", pady=6)

        self._section(tab, "Edit OA Info")
        ef = tk.Frame(tab, bg=C["bg"]); ef.pack(fill="x", padx=20)
        rows = [
            ("Platform",        "oa_platform",   job.get("oa_platform", "")),
            ("Assessment URL",  "oa_link",       job.get("oa_link", "")),
            ("Deadline (dd-mm-yyyy)", "oa_deadline", job.get("oa_deadline", "")),
            ("Duration",        "oa_duration",   job.get("oa_duration", "")),
        ]
        self._oa_vars = {}
        for i, (label, key, val) in enumerate(rows):
            tk.Label(ef, text=label, font=("Segoe UI", 9, "bold"),
                     bg=C["bg"], fg=C["sub"], anchor="w",
                     width=26).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=val)
            entry(ef, v, w=42).grid(row=i, column=1, sticky="w", padx=8, pady=3)
            self._oa_vars[key] = v

        tk.Label(ef, text="Details / Notes", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"], anchor="w").grid(
            row=len(rows), column=0, sticky="nw", pady=3)
        self.oa_details_txt = tk.Text(ef, height=3, width=44, font=("Segoe UI", 9),
                                      bg=C["card2"], fg=C["text"],
                                      insertbackground=C["accent"], relief="flat")
        self.oa_details_txt.grid(row=len(rows), column=1, sticky="w", padx=8, pady=3)
        self.oa_details_txt.insert("1.0", job.get("oa_details") or "")

    def _build_interview_tab(self, tab, job):
        self._section(tab, "Interview Details")

        has_int = any([job.get("interview_link"), job.get("interview_date"),
                       job.get("interview_details")])
        if not has_int:
            tk.Label(tab, text="No interview invite detected yet.\nUpdates automatically when an interview email is received.",
                     font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"],
                     justify="center").pack(pady=40)

        if job.get("interview_date"):
            f = tk.Frame(tab, bg=C["card2"], padx=12, pady=10)
            f.pack(fill="x", padx=20, pady=8)
            tk.Label(f, text="📅  Interview Date", font=("Segoe UI", 9, "bold"),
                     bg=C["card2"], fg=C["sub"]).pack(anchor="w")
            tk.Label(f, text=job["interview_date"], font=("Segoe UI", 15, "bold"),
                     bg=C["card2"], fg=C["yellow"]).pack(anchor="w", pady=2)

        if job.get("interview_details"):
            self._row(tab, "Details", job["interview_details"])

        if job.get("interview_link"):
            self._section(tab, "Meeting / Interview Link")
            lf = tk.Frame(tab, bg=C["card2"], padx=12, pady=10)
            lf.pack(fill="x", padx=20, pady=4)
            url = job["interview_link"]
            tk.Label(lf, text=url[:80] + ("…" if len(url)>80 else ""),
                     font=("Segoe UI", 9), bg=C["card2"], fg=C["sub"],
                     wraplength=480, justify="left").pack(anchor="w")
            Btn(lf, "🎤 Join Meeting", cmd=lambda u=url: webbrowser.open(u),
                bg=C["accent"], fg=C["bg"], w=160, h=28, fs=9).pack(anchor="w", pady=6)

        self._section(tab, "Edit Interview Info")
        ef = tk.Frame(tab, bg=C["bg"]); ef.pack(fill="x", padx=20)
        rows = [
            ("Interview Date (dd-mm-yyyy)", "interview_date", job.get("interview_date", "")),
            ("Meeting Link",                "interview_link", job.get("interview_link", "")),
        ]
        self._int_vars = {}
        for i, (label, key, val) in enumerate(rows):
            tk.Label(ef, text=label, font=("Segoe UI", 9, "bold"),
                     bg=C["bg"], fg=C["sub"], anchor="w",
                     width=30).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=val)
            entry(ef, v, w=42).grid(row=i, column=1, sticky="w", padx=8, pady=3)
            self._int_vars[key] = v

        tk.Label(ef, text="Details / Notes", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"], anchor="w").grid(
            row=len(rows), column=0, sticky="nw", pady=3)
        self.int_details_txt = tk.Text(ef, height=3, width=44, font=("Segoe UI", 9),
                                       bg=C["card2"], fg=C["text"],
                                       insertbackground=C["accent"], relief="flat")
        self.int_details_txt.grid(row=len(rows), column=1, sticky="w", padx=8, pady=3)
        self.int_details_txt.insert("1.0", job.get("interview_details") or "")

    def _build_referral_tab(self, tab, job):
        self._section(tab, "Referral Information")

        if job.get("referred_by"):
            f = tk.Frame(tab, bg=C["card2"], padx=16, pady=12)
            f.pack(fill="x", padx=20, pady=10)
            tk.Label(f, text="👥  Referred By", font=("Segoe UI", 9, "bold"),
                     bg=C["card2"], fg=C["sub"]).pack(anchor="w")
            tk.Label(f, text=job["referred_by"], font=("Segoe UI", 16, "bold"),
                     bg=C["card2"], fg=C["purple"]).pack(anchor="w", pady=4)
            if job.get("referral_date"):
                tk.Label(f, text=f"Referral date: {job['referral_date']}",
                         font=("Segoe UI", 9), bg=C["card2"], fg=C["sub"]).pack(anchor="w")
        else:
            tk.Label(tab, text="No referral detected yet.\nIf someone referred you, fill in the fields below.",
                     font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"],
                     justify="center").pack(pady=30)

        self._section(tab, "Edit Referral Info")
        ef = tk.Frame(tab, bg=C["bg"]); ef.pack(fill="x", padx=20)
        rows = [
            ("Referred By (name)",      "referred_by",    job.get("referred_by", "")),
            ("Referral Date (dd-mm-yyyy)", "referral_date", job.get("referral_date", "")),
        ]
        self._ref_vars = {}
        for i, (label, key, val) in enumerate(rows):
            tk.Label(ef, text=label, font=("Segoe UI", 9, "bold"),
                     bg=C["bg"], fg=C["sub"], anchor="w",
                     width=30).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=val)
            entry(ef, v, w=36).grid(row=i, column=1, sticky="w", padx=8, pady=4)
            self._ref_vars[key] = v

    def _build_timeline_tab(self, tab, job):
        self._section(tab, "Email History / Timeline")

        events = db.get_email_events(self.job_id)
        if not events:
            tk.Label(tab, text="No email events recorded yet.",
                     font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"]).pack(pady=30)
            return

        canvas = tk.Canvas(tab, bg=C["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg=C["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        sb.pack(side="right", fill="y")

        TYPE_ICON = {
            "application_sent": ("📨", C["accent"]),
            "referral":         ("👥", C["purple"]),
            "oa":               ("🧪", C["teal"]),
            "interview":        ("🎤", C["green"]),
            "rejected":         ("❌", C["red"]),
            "offer":            ("🎉", C["yellow"]),
            "accepted":         ("✅", C["green"]),
            "opportunity":      ("💡", C["teal"]),
            "unknown":          ("📧", C["sub"]),
        }

        for ev in events:
            icon, color = TYPE_ICON.get(ev["event_type"], ("📧", C["sub"]))
            card = tk.Frame(inner, bg=C["card"], pady=8, padx=12)
            card.pack(fill="x", pady=3)

            # Row 1: icon + type label + date + Open in Gmail button
            r1 = tk.Frame(card, bg=C["card"]); r1.pack(fill="x")
            tk.Label(r1, text=f"{icon} {ev['event_type'].replace('_', ' ').title()}",
                     font=("Segoe UI", 10, "bold"), bg=C["card"], fg=color).pack(side="left")

            # Open in Gmail button — uses message_id to build direct link
            msg_id = ev.get("message_id", "")
            if msg_id:
                gmail_url = f"https://mail.google.com/mail/u/0/#all/{msg_id}"
                gmail_btn = tk.Label(
                    r1, text="  📬 Open in Gmail",
                    font=("Segoe UI", 8, "underline"),
                    bg=C["card"], fg=C["accent"], cursor="hand2"
                )
                gmail_btn.pack(side="left", padx=(10, 0))
                gmail_btn.bind("<Button-1>", lambda e, url=gmail_url: webbrowser.open(url))

            tk.Label(r1, text=ev["event_date"], font=("Segoe UI", 9),
                     bg=C["card"], fg=C["dim"]).pack(side="right")

            # Subject
            tk.Label(card, text=ev["subject"], font=("Segoe UI", 9, "bold"),
                     bg=C["card"], fg=C["text"], anchor="w",
                     wraplength=560).pack(anchor="w", pady=(2, 0))

            # AI summary (shown if LLM was used)
            raw = ev.get("raw_details", "")
            if raw and raw.startswith("[AI]"):
                ai_line = raw.split("\n")[0].replace("[AI]", "").strip()
                tk.Label(card, text=f"🤖 {ai_line}",
                         font=("Segoe UI", 8, "italic"),
                         bg=C["card"], fg=C["teal"],
                         anchor="w", wraplength=560).pack(anchor="w", pady=(1, 0))

            # Snippet
            if ev.get("snippet"):
                tk.Label(card, text=ev["snippet"][:200],
                         font=("Segoe UI", 8), bg=C["card"], fg=C["sub"],
                         anchor="w", wraplength=560, justify="left").pack(anchor="w", pady=(1, 0))

            # Extracted dates
            if ev.get("extracted_dates"):
                tk.Label(card, text=f"📅 Dates: {ev['extracted_dates']}",
                         font=("Segoe UI", 8, "bold"), bg=C["card"],
                         fg=C["yellow"]).pack(anchor="w", pady=(2, 0))

            # Links
            if ev.get("extracted_links"):
                links = [l for l in ev["extracted_links"].split("\n") if l.strip()]
                for lnk in links[:3]:
                    lnk = lnk.strip()
                    if lnk:
                        lf = tk.Frame(card, bg=C["card"]); lf.pack(anchor="w")
                        tk.Label(lf, text="🔗", font=("Segoe UI", 8),
                                 bg=C["card"], fg=C["accent"]).pack(side="left")
                        LinkLabel(lf, lnk[:70] + ("…" if len(lnk)>70 else ""),
                                  lnk, bg=C["card"]).pack(side="left", padx=2)

            sep(card, color=C["border"]).pack(fill="x", pady=(6, 0))

    def _build_rawmail_tab(self, tab, job):
        """Full raw email viewer — one expandable card per email event."""
        self._section(tab, "Raw Email Content")

        events = db.get_email_events(self.job_id)
        if not events:
            tk.Label(tab, text="No emails recorded yet.",
                     font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"]).pack(pady=30)
            return

        # Scrollable container
        canvas = tk.Canvas(tab, bg=C["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg=C["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        sb.pack(side="right", fill="y")

        TYPE_ICON = {
            "application_sent": ("📨", C["accent"]),
            "referral":         ("👥", C["purple"]),
            "oa":               ("🧪", C["teal"]),
            "interview":        ("🎤", C["green"]),
            "rejected":         ("❌", C["red"]),
            "offer":            ("🎉", C["yellow"]),
            "accepted":         ("✅", C["green"]),
            "unknown":          ("📧", C["sub"]),
        }

        for ev in events:
            icon, color = TYPE_ICON.get(ev["event_type"], ("📧", C["sub"]))
            msg_id      = ev.get("message_id", "")
            sender_full = ev.get("sender_full", "")
            body_text   = ev.get("body_text", "") or ev.get("raw_details", "")

            # Outer card
            card = tk.Frame(inner, bg=C["card"], pady=0, padx=0,
                            relief="flat", bd=0)
            card.pack(fill="x", pady=4, padx=4)

            # ── Collapsed header (always visible) ────────────────────────
            hdr = tk.Frame(card, bg=C["card2"], padx=12, pady=8)
            hdr.pack(fill="x")

            # Left: icon + event type + date
            left_hdr = tk.Frame(hdr, bg=C["card2"]); left_hdr.pack(side="left", fill="x", expand=True)
            tk.Label(left_hdr,
                     text=f"{icon}  {ev['event_type'].replace('_',' ').title()}  ·  {ev['event_date']}",
                     font=("Segoe UI", 9, "bold"), bg=C["card2"], fg=color).pack(side="left")

            # Subject on same header row
            subj = ev.get("subject", "")
            if subj:
                tk.Label(left_hdr, text=f"   {subj[:80]}{'…' if len(subj)>80 else ''}",
                         font=("Segoe UI", 9), bg=C["card2"], fg=C["sub"]).pack(side="left")

            # Right: Gmail link + expand toggle
            right_hdr = tk.Frame(hdr, bg=C["card2"]); right_hdr.pack(side="right")

            if msg_id:
                gmail_url = f"https://mail.google.com/mail/u/0/#all/{msg_id}"
                gl = tk.Label(right_hdr, text="📬 Open in Gmail",
                              font=("Segoe UI", 8, "underline"),
                              bg=C["card2"], fg=C["accent"], cursor="hand2")
                gl.pack(side="left", padx=(0, 10))
                gl.bind("<Button-1>", lambda e, u=gmail_url: webbrowser.open(u))

            toggle_var = tk.StringVar(value="▼ Show")
            toggle_lbl = tk.Label(right_hdr, textvariable=toggle_var,
                                  font=("Segoe UI", 8), bg=C["card2"],
                                  fg=C["teal"], cursor="hand2", padx=6)
            toggle_lbl.pack(side="left")

            # ── Expandable body ───────────────────────────────────────────
            body_frame = tk.Frame(card, bg=C["card"], padx=14, pady=10)
            # Start collapsed
            body_frame._visible = False

            def toggle(bf=body_frame, tv=toggle_var, canvas_ref=canvas):
                if bf._visible:
                    bf.pack_forget()
                    tv.set("▼ Show")
                    bf._visible = False
                else:
                    bf.pack(fill="x")
                    tv.set("▲ Hide")
                    bf._visible = True
                canvas_ref.after(50, lambda: canvas_ref.configure(
                    scrollregion=canvas_ref.bbox("all")))

            toggle_lbl.bind("<Button-1>", lambda e, t=toggle: t())
            hdr.bind("<Button-1>",        lambda e, t=toggle: t())

            # Sender info
            if sender_full:
                sf = tk.Frame(body_frame, bg=C["card"]); sf.pack(fill="x", pady=(0, 6))
                tk.Label(sf, text="From:", font=("Segoe UI", 8, "bold"),
                         bg=C["card"], fg=C["sub"], width=10, anchor="w").pack(side="left")
                tk.Label(sf, text=sender_full, font=("Segoe UI", 8),
                         bg=C["card"], fg=C["text"], wraplength=500,
                         anchor="w", justify="left").pack(side="left")

            # Subject full
            if ev.get("subject"):
                sf2 = tk.Frame(body_frame, bg=C["card"]); sf2.pack(fill="x", pady=(0, 4))
                tk.Label(sf2, text="Subject:", font=("Segoe UI", 8, "bold"),
                         bg=C["card"], fg=C["sub"], width=10, anchor="w").pack(side="left")
                tk.Label(sf2, text=ev["subject"], font=("Segoe UI", 8),
                         bg=C["card"], fg=C["text"], wraplength=500,
                         anchor="w", justify="left").pack(side="left")

            sep(body_frame, color=C["border"]).pack(fill="x", pady=6)

            # AI summary
            raw = ev.get("raw_details", "")
            if raw and raw.startswith("[AI]"):
                ai_line = raw.split("\n")[0].replace("[AI]", "").strip()
                tk.Label(body_frame, text=f"🤖 AI Summary: {ai_line}",
                         font=("Segoe UI", 8, "italic"),
                         bg=C["card"], fg=C["teal"],
                         wraplength=540, anchor="w").pack(anchor="w", pady=(0, 6))

            # Full body text in a scrollable text widget
            if body_text and body_text.strip():
                tk.Label(body_frame, text="Email Body:",
                         font=("Segoe UI", 8, "bold"),
                         bg=C["card"], fg=C["sub"]).pack(anchor="w", pady=(0, 3))
                txt_frame = tk.Frame(body_frame, bg=C["card"])
                txt_frame.pack(fill="x")
                body_txt = tk.Text(txt_frame, height=18,
                                   font=("Segoe UI", 8),
                                   bg=C["card2"], fg=C["text"],
                                   relief="flat", padx=8, pady=6,
                                   wrap="word", state="normal",
                                   insertbackground=C["accent"])
                body_sb = ttk.Scrollbar(txt_frame, orient="vertical",
                                        command=body_txt.yview)
                body_txt.configure(yscrollcommand=body_sb.set)
                body_txt.pack(side="left", fill="x", expand=True)
                body_sb.pack(side="right", fill="y")
                # Clean up and insert text
                clean_body = body_text.strip()
                body_txt.insert("1.0", clean_body)
                body_txt.config(state="disabled")
            elif ev.get("snippet"):
                tk.Label(body_frame, text=ev["snippet"],
                         font=("Segoe UI", 8), bg=C["card"], fg=C["sub"],
                         wraplength=540, anchor="w", justify="left").pack(anchor="w")

            # Extracted links
            if ev.get("extracted_links"):
                links = [l.strip() for l in ev["extracted_links"].split("\n") if l.strip()]
                if links:
                    sep(body_frame, color=C["border"]).pack(fill="x", pady=6)
                    tk.Label(body_frame, text="Links found in email:",
                             font=("Segoe UI", 8, "bold"),
                             bg=C["card"], fg=C["sub"]).pack(anchor="w", pady=(0, 2))
                    for lnk in links:
                        lf = tk.Frame(body_frame, bg=C["card"]); lf.pack(anchor="w")
                        tk.Label(lf, text="🔗", font=("Segoe UI", 8),
                                 bg=C["card"], fg=C["accent"]).pack(side="left")
                        LinkLabel(lf, lnk[:80] + ("…" if len(lnk)>80 else ""),
                                  lnk, bg=C["card"]).pack(side="left", padx=2)

            # Dates
            if ev.get("extracted_dates"):
                sep(body_frame, color=C["border"]).pack(fill="x", pady=6)
                tk.Label(body_frame,
                         text=f"📅 Important dates: {ev['extracted_dates']}",
                         font=("Segoe UI", 8, "bold"),
                         bg=C["card"], fg=C["yellow"]).pack(anchor="w")

    def _save_all(self):
        db.update_job_status(
            self.job_id,
            status=self.status_var.get(),
            stage=self.stage_var.get(),
            notes=self.notes_txt.get("1.0", "end-1c"),
            oa_platform=self._oa_vars["oa_platform"].get().strip() or None,
            oa_link=self._oa_vars["oa_link"].get().strip() or None,
            oa_deadline=self._oa_vars["oa_deadline"].get().strip() or None,
            oa_duration=self._oa_vars["oa_duration"].get().strip() or None,
            oa_details=self.oa_details_txt.get("1.0", "end-1c") or None,
            interview_link=self._int_vars["interview_link"].get().strip() or None,
            interview_date=self._int_vars["interview_date"].get().strip() or None,
            interview_details=self.int_details_txt.get("1.0", "end-1c") or None,
            referred_by=self._ref_vars["referred_by"].get().strip() or None,
            referral_date=self._ref_vars["referral_date"].get().strip() or None,
        )
        if self.on_update:
            self.on_update()
        messagebox.showinfo("Saved", "All changes saved.")


# ──────────────────────────────────────────────────────────────────────────────
#  ADD JOB DIALOG
# ──────────────────────────────────────────────────────────────────────────────

class AddJobDialog(tk.Toplevel):
    def __init__(self, parent, accounts, on_save):
        super().__init__(parent)
        self.title("Add Job Application")
        self.configure(bg=C["bg"])
        self.geometry("500x480")
        self.resizable(False, False)
        self.on_save = on_save
        self.accounts = accounts or ["your@gmail.com"]
        self._build()

    def _build(self):
        tk.Label(self, text="Add Job Manually", font=("Segoe UI", 15, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(pady=(18, 4))
        sep(self).pack(fill="x", padx=20)

        f = tk.Frame(self, bg=C["bg"]); f.pack(fill="both", expand=True, padx=28, pady=10)
        self.vars = {}
        fields = [
            ("Company *",              "company",      ""),
            ("Role *",                 "role",         ""),
            ("Applied Date (dd-mm-yyyy)", "applied_date", datetime.now().strftime("%d-%m-%Y")),
            ("Job URL",                "job_url",      ""),
            ("Referred By",            "referred_by",  ""),
            ("Notes",                  "notes",        ""),
        ]
        for i, (label, key, default) in enumerate(fields):
            tk.Label(f, text=label, font=("Segoe UI", 9, "bold"),
                     bg=C["bg"], fg=C["sub"], anchor="w").grid(
                row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=default)
            entry(f, v, w=34).grid(row=i, column=1, sticky="w", padx=10, pady=4)
            self.vars[key] = v

        # Account
        tk.Label(f, text="Gmail Account", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"], anchor="w").grid(
            row=len(fields), column=0, sticky="w", pady=4)
        self.acct_var = tk.StringVar(value=self.accounts[0])
        ttk.Combobox(f, textvariable=self.acct_var, values=self.accounts,
                     width=32, state="readonly").grid(
            row=len(fields), column=1, sticky="w", padx=10, pady=4)

        bf = tk.Frame(self, bg=C["bg"]); bf.pack(pady=10)
        Btn(bf, "Save",   cmd=self._save,  bg=C["accent"],  w=90,  h=30).pack(side="left", padx=6)
        Btn(bf, "Cancel", cmd=self.destroy, bg=C["card2"], fg=C["text"], w=90, h=30).pack(side="left", padx=6)

    def _save(self):
        co = self.vars["company"].get().strip()
        ro = self.vars["role"].get().strip()
        if not co or not ro:
            messagebox.showwarning("Required", "Company and Role are required.")
            return
        db.add_job(
            company=co, role=ro,
            gmail_account=self.acct_var.get(),
            applied_date=self.vars["applied_date"].get().strip(),
            job_url=self.vars["job_url"].get().strip(),
            notes=self.vars["notes"].get().strip(),
            referred_by=self.vars["referred_by"].get().strip(),
        )
        self.on_save()
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  SETTINGS DIALOG
# ──────────────────────────────────────────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_save, app_ref=None):
        super().__init__(parent)
        self.title("Settings")
        self.configure(bg=C["bg"])
        self.geometry("600x580")
        self.on_save = on_save
        self.app_ref = app_ref
        self._build()

    def _build(self):
        tk.Label(self, text="⚙  Settings", font=("Segoe UI", 15, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(pady=(18, 4))
        sep(self).pack(fill="x", padx=20)

        f = tk.Frame(self, bg=C["bg"]); f.pack(fill="both", expand=True, padx=28, pady=10)

        # credentials.json
        lbl(f, "Google OAuth credentials.json:", bold=True, color=C["sub"]).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(10, 2))
        self.creds_var = tk.StringVar(value=db.get_setting("credentials_path", ""))
        entry(f, self.creds_var, w=44).grid(row=1, column=0, columnspan=2, sticky="w")
        Btn(f, "Browse", cmd=self._browse,
            bg=C["card2"], fg=C["text"], w=80, h=26, fs=9
            ).grid(row=1, column=2, padx=8)

        # How to get guide
        guide = (
            "1. console.cloud.google.com → New project\n"
            "2. APIs & Services → Library → Gmail API → Enable\n"
            "3. APIs & Services → Credentials → Create OAuth 2.0 Client (Desktop App)\n"
            "4. Download JSON, rename to credentials.json\n"
            "5. OAuth consent screen → Test Users → add both your Gmail addresses"
        )
        bg2 = tk.Frame(f, bg=C["card2"], padx=10, pady=8)
        bg2.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)
        tk.Label(bg2, text="How to get credentials.json:", font=("Segoe UI", 8, "bold"),
                 bg=C["card2"], fg=C["accent"]).pack(anchor="w")
        tk.Label(bg2, text=guide, font=("Segoe UI", 8), bg=C["card2"], fg=C["sub"],
                 justify="left").pack(anchor="w")

        sep(f, color=C["border"]).grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)

        # Gmail accounts
        lbl(f, "Gmail Accounts (one per line):", bold=True, color=C["sub"]).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 2))
        accts_raw = db.get_setting("gmail_accounts", "")
        self.accts_txt = tk.Text(f, height=3, width=50, font=("Segoe UI", 10),
                                 bg=C["card2"], fg=C["text"],
                                 insertbackground=C["accent"], relief="flat")
        self.accts_txt.grid(row=5, column=0, columnspan=3, sticky="w", pady=2)
        self.accts_txt.insert("1.0", accts_raw)

        # Auth buttons per account
        auth_f = tk.Frame(f, bg=C["bg"])
        auth_f.grid(row=6, column=0, columnspan=3, sticky="w", pady=4)
        lbl(auth_f, "Authorise accounts:", bold=True, color=C["sub"]).pack(anchor="w")
        self._auth_btn_frame = tk.Frame(auth_f, bg=C["bg"])
        self._auth_btn_frame.pack(anchor="w", pady=4)
        self._refresh_auth_buttons()

        sep(f, color=C["border"]).grid(row=7, column=0, columnspan=3, sticky="ew", pady=8)

        # Groq API key (free LLM for smarter email classification)
        lbl(f, "🤖 Groq API Key  (free – get yours at console.groq.com):",
            bold=True, color=C["sub"]).grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 2))
        groq_f = tk.Frame(f, bg=C["bg"]); groq_f.grid(row=9, column=0, columnspan=3, sticky="ew")
        self.groq_var = tk.StringVar(value=db.get_setting("groq_api_key", ""))
        groq_entry = entry(groq_f, self.groq_var, w=46)
        groq_entry.pack(side="left")
        groq_entry.config(show="*")
        show_lbl = tk.Label(groq_f, text="  show", font=("Segoe UI", 8), bg=C["bg"],
                            fg=C["accent"], cursor="hand2")
        show_lbl.pack(side="left")
        show_lbl.bind("<Button-1>", lambda e, en=groq_entry: en.config(
            show="" if en.cget("show") == "*" else "*"))

        # Test connection button
        self._groq_status = tk.StringVar(value="")
        test_btn = tk.Label(groq_f, text="  🔌 Test Connection", font=("Segoe UI", 8),
                            bg=C["bg"], fg=C["teal"], cursor="hand2")
        test_btn.pack(side="left", padx=(8, 0))
        test_btn.bind("<Button-1>", lambda e: self._test_groq())
        self._groq_status_lbl = tk.Label(groq_f, textvariable=self._groq_status,
                                          font=("Segoe UI", 8), bg=C["bg"], fg=C["green"])
        self._groq_status_lbl.pack(side="left", padx=(6, 0))
        lbl(f, "  Optional – enables AI-powered email classification (rejected / applied / moving forward).\n"
               "  Free tier: 14,400 requests/day. No credit card needed.",
            color=C["dim"], size=8).grid(row=10, column=0, columnspan=3, sticky="w", pady=(1, 4))

        sep(f, color=C["border"]).grid(row=11, column=0, columnspan=3, sticky="ew", pady=8)

        # Scan time + days back
        lbl(f, "Daily Auto-Scan Time (HH:MM, 24h format):", bold=True, color=C["sub"]).grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(4,2))
        tf = tk.Frame(f, bg=C["bg"]); tf.grid(row=13, column=0, columnspan=3, sticky="w")
        self.scan_time_var = tk.StringVar(value=db.get_setting("scan_time", "08:00"))
        entry(tf, self.scan_time_var, w=10).pack(side="left")
        lbl(tf, "  (app checks Gmail once a day at this time)", color=C["dim"], size=8).pack(side="left")

        lbl(f, "How far back to scan emails:", bold=True, color=C["sub"]).grid(
            row=14, column=0, columnspan=2, sticky="w", pady=(10, 2))
        days_f = tk.Frame(f, bg=C["bg"]); days_f.grid(row=15, column=0, columnspan=3, sticky="w")
        self.days_var = tk.StringVar(value=db.get_setting("days_back", "90"))
        entry(days_f, self.days_var, w=6).pack(side="left")
        lbl(days_f, "  days", color=C["sub"]).pack(side="left")
        # Quick preset buttons
        for label, val in [("1 week", "7"), ("1 month", "30"), ("3 months", "90"), ("6 months", "180"), ("1 year", "365")]:
            b = tk.Label(days_f, text=label, font=("Segoe UI", 8),
                         bg=C["card2"], fg=C["accent"], padx=6, pady=3, cursor="hand2")
            b.pack(side="left", padx=3)
            b.bind("<Button-1>", lambda e, v=val: self.days_var.set(v))
        lbl(f, "  Tip: Use 180 or 365 days on first scan to catch all past applications",
            color=C["yellow"], size=8).grid(row=16, column=0, columnspan=3, sticky="w", pady=(2,0))

        bf = tk.Frame(self, bg=C["bg"]); bf.pack(pady=10)
        Btn(bf, "💾 Save Settings", cmd=self._save,
            bg=C["accent"], w=140, h=30).pack(side="left", padx=6)
        Btn(bf, "Cancel", cmd=self.destroy,
            bg=C["card2"], fg=C["text"], w=90, h=30).pack(side="left", padx=6)

    def _refresh_auth_buttons(self):
        for w in self._auth_btn_frame.winfo_children():
            w.destroy()
        accounts = [a.strip() for a in self.accts_txt.get("1.0","end-1c").split("\n") if a.strip()]
        for acct in accounts:
            token_exists = os.path.exists(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "data", f"token_{acct.replace('@','_at_').replace('.','_')}.json")
            )
            icon = "✅" if token_exists else "🔑"
            label = f"{icon} {acct}  {'(authorised)' if token_exists else '(click to authorise)'}"
            btn = tk.Label(self._auth_btn_frame, text=label, font=("Segoe UI", 9),
                           bg=C["card2"], fg=C["teal"] if token_exists else C["yellow"],
                           padx=8, pady=4, cursor="hand2")
            btn.pack(anchor="w", pady=2)
            if not token_exists:
                btn.bind("<Button-1>", lambda e, a=acct: self._auth_account(a))

    def _auth_account(self, account):
        creds_path = self.creds_var.get().strip()
        if not creds_path or not os.path.exists(creds_path):
            messagebox.showerror("Error", "Set credentials.json path first.")
            return

        # Disable all auth buttons while working
        for w in self._auth_btn_frame.winfo_children():
            w.configure(text=f"  ⏳ Authorising {account}… (browser will open)",
                        fg=C["yellow"], cursor="arrow")
            w.unbind("<Button-1>")

        def run_auth():
            try:
                import gmail_scanner
                gmail_scanner.get_credentials(account, creds_path)
                # Success — update UI on main thread
                self.after(0, lambda: self._on_auth_success(account))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_auth_fail(account, err))

        threading.Thread(target=run_auth, daemon=True).start()

    def _on_auth_success(self, account):
        try:
            self._refresh_auth_buttons()
            messagebox.showinfo("Authorised ✅", f"Successfully authorised:\n{account}\n\nYou can now scan this account.")
        except Exception:
            pass  # dialog may have closed

    def _on_auth_fail(self, account, err):
        try:
            self._refresh_auth_buttons()
            messagebox.showerror("Auth Failed",
                f"Could not authorise {account}:\n\n{err}\n\n"
                "Make sure:\n"
                "1. credentials.json path is correct\n"
                "2. You added your Gmail as a Test User in Google Cloud Console\n"
                "3. You allowed access in the browser that opened")
        except Exception:
            pass

    def _browse(self):
        p = filedialog.askopenfilename(
            title="Select credentials.json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            self.creds_var.set(p)

    def _test_groq(self):
        """Save the key temporarily and test the Groq connection."""
        key = self.groq_var.get().strip()
        if not key:
            self._groq_status.set("⚠ No key entered")
            self._groq_status_lbl.config(fg=C["yellow"])
            return
        db.set_setting("groq_api_key", key)
        self._groq_status.set("⏳ Testing…")
        self._groq_status_lbl.config(fg=C["dim"])

        def run():
            try:
                import gmail_scanner
                ok, msg = gmail_scanner.test_groq_connection()
                color = C["green"] if ok else C["red"]
                self.after(0, lambda: self._groq_status.set(msg))
                self.after(0, lambda: self._groq_status_lbl.config(fg=color))
            except Exception as e:
                self.after(0, lambda: self._groq_status.set(f"Error: {e}"))
                self.after(0, lambda: self._groq_status_lbl.config(fg=C["red"]))

        threading.Thread(target=run, daemon=True).start()

    def _save(self):
        db.set_setting("credentials_path", self.creds_var.get().strip())
        db.set_setting("scan_time",         self.scan_time_var.get().strip())
        db.set_setting("days_back",         self.days_var.get().strip())
        db.set_setting("gmail_accounts",    self.accts_txt.get("1.0","end-1c").strip())
        db.set_setting("groq_api_key",      self.groq_var.get().strip())
        self.on_save()
        messagebox.showinfo("Saved", "Settings saved!")
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  JOB CARD  (list item)
# ──────────────────────────────────────────────────────────────────────────────

class JobCard(tk.Frame):
    def __init__(self, parent, job, on_click, on_delete, on_status_change, **kw):
        super().__init__(parent, bg=C["card"], **kw)
        self.job = job
        self._on_click = on_click
        self._build(on_delete, on_status_change)

    def _build(self, on_delete, on_status_change):
        inner = tk.Frame(self, bg=C["card"], padx=14, pady=10)
        inner.pack(fill="x")
        inner.bind("<Button-1>", lambda e: self._on_click(self.job["id"]))

        # Left
        left = tk.Frame(inner, bg=C["card"])
        left.pack(side="left", fill="x", expand=True)
        left.bind("<Button-1>", lambda e: self._on_click(self.job["id"]))

        # Company + badges row
        top = tk.Frame(left, bg=C["card"]); top.pack(anchor="w")
        tk.Label(top, text=self.job["company"], font=("Segoe UI", 13, "bold"),
                 bg=C["card"], fg=C["text"], cursor="hand2").pack(side="left")
        top.bind("<Button-1>", lambda e: self._on_click(self.job["id"]))

        # Special badges
        if self.job.get("referred_by"):
            tk.Label(top, text="  👥 Referred  ", font=("Segoe UI", 8, "bold"),
                     bg=C["purple"], fg=C["bg"], padx=2).pack(side="left", padx=4)
        if self.job.get("oa_link") or self.job.get("oa_platform"):
            plat = self.job.get("oa_platform") or "OA"
            tk.Label(top, text=f"  🧪 {plat}  ", font=("Segoe UI", 8, "bold"),
                     bg=C["teal"], fg=C["bg"], padx=2).pack(side="left", padx=2)
        if self.job.get("interview_link"):
            tk.Label(top, text="  🎤 Interview  ", font=("Segoe UI", 8, "bold"),
                     bg=C["accent"], fg=C["bg"], padx=2).pack(side="left", padx=2)

        # Role
        tk.Label(left, text=self.job["role"], font=("Segoe UI", 10),
                 bg=C["card"], fg=C["sub"]).pack(anchor="w")

        # Meta row
        meta = tk.Frame(left, bg=C["card"]); meta.pack(anchor="w", pady=(3, 0))
        pieces = []
        if self.job.get("applied_date"):
            pieces.append(("📅 " + self.job["applied_date"], C["dim"]))
        if self.job.get("gmail_account"):
            pieces.append(("📧 " + self.job["gmail_account"], C["dim"]))
        if self.job.get("referred_by"):
            pieces.append(("👥 " + self.job["referred_by"], C["purple"]))
        if self.job.get("oa_deadline"):
            pieces.append(("⏰ OA deadline: " + self.job["oa_deadline"], C["yellow"]))
        if self.job.get("important_dates"):
            pieces.append(("🗓 " + self.job["important_dates"][:50], C["yellow"]))

        for text, color in pieces:
            tk.Label(meta, text=text, font=("Segoe UI", 8),
                     bg=C["card"], fg=color).pack(side="left", padx=(0, 10))

        # OA link quick-open
        if self.job.get("oa_link"):
            lf = tk.Frame(left, bg=C["card"]); lf.pack(anchor="w", pady=(2, 0))
            lnk = self.job["oa_link"]
            tk.Label(lf, text="🔗 ", font=("Segoe UI", 8),
                     bg=C["card"], fg=C["teal"]).pack(side="left")
            LinkLabel(lf, lnk[:60]+("…" if len(lnk)>60 else ""), lnk,
                      bg=C["card"]).pack(side="left")

        # Right: status + controls
        right = tk.Frame(inner, bg=C["card"]); right.pack(side="right")

        sc = STATUS_COLOR.get(self.job["status"], C["dim"])
        tk.Label(right, text=f"  {self.job['status']}  ",
                 font=("Segoe UI", 9, "bold"), bg=sc, fg=C["bg"],
                 padx=4, pady=2).pack(anchor="e")
        tk.Label(right, text=self.job.get("stage", ""),
                 font=("Segoe UI", 8), bg=C["card"], fg=C["sub"]).pack(anchor="e", pady=2)

        # Visible "View Details" button
        details_btn = tk.Label(right, text="View Details →",
                               font=("Segoe UI", 8, "underline"),
                               bg=C["card"], fg=C["accent"], cursor="hand2",
                               padx=4, pady=2)
        details_btn.pack(anchor="e", pady=(2, 4))
        details_btn.bind("<Button-1>", lambda e: self._on_click(self.job["id"]))

        ctrl = tk.Frame(right, bg=C["card"]); ctrl.pack(anchor="e", pady=3)
        sv = tk.StringVar(value=self.job["status"])
        cb = ttk.Combobox(ctrl, textvariable=sv, values=STATUS_OPTIONS,
                          width=13, font=("Segoe UI", 8), state="readonly")
        cb.pack(side="left", padx=(0, 4))
        cb.bind("<<ComboboxSelected>>",
                lambda e: on_status_change(self.job["id"], sv.get()))

        del_btn = tk.Label(ctrl, text="🗑", font=("Segoe UI", 12),
                           bg=C["card"], fg=C["red"], cursor="hand2")
        del_btn.pack(side="left")
        del_btn.bind("<Button-1>", lambda e: on_delete(self.job["id"]))

        sep(self).pack(fill="x")


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN APP
# ──────────────────────────────────────────────────────────────────────────────

class ScanOptionsDialog(tk.Toplevel):
    """Dialog shown before scanning — lets user pick mode, filter, and days."""

    SCAN_MODES = [
        ("All emails",              "all"),
        ("Applied / Responses only","applied"),
    ]
    SCAN_FILTERS = [
        ("Everything",              "all"),
        ("Applied confirmations",   "application_sent"),
        ("Rejections",              "rejected"),
        ("Interviews",              "interview"),
        ("OA / Assessments",        "oa"),
        ("Offers",                  "offer"),
        ("Job Opportunities",       "opportunity"),
    ]

    def __init__(self, parent, accounts, on_start):
        super().__init__(parent)
        self.title("Scan Options")
        self.configure(bg=C["bg"])
        self.geometry("420x420")
        self.resizable(False, False)
        self.grab_set()
        self.on_start  = on_start
        self.accounts  = accounts
        self._build()

    def _build(self):
        tk.Label(self, text="🔍  Scan Options", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(pady=(18, 4))
        sep(self).pack(fill="x", padx=20)

        f = tk.Frame(self, bg=C["bg"]); f.pack(fill="x", padx=24, pady=10)

        # Days back
        tk.Label(f, text="Scan how far back:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"]).grid(row=0, column=0, sticky="w", pady=6)
        self.days_var = tk.StringVar(value=db.get_setting("days_back", "30"))
        days_f = tk.Frame(f, bg=C["bg"]); days_f.grid(row=0, column=1, sticky="w", padx=8)
        tk.Entry(days_f, textvariable=self.days_var, font=("Segoe UI", 9),
                 bg=C["card2"], fg=C["text"], insertbackground=C["accent"],
                 relief="flat", width=6).pack(side="left")
        tk.Label(days_f, text=" days", font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["sub"]).pack(side="left")

        sep(f, color=C["border"]).grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)

        # Scan mode
        tk.Label(f, text="Scan mode:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"]).grid(row=2, column=0, sticky="nw", pady=4)
        self.mode_var = tk.StringVar(value="applied")
        mf = tk.Frame(f, bg=C["bg"]); mf.grid(row=2, column=1, sticky="w", padx=8)
        for label, val in self.SCAN_MODES:
            tk.Radiobutton(mf, text=label, variable=self.mode_var, value=val,
                           font=("Segoe UI", 9), bg=C["bg"], fg=C["text"],
                           selectcolor=C["card2"], activebackground=C["bg"],
                           activeforeground=C["accent"]).pack(anchor="w")

        tk.Label(f, text="  Applied only = faster, skips newsletters",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["dim"]).grid(
                 row=3, column=0, columnspan=2, sticky="w")

        sep(f, color=C["border"]).grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)

        # What to look for
        tk.Label(f, text="Look for:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["sub"]).grid(row=5, column=0, sticky="nw", pady=4)
        self.filter_var = tk.StringVar(value="all")
        ff = tk.Frame(f, bg=C["bg"]); ff.grid(row=5, column=1, sticky="w", padx=8)
        for label, val in self.SCAN_FILTERS:
            tk.Radiobutton(ff, text=label, variable=self.filter_var, value=val,
                           font=("Segoe UI", 9), bg=C["bg"], fg=C["text"],
                           selectcolor=C["card2"], activebackground=C["bg"],
                           activeforeground=C["accent"]).pack(anchor="w")

        sep(self).pack(fill="x", padx=20, pady=8)

        bf = tk.Frame(self, bg=C["bg"]); bf.pack(pady=4)
        Btn(bf, "🔍 Start Scan", cmd=self._start,
            bg=C["green"], w=140, h=32).pack(side="left", padx=6)
        Btn(bf, "Cancel", cmd=self.destroy,
            bg=C["card2"], fg=C["text"], w=90, h=32).pack(side="left", padx=6)

    def _start(self):
        try:
            days = int(self.days_var.get())
        except ValueError:
            days = 30
        creds = db.get_setting("credentials_path", "")
        self.destroy()
        self.on_start(self.accounts, creds, days,
                      self.mode_var.get(), self.filter_var.get())


class JobTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.title("JobTracker — Gmail Job Application Manager")
        self.geometry("1150x740")
        self.configure(bg=C["bg"])
        self.minsize(920, 600)
        self._current_account = "All Accounts"
        self._setup_styles()
        self._build_ui()
        self._load_jobs()
        self._scheduler_running = True
        threading.Thread(target=self._scheduler_loop, daemon=True).start()

    def _setup_styles(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("TCombobox",
                    fieldbackground=C["card2"], background=C["card2"],
                    foreground=C["text"], selectbackground=C["accent"],
                    borderwidth=0)
        s.configure("Vertical.TScrollbar",
                    background=C["card2"], troughcolor=C["bg"],
                    borderwidth=0, arrowcolor=C["dim"])

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Sidebar ──────────────────────────────────────────────────────
        self.sb = tk.Frame(self, bg=C["card"], width=230)
        self.sb.pack(side="left", fill="y"); self.sb.pack_propagate(False)

        # Logo
        logo = tk.Frame(self.sb, bg=C["card"], pady=18, padx=14)
        logo.pack(fill="x")
        tk.Label(logo, text="📊", font=("Segoe UI", 26), bg=C["card"]).pack(side="left")
        tf = tk.Frame(logo, bg=C["card"]); tf.pack(side="left", padx=8)
        tk.Label(tf, text="JobTracker", font=("Segoe UI", 14, "bold"),
                 bg=C["card"], fg=C["text"]).pack(anchor="w")
        tk.Label(tf, text="Gmail Powered", font=("Segoe UI", 8),
                 bg=C["card"], fg=C["sub"]).pack(anchor="w")

        sep(self.sb, orient="h").pack(fill="x", padx=10)

        # Account switcher
        self.acct_frame = tk.Frame(self.sb, bg=C["card"], pady=8, padx=14)
        self.acct_frame.pack(fill="x")
        self._build_account_switcher()

        sep(self.sb, orient="h").pack(fill="x", padx=10)

        # Stats
        self.stats_frame = tk.Frame(self.sb, bg=C["card"], pady=8, padx=14)
        self.stats_frame.pack(fill="x")
        self._refresh_stats()

        sep(self.sb, orient="h").pack(fill="x", padx=10)

        # Nav / filters
        nav = tk.Frame(self.sb, bg=C["card"], pady=6)
        nav.pack(fill="x")
        self.filter_var = tk.StringVar(value="All")
        self._nav_btns = []
        filters = [
            ("All",                "All"),
            ("Applied",            "Applied"),
            ("In Progress",        "In Progress"),
            ("Rejected",           "Rejected"),
            ("Offer",              "Offer Received"),
            ("💡 Opportunities",   "Job Opportunity"),
        ]
        for label, val in filters:
            b = tk.Label(nav, text=f"   {label}", font=("Segoe UI", 10),
                         bg=C["card"], fg=C["sub"], anchor="w",
                         pady=7, cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, v=val, b=b: self._filter(v, b))
            b.bind("<Enter>",  lambda e, b=b: b.configure(bg=C["hover"]))
            b.bind("<Leave>",  lambda e, b=b: self._nav_leave(b))
            self._nav_btns.append((b, val))

        sep(self.sb, orient="h").pack(fill="x", padx=10, pady=4)

        # Action buttons
        ab = tk.Frame(self.sb, bg=C["card"], padx=14, pady=6)
        ab.pack(fill="x")
        Btn(ab, "➕  Add Job",       cmd=self._add_job,
            bg=C["accent"],  w=186, h=30).pack(pady=3)
        self._scan_btn_ref = Btn(ab, "🔍  Scan Gmail",    cmd=self._scan,
            bg=C["green"],   w=186, h=30)
        self._scan_btn_ref.pack(pady=3)
        self._stop_btn_ref = Btn(ab, "⏹  Stop Scan",     cmd=self._stop_scan,
            bg=C["red"],     w=186, h=30)
        # stop button hidden until scan starts
        Btn(ab, "⚙  Settings",      cmd=self._settings,
            bg=C["card2"], fg=C["text"], w=186, h=30).pack(pady=3)

        # Last scan label (bottom of sidebar)
        self.scan_lbl = tk.Label(self.sb, text="", font=("Segoe UI", 8),
                                 bg=C["card"], fg=C["dim"],
                                 wraplength=200, justify="left")
        self.scan_lbl.pack(side="bottom", padx=12, pady=8, anchor="w")
        ls = db.get_setting("last_scan_time", "Never")
        self.scan_lbl.configure(text=f"Last scan: {ls}")

        # ── Main area ─────────────────────────────────────────────────────
        main = tk.Frame(self, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        # Top bar
        top = tk.Frame(main, bg=C["bg"], pady=14, padx=18)
        top.pack(fill="x")
        self.title_lbl = tk.Label(top, text="All Applications",
                                  font=("Segoe UI", 17, "bold"),
                                  bg=C["bg"], fg=C["text"])
        self.title_lbl.pack(side="left")

        # Search
        sf = tk.Frame(top, bg=C["card2"], padx=8, pady=4)
        sf.pack(side="right", padx=4)
        tk.Label(sf, text="🔎", font=("Segoe UI", 10),
                 bg=C["card2"], fg=C["sub"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._load_jobs())
        tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 10),
                 bg=C["card2"], fg=C["text"], insertbackground=C["accent"],
                 relief="flat", width=26).pack(side="left", padx=4)

        # Scrollable job list
        lc = tk.Frame(main, bg=C["bg"])
        lc.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self.canvas = tk.Canvas(lc, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(lc, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=C["bg"])
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._canvas_win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        # Keep inner frame same width as canvas so cards fill properly
        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(self._canvas_win, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Progress label
        self.prog_var = tk.StringVar(value="")
        tk.Label(main, textvariable=self.prog_var, font=("Segoe UI", 8),
                 bg=C["bg"], fg=C["accent"]).pack(side="bottom", anchor="w", padx=18, pady=4)

    def _build_account_switcher(self):
        for w in self.acct_frame.winfo_children():
            w.destroy()
        tk.Label(self.acct_frame, text="Account", font=("Segoe UI", 8, "bold"),
                 bg=C["card"], fg=C["dim"]).pack(anchor="w")

        accounts_raw = db.get_setting("gmail_accounts", "")
        accounts = [a.strip() for a in accounts_raw.split("\n") if a.strip()]
        all_accounts = ["All Accounts"] + accounts

        self.acct_var = tk.StringVar(value=self._current_account)
        cb = ttk.Combobox(self.acct_frame, textvariable=self.acct_var,
                          values=all_accounts, width=24,
                          font=("Segoe UI", 9), state="readonly")
        cb.pack(anchor="w", pady=3)
        cb.bind("<<ComboboxSelected>>", lambda e: self._switch_account())

    def _switch_account(self):
        self._current_account = self.acct_var.get()
        self._refresh_stats()
        self._load_jobs()

    # ── Stats ─────────────────────────────────────────────────────────────

    def _refresh_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        stats = db.get_stats(self._current_account)
        tk.Label(self.stats_frame, text="Overview", font=("Segoe UI", 8, "bold"),
                 bg=C["card"], fg=C["dim"]).pack(anchor="w")
        items = [
            ("Total",           stats.get("total", 0),                 C["text"]),
            ("Applied",         stats.get("Applied", 0),               C["accent"]),
            ("In Progress",     stats.get("In Progress", 0),           C["green"]),
            ("Rejected",        stats.get("Rejected", 0),              C["red"]),
            ("Offer",           stats.get("Offer Received", 0),        C["yellow"]),
            ("💡 Opportunities", stats.get("Job Opportunity", 0),      C["teal"]),
        ]
        for label, count, color in items:
            r = tk.Frame(self.stats_frame, bg=C["card"]); r.pack(fill="x", pady=1)
            tk.Label(r, text=label, font=("Segoe UI", 9),
                     bg=C["card"], fg=C["sub"]).pack(side="left")
            tk.Label(r, text=str(count), font=("Segoe UI", 9, "bold"),
                     bg=C["card"], fg=color).pack(side="right")

    # ── Nav helpers ───────────────────────────────────────────────────────

    def _nav_leave(self, btn):
        active = self.filter_var.get()
        for b, v in self._nav_btns:
            if b is btn:
                b.configure(bg=C["accent"] if v == active else C["card"])
                return

    def _filter(self, val, btn):
        self.filter_var.set(val)
        for b, v in self._nav_btns:
            b.configure(bg=C["accent"] if v == val else C["card"],
                        fg=C["bg"] if v == val else C["sub"])
        title_map = {"All": "All Applications", "Applied": "Applied",
                     "In Progress": "In Progress", "Rejected": "Rejected",
                     "Offer Received": "Offers 🎉", "Job Opportunity": "💡 Job Opportunities"}
        self.title_lbl.configure(text=title_map.get(val, val))
        self._load_jobs()

    # ── Job list ──────────────────────────────────────────────────────────

    def _load_jobs(self):
        for w in self.inner.winfo_children():
            w.destroy()

        fv  = self.filter_var.get()
        srch = self.search_var.get().strip()
        acct = self._current_account

        jobs = db.get_all_jobs(
            filter_status=fv if fv != "All" else None,
            search_query=srch or None,
            filter_account=acct if acct != "All Accounts" else None,
        )

        if not jobs:
            tk.Label(self.inner,
                     text="No applications found.\n\nClick ➕ Add Job or 🔍 Scan Gmail to get started.",
                     font=("Segoe UI", 12), bg=C["bg"], fg=C["dim"],
                     justify="center").pack(pady=80)
            self._refresh_stats()
            return

        for job in jobs:
            card = JobCard(self.inner, job,
                           on_click=self._open_detail,
                           on_delete=self._delete_job,
                           on_status_change=self._quick_status)
            card.pack(fill="x", pady=(0, 2))

        self._refresh_stats()
        # Force canvas to recalculate scroll region after populating
        self.inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _open_detail(self, job_id):
        JobDetailWindow(self, job_id, on_update=self._load_jobs)

    def _delete_job(self, job_id):
        if messagebox.askyesno("Delete", "Delete this application and all related email history?"):
            db.delete_job(job_id)
            self._load_jobs()

    def _quick_status(self, job_id, status):
        db.update_job_status(job_id, status=status)
        self._load_jobs()

    # ── Dialogs ───────────────────────────────────────────────────────────

    def _add_job(self):
        raw = db.get_setting("gmail_accounts", "")
        accounts = [a.strip() for a in raw.split("\n") if a.strip()]
        AddJobDialog(self, accounts, on_save=self._load_jobs)

    def _settings(self):
        SettingsDialog(self, on_save=self._on_settings_saved, app_ref=self)

    def _on_settings_saved(self):
        self._build_account_switcher()
        self._load_jobs()

    # ── Scanning ──────────────────────────────────────────────────────────

    def _stop_scan(self):
        """Signal the running scan to stop after the current email."""
        self._scan_stop_flag = True
        self.prog_var.set("⏹ Stopping… finishing current email…")

    def _scan(self):
        creds = db.get_setting("credentials_path", "")
        raw   = db.get_setting("gmail_accounts", "")
        accounts = [a.strip() for a in raw.split("\n") if a.strip()]

        if not creds or not os.path.exists(creds):
            messagebox.showerror("Setup Required",
                "Please set your credentials.json in ⚙ Settings first.")
            return
        if not accounts:
            messagebox.showerror("No Accounts",
                "Add at least one Gmail address in ⚙ Settings.")
            return

        ScanOptionsDialog(self, accounts, on_start=self._start_scan)

    def _start_scan(self, accounts, creds_path, days_back, scan_mode, scan_filter):
        """Called by ScanOptionsDialog when user clicks Scan."""
        self._scan_stop_flag = False
        self._scan_btn_ref.pack_forget()
        self._stop_btn_ref.pack(pady=3)
        threading.Thread(
            target=self._scan_worker,
            args=(accounts, creds_path, days_back, scan_mode, scan_filter),
            daemon=True
        ).start()

    def _scan_worker(self, accounts, creds_path, days_back, scan_mode, scan_filter):
        try:
            import gmail_scanner
        except ImportError:
            self.after(0, self._show_install_dialog)
            return

        total_new = total_upd = 0

        for acct in accounts:
            self.after(0, lambda a=acct: self.prog_var.set(f"🔍 Scanning {a}…"))
            try:
                def cb(msg):
                    self.after(0, lambda m=msg: self.prog_var.set(m))
                n, u = gmail_scanner.scan_account(
                    acct, creds_path, days_back, cb,
                    scan_mode=scan_mode,
                    scan_filter=scan_filter,
                    stop_flag=lambda: self._scan_stop_flag,
                )
                total_new += n; total_upd += u
            except ImportError:
                self.after(0, self._show_install_dialog)
                return
            except Exception as e:
                self.after(0, lambda err=str(e), a=acct: messagebox.showerror(
                    "Scan Error", f"Error scanning {a}:\n{err}"))

            if self._scan_stop_flag:
                break

        stopped = self._scan_stop_flag
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        db.set_setting("last_scan_time", now)
        suffix = " (stopped early)" if stopped else ""
        self.after(0, lambda: self.scan_lbl.configure(text=f"Last scan: {now}"))
        self.after(0, lambda: self.prog_var.set(
            f"{'⏹' if stopped else '✅'} Done{suffix} — {total_new} new, {total_upd} updates"))
        self.after(0, self._load_jobs)
        # Restore scan button
        self.after(0, self._stop_btn_ref.pack_forget)
        self.after(0, lambda: self._scan_btn_ref.pack(pady=3))

    def _show_install_dialog(self):
        """Clear dialog when Google libraries are missing, with one-click auto-install."""
        win = tk.Toplevel(self)
        win.title("Install Required Libraries")
        win.configure(bg=C["bg"])
        win.geometry("520x320")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="⚠  Missing Libraries", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["yellow"]).pack(pady=(24, 4))
        tk.Label(win,
                 text="The Google Gmail libraries are not installed yet.\nClick the button below to install them automatically.",
                 font=("Segoe UI", 10), bg=C["bg"], fg=C["sub"],
                 justify="center").pack(pady=4)

        sep(win).pack(fill="x", padx=24, pady=10)

        cmd_frame = tk.Frame(win, bg=C["card2"], padx=12, pady=8)
        cmd_frame.pack(fill="x", padx=24)
        tk.Label(cmd_frame, text="Or paste this into Command Prompt manually:",
                 font=("Segoe UI", 8), bg=C["card2"], fg=C["dim"]).pack(anchor="w")
        pip_cmd = "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        cmd_txt = tk.Text(cmd_frame, height=2, font=("Courier New", 8),
                          bg=C["card"], fg=C["teal"], relief="flat", wrap="word")
        cmd_txt.pack(fill="x", pady=4)
        cmd_txt.insert("1.0", pip_cmd)
        cmd_txt.configure(state="disabled")

        status_var = tk.StringVar(value="")
        tk.Label(win, textvariable=status_var, font=("Segoe UI", 9),
                 bg=C["bg"], fg=C["green"]).pack(pady=4)

        install_btn = [None]  # mutable ref

        def do_install():
            install_btn[0].update_text("Installing…")
            status_var.set("⏳ Installing, please wait…")
            win.update()

            def run_pip():
                import subprocess, sys
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install",
                         "google-auth", "google-auth-oauthlib",
                         "google-auth-httplib2", "google-api-python-client"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        self.after(0, lambda: status_var.set(
                            "✅ Installed! Close this window and click Scan Gmail again."))
                        self.after(0, lambda: install_btn[0].update_text("✅ Done"))
                    else:
                        err = (result.stderr or "Unknown error")[-200:]
                        self.after(0, lambda: status_var.set(f"❌ Failed: {err}"))
                        self.after(0, lambda: install_btn[0].update_text("Retry"))
                except Exception as e:
                    self.after(0, lambda: status_var.set(f"❌ Error: {str(e)[:120]}"))
                    self.after(0, lambda: install_btn[0].update_text("Retry"))

            threading.Thread(target=run_pip, daemon=True).start()

        b = Btn(win, "⬇  Install Google Libraries Now",
                cmd=do_install, bg=C["accent"], fg=C["bg"], w=260, h=34, fs=11)
        b.pack(pady=10)
        install_btn[0] = b

        Btn(win, "Close", cmd=win.destroy,
            bg=C["card2"], fg=C["text"], w=90, h=28).pack()

    def _scheduler_loop(self):
        import time
        while self._scheduler_running:
            scan_time = db.get_setting("scan_time", "08:00")
            now = datetime.now().strftime("%H:%M")
            if now == scan_time:
                creds = db.get_setting("credentials_path", "")
                raw   = db.get_setting("gmail_accounts", "")
                accounts = [a.strip() for a in raw.split("\n") if a.strip()]
                if creds and accounts:
                    self.after(0, lambda: self._scan_worker(accounts, creds))
                time.sleep(62)
            time.sleep(28)

    def on_close(self):
        self._scheduler_running = False
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────

def main():
    app = JobTrackerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()