"""The Matchday Bridge window: a dark, card-style tkinter UI (shapes antialiased with Pillow).

    View(root)                     header, match card, progress steps, message, buttons, footer
    view.idle(title, body)         no fixture: placeholder card
    view.fixture(home, away, ...)  team names/abbreviations, which one is yours, competition line
    view.score(hg, ag, label)      big score in the card ("LIVE 63'", "FULL TIME")
    view.step(i)                   progress: 0 squads, 1 launch, 2 teams, 3 play, 4 saved (-1 none, 5 all done)
    view.message(title, body, detail, tone)
    view.buttons(play, sim)        enable/disable the two choices
All methods must run on the Tk thread.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import tkinter as tk
from collections import OrderedDict
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageTk

BG, PANEL, CARD, LINE = "#0b1220", "#0f1830", "#141f3a", "#26355a"
TEXT, MUTED, DIM = "#e8eef8", "#8d9dbb", "#5b6a8a"
GREEN, GREEN_HI, GREEN_LO = "#22c55e", "#3ddc78", "#14532d"
AMBER, RED, BLUE = "#f5a524", "#f05252", "#4ea8ff"
TONES = {"ok": GREEN, "busy": BLUE, "warn": AMBER, "error": RED, "idle": MUTED}
CREST = ["#e5484d", "#f76b15", "#ffc53d", "#30a46c", "#12a594", "#0090ff", "#6e56cf", "#d6409f", "#8e4ec6", "#3e63dd"]
STEPS = ["Squads", "Launch", "Teams", "Play", "Saved"]


def _family(*names: str) -> str:
    have = set(tkfont.families())
    return next((n for n in names if n in have), "Segoe UI")


class Smooth:
    """Antialiased shapes on tk canvases. Tk draws ovals, arcs and smoothed polygons without antialiasing (jagged
    edges), so these are painted by Pillow at 4x size, downsampled and placed as images; text stays Tk's own.
    Images are cached by shape (the spinner and the pulsing dot are quantized), and each canvas keeps the ones it
    shows until its next begin(), so a cache eviction never blanks a shape on screen. Coordinates and the outline
    straddling the path follow Tk's create_oval / create_arc."""
    SS = 4

    def __init__(self, limit: int = 300):
        self.cache: OrderedDict = OrderedDict()
        self.limit = limit

    @staticmethod
    def begin(c: tk.Canvas):
        c._smooth_keep = []

    @staticmethod
    def _rgba(col):
        return None if not col else (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16), 255)

    def _place(self, c, key, box, width, paint):
        x1, y1, x2, y2 = box
        pad = width / 2 + 1
        ox, oy = math.floor(x1 - pad), math.floor(y1 - pad)
        w, h = math.ceil(x2 + pad) - ox, math.ceil(y2 + pad) - oy
        key = key + (round(x1 - ox, 2), round(y1 - oy, 2), round(x2 - x1, 2), round(y2 - y1, 2), width)
        ph = self.cache.get(key)
        if ph is None:
            k = self.SS
            im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
            e = width / 2                                        # Tk strokes are centred on the path
            paint(ImageDraw.Draw(im), [(x1 - ox - e) * k, (y1 - oy - e) * k, (x2 - ox + e) * k, (y2 - oy + e) * k],
                  max(1, round(width * k)))
            ph = ImageTk.PhotoImage(im.resize((w, h), Image.BOX))
            self.cache[key] = ph
            if len(self.cache) > self.limit:
                self.cache.popitem(last=False)
        else:
            self.cache.move_to_end(key)
        getattr(c, "_smooth_keep", []).append(ph)
        return c.create_image(ox, oy, image=ph, anchor="nw")

    def oval(self, c, x1, y1, x2, y2, fill=None, outline=None, width=0):
        width = width if outline else 0
        return self._place(c, ("oval", fill, outline), (x1, y1, x2, y2), width,
                           lambda d, b, wd: d.ellipse(b, fill=self._rgba(fill), outline=self._rgba(outline),
                                                      width=wd if outline else 0))

    def rrect(self, c, x1, y1, x2, y2, r, fill=None, outline=None, width=0):
        width = width if outline else 0
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        return self._place(c, ("rrect", r, fill, outline), (x1, y1, x2, y2), width,
                           lambda d, b, wd: d.rounded_rectangle(b, radius=(r + width / 2) * self.SS,
                                                                fill=self._rgba(fill), outline=self._rgba(outline),
                                                                width=wd if outline else 0))

    def _points(self, c, kind, pts, color, width, paint):
        """Shapes given as canvas points (polygon, polyline): painted relative to their bounding box."""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x1, y1 = min(xs), min(ys)
        rel = tuple((round(x - x1, 2), round(y - y1, 2)) for x, y in pts)
        k, e = self.SS, width / 2

        def draw(d, b, wd):
            ip = [(b[0] + (e + x) * k, b[1] + (e + y) * k) for x, y in rel]
            paint(d, ip, wd)
        return self._place(c, (kind, color, rel), (x1, y1, max(xs), max(ys)), width, draw)

    def polygon(self, c, pts, fill):
        return self._points(c, "polygon", pts, fill, 0, lambda d, ip, wd: d.polygon(ip, fill=self._rgba(fill)))

    def polyline(self, c, pts, fill, width):
        """A stroke with round joints and caps (a check mark)."""
        def paint(d, ip, wd):
            d.line(ip, fill=self._rgba(fill), width=wd, joint="curve")
            for x, y in (ip[0], ip[-1]):
                d.ellipse([x - wd / 2, y - wd / 2, x + wd / 2, y + wd / 2], fill=self._rgba(fill))
        return self._points(c, "polyline", pts, fill, width, paint)

    def check(self, c, cx, cy, size, fill, width):
        """Check mark centred on (cx, cy), `size` wide."""
        return self.polyline(c, [(cx - 0.30 * size, cy + 0.02 * size), (cx - 0.08 * size, cy + 0.24 * size),
                                 (cx + 0.32 * size, cy - 0.22 * size)], fill, width)

    def play(self, c, cx, cy, size, fill):
        """Play triangle centred on (cx, cy), `size` high."""
        h, w = size / 2, size * 0.87
        return self.polygon(c, [(cx - w / 2, cy - h), (cx + w / 2, cy), (cx - w / 2, cy + h)], fill)

    def arc(self, c, x1, y1, x2, y2, start, extent, outline, width=1):
        """Tk angles: degrees counter-clockwise from 3 o'clock (Pillow goes clockwise)."""
        start, extent = round(start) % 360, round(extent)
        return self._place(c, ("arc", start, extent, outline), (x1, y1, x2, y2), width,
                           lambda d, b, wd: d.arc(b, -(start + extent), -start, fill=self._rgba(outline), width=wd))


