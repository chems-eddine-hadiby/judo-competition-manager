# -*- coding: utf-8 -*-
"""
scoreboard_window.py  –  IJF / Omega Olympic-style scoreboard  (PyQt5)

Matches the reference image exactly:

┌─────────────────────────────────────────────────────────────────────┐
│ [Olympic rings]           dark wood/charcoal header    Ω OMEGA      │
├─────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐   SHIKHALIZADA N                    ┌───────┐          │
│ │  [flag]  │                   1                 │ card  │  WHITE   │
│ │          │                                     │       │  row     │
│  AZE                                             └───────┘          │
├─────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐   URIARTE Sugoi                     ┌───────┐          │
│ │  [flag]  │                   0                 │ card  │  BLUE    │
│  ESP                                             └───────┘   row    │
├─────────────────────────────────────────────────────────────────────┤
│  Round of 32                     0:06                               │
│  -66 kg                                                             │
└─────────────────────────────────────────────────────────────────────┘

White row: near-white (#e8e8e8) background, black text
Blue row:  vivid blue (#1a6fd4) background, white text
Score:     huge black digit (white row) / huge white digit (blue row) — centered
Name:      SURNAME top of each half, full name bottom of blue row
Country:   bold bottom-left of each row
Card:      yellow card graphic top-right
Timer:     huge bright green, bottom bar dark charcoal
"""

from __future__ import annotations
import os
import sys
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSizePolicy, QVBoxLayout,
)
from PyQt5.QtCore import Qt, QRect, QRectF, QPointF
from PyQt5.QtGui  import (
    QPainter, QColor, QFont, QBrush, QPen, QIcon,
    QLinearGradient, QFontMetrics, QKeyEvent,
    QPainterPath, QRadialGradient,
)

# ── Palette ────────────────────────────────────────────────────────────────────
_HDR_TOP    = "#2a2218"   # dark wood / charcoal header top
_HDR_BOT    = "#1a1510"   # header bottom
_WHITE_ROW  = "#e0e0e0"   # white athlete row background
_WHITE_ROW2 = "#f0f0f0"   # highlight
_BLUE_ROW   = "#1060cc"   # blue athlete row background
_BLUE_ROW2  = "#1878e8"   # blue highlight (top)
_DIV_LINE   = "#2a2a2a"   # divider between rows
_BOTTOM_BG  = "#1a1a1a"   # bottom bar background
_BOTTOM_BG2 = "#111111"

_SCORE_W    = "#111111"   # score digit on white row
_SCORE_B    = "#ffffff"   # score digit on blue row
_NAME_W     = "#111111"   # name on white row
_NAME_B     = "#ffffff"   # name on blue row
_CTRY_W     = "#111111"   # country on white row
_CTRY_B     = "#5badff"   # country on blue row (light blue, matching image)

_CARD_FACE  = "#d4b800"   # yellow card face (slightly darker gold)
_CARD_EDGE  = "#8a7000"   # card edge/shadow
_CARD_RED   = "#cc1111"   # red card (hansokumake)

_TIMER_NRM  = "#00cc00"   # green timer (normal)
_TIMER_WRN  = "#ffaa00"   # orange (≤60s)
_TIMER_HOT  = "#ff2020"   # red (≤30s)
_TIMER_GS   = "#FFD600"   # golden (GS)

_WIN_BG     = "#003300"
_WIN_FG     = "#00ee66"

_OSAE_BG    = "#333300"
_OSAE_FILL  = "#FFD600"


def _resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


def _qc(hex_str: str) -> QColor:
    return QColor(hex_str)


