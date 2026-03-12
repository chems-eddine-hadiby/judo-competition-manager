# -*- coding: utf-8 -*-
"""
tab_draw.py — Tournament draw (PyQt5)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QFrame, QSizePolicy, QMessageBox, QSplitter, QGridLayout,
    QFileDialog, QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui  import QColor, QPainter, QPen, QFontMetrics
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from datetime import datetime
import re
import database as db
import match_engine as eng

C_BG="#0a0a12"; C_PANEL="#0e0e1a"; C_CARD="#111120"
C_RED="#D32F2F"; C_BLUE="#1565C0"; C_TEXT="#FFFFFF"
C_DIM="#666688"; C_BORDER="#1e1e35"; C_GOLD="#FFD600"
C_GREEN="#2E7D32"
CARD_H = 108
CARD_SPACING = 20

def _l(t="",sz=11,bold=False,col=C_TEXT):
    lbl=QLabel(t); w="bold" if bold else "normal"
    lbl.setStyleSheet(f"color:{col};background:transparent;font-size:{sz}px;font-weight:{w};")
    return lbl

def _btn(t,color,bg="#111130",mh=32,sz=10):
    b=QPushButton(t); b.setMinimumHeight(mh)
    b.setStyleSheet(f"QPushButton{{background:{bg};color:{color};border:1px solid {color};"
                    f"border-radius:3px;font-size:{sz}px;font-weight:bold;padding:3px 8px;}}"
                    f"QPushButton:hover{{background:{color};color:#000;}}")
    return b


class ChampionsDialog(QDialog):
    def __init__(self, pool, selected_ids=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Champions (max 8)")
        self.setMinimumSize(560, 360)
        self._pool = pool[:]
        self._selected = list(selected_ids or [])
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        lists = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(_l("AVAILABLE ATHLETES", 9, True, C_DIM))
        self.available = QListWidget()
        left.addWidget(self.available)

        mid = QVBoxLayout()
        mid.addStretch()
        self.btn_add = _btn("ADD →", C_TEXT, "#222", 28, 10)
        self.btn_remove = _btn("← REMOVE", C_TEXT, "#222", 28, 10)
        self.btn_up = _btn("↑ UP", C_TEXT, "#222", 28, 10)
        self.btn_down = _btn("↓ DOWN", C_TEXT, "#222", 28, 10)
        self.btn_clear = _btn("CLEAR", C_TEXT, "#222", 28, 10)
        for b in (self.btn_add, self.btn_remove, self.btn_up, self.btn_down, self.btn_clear):
            mid.addWidget(b)
        mid.addStretch()

        right = QVBoxLayout()
        right.addWidget(_l("CHAMPIONS ORDER", 9, True, C_DIM))
        self.champions = QListWidget()
        right.addWidget(self.champions)

        lists.addLayout(left, 1)
        lists.addLayout(mid)
        lists.addLayout(right, 1)
        root.addLayout(lists)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        root.addWidget(buttons)

        self.btn_add.clicked.connect(self._add_selected)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_clear.clicked.connect(self._clear_all)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._populate()

    def _populate(self):
        self.available.clear()
        self.champions.clear()
        pool_ids = {p.get("id") for p in self._pool}
        ordered = [cid for cid in self._selected if cid in pool_ids]
        by_id = {p.get("id"): p for p in self._pool}

        for cid in ordered:
            p = by_id.get(cid)
            if not p:
                continue
            self.champions.addItem(self._make_item(p))

        for p in self._pool:
            if p.get("id") in ordered:
                continue
            self.available.addItem(self._make_item(p))

    def _make_item(self, p):
        club = p.get("club", "").strip()
        name = p.get("name", "TBD")
        text = f"{name} ({club})" if club else name
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, p.get("id"))
        return item

    def _add_selected(self):
        items = self.available.selectedItems()
        if not items:
            return
        for it in items:
            if self.champions.count() >= 8:
                QMessageBox.information(self, "Limit", "Maximum 8 champions per pool.")
                break
            row = self.available.row(it)
            self.available.takeItem(row)
            self.champions.addItem(it)

    def _remove_selected(self):
        items = self.champions.selectedItems()
        if not items:
            return
        for it in items:
            row = self.champions.row(it)
            self.champions.takeItem(row)
            self.available.addItem(it)

    def _move_selected(self, direction):
        row = self.champions.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.champions.count():
            return
        item = self.champions.takeItem(row)
        self.champions.insertItem(new_row, item)
        self.champions.setCurrentRow(new_row)

    def _clear_all(self):
        while self.champions.count():
            it = self.champions.takeItem(0)
            self.available.addItem(it)

    def selected_ids(self):
        ids = []
        for i in range(self.champions.count()):
            it = self.champions.item(i)
            ids.append(it.data(Qt.UserRole))
        return ids


class DrawTab(QWidget):
    def __init__(self, on_start_match=None, parent=None):
        super().__init__(parent)
        self.on_start_match = on_start_match or (lambda *a: None)
        self._active_key    = None
        self._cat_btns: dict = {}
        self._champion_ids = []
        self.setStyleSheet(f"background:{C_BG};")
        self._build()
        self.refresh_categories()

    def _weight_list(self, gender):
        settings = db.load_settings()
        age_group = settings.get("age_group", "Senior")
        custom_txt = settings.get("custom_weight_categories", "")
        return db.combined_weights(age_group, gender, custom_txt)

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(1)

        # ── Left: category list ────────────────────────────────────────────
        left = QWidget(); left.setFixedWidth(210)
        left.setStyleSheet(f"background:{C_PANEL};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8,12,8,8)
        ll.setSpacing(4)
        ll.addWidget(_l("WEIGHT CATEGORIES",9,True,C_DIM))

        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll.setStyleSheet("background:transparent;border:none;")
        self.cat_inner = QWidget()
        self.cat_inner.setStyleSheet(f"background:{C_PANEL};")
        self.cat_vbox  = QVBoxLayout(self.cat_inner)
        self.cat_vbox.setContentsMargins(0,0,0,0)
        self.cat_vbox.setSpacing(2)
        self.cat_vbox.addStretch()
        self.cat_scroll.setWidget(self.cat_inner)
        ll.addWidget(self.cat_scroll, stretch=1)
        root.addWidget(left)

        # ── Right: bracket area ────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14,14,14,14)
        rl.setSpacing(8)
        right.setStyleSheet(f"background:{C_BG};")

        hdr = QHBoxLayout()
        self.lbl_title = _l("← Select a category", 18, True, C_DIM)
        self.rep_combo = QComboBox()
        self.rep_combo.addItems(["simple", "double"])
        self.rep_combo.setFixedHeight(28)
        self.rep_combo.setStyleSheet(
            "QComboBox{background:#111130;color:#fff;border:1px solid #2a2a4a;"
            "border-radius:3px;padding:4px 8px;font-size:10px;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#111130;color:#fff;"
            "selection-background-color:#1a1a3a;}")
        self.rep_combo.currentTextChanged.connect(self._on_repechage_mode)
        settings = db.load_settings()
        self.rep_combo.setCurrentText(settings.get("repechage_mode", "simple"))

        self.btn_gen   = QPushButton("GENERATE DRAW")
        self.btn_gen.setEnabled(False)
        self.btn_gen.setMinimumHeight(36)
        self.btn_gen.setStyleSheet(
            f"QPushButton{{background:{C_RED};color:#fff;border:none;border-radius:4px;"
            f"font-size:12px;font-weight:bold;padding:4px 18px;}}"
            f"QPushButton:hover{{background:#a01020;}} QPushButton:disabled{{background:#2a0a0a;color:#555;}}")
        self.btn_gen.clicked.connect(self._generate)
        self.btn_champ = QPushButton("SET CHAMPIONS")
        self.btn_champ.setEnabled(False)
        self.btn_champ.setMinimumHeight(32)
        self.btn_champ.setStyleSheet(
            "QPushButton {background:#222;color:#fff;border:none;border-radius:4px;"
            "font-size:11px;font-weight:bold;padding:4px 14px;}"
            "QPushButton:hover {background:#333;}")
        self.btn_champ.clicked.connect(self._edit_champions)
        self.btn_print = QPushButton("PRINT DRAW")
        self.btn_print.setEnabled(False)
        self.btn_print.setMinimumHeight(32)
        self.btn_print.setStyleSheet(
            "QPushButton {background:#222;color:#fff;border:none;border-radius:4px;"
            "font-size:11px;font-weight:bold;padding:4px 14px;}"
            "QPushButton:hover {background:#333;}")
        self.btn_print.clicked.connect(self._print_draw)
        hdr.addWidget(self.lbl_title, stretch=1)
        hdr.addWidget(QLabel("Repechage:"))
        hdr.addWidget(self.rep_combo)
        hdr.addWidget(self.btn_gen)
        hdr.addWidget(self.btn_champ)
        hdr.addWidget(self.btn_print)
        rl.addLayout(hdr)

        self.bracket_scroll = QScrollArea()
        self.bracket_scroll.setWidgetResizable(True)
        self.bracket_scroll.setStyleSheet(f"background:{C_BG};border:1px solid {C_BORDER};")
        self.bracket_widget = QWidget()
        self.bracket_widget.setStyleSheet(f"background:{C_BG};")
        self.bracket_vbox = QVBoxLayout(self.bracket_widget)
        self.bracket_vbox.setContentsMargins(16,16,16,16)
        self.bracket_vbox.setSpacing(14)
        self.bracket_vbox.addStretch()
        self.bracket_scroll.setWidget(self.bracket_widget)
        rl.addWidget(self.bracket_scroll, stretch=1)
        root.addWidget(right, stretch=1)

    # ── Category sidebar ───────────────────────────────────────────────────────

    def refresh_categories(self):
        # Clear old buttons
        while self.cat_vbox.count() > 1:
            item = self.cat_vbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._cat_btns.clear()

        players = db.load_players()
        draws   = db.load_draws()

        for gender in ("male","female"):
            for weight in self._weight_list(gender):
                pool = [p for p in players if p.get("gender")==gender and p.get("weight")==weight]
                if not pool: continue
                key = f"{gender}-{weight}"
                is_active = key == self._active_key
                has_draw  = key in draws

                btn = QPushButton(f"  {weight}  {'♂' if gender=='male' else '♀'}  ({len(pool)})")
                btn.setCheckable(True)
                btn.setChecked(is_active)
                btn.setMinimumHeight(36)
                bg  = "#1a0810" if is_active else C_PANEL
                bdr = C_RED     if is_active else C_BORDER
                btn.setStyleSheet(
                    f"QPushButton{{background:{bg};color:#ccc;border-left:3px solid {bdr};"
                    f"text-align:left;font-size:12px;font-weight:bold;padding:4px 8px;}}"
                    f"QPushButton:hover{{background:#1a1a2e;border-left-color:{C_RED};}}"
                    f"QPushButton:checked{{background:#1a0810;border-left-color:{C_RED};}}")
                btn.clicked.connect(lambda _, k=key: self._select(k))
                self.cat_vbox.insertWidget(self.cat_vbox.count()-1, btn)
                self._cat_btns[key] = btn

                if has_draw:
                    dot = _l("   ✓ draw ready", 8, False, C_RED)
                    self.cat_vbox.insertWidget(self.cat_vbox.count()-1, dot)

    # ── Category selection ─────────────────────────────────────────────────────

    def _select(self, key):
        self._active_key = key
        self.refresh_categories()
        g, w = key.split("-",1)
        settings = db.load_settings()
        age_label = settings.get("age_group","Senior")
        if age_label == "Custom":
            age_label = settings.get("custom_category_label", "Custom")
        stage_label = settings.get("stage","Final")
        champs = settings.get("champions_by_category", {}).get(key, [])
        pool_ids = {p.get("id") for p in db.get_players_by_category(g, w)}
        self._champion_ids = [cid for cid in champs if cid in pool_ids]
        self.lbl_title.setText(f"{stage_label.upper()} · {age_label.upper()} · {w.upper()}  {'MEN' if g=='male' else 'WOMEN'}")
        self.lbl_title.setStyleSheet(f"color:{C_TEXT};background:transparent;font-size:18px;font-weight:bold;")
        self.btn_gen.setEnabled(True)
        self.btn_champ.setEnabled(True)
        self._render(db.get_draw(key))

    # ── Generate draw ──────────────────────────────────────────────────────────

    def _generate(self):
        if not self._active_key: return
        g, w = self._active_key.split("-",1)
        pool = db.get_players_by_category(g, w)
        if len(pool) < 2:
            QMessageBox.warning(self,"Not Enough","Need at least 2 athletes."); return
        if db.get_draw(self._active_key):
            r = QMessageBox.question(self,"Redraw?","Regenerate? Existing results will be lost.",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return
        data = eng.generate_draw(pool, repechage_mode=self.rep_combo.currentText(),
                                 champion_ids=self._champion_ids)
        db.set_draw(self._active_key, data)
        self._render(data)
        self.refresh_categories()

    def _on_repechage_mode(self, mode):
        settings = db.load_settings()
        settings["repechage_mode"] = mode
        db.save_settings(settings)

    def _edit_champions(self):
        if not self._active_key:
            return
        g, w = self._active_key.split("-", 1)
        pool = db.get_players_by_category(g, w)
        settings = db.load_settings()
        champs = settings.get("champions_by_category", {}).get(self._active_key, [])
        dlg = ChampionsDialog(pool, champs, self)
        if dlg.exec_() == QDialog.Accepted:
            ids = dlg.selected_ids()
            settings = db.load_settings()
            champs_map = settings.get("champions_by_category", {}) or {}
            champs_map[self._active_key] = ids
            settings["champions_by_category"] = champs_map
            db.save_settings(settings)
            self._champion_ids = ids
            self._render(db.get_draw(self._active_key))

    def _print_draw(self):
        if not self._active_key:
            return
        settings = db.load_settings()
        event_name = settings.get("event_name", "Competition")
        g, w = self._active_key.split("-", 1)
        category = f"{w}-{g}"
        date_str = datetime.now().strftime("%Y-%m-%d")
        base = f"{category}-{event_name}-{date_str}".strip()
        base = re.sub(r"[^A-Za-z0-9._-]+", "-", base)
        default_name = f"{base}.pdf"

        path, _ = QFileDialog.getSaveFileName(self, "Save Draw PDF", default_name, "PDF Files (*.pdf)")
        if not path:
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)

        widget = self.bracket_widget
        widget.adjustSize()
        painter = QPainter(printer)
        page = printer.pageRect(QPrinter.DevicePixel)
        scale = min(page.width() / max(1, widget.width()),
                    page.height() / max(1, widget.height()))
        painter.scale(scale, scale)
        widget.render(painter)
        painter.end()

    # ── Render bracket ─────────────────────────────────────────────────────────

    def _render(self, draw_data):
        # Clear old content
        while self.bracket_vbox.count() > 1:
            item = self.bracket_vbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.btn_print.setEnabled(bool(draw_data))

        if not draw_data:
            lbl = _l("Click  GENERATE DRAW  to create the bracket", 13, False, C_DIM)
            lbl.setAlignment(Qt.AlignCenter)
            self.bracket_vbox.insertWidget(0, lbl)
            return
        if draw_data.get("type") == "round_robin":
            self._render_round_robin(draw_data)
            return
        if draw_data.get("type") == "pool5":
            self._render_pool5(draw_data)
            return

        rounds = draw_data.get("rounds", [])
        self._render_bracket_section("POOL / MAIN DRAW", rounds, context="main", draw_data=draw_data)

        rep = draw_data.get("repechage")
        if rep:
            rep_widget = QWidget(); rep_widget.setStyleSheet("background:transparent;")
            rep_v = QVBoxLayout(rep_widget); rep_v.setContentsMargins(0,0,0,0); rep_v.setSpacing(8)
            rep_label = _l("REPECHAGE", 12, True, C_GOLD)
            rep_label.setAlignment(Qt.AlignCenter)
            rep_v.addWidget(rep_label)
            rep_row = QHBoxLayout(); rep_row.setSpacing(20)
            for side_key in ("top","bottom"):
                side = rep.get(side_key)
                if not side: continue
                rep_row.addWidget(self._render_rounds_widget(side.get("rounds", []),
                                                            context="repechage",
                                                            side_key=side_key))
            rep_v.addLayout(rep_row)
            self.bracket_vbox.insertWidget(self.bracket_vbox.count()-1, rep_widget)


    def _render_bracket_section(self, title, rounds, context="main", draw_data=None):
        sec = QWidget(); sec.setStyleSheet("background:transparent;")
        v = QVBoxLayout(sec); v.setContentsMargins(0,0,0,0); v.setSpacing(8)
        lbl = _l(title, 12, True, C_TEXT)
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        v.addWidget(self._render_rounds_widget(rounds, context=context, draw_data=draw_data))
        self.bracket_vbox.insertWidget(self.bracket_vbox.count()-1, sec)

    def _round_label(self, size, round_index, total_rounds):
        if size == -5:
            return "SEMI-FINAL" if round_index == 0 else "FINAL"
        if total_rounds <= 0:
            return f"ROUND {round_index+1}"
        if size <= 0:
            size = 2 ** total_rounds
        elif size < (2 ** total_rounds):
            size = 2 ** total_rounds
        stage = size // (2 ** round_index)
        if stage >= 64: return f"ROUND OF {stage}"
        if stage == 32: return "ROUND OF 32"
        if stage == 16: return "ROUND OF 16"
        if stage == 8:  return "QUARTER-FINAL"
        if stage == 4:  return "SEMI-FINAL"
        if stage == 2:  return "FINAL"
        return f"ROUND {round_index+1}"

    def _render_rounds_widget(self, rounds, context="main", side_key=None, draw_data=None):
        n = len(rounds)
        row = QWidget(); row.setStyleSheet("background:transparent;")
        h = QHBoxLayout(row); h.setContentsMargins(0,0,0,0); h.setSpacing(0)
        size = (draw_data or {}).get("size", 0)
        if (draw_data or {}).get("type") == "pool5":
            size = -5
        base_step = CARD_H + CARD_SPACING
        for ri, round_list in enumerate(rounds):
            col = QWidget(); col.setFixedWidth(420)
            col.setStyleSheet("background:transparent;")
            cl = QVBoxLayout(col); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
            top_offset = 0

            if n > 1:
                if context == "repechage":
                    rlbl = "BRONZE" if ri == n-1 else "REPECHAGE"
                else:
                    rlbl = self._round_label(size, ri, n)
                hl = _l(rlbl, 9, True, C_DIM)
                hl.setAlignment(Qt.AlignCenter)
                cl.addWidget(hl)
                top_offset = 22
            step = base_step * (2 ** ri)
            top_pad = max(0, (step - CARD_H) // 2)
            cl.addSpacing(top_pad)
            centers = []
            y = top_offset + top_pad
            for mi, match in enumerate(round_list):
                if match is None:
                    card = self._make_empty_card()
                    cl.addWidget(card)
                    centers.append(y + CARD_H // 2)
                    cl.addSpacing(step - CARD_H)
                    y += step
                    continue
                if context == "repechage":
                    stage_label = "BRONZE" if ri == n-1 else "REPECHAGE"
                else:
                    stage_label = self._round_label(size, ri, n)
                card = self._make_match_card(match, ri, mi, context=context, side_key=side_key, round_label=stage_label)
                cl.addWidget(card)
                centers.append(y + CARD_H // 2)
                cl.addSpacing(step - CARD_H)
                y += step

            cl.addStretch()
            h.addWidget(col)

            if ri < n-1:
                spacer = ConnectorWidget(centers)
                spacer.setFixedWidth(22)
                spacer.setStyleSheet("background:transparent;")
                h.addWidget(spacer)
        return row

    def _make_empty_card(self):
        card = QFrame()
        card.setStyleSheet(f"background:{C_PANEL};border:1px dashed {C_BORDER};border-radius:4px;")
        card.setFixedHeight(CARD_H)
        cl = QVBoxLayout(card); cl.setContentsMargins(6,6,6,6); cl.setSpacing(3)
        for _ in range(2):
            row = QLabel("  TBD")
            row.setStyleSheet(f"color:{C_DIM};background:#0a0a16;font-size:14px;padding:8px;")
            cl.addWidget(row)
        return card

    def _render_round_robin(self, draw_data):
        sec = QWidget(); sec.setStyleSheet("background:transparent;")
        v = QVBoxLayout(sec); v.setContentsMargins(0,0,0,0); v.setSpacing(8)
        lbl = _l("ROUND ROBIN", 12, True, C_TEXT)
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)

        matches = draw_data.get("matches", [])
        grid = QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(6)
        grid.addWidget(_l("ATHLETE A", 9, True, C_DIM), 0, 0)
        grid.addWidget(_l("ATHLETE B", 9, True, C_DIM), 0, 1)
        grid.addWidget(_l("ACTIONS", 9, True, C_DIM), 0, 2)

        players = {p.get("id"): p for p in db.load_players()}
        for i, m in enumerate(matches):
            p1 = m.get("p1"); p2 = m.get("p2")
            grid.addWidget(_l(p1.get("name","TBD") if p1 else "TBD", 10), i+1, 0)
            grid.addWidget(_l(p2.get("name","TBD") if p2 else "TBD", 10), i+1, 1)
            if p1 and p2:
                action_col = QVBoxLayout(); action_col.setSpacing(4)
                g, w = (self._active_key.split("-",1) if self._active_key else ("",""))
                cat_label = f"{'Men' if g=='male' else 'Women'} {w}"
                if m.get("winner_id"):
                    win = players.get(m.get("winner_id"))
                    win_name = win.get("name","—") if win else "—"
                    win_lbl = _l(f"WINNER: {win_name}", 9, True, C_GOLD)
                    action_col.addWidget(win_lbl)
                else:
                    start_btn = _btn("▶ START MATCH", C_RED, "#14060a", 26, 9)
                    start_btn.clicked.connect(
                        lambda _, wp=p1, bp=p2, c=cat_label: self.on_start_match(wp["id"], bp["id"], c, "ROUND ROBIN"))
                    b1 = _btn(f"Winner: {p1['name'][:12]}", C_DIM, "#0e0e1e", 22, 9)
                    b2 = _btn(f"Winner: {p2['name'][:12]}", C_DIM, "#0e0e1e", 22, 9)
                    b1.clicked.connect(lambda _, pid=p1["id"], mi=i: self._mark_rr_winner(pid, mi))
                    b2.clicked.connect(lambda _, pid=p2["id"], mi=i: self._mark_rr_winner(pid, mi))
                    action_col.addWidget(start_btn)
                    action_col.addWidget(b1)
                    action_col.addWidget(b2)
                w = QWidget(); w.setLayout(action_col)
                grid.addWidget(w, i+1, 2)
        v.addLayout(grid)
        self.bracket_vbox.insertWidget(self.bracket_vbox.count()-1, sec)

    def _render_pool5(self, draw_data):
        sec = QWidget(); sec.setStyleSheet("background:transparent;")
        v = QVBoxLayout(sec); v.setContentsMargins(0,0,0,0); v.setSpacing(12)
        lbl = _l("POOLS (5 ATHLETES)", 12, True, C_TEXT)
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)

        def _pool_table(title, matches, stage_label, stage_key):
            box = QWidget()
            lv = QVBoxLayout(box); lv.setContentsMargins(0,0,0,0); lv.setSpacing(6)
            t = _l(title, 11, True, C_GOLD)
            lv.addWidget(t)
            grid = QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(6)
            grid.addWidget(_l("ATHLETE A", 9, True, C_DIM), 0, 0)
            grid.addWidget(_l("ATHLETE B", 9, True, C_DIM), 0, 1)
            grid.addWidget(_l("ACTIONS", 9, True, C_DIM), 0, 2)
            players = {p.get("id"): p for p in db.load_players()}
            for i, m in enumerate(matches):
                p1 = m.get("p1"); p2 = m.get("p2")
                grid.addWidget(_l(p1.get("name","TBD") if p1 else "TBD", 10), i+1, 0)
                grid.addWidget(_l(p2.get("name","TBD") if p2 else "TBD", 10), i+1, 1)
                if p1 and p2:
                    action_col = QVBoxLayout(); action_col.setSpacing(4)
                    g, w = (self._active_key.split("-",1) if self._active_key else ("",""))
                    cat_label = f"{'Men' if g=='male' else 'Women'} {w}"
                    if m.get("winner_id"):
                        win = players.get(m.get("winner_id"))
                        win_name = win.get("name","-") if win else "-"
                        win_lbl = _l(f"WINNER: {win_name}", 9, True, C_GOLD)
                        action_col.addWidget(win_lbl)
                    else:
                        start_btn = _btn("▶ START MATCH", C_RED, "#14060a", 26, 9)
                        start_btn.clicked.connect(
                            lambda _, wp=p1, bp=p2, c=cat_label, st=stage_label:
                                self.on_start_match(wp["id"], bp["id"], c, st))
                        b1 = _btn(f"Winner: {p1['name'][:12]}", C_DIM, "#0e0e1e", 22, 9)
                        b2 = _btn(f"Winner: {p2['name'][:12]}", C_DIM, "#0e0e1e", 22, 9)
                        b1.clicked.connect(lambda _, pid=p1["id"], mi=i, sk=stage_key: self._mark_pool5_winner(pid, sk, mi))
                        b2.clicked.connect(lambda _, pid=p2["id"], mi=i, sk=stage_key: self._mark_pool5_winner(pid, sk, mi))
                        action_col.addWidget(start_btn)
                        action_col.addWidget(b1)
                        action_col.addWidget(b2)
                    w = QWidget(); w.setLayout(action_col)
                    grid.addWidget(w, i+1, 2)
            lv.addLayout(grid)
            return box

        pools = draw_data.get("pools", {})
        pool_row = QHBoxLayout(); pool_row.setSpacing(16)
        pool_row.addWidget(_pool_table("POOL A (2)", pools.get("A", {}).get("matches", []), "POOL A", "pool_a"))
        pool_row.addWidget(_pool_table("POOL B (3)", pools.get("B", {}).get("matches", []), "POOL B", "pool_b"))
        v.addLayout(pool_row)

        # Semis and final
        semis = draw_data.get("semis", [])
        final = draw_data.get("final")
        sec2 = QWidget(); sec2.setStyleSheet("background:transparent;")
        v2 = QVBoxLayout(sec2); v2.setContentsMargins(0,0,0,0); v2.setSpacing(8)
        v2.addWidget(_l("SEMI-FINALS / FINAL", 12, True, C_TEXT, ))
        rounds = [semis, [final] if final else []]
        v2.addWidget(self._render_rounds_widget(rounds, context="pool5", draw_data=draw_data))
        v.addWidget(sec2)

        self.bracket_vbox.insertWidget(self.bracket_vbox.count()-1, sec)

    def _make_match_card(self, match, ri, mi, context="main", side_key=None, round_label=None):
        card = QFrame()
        card.setStyleSheet(f"background:{C_PANEL};border:1px solid {C_BORDER};border-radius:4px;")
        card.setFixedHeight(CARD_H)
        cl = QVBoxLayout(card); cl.setContentsMargins(6,6,6,6); cl.setSpacing(3)

        white_p = match.get("white")
        blue_p  = match.get("blue")
        winner  = match.get("winner_id")
        is_bye  = match.get("bye", False)

        rows = [("blue", blue_p), ("white", white_p)]
        wf = match.get("white_from")
        bf = match.get("blue_from")
        if white_p and blue_p and (wf is not None or bf is not None):
            if wf is not None and bf is not None:
                rows = [("white", white_p), ("blue", blue_p)] if wf <= bf else [("blue", blue_p), ("white", white_p)]
            elif wf is not None:
                rows = [("white", white_p), ("blue", blue_p)]
            elif bf is not None:
                rows = [("blue", blue_p), ("white", white_p)]
        elif white_p and (wf is not None):
            top_first = (wf % 2 == 0)
            rows = [("white", white_p), ("blue", blue_p)] if top_first else [("blue", blue_p), ("white", white_p)]
        elif blue_p and (bf is not None):
            top_first = (bf % 2 == 0)
            rows = [("blue", blue_p), ("white", white_p)] if top_first else [("white", white_p), ("blue", blue_p)]
        elif blue_p and white_p:
            blue_is_champ = blue_p.get("id") in self._champion_ids
            white_is_champ = white_p.get("id") in self._champion_ids
            if blue_is_champ != white_is_champ:
                rows = [("blue", blue_p), ("white", white_p)] if blue_is_champ else [("white", white_p), ("blue", blue_p)]

        for side, player in rows:
            if player is None and is_bye and side=="blue":
                bye_row = QLabel("  BYE")
                bye_row.setStyleSheet(f"color:{C_DIM};background:#08080e;font-size:14px;padding:8px;")
                cl.addWidget(bye_row)
                continue

            is_w = (side == "white")
            accent = "#cccccc" if is_w else "#3a6fcc"
            won    = winner == player.get("id") if player else False
            row_bg = ("#081808" if (won and is_w) else "#080818" if (won and not is_w) else "#0a0a18")
            bdr    = (C_GREEN if (won and is_w) else C_BLUE if (won and not is_w) else C_BORDER)

            row = QWidget()
            row.setStyleSheet(f"background:{row_bg};border-left:3px solid {bdr};")
            row.setMinimumHeight(36)
            rl  = QHBoxLayout(row); rl.setContentsMargins(6,4,6,4); rl.setSpacing(6)

            dot = QLabel(); dot.setFixedSize(10,10)
            dot.setStyleSheet(f"background:{accent};border-radius:5px;")
            rl.addWidget(dot)

            if player:
                club = player.get("club","").strip()
                name_text = player.get("name","TBD")
                if club:
                    name_text = f"{name_text} ({club})"
            else:
                name_text = "TBD"
            is_champ = player and (player.get("id") in self._champion_ids)
            name_lbl = QLabel(name_text)
            name_color = C_GOLD if is_champ else ("#fff" if player else C_DIM)
            name_lbl.setStyleSheet(f"color:{name_color};font-size:14px;font-weight:bold;background:transparent;")
            fm = QFontMetrics(name_lbl.font())
            name_lbl.setText(fm.elidedText(name_lbl.text(), Qt.ElideRight, 280))
            rl.addWidget(name_lbl, stretch=1)

            if won:
                win_lbl = QLabel("WIN")
                win_lbl.setStyleSheet(f"color:{C_GOLD};font-size:9px;font-weight:bold;background:transparent;")
                rl.addWidget(win_lbl)

            cl.addWidget(row)

        if context == "repechage":
            tag = QLabel("BRONZE" if match.get("bronze") else "REPECHAGE")
            tag.setStyleSheet(f"color:{C_GOLD if match.get('bronze') else C_DIM};"
                              "font-size:9px;font-weight:bold;background:transparent;")
            cl.addWidget(tag)

        # Action buttons
        if not winner and white_p and blue_p and not is_bye:
            g, w = (self._active_key.split("-",1) if self._active_key else ("",""))
            cat_label = f"{'Men' if g=='male' else 'Women'} {w}"
            stage_label = round_label or ""
            start_btn = _btn("▶ START MATCH", C_RED, "#14060a", 28, 10)
            start_btn.clicked.connect(
                lambda _, wp=white_p, bp=blue_p, c=cat_label, st=stage_label:
                    self.on_start_match(wp["id"], bp["id"], c, st))
            cl.addWidget(start_btn)
        elif not winner and not is_bye:
            for side, player in [("white",white_p),("blue",blue_p)]:
                if player:
                    mb = _btn(f"Winner: {player['name'][:18]}", C_DIM, "#0e0e1e", 24, 9)
                    if context == "repechage":
                        mb.clicked.connect(
                            lambda _, pid=player["id"], r=ri, m=mi, sk=side_key:
                                self._mark_rep_winner(pid, r, m, sk))
                    elif context == "pool5":
                        mb.clicked.connect(
                            lambda _, pid=player["id"], r=ri, m=mi:
                                self._mark_pool5_winner(pid, "semi" if r == 0 else "final", m))
                    else:
                        mb.clicked.connect(
                            lambda _, pid=player["id"], r=ri, m=mi:
                                self._mark_winner(pid, r, m))
                    cl.addWidget(mb)
        return card

    def _mark_winner(self, winner_id, ri, mi):
        if not self._active_key: return
        draw = db.get_draw(self._active_key)
        if not draw: return
        eng.advance_winner(draw, ri, mi, winner_id, db.load_players())
        db.set_draw(self._active_key, draw)
        self._render(draw)

    def _mark_rep_winner(self, winner_id, ri, mi, side_key):
        if not self._active_key: return
        draw = db.get_draw(self._active_key)
        if not draw: return
        eng.advance_repechage(draw, side_key, ri, mi, winner_id, db.load_players())
        db.set_draw(self._active_key, draw)
        self._render(draw)

    def _mark_rr_winner(self, winner_id, match_idx):
        if not self._active_key: return
        draw = db.get_draw(self._active_key)
        if not draw: return
        eng.advance_winner(draw, 0, match_idx, winner_id, db.load_players())
        db.set_draw(self._active_key, draw)
        self._render(draw)

    def _mark_pool5_winner(self, winner_id, stage_key, match_idx):
        if not self._active_key: return
        draw = db.get_draw(self._active_key)
        if not draw: return
        eng.advance_pool5(draw, stage_key, match_idx, winner_id, db.load_players())
        db.set_draw(self._active_key, draw)
        self._render(draw)


class ConnectorWidget(QWidget):
    def __init__(self, centers, parent=None):
        super().__init__(parent)
        self.centers = centers
        self.setMinimumHeight(40)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        x = w // 2
        pen = QPen(QColor("#ffffff"), 1)
        p.setPen(pen)
        for cy in self.centers:
            p.drawLine(0, cy, x, cy)
        for i in range(0, len(self.centers), 2):
            if i + 1 >= len(self.centers):
                p.drawLine(x, self.centers[i], w, self.centers[i])
                continue
            y1, y2 = self.centers[i], self.centers[i + 1]
            p.drawLine(x, y1, x, y2)
            mid = (y1 + y2) // 2
            p.drawLine(x, mid, w, mid)
        p.end()

    pass