_smooth: Smooth | None = None


def smooth() -> Smooth:
    global _smooth
    if _smooth is None:
        _smooth = Smooth()
    return _smooth


def crest_color(name: str) -> str:
    return CREST[int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(CREST)]


def initials(name: str, abbr: str = "") -> str:
    if abbr:
        return abbr[:3].upper()
    words = [w for w in name.replace("-", " ").split() if w[:1].isalpha() and w.upper() not in ("FC", "AFC", "CF", "SC")]
    if len(words) >= 2:
        return "".join(w[0] for w in words[:3]).upper()
    return (words[0][:3] if words else name[:3]).upper()


class Button(tk.Canvas):
    """Rounded button drawn on a canvas: 'primary' (filled green) or 'ghost' (outlined)."""

    def __init__(self, master, text: str, command, kind: str = "primary", width: int = 220, height: int = 46,
                 scale: float = 1.0, fonts=None):
        super().__init__(master, width=int(width * scale), height=int(height * scale), bg=master["bg"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.command, self.kind, self.s = text, command, kind, scale
        self.icon = text.startswith("▶")            # drawn as a shape: the font has no smooth ▶ glyph
        if self.icon:
            self.text = text.lstrip("▶").strip()
        self.font = fonts["button"]
        self.enabled, self.hover = True, False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False))
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._draw()

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on: bool):
        self.configure(cursor="hand2" if on else "arrow")
        self._set(enabled=on)

    def _draw(self):
        self.delete("all")
        sm = smooth()
        sm.begin(self)
        w, h = int(self["width"]), int(self["height"])
        if self.kind == "primary":
            fill = (GREEN_HI if self.hover else GREEN) if self.enabled else "#1d3b2a"
            fg = "#06210f" if self.enabled else "#4f7a60"
            sm.rrect(self, 1, 1, w - 1, h - 1, 12 * self.s, fill=fill)
        else:
            fill = "#1a2747" if self.hover and self.enabled else BG
            edge = (MUTED if self.hover else LINE) if self.enabled else "#1c2742"
            fg = TEXT if self.enabled else DIM
            sm.rrect(self, 1.5, 1.5, w - 1.5, h - 1.5, 12 * self.s, fill=fill, outline=edge,
                     width=max(1.0, 1.5 * self.s))
        if self.icon:
            size, gap = 11 * self.s, 10 * self.s
            tw = tkfont.Font(font=self.font).measure(self.text)
            x = (w - (size * 0.87 + gap + tw)) / 2
            sm.play(self, x + size * 0.87 / 2, h / 2, size, fg)
            self.create_text(x + size * 0.87 + gap, h / 2, text=self.text, fill=fg, font=self.font, anchor="w")
        else:
            self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)