# ══════════════════════════════════════════════════════════════════════════════
def _draw_penalty_card(p: QPainter, x: int, y: int, w: int, h: int,
                        face_hex: str, count: int = 1):
    """
    Draw stacked card icon.  count=1 → single card, count=2 → stack of 2, etc.
    The card in the image looks like an upright rectangle slightly tilted
    with a second card peeking behind — we recreate that.
    """
    if count <= 0:
        return

    face   = QColor(face_hex)
    # darker shade for the shadow/back card
    back   = face.darker(140)
    shadow = QColor(0, 0, 0, 100)

    cw = int(w * 0.68)
    ch = int(h * 0.82)

    # back card (offset up-right, darker)
    if count >= 2:
        bx = x + int(w * 0.22)
        by = y
        p.setBrush(QBrush(shadow)); p.setPen(Qt.NoPen)
        p.drawRoundedRect(bx + 3, by + 3, cw, ch, 5, 5)
        p.setBrush(QBrush(back))
        p.setPen(QPen(_qc(_CARD_EDGE), 1))
        p.drawRoundedRect(bx, by, cw, ch, 5, 5)

    # front card (offset down-left)
    fx = x + int(w * 0.06)
    fy = y + int(h * 0.10)
    p.setBrush(QBrush(shadow)); p.setPen(Qt.NoPen)
    p.drawRoundedRect(fx + 3, fy + 3, cw, ch, 5, 5)
    p.setBrush(QBrush(face))
    p.setPen(QPen(_qc(_CARD_EDGE), 1))
    p.drawRoundedRect(fx, fy, cw, ch, 5, 5)

    # subtle inner highlight on front card
    hi = QColor(255, 255, 255, 60)
    p.setBrush(QBrush(hi)); p.setPen(Qt.NoPen)
    p.drawRoundedRect(fx + 4, fy + 4, cw * 4 // 9, ch * 3 // 8, 3, 3)


# ══════════════════════════════════════════════════════════════════════════════
class AthleteRow(QWidget):
    """
    One full-width athlete row, painted exactly like the reference image.

    Layout (proportional to widget dimensions):
    ┌──────────────────────────────────────────────────────────────────┐
    │  [flag]      NAME (top)              [huge score]    [card]      │
    │  COUNTRY                                                         │
    │              Full name (blue row only, bottom)                   │
    └──────────────────────────────────────────────────────────────────┘

    White row: light background, black text
    Blue row:  blue background, white/light-blue text
    """

    def __init__(self, is_white: bool, parent=None):
        super().__init__(parent)
        self.is_white = is_white
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(100)

        # — data —
        self.athlete_name : str  = ""    # "SURNAME Firstname"
        self.country      : str  = ""    # "AZE"
        self.club         : str  = ""
        self.score_value  : int  = 0
        self.ippon        : bool = False
        self.shido        : int  = 0
        self.hansoku      : bool = False
        self.osaekomi     : bool = False
        self.osae_sec     : int  = 0
        self.is_winner    : bool = False
        self.yuko         : int  = 0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()

        # ── Background ────────────────────────────────────────────────────
        grad = QLinearGradient(0, 0, 0, H)
        if self.is_white:
            grad.setColorAt(0.0, _qc(_WHITE_ROW2))
            grad.setColorAt(1.0, _qc(_WHITE_ROW))
        else:
            grad.setColorAt(0.0, _qc(_BLUE_ROW2))
            grad.setColorAt(1.0, _qc(_BLUE_ROW))
        p.fillRect(0, 0, W, H, QBrush(grad))

        # winner glow
        if self.is_winner:
            wg = QLinearGradient(0, 0, W, 0)
            wg.setColorAt(0.0, QColor(0, 220, 80, 60))
            wg.setColorAt(0.7, QColor(0, 220, 80, 15))
            wg.setColorAt(1.0, QColor(0, 220, 80, 0))
            p.fillRect(0, 0, W, H, QBrush(wg))

        # ── Geometry constants ────────────────────────────────────────────
        pad      = max(10, int(W * 0.014))

        # No flag space: name starts near the left padding
        name_x   = pad
        card_zw  = int(W * 0.13)
        card_zx  = W - card_zw - pad
        name_w   = max(80, card_zx - name_x - int(W * 0.12))

        # Score: large digit, aligned right so it never overlaps the name
        available = max(10, card_zx - name_x - int(W * 0.04))
        score_w  = min(int(W * 0.16), max(int(W * 0.14), available))
        score_x  = max(card_zx - score_w, name_x + int(W * 0.02))

        # Colours
        nc = _qc(_NAME_W)  if self.is_white else _qc(_NAME_B)
        sc = _qc(_SCORE_W) if self.is_white else _qc(_SCORE_B)
        cc = _qc(_CTRY_W)  if self.is_white else _qc(_CTRY_B)

        # ── Athlete name ──────────────────────────────────────────────────
        # Use full name on both rows and ensure it never overlaps the score area
        if self.athlete_name:
            parts   = self.athlete_name.strip().split(" ", 1)
            surname = parts[0].upper()
            fname   = parts[1] if len(parts) > 1 else ""

            full = f"{surname} {fname}".strip()
            f_sz = max(32, int(H * 1.20))
            fnt_full = QFont("Arial Black", f_sz, QFont.Weight.Bold)
            fm2 = QFontMetrics(fnt_full)
            while fm2.horizontalAdvance(full) > name_w * 0.92 and f_sz > 10:
                f_sz -= 1
                fnt_full = QFont("Arial Black", f_sz, QFont.Weight.Bold)
                fm2 = QFontMetrics(fnt_full)
            # Final guard: elide to prevent overlap
            full = fm2.elidedText(full, Qt.ElideRight, int(name_w * 0.92))
            p.setFont(fnt_full); p.setPen(nc)
            p.drawText(QRect(name_x, 0, name_w, H),
                       Qt.AlignCenter,
                       full)

        # ── Club (under name) ────────────────────────────────────────────
        if self.club:
            club_sz = max(8, int(H * 0.14))
            fnt_club = QFont("Arial", club_sz, QFont.Weight.Medium)
            p.setFont(fnt_club); p.setPen(_qc("#000000") if self.is_white else _qc("#cfd8ff"))
            p.drawText(QRect(name_x, int(H * 0.62), name_w, int(H * 0.30)),
                       Qt.AlignCenter | Qt.AlignTop,
                       self.club)

        # ── Score digit ───────────────────────────────────────────────────
        digit = "IPPON" if self.ippon else str(self.score_value)
        if self.ippon:
            d_sz = max(16, int(H * 0.70))
            target_w = 0.88
        else:
            base = 0.70 if len(digit) >= 2 else 0.60
            d_sz = max(14, int(H * base))
            target_w = 0.98 if len(digit) >= 2 else 0.88
        fnt_d = QFont("Arial Black", d_sz, QFont.Weight.Black)
        fm3   = QFontMetrics(fnt_d)
        while fm3.horizontalAdvance(digit) > score_w * target_w and d_sz > 12:
            d_sz -= 1
            fnt_d  = QFont("Arial Black", d_sz, QFont.Weight.Black)
            fm3    = QFontMetrics(fnt_d)

        # Ippon glow
        if self.ippon and self.score_value > 0:
            sc = _qc("#FFD600")

        p.setFont(fnt_d); p.setPen(sc)
        p.drawText(QRect(score_x, 0, score_w, H), Qt.AlignCenter, digit)

        # ── Penalty card icon ─────────────────────────────────────────────
        if self.shido > 0 or self.hansoku:
            is_red = (self.hansoku or self.shido >= 3)
            face   = _CARD_RED if is_red else _CARD_FACE
            # For hansokumake, IJF display usually shows a single red card.
            # For shido, we show 1 or 2 yellow cards stacked.
            n      = 1 if is_red else min(2, self.shido)
            
            cz_h = int(H * 0.72)
            cz_w = int(card_zw * 0.85)
            cz_x = card_zx + (card_zw - cz_w) // 2
            cz_y = (H - cz_h) // 2
            _draw_penalty_card(p, cz_x, cz_y, cz_w, cz_h, face, n)
        else:
            # Show empty faint card placeholder (like image: card shown even at 0 penalties)
            cz_h = int(H * 0.72)
            cz_w = int(card_zw * 0.85)
            cz_x = card_zx + (card_zw - cz_w) // 2
            cz_y = (H - cz_h) // 2
            faint = QColor(180, 160, 0, 60) if self.is_white else QColor(180, 160, 0, 45)
            p.setBrush(QBrush(faint)); p.setPen(QPen(QColor(150, 130, 0, 80), 1))
            p.drawRoundedRect(cz_x + int(cz_w * 0.15), cz_y, int(cz_w * 0.72), cz_h, 4, 4)

        # ── Osaekomi bar (thin strip at bottom) ───────────────────────────
        if self.osaekomi:
            bar_h = max(5, int(H * 0.12))
            pct   = min(1.0, self.osae_sec / 20.0)
            p.fillRect(0, H - bar_h, W, bar_h, _qc(_OSAE_BG))
            fc = (_qc("#ff3300") if self.osae_sec >= 20 else
                  _qc("#ff9900") if self.osae_sec >= 10 else _qc(_OSAE_FILL))
            p.fillRect(0, H - bar_h, int(W * pct), bar_h, fc)
            
            # Digital counter
            t_fnt = QFont("Arial Black", max(10, int(bar_h * 1.5)), QFont.Weight.Black)
            p.setFont(t_fnt); p.setPen(_qc("#000000"))
            p.drawText(QRect(W - int(W*0.15), H - bar_h - int(bar_h*1.5), int(W*0.12), int(bar_h*2)), 
                       Qt.AlignRight | Qt.AlignBottom, str(int(self.osae_sec)))

        # ── Winner badge ──────────────────────────────────────────────────
        if self.is_winner and not self.ippon:
            badge_sz = max(7, int(H * 0.16))
            fnt_b = QFont("Arial Black", badge_sz, QFont.Weight.Black)
            p.setFont(fnt_b); p.setPen(_qc(_WIN_FG))
            p.drawText(QRect(name_x, 0, card_zx - name_x - 8, H),
                       Qt.AlignRight | Qt.AlignVCenter,
                       "WINNER")

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
class BottomBar(QWidget):
    """
    Dark bottom bar: category+round left, large green timer centre.
    Matches the reference image: "Round of 32 / -66 kg" left, "0:06" centre
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.category : str  = ""
        self.time_str : str  = "4:00"
        self.golden   : bool = False
        self.running  : bool = False
        self.finished : bool = False
        self.osaekomi : bool = False
        self.osae_sec : int  = 0
        self.osae_paused : bool = False
        self.stage_text : str = ""
        self.winner_side : Optional[str] = None
        self._flash_tick = 0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()
        self._flash_tick = (self._flash_tick + 1) % 10

        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, _qc(_BOTTOM_BG)); grad.setColorAt(1.0, _qc(_BOTTOM_BG2))
        p.fillRect(0, 0, W, H, QBrush(grad))

        pad = max(10, int(W * 0.016))

        # ── Category / round (left two lines) ────────────────────────────
        if self.category:
            lines = self.category.split("\n", 1)
            fnt_l1 = QFont("Arial", max(8, int(H * 0.26)), QFont.Weight.Bold)
            p.setFont(fnt_l1); p.setPen(_qc("#dddddd"))
            p.drawText(QRect(pad, int(H * 0.04), int(W * 0.32), int(H * 0.48)),
                       Qt.AlignBottom | Qt.AlignLeft,
                       lines[0])
            if len(lines) > 1:
                fnt_l2 = QFont("Arial", max(8, int(H * 0.24)), QFont.Weight.Bold)
                p.setFont(fnt_l2); p.setPen(_qc("#bbbbbb"))
                p.drawText(QRect(pad, int(H * 0.52), int(W * 0.32), int(H * 0.44)),
                           Qt.AlignTop | Qt.AlignLeft,
                           lines[1])

        # ── Timer (centre, very large) ────────────────────────────────────
        if self.golden:
            t_col   = _qc(_TIMER_GS)
            display = "GS  " + self.time_str
        elif self.finished:
            t_col   = _qc(_TIMER_HOT)
            display = self.time_str
        else:
            try:
                parts = self.time_str.split(":")
                secs  = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                secs  = 9999
            if   secs <= 30: t_col = _qc(_TIMER_HOT)
            elif secs <= 60: t_col = _qc(_TIMER_WRN)
            else:            t_col = _qc(_TIMER_NRM)
            display = self.time_str

        # The timer in the image is very large and bold — greenish, about 70% of bar height
        t_sz = max(16, int(H * 0.90))
        fnt_t = QFont("Arial", t_sz, QFont.Weight.Bold)
        p.setFont(fnt_t); p.setPen(t_col)
        p.drawText(QRect(int(W * 0.28), 0, int(W * 0.44), H),
                   Qt.AlignCenter, display)

        # ── Sono-mama indicator ───────────────────────────────────────────
        if self.osae_paused and (self._flash_tick < 5):
            fnt_sm = QFont("Arial Black", max(12, int(H * 0.30)), QFont.Weight.Black)
            p.setFont(fnt_sm); p.setPen(_qc("#FFD600"))
            p.drawText(QRect(int(W * 0.30), int(H * 0.75), int(W * 0.40), int(H * 0.25)),
                       Qt.AlignCenter, "SONO-MAMA")

        # ── Status indicator (right) ──────────────────────────────────────
        stage_label = self.stage_text or ""
        fnt_s = QFont("Arial", max(7, int(H * 0.22)), QFont.Weight.Bold)
        p.setFont(fnt_s)
        if self.finished:
            p.setPen(_qc(_TIMER_HOT))
            st = "DRAW" if self.winner_side is None else (stage_label if stage_label else "RESULT")
        elif self.running:
            p.setPen(_qc("#00cc44"))
            st = "● LIVE"
        else:
            p.setPen(_qc("#555566"))
            st = stage_label
        p.drawText(QRect(int(W * 0.76), 0, int(W * 0.22), H),
                   Qt.AlignVCenter | Qt.AlignRight, st)

        # ── Osaekomi progress strip at very bottom ────────────────────────
        if self.osaekomi:
            bh  = max(4, int(H * 0.09))
            pct = min(1.0, self.osae_sec / 20.0)
            p.fillRect(0, H - bh, W, bh, _qc(_OSAE_BG))
            fc = (_qc("#ff4400") if self.osae_sec >= 20 else
                  _qc("#ff9900") if self.osae_sec >= 10 else _qc(_OSAE_FILL))
            p.fillRect(0, H - bh, int(W * pct), bh, fc)
            p.setPen(QPen(_qc("#00000099"), 2))
            for t in (10, 20):
                p.drawLine(int(W * t / 20), H - bh, int(W * t / 20), H)

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
class HeaderBar(QWidget):
    """
    Dark wood/charcoal header. Left: Olympic rings icon. Right: Ω OMEGA style.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.event_name = "JUDO CHAMPIONSHIP · IJF 2026"
        self.stage = ""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Dark wood-grain gradient
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, _qc(_HDR_TOP))
        grad.setColorAt(1.0, _qc(_HDR_BOT))
        p.fillRect(0, 0, W, H, QBrush(grad))

        # Subtle wood grain lines
        p.setPen(QPen(QColor(255, 255, 255, 8), 1))
        for i in range(0, H, 3):
            p.drawLine(0, i, W, i)

        pad = max(10, int(W * 0.014))

        # ── Olympic rings (5 interlocking circles, left side) ─────────────
        rings_x = pad
        rings_y = H // 2
        r       = max(6, int(H * 0.22))
        gap     = int(r * 0.55)
        colors  = ["#0085c7", "#f4c300", "#000000", "#009f3d", "#df0024"]
        ring_cx = [rings_x + r + i * (r * 2 - gap) for i in range(5)]
        # draw all rings unclipped first (back layer)
        for i, (cx, col) in enumerate(zip(ring_cx, colors)):
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(_qc(col), max(2, int(r * 0.30))))
            p.drawEllipse(cx - r, rings_y - r, r * 2, r * 2)

        # ── Event name (centre) ───────────────────────────────────────────
        ev_x = rings_x + int(r * 2 * 5) + int(W * 0.01)
        fnt_e = QFont("Arial Black", max(8, int(H * 0.36)), QFont.Weight.Black)
        p.setFont(fnt_e); p.setPen(_qc("#dddddd"))
        p.drawText(QRect(ev_x, 0, int(W * 0.55), H),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   self.event_name.upper())

        # ── Stage label (right)
        stage_text = (self.stage or "MATCH").upper()
        fnt_stage = QFont("Arial", max(9, int(H * 0.40)), QFont.Weight.Bold)
        p.setFont(fnt_stage); p.setPen(_qc("#cccccc"))
        p.drawText(QRect(int(W * 0.65), 0, int(W * 0.35), H),
                   Qt.AlignVCenter | Qt.AlignRight,
                   stage_text)

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
class WinnerBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(0)
        self._text = ""

    def set_winner(self, name: str, side: str, method: str):
        s = "BLUE" if side == "blue" else "WHITE"
        self._text = f"🏆   {name.upper()}  ({s})   —   {method}"
        self.setFixedHeight(40)
        self.update()

    def clear(self):
        self._text = ""
        self.setFixedHeight(0)
        self.update()

    def paintEvent(self, _):
        if not self._text:
            return
        p = QPainter(self)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, _qc(_WIN_BG))
        p.fillRect(0, 0, W, 2, _qc(_WIN_FG))
        fnt = QFont("Arial Black", max(10, int(H * 0.52)), QFont.Weight.Black)
        p.setFont(fnt); p.setPen(_qc(_WIN_FG))
        p.drawText(QRect(0, 0, W, H), Qt.AlignCenter, self._text)
        p.end()


