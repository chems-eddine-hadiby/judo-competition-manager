# -*- coding: utf-8 -*-
"""
tab_results.py — Match results history (PyQt5)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
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

        hdr = QHBoxLayout()
        hdr.addWidget(_l("MATCH RESULTS HISTORY",16,True))
        btn_ref = QPushButton("↻  REFRESH")
        btn_ref.setMinimumHeight(32)
        btn_ref.setStyleSheet(
            f"background:{C_PANEL};color:{C_DIM};border:1px solid {C_BORDER};"
            "border-radius:3px;font-size:11px;font-weight:bold;padding:4px 14px;"
            f"QPushButton:hover{{background:#1a1a2e;}}")
        btn_ref.clicked.connect(self.refresh)
        hdr.addStretch(); hdr.addWidget(btn_ref)
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