class View:
    def __init__(self, root: tk.Tk, app: str, on_play, on_sim):
        self.root = root
        try:
            self.s = max(1.0, root.winfo_fpixels("1i") / 96)
        except tk.TclError:
            self.s = 1.0
        S = self.S
        ui = _family("Segoe UI Variable Text", "Segoe UI")
        disp = _family("Segoe UI Variable Display", "Segoe UI")
        self.f = {
            "brand": (disp, 15, "bold"), "sub": (ui, 9), "pill": (ui, 9, "bold"),
            "comp": (ui, 9, "bold"), "team": (disp, 13, "bold"), "crest": (disp, 15, "bold"),
            "score": (disp, 40, "bold"), "vs": (disp, 20, "bold"), "state": (ui, 9, "bold"),
            "you": (ui, 8, "bold"), "step": (ui, 9), "title": (disp, 15, "bold"), "body": (ui, 11),
            "detail": (ui, 9), "button": (ui, 11, "bold"), "foot": (ui, 8),
        }
        root.title(app)
        root.configure(bg=BG)
        root.geometry(f"{S(680)}x{S(640)}")
        root.minsize(S(600), S(600))
        self._dark_titlebar()
        self._icon()

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=S(24), pady=(S(20), S(12)))
        brand = tk.Frame(head, bg=BG)
        brand.pack(side="left")
        tk.Label(brand, text="MATCHDAY BRIDGE", font=self.f["brand"], fg=TEXT, bg=BG).pack(anchor="w")
        tk.Label(brand, text="Football Manager 2024  ×  SP Football Life 2026", font=self.f["sub"], fg=MUTED,
                 bg=BG).pack(anchor="w")
        self.pill = tk.Canvas(head, width=S(190), height=S(30), bg=BG, highlightthickness=0)
        self.pill.pack(side="right")
        self._pill = ("Starting", "idle")

        self.card = tk.Canvas(root, height=S(210), bg=BG, highlightthickness=0)
        self.card.pack(fill="x", padx=S(24))
        self.card.bind("<Configure>", lambda e: self._draw_card())
        self.steps = tk.Canvas(root, height=S(64), bg=BG, highlightthickness=0)
        self.steps.pack(fill="x", padx=S(24), pady=(S(14), 0))
        self.steps.bind("<Configure>", lambda e: self._draw_steps())

        msg = tk.Frame(root, bg=BG)
        msg.pack(fill="both", expand=True, padx=S(28), pady=(S(8), 0))
        self.title_var, self.body_var, self.detail_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.title_lbl = tk.Label(msg, textvariable=self.title_var, font=self.f["title"], fg=TEXT, bg=BG,
                                  anchor="w", justify="left")
        self.title_lbl.pack(fill="x")
        self.body_lbl = tk.Label(msg, textvariable=self.body_var, font=self.f["body"], fg="#c9d4e8", bg=BG,
                                 anchor="w", justify="left", wraplength=S(620))
        self.body_lbl.pack(fill="x", pady=(S(4), 0))
        self.detail_lbl = tk.Label(msg, textvariable=self.detail_var, font=self.f["detail"], fg=MUTED, bg=BG,
                                   anchor="w", justify="left", wraplength=S(620))
        self.detail_lbl.pack(fill="x", pady=(S(6), 0))
        msg.bind("<Configure>", lambda e: [lbl.configure(wraplength=max(200, e.width - 8))
                                           for lbl in (self.body_lbl, self.detail_lbl)])

        bar = tk.Frame(root, bg=BG, height=S(48))
        bar.pack(fill="x", padx=S(24), pady=(S(10), S(8)))
        self.play_btn = Button(bar, "▶  Play in SPFL26", on_play, "primary", 250, 48, self.s, self.f)
        self.sim_btn = Button(bar, "Let FM24 simulate", on_sim, "ghost", 200, 48, self.s, self.f)

        foot = tk.Frame(root, bg=BG)
        foot.pack(fill="x", side="bottom", padx=S(24), pady=(0, S(12)))
        self.foot_var = tk.StringVar()
        tk.Label(foot, textvariable=self.foot_var, font=self.f["foot"], fg=DIM, bg=BG, anchor="w").pack(side="left")

        self.home = self.away = None
        self.score_text, self.state_text, self.state_tone = None, "", "idle"
        self.placeholder = ("Waiting for match day", "")
        self.active, self.failed_step = -1, None
        self.phase = 0.0
        self.buttons(False, False)
        self._tick()

    def S(self, px: float) -> int:
        return int(round(px * self.s))

    # ------------------------------------------------------------------ window chrome
    def _dark_titlebar(self):
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            on = ctypes.c_int(1)
            for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 11 / older Windows 10)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                    break
        except (OSError, AttributeError):
            pass

    def _icon(self):
        try:
            n = 64
            img = tk.PhotoImage(width=n, height=n)
            rows = []
            for y in range(n):
                row = []
                for x in range(n):
                    dx, dy = x - n / 2 + 0.5, y - n / 2 + 0.5
                    d = math.hypot(dx, dy)
                    if d > 30:
                        row.append(BG)
                    elif d > 26 or abs(dx) < 2 or 9 < d < 13:
                        row.append("#ffffff")
                    else:
                        row.append(GREEN if (int((x + 4) / 8) % 2) else "#1aa34a")
                rows.append("{" + " ".join(row) + "}")
            img.put(" ".join(rows))
            self.root.iconphoto(True, img)
            self._icon_img = img
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ public API
    def status(self, text: str, tone: str = "idle"):
        self._pill = (text, tone)
        self._draw_pill()

    def idle(self, title: str, sub: str = ""):
        self.home = self.away = None
        self.score_text, self.state_text = None, ""
        self.placeholder = (title, sub)
        self._draw_card()

    def fixture(self, home: dict, away: dict, comp: str = ""):
        """home/away: {"name", "abbr", "human"}."""
        self.home, self.away, self.comp = home, away, comp
        self.score_text, self.state_text, self.state_tone = None, "", "idle"
        self._draw_card()

    def score(self, hg: int | None, ag: int | None, state: str = "", tone: str = "idle"):
        self.score_text = None if hg is None else f"{hg}  –  {ag}"
        self.state_text, self.state_tone = state, tone
        self._draw_card()

    def step(self, i: int, failed: bool = False):
        self.active, self.failed_step = i, (i if failed else None)
        self._draw_steps()

    def message(self, title: str, body: str = "", detail: str = ""):
        self.title_var.set(title)
        self.body_var.set(body)
        self.detail_var.set(detail)

    def detail(self, text: str):
        self.detail_var.set(text)

    def footer(self, text: str):
        self.foot_var.set(text)

    def buttons(self, play: bool, sim: bool):
        self.play_btn.set_enabled(play)
        self.sim_btn.set_enabled(sim)
        if play or sim:
            self.play_btn.pack(side="left")
            self.sim_btn.pack(side="left", padx=(self.S(12), 0))
        else:
            self.play_btn.pack_forget()
            self.sim_btn.pack_forget()

    # ------------------------------------------------------------------ drawing
    def _tick(self):
        self.phase = (self.phase + 0.08) % (2 * math.pi)
        if 0 <= self.active < len(STEPS) and self.failed_step is None:
            self._draw_steps()
        if self.state_tone == "live":
            self._draw_card()
        self.root.after(60, self._tick)

    def _draw_pill(self):
        c, S = self.pill, self.S
        c.delete("all")
        sm = smooth()
        sm.begin(c)
        text, tone = self._pill
        col = TONES.get(tone, MUTED)
        w = int(c["width"])
        tw = tkfont.Font(font=self.f["pill"]).measure(text) + S(38)
        x0 = max(2, w - tw)
        sm.rrect(c, x0, S(2), w - 2, S(28), S(13), fill=PANEL, outline=LINE, width=1)
        sm.oval(c, x0 + S(12), S(11), x0 + S(20), S(19), fill=col)
        c.create_text(x0 + S(27), S(15), text=text, anchor="w", fill=TEXT, font=self.f["pill"])

    def _draw_card(self):
        c, S = self.card, self.S
        c.delete("all")
        sm = smooth()
        sm.begin(c)
        w, h = c.winfo_width(), int(c["height"])
        if w < 50:
            return
        sm.rrect(c, 1, 1, w - 1, h - 1, S(18), fill=CARD, outline=LINE, width=1)
        c.create_rectangle(S(18), 1, w - S(18), S(4), fill=GREEN, outline="")
        if not self.home:
            title, sub = self.placeholder
            cx = w / 2
            sm.oval(c, cx - S(22), S(40), cx + S(22), S(84), outline=LINE, width=S(2))
            c.create_line(cx, S(40), cx, S(84), fill=LINE, width=S(2))
            sm.oval(c, cx - S(7), S(55), cx + S(7), S(69), outline=LINE, width=S(2))
            c.create_text(cx, S(116), text=title, fill=TEXT, font=self.f["team"])
            c.create_text(cx, S(146), text=sub, fill=MUTED, font=self.f["detail"], width=w - S(80), justify="center")
            return
        if self.comp:
            c.create_text(w / 2, S(26), text=self.comp.upper(), fill=MUTED, font=self.f["comp"])
        for side, team in ((0, self.home), (1, self.away)):
            cx = w * (0.2 if side == 0 else 0.8)
            col = crest_color(team["name"])
            r = S(30)
            cy = S(78)
            sm.oval(c, cx - r - S(3), cy - r - S(3), cx + r + S(3), cy + r + S(3), outline=col, width=S(2))
            sm.oval(c, cx - r, cy - r, cx + r, cy + r, fill=col)
            c.create_text(cx, cy, text=initials(team["name"], team.get("abbr", "")), fill="#ffffff",
                          font=self.f["crest"])
            c.create_text(cx, S(132), text=team["name"], fill=TEXT, font=self.f["team"], width=w * 0.34,
                          justify="center")
            c.create_text(cx, S(160), text="HOME" if side == 0 else "AWAY", fill=DIM, font=self.f["you"])
            if team.get("human"):
                tw = S(54)
                sm.rrect(c, cx - tw / 2, S(172), cx + tw / 2, S(192), S(10), fill=GREEN_LO, outline=GREEN, width=1)
                c.create_text(cx, S(182), text="YOU", fill=GREEN_HI, font=self.f["you"])
        mx = w / 2
        if self.score_text:
            c.create_text(mx, S(84), text=self.score_text, fill=TEXT, font=self.f["score"])
        else:
            c.create_text(mx, S(84), text="VS", fill=DIM, font=self.f["vs"])
        if self.state_text:
            live = self.state_tone == "live"
            col = RED if live else TONES.get(self.state_tone, MUTED)
            tw = tkfont.Font(font=self.f["state"]).measure(self.state_text) + S(30 if live else 20)
            sm.rrect(c, mx - tw / 2, S(126), mx + tw / 2, S(150), S(12), fill=PANEL, outline=LINE, width=1)
            x = mx - tw / 2 + S(10)
            if live:
                a = round((0.55 + 0.45 * math.sin(self.phase * 2)) * 12) / 12     # 13 cached shades
                sm.oval(c, x, S(134), x + S(8), S(142), fill=_mix(PANEL, RED, a))
                x += S(14)
            c.create_text(x, S(138), text=self.state_text, anchor="w", fill=col if not live else TEXT,
                          font=self.f["state"])

    def _draw_steps(self):
        c, S = self.steps, self.S
        c.delete("all")
        sm = smooth()
        sm.begin(c)
        w = c.winfo_width()
        if w < 50:
            return
        n = len(STEPS)
        xs = [S(30) + i * (w - S(60)) / (n - 1) for i in range(n)]
        y, r = S(18), S(9)
        for i in range(n - 1):
            done = i < self.active
            c.create_line(xs[i] + r + S(4), y, xs[i + 1] - r - S(4), y, fill=GREEN if done else LINE, width=S(2))
        for i, x in enumerate(xs):
            if self.failed_step == i:
                sm.oval(c, x - r, y - r, x + r, y + r, fill=AMBER)
                c.create_text(x, y, text="!", fill="#2a1a00", font=self.f["pill"])
                col = AMBER
            elif i < self.active:
                sm.oval(c, x - r, y - r, x + r, y + r, fill=GREEN)
                sm.check(c, x, y, r * 1.2, "#06210f", 2.2 * self.s)
                col = TEXT
            elif i == self.active:
                sm.oval(c, x - r, y - r, x + r, y + r, fill=PANEL, outline=BLUE, width=S(2))
                a = round(math.degrees(self.phase) * 3 / 6) * 6               # 60 cached spinner angles
                sm.arc(c, x - r - S(4), y - r - S(4), x + r + S(4), y + r + S(4), -a, 100, BLUE, S(2))
                sm.oval(c, x - S(3), y - S(3), x + S(3), y + S(3), fill=BLUE)
                col = TEXT
            else:
                sm.oval(c, x - r, y - r, x + r, y + r, fill=BG, outline=LINE, width=S(2))
                col = DIM
            c.create_text(x, y + S(26), text=STEPS[i], fill=col, font=self.f["step"])


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


