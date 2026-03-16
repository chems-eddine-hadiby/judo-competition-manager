# -*- coding: utf-8 -*-
"""
tab_match.py — Referee match control panel (PyQt5)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QFrame, QSizePolicy, QMessageBox, QScrollArea,
    QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui  import QFont, QColor

import database as db
import match_engine as eng
from match_engine import MatchEngine, MATCH_DURATION

# Dark palette colours
C_BG    = "#0a0a12"; C_PANEL="#0e0e1a"; C_CARD="#111120"
C_RED   = "#D32F2F"; C_RED2="#8B0000"; C_ORANGE="#F57C00"
C_GOLD  = "#FFD600"; C_GREEN="#2E7D32"; C_BLUE="#1565C0"
C_TEXT  = "#FFFFFF"; C_DIM="#666688";  C_BORDER="#1e1e35"
C_BTN   = "#1a1a2e"

STAGE_OPTIONS = ["Round of 64","Round of 32","Round of 16",
                 "Quarter-final","Semi-final","Final","Repechage"]
AGE_GROUPS   = ["Senior","Junior","Cadet","Custom"]
GENDER_FILTERS = ["All","male","female"]

def _btn(text, color, bg=C_BTN, size=12, bold=True, min_h=40) -> QPushButton:
    b = QPushButton(text)
    b.setMinimumHeight(min_h)
    weight = "bold" if bold else "normal"
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {color};
            border: 2px solid {color}; border-radius: 4px;
            font-size: {size}px; font-weight: {weight}; padding: 4px 8px;
        }}
        QPushButton:hover  {{ background: {color}; color: #000; }}
        QPushButton:pressed{{ background: {color}88; }}
        QPushButton:disabled{{ border-color: #333355; color: #333355; background: #0a0a18; }}
    """)
    return b

def _label(text="", size=11, bold=False, color=C_TEXT, bg="transparent") -> QLabel:
    lbl = QLabel(text)
    w = "bold" if bold else "normal"
    lbl.setStyleSheet(f"color:{color};background:{bg};font-size:{size}px;font-weight:{w};")
    return lbl

def _separator():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background:{C_BORDER};"); f.setFixedHeight(1)
    return f


