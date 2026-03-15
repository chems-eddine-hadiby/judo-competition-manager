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
    QComboBox, QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QInputDialog
)
from PyQt5.QtCore  import Qt, QTimer
from PyQt5.QtGui   import QFont, QColor, QIcon, QKeySequence, QPalette

import os
import database as db
import github_sync as gsync
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

        grid.addWidget(QLabel("Competition name"), 3, 0)
        self.event_name = QLineEdit()
        self.event_name.setPlaceholderText("e.g. Open Cup 2026")
        grid.addWidget(self.event_name, 3, 1, 1, 3)

        grid.addWidget(QLabel("Custom category name"), 4, 0)
        self.custom_cat = QLineEdit()
        self.custom_cat.setPlaceholderText("e.g. VETERAN / OPEN / POUSSINS")
        grid.addWidget(self.custom_cat, 4, 1, 1, 3)

        add_row = QHBoxLayout()
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female"])
        self.gender_combo.setFixedWidth(90)
        self.new_weight = QLineEdit(); self.new_weight.setPlaceholderText("-66kg")
        self.add_weight = QPushButton("Add"); self.add_weight.clicked.connect(self._add_weight)
        self.remove_weight = QPushButton("Remove"); self.remove_weight.clicked.connect(self._remove_weight)
        add_row.addWidget(self.gender_combo)
        add_row.addWidget(self.new_weight)
        add_row.addWidget(self.add_weight)
        add_row.addWidget(self.remove_weight)
        layout.addLayout(add_row)

        sync = QVBoxLayout()
        sync.setSpacing(6)
        sync.addWidget(QLabel("Sync"))
        self.sync_list = QComboBox()
        self.sync_list.setMinimumHeight(28)
        sync.addWidget(self.sync_list)
        self.sync_password = QLineEdit()
        self.sync_password.setPlaceholderText("Competition password (for publish)")
        self.sync_password.setEchoMode(QLineEdit.Password)
        sync.addWidget(self.sync_password)
        sync_btns = QHBoxLayout()
        self.sync_refresh = QPushButton("Refresh list")
        self.sync_refresh.clicked.connect(self._sync_refresh)
        self.sync_publish = QPushButton("Publish competition")
        self.sync_publish.clicked.connect(self._sync_publish)
        self.sync_import = QPushButton("Import competition")
        self.sync_import.clicked.connect(self._sync_import)
        sync_btns.addWidget(self.sync_refresh)
        sync_btns.addWidget(self.sync_publish)
        sync_btns.addWidget(self.sync_import)
        sync.addLayout(sync_btns)
        layout.addLayout(sync)

        btn_row = QHBoxLayout()
        self.reset_app = QPushButton("Reset app info")
        self.reset_app.clicked.connect(self._reset_app_info)
        btn_row.addWidget(self.reset_app)
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
        self.event_name.setText(settings.get("event_name", "Competition"))
        self.custom_cat.setText(settings.get("custom_category_label", "Custom"))
        self._refresh_weights()

    def _refresh_weights(self):
        self.weights_list.clear()
        age_group = self.age_box.currentText()
        settings = db.load_settings()
        custom_text = settings.get("custom_weight_categories", "")
        removed_text = settings.get("removed_weight_categories", "")
        custom_by_gender = db.parse_custom_weights_by_gender(custom_text)
        removed_by_gender = db.parse_gendered_list(removed_text)

        def _add_item(gender, weight, is_base):
            prefix = "M" if gender == "male" else "F"
            item = QListWidgetItem(f"{prefix} {weight}")
            item.setData(Qt.UserRole, {"gender": gender, "weight": weight, "base": is_base})
            if is_base:
                item.setForeground(QColor("#8888aa"))
            self.weights_list.addItem(item)

        if age_group != "Custom":
            for w in db.get_age_group_weights(age_group, "male"):
                if w not in removed_by_gender.get("male", []):
                    _add_item("male", w, True)
            for w in db.get_age_group_weights(age_group, "female"):
                if w not in removed_by_gender.get("female", []):
                    _add_item("female", w, True)
        for w in custom_by_gender.get("male", []):
            _add_item("male", w, False)
        for w in custom_by_gender.get("female", []):
            _add_item("female", w, False)
        if age_group == "Custom":
            self.custom_cat.setEnabled(True)
        else:
            self.custom_cat.setEnabled(False)
            self.custom_cat.setText("")

    def _add_weight(self):
        text = self.new_weight.text().strip()
        if not text:
            return
        gender = "male" if self.gender_combo.currentText() == "Male" else "female"
        settings = db.load_settings()
        removed_text = settings.get("removed_weight_categories", "")
        removed_by_gender = db.parse_gendered_list(removed_text)
        if text in removed_by_gender.get(gender, []):
            removed_by_gender[gender] = [w for w in removed_by_gender[gender] if w != text]
            settings["removed_weight_categories"] = ",".join(
                [f"male:{w}" for w in removed_by_gender.get("male", [])] +
                [f"female:{w}" for w in removed_by_gender.get("female", [])]
            )
            db.save_settings(settings)
            self._refresh_weights()
            self.new_weight.clear()
            return
        # Prevent duplicates
        for i in range(self.weights_list.count()):
            it = self.weights_list.item(i)
            data = it.data(Qt.UserRole) or {}
            if data.get("gender") == gender and data.get("weight") == text:
                return
        prefix = "M" if gender == "male" else "F"
        item = QListWidgetItem(f"{prefix} {text}")
        item.setData(Qt.UserRole, {"gender": gender, "weight": text, "base": False})
        self.weights_list.addItem(item)
        self.new_weight.clear()

    def _remove_weight(self):
        current = self.weights_list.currentItem()
        if current:
            data = current.data(Qt.UserRole) or {}
            gender = data.get("gender")
            weight = data.get("weight")
            if not gender or not weight:
                return
            if data.get("base"):
                settings = db.load_settings()
                removed_text = settings.get("removed_weight_categories", "")
                removed_by_gender = db.parse_gendered_list(removed_text)
                if weight not in removed_by_gender.get(gender, []):
                    removed_by_gender[gender].append(weight)
                settings["removed_weight_categories"] = ",".join(
                    [f"male:{w}" for w in removed_by_gender.get("male", [])] +
                    [f"female:{w}" for w in removed_by_gender.get("female", [])]
                )
                db.save_settings(settings)
                self._refresh_weights()
                return
            self.weights_list.takeItem(self.weights_list.row(current))

    def _clear_competitors(self):
        if QMessageBox.question(self, "Clear competitors", "Remove all competitors from the database?") == QMessageBox.Yes:
            db.save_players([])
            QMessageBox.information(self, "Done", "Competitors cleared.")
    
    def _reset_app_info(self):
        if QMessageBox.question(
            self,
            "Reset app info",
            "This will reset settings and clear competitors, draws, and match history. Continue?"
        ) != QMessageBox.Yes:
            return
        db.save_settings(db.DEFAULT_SETTINGS.copy())
        db.save_players([])
        db.save_draws({})
        db.clear_match_history()
        self._load_settings()

    def _competition_folder(self):
        settings = db.load_settings()
        event = settings.get("event_name", "Competition")
        age = settings.get("age_group", "Senior")
        if age == "Custom":
            age = settings.get("custom_category_label", "Custom")
        return gsync.sanitize_folder_name(f"{event}-{age}")

    def double_base64_decrypt(encoded_string):
        # First decode
        first_decode = base64.b64decode(encoded_string)
        
        # Second decode
        second_decode = base64.b64decode(first_decode)
        
        # Convert bytes to string
        return second_decode.decode('utf-8')
    def _get_github_token(self):
        return double_base64_decrypt("WjJsMGFIVmlYM0JoZEY4eE1VSkpVMDVMVkZrd1JWSlNiM2RuT0hwQ1dGaHFYMUpHV0hNMU1ESkxXR2RsZWtZNVMyTjZZbGh3UmpCdWJEbFNabXAxV0VGRFRWSmxiSGxCTUU0MU5rRk1SMUpTVlZaTFZVTmtkbkZDUkdoUw==".strip()) or None

    def _sync_refresh(self):
        token = self._get_github_token()

        try:
            names = gsync.list_competitions(token)
        except Exception as e:
            QMessageBox.warning(self, "Sync error", str(e))
            return
        self.sync_list.clear()
        self.sync_list.addItems(names)

    def _sync_publish(self):
        token = self._get_github_token()
        if not token:
            QMessageBox.warning(self, "Missing token", "Set environment variable GITHUB_TOKEN first.")
            return

        password = self.sync_password.text().strip()
        if not password:
            QMessageBox.warning(self, "Missing password", "Set a competition password first.")
            return
        folder = self._competition_folder()
        if not folder:
            QMessageBox.warning(self, "Invalid name", "Competition name or age group is invalid.")
            return
        try:
            existing = gsync.list_competitions(token)
        except Exception as e:
            QMessageBox.warning(self, "Sync error", str(e))
            return
        if folder in existing:
            QMessageBox.warning(self, "Name exists", "Competition already exists. Use another name.")
            return

        import hashlib, secrets, datetime
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        meta = {
            "competition": folder,
            "created_at": datetime.datetime.now().isoformat(),
            "password_salt": salt,
            "password_hash": pwd_hash,
        }
        settings = db.load_settings()
        export_settings = dict(settings)
        export_settings.pop("github_token", None)
        message = f"Publish {folder}"
        try:
            gsync.put_json(token, folder, "meta.json", meta, message)
            gsync.put_json(token, folder, "players.json", db.load_players(), message)
            gsync.put_json(token, folder, "draws.json", db.load_draws(), message)
            gsync.put_json(token, folder, "matches.json", db.load_matches(), message)
            gsync.put_json(token, folder, "settings.json", export_settings, message)
        except Exception as e:
            QMessageBox.warning(self, "Sync error", str(e))
            return
        QMessageBox.information(self, "Published", "Competition published to GitHub.")
        self._sync_refresh()

    def _sync_import(self):
        token = self._get_github_token()
        if not token:
            QMessageBox.warning(self, "Missing token", "Set environment variable GITHUB_TOKEN first.")
            return

        folder = self.sync_list.currentText().strip()
        if not folder:
            QMessageBox.warning(self, "Missing selection", "Select a competition to import.")
            return
        pwd, ok = QInputDialog.getText(self, "Password", "Enter competition password:", QLineEdit.Password)
        if not ok:
            return
        try:
            meta = gsync.get_json(token, folder, "meta.json")
        except Exception as e:
            QMessageBox.warning(self, "Sync error", str(e))
            return
        import hashlib
        salt = meta.get("password_salt", "")
        expected = meta.get("password_hash", "")
        if hashlib.sha256((salt + pwd).encode("utf-8")).hexdigest() != expected:
            QMessageBox.warning(self, "Invalid password", "Password does not match.")
            return
        try:
            players = gsync.get_json(token, folder, "players.json")
            draws = gsync.get_json(token, folder, "draws.json")
            matches = gsync.get_json(token, folder, "matches.json")
            settings = gsync.get_json(token, folder, "settings.json")
        except Exception as e:
            QMessageBox.warning(self, "Sync error", str(e))
            return
        db.save_players(players)
        db.save_draws(draws)
        db.save_matches(matches)
        db.save_settings(settings)
        self._load_settings()
        QMessageBox.information(self, "Imported", "Competition imported.")

    def selected_weights(self):
        out = []
        for i in range(self.weights_list.count()):
            data = self.weights_list.item(i).data(Qt.UserRole) or {}
            if data.get("base"):
                continue
            g = data.get("gender")
            w = data.get("weight")
            if g and w:
                out.append((g, w))
        return out

    def accept(self):
        settings = db.load_settings()
        settings["age_group"] = self.age_box.currentText()
        seconds = max(1, self.btn_minutes.value() * 60 + self.btn_seconds.value())
        settings["match_duration"] = seconds
        settings["event_name"] = self.event_name.text().strip() or "Competition"
        settings["custom_weight_categories"] = ",".join(f"{g}:{w}" for g, w in self.selected_weights())
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
        self.setStyleSheet(f"""
            background:{C_BG}; color:{C_TEXT};
            QScrollBar:vertical {{
                background: {C_PANEL};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_RED};
                min-height: 24px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C_GOLD};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: {C_PANEL};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {C_RED};
                min-width: 24px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {C_GOLD};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: transparent;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
        """)

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