class _Divider(QWidget):
    def __init__(self, h=3, col="#1a1a1a", parent=None):
        super().__init__(parent)
        self.setFixedHeight(h); self._c = col

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), self.height(), _qc(self._c))
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
class ScoreboardWindow(QMainWindow):
    """
    Public IJF/Olympic-style scoreboard.
    Drag to second monitor/projector — F11 for fullscreen, Esc to exit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Judo Scoreboard — IJF 2026 — Public Display")
        self.setWindowIcon(QIcon(_resource_path("icon.ico")))
        self.resize(1280, 720)
        self.setStyleSheet("background: #111;")
        self._build()
        self._last_white_state = None
        self._last_blue_state = None
        self._last_bottom_state = None
        self._last_winner_state = None

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.header     = HeaderBar()
        self.white_row  = AthleteRow(is_white=True)
        self.blue_row   = AthleteRow(is_white=False)
        self.win_banner = WinnerBanner()
        self.bottom     = BottomBar()
        self.bottom.setFixedHeight(140)

        v.addWidget(self.header)
        v.addWidget(_Divider(2, "#000000"))
        v.addWidget(self.white_row,  stretch=4)
        v.addWidget(_Divider(3, _DIV_LINE))
        v.addWidget(self.blue_row,   stretch=4)
        v.addWidget(_Divider(2, "#000000"))
        v.addWidget(self.win_banner)
        v.addWidget(self.bottom)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_event_name(self, name: str):
        self.header.event_name = (name or "JUDO CHAMPIONSHIP · IJF 2026").upper()
        self.header.update()

    def update_state(self, engine, white_player, blue_player):
        """Call every tick from the control panel."""
        try:
            w_state = self._row_state(engine, engine.white, "white", white_player)
            if w_state != self._last_white_state:
                self._last_white_state = w_state
                self._apply_row_state(self.white_row, w_state)
                self.white_row.update()

            b_state = self._row_state(engine, engine.blue, "blue", blue_player)
            if b_state != self._last_blue_state:
                self._last_blue_state = b_state
                self._apply_row_state(self.blue_row, b_state)
                self.blue_row.update()

            bottom_state = self._bottom_state(engine)
            if bottom_state != self._last_bottom_state:
                self._last_bottom_state = bottom_state
                self._apply_bottom_state(bottom_state)
                self.bottom.update()

            winner_state = self._winner_state(engine, white_player, blue_player)
            if winner_state != self._last_winner_state:
                self._last_winner_state = winner_state
                self._apply_winner_state(winner_state)
        except Exception:
            pass

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _apply_row(self, row: AthleteRow, score, side: str,
                   player: Optional[dict], engine):
        row.athlete_name = player["name"]    if player else "—"
        row.country      = player["country"] if player else ""
        row.club         = player.get("club","") if player else ""
        row.score_value  = self._score_value(score)
        row.ippon        = score.ippon > 0 or score.wazaari >= 2
        row.shido        = score.shido
        row.hansoku      = score.hansokumake
        row.osaekomi     = (engine.osaekomi == side)
        row.osae_sec     = engine.osaekomi_elapsed if row.osaekomi else 0
        row.is_winner    = (engine.winner == side)
        row.yuko         = score.yuko

    @staticmethod
    def _score_value(score):
        return score.yuko + score.wazaari * 10 + score.ippon * 100

    def _row_state(self, engine, score, side: str, player: Optional[dict]):
        name = player["name"] if player else "-"
        country = player["country"] if player else "-"
        club = player.get("club", "") if player else ""
        score_value = self._score_value(score)
        ippon = score.ippon > 0 or score.wazaari >= 2
        shido = score.shido
        hansoku = score.hansokumake
        osaekomi = (engine.osaekomi == side)
        osae_sec = engine.osaekomi_elapsed if osaekomi else 0
        is_winner = (engine.winner == side)
        yuko = score.yuko
        return (name, country, club, score_value, ippon, shido, hansoku, osaekomi, osae_sec, is_winner, yuko)

    def _apply_row_state(self, row: AthleteRow, state):
        (row.athlete_name, row.country, row.club, row.score_value, row.ippon,
         row.shido, row.hansoku, row.osaekomi, row.osae_sec, row.is_winner, row.yuko) = state

    def _bottom_state(self, engine):
        stage_label = (engine.stage or "").upper()
        cat = engine.category or ""
        stage_u = stage_label
        if cat.upper().startswith(stage_u) and stage_u:
            cat = cat[len(stage_u):].strip()
            if cat.startswith("Â·") or cat.startswith("-"):
                cat = cat[1:].strip()
        category = f"{stage_u}\n{cat}" if stage_u else cat
        return (
            category,
            engine.time_str(),
            bool(engine.golden),
            bool(engine.running),
            bool(engine.finished),
            engine.osaekomi is not None,
            int(engine.osaekomi_elapsed or 0),
            engine.winner,
            bool(engine.osaekomi_paused),
        )

    def _apply_bottom_state(self, state):
        (self.bottom.category, self.bottom.time_str, self.bottom.golden, self.bottom.running,
         self.bottom.finished, self.bottom.osaekomi, self.bottom.osae_sec, self.bottom.winner_side,
         self.bottom.osae_paused) = state
        self.bottom.stage_text = ""

    def _winner_state(self, engine, white_player, blue_player):
        if not (engine.finished and engine.winner):
            return None
        pl = white_player if engine.winner == "white" else blue_player
        name = pl["name"] if pl else engine.winner.upper()
        sc = engine.white if engine.winner == "white" else engine.blue
        opp = engine.blue if engine.winner == "white" else engine.white
        if sc.ippon:
            method = "IPPON"
        elif sc.wazaari >= 2:
            method = "WAZA-ARI x2"
        elif opp.hansokumake:
            method = "HANSOKUMAKE"
        else:
            method = "SCORE"
        return (name, engine.winner, method)

    def _apply_winner_state(self, state):
        if not state:
            self.win_banner.clear()
            return
        name, side, method = state
        self.win_banner.set_winner(name, side, method)

    def _apply_bottom(self, engine):
        b = self.bottom
        stage_label = (engine.stage or "").upper()
        cat = engine.category or ""
        stage_u = stage_label
        if cat.upper().startswith(stage_u) and stage_u:
            cat = cat[len(stage_u):].strip()
            if cat.startswith("·") or cat.startswith("-"):
                cat = cat[1:].strip()
        # Ensure custom category label is visible when configured
        try:
            import database as db
            settings = db.load_settings()
            age_group = settings.get("age_group", "")
            if age_group == "Custom":
                custom_label = settings.get("custom_category_label", "Custom").upper()
                if custom_label and custom_label not in cat.upper():
                    cat = f"{custom_label} · {cat}" if cat else custom_label
        except Exception:
            pass
        b.category = f"{stage_u}\n{cat}" if stage_u else cat
        b.time_str = engine.time_str()
        b.golden   = engine.golden
        b.running  = engine.running
        b.finished = engine.finished
        b.osaekomi = engine.osaekomi is not None
        b.osae_sec = engine.osaekomi_elapsed
        b.stage_text = ""
        b.winner_side = engine.winner
        self.header.stage = ""
        self.header.update()

    def _apply_winner(self, engine, white_player, blue_player):
        if engine.finished and engine.winner:
            pl   = white_player if engine.winner == "white" else blue_player
            name = pl["name"] if pl else engine.winner.upper()
            sc   = engine.white if engine.winner == "white" else engine.blue
            opp  = engine.blue  if engine.winner == "white" else engine.white
            if   sc.ippon:           method = "IPPON"
            elif sc.wazaari >= 2:    method = "WAZA-ARI x2"
            elif opp.hansokumake:    method = "HANSOKUMAKE"
            else:                    method = "SCORE"
            self.win_banner.set_winner(name, engine.winner, method)
        else:
            self.win_banner.clear()

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)