class ChoiceDialog:
    """The match-day question, shown over FM24's window when the player presses Match Preview: FM's window is
    dimmed by a translucent overlay (and disabled by the caller) until one of the two buttons is pressed.

    teams: [{"name", "abbr", "human", "logo": PIL image or None}] home, away. rect: FM's window (x0, y0, x1, y1)
    in screen pixels."""

    def __init__(self, root: tk.Tk, rect, teams, comp: str, on_play, on_sim):
        self.root, self.done = root, False
        self.on_play, self.on_sim = on_play, on_sim
        x0, y0, x1, y1 = rect
        try:
            s = max(1.0, root.winfo_fpixels("1i") / 96)
        except tk.TclError:
            s = 1.0
        S = lambda v: int(round(v * s))
        ui = _family("Segoe UI Variable Text", "Segoe UI")
        disp = _family("Segoe UI Variable Display", "Segoe UI")
        f = {"kicker": (ui, 9, "bold"), "title": (disp, 17, "bold"), "team": (disp, 12, "bold"), "vs": (disp, 18, "bold"),
             "body": (ui, 10), "button": (ui, 11, "bold"), "you": (ui, 8, "bold"), "crest": (disp, 15, "bold")}

        self.shade = tk.Toplevel(root)
        self.shade.overrideredirect(True)
        self.shade.configure(bg="#000000")
        self.shade.attributes("-alpha", 0.6, "-topmost", True)
        self.shade.geometry(f"{x1 - x0}x{y1 - y0}+{x0}+{y0}")

        w, h = S(620), S(360)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="#000000")
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", "#000001")
        except tk.TclError:
            pass
        self.win.geometry(f"{w}x{h}+{(x0 + x1 - w) // 2}+{(y0 + y1 - h) // 2}")
        c = tk.Canvas(self.win, width=w, height=h, bg="#000001", highlightthickness=0)
        c.pack()
        sm = smooth()
        sm.begin(c)
        sm.rrect(c, 1, 1, w - 1, h - 1, S(20), fill=CARD, outline=LINE, width=S(1.5))
        c.create_rectangle(S(24), 1, w - S(24), S(4), fill=GREEN, outline="")
        c.create_text(w / 2, S(30), text=("MATCH DAY  ·  " + comp).upper() if comp else "MATCH DAY", fill=MUTED,
                      font=f["kicker"])
        c.create_text(w / 2, S(58), text="Where do you want to play this one?", fill=TEXT, font=f["title"])
        self.images = []
        for side, team in enumerate(teams):
            cx, cy = w * (0.24 if side == 0 else 0.76), S(132)
            logo = team.get("logo")
            if logo is not None:
                im = logo.copy()
                im.thumbnail((S(84), S(84)), Image.LANCZOS)
                ph = ImageTk.PhotoImage(im)
                self.images.append(ph)
                c.create_image(cx, cy, image=ph)
            else:
                col, r = crest_color(team["name"]), S(36)
                sm.oval(c, cx - r, cy - r, cx + r, cy + r, fill=col)
                c.create_text(cx, cy, text=initials(team["name"], team.get("abbr", "")), fill="#ffffff", font=f["crest"])
            c.create_text(cx, S(194), text=team["name"], fill=TEXT, font=f["team"], width=w * 0.38, justify="center")
            if team.get("human"):
                sm.rrect(c, cx - S(26), S(212), cx + S(26), S(230), S(9), fill=GREEN_LO, outline=GREEN, width=1)
                c.create_text(cx, S(221), text="YOU", fill=GREEN_HI, font=f["you"])
        c.create_text(w / 2, S(132), text="VS", fill=DIM, font=f["vs"])
        c.create_text(w / 2, S(256), text="SP Football Life 2026: you play it, FM24 plays its own match meanwhile and "
                      "takes your score and scorers.", fill=MUTED, font=f["body"], width=w - S(80), justify="center")
        bar = tk.Frame(self.win, bg=CARD)
        c.create_window(w / 2, S(316), window=bar)
        fonts = {"button": f["button"]}
        Button(bar, "▶  Play in SP Football Life 2026", self._play, "primary", 300, 46, s, fonts).pack(side="left")
        Button(bar, "Simulate in FM24", self._sim, "ghost", 190, 46, s, fonts).pack(side="left", padx=(S(12), 0))
        bar.configure(bg=CARD)
        for b in bar.winfo_children():
            b.configure(bg=CARD)
            b._draw()
        self.win.bind("<Return>", lambda e: self._play())
        self.win.bind("<Escape>", lambda e: self._sim())
        self.raise_()

    def raise_(self):
        for t in (self.shade, self.win):
            t.lift()
            t.attributes("-topmost", True)
        try:
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)        # a key event lets SetForegroundWindow work
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except OSError:
            pass
        self.win.focus_force()

    def close(self):
        self.done = True
        for t in (self.win, self.shade):
            try:
                t.destroy()
            except tk.TclError:
                pass

    def _play(self):
        if not self.done:
            self.close()
            self.on_play()

    def _sim(self):
        if not self.done:
            self.close()
            self.on_sim()
