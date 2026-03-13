# -*- coding: utf-8 -*-
"""
main.py — Judo Competition Manager · IJF 2026
PyQt5 desktop application, entry point + main window
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QTabWidget, QFrame, QSizePolicy, QStatusBar, QShortcut,
    QComboBox, QSpinBox, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore  import Qt, QTimer
from PyQt5.QtGui   import QFont, QColor, QIcon, QKeySequence, QPalette

import database as db
from match_engine     import MatchEngine, MATCH_DURATION
from scoreboard_window import ScoreboardWindow
from tab_match        import MatchTab
from tab_competitors  import CompetitorsTab
from tab_draw         import DrawTab
from tab_results      import ResultsTab


class ConfigDialog(QDialog):
    AGE_OPTIONS = ["Senior","Junior","Cadet","Custom"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Competition Settings")
        self.resize(540, 320)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        layout.addLayout(grid)

        grid.addWidget(QLabel("Age group"), 0, 0)
        self.age_box = QComboBox(); self.age_box.addItems(self.AGE_OPTIONS)
        grid.addWidget(self.age_box, 0, 1)

        grid.addWidget(QLabel("Minutes"), 1, 0)
        self.btn_minutes = QSpinBox(); self.btn_minutes.setRange(0, 10)
        grid.addWidget(self.btn_minutes, 1, 1)
        grid.addWidget(QLabel("Seconds"), 1, 2)
        self.btn_seconds = QSpinBox(); self.btn_seconds.setRange(0, 59)
        grid.addWidget(self.btn_seconds, 1, 3)

        grid.addWidget(QLabel("Weight categories"), 2, 0, 1, 4)
        self.weights_list = QListWidget()
        self.weights_list.setFixedHeight(120)
        layout.addWidget(self.weights_list)

        grid.addWidget(QLabel("Custom category name"), 3, 0)
        self.custom_cat = QLineEdit()
        self.custom_cat.setPlaceholderText("e.g. OPEN / CLUB / ELITE")
        grid.addWidget(self.custom_cat, 3, 1, 1, 3)

        add_row = QHBoxLayout()
        self.new_weight = QLineEdit(); self.new_weight.setPlaceholderText("-66kg")
        self.add_weight = QPushButton("Add"); self.add_weight.clicked.connect(self._add_weight)
        self.remove_weight = QPushButton("Remove"); self.remove_weight.clicked.connect(self._remove_weight)
        add_row.addWidget(self.new_weight)
        add_row.addWidget(self.add_weight)
        add_row.addWidget(self.remove_weight)
        layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        self.clear_users = QPushButton("Clear competitors"); self.clear_users.clicked.connect(self._clear_competitors)
        btn_row.addWidget(self.clear_users)
        btn_row.addStretch()
        self.accept_btn = QPushButton("Continue")
        self.accept_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.accept_btn)
        layout.addLayout(btn_row)

        self.age_box.currentTextChanged.connect(self._refresh_weights)
        self._load_settings()

    def _load_settings(self):
        settings = db.load_settings()
        self.age_box.setCurrentText(settings.get("age_group", "Senior"))
        total = settings.get("match_duration", 240)
        self.btn_minutes.setValue(total // 60)
        self.btn_seconds.setValue(total % 60)
        self.custom_cat.setText(settings.get("custom_category_label", "Custom"))
        self._refresh_weights()

    def _refresh_weights(self):
        self.weights_list.clear()
        age_group = self.age_box.currentText()
        custom_text = db.load_settings().get("custom_weight_categories", "")
        weights = []
        if age_group != "Custom":
            weights = db.get_age_group_weights(age_group, "male") + db.get_age_group_weights(age_group, "female")
            seen = []
            for w in weights:
                if w not in seen:
                    seen.append(w)
            weights = seen
        else:
            weights = [w.strip() for w in custom_text.split(",") if w.strip()]
        for w in weights:
            self.weights_list.addItem(w)
        self.custom_cat.setEnabled(age_group == "Custom")

    def _add_weight(self):
        text = self.new_weight.text().strip()
        if not text:
            return
        self.weights_list.addItem(text)
        self.new_weight.clear()

    def _remove_weight(self):
        current = self.weights_list.currentItem()
        if current:
            self.weights_list.takeItem(self.weights_list.row(current))

    def _clear_competitors(self):
        if QMessageBox.question(self, "Clear competitors", "Remove all competitors from the database?") == QMessageBox.Yes:
            db.save_players([])
            QMessageBox.information(self, "Done", "Competitors cleared.")

    def selected_weights(self):
        return [self.weights_list.item(i).text() for i in range(self.weights_list.count())]

    def accept(self):
        settings = db.load_settings()
        settings["age_group"] = self.age_box.currentText()
        seconds = max(1, self.btn_minutes.value() * 60 + self.btn_seconds.value())
        settings["match_duration"] = seconds
        settings["custom_weight_categories"] = ",".join(self.selected_weights())
        settings["custom_category_label"] = self.custom_cat.text().strip() or "Custom"
        db.save_settings(settings)
        super().accept()

C_BG    = "#0a0a12"
C_PANEL = "#0d0d1c"
C_RED   = "#D32F2F"
C_GOLD  = "#FFD600"
C_TEXT  = "#FFFFFF"
C_DIM   = "#666688"
C_CYAN  = "#00E676"
C_BORDER= "#1e1e35"

def _resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Judo Competition Manager · IJF 2026")
        self.setWindowIcon(QIcon(_resource_path("icon.ico")))
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        # Load settings
        settings = db.load_settings()

        # Shared match engine
        self.engine = MatchEngine(
            on_update=self._on_engine_update,
            match_duration=settings.get("match_duration", 240),
            allow_golden=settings.get("golden_score", True))

        self._scoreboard: ScoreboardWindow = None
        self._scoreboard_white_id = None
        self._scoreboard_blue_id = None
        self._scoreboard_white_player = None
        self._scoreboard_blue_player = None

        db.ensure_sample_players()
        self._build()

    # ── Build main window ─────────────────────────────────────────────────────

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background:{C_PANEL}; border-bottom:1px solid {C_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20,0,20,0)
        hl.setSpacing(16)

        # Logo
        logo_lbl = QLabel("⚔")
        logo_lbl.setFixedSize(36,36)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet(
            f"background:{C_RED};color:#fff;font-size:18px;font-weight:bold;"
            "border-radius:4px;")
        hl.addWidget(logo_lbl)

        title = QLabel("JUDO MANAGER")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#fff;background:transparent;")
        hl.addWidget(title)

        badge = QLabel(" IJF 2026 ")
        badge.setStyleSheet(f"color:{C_RED};background:transparent;font-size:11px;font-weight:bold;")
        hl.addWidget(badge)

        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"background:{C_BORDER};"); sep.setFixedWidth(1)
        hl.addWidget(sep)

        # Live indicator
        self.lbl_live = QLabel("● STANDBY")
        self.lbl_live.setStyleSheet(f"color:{C_DIM};background:transparent;font-size:12px;font-weight:bold;")
        hl.addWidget(self.lbl_live)

        hl.addStretch()

        # Event name
        ev_lbl = QLabel("EVENT:")
        ev_lbl.setStyleSheet(f"color:{C_DIM};background:transparent;font-size:10px;font-weight:bold;")
        hl.addWidget(ev_lbl)

        settings = db.load_settings()
        self.event_edit = QLineEdit(settings.get("event_name","Judo Championship"))
        self.event_edit.setFixedWidth(280)
        self.event_edit.setStyleSheet(
            "background:#1a1a2e;color:#fff;border:1px solid #2a2a4a;"
            "border-radius:3px;padding:5px 8px;font-size:11px;"
            "selection-background-color:#D32F2F;selection-color:#ffffff;")
        self.event_edit.textChanged.connect(self._on_event_name_change)
        hl.addWidget(self.event_edit)

        self.btn_config = QPushButton("⚙️  CONFIG COMPETITION")
        self.btn_config.setMinimumHeight(36)
        self.btn_config.setStyleSheet("""
            QPushButton {
                background: #111129; color: #fff;
                border: 1px solid #2a2a4a; border-radius: 4px;
                font-size: 11px; font-weight: bold; padding: 4px 14px;
            }
            QPushButton:hover { background: #1a1a32; }
        """)
        self.btn_config.clicked.connect(self._open_config_panel)
        hl.addWidget(self.btn_config)

        # Scoreboard button
        self.btn_scoreboard = QPushButton("📺  OPEN PUBLIC SCOREBOARD")
        self.btn_scoreboard.setMinimumHeight(36)
        self.btn_scoreboard.setStyleSheet("""
            QPushButton {
                background: #0e0e28; color: #7ab4ff;
                border: 1px solid #2a2a5a; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 4px 16px;
            }
            QPushButton:hover { background: #1a1a3a; }
        """)
        self.btn_scoreboard.clicked.connect(self._open_scoreboard)
        hl.addWidget(self.btn_scoreboard)

        root.addWidget(header)

        # ── Tabs ──────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none; background: {C_BG};
            }}
            QTabBar::tab {{
                background: {C_PANEL}; color: {C_DIM};
                padding: 10px 22px; font-size: 12px; font-weight: bold;
                border: none; border-bottom: 3px solid transparent;
                min-width: 140px;
            }}
            QTabBar::tab:selected {{
                color: {C_TEXT}; border-bottom: 3px solid {C_RED};
                background: {C_BG};
            }}
            QTabBar::tab:hover {{ color: {C_TEXT}; background: {C_BG}; }}
        """)

        self.match_tab = MatchTab(self.engine,
                                  on_update=self._on_engine_update,
                                  on_profile_change=self._on_profile_change,
                                  on_draw_update=self._on_draw_update)
        self.comp_tab  = CompetitorsTab(on_change=self._on_competitors_change)
        self.draw_tab  = DrawTab(on_start_match=self._start_match_from_draw)
        self.res_tab   = ResultsTab()

        self.tabs.addTab(self.match_tab, "⏱  MATCH CONTROL")
        self.tabs.addTab(self.comp_tab,  "👥  COMPETITORS")
        self.tabs.addTab(self.draw_tab,  "🏆  DRAW")
        self.tabs.addTab(self.res_tab,   "📊  RESULTS")

        root.addWidget(self.tabs, stretch=1)

        # ── Status bar ────────────────────────────────────────────────────
        status = self.statusBar()
        status.setStyleSheet(f"background:{C_PANEL};color:{C_DIM};font-size:9px;")
        self.lbl_status = QLabel(f"Data: {db.get_data_dir()}")
        status.addWidget(self.lbl_status)

        self._apply_settings()

        # ── Keyboard shortcuts ────────────────────────────────────────────
        QShortcut(QKeySequence("Space"), self, self.engine.toggle)
        QShortcut(QKeySequence("F11"),   self, self._toggle_scoreboard_fullscreen)

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _on_engine_update(self):
        try:
            if self.engine.finished:
                self.lbl_live.setText("● MATCH OVER")
                self.lbl_live.setStyleSheet(f"color:{C_RED};background:transparent;font-size:12px;font-weight:bold;")
            elif self.engine.running:
                self.lbl_live.setText("● LIVE")
                self.lbl_live.setStyleSheet(f"color:{C_CYAN};background:transparent;font-size:12px;font-weight:bold;")
            else:
                self.lbl_live.setText("● STANDBY")
                self.lbl_live.setStyleSheet(f"color:{C_DIM};background:transparent;font-size:12px;font-weight:bold;")

            if self._scoreboard and not self._scoreboard.isHidden():
                if self.engine.white_id != self._scoreboard_white_id:
                    self._scoreboard_white_id = self.engine.white_id
                    self._scoreboard_white_player = (
                        db.get_player(self.engine.white_id) if self.engine.white_id else None
                    )
                if self.engine.blue_id != self._scoreboard_blue_id:
                    self._scoreboard_blue_id = self.engine.blue_id
                    self._scoreboard_blue_player = (
                        db.get_player(self.engine.blue_id) if self.engine.blue_id else None
                    )
                wp = self._scoreboard_white_player
                bp = self._scoreboard_blue_player
                self._scoreboard.update_state(self.engine, wp, bp)
        except Exception:
            pass

    def _open_config_panel(self):
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._apply_settings()

    def _apply_settings(self):
        settings = db.load_settings()
        stage = settings.get("stage", "Final")
        match_time = settings.get("match_duration", MATCH_DURATION)
        allow_golden = settings.get("golden_score", True)
        self.engine.set_stage(stage)
        self.engine.set_match_duration(match_time)
        self.engine.set_allow_golden(allow_golden)
        if hasattr(self, "draw_tab"):
            self.draw_tab.refresh_categories()
        if hasattr(self, "match_tab"):
            self.match_tab.refresh_from_settings()
        self._on_engine_update()

    def _on_competitors_change(self):
        self.match_tab.refresh_competitors()
        self.draw_tab.refresh_categories()
        self._scoreboard_white_id = None
        self._scoreboard_blue_id = None
        self._scoreboard_white_player = None
        self._scoreboard_blue_player = None

    def _on_profile_change(self):
        self.draw_tab.refresh_categories()
        self._on_engine_update()

    def _on_draw_update(self):
        self.draw_tab.refresh_categories()
        if self.draw_tab._active_key:
            self.draw_tab._render(db.get_draw(self.draw_tab._active_key))
        if hasattr(self, "res_tab"):
            self.res_tab.refresh()

    def _on_event_name_change(self, name):
        if self._scoreboard:
            self._scoreboard.set_event_name(name)
        s = db.load_settings(); s["event_name"]=name; db.save_settings(s)

    def _start_match_from_draw(self, white_id, blue_id, category, stage=None):
        self.match_tab.load_match(white_id, blue_id, category, stage=stage)
        self.tabs.setCurrentIndex(0)

    # ── Public scoreboard ──────────────────────────────────────────────────────

    def _open_scoreboard(self):
        if self._scoreboard is None or self._scoreboard.isHidden():
            self._scoreboard = ScoreboardWindow(self)
            self._scoreboard.show()
        else:
            self._scoreboard.raise_()
            self._scoreboard.activateWindow()
        self._scoreboard.set_event_name(self.event_edit.text())
        self._scoreboard_white_id = self.engine.white_id
        self._scoreboard_blue_id = self.engine.blue_id
        self._scoreboard_white_player = db.get_player(self.engine.white_id) if self.engine.white_id else None
        self._scoreboard_blue_player = db.get_player(self.engine.blue_id)  if self.engine.blue_id  else None
        wp = self._scoreboard_white_player
        bp = self._scoreboard_blue_player
        self._scoreboard.update_state(self.engine, wp, bp)

    def _toggle_scoreboard_fullscreen(self):
        if self._scoreboard:
            if self._scoreboard.isFullScreen(): self._scoreboard.showNormal()
            else:                               self._scoreboard.showFullScreen()

    # ── Close ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        s = db.load_settings()
        s["event_name"] = self.event_edit.text()
        db.save_settings(s)
        super().closeEvent(event)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Judo Manager")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(_resource_path("icon.ico")))

    # Dark palette for native dialogs
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#0a0a12"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#0e0e1a"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#111120"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#1a1a2e"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#D32F2F"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    config = ConfigDialog()
    if config.exec() != QDialog.Accepted:
        return

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
