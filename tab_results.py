# -*- coding: utf-8 -*-
"""
tab_results.py — Match results history (PyQt5)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTabWidget,
    QComboBox, QGridLayout
)
from PyQt5.QtGui  import QBrush, QColor
import database as db

C_BG="#0a0a12"; C_PANEL="#0e0e1a"; C_RED="#D32F2F"
C_TEXT="#FFFFFF"; C_DIM="#666688"; C_BORDER="#1e1e35"; C_GOLD="#FFD600"

def _l(t="",sz=11,bold=False,col=C_TEXT):
    lbl=QLabel(t); w="bold" if bold else "normal"
    lbl.setStyleSheet(f"color:{col};background:transparent;font-size:{sz}px;font-weight:{w};")
    return lbl


class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16,16,16,16)
        root.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:1px solid {C_BORDER}; background:{C_BG}; }}
            QTabBar::tab {{ background:{C_PANEL}; color:{C_DIM}; padding:6px 12px; }}
            QTabBar::tab:selected {{ background:{C_BG}; color:{C_TEXT}; }}
        """)

        self.history_page = QWidget()
        self._build_history(self.history_page)
        self.tabs.addTab(self.history_page, "CONTEST HISTORY")

        self.results_page = QWidget()
        self._build_classement(self.results_page)
        self.tabs.addTab(self.results_page, "RESULTS")

        root.addWidget(self.tabs, stretch=1)

    def _build_history(self, parent):
        root = QVBoxLayout(parent)
        root.setContentsMargins(12,12,12,12)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        hdr.addWidget(_l("CONTEST HISTORY",16,True))
        btn_clear = QPushButton("🗑  CLEAR HISTORY")
        btn_clear.setMinimumHeight(32)
        btn_clear.setStyleSheet(
            f"background:#1a0c0c;color:{C_RED};border:1px solid {C_RED};"
            "border-radius:3px;font-size:11px;font-weight:bold;padding:4px 14px;"
            f"QPushButton:hover{{background:#240f0f;}}")
        btn_clear.clicked.connect(self._clear_history)
        btn_ref = QPushButton("↻  REFRESH")
        btn_ref.setMinimumHeight(32)
        btn_ref.setStyleSheet(
            f"background:{C_PANEL};color:{C_DIM};border:1px solid {C_BORDER};"
            "border-radius:3px;font-size:11px;font-weight:bold;padding:4px 14px;"
            f"QPushButton:hover{{background:#1a1a2e;}}")
        btn_ref.clicked.connect(self.refresh)
        hdr.addStretch(); hdr.addWidget(btn_clear); hdr.addWidget(btn_ref)
        root.addLayout(hdr)

        cols = ["DATE","CATEGORY","WHITE","BLUE","WINNER","WHITE SCORE","BLUE SCORE","GOLDEN?"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:{C_PANEL};color:{C_TEXT};
              border:1px solid {C_BORDER};gridline-color:{C_BORDER};
              selection-background-color:#1a1a35;font-size:11px;}}
            QHeaderView::section{{background:#111130;color:{C_RED};
              border:none;padding:6px;font-weight:bold;font-size:10px;}}
            QTableWidget::item{{padding:4px 6px;}}
        """)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        root.addWidget(self.table, stretch=1)

        self.lbl_stats = _l("", 9, False, C_DIM)
        root.addWidget(self.lbl_stats)

    def _build_classement(self, parent):
        root = QVBoxLayout(parent)
        root.setContentsMargins(12,12,12,12)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        hdr.addWidget(_l("FINAL CLASSEMENT",16,True))
        hdr.addStretch()
        hdr.addWidget(_l("Category:", 10, False, C_DIM))
        self.cat_combo = QComboBox()
        self.cat_combo.setFixedHeight(28)
        self.cat_combo.setStyleSheet(
            "QComboBox{background:#111130;color:#fff;border:1px solid #2a2a4a;"
            "border-radius:3px;padding:4px 8px;font-size:10px;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#111130;color:#fff;"
            "selection-background-color:#1a1a3a;}")
        self.cat_combo.currentTextChanged.connect(self._refresh_classement)
        hdr.addWidget(self.cat_combo)
        root.addLayout(hdr)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.addWidget(_l("PLACE", 10, True, C_DIM), 0, 0)
        grid.addWidget(_l("ATHLETE", 10, True, C_DIM), 0, 1)

        self.place_labels = []
        places = ["1", "2", "3", "3", "5", "5", "7", "7"]
        for i, place in enumerate(places, start=1):
            grid.addWidget(_l(place, 12, True, C_RED), i, 0)
            lbl = _l("—", 12, False, C_TEXT)
            grid.addWidget(lbl, i, 1)
            self.place_labels.append(lbl)

        root.addLayout(grid)

    def refresh(self):
        matches = db.load_matches()
        players = {p["id"]: p for p in db.load_players()}

        self.table.setRowCount(len(matches))
        for i, m in enumerate(reversed(matches)):
            saved   = m.get("saved_at","")[:16].replace("T"," ")
            cat     = m.get("category","—")
            wid     = m.get("white_id")
            bid     = m.get("blue_id")
            winner  = m.get("winner","")

            def pstr(pid):
                p = players.get(pid)
                return f"{p['name']} ({p.get('country','')})" if p else "—"

            def sstr(s):
                return (f"I:{s.get('ippon',0)} W:{s.get('wazaari',0)} "
                        f"P:{s.get('shido',0)}"
                        + f" Y:{s.get('yuko',0)}"
                        + (" DQ" if s.get("hansokumake") else ""))

            wname = pstr(wid); bname = pstr(bid)
            wname_w = wname if winner=="white" else bname if winner=="blue" else "—"

            vals = [saved, cat, wname, bname, wname_w,
                    sstr(m.get("white_score",{})), sstr(m.get("blue_score",{})),
                    "Yes" if m.get("golden_score") else "No"]

            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if j==4 and winner:  # winner cell
                    item.setForeground(QBrush(QColor(C_GOLD)))
                self.table.setItem(i, j, item)

        self.lbl_stats.setText(
            f"{len(matches)} results stored  |  {db.get_data_dir()}")
        self._refresh_categories()
        self._refresh_classement()

    def _clear_history(self):
        from PyQt5.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Clear contest history?",
                                "This will delete all saved matches.",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        db.clear_match_history()
        self.refresh()

    def _refresh_categories(self):
        draws = db.load_draws()
        keys = list(draws.keys())
        cur = self.cat_combo.currentText() if hasattr(self, "cat_combo") else ""
        if hasattr(self, "cat_combo"):
            self.cat_combo.blockSignals(True)
            self.cat_combo.clear()
            self.cat_combo.addItems(keys)
            if cur in keys:
                self.cat_combo.setCurrentText(cur)
            self.cat_combo.blockSignals(False)

    def _refresh_classement(self):
        if not hasattr(self, "cat_combo"):
            return
        key = self.cat_combo.currentText()
        if not key:
            for lbl in self.place_labels:
                lbl.setText("—")
            return
        draw = db.get_draw(key)
        players = {p["id"]: p for p in db.load_players()}
        places = self._compute_classement(draw, players)
        for lbl, name in zip(self.place_labels, places):
            lbl.setText(name or "—")

    def _compute_classement(self, draw, players):
        if not draw:
            return ["—"] * 8

        if draw.get("type") == "round_robin":
            return self._compute_rr_classement(draw, players)

        def pstr(pid):
            p = players.get(pid)
            if not p:
                return "—"
            club = p.get("club", "").strip()
            name = p.get("name", "—")
            return f"{name} ({club})" if club else name

        def loser_of(match):
            if not match: return None
            w = match.get("white"); b = match.get("blue")
            if not w or not b: return None
            wid = match.get("winner_id")
            if not wid: return None
            return b if w.get("id") == wid else w

        rounds = draw.get("rounds", [])
        gold = silver = None
        if rounds and rounds[-1]:
            final = rounds[-1][0]
            if final and final.get("winner_id"):
                wid = final.get("winner_id")
                gold = wid
                other = final.get("blue") if final.get("white", {}).get("id") == wid else final.get("white")
                silver = other.get("id") if other else None

        rep = draw.get("repechage") or {}
        if not rep and rounds:
            # Try to preserve previous classement after final: rebuild repechage from rounds
            try:
                import match_engine as eng
                eng._update_repechage(draw, list(players.values()))
                rep = draw.get("repechage") or {}
            except Exception:
                rep = draw.get("repechage") or {}

        bronze_ids = []
        fifth_ids = []
        seventh_ids = []
        if isinstance(rep, dict):
            for side in ("top", "bottom"):
                side_data = rep.get(side) or {}
                rrounds = side_data.get("rounds", [])
                if not rrounds:
                    continue
                bronze_match = rrounds[-1][0] if rrounds[-1] else None
                if bronze_match and bronze_match.get("winner_id"):
                    bronze_ids.append(bronze_match.get("winner_id"))
                    loser = loser_of(bronze_match)
                    if loser: fifth_ids.append(loser.get("id"))
                if len(rrounds) >= 2 and rrounds[-2]:
                    rep_final = rrounds[-2][0]
                    loser = loser_of(rep_final)
                    if loser: seventh_ids.append(loser.get("id"))

        places = [pstr(gold), pstr(silver)]
        places.extend(pstr(pid) for pid in bronze_ids[:2])
        while len(places) < 4:
            places.append("—")
        places.extend(pstr(pid) for pid in fifth_ids[:2])
        while len(places) < 6:
            places.append("—")
        places.extend(pstr(pid) for pid in seventh_ids[:2])
        while len(places) < 8:
            places.append("—")
        return places

    def _compute_rr_classement(self, draw, players):
        pool = draw.get("players", [])
        if not pool:
            return ["—"] * 8
        pool_ids = [p.get("id") for p in pool if p.get("id") is not None]
        stats = {pid: {"wins": 0, "points": 0} for pid in pool_ids}

        # Build expected category label to filter match history
        key = self.cat_combo.currentText() if hasattr(self, "cat_combo") else ""
        cat_label = ""
        if key and "-" in key:
            g, w = key.split("-", 1)
            cat_label = f"{'Men' if g=='male' else 'Women'} {w}"

        matches = db.load_matches()
        for m in matches:
            if cat_label and m.get("category") != cat_label:
                continue
            wid = m.get("white_id")
            bid = m.get("blue_id")
            if wid not in stats or bid not in stats:
                continue
            winner = m.get("winner")
            if winner == "white":
                stats[wid]["wins"] += 1
            elif winner == "blue":
                stats[bid]["wins"] += 1

            def score_points(s):
                return (s.get("ippon", 0) * 100 +
                        s.get("wazaari", 0) * 10 +
                        s.get("yuko", 0) * 1)

            stats[wid]["points"] += score_points(m.get("white_score", {}))
            stats[bid]["points"] += score_points(m.get("blue_score", {}))

        def pstr(pid):
            p = players.get(pid)
            if not p:
                return "—"
            club = p.get("club", "").strip()
            name = p.get("name", "—")
            return f"{name} ({club})" if club else name

        ordered = sorted(pool_ids, key=lambda pid: (-stats[pid]["wins"], -stats[pid]["points"]))
        places = [pstr(pid) for pid in ordered[:8]]
        while len(places) < 8:
            places.append("—")
        return places