class MatchTab(QWidget):
    def __init__(self, engine: MatchEngine, on_update=None, on_profile_change=None, on_draw_update=None, parent=None):
        super().__init__(parent)
        self.engine    = engine
        self.on_update = on_update or (lambda: None)
        self._profile_change = on_profile_change or (lambda: None)
        self._draw_update = on_draw_update or (lambda: None)
        self.setStyleSheet(f"background:{C_BG};")
        self._player_map: dict = {}
        self._id_to_label: dict = {}
        self._build()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)
        self._auto_advanced = False

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        settings = db.load_settings()
        stage_value = settings.get("stage", "Final")
        if stage_value not in STAGE_OPTIONS:
            stage_value = STAGE_OPTIONS[-1]
        age_value = settings.get("age_group", "Senior")
        if age_value not in AGE_GROUPS:
            age_value = "Senior"
        match_time = settings.get("match_duration", MATCH_DURATION)
        golden_enabled = settings.get("golden_score", True)

        profile = QWidget()
        profile.setStyleSheet(f"background:{C_PANEL};border-bottom:1px solid {C_BORDER};")
        pl = QGridLayout(profile)
        pl.setContentsMargins(14, 8, 14, 8)
        pl.setSpacing(10)

        pl.addWidget(_label("STAGE", 9, True, C_DIM), 0, 0)
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(STAGE_OPTIONS)
        self.stage_combo.setCurrentText(stage_value)
        self.stage_combo.currentTextChanged.connect(self._on_stage_change)
        pl.addWidget(self.stage_combo, 0, 1)

        pl.addWidget(_label("AGE GROUP", 9, True, C_DIM), 0, 2)
        self.age_combo = QComboBox()
        self.age_combo.addItems(AGE_GROUPS)
        self.age_combo.setCurrentText(age_value)
        self.age_combo.currentTextChanged.connect(self._on_age_group_change)
        self.age_combo.setEnabled(False)
        pl.addWidget(self.age_combo, 0, 3)

        pl.addWidget(_label("GENDER", 9, True, C_DIM), 1, 0)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["All","male","female"])
        self.gender_combo.setCurrentText("All")
        self.gender_combo.currentTextChanged.connect(self._on_gender_change)
        pl.addWidget(self.gender_combo, 1, 1)

        pl.addWidget(_label("WEIGHT CAT", 9, True, C_DIM), 1, 2)
        self.weight_combo = QComboBox()
        pl.addWidget(self.weight_combo, 1, 3)
        self._populate_weight_combo()
        self.weight_combo.currentTextChanged.connect(self._on_weight_change)

        pl.addWidget(_label("MATCH TIME", 9, True, C_DIM), 2, 0)
        time_hbox = QHBoxLayout()
        self.time_min = QSpinBox(); self.time_min.setRange(0, 10)
        self.time_min.setSuffix(" m")
        self.time_min.setValue(match_time // 60)
        self.time_min.valueChanged.connect(self._on_duration_change)
        time_hbox.addWidget(self.time_min)
        self.time_sec = QSpinBox(); self.time_sec.setRange(0, 59)
        self.time_sec.setSuffix(" s")
        self.time_sec.setValue(match_time % 60)
        self.time_sec.valueChanged.connect(self._on_duration_change)
        time_hbox.addWidget(self.time_sec)
        pl.addLayout(time_hbox, 2, 1, 1, 3)

        self.chk_golden = QCheckBox("Enable golden score")
        self.chk_golden.setStyleSheet("color:#bbbbbb;")
        self.chk_golden.setChecked(bool(golden_enabled))
        self.chk_golden.toggled.connect(self._on_golden_toggled)
        pl.addWidget(self.chk_golden, 3, 0, 1, 2)

        self._populate_weight_combo()

        root.addWidget(profile)

        # ── Competitor selector bar ────────────────────────────────────────
        sel_bar = QWidget(); sel_bar.setStyleSheet(f"background:{C_PANEL};")
        sel_layout = QHBoxLayout(sel_bar)
        sel_layout.setContentsMargins(16, 10, 16, 10)
        sel_layout.setSpacing(12)

        sel_layout.addWidget(_label("BLUE:", 11, True, "#6699ff"))
        self.cb_blue = QComboBox()
        self._style_combo(self.cb_blue, "#1e2a4a")
        self.cb_blue.currentIndexChanged.connect(self._on_blue_change)
        sel_layout.addWidget(self.cb_blue, stretch=2)

        sel_layout.addWidget(_label("CATEGORY:", 11, True, C_DIM))
        self.cat_edit = QLineEdit()
        self.cat_edit.setPlaceholderText("e.g. Men -73kg Final")
        self.cat_edit.setStyleSheet(
            f"background:#1a1a2e;color:{C_TEXT};border:1px solid {C_BORDER};"
            "border-radius:3px;padding:5px 8px;font-size:11px;"
            "selection-background-color:#D32F2F;selection-color:#ffffff;")
        self.cat_edit.textChanged.connect(
            lambda t: setattr(self.engine, "category", t))
        self._update_category_label()
        sel_layout.addWidget(self.cat_edit, stretch=2)

        sel_layout.addWidget(_label("WHITE:", 11, True, C_DIM))
        self.cb_white = QComboBox()
        self._style_combo(self.cb_white, "#1a1a2e")
        self.cb_white.currentIndexChanged.connect(self._on_white_change)
        sel_layout.addWidget(self.cb_white, stretch=2)

        root.addWidget(sel_bar)
        root.addWidget(_separator())

        # ── Main area: blue ctrl | center ctrl | white ctrl ────────────────
        main = QWidget()
        main_layout = QHBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(1)

        self.blue_ctrl  = SideControl("blue",  self.engine, self._on_score)
        self.center_ctrl= CenterControl(self.engine,
                           on_toggle   = self.engine.toggle,
                           on_osae_w   = lambda: self.engine.start_osaekomi("white"),
                           on_osae_b   = lambda: self.engine.start_osaekomi("blue"),
                           on_toketa   = self.engine.stop_osaekomi,
                           on_sono_mama= self.engine.sono_mama,
                           on_yoshi    = self.engine.yoshi,
                           on_undo     = self._undo,
                           on_reset    = self._reset,
                           on_save     = self._save)
        self.white_ctrl = SideControl("white", self.engine, self._on_score)

        main_layout.addWidget(self.blue_ctrl,   stretch=3)
        main_layout.addWidget(self.center_ctrl, stretch=2)
        main_layout.addWidget(self.white_ctrl,  stretch=3)
        root.addWidget(main, stretch=1)

        root.addWidget(_separator())

        # ── Event log ──────────────────────────────────────────────────────
        log_bar = QWidget(); log_bar.setFixedHeight(36)
        log_bar.setStyleSheet(f"background:{C_PANEL};")
        log_l = QHBoxLayout(log_bar)
        log_l.setContentsMargins(14, 0, 14, 0)
        log_l.addWidget(_label("LOG:", 9, True, C_DIM))
        self.lbl_log = _label("No events", 9, False, "#8888aa")
        log_l.addWidget(self.lbl_log, stretch=1)
        root.addWidget(log_bar)

        self.engine.set_match_duration(match_time)
        self.engine.set_allow_golden(bool(golden_enabled))
        self.engine.set_stage(stage_value)
        self.refresh_competitors()

    def _write_setting(self, key, value, notify=False):
        settings = db.load_settings()
        if settings.get(key) == value: return
        settings[key] = value
        db.save_settings(settings)
        if notify: self._profile_change()

    @staticmethod
    def _style_combo(cb: QComboBox, bg: str):
        cb.setStyleSheet(f"""
            QComboBox {{
                background:{bg}; color:#fff;
                border:1px solid #2a2a4a; border-radius:3px;
                padding:5px 8px; font-size:11px; min-height:28px;
            }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{
                background:#111130; color:#fff;
                selection-background-color:#1a1a3a;
            }}
        """)

    def _populate_weight_combo(self, preserve=True):
        age_group = self.age_combo.currentText()
        gender = self.gender_combo.currentText()
        custom_txt = ""
        genders = GENDER_FILTERS[1:] if gender == "All" else [gender]
        weights = []
        for g in genders:
            for w in db.combined_weights(age_group, g, custom_txt):
                if w not in weights:
                    weights.append(w)
        current = self.weight_combo.currentText() if preserve and self.weight_combo.count() else "All"
        self.weight_combo.blockSignals(True)
        self.weight_combo.clear()
        self.weight_combo.addItem("All")
        self.weight_combo.addItems(weights)
        if current:
            idx = self.weight_combo.findText(current)
            if idx >= 0:
                self.weight_combo.setCurrentIndex(idx)
        self.weight_combo.blockSignals(False)

    def _update_category_label(self):
        age_label = self.age_combo.currentText()
        if age_label == "Custom":
            settings = db.load_settings()
            age_label = settings.get("custom_category_label", "Custom")
        parts = [self.stage_combo.currentText(), age_label]
        weight = self.weight_combo.currentText()
        if weight and weight != "All":
            parts.append(weight)
        label = " · ".join(p.upper() for p in parts if p)
        self.cat_edit.blockSignals(True)
        self.cat_edit.setText(label)
        self.cat_edit.blockSignals(False)
        self.engine.category = label

    # ── Competitor dropdowns ───────────────────────────────────────────────────

    def refresh_competitors(self):
        players = db.load_players()
        gender_pref = self.gender_combo.currentText()
        weight_pref = self.weight_combo.currentText()
        def matches(p):
            if gender_pref not in ("All","") and p.get("gender") != gender_pref:
                return False
            if weight_pref not in ("All","") and p.get("weight") != weight_pref:
                return False
            return True
        players = [p for p in players if matches(p)]
        self._player_map   = {f"{p['name']}  ({p.get('country','')})  {p.get('weight','')}": p["id"]
                               for p in players}
        self._id_to_label  = {v: k for k, v in self._player_map.items()}

        for cb in (self.cb_white, self.cb_blue):
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("— Select —", None)
            for lbl in self._player_map:
                cb.addItem(lbl, self._player_map[lbl])
            cb.blockSignals(False)

        self._restore_selection()

    def _restore_selection(self):
        for cb, pid in [(self.cb_white, self.engine.white_id),
                        (self.cb_blue,  self.engine.blue_id)]:
            if pid:
                lbl = self._id_to_label.get(pid, "")
                idx = cb.findText(lbl)
                if idx >= 0: cb.setCurrentIndex(idx)

    def _on_white_change(self, idx):
        self.engine.white_id = self.cb_white.itemData(idx)
        self.on_update()

    def _on_blue_change(self, idx):
        self.engine.blue_id = self.cb_blue.itemData(idx)
        self.on_update()

    def _on_stage_change(self, text):
        stage = text or "Final"
        self.engine.set_stage(stage)
        self._write_setting("stage", stage)
        self._update_category_label()
        self.refresh_competitors()
        self.on_update()

    def _on_age_group_change(self, text):
        group = text or "Senior"
        self._write_setting("age_group", group, notify=True)
        self._populate_weight_combo()
        self._update_category_label()
        self.refresh_competitors()
        self.on_update()

    def _on_gender_change(self, _=None):
        self._populate_weight_combo()
        self.refresh_competitors()
        self._update_category_label()

    def _on_weight_change(self, _=None):
        self.refresh_competitors()
        self._update_category_label()

    def _on_duration_change(self, _=None):
        seconds = max(1, self.time_min.value() * 60 + self.time_sec.value())
        self.engine.set_match_duration(seconds)
        self._write_setting("match_duration", seconds)
        self.on_update()

    def _on_golden_toggled(self, checked):
        self.engine.set_allow_golden(checked)
        self._write_setting("golden_score", bool(checked))
        self.on_update()

    def refresh_from_settings(self):
        settings = db.load_settings()
        stage_value = settings.get("stage", "Final")
        if stage_value not in STAGE_OPTIONS:
            stage_value = "Final"
        age_value = settings.get("age_group", "Senior")
        if age_value not in AGE_GROUPS:
            age_value = "Senior"
        match_time = settings.get("match_duration", MATCH_DURATION)
        golden_enabled = settings.get("golden_score", True)

        self.stage_combo.blockSignals(True)
        self.age_combo.blockSignals(True)
        self.time_min.blockSignals(True)
        self.time_sec.blockSignals(True)
        self.chk_golden.blockSignals(True)

        self.stage_combo.setCurrentText(stage_value)
        self.age_combo.setCurrentText(age_value)
        self.time_min.setValue(match_time // 60)
        self.time_sec.setValue(match_time % 60)
        self.chk_golden.setChecked(bool(golden_enabled))

        self.stage_combo.blockSignals(False)
        self.age_combo.blockSignals(False)
        self.time_min.blockSignals(False)
        self.time_sec.blockSignals(False)
        self.chk_golden.blockSignals(False)

        self._populate_weight_combo(preserve=False)
        self._update_category_label()
        self.refresh_competitors()
        self.engine.set_stage(stage_value)
        self.engine.set_match_duration(match_time)
        self.engine.set_allow_golden(bool(golden_enabled))
        self.on_update()

    # ── Timer tick ─────────────────────────────────────────────────────────────

    def _tick(self):
        self.engine.tick()
        self._refresh()

    # ── Actions ────────────────────────────────────────────────────────────────

    def _on_score(self, side, action, remove=False):
        if remove:
            self.engine.remove_score(side, action)
        else:
            {
                "ippon":       lambda: self.engine.add_ippon(side),
                "wazaari":     lambda: self.engine.add_wazaari(side),
                "yuko":        lambda: self.engine.add_yuko(side),
                "shido":       lambda: self.engine.add_shido(side),
                "hansokumake": lambda: self.engine.add_hansokumake(side),
            }[action]()
        self._refresh()
        self.on_update()

    def _undo(self):
        if not self.engine.events: return
        last = self.engine.events[-1]
        t = last.event_type.replace("osaekomi_","")
        self.engine.remove_score(last.side, t)
        self.engine.events.pop()
        self._refresh(); self.on_update()

    def _reset(self):
        r = QMessageBox.question(self, "Reset Match?",
            "Clear all scores and restart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.engine.reset(); self._refresh(); self.on_update()
            self._auto_advanced = False

    def _save(self):
        if not self.engine.finished:
            QMessageBox.information(self, "Not Finished", "Match is not finished yet.")
            return
        db.save_match_result(self.engine.to_result_dict())
        winner_id = None
        if self.engine.winner == "white":
            winner_id = self.engine.white_id
        elif self.engine.winner == "blue":
            winner_id = self.engine.blue_id
        if winner_id:
            draws = db.load_draws()
            players = db.load_players()
            updated = False
            for key, draw in draws.items():
                if eng.apply_result_to_draw(draw, self.engine.white_id, self.engine.blue_id, winner_id, players):
                    db.set_draw(key, draw)
                    updated = True
            if updated:
                self.on_update()
                self._draw_update()
        QMessageBox.information(self, "Saved", "Match result saved.")

    def load_match(self, white_id, blue_id, category, stage=None):
        self.engine.reset(white_id=white_id, blue_id=blue_id, category=category)
        self.cat_edit.setText(category)
        if stage:
            self.engine.set_stage(stage)
        self.refresh_competitors()
        self._refresh()
        self.on_update()
        self._auto_advanced = False

    # ── Refresh ────────────────────────────────────────────────────────────────

    def _refresh(self):
        try:
            self.blue_ctrl.refresh(self.engine)
            self.white_ctrl.refresh(self.engine)
            self.center_ctrl.refresh(self.engine)
            self._refresh_log()
            if not self.engine.finished:
                self._auto_advanced = False
            if self.engine.finished and self.engine.winner and not self._auto_advanced:
                self._auto_advance_draw()
                self._auto_advanced = True
        except: pass

    def _auto_advance_draw(self):
        winner_id = None
        if self.engine.winner == "white":
            winner_id = self.engine.white_id
        elif self.engine.winner == "blue":
            winner_id = self.engine.blue_id
        if not winner_id:
            return
        draws = db.load_draws()
        players = db.load_players()
        updated = False
        for key, draw in draws.items():
            if eng.apply_result_to_draw(draw, self.engine.white_id, self.engine.blue_id, winner_id, players):
                db.set_draw(key, draw)
                updated = True
        if updated:
            self.on_update()
            self._draw_update()

    def _refresh_log(self):
        if not self.engine.events:
            self.lbl_log.setText("No events"); return
        parts = [f"{e.event_type.upper().replace('_',' ')} [{e.side.upper()}]"
                 f" @{e.match_time//60:02d}:{e.match_time%60:02d}"
                 for e in reversed(self.engine.events[-8:])]
        self.lbl_log.setText("   |   ".join(parts))


# ── Side score control ─────────────────────────────────────────────────────────

class SideControl(QWidget):
    def __init__(self, side, engine, on_score, parent=None):
        super().__init__(parent)
        self.side     = side
        self.engine   = engine
        self.on_score = on_score
        self.is_blue  = side == "blue"
        accent = "#3a6fcc" if self.is_blue else "#cccccc"
        self.setStyleSheet(f"background:#0d0d1c; border-right:1px solid #1e1e35;"
                            if self.is_blue else f"background:#0d0d1c; border-left:1px solid #1e1e35;")
        self._build(accent)

    def _build(self, accent):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        dot = QLabel(); dot.setFixedSize(14,14)
        dot.setStyleSheet(f"background:{accent}; border-radius:2px;")
        hdr.addWidget(dot)
        hdr.addWidget(_label("BLUE" if self.is_blue else "WHITE", 13, True, accent))
        self.lbl_winner = _label("", 12, True, C_GOLD)
        hdr.addStretch(); hdr.addWidget(self.lbl_winner)
        root.addLayout(hdr)

        self.lbl_osae = _label("", 10, True, "#000000")
        self.lbl_osae.setStyleSheet(
            "color:#000;background:#FFD600;padding:2px 8px;border-radius:3px;")
        self.lbl_osae.hide()
        root.addWidget(self.lbl_osae)

        # Score display
        score_row = QHBoxLayout(); score_row.setSpacing(6)
        self.disp_ippon   = ScoreDisplay("IPPON",    C_RED,    "#1a0808")
        self.disp_wazaari = ScoreDisplay("WAZA-ARI", C_ORANGE, "#1a1000")
        self.disp_yuko    = ScoreDisplay("YUKO",     "#FFD600", "#3a2b00")
        score_row.addWidget(self.disp_ippon,   stretch=3)
        score_row.addWidget(self.disp_wazaari, stretch=2)
        score_row.addWidget(self.disp_yuko,    stretch=2)
        root.addLayout(score_row)

        # Penalty indicators
        pen_row = QHBoxLayout(); pen_row.setSpacing(5)
        pen_row.addWidget(_label("PENALTIES:", 9, True, C_DIM))
        self.shido_dots = []
        for i in range(3):
            d = QLabel(str(i+1))
            d.setFixedSize(26,26)
            d.setAlignment(Qt.AlignCenter)
            d.setStyleSheet("background:#1a1a2e;color:#444466;border-radius:13px;font-size:10px;font-weight:bold;")
            self.shido_dots.append(d); pen_row.addWidget(d)
        self.lbl_dq = _label("", 10, True, C_RED)
        pen_row.addWidget(self.lbl_dq); pen_row.addStretch()
        root.addLayout(pen_row)

        root.addWidget(_separator())

        # Score buttons
        root.addWidget(_label("SCORE", 9, True, C_DIM))
        sg = QGridLayout(); sg.setSpacing(5)
        self.btn_ippon   = _btn("+ IPPON",    C_RED,    min_h=48, size=13)
        self.btn_wazaari = _btn("+ WAZA-ARI", C_ORANGE, min_h=48, size=13)
        self.btn_yuko    = _btn("+ YUKO",     "#FFD600", min_h=48, size=13)
        self.btn_ippon.clicked.connect(   lambda: self.on_score(self.side, "ippon"))
        self.btn_wazaari.clicked.connect( lambda: self.on_score(self.side, "wazaari"))
        self.btn_yuko.clicked.connect(    lambda: self.on_score(self.side, "yuko"))
        sg.addWidget(self.btn_ippon,   0, 0)
        sg.addWidget(self.btn_wazaari, 0, 1)
        sg.addWidget(self.btn_yuko,    0, 2)
        root.addLayout(sg)

        root.addWidget(_label("PENALTIES", 9, True, C_DIM))
        pg = QGridLayout(); pg.setSpacing(5)
        btn_shido = _btn("+ SHIDO",      "#aaaaaa", min_h=36, size=11)
        btn_hm    = _btn("DISQUALIFY",   C_RED2,    min_h=36, size=11)
        btn_shido.clicked.connect(lambda: self.on_score(self.side, "shido"))
        btn_hm.clicked.connect(   lambda: self.on_score(self.side, "hansokumake"))
        pg.addWidget(btn_shido, 0, 0); pg.addWidget(btn_hm, 0, 1)
        root.addLayout(pg)

        root.addWidget(_label("CORRECTIONS", 9, True, C_DIM))
        cg = QGridLayout(); cg.setSpacing(4)
        for col, (lbl, sc) in enumerate([("− IPPON","ippon"),("− W-A","wazaari"),
                                         ("− YUKO","yuko"),("− SHIDO","shido")]):
            b = _btn(lbl, C_DIM, size=9, min_h=28)
            b.clicked.connect(lambda _, s=sc: self.on_score(self.side, s, remove=True))
            cg.addWidget(b, 0, col)
        root.addLayout(cg)
        root.addStretch()

    def refresh(self, engine):
        s = engine.blue if self.is_blue else engine.white
        self.disp_ippon.set(s.ippon)
        self.disp_wazaari.set(s.wazaari)
        self.disp_yuko.set(s.yuko)
        for i, dot in enumerate(self.shido_dots):
            if s.shido > i:
                dot.setStyleSheet("background:#FFD600;color:#000;border-radius:13px;"
                                   "font-size:10px;font-weight:bold;")
            else:
                dot.setStyleSheet("background:#1a1a2e;color:#444466;border-radius:13px;"
                                   "font-size:10px;font-weight:bold;")
        self.lbl_dq.setText("DISQUALIFIED" if s.hansokumake else "")
        self.lbl_winner.setText("🏆 WINNER" if engine.winner==self.side else "")
        if engine.osaekomi == self.side:
            self.lbl_osae.setText(f" HOLD  {engine.osaekomi_elapsed}s ")
            self.lbl_osae.show()
        else:
            self.lbl_osae.hide()


class ScoreDisplay(QWidget):
    def __init__(self, label, color, bg_active, parent=None):
        super().__init__(parent)
        self.color = color; self.bg_active = bg_active
        self.setMinimumHeight(80)
        layout = QVBoxLayout(self); layout.setContentsMargins(4,4,4,4); layout.setSpacing(0)
        self.lbl_label = _label(label, 9, True, C_DIM, C_DIM)
        self.lbl_label.setAlignment(Qt.AlignCenter)
        self.lbl_val   = _label("0",  44, True, "#1e1e35")
        self.lbl_val.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_label); layout.addWidget(self.lbl_val, stretch=1)
        self.setStyleSheet(f"background:#0e0e1e;border:1px solid #1e1e35;border-radius:4px;")

    def set(self, v):
        if v > 0:
            self.setStyleSheet(f"background:{self.bg_active};border:2px solid {self.color};border-radius:4px;")
            self.lbl_val.setStyleSheet(f"color:{self.color};background:transparent;font-size:44px;font-weight:bold;")
        else:
            self.setStyleSheet("background:#0e0e1e;border:1px solid #1e1e35;border-radius:4px;")
            self.lbl_val.setStyleSheet("color:#1e1e35;background:transparent;font-size:44px;font-weight:bold;")
        self.lbl_val.setText(str(v))


# ── Center control ─────────────────────────────────────────────────────────────

class CenterControl(QWidget):
    def __init__(self, engine, on_toggle, on_osae_w, on_osae_b,
                  on_toketa, on_sono_mama, on_yoshi, on_undo, on_reset, on_save, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setStyleSheet(f"background:#08080e;")
        self._build(on_toggle, on_osae_w, on_osae_b, on_toketa, on_sono_mama, on_yoshi, on_undo, on_reset, on_save)

    def _build(self, on_toggle, on_osae_w, on_osae_b, on_toketa, on_sono_mama, on_yoshi, on_undo, on_reset, on_save):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Clock
        self.lbl_time = QLabel("04:00")
        self.lbl_time.setFont(QFont("Courier New", 58, QFont.Weight.Bold))
        self.lbl_time.setAlignment(Qt.AlignCenter)
        self.lbl_time.setStyleSheet("color:#fff;background:transparent;")
        root.addWidget(self.lbl_time)

        time_adj = QHBoxLayout(); time_adj.setSpacing(6)
        def _tbtn(label, delta):
            b = _btn(label, C_DIM, "#111130", min_h=28, size=9)
            b.clicked.connect(lambda: self.engine.adjust_time(delta))
            return b
        time_adj.addStretch()
        for d in (-1, -5, -10, -30):
            time_adj.addWidget(_tbtn(f"{d}s", d))
        for d in (1, 5, 10, 30):
            time_adj.addWidget(_tbtn(f"+{d}s", d))
        time_adj.addStretch()
        root.addLayout(time_adj)

        self.lbl_golden = _label("", 11, True, C_GOLD, C_DIM)
        self.lbl_golden.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_golden)

        # Osaekomi bar (compact label)
        self.osa_bar = QLabel("")
        self.osa_bar.setFixedHeight(18)
        self.osa_bar.setAlignment(Qt.AlignCenter)
        self.osa_bar.setStyleSheet(
            "background:#111130;color:#FFD600;font-size:10px;font-weight:bold;")
        root.addWidget(self.osa_bar)

        # Start/stop
        self.btn_start = QPushButton("▶  START")
        self.btn_start.setMinimumHeight(52)
        self.btn_start.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.btn_start.clicked.connect(on_toggle)
        self._set_start_style(False)
        root.addWidget(self.btn_start)

        # Hold buttons
        hold_row = QHBoxLayout(); hold_row.setSpacing(4)
        self.btn_hold_blue  = _btn("HOLD BLUE",  "#6699ff", min_h=34, size=10)
        self.btn_hold_white = _btn("HOLD WHITE", "#cccccc", min_h=34, size=10)
        self.btn_hold_blue.clicked.connect(on_osae_b)
        self.btn_hold_white.clicked.connect(on_osae_w)
        hold_row.addWidget(self.btn_hold_blue)
        hold_row.addWidget(self.btn_hold_white)
        root.addLayout(hold_row)

        self.btn_toketa = _btn("✋  RELEASE HOLD (TOKETA)", C_ORANGE, "#1c1400", min_h=34, size=10)
        self.btn_toketa.clicked.connect(on_toketa)
        self.btn_toketa.hide()
        root.addWidget(self.btn_toketa)

        sm_row = QHBoxLayout(); sm_row.setSpacing(4)
        self.btn_sono_mama = _btn("SONO MAMA", C_GOLD, "#2a2300", min_h=30, size=9)
        self.btn_yoshi = _btn("YOSHI", "#00cc44", "#0a1e0a", min_h=30, size=9)
        self.btn_sono_mama.clicked.connect(on_sono_mama)
        self.btn_yoshi.clicked.connect(on_yoshi)
        sm_row.addWidget(self.btn_sono_mama)
        sm_row.addWidget(self.btn_yoshi)
        root.addLayout(sm_row)

        root.addWidget(_separator())

        # Utility row
        util = QHBoxLayout(); util.setSpacing(4)
        btn_undo  = _btn("↩ UNDO",  C_DIM, min_h=32, size=10)
        btn_reset = _btn("↺ RESET", C_RED2, min_h=32, size=10)
        btn_undo.clicked.connect(on_undo)
        btn_reset.clicked.connect(on_reset)
        util.addWidget(btn_undo); util.addWidget(btn_reset)
        root.addLayout(util)

        self.btn_save = _btn("💾  SAVE RESULT", "#aaaaaa", min_h=34, size=10)
        self.btn_save.clicked.connect(on_save)
        root.addWidget(self.btn_save)

        self.lbl_winner_disp = _label("", 15, True, C_GOLD, C_GOLD)
        self.lbl_winner_disp.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_winner_disp)

        root.addStretch()

    def _set_start_style(self, running: bool):
        if running:
            self.btn_start.setText("⏸  STOP")
            self.btn_start.setStyleSheet("""
                QPushButton { background:#0a1e0a; color:#4CAF50;
                  border:2px solid #4CAF50; border-radius:4px;
                  font-size:16px; font-weight:bold; }
                QPushButton:hover { background:#4CAF50; color:#000; }
            """)
        else:
            self.btn_start.setText("▶  START")
            self.btn_start.setStyleSheet("""
                QPushButton { background:#1e080a; color:#D32F2F;
                  border:2px solid #D32F2F; border-radius:4px;
                  font-size:16px; font-weight:bold; }
                QPushButton:hover { background:#D32F2F; color:#fff; }
            """)

    def refresh(self, engine):
        # Clock
        if engine.golden:
            self.lbl_time.setText("G.S.")
            self.lbl_time.setStyleSheet("color:#FFD600;background:transparent;font-size:58px;font-weight:bold;")
            self.lbl_golden.setText("GOLDEN SCORE")
        else:
            color = "#D32F2F" if engine.time_left<=30 else "#fff"
            self.lbl_time.setText(engine.time_str())
            self.lbl_time.setStyleSheet(f"color:{color};background:transparent;font-size:58px;font-weight:bold;")
            self.lbl_golden.setText("")

        self._set_start_style(engine.running)
        if engine.finished:
            self.btn_start.setText("MATCH OVER")
            self.btn_start.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)

        # Osaekomi
        if engine.osaekomi:
            if engine.osaekomi_paused:
                self.osa_bar.setText(f"HOLD PAUSED  {int(engine.osaekomi_elapsed)}s / 20s")
            else:
                self.osa_bar.setText(f"HOLD  {int(engine.osaekomi_elapsed)}s / 20s")
            self.btn_toketa.show()
            self.btn_hold_blue.setEnabled(False)
            self.btn_hold_white.setEnabled(False)
            self.btn_sono_mama.setEnabled(not engine.osaekomi_paused)
            self.btn_yoshi.setEnabled(engine.osaekomi_paused)
        else:
            self.osa_bar.setText("")
            self.btn_toketa.hide()
            self.btn_hold_blue.setEnabled(True)
            self.btn_hold_white.setEnabled(True)
            self.btn_sono_mama.setEnabled(False)
            self.btn_yoshi.setEnabled(False)

        # Winner
        if engine.finished and engine.winner:
            self.lbl_winner_disp.setText(f"🏆  {engine.winner.upper()}\nWINNER")
        else:
            self.lbl_winner_disp.setText("")
