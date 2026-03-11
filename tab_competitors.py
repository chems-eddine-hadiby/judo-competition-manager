# -*- coding: utf-8 -*-
"""
tab_competitors.py — Competitor management (PyQt5)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QSizePolicy, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui  import QColor, QBrush, QFont
import database as db

AGE_OPTIONS = ["Senior","Junior","Cadet","Custom"]

C_BG="#0a0a12"; C_PANEL="#0e0e1a"; C_CARD="#111120"
C_RED="#D32F2F"; C_TEXT="#FFFFFF"; C_DIM="#666688"; C_BORDER="#1e1e35"

def _label(t="",size=11,bold=False,color=C_TEXT):
    l=QLabel(t); w="bold" if bold else "normal"
    l.setStyleSheet(f"color:{color};background:transparent;font-size:{size}px;font-weight:{w};")
    return l

def _input(placeholder=""):
    e=QLineEdit(); e.setPlaceholderText(placeholder)
    e.setStyleSheet("background:#1a1a2e;color:#fff;border:1px solid #2a2a4a;"
                    "border-radius:3px;padding:6px 8px;font-size:12px;")
    return e

def _combo(items):
    c=QComboBox()
    c.setStyleSheet("QComboBox{background:#1a1a2e;color:#fff;border:1px solid #2a2a4a;"
                    "border-radius:3px;padding:5px 8px;font-size:12px;}"
                    "QComboBox::drop-down{border:none;}"
                    "QComboBox QAbstractItemView{background:#111130;color:#fff;"
                    "selection-background-color:#1a1a3a;}")
    c.addItems(items); return c

def _btn(text, color="#D32F2F", bg="#1a0a0a", min_h=36):
    b=QPushButton(text)
    b.setMinimumHeight(min_h)
    b.setStyleSheet(f"QPushButton{{background:{bg};color:{color};border:2px solid {color};"
                    f"border-radius:4px;font-size:11px;font-weight:bold;padding:4px 12px;}}"
                    f"QPushButton:hover{{background:{color};color:#000;}}")
    return b


class CompetitorsTab(QWidget):
    def __init__(self, on_change=None, parent=None):
        super().__init__(parent)
        self.on_change  = on_change or (lambda: None)
        self._editing_id = None
        self.setStyleSheet(f"background:{C_BG};")
        self._build()
        self.refresh()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)

        # ── Left: form ─────────────────────────────────────────────────────
        form = QWidget(); form.setFixedWidth(320)
        form.setStyleSheet(f"background:{C_PANEL};")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(20, 20, 20, 20)
        fl.setSpacing(10)

        self.form_title = _label("ADD COMPETITOR", 14, True, C_RED)
        fl.addWidget(self.form_title)

        self.e_name    = _input("Full name"); fl.addWidget(_label("FULL NAME",9,True,C_DIM)); fl.addWidget(self.e_name)
        self.e_country = _input("e.g. JPN");  fl.addWidget(_label("COUNTRY CODE",9,True,C_DIM)); fl.addWidget(self.e_country)
        self.e_club    = _input("Club/Team"); fl.addWidget(_label("CLUB / TEAM",9,True,C_DIM)); fl.addWidget(self.e_club)

        fl.addWidget(_label("GENDER",9,True,C_DIM))
        self.cb_gender = _combo(["male","female"])
        self.cb_gender.currentTextChanged.connect(self._on_gender_change)
        fl.addWidget(self.cb_gender)

        fl.addWidget(_label("AGE CATEGORY",9,True,C_DIM))
        self.cb_age = _combo(AGE_OPTIONS)
        settings = db.load_settings()
        default_age = settings.get("age_group", "Senior")
        if default_age in AGE_OPTIONS:
            self.cb_age.setCurrentText(default_age)
        else:
            self.cb_age.setCurrentText("Custom")
        fl.addWidget(self.cb_age)

        fl.addWidget(_label("WEIGHT CLASS",9,True,C_DIM))
        self.cb_weight = _combo(self._weight_list("male"))
        fl.addWidget(self.cb_weight)

        self.btn_save = _btn("ADD COMPETITOR", "#D32F2F", "#200808", 42)
        self.btn_save.clicked.connect(self._save)
        fl.addWidget(self.btn_save)

        self.btn_cancel = _btn("CANCEL", C_DIM, "#1a1a2a", 32)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_cancel.hide()
        fl.addWidget(self.btn_cancel)

        self.lbl_stats = _label("", 9, False, C_DIM)
        fl.addWidget(self.lbl_stats)
        fl.addStretch()
        root.addWidget(form)

        # ── Right: table ───────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(8)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(_label("FILTER:", 10, True, C_DIM))
        self.f_gender = _combo(["all","male","female"]); self.f_gender.setFixedWidth(110)
        self.f_weight = _combo(["all"] + self._weight_list("male") + self._weight_list("female"))
        self.f_weight.setFixedWidth(110)
        self.e_search = _input("Search name/country/club"); self.e_search.setFixedWidth(220)
        for w in (self.f_gender, self.f_weight, self.e_search):
            filter_row.addWidget(w)
        filter_row.addStretch()

        self.lbl_count = _label("", 10, True, C_DIM)
        filter_row.addWidget(self.lbl_count)
        rl.addLayout(filter_row)

        for w in (self.f_gender, self.f_weight, self.e_search):
            (w.currentTextChanged if isinstance(w, QComboBox) else w.textChanged).connect(
                lambda _: self.refresh())

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["NAME","COUNTRY","GENDER","AGE","WEIGHT","CLUB"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        for c in (1,2,3,4): self.table.setColumnWidth(c, 90)
        self.table.setStyleSheet(f"""
            QTableWidget{{background:{C_PANEL};color:{C_TEXT};
              border:1px solid {C_BORDER};gridline-color:{C_BORDER};
              selection-background-color:#1a1a35;font-size:12px;}}
            QHeaderView::section{{background:#111130;color:#D32F2F;
              border:none;padding:6px;font-weight:bold;font-size:10px;}}
            QTableWidget::item{{padding:4px 6px;}}
        """)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(True)
        rl.addWidget(self.table, stretch=1)

        # Action buttons
        act_row = QHBoxLayout(); act_row.setSpacing(8)
        self.btn_edit   = _btn("EDIT SELECTED",   "#aaaaaa", "#1a1a2a")
        self.btn_delete = _btn("DELETE SELECTED", C_RED,     "#200808")
        self.btn_sample = _btn("IMPORT SAMPLES",  "#555577", "#0a0a18")
        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_sample.clicked.connect(self._import_samples)
        for b in (self.btn_edit, self.btn_delete, self.btn_sample):
            act_row.addWidget(b)
        act_row.addStretch()
        rl.addLayout(act_row)
        root.addWidget(right, stretch=1)

    def _on_gender_change(self, g):
        self.cb_weight.blockSignals(True)
        self.cb_weight.clear()
        self.cb_weight.addItems(self._weight_list(g))
        self.cb_weight.blockSignals(False)

    def _weight_list(self, gender):
        settings = db.load_settings()
        age_group = settings.get("age_group", "Senior")
        custom_txt = settings.get("custom_weight_categories", "")
        weights = db.combined_weights(age_group, gender, custom_txt)
        return weights

    def refresh(self):
        self._refresh_weight_filters()
        players = db.load_players()
        fg = self.f_gender.currentText()
        fw = self.f_weight.currentText()
        q  = self.e_search.text().lower()

        rows = [p for p in players
                if (fg=="all" or p.get("gender")==fg)
                and (fw=="all" or p.get("weight")==fw)
                and (not q or q in p.get("name","").lower()
                     or q in p.get("country","").lower()
                     or q in p.get("club","").lower())]

        self.table.setRowCount(len(rows))
        for i,p in enumerate(rows):
            for j, val in enumerate([p.get("name",""), p.get("country",""),
                                      p.get("gender",""), p.get("age_category",""),
                                      p.get("weight",""), p.get("club","")]):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, p["id"])
                if j==1: item.setForeground(QBrush(QColor("#D32F2F")))
                self.table.setItem(i,j,item)
        self.table.setRowHeight(i, 28) if rows else None
        self.lbl_count.setText(f"{len(rows)} / {len(players)} athletes")
        self.lbl_stats.setText(f"DB: {db.get_data_dir()}")

    def _refresh_weight_filters(self):
        weights_all = self._weight_list("male") + self._weight_list("female")
        existing = [self.f_weight.itemText(i) for i in range(self.f_weight.count())]
        desired = ["all"] + weights_all
        if existing != desired:
            self.f_weight.blockSignals(True)
            self.f_weight.clear()
            self.f_weight.addItems(desired)
            self.f_weight.blockSignals(False)

    def _save(self):
        name = self.e_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Please enter a name."); return
        settings = db.load_settings()
        default_age = settings.get("age_group", "Senior")
        age_value = self.cb_age.currentText() if hasattr(self, "cb_age") else default_age
        p = {"name": name, "country": self.e_country.text().strip().upper(),
             "club": self.e_club.text().strip(),
             "gender": self.cb_gender.currentText(),
             "age_category": age_value,
             "weight": self.cb_weight.currentText()}
        if self._editing_id:
            db.update_player(self._editing_id, p); self._cancel()
        else:
            db.add_player(p); self._clear_form()
        self.refresh(); self.on_change()

    def _edit_selected(self):
        row = self.table.currentRow()
        if row < 0: return
        pid = self.table.item(row, 0).data(Qt.UserRole)
        p = db.get_player(pid)
        if not p: return
        self._editing_id = pid
        self.e_name.setText(p.get("name",""))
        self.e_country.setText(p.get("country",""))
        self.e_club.setText(p.get("club",""))
        self.cb_gender.setCurrentText(p.get("gender","male"))
        self.cb_age.setCurrentText(p.get("age_category","Senior"))
        self.cb_weight.setCurrentText(p.get("weight","-60kg"))
        self.form_title.setText("EDIT COMPETITOR")
        self.btn_save.setText("UPDATE")
        self.btn_cancel.show()

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0: return
        pid = self.table.item(row, 0).data(Qt.UserRole)
        p = db.get_player(pid)
        r = QMessageBox.question(self, "Delete?", f"Delete '{p['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            db.delete_player(pid); self.refresh(); self.on_change()

    def _cancel(self):
        self._editing_id = None; self._clear_form()
        self.form_title.setText("ADD COMPETITOR")
        self.btn_save.setText("ADD COMPETITOR")
        self.btn_cancel.hide()

    def _clear_form(self):
        self.e_name.clear(); self.e_country.clear(); self.e_club.clear()
        self.cb_gender.setCurrentIndex(0); self.cb_weight.setCurrentIndex(0)
        settings = db.load_settings()
        default_age = settings.get("age_group", "Senior")
        if default_age in AGE_OPTIONS:
            self.cb_age.setCurrentText(default_age)
        else:
            self.cb_age.setCurrentText("Custom")

    def _import_samples(self):
        existing = {p["name"] for p in db.load_players()}
        added = sum(1 for s in db.SAMPLE_PLAYERS
                    if s["name"] not in existing and db.add_player(dict(s)))
        QMessageBox.information(self,"Import",
            f"{added} athletes imported." if added else "All samples already exist.")
        self.refresh(); self.on_change()
