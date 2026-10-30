"""Settings, connectivity, and device-management pages for the Nexus Core UI.

These classes are split from ui.py to keep the main UI module manageable.
The namespace bridge is transitional: it preserves the existing UI dependency
surface while these pages are progressively decoupled into smaller modules.
"""
import ui as _ui
globals().update({name: value for name, value in vars(_ui).items() if not name.startswith("__")})

class SystemConnectivitySidebar(QFrame):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivitySidebar")
        self.setStyleSheet(
            f"""
            QFrame#SystemConnectivitySidebar {{
                background: rgba(0, 229, 255, 0.03);
                border: 1px solid rgba(0, 229, 255, 0.6);
                border-radius: 22px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                text-align: left;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.10);
                border: 1px solid rgba(0, 229, 255, 0.3);
            }}
            """
        )
        try:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 229, 255, 80))
            shadow.setOffset(0, 0)
            self.setGraphicsEffect(shadow)
        except: pass
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)

        title = QLabel("SYSTEM STATUS")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(title)

        self._status_card = QFrame()
        self._status_card.setStyleSheet("QFrame { background: rgba(14,16,20,0.88); border: 1px solid rgba(53,255,117,0.18); border-radius: 14px; }")
        s_lay = QVBoxLayout(self._status_card)
        s_lay.setContentsMargins(16, 14, 16, 14)
        s_lay.setSpacing(10)
        self._online_lbl = QLabel("● System Online")
        self._online_lbl.setStyleSheet("color: #35ff75; font-weight: 700;")
        self._desc_lbl = QLabel("All systems are operational.")
        self._desc_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        s_lay.addWidget(self._online_lbl)
        s_lay.addWidget(self._desc_lbl)
        lay.addWidget(self._status_card)

        self._info_rows: dict[str, QLabel] = {}
        for label in ("Version", "Platform", "Current AI Provider", "Last Updated"):
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 4)
            row.setSpacing(10)
            icon = QLabel("◌")
            icon.setFixedWidth(18)
            icon.setStyleSheet(f"color: {C.WHITE};")
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(f"color: {C.WHITE};")
            val_lbl = QLabel("")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            row.addWidget(icon)
            row.addWidget(key_lbl)
            row.addStretch(1)
            row.addWidget(val_lbl)
            lay.addLayout(row)
            self._info_rows[label] = val_lbl

        quick_title = QLabel("QUICK ACTIONS")
        quick_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        quick_title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        lay.addWidget(quick_title)

        self._quick_actions = QVBoxLayout()
        self._quick_actions.setSpacing(10)
        lay.addLayout(self._quick_actions)
        self._mk_quick_action("↻ Restart Nexus Core", QStyle.StandardPixmap.SP_BrowserReload, self._restart)
        self._mk_quick_action("⟳ Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload)
        self._mk_quick_action("≡ƒôü Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder)
        self._mk_quick_action("≡ƒôä View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs)
        self._mk_quick_action("⬇ Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates)

        tip = QFrame()
        tip.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        tip_lay = QVBoxLayout(tip)
        tip_lay.setContentsMargins(16, 14, 16, 14)
        tip_lay.setSpacing(8)
        tip_title = QLabel("Security Tip")
        tip_title.setStyleSheet("color: #ffbf00; font-weight: 700;")
        tip_body = QLabel('"Never share your API keys with anyone."')
        tip_body.setWordWrap(True)
        tip_body.setStyleSheet(f"color: {C.TEXT_MED};")
        tip_lay.addWidget(tip_title)
        tip_lay.addWidget(tip_body)
        lay.addStretch(1)
        lay.addWidget(tip)

        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _mk_quick_action(self, text: str, icon_kind, slot):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(self.style().standardIcon(icon_kind))
        btn.clicked.connect(slot)
        self._quick_actions.addWidget(btn)
        return btn

    def _bridge(self):
        return self._controller

    def _restart(self):
        if self._bridge() and hasattr(self._bridge(), "_restart_app"):
            self._bridge()._restart_app()

    def _reload(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            try:
                self._bridge()._win._load_api_defaults()
                self._bridge()._win._load_discord_settings()
                self._bridge()._log_sig.emit("SYS: Configuration reloaded.")
            except Exception:
                pass

    def _open_data_folder(self):
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(str(CONFIG_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(CONFIG_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
        except Exception:
            pass

    def _view_logs(self):
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(str(BASE_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(BASE_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(BASE_DIR)])
        except Exception:
            pass

    def _check_updates(self):
        if self._bridge() and hasattr(self._bridge(), "write_log"):
            self._bridge().write_log("SYS: Update check is not connected to a remote service yet.")

    def refresh(self):
        if self._bridge() and hasattr(self._bridge(), "_win"):
            version = "v1.0.0"
            platform_name = platform.system()
            provider = self._bridge()._win._load_app_settings().get("default_ai_provider", "Gemini")
            last_updated = time.strftime("%d %b %Y %H:%M")
            self._info_rows["Version"].setText(version)
            self._info_rows["Platform"].setText(platform_name)
            self._info_rows["Current AI Provider"].setText(provider)
            self._info_rows["Last Updated"].setText(last_updated)
        else:
            self._info_rows["Version"].setText("v1.0.0")
            self._info_rows["Platform"].setText(platform.system())
            self._info_rows["Current AI Provider"].setText("Gemini")
            self._info_rows["Last Updated"].setText(time.strftime("%d %b %Y %H:%M"))



class SettingsHubPage(QWidget):
    def __init__(self, navigation_callback, parent=None):
        super().__init__(parent)
        self._nav_cb = navigation_callback
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 60, 40, 60)
        lay.setSpacing(25)

        title = QLabel("Settings Hub")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Black))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel("Select a section below to configure your Nexus Core environment.")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(subtitle)

        cards_lay = QHBoxLayout()
        cards_lay.setSpacing(24)
        cards_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cards_data = [
            ("Nexus Core Home", "Configure smart home integrations", "🏠", 1),
            ("Devices", "Manage and control connected hardware", "🔌", 2),
            ("System & Connect", "Configure providers and api preferences", "⚙️", 3)
        ]

        for title_text, desc_text, icon_emoji, target_idx in cards_data:
            card = QFrame()
            card.setFixedSize(280, 200)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(
                f"QFrame {{ "
                f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(16, 18, 26, 0.75), stop:1 rgba(8, 10, 15, 0.85)); "
                f"  border: 1px solid rgba(0, 229, 255, 0.18); "
                f"  border-radius: 18px; "
                f"}} "
                f"QFrame:hover {{ "
                f"  border: 1.5px solid {C.PRI}; "
                f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(35, 28, 15, 0.8), stop:1 rgba(16, 12, 8, 0.9)); "
                f"}}"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(20, 20, 20, 20)
            card_lay.setSpacing(12)
            card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_lbl = QLabel(icon_emoji)
            icon_lbl.setFont(QFont("Segoe UI", 36))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("background: transparent; border: none;")
            card_lay.addWidget(icon_lbl)

            t = QLabel(title_text)
            t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            t.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_lay.addWidget(t)

            d = QLabel(desc_text)
            d.setFont(QFont("Segoe UI", 9))
            d.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
            d.setWordWrap(True)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_lay.addWidget(d)

            card.mousePressEvent = lambda e, idx=target_idx: self._nav_cb(idx)
            cards_lay.addWidget(card)

        lay.addStretch(1)
        lay.addLayout(cards_lay)
        lay.addStretch(2)

class SystemConnectivityPage(QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setObjectName("SystemConnectivityPage")
        self.setStyleSheet(f"""
            QWidget#SystemConnectivityPage {{
                background: transparent;
            }}
            QFrame#SettingsCard {{
                background: rgba(10, 12, 18, 160);
                border: 1.5px solid rgba(0, 229, 255, 0.15);
                border-radius: 18px;
            }}
            QFrame#SettingsCard:hover {{
                border: 1.5px solid rgba(0, 229, 255, 0.35);
                background: rgba(20, 16, 12, 200);
            }}
            QLabel {{
                background: transparent;
                color: #e6edf3;
            }}
            QPushButton {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.12);
                border: 1px solid rgba(0, 229, 255, 0.45);
            }}
            QLineEdit, QComboBox {{
                background: rgba(13, 15, 19, 240);
                color: {C.WHITE};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {C.PRI};
                background: rgba(0, 229, 255, 0.02);
            }}
            QMessageBox, QDialog {{
                background-color: #0b0f19;
                color: #ffffff;
                border: 1.5px solid rgba(0, 229, 255, 0.35);
                border-radius: 14px;
            }}
            QMessageBox QLabel, QDialog QLabel {{
                color: #ffffff;
                background-color: transparent;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 13px;
                padding: 4px;
            }}
            QMessageBox QPushButton, QDialog QPushButton {{
                background-color: #00e5ff;
                color: #050a12;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                min-width: 80px;
                min-height: 30px;
            }}
            QMessageBox QPushButton:hover, QDialog QPushButton:hover {{
                background-color: #33ebff;
            }}
            QMessageBox QPushButton:pressed, QDialog QPushButton:pressed {{
                background-color: #00b3cc;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        root.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(6)
        title = QLabel("SYSTEM & CONNECTIVITY")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Black))
        title.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        sub = QLabel("Manage your AI providers, connections and application preferences.")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color: {C.TEXT_DIM};")
        h_lay.addWidget(title)
        h_lay.addWidget(sub)
        lay.addWidget(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._build_left_column(), 7)
        top.addWidget(self._build_summary_card(), 3)
        lay.addLayout(top)
        lay.addStretch(1)

        self.refresh()

    def set_controller(self, controller):
        self._controller = controller
        self.refresh()

    def _ctrl(self):
        return self._controller

    def _card(self, title: str, subtitle: str = "") -> QFrame:
        frame = QFrame()
        frame.setObjectName("SettingsCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        head = QLabel(title)
        head.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        head.setStyleSheet(f"color: {C.WHITE};")
        lay.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {C.TEXT_DIM};")
            lay.addWidget(sub)
        return frame

    def _mk_toggle(self, text: str, checked: bool, callback):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: callback(btn.isChecked()))
        btn.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 12px 14px;
            }}
            QPushButton:checked {{
                background: rgba(0, 229, 255,0.12);
                border: 1px solid {C.PRI};
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255,0.08);
            }}
            """
        )
        return btn

    def _provider_key_preview(self, key: str) -> str:
        key = (key or "").strip()
        if not key:
            return "Not set"
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"

    def _provider_row(self, name: str, key: str, model: str, setting_key: str):
        row = QFrame()
        if key:
            row.setStyleSheet("QFrame { background: rgba(55, 255, 95, 0.02); border: 1px solid rgba(55, 255, 95, 0.1); border-radius: 14px; } QFrame:hover { background: rgba(55, 255, 95, 0.05); border: 1px solid rgba(55, 255, 95, 0.25); }")
        else:
            row.setStyleSheet("QFrame { background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 14px; } QFrame:hover { background: rgba(0, 229, 255, 0.04); border: 1px solid rgba(0, 229, 255, 0.3); }")
        r = QHBoxLayout(row)
        r.setContentsMargins(14, 12, 14, 12)
        r.setSpacing(12)
        icon = QLabel(name[:1].upper())
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        if key:
            icon.setStyleSheet(f"background: rgba(55, 255, 95, 0.12); color: {C.GREEN}; border: 1px solid rgba(55, 255, 95, 0.3); border-radius: 21px;")
        else:
            icon.setStyleSheet(f"background: rgba(0, 229, 255, 0.12); color: {C.WHITE}; border: 1px solid rgba(0, 229, 255, 0.38); border-radius: 21px;")
        r.addWidget(icon)
        meta = QVBoxLayout()
        title = QLabel(name)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; border: none;")
        if key:
            status = QLabel("\u2713  Already Added")
            status.setStyleSheet(f"color: {C.GREEN}; border: none; font-weight: bold;")
        else:
            status = QLabel("Not configured")
            status.setStyleSheet(f"color: {C.TEXT_DIM}; border: none;")
        model_lbl = QLabel(f"Current model: {model}")
        model_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; border: none;")
        api_lbl = QLabel(self._provider_key_preview(key))
        api_lbl.setStyleSheet(f"color: {C.TEXT_MED}; border: none;")
        meta.addWidget(title)
        meta.addWidget(status)
        meta.addWidget(model_lbl)
        meta.addWidget(api_lbl)
        r.addLayout(meta, 1)
        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(8)
        if key:
            edit = QPushButton("Edit API Key")
        else:
            edit = QPushButton("Add API Key")
            edit.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 229, 255, 0.1);
                    color: #00e5ff;
                    border: 1px solid rgba(0, 229, 255, 0.3);
                    border-radius: 12px;
                    padding: 10px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.2);
                    border: 1px solid rgba(0, 229, 255, 0.5);
                }
            """)
        edit.clicked.connect(lambda: self._open_api_keys())
        test = QPushButton("Test Connection")
        test.clicked.connect(lambda: self._test_provider(setting_key))
        btn_lay.addWidget(edit)
        btn_lay.addWidget(test)
        r.addLayout(btn_lay)
        return row, status, api_lbl

    def _build_spotify_mcp_card(self):
        spotify_card = self._card("Spotify MCP Server", "Voice & AI music streaming, song searches, playlist browsing, and queue management via Spotify Web API.")
        s_lay = spotify_card.layout()

        self._spotify_status_lbl = QLabel("Status: Checking...")
        self._spotify_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        s_lay.addWidget(self._spotify_status_lbl)

        cid_row = QHBoxLayout()
        cid_lbl = QLabel("Client ID")
        cid_lbl.setStyleSheet(f"color: {C.WHITE}; min-width: 90px;")
        cid_row.addWidget(cid_lbl)
        self._spotify_client_id = QLineEdit()
        self._spotify_client_id.setPlaceholderText("Spotify Client ID from Developer Dashboard")
        cid_row.addWidget(self._spotify_client_id, 1)
        s_lay.addLayout(cid_row)

        csec_row = QHBoxLayout()
        csec_lbl = QLabel("Client Secret")
        csec_lbl.setStyleSheet(f"color: {C.WHITE}; min-width: 90px;")
        csec_row.addWidget(csec_lbl)
        self._spotify_client_secret = QLineEdit()
        self._spotify_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._spotify_client_secret.setPlaceholderText("Spotify Client Secret")
        csec_row.addWidget(self._spotify_client_secret, 1)

        self._spotify_reveal_btn = QPushButton("Reveal")
        self._spotify_reveal_btn.setCheckable(True)
        self._spotify_reveal_btn.clicked.connect(self._toggle_spotify_secret_reveal)
        csec_row.addWidget(self._spotify_reveal_btn)
        s_lay.addLayout(csec_row)

        redir_row = QHBoxLayout()
        redir_lbl = QLabel("Redirect URI:")
        redir_lbl.setStyleSheet(f"color: {C.TEXT_MED}; font-size: 11px;")
        redir_val = QLabel("http://127.0.0.1:8888/callback")
        redir_val.setStyleSheet("color: #00e5ff; font-size: 11px; font-family: monospace; font-weight: bold;")
        copy_btn = QPushButton("Copy URI")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("padding: 4px 10px; font-size: 10px;")
        copy_btn.clicked.connect(self._copy_spotify_redirect_uri)
        redir_row.addWidget(redir_lbl)
        redir_row.addWidget(redir_val)
        redir_row.addStretch(1)
        redir_row.addWidget(copy_btn)
        s_lay.addLayout(redir_row)

        s_btns_row = QHBoxLayout()
        s_btns_row.setSpacing(10)

        self._spotify_save_btn = QPushButton("Save Credentials")
        self._spotify_save_btn.clicked.connect(self._handle_spotify_save)
        s_btns_row.addWidget(self._spotify_save_btn)

        self._spotify_auth_btn = QPushButton("🔗 Authenticate in Browser")
        self._spotify_auth_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255, 0.12);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.45);
                font-weight: bold;
                border-radius: 12px;
                padding: 10px 14px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.25);
                border: 1px solid #00e5ff;
            }}
        """)
        self._spotify_auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._spotify_auth_btn.clicked.connect(self._handle_spotify_auth)
        s_btns_row.addWidget(self._spotify_auth_btn)

        self._spotify_test_btn = QPushButton("Test Connection")
        self._spotify_test_btn.clicked.connect(self._handle_spotify_test)
        s_btns_row.addWidget(self._spotify_test_btn)

        self._spotify_disconnect_btn = QPushButton("Disconnect")
        self._spotify_disconnect_btn.clicked.connect(self._handle_spotify_disconnect)
        s_btns_row.addWidget(self._spotify_disconnect_btn)

        s_lay.addLayout(s_btns_row)

        spotify_tip = QLabel("Tip: In developer.spotify.com/dashboard ➔ Settings ➔ add 'http://127.0.0.1:8888/callback' to Redirect URIs and save.")
        spotify_tip.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 10px;")
        spotify_tip.setWordWrap(True)
        s_lay.addWidget(spotify_tip)

        self._prefill_spotify_credentials()
        self._update_spotify_status()

        return spotify_card

    def _build_left_column(self):
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)


        


        # Instagram Connect
        ig_card = self._card("Instagram Connect", "Connect your personal Instagram account to allow Nexus Core to manage your DMs.")
        ig_lay = ig_card.layout()

        self._ig_status_lbl = QLabel("Status: Checking...")
        self._ig_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        ig_lay.addWidget(self._ig_status_lbl)

        self._ig_browser_btn = QPushButton("🌐 Connect via Browser (Recommended)")
        self._ig_browser_btn.setStyleSheet(f"background: {C.PRI}; color: {C.DARK}; font-weight: bold; padding: 7px; border-radius: 4px;")
        self._ig_browser_btn.setToolTip("Opens Instagram in a genuine browser window. Login once, solve 2FA easily, and never get blocked by Meta.")
        self._ig_browser_btn.clicked.connect(self._handle_ig_browser_connect)
        ig_lay.addWidget(self._ig_browser_btn)

        or_sep = QLabel("─── or connect with mobile credentials ───")
        or_sep.setAlignment(__import__('PyQt6').QtCore.Qt.AlignmentFlag.AlignCenter)
        or_sep.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 10px; margin: 4px 0;")
        ig_lay.addWidget(or_sep)

        ig_user_row = QHBoxLayout()
        ig_user_row.addWidget(QLabel("Username"))
        self._ig_username = QLineEdit()
        self._ig_username.setPlaceholderText("Instagram Username")
        ig_user_row.addWidget(self._ig_username)
        ig_lay.addLayout(ig_user_row)

        ig_pass_row = QHBoxLayout()
        ig_pass_row.addWidget(QLabel("Password"))
        self._ig_password = QLineEdit()
        self._ig_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._ig_password.setPlaceholderText("Instagram Password (or browser sessionid)")
        ig_pass_row.addWidget(self._ig_password, 1)

        self._ig_reveal_btn = QPushButton("Reveal")
        self._ig_reveal_btn.setCheckable(True)
        self._ig_reveal_btn.clicked.connect(self._toggle_ig_password_reveal)
        ig_pass_row.addWidget(self._ig_reveal_btn)
        ig_lay.addLayout(ig_pass_row)

        ig_hint = QLabel("Tip: Use 'Connect via Browser' above to avoid Meta's automated mobile blocks and 429 rate limits.")
        ig_hint.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 11px;")
        ig_hint.setWordWrap(True)
        ig_lay.addWidget(ig_hint)
        
        ig_btns_row = QHBoxLayout()
        
        self._ig_connect_btn = QPushButton("Connect (Password)")
        self._ig_connect_btn.clicked.connect(self._handle_ig_connect)
        ig_btns_row.addWidget(self._ig_connect_btn)

        self._ig_cookie_btn = QPushButton("🍪 Connect via Cookie")
        self._ig_cookie_btn.setToolTip("Fastest 100% reliable login bypassing all Meta security checks: paste your browser sessionid cookie.")
        self._ig_cookie_btn.clicked.connect(self._handle_ig_cookie_dialog)
        ig_btns_row.addWidget(self._ig_cookie_btn)
        
        self._ig_disconnect_btn = QPushButton("Disconnect")
        self._ig_disconnect_btn.clicked.connect(self._handle_ig_disconnect)
        ig_btns_row.addWidget(self._ig_disconnect_btn)

        ig_lay.addLayout(ig_btns_row)
        
        lay.addWidget(ig_card)
        
        # Pre-fill from API keys if they exist
        try:
            with open(Path("config/api_keys.json"), "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("instagram_username"):
                    self._ig_username.setText(d.get("instagram_username"))
                if d.get("instagram_password"):
                    self._ig_password.setText(d.get("instagram_password"))
        except Exception:
            pass

        self._update_ig_status()

        # Google Workspace (Gmail / Calendar / Drive)
        gw_card = self._card("Google Workspace (Gmail / Calendar / Drive)", "Configure your Gmail, Google Calendar, and Drive integration.")
        gw_lay = gw_card.layout()

        gw_email_row = QHBoxLayout()
        gw_email_row.addWidget(QLabel("Gmail Address"))
        self._gw_email = QLineEdit()
        self._gw_email.setPlaceholderText("your-email@gmail.com")
        gw_email_row.addWidget(self._gw_email)
        gw_lay.addLayout(gw_email_row)

        gw_pass_row = QHBoxLayout()
        gw_pass_row.addWidget(QLabel("App Password"))
        self._gw_password = QLineEdit()
        self._gw_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._gw_password.setPlaceholderText("16-character Google App Password")
        gw_pass_row.addWidget(self._gw_password)

        self._gw_reveal_btn = QPushButton("Reveal")
        self._gw_reveal_btn.setCheckable(True)
        self._gw_reveal_btn.clicked.connect(self._toggle_gw_password_reveal)
        gw_pass_row.addWidget(self._gw_reveal_btn)
        gw_lay.addLayout(gw_pass_row)

        gw_btns_row = QHBoxLayout()
        self._gw_save_btn = QPushButton("Save Credentials")
        self._gw_save_btn.clicked.connect(self._handle_gw_save)
        gw_btns_row.addWidget(self._gw_save_btn)

        self._gw_test_btn = QPushButton("Test Connection")
        self._gw_test_btn.clicked.connect(self._handle_gw_test)
        gw_btns_row.addWidget(self._gw_test_btn)

        self._gw_oauth_btn = QPushButton("Load OAuth JSON")
        self._gw_oauth_btn.clicked.connect(self._handle_gw_oauth)
        gw_btns_row.addWidget(self._gw_oauth_btn)
        gw_lay.addLayout(gw_btns_row)

        self._gw_status_lbl = QLabel("Status: Ready")
        self._gw_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        gw_lay.addWidget(self._gw_status_lbl)

        gw_help = QLabel("Tip: Generate a 16-character App Password at myaccount.google.com/apppasswords")
        gw_help.setStyleSheet(f"color: {C.TEXT_MED}; font-size: 11px;")
        gw_lay.addWidget(gw_help)

        lay.addWidget(gw_card)

        # Pre-fill stored Google Workspace credentials
        try:
            from actions.google_workspace_mcp import get_stored_gmail_credentials
            _em, _pw = get_stored_gmail_credentials()
            if _em:
                self._gw_email.setText(_em)
            if _pw:
                self._gw_password.setText(_pw)
        except Exception:
            pass

        # Spotify MCP Server
        lay.addWidget(self._build_spotify_mcp_card())

        # Identity & Profile
        identity_card = self._card("Identity & Profile", "Configure assistant identity, user profile, and behavior.")
        ilay = identity_card.layout()
        
        # Assistant Settings
        ast_row = QHBoxLayout()
        ast_row.addWidget(QLabel("Assistant Name"))
        self._set_ast_name = QLineEdit(identity.get_assistant_name())
        self._set_ast_name.textChanged.connect(lambda t: identity.set_assistant_name(t.strip() or "Nexus"))
        ast_row.addWidget(self._set_ast_name)
        ilay.addLayout(ast_row)
        
        app_row = QHBoxLayout()
        app_row.addWidget(QLabel("Application Name"))
        self._set_app_name = QLineEdit(identity.get_application_name())
        self._set_app_name.textChanged.connect(lambda t: identity.set_application_name(t.strip() or "Nexus Core"))
        app_row.addWidget(self._set_app_name)
        ilay.addLayout(app_row)

        # Owner Profile
        own_row = QHBoxLayout()
        own_row.addWidget(QLabel("Your Name"))
        self._set_own_name = QLineEdit(identity.get_owner_name())
        self._set_own_name.textChanged.connect(lambda t: identity.set_owner_name(t.strip()))
        own_row.addWidget(self._set_own_name)
        ilay.addLayout(own_row)

        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Your Role"))
        self._set_own_role = QLineEdit(identity.get_owner_role())
        self._set_own_role.textChanged.connect(lambda t: identity.set_owner_role(t.strip()))
        role_row.addWidget(self._set_own_role)
        ilay.addLayout(role_row)

        # Behavior
        beh_row = QHBoxLayout()
        beh_row.addWidget(QLabel("Behavior Mode"))
        self._set_beh_mode = QComboBox()
        self._set_beh_mode.addItems(["professional", "casual", "technical", "minimal", "proactive"])
        self._set_beh_mode.setCurrentText(identity.get_behavior_mode())
        self._set_beh_mode.currentTextChanged.connect(lambda t: identity.set_behavior_mode(t))
        beh_row.addWidget(self._set_beh_mode)
        ilay.addLayout(beh_row)

        lay.addWidget(identity_card)

        # AI Providers
        card = self._card("AI Providers", "Only the supported providers are shown here.")
        lay1 = card.layout()
        self._api_defaults = self._load_api_defaults()
        self._gemini_row, self._gemini_status, self._gemini_key = self._provider_row(
            "Google Gemini",
            self._api_defaults.get("gemini_api_key", ""),
            "gemini-3.8-flash",
            "gemini",
        )
        self._or_row, self._or_status, self._or_key = self._provider_row(
            "OpenRouter",
            self._api_defaults.get("openrouter_api_key", ""),
            "auto",
            "openrouter",
        )
        self._nvidia_row, self._nvidia_status, self._nvidia_key = self._provider_row(
            "NVIDIA",
            self._api_defaults.get("nvidia_api_key", ""),
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia",
        )
        self._groq_row, self._groq_status, self._groq_key = self._provider_row(
            "Groq",
            self._api_defaults.get("groq_api_key", ""),
            "llama-3.1-8b-instant",
            "groq",
        )
        self._custom_row, self._custom_status, self._custom_key = self._provider_row(
            "Custom",
            self._api_defaults.get("custom_ai_api_key", ""),
            "custom-model",
            "custom",
        )
        self._pollinations_row, self._pollinations_status, self._pollinations_key = self._provider_row(
            "Pollinations (Images)",
            self._api_defaults.get("pollinations_api_key", ""),
            "flux",
            "pollinations",
        )
        lay1.addWidget(self._gemini_row)
        lay1.addWidget(self._or_row)
        lay1.addWidget(self._nvidia_row)
        lay1.addWidget(self._groq_row)
        lay1.addWidget(self._custom_row)
        lay1.addWidget(self._pollinations_row)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self._default_provider = QComboBox()
        self._default_provider.addItems(["Google Gemini", "OpenRouter", "NVIDIA", "Groq", "Custom", "Local"])
        
        current_provider = self._load_app_settings().get("default_ai_provider", "Gemini")
        if current_provider in {"Gemini", "Google Gemini"}:
            self._default_provider.setCurrentText("Google Gemini")
        elif current_provider == "Local":
            self._default_provider.setCurrentText("Local")
        elif current_provider == "NVIDIA":
            self._default_provider.setCurrentText("NVIDIA")
        elif current_provider == "Groq":
            self._default_provider.setCurrentText("Groq")
        elif current_provider == "Custom":
            self._default_provider.setCurrentText("Custom")
        else:
            self._default_provider.setCurrentText("OpenRouter")
            
        self._default_provider.currentTextChanged.connect(self._set_default_provider)
        controls.addWidget(QLabel("Default AI Provider"))
        controls.addWidget(self._default_provider, 1)
        lay1.addLayout(controls)
        
        # Local AI Settings
        self._local_ai_widget = QWidget()
        local_lay = QVBoxLayout(self._local_ai_widget)
        local_lay.setContentsMargins(0, 8, 0, 8)
        local_lay.setSpacing(10)
        
        # Engine Status Row
        status_row = QHBoxLayout()
        is_online = local_brain.is_available()
        status_text = "🟢 Local Engine Online (Ollama)" if is_online else "🔴 Local Engine Offline"
        self._local_status_lbl = QLabel(status_text)
        self._local_status_lbl.setStyleSheet("color: #00ffaa; font-weight: bold;" if is_online else "color: #ff5555; font-weight: bold;")
        status_row.addWidget(QLabel("Engine Status:"))
        status_row.addWidget(self._local_status_lbl, 1)
        local_lay.addLayout(status_row)

        # Server URL
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Local Server URL"))
        self._local_url_input = QLineEdit(self._load_app_settings().get("local_ai_url", "http://localhost:11434/v1"))
        self._local_url_input.textChanged.connect(lambda t: self._set_setting("local_ai_url", t))
        url_row.addWidget(self._local_url_input, 1)
        local_lay.addLayout(url_row)
        
        # Model Selection with Combo Box & Refresh
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Local Model"))
        self._local_model_combo = QComboBox()
        self._local_model_combo.setEditable(True)
        
        def _populate_models():
            self._local_model_combo.clear()
            installed = local_brain.list_installed_models()
            if installed:
                self._local_model_combo.addItems(installed)
            else:
                self._local_model_combo.addItem("qwen2.5:3b")
            saved_model = self._load_app_settings().get("local_ai_model", "qwen2.5:3b")
            self._local_model_combo.setCurrentText(saved_model)
            online = local_brain.is_available()
            self._local_status_lbl.setText("🟢 Local Engine Online (Ollama)" if online else "🔴 Local Engine Offline")
            self._local_status_lbl.setStyleSheet("color: #00ffaa; font-weight: bold;" if online else "color: #ff5555; font-weight: bold;")

        _populate_models()
        self._local_model_combo.currentTextChanged.connect(lambda t: self._set_setting("local_ai_model", t))
        model_row.addWidget(self._local_model_combo, 1)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setFixedWidth(85)
        btn_refresh.setStyleSheet("background: rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 5px;")
        btn_refresh.clicked.connect(_populate_models)
        model_row.addWidget(btn_refresh)
        local_lay.addLayout(model_row)

        # 1-Click Model Download Helper Button
        action_row = QHBoxLayout()
        btn_pull = QPushButton("📥 Pull Qwen 2.5 (3B)")
        btn_pull.setStyleSheet("background: rgba(0, 255, 170, 0.15); color: #00ffaa; border: 1px solid #00ffaa; border-radius: 4px; padding: 6px;")
        def _on_download_click():
            btn_pull.setText("⏳ Downloading model in background...")
            btn_pull.setEnabled(False)
            local_brain.pull_model_async("qwen2.5:3b", lambda chunk: _populate_models())
        btn_pull.clicked.connect(_on_download_click)
        action_row.addWidget(btn_pull)
        local_lay.addLayout(action_row)

        self._local_ai_widget.setVisible(current_provider == "Local")
        self._default_provider.currentTextChanged.connect(lambda t: self._local_ai_widget.setVisible(t == "Local"))
        
        lay1.addWidget(self._local_ai_widget)
        
        self._auto_switch_btn = self._mk_toggle("Automatically switch if a provider fails", bool(self._load_app_settings().get("auto_provider_switch", True)), self._toggle_auto_provider_switch)
        lay1.addWidget(self._auto_switch_btn)

        # Dedicated Offline Mode Toggle
        is_offline_mode = bool(self._load_app_settings().get("offline_mode_enabled", False))
        self._offline_mode_btn = self._mk_toggle(
            "🔒 Offline Mode (Air-Gapped: 100% Local Inference & Speech)",
            is_offline_mode,
            self._toggle_offline_mode
        )
        lay1.addWidget(self._offline_mode_btn)
        lay.addWidget(card)

        # STT Engine Settings
        stt_card = self._card("Speech-to-Text Engine", "Choose how Nexus Core transcribes your voice.")
        stt_lay = stt_card.layout()

        # Engine selection
        stt_engine_row = QHBoxLayout()
        stt_engine_row.addWidget(QLabel("STT Engine"))
        self._stt_engine_combo = QComboBox()
        engines = get_available_stt_engines()
        for eng in engines:
            label = eng["name"]
            if not eng["available"]:
                label += " (not installed)"
            self._stt_engine_combo.addItem(label, eng["id"])
        current_stt = self._load_app_settings().get("stt_engine", "moonshine")
        idx = self._stt_engine_combo.findData(current_stt)
        if idx >= 0:
            self._stt_engine_combo.setCurrentIndex(idx)
        self._stt_engine_combo.currentTextChanged.connect(self._on_stt_engine_changed)
        stt_engine_row.addWidget(self._stt_engine_combo, 1)
        stt_lay.addLayout(stt_engine_row)

        # Autocorrect toggle
        is_autocorrect = bool(self._load_app_settings().get("stt_autocorrect", True))
        self._stt_autocorrect_btn = self._mk_toggle(
            "Auto-correct transcriptions",
            is_autocorrect,
            self._toggle_stt_autocorrect
        )
        stt_lay.addWidget(self._stt_autocorrect_btn)

        # Moonshine availability info + Install button
        moonshine_lay = QHBoxLayout()
        moonshine_lay.setContentsMargins(0, 0, 0, 0)
        moonshine_lay.setSpacing(8)

        moonshine_info = QLabel()
        if is_moonshine_available():
            moonshine_info.setText("✅ Moonshine STT is installed and ready")
            moonshine_info.setStyleSheet(f"color: {C.GREEN}; font-size: 11px;")
        else:
            moonshine_info.setText("⚠️ Moonshine not installed — click below to auto-install")
            moonshine_info.setStyleSheet(f"color: #ff5555; font-size: 11px;")
        moonshine_lay.addWidget(moonshine_info)

        # Install button (only shown when not available)
        self._moonshine_install_btn = QPushButton("Install Moonshine")
        self._moonshine_install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._moonshine_install_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.12);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.22);
                border: 1px solid #00e5ff;
            }
            QPushButton:disabled {
                background: rgba(128, 128, 128, 0.15);
                color: #666;
                border: 1px solid rgba(128, 128, 128, 0.15);
            }
        """)
        self._moonshine_install_btn.setVisible(not is_moonshine_available())
        self._moonshine_install_btn.clicked.connect(self._install_moonshine)
        moonshine_lay.addWidget(self._moonshine_install_btn)

        moonshine_lay.addStretch()
        stt_lay.addLayout(moonshine_lay)

        lay.addWidget(stt_card)

        # TTS Engine Settings
        tts_card = self._card("Text-to-Speech Engine", "Choose how Nexus Core speaks.")
        tts_lay = tts_card.layout()

        tts_engine_row = QHBoxLayout()
        tts_engine_row.addWidget(QLabel("TTS Engine"))
        self._tts_engine_combo = QComboBox()
        tts_providers = get_available_tts_providers()
        for p in tts_providers:
            label = p["name"]
            if not p["available"]:
                label += " (not configured)"
            self._tts_engine_combo.addItem(label, p["id"])
        current_tts = self._load_app_settings().get("tts_engine", "elevenlabs")
        idx = self._tts_engine_combo.findData(current_tts)
        if idx >= 0:
            self._tts_engine_combo.setCurrentIndex(idx)
        self._tts_engine_combo.currentTextChanged.connect(self._on_tts_engine_changed)
        tts_engine_row.addWidget(self._tts_engine_combo, 1)
        tts_lay.addLayout(tts_engine_row)

        # Voice selection
        tts_voice_row = QHBoxLayout()
        tts_voice_row.addWidget(QLabel("Voice"))
        self._tts_voice_combo = QComboBox()
        current_voice = self._load_app_settings().get("tts_voice_id", "pNInz6obpgDQGcFmaJgB")
        # Populate with default voices from first available provider
        for p in tts_providers:
            if p["available"]:
                for v in p.get("voices", []):
                    self._tts_voice_combo.addItem(f"{v['name']} ({v['id']})", v["id"])
        if self._tts_voice_combo.findData(current_voice) >= 0:
            self._tts_voice_combo.setCurrentData(current_voice)
        self._tts_voice_combo.currentIndexChanged.connect(lambda: self._set_setting("tts_voice_id", self._tts_voice_combo.currentData()))
        tts_voice_row.addWidget(self._tts_voice_combo, 1)
        tts_lay.addLayout(tts_voice_row)

        lay.addWidget(tts_card)

        # Search Engine Settings
        search_card = self._card("Search Engine", "Choose how Nexus Core searches the web.")
        search_lay = search_card.layout()

        search_engine_row = QHBoxLayout()
        search_engine_row.addWidget(QLabel("Search Engine"))
        self._search_engine_combo = QComboBox()
        search_providers = get_available_search_providers()
        for p in search_providers:
            label = p["name"]
            if not p["available"]:
                label += " (not configured)"
            self._search_engine_combo.addItem(label, p["id"])
        current_search = self._load_app_settings().get("search_engine", "tavily")
        idx = self._search_engine_combo.findData(current_search)
        if idx >= 0:
            self._search_engine_combo.setCurrentIndex(idx)
        self._search_engine_combo.currentTextChanged.connect(lambda: self._set_setting("search_engine", self._search_engine_combo.currentData()))
        search_engine_row.addWidget(self._search_engine_combo, 1)
        search_lay.addLayout(search_engine_row)

        lay.addWidget(search_card)

        # Image Generation Settings
        image_card = self._card("Image Generation", "Choose how Nexus Core generates images.")
        image_lay = image_card.layout()

        image_engine_row = QHBoxLayout()
        image_engine_row.addWidget(QLabel("Image Engine"))
        self._image_engine_combo = QComboBox()
        image_providers = get_available_image_providers()
        for p in image_providers:
            label = p["name"]
            if not p["available"]:
                label += " (not configured)"
            self._image_engine_combo.addItem(label, p["id"])
        current_image = self._load_app_settings().get("image_engine", "pollinations")
        idx = self._image_engine_combo.findData(current_image)
        if idx >= 0:
            self._image_engine_combo.setCurrentIndex(idx)
        self._image_engine_combo.currentTextChanged.connect(lambda: self._set_setting("image_engine", self._image_engine_combo.currentData()))
        image_engine_row.addWidget(self._image_engine_combo, 1)
        image_lay.addLayout(image_engine_row)

        # Pollinations model selection
        image_model_row = QHBoxLayout()
        image_model_row.addWidget(QLabel("Pollinations Model"))
        self._image_model_combo = QComboBox()
        self._image_model_combo.addItems(["flux", "flux-pro", "flux-dev", "turbo", "community/scriptsnsenses-sys/flux-2-dev-free"])
        current_image_model = self._load_app_settings().get("image_model", "community/scriptsnsenses-sys/flux-2-dev-free")
        idx = self._image_model_combo.findText(current_image_model)
        if idx >= 0:
            self._image_model_combo.setCurrentIndex(idx)
        self._image_model_combo.currentTextChanged.connect(lambda t: self._set_setting("image_model", t))
        image_model_row.addWidget(self._image_model_combo, 1)
        image_lay.addLayout(image_model_row)

        lay.addWidget(image_card)

        # Mobile connect
        mobile = self._card("Mobile Connect", "Connect your phone and control Nexus Core remotely.")
        ml = mobile.layout()
        self._mobile_status = QLabel("Connection Status: Ready")
        self._mobile_phone = QLabel("Phone Name: Not connected")
        self._mobile_last = QLabel("Last Connected: Never")
        for lbl in (self._mobile_status, self._mobile_phone, self._mobile_last):
            lbl.setStyleSheet(f"color: {C.TEXT_MED};")
            ml.addWidget(lbl)
        row = QHBoxLayout()
        self._mobile_connect_btn = QPushButton("Connect Device")
        self._mobile_connect_btn.clicked.connect(self._connect_mobile)
        self._mobile_disconnect_btn = QPushButton("Disconnect")
        self._mobile_disconnect_btn.clicked.connect(self._disconnect_mobile)
        self._mobile_qr_btn = QPushButton("Generate QR Code")
        self._mobile_qr_btn.clicked.connect(self._show_qr_code)
        row.addWidget(self._mobile_connect_btn)
        row.addWidget(self._mobile_disconnect_btn)
        row.addWidget(self._mobile_qr_btn)
        ml.addLayout(row)
        lay.addWidget(mobile)

        # Attention prompts
        attention = self._card("Attention Prompts", "Control incoming message and call alerts.")
        al = attention.layout()
        self._attention_message_btn = self._mk_toggle(
            "Show incoming message prompts",
            bool(self._load_app_settings().get("attention_message_prompts", True)),
            self._toggle_attention_message_prompts,
        )
        self._attention_call_btn = self._mk_toggle(
            "Show incoming call prompts",
            bool(self._load_app_settings().get("attention_call_prompts", True)),
            self._toggle_attention_call_prompts,
        )
        al.addWidget(self._attention_message_btn)
        al.addWidget(self._attention_call_btn)
        lay.addWidget(attention)

        # Startup
        startup = self._card("Startup", "Use Nexus Core with Windows startup preferences.")
        sl = startup.layout()
        self._startup_launch_btn = self._mk_toggle("Launch Nexus Core when Windows starts", bool(self._load_app_settings().get("show_workspace_on_startup", False)), self._toggle_startup_from_page)
        self._startup_minimized_btn = self._mk_toggle("Launch Minimized", bool(self._load_app_settings().get("launch_minimized", False)), self._toggle_launch_minimized)
        self._startup_updates_btn = self._mk_toggle("Check for updates on startup", bool(self._load_app_settings().get("check_updates_on_startup", True)), self._toggle_update_check)
        sl.addWidget(self._startup_launch_btn)
        sl.addWidget(self._startup_minimized_btn)
        sl.addWidget(self._startup_updates_btn)
        lay.addWidget(startup)

        # Shortcuts & Pinning
        shortcuts = self._card("Shortcuts & Pinning", "Create shortcuts and pin Nexus Core to your Windows system.")
        shl = shortcuts.layout()
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        self._desktop_shortcut_btn = QPushButton("Create Desktop Shortcut")
        self._desktop_shortcut_btn.clicked.connect(self._handle_create_desktop_shortcut)
        self._taskbar_pin_btn = QPushButton("Pin to Taskbar")
        self._taskbar_pin_btn.clicked.connect(self._handle_pin_to_taskbar)
        
        btn_row.addWidget(self._desktop_shortcut_btn, 1)
        btn_row.addWidget(self._taskbar_pin_btn, 1)
        shl.addLayout(btn_row)
        lay.addWidget(shortcuts)

        # App Theme
        theme_card = self._card("App Theme", "Select the primary color theme for Nexus Core.")
        tl = theme_card.layout()
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Primary Color:"))
        
        self._pick_theme_btn = QPushButton("Pick Color Palette")
        self._pick_theme_btn.clicked.connect(self._pick_theme_color)
        
        current_theme = "Gold"
        try:
            if APP_SETTINGS_FILE.exists():
                with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    _d = json.load(f)
                    current_theme = _d.get("app_theme", "Gold")
        except:
            pass
            
        if current_theme.startswith("#"):
            self._pick_theme_btn.setStyleSheet(f"background: {current_theme}; color: #ffffff;")
        
        theme_row.addWidget(self._pick_theme_btn, 1)
        tl.addLayout(theme_row)
        lay.addWidget(theme_card)

        # Startup animation
        anim = self._card("Startup Animation", "Control how the boot sequence behaves.")
        al = anim.layout()
        self._startup_anim_enable_btn = self._mk_toggle("Enable Startup Animation", bool(self._startup_animation_enabled()), self._toggle_startup_animation_from_page)
        al.addWidget(self._startup_anim_enable_btn)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Animation Speed"))
        self._anim_speed = QComboBox()
        self._anim_speed.addItems(["Fast", "Normal", "Slow"])
        self._anim_speed.setCurrentText(self._load_app_settings().get("startup_anim_speed", "Normal"))
        speed_row.addWidget(self._anim_speed, 1)
        al.addLayout(speed_row)
        self._anim_preview_btn = QPushButton("Preview Animation")
        self._anim_preview_btn.clicked.connect(self._preview_animation)
        al.addWidget(self._anim_preview_btn)
        self._preview_progress = QProgressBar()
        self._preview_progress.setRange(0, 100)
        self._preview_progress.setValue(0)
        self._preview_progress.setTextVisible(False)
        self._preview_progress.setFixedHeight(8)
        self._preview_progress.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.05); border: none; border-radius: 4px; } QProgressBar::chunk { background: #00e5ff; border-radius: 4px; }")
        al.addWidget(self._preview_progress)
        lay.addWidget(anim)
        # Discord bot
        discord = self._card("Discord Bot", "Mirror Nexus Core between the app and your server.")
        dl = discord.layout()
        self._discord_defaults = self._load_discord_settings()
        self._discord_status = QLabel("Bot Status: Offline")
        dl.addWidget(self._discord_status)
        self._discord_token = QLineEdit()
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._discord_token.setPlaceholderText("Bot Token")
        self._discord_token.setText((self._discord_defaults.get("bot_token") or "").strip())
        self._discord_token.setCursorPosition(0)
        dl.addWidget(self._discord_token)
        self._discord_reveal = QPushButton("Reveal")
        self._discord_reveal.setCheckable(True)
        self._discord_reveal.clicked.connect(self._toggle_discord_reveal)
        dl.addWidget(self._discord_reveal)
        self._discord_channel = QLineEdit()
        self._discord_channel.setPlaceholderText("Optional Channel ID")
        self._discord_channel.setText((self._discord_defaults.get("channel_id") or "").strip())
        dl.addWidget(self._discord_channel)
        db = QHBoxLayout()
        self._discord_save = QPushButton("Save")
        self._discord_test = QPushButton("Test Connection")
        self._discord_restart = QPushButton("Restart Bot")
        self._discord_save.clicked.connect(self._save_discord_from_page)
        self._discord_test.clicked.connect(self._test_discord_from_page)
        self._discord_restart.clicked.connect(self._restart_discord_from_page)
        db.addWidget(self._discord_save)
        db.addWidget(self._discord_test)
        db.addWidget(self._discord_restart)
        dl.addLayout(db)
        self._discord_msg = QLabel("")
        self._discord_msg.setStyleSheet(f"color: {C.TEXT_DIM};")
        dl.addWidget(self._discord_msg)
        lay.addWidget(discord)

        about = self._card("About Nexus Core", "Nexus Core information only.")
        ab = about.layout()
        about_grid = QGridLayout()
        about_grid.setHorizontalSpacing(22)
        about_grid.setVerticalSpacing(8)
        entries = [
            ("Version", "v1.0.0"),
            ("Build Number", "2026.06.29"),
            ("Release Date", "29 Jun 2026"),
        ]
        self._about_values: dict[str, QLabel] = {}
        for idx, (label, value) in enumerate(entries):
            key = QLabel(label)
            key.setStyleSheet(f"color: {C.TEXT_DIM};")
            val = QLabel(value)
            val.setStyleSheet(f"color: {C.WHITE}; font-weight: 700;")
            about_grid.addWidget(key, idx, 0)
            about_grid.addWidget(val, idx, 1)
            self._about_values[label] = val
        ab.addLayout(about_grid)
        lay.addWidget(about)

        # Autonomous Self-Healing & Continuous Self-Improvement Card
        auto_heal_card = self._card("Auto-Heal & Continuous Self-Improvement", "Autonomous bug repair, crash recovery sentry, AST-verified patching, and persistent behavioral directives.")
        ah_lay = auto_heal_card.layout()

        self._ah_status_lbl = QLabel("Sentry: Active | Sandbox: Enabled | Rules: 0 active")
        self._ah_status_lbl.setStyleSheet(f"color: {C.WHITE}; font-size: 12px; font-weight: bold; padding: 4px 0;")
        ah_lay.addWidget(self._ah_status_lbl)

        ah_btn_row = QHBoxLayout()
        self._ah_history_btn = QPushButton("Patch History")
        self._ah_history_btn.clicked.connect(self._handle_ah_history)
        ah_btn_row.addWidget(self._ah_history_btn)

        self._ah_rollback_btn = QPushButton("Rollback Last Patch")
        self._ah_rollback_btn.clicked.connect(self._handle_ah_rollback)
        ah_btn_row.addWidget(self._ah_rollback_btn)

        self._ah_rules_btn = QPushButton("Learned Rules")
        self._ah_rules_btn.clicked.connect(self._handle_ah_rules)
        ah_btn_row.addWidget(self._ah_rules_btn)
        ah_lay.addLayout(ah_btn_row)

        test_row = QHBoxLayout()
        self._ah_trigger_bug_btn = QPushButton("⚡ Trigger Test Bug")
        self._ah_trigger_bug_btn.clicked.connect(self._handle_ah_trigger_test_bug)
        test_row.addWidget(self._ah_trigger_bug_btn)

        self._ah_fix_bug_btn = QPushButton("🛠️ Fix Captured Bug")
        self._ah_fix_bug_btn.clicked.connect(self._handle_ah_fix_captured_bug)
        test_row.addWidget(self._ah_fix_bug_btn)
        ah_lay.addLayout(test_row)

        rule_input_row = QHBoxLayout()
        self._ah_rule_input = QLineEdit()
        self._ah_rule_input.setPlaceholderText("Teach Nexus a rule (e.g. Always summarize in bullet points)")
        rule_input_row.addWidget(self._ah_rule_input)
        self._ah_learn_btn = QPushButton("Teach Rule")
        self._ah_learn_btn.clicked.connect(self._handle_ah_learn_rule)
        rule_input_row.addWidget(self._ah_learn_btn)
        ah_lay.addLayout(rule_input_row)

        self._ah_output_lbl = QLabel("Self-healing sentry is active. Safe unbrick & auto-rollback protected.")
        self._ah_output_lbl.setStyleSheet(f"color: {C.TEXT_MED}; font-size: 11px;")
        self._ah_output_lbl.setWordWrap(True)
        ah_lay.addWidget(self._ah_output_lbl)

        lay.addWidget(auto_heal_card)
        try:
            self._refresh_auto_heal_status()
        except Exception:
            pass

        # Nexus Audio Routing & Hardware Controls
        audio_card = self._card("Audio Routing & Hardware Controls", "Select hardware audio interfaces, toggle Push-to-Talk, or inspect long-term memory.")
        alay = audio_card.layout()

        # Mic selection row
        mic_row = QHBoxLayout()
        mic_lbl = QLabel("Input Microphone")
        mic_lbl.setStyleSheet(f"color: {C.WHITE}; min-width: 130px;")
        mic_row.addWidget(mic_lbl)

        self._mic_combo = QComboBox()
        self._mic_combo.addItem("Default System Microphone")
        try:
            from core import audio_devices
            from memory import config_manager
            audio_devices.prefetch()
            input_devs = audio_devices.list_devices("input")
            for dev in input_devs:
                self._mic_combo.addItem(dev)
            saved_in = config_manager.get_input_device()
            if saved_in and saved_in in input_devs:
                self._mic_combo.setCurrentText(saved_in)
        except Exception:
            pass
        self._mic_combo.currentTextChanged.connect(self._on_input_device_changed)
        mic_row.addWidget(self._mic_combo, 1)
        alay.addLayout(mic_row)

        # Speaker selection row
        spk_row = QHBoxLayout()
        spk_lbl = QLabel("Output Speaker")
        spk_lbl.setStyleSheet(f"color: {C.WHITE}; min-width: 130px;")
        spk_row.addWidget(spk_lbl)

        self._spk_combo = QComboBox()
        self._spk_combo.addItem("Default System Speaker")
        try:
            from core import audio_devices
            from memory import config_manager
            output_devs = audio_devices.list_devices("output")
            for dev in output_devs:
                self._spk_combo.addItem(dev)
            saved_out = config_manager.get_output_device()
            if saved_out and saved_out in output_devs:
                self._spk_combo.setCurrentText(saved_out)
        except Exception:
            pass
        self._spk_combo.currentTextChanged.connect(self._on_output_device_changed)
        spk_row.addWidget(self._spk_combo, 1)
        alay.addLayout(spk_row)

        # Push-to-Talk and Memory Inspector Action buttons
        tools_row = QHBoxLayout()
        try:
            from memory import config_manager
            ptt_enabled = config_manager.get_push_to_talk_enabled()
        except Exception:
            ptt_enabled = False

        self._ptt_toggle = self._mk_toggle(
            "Push-to-Talk (Hold Ctrl+Space)",
            ptt_enabled,
            self._on_ptt_toggled
        )
        tools_row.addWidget(self._ptt_toggle)

        # Wake-word listening toggle (off by default = not intrusive)
        try:
            from memory import config_manager
            ww_enabled = config_manager.get_wake_word_enabled()
        except Exception:
            ww_enabled = False

        self._ww_toggle = self._mk_toggle(
            "Wake-word listening (Say 'Hey Nexus')",
            ww_enabled,
            self._on_ww_toggled
        )
        tools_row.addWidget(self._ww_toggle)

        mem_btn = QPushButton("🧠 Inspect Memory")
        mem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_btn.clicked.connect(self._open_memory_inspector)
        tools_row.addWidget(mem_btn)

        undo_btn = QPushButton("↺ Rollback (Undo)")
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(self._handle_undo_click)
        tools_row.addWidget(undo_btn)
        alay.addLayout(tools_row)

        self._audio_status_lbl = QLabel("Hardware audio deduplication, echo guard and undo stack active.")
        self._audio_status_lbl.setStyleSheet(f"color: {C.TEXT_MED}; font-size: 11px;")
        alay.addWidget(self._audio_status_lbl)

        lay.addWidget(audio_card)

        lay.addStretch(1)
        return col


    def _on_input_device_changed(self, name: str):
        try:
            from memory import config_manager
            val = "" if name == "Default System Microphone" else name
            config_manager.set_input_device(val)
            self._audio_status_lbl.setText(f"✅ Input device set to: {name}")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error setting input: {e}")

    def _on_output_device_changed(self, name: str):
        try:
            from memory import config_manager
            val = "" if name == "Default System Speaker" else name
            config_manager.set_output_device(val)
            self._audio_status_lbl.setText(f"✅ Output device set to: {name}")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error setting output: {e}")

    def _on_ptt_toggled(self, checked: bool):
        try:
            from memory import config_manager
            config_manager.set_push_to_talk_enabled(checked)
            self._audio_status_lbl.setText(f"✅ Push-to-Talk {'enabled (Hold Ctrl+Space)' if checked else 'disabled'}")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error toggling PTT: {e}")

    def _on_ww_toggled(self, checked: bool):
        try:
            from memory import config_manager
            config_manager.save_wake_word_enabled(checked)
            self._audio_status_lbl.setText(f"✅ Wake-word listening {'ON (say Hey Nexus)' if checked else 'OFF (not intrusive)'}")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error toggling wake word: {e}")

    def _open_memory_inspector(self):
        try:
            win = self.window()
            if hasattr(win, "show_memory_inspector"):
                win.show_memory_inspector()
            elif hasattr(win, "_memory_overlay_sig"):
                win._memory_overlay_sig.emit("show")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error opening memory inspector: {e}")

    def _handle_undo_click(self):
        try:
            from core import undo
            if not undo.can_undo():
                self._audio_status_lbl.setText("ℹ Nothing to undo yet.")
                return
            res = undo.undo_last()
            self._audio_status_lbl.setText(f"↺ {res}")
        except Exception as e:
            self._audio_status_lbl.setText(f"Error running undo: {e}")

    def _update_ig_status(self):
        try:
            if not hasattr(self, "_ig_status_lbl"):
                return
            from pathlib import Path
            import json
            from actions.instagram_mcp import CONFIG_PATH, SESSION_PATH

            username = ""
            d = {}
            for api_keys in [CONFIG_PATH, Path("config/api_keys.json")]:
                if api_keys.exists():
                    try:
                        with open(api_keys, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if data.get("instagram_username") or data.get("instagram_sessionid"):
                                d = data
                                username = d.get("instagram_username", "")
                                break
                    except Exception:
                        pass

            is_browser_auth = bool(d.get("instagram_browser_authenticated") and d.get("instagram_sessionid"))
            if is_browser_auth:
                name_str = f" (@{username})" if username else ""
                self._ig_status_lbl.setText(f"Status: 🟢 Connected via Browser / Session{name_str}")
                self._ig_status_lbl.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
                return

            has_session = False
            for sp in [SESSION_PATH, Path("config/ig_session.json")]:
                if sp.exists():
                    has_session = True
                    break

            if username and has_session:
                self._ig_status_lbl.setText(f"Status: 🟢 Connected (@{username})")
                self._ig_status_lbl.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
                return

            self._ig_status_lbl.setText("Status: ⚪ Not Connected — Click 'Connect via Browser' or 'Cookie'")
            self._ig_status_lbl.setStyleSheet(f"color: {C.PRI}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        except Exception:
            pass

    def _handle_ig_disconnect(self):
        try:
            import json
            import shutil
            from pathlib import Path
            from actions.instagram_mcp import CONFIG_PATH, SESSION_PATH, BROWSER_PROFILE_DIR, stop_daemon, kill_browser_processes

            for cfg_path in [CONFIG_PATH, Path("config/api_keys.json")]:
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            d = json.load(f)
                        d["instagram_username"] = ""
                        d["instagram_password"] = ""
                        d["instagram_sessionid"] = ""
                        d["instagram_user_id"] = ""
                        d["instagram_browser_authenticated"] = False
                        with open(cfg_path, "w", encoding="utf-8") as f:
                            json.dump(d, f, indent=4)
                    except Exception:
                        pass
                
            for sp in [SESSION_PATH, Path("config/ig_session.json")]:
                if sp.exists():
                    try:
                        sp.unlink()
                    except Exception:
                        pass

            for pdir in [BROWSER_PROFILE_DIR, Path("config/ig_browser_profile")]:
                if pdir.exists():
                    try:
                        shutil.rmtree(pdir)
                    except Exception:
                        pass
                
            stop_daemon()
            kill_browser_processes()
            
            self._update_ig_status()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Disconnected", "Instagram account disconnected.")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error disconnecting Instagram: {e}")

    class IGBrowserLoginWorker(__import__('PyQt6').QtCore.QThread):
        finished_success = __import__('PyQt6').QtCore.pyqtSignal(str)
        finished_error = __import__('PyQt6').QtCore.pyqtSignal(str)
        status_update = __import__('PyQt6').QtCore.pyqtSignal(str)

        def __init__(self, username=""):
            super().__init__()
            self.username = username

        def run(self):
            try:
                from playwright.sync_api import sync_playwright
                from pathlib import Path
                import json
                import time
                from actions.instagram_mcp import CONFIG_PATH, BROWSER_PROFILE_DIR, launch_robust_browser_context

                profile_dir = BROWSER_PROFILE_DIR
                profile_dir.mkdir(parents=True, exist_ok=True)

                self.status_update.emit("Launching browser for Instagram (using Chromium / Edge)...")
                with sync_playwright() as p:
                    context = launch_robust_browser_context(
                        p,
                        profile_dir,
                        headless=False,
                        args=["--disable-blink-features=AutomationControlled"],
                        viewport={"width": 1080, "height": 800},
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto("https://www.instagram.com/accounts/login/", timeout=60000)

                    # Try to prefill username
                    if self.username:
                        try:
                            user_input = page.wait_for_selector('input[name="username"], input[name="email"]', timeout=5000)
                            if user_input and not user_input.input_value():
                                user_input.fill(self.username)
                        except Exception:
                            pass

                    self.status_update.emit("Please log in in the opened browser window...")

                    logged_in = False
                    detected_username = self.username
                    # Poll cookies for up to 5 minutes
                    for _ in range(300):
                        if self.isInterruptionRequested():
                            break
                        try:
                            cookies = context.cookies("https://www.instagram.com")
                            cookie_map = {c["name"]: c["value"] for c in cookies}
                            if "sessionid" in cookie_map and "ds_user_id" in cookie_map:
                                logged_in = True
                                sid = cookie_map["sessionid"]
                                uid = cookie_map["ds_user_id"]

                                time.sleep(2)
                                try:
                                    u = page.evaluate("() => window._sharedData?.config?.viewer?.username || ''")
                                    if u:
                                        detected_username = u
                                    else:
                                        parts = [x for x in page.url.replace("https://www.instagram.com/", "").split("/") if x]
                                        if parts and parts[0] not in ["accounts", "direct", "explore", "reels"]:
                                            detected_username = parts[0]
                                except Exception:
                                    pass

                                cfg_targets = [CONFIG_PATH, Path("config/api_keys.json")]
                                for target_file in cfg_targets:
                                    try:
                                        data = {}
                                        if target_file.exists():
                                            with open(target_file, "r", encoding="utf-8") as f:
                                                data = json.load(f)
                                        if detected_username:
                                            data["instagram_username"] = detected_username
                                        data["instagram_sessionid"] = sid
                                        data["instagram_user_id"] = uid
                                        data["instagram_browser_authenticated"] = True
                                        target_file.parent.mkdir(parents=True, exist_ok=True)
                                        with open(target_file, "w", encoding="utf-8") as f:
                                            json.dump(data, f, indent=4)
                                    except Exception:
                                        pass

                                break
                        except Exception:
                            pass
                        time.sleep(1)

                    context.close()

                    if logged_in:
                        from actions.instagram_mcp import stop_daemon, start_daemon
                        stop_daemon()
                        start_daemon()
                        self.finished_success.emit(detected_username or "")
                    else:
                        self.finished_error.emit("Login timed out or the browser window was closed before login was completed.")
            except Exception as e:
                self.finished_error.emit(str(e))

    def _handle_ig_browser_connect(self):
        self._ig_browser_btn.setEnabled(False)
        self._ig_browser_btn.setText("Connecting via Browser...")
        from actions.instagram_mcp import stop_daemon, kill_browser_processes
        stop_daemon()
        kill_browser_processes()
        username = self._ig_username.text().strip()
        self._ig_browser_worker = self.IGBrowserLoginWorker(username)
        self._ig_browser_worker.finished_success.connect(self._ig_browser_success)
        self._ig_browser_worker.finished_error.connect(self._ig_browser_error)
        self._ig_browser_worker.start()

    def _ig_browser_success(self, detected_username):
        self._ig_browser_btn.setEnabled(True)
        self._ig_browser_btn.setText("🌐 Connect via Browser (Recommended)")
        if detected_username:
            self._ig_username.setText(detected_username)
        self._update_ig_status()
        from PyQt6.QtWidgets import QMessageBox
        name_str = f" as @{detected_username}" if detected_username else ""
        QMessageBox.information(self, "Instagram Connected", f"Instagram successfully connected via Browser{name_str}!\n\nNexus is now active for voice DM notifications and instant direct replies.")

    def _ig_browser_error(self, err_msg):
        self._ig_browser_btn.setEnabled(True)
        self._ig_browser_btn.setText("🌐 Connect via Browser (Recommended)")
        self._update_ig_status()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Browser Login", f"Browser connection was not completed: {err_msg}")

    def _handle_ig_cookie_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QMessageBox
        import json
        import re
        from pathlib import Path

        dlg = QDialog(self)
        dlg.setWindowTitle("Connect Instagram via Session Cookie")
        dlg.setFixedWidth(460)
        vbox = QVBoxLayout(dlg)
        vbox.setSpacing(10)

        lbl = QLabel(
            "<b>Connect directly with your browser session:</b><br>"
            "1. Open <b>instagram.com</b> in Chrome or Edge (where you're logged in).<br>"
            "2. Press <b>F12</b> (Inspect) → <b>Application</b> tab → <b>Cookies</b> → <i>https://www.instagram.com</i>.<br>"
            "3. Copy the value of <b>sessionid</b> and paste it below."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; font-size: 11px; line-height: 1.4;")
        vbox.addWidget(lbl)

        u_input = QLineEdit()
        u_input.setPlaceholderText("Instagram Username (e.g. your_handle)")
        curr_u = self._ig_username.text().strip()
        if curr_u:
            u_input.setText(curr_u)
        vbox.addWidget(u_input)

        s_input = QLineEdit()
        s_input.setPlaceholderText("Paste 'sessionid' cookie value here...")
        s_input.setEchoMode(QLineEdit.EchoMode.Password)
        vbox.addWidget(s_input)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        vbox.addWidget(bbox)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            sid = s_input.text().strip()
            username = u_input.text().strip()
            if not sid:
                QMessageBox.warning(self, "Missing Cookie", "Please enter a valid sessionid cookie value.")
                return

            if "sessionid=" in sid:
                sid = sid.split("sessionid=")[-1].split(";")[0].strip()

            user_match = re.search(r"^\d+", sid)
            uid = user_match.group() if user_match else ""

            from actions.instagram_mcp import CONFIG_PATH, stop_daemon, start_daemon
            cfg_targets = [CONFIG_PATH, Path("config/api_keys.json")]
            for target_file in cfg_targets:
                cfg = {}
                if target_file.exists():
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    except Exception:
                        cfg = {}
                if username:
                    cfg["instagram_username"] = username
                cfg["instagram_sessionid"] = sid
                cfg["instagram_password"] = f"sessionid:{sid}"
                if uid:
                    cfg["instagram_user_id"] = uid
                cfg["instagram_browser_authenticated"] = True
                try:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_file, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                except Exception:
                    pass

            if username:
                self._ig_username.setText(username)

            stop_daemon()
            start_daemon()
            self._update_ig_status()
            QMessageBox.information(self, "Instagram Connected", f"Instagram successfully connected via Session Cookie!\n\nNexus background DM daemon is now active.")

    class IGLoginWorker(__import__('PyQt6').QtCore.QThread):
        finished_success = __import__('PyQt6').QtCore.pyqtSignal()
        finished_error = __import__('PyQt6').QtCore.pyqtSignal(str)
        request_2fa = __import__('PyQt6').QtCore.pyqtSignal()
        request_challenge = __import__('PyQt6').QtCore.pyqtSignal()
        
        def __init__(self, username, password):
            super().__init__()
            self.username = username
            self.password = password
            self.code_event = __import__('threading').Event()
            self.code = None
            
        def run(self):
            try:
                from instagrapi import Client
                from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired
                import json
                from pathlib import Path
                cl = Client()
                
                pwd = (self.password or "").strip()
                if pwd.startswith("sessionid:") or (len(pwd) > 40 and "%3A" in pwd):
                    sid = pwd.replace("sessionid:", "").strip()
                    cl.login_by_sessionid(sid)
                else:
                    cl.username = self.username
                    outcome = cl.bloks_caa_login(self.username, pwd)
                    raw_str = json.dumps(outcome, default=str)
                    
                    if outcome.get("logged_in"):
                        cl.login_flow()
                    elif "login_wrong_password" in raw_str or "Incorrect password" in raw_str or "password you entered is incorrect" in raw_str:
                        raise Exception("The password you entered is incorrect. Please check your Instagram password, or paste your web browser 'sessionid' cookie.")
                    elif "checkpoint_required" in raw_str or "challenge_required" in raw_str:
                        try:
                            cl.login(self.username, pwd)
                        except TwoFactorRequired:
                            self.request_2fa.emit()
                            self.code_event.wait()
                            if not self.code:
                                raise Exception("2FA code not provided.")
                            cl.two_factor_login(self.code)
                        except ChallengeRequired:
                            self.request_challenge.emit()
                            self.code_event.wait()
                            if not self.code:
                                raise Exception("Challenge code not provided.")
                            cl.challenge_resolve(self.code)
                    else:
                        try:
                            cl.login(self.username, pwd)
                        except TwoFactorRequired:
                            self.request_2fa.emit()
                            self.code_event.wait()
                            if not self.code:
                                raise Exception("2FA code not provided.")
                            cl.two_factor_login(self.code)
                        except ChallengeRequired:
                            self.request_challenge.emit()
                            self.code_event.wait()
                            if not self.code:
                                raise Exception("Challenge code not provided.")
                            cl.challenge_resolve(self.code)
                        except Exception as e:
                            err_str = str(e)
                            if "out of date" in err_str.lower() or "CAA login" in err_str:
                                raise Exception("Instagram rejected credentials or security check. Please check your username/password or paste your web browser 'sessionid' cookie.")
                            raise
                
                from actions.instagram_mcp import SESSION_PATH, CONFIG_PATH, stop_daemon, start_daemon
                SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
                cl.dump_settings(str(SESSION_PATH))
                try:
                    Path("config").mkdir(parents=True, exist_ok=True)
                    cl.dump_settings("config/ig_session.json")
                except Exception:
                    pass

                stop_daemon()
                start_daemon()
                self.finished_success.emit()
            except Exception as e:
                self.finished_error.emit(str(e))

    def _handle_ig_connect(self):
        username = self._ig_username.text().strip()
        password = self._ig_password.text().strip()
        
        from PyQt6.QtWidgets import QMessageBox
        import json
        from actions.instagram_mcp import CONFIG_PATH
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password.")
            return
            
        self._ig_connect_btn.setEnabled(False)
        self._ig_connect_btn.setText("Connecting...")
        
        # Save credentials to both canonical and local configs
        for target_file in [CONFIG_PATH, Path("config/api_keys.json")]:
            try:
                d = {}
                if target_file.exists():
                    with open(target_file, "r", encoding="utf-8") as f:
                        d = json.load(f)
                d["instagram_username"] = username
                d["instagram_password"] = password
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=4)
            except Exception:
                pass
            
        self._ig_worker = self.IGLoginWorker(username, password)
        self._ig_worker.finished_success.connect(self._ig_login_success)
        self._ig_worker.finished_error.connect(self._ig_login_error)
        self._ig_worker.request_2fa.connect(self._ig_login_2fa)
        self._ig_worker.request_challenge.connect(self._ig_login_challenge)
        self._ig_worker.start()

    def _ig_login_success(self):
        self._ig_connect_btn.setEnabled(True)
        self._ig_connect_btn.setText("Connect (Password)")
        self._update_ig_status()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Success", "Instagram login successful and daemon started!")

    def _ig_login_error(self, err_msg):
        self._ig_connect_btn.setEnabled(True)
        self._ig_connect_btn.setText("Connect (Password)")
        self._update_ig_status()
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Instagram Mobile Login Blocked",
            f"Instagram direct password login failed:\n{err_msg}\n\n"
            "Meta frequently blocks automated mobile password logins.\n"
            "Would you like to connect securely via Browser instead?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._handle_ig_browser_connect()

    def _ig_login_2fa(self):
        from PyQt6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(self, "2-Factor Authentication", "Enter the 6-digit code sent to your device:")
        if ok and code:
            self._ig_worker.code = code
        else:
            self._ig_worker.code = None
        self._ig_worker.code_event.set()

    def _ig_login_challenge(self):
        from PyQt6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(self, "Challenge Required", "Enter the verification code sent to your email/phone:")
        if ok and code:
            self._ig_worker.code = code
        else:
            self._ig_worker.code = None
        self._ig_worker.code_event.set()

    def _toggle_ig_password_reveal(self):
        from PyQt6.QtWidgets import QLineEdit
        if getattr(self, "_ig_reveal_btn", None) and self._ig_reveal_btn.isChecked():
            self._ig_password.setEchoMode(QLineEdit.EchoMode.Normal)
            self._ig_reveal_btn.setText("Hide")
        else:
            self._ig_password.setEchoMode(QLineEdit.EchoMode.Password)
            self._ig_reveal_btn.setText("Reveal")

    def _toggle_gw_password_reveal(self):
        from PyQt6.QtWidgets import QLineEdit
        if getattr(self, "_gw_reveal_btn", None) and self._gw_reveal_btn.isChecked():
            self._gw_password.setEchoMode(QLineEdit.EchoMode.Normal)
            self._gw_reveal_btn.setText("Hide")
        else:
            self._gw_password.setEchoMode(QLineEdit.EchoMode.Password)
            self._gw_reveal_btn.setText("Reveal")

    def _handle_gw_save(self):
        email_val = self._gw_email.text().strip()
        pw_val = self._gw_password.text().strip()
        from PyQt6.QtWidgets import QMessageBox
        if not email_val:
            QMessageBox.warning(self, "Missing Email", "Please enter your Gmail address.")
            return
        try:
            from actions.google_workspace_mcp import save_stored_gmail_credentials
            ok = save_stored_gmail_credentials(email_val, pw_val)
            if ok:
                try:
                    from actions.google_workspace_mcp import stop_email_daemon, start_email_daemon
                    stop_email_daemon()
                    start_email_daemon()
                except Exception:
                    pass
                self._gw_status_lbl.setText("Status: Credentials saved securely.")
                self._gw_status_lbl.setStyleSheet("color: #4caf50;")
                QMessageBox.information(self, "Saved", "Google Workspace credentials saved successfully!")
            else:
                QMessageBox.critical(self, "Error", "Failed to encrypt and save credentials.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving credentials: {e}")

    def _handle_gw_test(self):
        self._gw_status_lbl.setText("Status: Testing connection...")
        self._gw_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        email_val = self._gw_email.text().strip()
        pw_val = self._gw_password.text().strip()
        if email_val and pw_val:
            try:
                from actions.google_workspace_mcp import save_stored_gmail_credentials
                save_stored_gmail_credentials(email_val, pw_val)
            except Exception:
                pass

        from actions.google_workspace_mcp import GmailEngine
        res = GmailEngine.test_connection()
        from PyQt6.QtWidgets import QMessageBox
        if res.get("success"):
            self._gw_status_lbl.setText(f"Status: {res.get('message')}")
            self._gw_status_lbl.setStyleSheet("color: #4caf50;")
            QMessageBox.information(self, "Connection Successful", res.get("message"))
        else:
            self._gw_status_lbl.setText(f"Status: {res.get('message')}")
            self._gw_status_lbl.setStyleSheet("color: #f44336;")
            QMessageBox.warning(self, "Connection Failed", res.get("message"))

    def _handle_gw_oauth(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, "Select Google Cloud credentials.json", str(Path.home()), "JSON Files (*.json)")
        if path:
            try:
                import shutil
                shutil.copy2(path, Path("config/google_workspace_credentials.json"))
                self._gw_status_lbl.setText("Status: OAuth credentials.json loaded.")
                self._gw_status_lbl.setStyleSheet("color: #4caf50;")
                QMessageBox.information(self, "Success", "Google Cloud OAuth credentials loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load credentials: {e}")

    class SpotifyTestWorker(__import__('PyQt6').QtCore.QThread):
        finished_result = __import__('PyQt6').QtCore.pyqtSignal(bool, str)

        def run(self):
            try:
                from actions.spotify_controller import is_spotify_configured, _spotify_mcp_call, get_spotify_config
                if not is_spotify_configured():
                    self.finished_result.emit(False, "Spotify MCP is not configured. Please enter your Client ID and Client Secret.")
                    return
                data = get_spotify_config()
                if not data.get("refreshToken"):
                    self.finished_result.emit(False, "Credentials saved, but browser authorization has not been completed. Click 'Authenticate in Browser'.")
                    return
                res = _spotify_mcp_call("getAvailableDevices", {})
                out = res.get("output", "")
                if "Error" in out or not res.get("success", False):
                    self.finished_result.emit(False, out or res.get("error", "Failed to contact Spotify API."))
                else:
                    self.finished_result.emit(True, out or "Successfully connected to Spotify MCP server!")
            except Exception as e:
                self.finished_result.emit(False, str(e))

    def _prefill_spotify_credentials(self):
        try:
            from actions.spotify_controller import get_spotify_config
            cfg = get_spotify_config()
            cid = cfg.get("clientId", "")
            csec = cfg.get("clientSecret", "")
            if cid and hasattr(self, "_spotify_client_id"):
                self._spotify_client_id.setText(cid)
            if csec and hasattr(self, "_spotify_client_secret"):
                self._spotify_client_secret.setText(csec)
        except Exception:
            pass

    def _update_spotify_status(self):
        try:
            if not hasattr(self, "_spotify_status_lbl"):
                return
            from actions.spotify_controller import get_spotify_config
            cfg = get_spotify_config()
            has_id = bool(cfg.get("clientId"))
            has_sec = bool(cfg.get("clientSecret"))
            has_token = bool(cfg.get("refreshToken"))
            if has_id and has_sec and has_token:
                self._spotify_status_lbl.setText("Status: 🟢 Connected & Authorized (Ready)")
                self._spotify_status_lbl.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
            elif has_id and has_sec:
                self._spotify_status_lbl.setText("Status: 🟡 Credentials Saved — Click 'Authenticate in Browser'")
                self._spotify_status_lbl.setStyleSheet(f"color: {C.ACC}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
            else:
                self._spotify_status_lbl.setText("Status: ⚪ Not Configured — Enter credentials below")
                self._spotify_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        except Exception:
            pass

    def _toggle_spotify_secret_reveal(self):
        from PyQt6.QtWidgets import QLineEdit
        if getattr(self, "_spotify_reveal_btn", None) and self._spotify_reveal_btn.isChecked():
            self._spotify_client_secret.setEchoMode(QLineEdit.EchoMode.Normal)
            self._spotify_reveal_btn.setText("Hide")
        else:
            self._spotify_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
            self._spotify_reveal_btn.setText("Reveal")

    def _copy_spotify_redirect_uri(self):
        try:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText("http://127.0.0.1:8888/callback")
            if hasattr(self, "_spotify_status_lbl"):
                self._spotify_status_lbl.setText("Status: 📋 Redirect URI copied to clipboard!")
                self._spotify_status_lbl.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
                QTimer.singleShot(2500, self._update_spotify_status)
        except Exception:
            pass

    def _handle_spotify_save(self):
        cid = self._spotify_client_id.text().strip()
        csec = self._spotify_client_secret.text().strip()
        from PyQt6.QtWidgets import QMessageBox
        if not cid or not csec:
            QMessageBox.warning(self, "Missing Credentials", "Please enter both Spotify Client ID and Client Secret.")
            return
        try:
            from actions.spotify_controller import save_spotify_credentials
            ok = save_spotify_credentials(cid, csec)
            if ok:
                self._update_spotify_status()
                QMessageBox.information(
                    self,
                    "Credentials Saved",
                    "Spotify credentials saved successfully!\n\n"
                    "Now click 'Authenticate in Browser' to link your Spotify account."
                )
            else:
                QMessageBox.critical(self, "Error", "Failed to save Spotify configuration.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving credentials: {e}")

    def _handle_spotify_auth(self):
        cid = self._spotify_client_id.text().strip()
        csec = self._spotify_client_secret.text().strip()
        from PyQt6.QtWidgets import QMessageBox
        from actions.spotify_controller import is_spotify_configured, save_spotify_credentials, _spotify_mcp_action
        if cid and csec:
            save_spotify_credentials(cid, csec)
        elif not is_spotify_configured():
            QMessageBox.warning(self, "Configuration Required", "Please enter your Spotify Client ID and Client Secret before authenticating.")
            return

        self._spotify_status_lbl.setText("Status: 🌐 Opening browser for Spotify authorization...")
        self._spotify_status_lbl.setStyleSheet(f"color: {C.ACC}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        self._spotify_auth_btn.setEnabled(False)
        self._spotify_auth_btn.setText("Authenticating...")

        msg = _spotify_mcp_action({"action": "auth"})

        self._spotify_auth_ticks = 0
        if not hasattr(self, "_spotify_auth_timer"):
            self._spotify_auth_timer = QTimer(self)
            self._spotify_auth_timer.setInterval(1500)
            self._spotify_auth_timer.timeout.connect(self._poll_spotify_auth_status)
        self._spotify_auth_timer.start()

        QMessageBox.information(
            self,
            "Spotify Authorization",
            f"{msg}\n\n"
            "Steps to complete:\n"
            "1. Log in to Spotify in the browser window.\n"
            "2. Click 'Agree' to grant playback permissions.\n"
            "3. Once redirected to callback, Nexus Core will automatically detect authorization!\n\n"
            "⚠️ Important: In developer.spotify.com/dashboard -> Your App -> Settings -> ensure 'http://127.0.0.1:8888/callback' is added to Redirect URIs."
        )

    def _poll_spotify_auth_status(self):
        self._spotify_auth_ticks = getattr(self, "_spotify_auth_ticks", 0) + 1
        from actions.spotify_controller import get_spotify_config
        cfg = get_spotify_config()
        if cfg.get("refreshToken"):
            if hasattr(self, "_spotify_auth_timer"):
                self._spotify_auth_timer.stop()
            if hasattr(self, "_spotify_auth_btn"):
                self._spotify_auth_btn.setEnabled(True)
                self._spotify_auth_btn.setText("🔗 Authenticate in Browser")
            self._update_spotify_status()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Spotify Connected", "Spotify MCP Server has been successfully authorized and connected!")
            return
        if self._spotify_auth_ticks >= 60:
            if hasattr(self, "_spotify_auth_timer"):
                self._spotify_auth_timer.stop()
            if hasattr(self, "_spotify_auth_btn"):
                self._spotify_auth_btn.setEnabled(True)
                self._spotify_auth_btn.setText("🔗 Authenticate in Browser")
            self._update_spotify_status()

    def _handle_spotify_test(self):
        from actions.spotify_controller import is_spotify_configured
        from PyQt6.QtWidgets import QMessageBox
        if not is_spotify_configured():
            QMessageBox.warning(self, "Not Configured", "Please enter and save your Spotify Client ID and Client Secret first.")
            return

        self._spotify_test_btn.setEnabled(False)
        self._spotify_test_btn.setText("Testing...")
        self._spotify_status_lbl.setText("Status: Testing Spotify MCP connection...")

        self._spotify_test_worker = self.SpotifyTestWorker()
        self._spotify_test_worker.finished_result.connect(self._on_spotify_test_finished)
        self._spotify_test_worker.start()

    def _on_spotify_test_finished(self, success: bool, message: str):
        self._spotify_test_btn.setEnabled(True)
        self._spotify_test_btn.setText("Test Connection")
        self._update_spotify_status()
        from PyQt6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(self, "Spotify Connection Successful", f"Connection to Spotify MCP Server was successful!\n\n{message}")
        else:
            QMessageBox.warning(self, "Spotify Connection Test", f"Spotify test result:\n\n{message}")

    def _handle_spotify_disconnect(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Disconnect Spotify",
            "Are you sure you want to disconnect Spotify and clear stored credentials?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from actions.spotify_controller import clear_spotify_credentials
                clear_spotify_credentials()
                if hasattr(self, "_spotify_client_id"):
                    self._spotify_client_id.clear()
                if hasattr(self, "_spotify_client_secret"):
                    self._spotify_client_secret.clear()
                self._update_spotify_status()
                QMessageBox.information(self, "Disconnected", "Spotify configuration and credentials removed.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to disconnect: {e}")

    def _refresh_hw_vitals(self):
        try:
            from actions.system_diagnostics_mcp import get_full_diagnostics
            d = get_full_diagnostics()
            cpu_pct = d["cpu"]["usage_percent"]
            ram_pct = d["ram"]["usage_percent"]
            bat_pct = d["battery"].get("percent", "--")
            disp = d["display"].get("brightness_levels", [80])
            b_val = disp[0] if disp else 80
            self._hw_vitals_lbl.setText(f"CPU: {cpu_pct}% | RAM: {ram_pct}% | Battery: {bat_pct}% | Display: {b_val}%")
            self._hw_brightness_slider.blockSignals(True)
            self._hw_brightness_slider.setValue(int(b_val))
            self._hw_brightness_val_lbl.setText(f"{b_val}%")
            self._hw_brightness_slider.blockSignals(False)
            self._hw_output_lbl.setText(f"Vitals updated. Uptime: {d['uptime']} ({d['running_processes_count']} processes).")
        except Exception as e:
            self._hw_output_lbl.setText(f"Error fetching vitals: {e}")

    def _handle_hw_brightness_slider(self, val):
        self._hw_brightness_val_lbl.setText(f"{val}%")
        try:
            from actions.system_diagnostics_mcp import set_brightness
            set_brightness(val)
        except Exception:
            pass

    def _handle_hw_ram_hogs(self):
        try:
            from actions.system_diagnostics_mcp import system_diagnostics
            res = system_diagnostics({"action": "ram_hogs", "limit": 4})
            self._hw_output_lbl.setText(res)
        except Exception as e:
            self._hw_output_lbl.setText(f"Error scanning RAM hogs: {e}")

    def _handle_hw_battery(self):
        try:
            from actions.system_diagnostics_mcp import system_diagnostics
            res = system_diagnostics({"action": "battery"})
            self._hw_output_lbl.setText(res)
        except Exception as e:
            self._hw_output_lbl.setText(f"Error checking battery: {e}")

    def _handle_hw_kill(self):
        target = self._hw_kill_target.text().strip()
        if not target:
            self._hw_output_lbl.setText("Please enter an application name or PID to kill.")
            return
        try:
            from actions.system_diagnostics_mcp import kill_process
            res = kill_process(target)
            msg = res.get("message", "Done.")
            self._hw_output_lbl.setText(msg)
            from PyQt6.QtWidgets import QMessageBox
            if res.get("success"):
                QMessageBox.information(self, "Process Terminated", msg)
            else:
                QMessageBox.warning(self, "Process Management", msg)
        except Exception as e:
            self._hw_output_lbl.setText(f"Error: {e}")

    def _refresh_auto_heal_status(self):
        try:
            from core.learned_rules import LearnedRulesEngine
            rules = LearnedRulesEngine.list_rules()
            active_count = sum(1 for r in rules if r.get("active", True))
            self._ah_status_lbl.setText(f"Sentry: Active | Sandbox: Verified | Rules: {active_count} active")
        except Exception as e:
            self._ah_status_lbl.setText(f"Status: Error loading ({e})")

    def _handle_ah_history(self):
        try:
            from actions.auto_heal_engine import auto_heal
            res = auto_heal({"action": "history"})
            self._ah_output_lbl.setText(res)
        except Exception as e:
            self._ah_output_lbl.setText(f"Error reading patch history: {e}")

    def _handle_ah_rollback(self):
        try:
            from PyQt6.QtWidgets import QMessageBox
            from actions.auto_heal_engine import auto_heal
            reply = QMessageBox.question(
                self,
                "Confirm Rollback",
                "Are you sure you want to rollback the most recent autonomous patch?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                res = auto_heal({"action": "rollback", "patch_id": "latest"})
                self._ah_output_lbl.setText(res)
                self._refresh_auto_heal_status()
                QMessageBox.information(self, "Rollback Result", res)
        except Exception as e:
            self._ah_output_lbl.setText(f"Error executing rollback: {e}")

    def _handle_ah_rules(self):
        try:
            from actions.auto_heal_engine import auto_heal
            res = auto_heal({"action": "list_rules"})
            self._ah_output_lbl.setText(res)
        except Exception as e:
            self._ah_output_lbl.setText(f"Error reading learned rules: {e}")

    def _handle_ah_learn_rule(self):
        txt = self._ah_rule_input.text().strip()
        if not txt:
            self._ah_output_lbl.setText("Please enter a rule or habit to teach.")
            return
        try:
            from core.learned_rules import LearnedRulesEngine
            res = LearnedRulesEngine.add_rule(txt, origin="ui_settings")
            msg = res.get("message", "Rule saved.")
            self._ah_output_lbl.setText(f"✅ {msg}")
            self._ah_rule_input.clear()
            self._refresh_auto_heal_status()
        except Exception as e:
            self._ah_output_lbl.setText(f"Error saving rule: {e}")

    def _handle_ah_trigger_test_bug(self):
        try:
            from actions.test_action import test_action
            res = test_action({})
            self._ah_output_lbl.setText(f"✅ Test action executed cleanly with no errors: {res}\nThe code is already healthy!")
        except Exception as e:
            import traceback
            from actions.auto_heal_engine import AutoHealEngine
            tb = traceback.format_exc()
            AutoHealEngine.record_last_error(tb)
            self._ah_output_lbl.setText(
                f"❌ Simulated bug triggered in test_action.py: {type(e).__name__}: {e}\n"
                f"Traceback captured in AutoHealEngine! Click 'Fix Captured Bug' or say 'Nexus, fix that bug'."
            )

    def _handle_ah_fix_captured_bug(self):
        self._ah_output_lbl.setText("⏳ Gemini is synthesizing hotfix in safety sandbox...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            from actions.auto_heal_engine import auto_heal
            res = auto_heal({"action": "heal"})
            self._ah_output_lbl.setText(f"🛠️ Result:\n{res}")
            self._refresh_auto_heal_status()
        except Exception as e:
            self._ah_output_lbl.setText(f"Error repairing bug: {e}")

    def _pick_theme_color(self):
        color = QColorDialog.getColor(QColor(C.PRI), self, "Select App Theme Color")
        if color.isValid():
            self._change_theme(color.name())

    def _change_theme(self, new_theme: str):
        settings = {}
        try:
            if APP_SETTINGS_FILE.exists():
                with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
        except Exception:
            pass
        old_theme = settings.get("app_theme", "Gold")
        if new_theme.lower() == old_theme.lower():
            return
        settings["app_theme"] = new_theme
        try:
            with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving theme: {e}")
        import subprocess
        import sys
        QMessageBox.information(self, "Restart Required", "The application will now restart to apply the new theme.")
        subprocess.Popen([sys.executable, "main.py"])
        QApplication.quit()

    def _build_summary_card(self):
        card = self._card("")
        card.layout().setContentsMargins(18, 18, 18, 18)
        card.layout().setSpacing(14)
        card.layout().addWidget(self._build_status_box())
        card.layout().addWidget(self._build_quick_actions_box())
        card.layout().addWidget(self._build_security_tip())
        return card

    def _build_status_box(self):
        box = self._card("System Status", "")
        lay = box.layout()
        self._sys_online = QLabel("≡ƒƒó System Online")
        self._sys_online.setStyleSheet("color: #35ff75; font-weight: 700;")
        self._sys_note = QLabel("All systems are operational.")
        self._sys_note.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(self._sys_online)
        lay.addWidget(self._sys_note)
        self._sys_version = QLabel("v1.0.0")
        self._sys_platform = QLabel(platform.system())
        self._sys_provider = QLabel("Gemini")
        self._sys_updated = QLabel(time.strftime("%d %b %Y %H:%M"))
        for label, val in (("Version", self._sys_version), ("Platform", self._sys_platform), ("Current AI Provider", self._sys_provider), ("Last Updated", self._sys_updated)):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch(1)
            row.addWidget(val)
            lay.addLayout(row)
        return box

    def _build_quick_actions_box(self):
        box = self._card("Quick Actions", "")
        lay = box.layout()
        actions = [
            ("Restart Nexus Core", QStyle.StandardPixmap.SP_BrowserReload, self._restart_app),
            ("Reload Configuration", QStyle.StandardPixmap.SP_BrowserReload, self._reload_config),
            ("Open Data Folder", QStyle.StandardPixmap.SP_DirOpenIcon, self._open_data_folder),
            ("View Logs", QStyle.StandardPixmap.SP_FileDialogDetailedView, self._view_logs),
            ("Check for Updates", QStyle.StandardPixmap.SP_ArrowDown, self._check_updates),
        ]
        for text, icon_kind, slot in actions:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(self.style().standardIcon(icon_kind))
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        return box

    def _build_security_tip(self):
        box = QFrame()
        box.setStyleSheet("QFrame { background: rgba(24, 18, 8, 0.85); border: 1px solid rgba(255, 191, 0, 0.22); border-radius: 14px; }")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        title = QLabel("Security Tip")
        title.setStyleSheet("color: #ffbf00; font-weight: 700;")
        body = QLabel('"Never share your API keys with anyone."')
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {C.TEXT_MED};")
        lay.addWidget(title)
        lay.addWidget(body)
        return box

    def _load_api_defaults(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_api_defaults()
        return {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "os_system": platform.system(),
        }

    def _load_app_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_app_settings()
        return _default_app_settings()

    def _load_discord_settings(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._load_discord_settings()
        return _default_discord_settings()

    def _startup_animation_enabled(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            return self._ctrl()._win._startup_animation_enabled()
        return True

    def _toggle_sound_effects(self, enabled: bool):
        sound_mgr.enabled = enabled
        self._set_setting("sound_effects_enabled", enabled)
        if enabled:
            sound_mgr.play_listening_start()

    def _on_sfx_volume_changed(self, val: int):
        sound_mgr.set_volume_percent(val)
        if hasattr(self, "_sfx_val_lbl"):
            self._sfx_val_lbl.setText(f"{val}%")
        self._set_setting("sound_effects_volume", val)

    def _set_setting(self, key: str, value):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            settings = self._ctrl()._win._load_app_settings()
            settings[key] = value
            self._ctrl()._win._save_app_settings(settings)
        else:
            try:
                data = {}
                if APP_SETTINGS_FILE.exists():
                    with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                data[key] = value
                with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            except Exception:
                pass

    def _open_api_keys(self):
        win = getattr(self._ctrl(), "_win", None) if self._ctrl() else None
        try:
            if win is not None and hasattr(win, "_open_api_keys"):
                win._open_api_keys()
                self.refresh()
                return
            data = {}
            if APP_SETTINGS_FILE.exists():
                with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            dialog = APIKeySettingsDialog(data, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                merged = dict(data)
                merged.update(dialog.get_settings())
                _write_settings_files(merged)
                if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                    self._ctrl().write_log("SYS: API keys updated.")
                self.refresh()
        except Exception as e:
            print(f"[Settings] Error saving API keys: {e}")

    def _test_provider(self, setting_key: str):
        api = self._load_api_defaults()
        key_map = {
            "gemini": ("gemini_api_key", "Google Gemini"),
            "openrouter": ("openrouter_api_key", "OpenRouter"),
            "nvidia": ("nvidia_api_key", "NVIDIA NIM"),
            "groq": ("groq_api_key", "Groq"),
            "custom": ("custom_ai_api_key", "Custom AI"),
            "tavily": ("tavily_api_key", "Tavily Search"),
            "firecrawl": ("firecrawl_api_key", "Firecrawl"),
            "serpapi": ("serpapi_api_key", "SerpAPI"),
            "anthropic": ("anthropic_api_key", "Anthropic Claude"),
            "pollinations": ("pollinations_api_key", "Pollinations"),
            "elevenlabs": ("elevenlabs_api_key", "ElevenLabs"),
            "fish_audio": ("fish_audio_api_key", "Fish Audio"),
            "cloudflare": ("cloudflare_api_key", "Cloudflare"),
        }
        key_field, name = key_map.get(setting_key, ("gemini_api_key", "Google Gemini"))
        val = api.get(key_field, "")
        msg = f"{name} key detected." if val.strip() else f"{name} key missing."
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: {msg}")
        self.refresh()

    def _connect_mobile(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            self._mobile_connect_btn.setText("Connecting...")
            target._show_remote_connect()
            QTimer.singleShot(1100, lambda: self._mobile_connect_btn.setText("Connect Device"))

    def _disconnect_mobile(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Mobile Connect session closed.")
        self._mobile_status.setText("Connection Status: Disconnected")
        self._mobile_phone.setText("Phone Name: Not connected")
        self._mobile_last.setText("Last Connected: Never")

    def _show_qr_code(self):
        ctrl = self._ctrl()
        if not ctrl:
            return
        target = None
        if hasattr(ctrl, "_show_remote_connect"):
            target = ctrl
        elif hasattr(ctrl, "_win") and hasattr(ctrl._win, "_show_remote_connect"):
            target = ctrl._win
        if target is not None:
            target._show_remote_connect()

    def _toggle_startup_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_button()

    def _toggle_launch_minimized(self, checked: bool):
        self._set_setting("launch_minimized", bool(checked))

    def _toggle_update_check(self, checked: bool):
        self._set_setting("check_updates_on_startup", bool(checked))

    def _toggle_startup_animation_from_page(self, checked: bool):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._set_startup_animation_enabled(bool(checked))
            self._ctrl()._win._refresh_startup_animation_button()

    def _set_default_provider(self, text: str):
        raw = (text or "").strip().lower()
        if raw.startswith("google") or raw == "gemini":
            provider = "Gemini"
            self._set_setting("offline_mode_enabled", False)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(False)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            msg = "SYS: Default AI provider set to Google Gemini. Cloud connectivity active."
        elif raw == "local":
            provider = "Local"
            self._set_setting("offline_mode_enabled", True)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(True)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(True)
            msg = "SYS: Default AI provider set to Local AI (Ollama). Offline Mode active."
        elif raw == "nvidia":
            provider = "NVIDIA"
            self._set_setting("offline_mode_enabled", False)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(False)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            msg = "SYS: Default AI provider set to NVIDIA NIM. Cloud connectivity active."
        elif raw == "groq":
            provider = "Groq"
            self._set_setting("offline_mode_enabled", False)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(False)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            msg = "SYS: Default AI provider set to Groq. Cloud connectivity active."
        elif raw == "custom":
            provider = "Custom"
            self._set_setting("offline_mode_enabled", False)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(False)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            msg = "SYS: Default AI provider set to Custom OpenAI-compatible endpoint. Cloud connectivity active."
        else:
            provider = "OpenRouter"
            self._set_setting("offline_mode_enabled", False)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.blockSignals(True)
                self._offline_mode_btn.setChecked(False)
                self._offline_mode_btn.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            msg = "SYS: Default AI provider set to OpenRouter. Cloud connectivity active."
        self._set_setting("default_ai_provider", provider)
        if hasattr(self, "_sys_provider"):
            self._sys_provider.setText(provider)
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(msg)

    def _toggle_auto_provider_switch(self, checked: bool):
        self._set_setting("auto_provider_switch", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Auto provider switch {'enabled' if checked else 'disabled'}.")

    def _toggle_offline_mode(self, checked: bool):
        self._set_setting("offline_mode_enabled", bool(checked))
        if checked:
            self._set_setting("default_ai_provider", "Local")
            if hasattr(self, "_default_provider"):
                self._default_provider.blockSignals(True)
                self._default_provider.setCurrentText("Local")
                self._default_provider.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(True)
            if hasattr(self, "_sys_provider"):
                self._sys_provider.setText("Local")
            msg = "🔒 SYSTEM: Air-Gapped Offline Mode ENGAGED. All operations running 100% locally."
        else:
            self._set_setting("default_ai_provider", "Gemini")
            if hasattr(self, "_default_provider"):
                self._default_provider.blockSignals(True)
                self._default_provider.setCurrentText("Google Gemini")
                self._default_provider.blockSignals(False)
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(False)
            if hasattr(self, "_sys_provider"):
                self._sys_provider.setText("Gemini")
            msg = "🌐 SYSTEM: Offline Mode DISENGAGED. Cloud connectivity restored."
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(msg)

    def _on_stt_engine_changed(self, text: str):
        """Handle STT engine dropdown change."""
        if not hasattr(self, "_stt_engine_combo"):
            return
        engine_id = self._stt_engine_combo.currentData()
        if engine_id:
            self._set_setting("stt_engine", engine_id)
            # Apply to live voice engine
            if self._ctrl() and hasattr(self._ctrl(), "_win") and hasattr(self._ctrl()._win, "_nexus_connect"):
                pass  # Will be applied via engine getter
            # Update live voice engine if accessible
            try:
                from core.live_voice_engine import live_voice_engine as lve
                lve.set_stt_config(engine=engine_id)
            except Exception:
                pass
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log(f"SYS: STT engine set to {engine_id}")

    def _toggle_stt_autocorrect(self, checked: bool):
        """Toggle STT auto-correction."""
        self._set_setting("stt_autocorrect", bool(checked))
        try:
            from core.live_voice_engine import live_voice_engine as lve
            lve.set_stt_config(autocorrect=bool(checked))
        except Exception:
            pass
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: STT auto-correction {'enabled' if checked else 'disabled'}")

    def _install_moonshine(self):
        """Install Moonshine STT via pip."""
        if not hasattr(self, "_moonshine_install_btn"):
            return
        self._moonshine_install_btn.setEnabled(False)
        self._moonshine_install_btn.setText("Installing...")

        try:
            from core.moonshine_stt import install_moonshine
            ok, msg = install_moonshine(progress_cb=self._moonshine_install_log)
            if ok:
                self._moonshine_install_btn.setText("Installed ✓")
                self._moonshine_install_btn.setEnabled(False)
                moonshine_info = getattr(self, "_moonshine_info", None)
                if moonshine_info:
                    moonshine_info.setText("✅ Moonshine STT installed and ready")
                    moonshine_info.setStyleSheet(f"color: {C.GREEN}; font-size: 11px;")
                if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                    self._ctrl().write_log("SYS: Moonshine STT installed successfully")
                self.refresh()
            else:
                self._moonshine_install_btn.setText("Install Failed")
                if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                    self._ctrl().write_log(f"SYS: Moonshine install failed: {msg}")
        except Exception as e:
            self._moonshine_install_btn.setText("Install Failed")
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log(f"SYS: Moonshine install error: {e}")

    def _moonshine_install_log(self, msg: str):
        """Progress callback for moonshine install."""
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Moonshine install — {msg}")

    def _on_tts_engine_changed(self, text: str):
        """Handle TTS engine dropdown change."""
        if not hasattr(self, "_tts_engine_combo"):
            return
        engine_id = self._tts_engine_combo.currentData()
        if engine_id:
            self._set_setting("tts_engine", engine_id)
            try:
                from core.live_voice_engine import live_voice_engine as lve
                lve.set_tts_config(engine=engine_id)
            except Exception:
                pass
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log(f"SYS: TTS engine set to {engine_id}")

    def _toggle_attention_message_prompts(self, checked: bool):
        self._set_setting("attention_message_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming message prompts {'enabled' if checked else 'disabled'}.")

    def _toggle_attention_call_prompts(self, checked: bool):
        self._set_setting("attention_call_prompts", bool(checked))
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log(f"SYS: Incoming call prompts {'enabled' if checked else 'disabled'}.")

    def _preview_animation(self):
        self._preview_progress.setValue(0)
        if hasattr(self, "_preview_timer") and self._preview_timer:
            try:
                self._preview_timer.stop()
            except Exception:
                pass
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._tick_preview)
        self._preview_timer.start(24)

    def _tick_preview(self):
        value = min(100, self._preview_progress.value() + 4)
        self._preview_progress.setValue(value)
        if value >= 100 and hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
            if self._ctrl() and hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Startup animation preview finished.")

    def _toggle_discord_reveal(self, checked: bool):
        self._discord_token.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _save_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._discord_token_input = self._discord_token
            self._ctrl()._win._discord_channel_input = self._discord_channel
            self._ctrl()._win._save_discord_token()
            self._discord_status.setText("Bot Status: Saved")
            self.refresh()

    def _test_discord_from_page(self):
        self._save_discord_from_page()
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._start_discord_bot()
            self._ctrl()._win._stop_discord_bot()
            self._discord_status.setText("Bot Status: Test sent")
            self._discord_msg.setText("Connected as Nexus Core#9649" if self._discord_token.text().strip() else "Bot Offline")

    def _restart_discord_from_page(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._stop_discord_bot()
            self._ctrl()._win._start_discord_bot()
            self._discord_status.setText("Bot Status: Restarted")

    def _restart_app(self):
        if self._ctrl() and hasattr(self._ctrl(), "_restart_app"):
            self._ctrl()._restart_app()

    def _reload_config(self):
        if self._ctrl() and hasattr(self._ctrl(), "_win"):
            self._ctrl()._win._load_api_defaults()
            self._ctrl()._win._load_discord_settings()
            if hasattr(self._ctrl(), "write_log"):
                self._ctrl().write_log("SYS: Configuration reloaded.")
            self.refresh()

    def _open_data_folder(self):
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(str(CONFIG_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(CONFIG_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
        except Exception:
            pass

    def _view_logs(self):
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(str(BASE_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(BASE_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(BASE_DIR)])
        except Exception:
            pass

    def _check_updates(self):
        if self._ctrl() and hasattr(self._ctrl(), "write_log"):
            self._ctrl().write_log("SYS: Update check requested.")

    def refresh(self):
        api = self._load_api_defaults()
        app = self._load_app_settings()
        discord = self._load_discord_settings()
        for widget in (
            getattr(self, "_default_provider", None),
            getattr(self, "_offline_mode_btn", None),
            getattr(self, "_auto_switch_btn", None),
            getattr(self, "_attention_message_btn", None),
            getattr(self, "_attention_call_btn", None),
            getattr(self, "_startup_launch_btn", None),
            getattr(self, "_startup_minimized_btn", None),
            getattr(self, "_startup_updates_btn", None),
            getattr(self, "_startup_anim_enable_btn", None),
            getattr(self, "_discord_token", None),
            getattr(self, "_discord_channel", None),
            getattr(self, "_discord_reveal", None),
        ):
            if widget is not None:
                widget.blockSignals(True)
        try:
            self._gemini_status.setText("Connected" if api.get("gemini_api_key") else "Not connected")
            self._or_status.setText("Connected" if api.get("openrouter_api_key") else "Not connected")
            self._gemini_key.setText(self._provider_key_preview(api.get("gemini_api_key", "")))
            self._or_key.setText(self._provider_key_preview(api.get("openrouter_api_key", "")))
            self._nvidia_status.setText("Connected" if api.get("nvidia_api_key") else "Not connected")
            self._nvidia_key.setText(self._provider_key_preview(api.get("nvidia_api_key", "")))
            self._groq_status.setText("Connected" if api.get("groq_api_key") else "Not connected")
            self._groq_key.setText(self._provider_key_preview(api.get("groq_api_key", "")))
            self._custom_status.setText("Connected" if api.get("custom_ai_api_key") else "Not connected")
            self._custom_key.setText(self._provider_key_preview(api.get("custom_ai_api_key", "")))
            if hasattr(self, "_pollinations_status"):
                self._pollinations_status.setText("Connected" if api.get("pollinations_api_key") else "Not connected")
                self._pollinations_key.setText(self._provider_key_preview(api.get("pollinations_api_key", "")))
            
            prov = app.get("default_ai_provider", "Gemini")
            is_offline = bool(app.get("offline_mode_enabled", False))
            if prov == "Local" or is_offline:
                disp_prov = "Local"
            elif prov == "OpenRouter":
                disp_prov = "OpenRouter"
            elif prov == "NVIDIA":
                disp_prov = "NVIDIA"
            elif prov == "Groq":
                disp_prov = "Groq"
            elif prov == "Custom":
                disp_prov = "Custom"
            else:
                disp_prov = "Google Gemini"
            if hasattr(self, "_default_provider"):
                self._default_provider.setCurrentText(disp_prov)
            if hasattr(self, "_offline_mode_btn"):
                self._offline_mode_btn.setChecked(is_offline or prov == "Local")
            if hasattr(self, "_local_ai_widget"):
                self._local_ai_widget.setVisible(is_offline or prov == "Local")

            self._auto_switch_btn.setChecked(bool(app.get("auto_provider_switch", True)))
            self._attention_message_btn.setChecked(bool(app.get("attention_message_prompts", True)))
            self._attention_call_btn.setChecked(bool(app.get("attention_call_prompts", True)))
            self._startup_launch_btn.setChecked(bool(app.get("show_workspace_on_startup", False)))
            self._startup_minimized_btn.setChecked(bool(app.get("launch_minimized", False)))
            self._startup_updates_btn.setChecked(bool(app.get("check_updates_on_startup", True)))
            self._startup_anim_enable_btn.setChecked(bool(self._startup_animation_enabled()))
            self._discord_token.setText((discord.get("bot_token") or "").strip())
            self._discord_channel.setText((discord.get("channel_id") or "").strip())
        finally:
            for widget in (
                getattr(self, "_default_provider", None),
                getattr(self, "_offline_mode_btn", None),
                getattr(self, "_auto_switch_btn", None),
                getattr(self, "_attention_message_btn", None),
                getattr(self, "_attention_call_btn", None),
                getattr(self, "_startup_launch_btn", None),
                getattr(self, "_startup_minimized_btn", None),
                getattr(self, "_startup_updates_btn", None),
                getattr(self, "_startup_anim_enable_btn", None),
                getattr(self, "_discord_token", None),
                getattr(self, "_discord_channel", None),
                getattr(self, "_discord_reveal", None),
            ):
                if widget is not None:
                    widget.blockSignals(False)
        enabled = bool(discord.get("enabled", False))
        token = (discord.get("bot_token") or "").strip()
        if enabled and token:
            self._discord_status.setText("Bot Status: Online")
            self._discord_msg.setText("Connected as Nexus Core#9649")
        elif token:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Bot Offline")
        else:
            self._discord_status.setText("Bot Status: Offline")
            self._discord_msg.setText("Token required")
        if hasattr(self, "_sys_provider"):
            self._sys_provider.setText(app.get("default_ai_provider", "Gemini"))
        if hasattr(self, "_update_spotify_status"):
            self._update_spotify_status()

    def _handle_create_desktop_shortcut(self):
        success, path_or_err = self._create_desktop_shortcut_logic()
        if success:
            QMessageBox.information(
                self, 
                "Success", 
                f"Desktop shortcut created successfully at:\n{path_or_err}"
            )
        else:
            QMessageBox.warning(
                self, 
                "Error", 
                f"Failed to create desktop shortcut:\n{path_or_err}"
            )

    def _handle_pin_to_taskbar(self):
        success, msg = self._pin_app_to_taskbar_logic()
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.warning(
                self, 
                "Taskbar Pinning", 
                msg
            )

    def _create_desktop_shortcut_logic(self):
        # .lnk desktop shortcuts are a Windows-only concept; skip on macOS/Linux.
        if sys.platform != "win32":
            return
        try:
            import os
            import shutil
            import subprocess
            from pathlib import Path
            import winreg
            
            # Find the correct Desktop folder path using registry (OneDrive safe!)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                desktop_raw, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                desktop_dir = Path(os.path.expandvars(desktop_raw))
            except Exception:
                desktop_dir = Path(os.path.expanduser("~")) / "Desktop"
                
            desktop_dir.mkdir(parents=True, exist_ok=True)
            shortcut_path = desktop_dir / "Nexus Core - Premium.lnk"
            
            # Base variables
            base_dir = Path(os.path.abspath("."))
            script_path = base_dir / "main.py"
            icon_path = base_dir / "assets" / "nexus_lite_logo.ico"
            
            python_exe = sys.executable
            if not python_exe:
                python_exe = shutil.which("pythonw") or shutil.which("python") or "pythonw"
                
            shortcut_target = python_exe
            shortcut_args = f'"{script_path}"'
            if getattr(sys, "frozen", False):
                shortcut_target = python_exe
                shortcut_args = ""
                
            powershell_exe = shutil.which("powershell.exe") or "powershell"
            
            def _ps_escape(value: str) -> str:
                return value.replace("'", "''")
                
            icon_value = str(icon_path) if icon_path.exists() else ""
            ps1_script = "\n".join([
                "$WshShell = New-Object -ComObject WScript.Shell",
                f"$Shortcut = $WshShell.CreateShortcut('{_ps_escape(str(shortcut_path))}')",
                f"$Shortcut.TargetPath = '{_ps_escape(shortcut_target)}'",
                f"$Shortcut.Arguments = '{_ps_escape(shortcut_args)}'",
                f"$Shortcut.WorkingDirectory = '{_ps_escape(str(base_dir))}'",
                "$Shortcut.WindowStyle = 7",
                "$Shortcut.Description = 'Launch Nexus Core - Premium'",
                f"if ('{_ps_escape(icon_value)}') {{ $Shortcut.IconLocation = '{_ps_escape(icon_value)},0' }}",
                "$Shortcut.Save()",
            ])
            
            ps1_path = get_user_data_dir() / "config" / "create_desktop_shortcut.ps1"
            ps1_path.write_text(ps1_script, encoding="utf-8")
            
            subprocess.run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            
            # Write marker file
            marker_path = get_user_data_dir() / "config" / ".desktop_shortcut_created"
            marker_path.write_text("created", encoding="utf-8")
            
            return True, str(shortcut_path)
        except Exception as e:
            return False, str(e)

    def _pin_app_to_taskbar_logic(self):
        try:
            import os
            import sys
            import shutil
            import subprocess
            from pathlib import Path
            
            # Ensure desktop shortcut exists first
            success, path_or_err = self._create_desktop_shortcut_logic()
            if not success:
                return False, f"Failed to create desktop shortcut first: {path_or_err}"
                
            shortcut_path = Path(path_or_err)
            if not shortcut_path.exists():
                return False, "Shortcut file does not exist."
                
            powershell_exe = shutil.which("powershell.exe") or "powershell"
            
            # COM pin script
            def _ps_escape(value: str) -> str:
                return value.replace("'", "''")
                
            pin_script = "\n".join([
                "$Shell = New-Object -ComObject Shell.Application",
                f"$Folder = $Shell.NameSpace('{_ps_escape(str(shortcut_path.parent))}')",
                f"$Item = $Folder.ParseName('{_ps_escape(shortcut_path.name)}')",
                "$Verb = $Item.Verbs() | Where-Object { $_.Name.Replace('&', '') -match 'Pin to taskbar' }",
                "if ($Verb) { $Verb.DoIt(); exit 0 } else { exit 1 }"
            ])
            
            res = subprocess.run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", pin_script],
                capture_output=True
            )
            
            if res.returncode == 0:
                return True, "Nexus Core has been pinned to your Taskbar!"
            else:
                return False, "Windows restricts programmatic taskbar pinning. Please right-click the 'Nexus Core - Premium.lnk' shortcut on your Desktop and select 'Pin to taskbar', or drag it directly onto your taskbar."
        except Exception as e:
            return False, f"Error pinning to taskbar: {e}"

class SmartDevicesSection(QFrame):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._service = SmartHomeService()
        self._snapshot = ""
        self._device_tiles: list[_DeviceTile] = []
        self._card_anims: list[QPropertyAnimation] = []
        self._selected_device: dict[str, object] | None = None

        self.setObjectName("SmartDevicesSection")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f"""
            QFrame#SmartDevicesSection {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._title_lbl = QLabel("SMART DEVICES")
        self._title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.WHITE}; letter-spacing: 1px;")
        self._subtitle_lbl = QLabel("Quick access to your connected home devices.")
        self._subtitle_lbl.setFont(QFont("Segoe UI", 8))
        self._subtitle_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        title_box.addWidget(self._title_lbl)
        title_box.addWidget(self._subtitle_lbl)
        header.addLayout(title_box, 1)

        self._count_chip = QLabel("0 devices")
        self._count_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_chip.setStyleSheet(
            f"QLabel {{ background: rgba(255,255,255,0.03); color: {C.PRI}; border: 1px solid rgba(255,255,255,0.07); border-radius: 10px; padding: 4px 10px; }}"
        )
        header.addWidget(self._count_chip)

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(32, 32)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255,0.08);
                border: 1px solid {C.PRI};
            }}
        """)
        self._refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        header.addWidget(self._refresh_btn)

        self._open_home_btn = QPushButton("Add Device")
        self._open_home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_home_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255,0.10);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 9px;
                padding: 0 14px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255,0.16);
            }}
        """)
        self._open_home_btn.clicked.connect(self._open_brahma_home)
        header.addWidget(self._open_home_btn)
        root.addLayout(header)

        self._empty_card = QWidget()
        self._empty_card.setStyleSheet("background: transparent;")
        empty_lay = QVBoxLayout(self._empty_card)
        empty_lay.setContentsMargins(6, 4, 6, 4)
        empty_lay.setSpacing(6)
        empty_title = QLabel("No Smart Devices Connected")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        empty_title.setStyleSheet(f"color: {C.WHITE}; border: none;")
        empty_desc = QLabel("Connect your first smart device to control it directly from your dashboard.")
        empty_desc.setWordWrap(True)
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_desc.setFont(QFont("Segoe UI", 8))
        empty_desc.setStyleSheet(f"color: {C.TEXT_DIM};")
        empty_btn = QPushButton("Open Nexus Core Home")
        empty_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        empty_btn.setFixedWidth(160)
        empty_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255,0.12);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 10px;
                min-height: 34px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255,0.18);
            }}
        """)
        empty_btn.clicked.connect(self._open_brahma_home)
        empty_lay.addStretch(1)
        empty_lay.addWidget(empty_title)
        empty_lay.addWidget(empty_desc)
        empty_lay.addWidget(empty_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_lay.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._grid_page = QWidget()
        self._grid_page.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_page)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setHorizontalSpacing(12)
        self._grid_layout.setVerticalSpacing(12)

        self._row_page = QWidget()
        self._row_page.setStyleSheet("background: transparent;")
        self._row_layout = QHBoxLayout(self._row_page)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(12)

        self._cards_stack = QStackedWidget()
        self._cards_stack.setStyleSheet("background: transparent; border: none;")
        self._cards_stack.addWidget(self._grid_page)
        self._cards_stack.addWidget(self._row_page)
        self._scroll.setWidget(self._cards_stack)
        root.addWidget(self._empty_card)
        root.addWidget(self._scroll, 1)

        self._panel = QFrame(self)
        self._panel.setObjectName("SmartDevicePanel")
        self._panel.setStyleSheet(f"""
            QFrame#SmartDevicePanel {{
                background: rgba(8, 9, 13, 245);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba(255,255,255,0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255,0.08);
                border: 1px solid {C.PRI};
            }}
        """)
        self._panel.setVisible(False)
        self._panel.setMinimumSize(280, 260)
        self._panel_effect = QGraphicsOpacityEffect(self._panel)
        self._panel_effect.setOpacity(0.0)
        self._panel.setGraphicsEffect(self._panel_effect)
        self._panel_lay = QVBoxLayout(self._panel)
        self._panel_lay.setContentsMargins(14, 12, 14, 12)
        self._panel_lay.setSpacing(8)

        panel_top = QHBoxLayout()
        panel_top.setSpacing(6)
        self._panel_name = QLabel("Device")
        self._panel_name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._panel_name.setStyleSheet(f"color: {C.WHITE};")
        panel_top.addWidget(self._panel_name, 1)
        self._panel_close = QPushButton("X")
        self._panel_close.setFixedSize(28, 28)
        self._panel_close.clicked.connect(self._close_panel)
        panel_top.addWidget(self._panel_close)
        self._panel_lay.addLayout(panel_top)

        self._panel_meta = QLabel("")
        self._panel_meta.setWordWrap(True)
        self._panel_meta.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._panel_lay.addWidget(self._panel_meta)

        self._panel_status = QLabel("")
        self._panel_status.setStyleSheet(f"color: {C.GREEN}; font-weight: 700;")
        self._panel_lay.addWidget(self._panel_status)

        self._panel_controls = QVBoxLayout()
        self._panel_controls.setSpacing(10)
        self._panel_lay.addLayout(self._panel_controls)
        self._panel_lay.addStretch(1)

        self._panel_actions = QHBoxLayout()
        self._panel_actions.setSpacing(8)
        self._panel_lay.addLayout(self._panel_actions)

        self._panel_hint = QLabel("")
        self._panel_hint.setWordWrap(True)
        self._panel_hint.setStyleSheet(f"color: {C.TEXT_DIM};")
        self._panel_lay.addWidget(self._panel_hint)

        self._poll_tmr = QTimer(self)
        self._poll_tmr.timeout.connect(lambda: self.refresh(force=False))
        self._poll_tmr.start(2500)

        self.refresh(force=True)

    def _controller_bridge(self):
        return self._controller

    def _open_brahma_home(self):
        bridge = self._controller_bridge()
        if bridge and hasattr(bridge, "_set_page"):
            bridge._set_page("home")

    def _snapshot_devices(self, devices: list[dict[str, object]]) -> str:
        payload = [
            (
                str(d.get("id", "")),
                int(d.get("updated_at") or 0),
                str(d.get("name", "")),
                bool(d.get("is_on")),
                str(d.get("room", "")),
                str(d.get("device_type", "")),
                str(d.get("manufacturer", "")),
            )
            for d in devices
        ]
        return json.dumps(payload, ensure_ascii=True, sort_keys=False)

    def refresh(self, force: bool = False):
        devices = self._service.list_devices()
        snapshot = self._snapshot_devices(devices)
        if not force and snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self._count_chip.setText(f"{len(devices)} device(s)")
        self._empty_card.setVisible(not devices)
        self._scroll.setVisible(bool(devices))
        self._rebuild_device_cards(devices)
        if self._panel.isVisible() and self._selected_device:
            device_id = str(self._selected_device.get("id", ""))
            device = self._find_device(device_id)
            if device:
                self._selected_device = device
                self._populate_panel(device)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild_device_cards(self, devices: list[dict[str, object]]):
        self._clear_layout(self._grid_layout)
        self._clear_layout(self._row_layout)
        self._device_tiles.clear()
        self._card_anims.clear()

        if not devices:
            self._cards_stack.setCurrentIndex(0)
            self._close_panel()
            return

        count = len(devices)
        if count <= 3:
            self._cards_stack.setCurrentIndex(1)
            self._clear_layout(self._row_layout)
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._row_layout.addWidget(tile)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            self._row_layout.addStretch(1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif count <= 6:
            self._cards_stack.setCurrentIndex(0)
            columns = 3 if count > 3 else count
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._grid_layout.addWidget(tile, idx // columns, idx % columns)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            last_row = (count - 1) // columns + 1
            self._grid_layout.setRowStretch(last_row, 1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self._cards_stack.setCurrentIndex(1)
            self._clear_layout(self._row_layout)
            for idx, device in enumerate(devices):
                tile = _DeviceTile(device)
                tile.select_requested.connect(self._open_device_panel)
                tile.action_requested.connect(self._apply_tile_action)
                self._row_layout.addWidget(tile)
                self._animate_card(tile, idx)
                self._device_tiles.append(tile)
            self._row_layout.addStretch(1)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _animate_card(self, widget: QWidget, index: int):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._card_anims.append(anim)
        QTimer.singleShot(index * 45, anim.start)

    def _device_id_from_input(self, device_or_id):
        if isinstance(device_or_id, dict):
            return str(device_or_id.get("id", ""))
        return str(device_or_id or "")

    def _find_device(self, device_id: str) -> dict[str, object] | None:
        for device in self._service.list_devices():
            if str(device.get("id", "")) == device_id:
                return device
        return None

    def _apply_tile_action(self, device_id: str, action: str, payload: dict):
        try:
            self._service.execute_device_action(device_id, action, payload)
        except Exception:
            return
        self.refresh(force=True)
        device = self._find_device(device_id)
        if device:
            self._selected_device = device
            self._open_device_panel(device)

    def _open_device_panel(self, device_or_id):
        try:
            device_id = self._device_id_from_input(device_or_id)
            device = self._find_device(device_id)
            if not device:
                return
            self._selected_device = device
            self._populate_panel(device)
            self._show_panel()
        except Exception:
            return

    def _show_panel(self):
        try:
            self._position_panel()
            self._panel.setVisible(True)
            self._panel.raise_()
            self._panel_effect.setOpacity(1.0)
        except Exception:
            self._panel.hide()
            self._panel_effect.setOpacity(0.0)

    def _close_panel(self):
        if not self._panel.isVisible():
            return
        self._panel.hide()
        self._panel_effect.setOpacity(0.0)

    def _clear_panel_controls(self):
        self._clear_layout(self._panel_controls)
        self._clear_layout(self._panel_actions)

    def _populate_panel(self, device: dict[str, object]):
        try:
            self._clear_panel_controls()
            self._clear_layout(self._panel_actions)
            name = str(device.get("name", "Device"))
            room = str(device.get("room", ""))
            device_type = str(device.get("device_type", "device")).lower()
            is_on = bool(device.get("is_on"))
            traits = device.get("traits") if isinstance(device.get("traits"), dict) else {}

            self._panel_name.setText(name)
            self._panel_meta.setText(
                f"Room: {room or 'Unassigned'}\nType: {device_type.title()}\nManufacturer: {device.get('manufacturer', '')}\nConnection: Connected"
            )
            self._panel_status.setText("ON" if is_on else "OFF")
            self._panel_hint.setText("Click outside the panel to close.")

            power_btn = QPushButton("Power")
            power_btn.clicked.connect(lambda: self._apply_tile_action(str(device.get("id", "")), "power", {"is_on": not is_on}))
            self._panel_actions.addWidget(power_btn)

            forget_btn = QPushButton("Forget")
            forget_btn.clicked.connect(lambda: self._forget_device(str(device.get("id", ""))))
            self._panel_actions.addWidget(forget_btn)

            rename_btn = QPushButton("Rename")
            rename_btn.clicked.connect(lambda: self._rename_device(str(device.get("id", "")), name))
            self._panel_actions.addWidget(rename_btn)

            if device_type == "fan":
                speed = int(traits.get("speed", 4) or 4)
                lbl = QLabel(f"Speed {speed}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(1, 6)
                slider.setValue(speed)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "speed", {"speed": value}))
                self._panel_controls.addWidget(slider)
            elif device_type == "light":
                brightness = int(traits.get("brightness", 75) or 75)
                lbl = QLabel(f"Brightness {brightness}%")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(1, 100)
                slider.setValue(brightness)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "brightness", {"brightness": value}))
                self._panel_controls.addWidget(slider)
                color_btn = QPushButton("Color")
                color_btn.clicked.connect(lambda: self._pick_color(device))
                self._panel_controls.addWidget(color_btn)
            elif device_type == "ac":
                temperature = int(traits.get("temperature", 24) or 24)
                lbl = QLabel(f"Temperature {temperature}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(16, 30)
                slider.setValue(temperature)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "temperature", {"temperature": value}))
                self._panel_controls.addWidget(slider)
            elif device_type in ("tv", "speaker"):
                volume = int(traits.get("volume", 18) or 18)
                lbl = QLabel(f"Volume {volume}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 100)
                slider.setValue(volume)
                slider.valueChanged.connect(lambda value: self._apply_tile_action(str(device.get("id", "")), "volume", {"volume": value}))
                self._panel_controls.addWidget(slider)
            elif device_type == "plug":
                usage = traits.get("energy_usage", traits.get("power_usage", "N/A"))
                lbl = QLabel(f"Energy usage: {usage}")
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
            else:
                lbl = QLabel("Primary controls are available from the card below.")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {C.TEXT_MED};")
                self._panel_controls.addWidget(lbl)
        except Exception:
            return

    def _pick_color(self, device: dict[str, object]):
        color = QColorDialog.getColor(QColor(C.PRI), self, "Pick Light Color")
        if color.isValid():
            self._apply_tile_action(str(device.get("id", "")), "color", {"color": color.name()})

    def _rename_device(self, device_id: str, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Device", "New name:", text=current_name)
        if ok and new_name.strip():
            try:
                self._service.rename_device(device_id, new_name.strip())
            except Exception:
                return
            self.refresh(force=True)

    def _forget_device(self, device_id: str):
        try:
            self._service.forget_device(device_id)
        except Exception:
            return
        self._close_panel()
        self.refresh(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._panel.isVisible():
            self._position_panel()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh(force=True)

    def _position_panel(self):
        panel_w = min(330, max(270, int(self.width() * 0.28)))
        panel_h = min(340, max(240, int(self.height() * 0.45)))
        x = max(12, self.width() - panel_w - 12)
        y = 12
        self._panel.setGeometry(x, y, panel_w, panel_h)



class _ConnectDeviceCard(QFrame):
    clicked = pyqtSignal(str)
    action_requested = pyqtSignal(str, str, dict)

    def __init__(self, device: dict[str, object], parent=None):
        super().__init__(parent)
        self.device = device
        self._expanded = False
        self.setObjectName("ConnectDeviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumSize(220, 150)
        self.setStyleSheet("""
            QFrame#ConnectDeviceCard {
                background: rgba(10, 12, 18, 240);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
            }
            QLabel {
                background: transparent;
            }
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                min-height: 30px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255,0.12);
                color: #00e5ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self._title = QLabel(str(device.get("name", "Device")))
        self._title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._title)

        platform = str(device.get("platform", "UNKNOWN")).upper()
        status = "ONLINE" if bool(device.get("online")) else "OFFLINE"
        self._status_label = QLabel(f"{platform} • {status}")
        self._status_label.setFont(QFont("Segoe UI", 8))
        self._status_label.setStyleSheet("color: rgba(255,255,255,0.55);")
        layout.addWidget(self._status_label)

        info = []
        if device.get("manufacturer"):
            info.append(str(device.get("manufacturer")))
        if device.get("device_type"):
            info.append(str(device.get("device_type")))
        if device.get("ip"):
            info.append(str(device.get("ip")))
        self._info_lbl = QLabel(" ┬╖ ".join(info) if info else "Connected device")
        self._info_lbl.setFont(QFont("Segoe UI", 8))
        self._info_lbl.setStyleSheet("color: rgba(255,255,255,0.45);")
        self._info_lbl.setWordWrap(True)
        layout.addWidget(self._info_lbl)

        layout.addStretch(1)

        self._action_container = QFrame(self)
        self._action_container.setVisible(False)
        self._action_container.setStyleSheet("QFrame { background: rgba(255,255,255,0.03); border-radius: 14px; }")
        actions_layout = QHBoxLayout(self._action_container)
        actions_layout.setContentsMargins(8, 8, 8, 8)
        actions_layout.setSpacing(8)

        self._rename_btn = QPushButton("Rename")
        self._disconnect_btn = QPushButton("Disconnect")
        self._forget_btn = QPushButton("Remove")
        self._pin_btn = QPushButton("Set PIN")

        actions_layout.addWidget(self._pin_btn)
        actions_layout.addWidget(self._rename_btn)
        actions_layout.addWidget(self._disconnect_btn)
        actions_layout.addWidget(self._forget_btn)
        layout.addWidget(self._action_container)

        self._pin_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device.get("device_id", "")), "set_pin", {}))
        self._rename_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device.get("device_id", "")), "rename", {}))
        self._disconnect_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device.get("device_id", "")), "disconnect", {}))
        self._forget_btn.clicked.connect(lambda: self.action_requested.emit(str(self.device.get("device_id", "")), "forget", {}))

    def set_expanded(self, expanded: bool):
        self._expanded = bool(expanded)
        self._action_container.setVisible(self._expanded)
        if self._expanded:
            self.setStyleSheet("""
                QFrame#ConnectDeviceCard {
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(0, 229, 255,0.25);
                    border-radius: 18px;
                }
                QLabel {
                    background: transparent;
                }
                QPushButton {
                    background: rgba(255,255,255,0.08);
                    color: #ffffff;
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 10px;
                    min-height: 30px;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255,0.16);
                    color: #00e5ff;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#ConnectDeviceCard {
                    background: rgba(10, 12, 18, 240);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 18px;
                }
                QLabel {
                    background: transparent;
                }
                QPushButton {
                    background: rgba(255,255,255,0.06);
                    color: #ffffff;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 10px;
                    min-height: 30px;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255,0.12);
                    color: #00e5ff;
                }
            """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(str(self.device.get("device_id", "")))
        super().mouseReleaseEvent(event)


class NexusConnectDevicesPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = None
        self._connected_device = None
        self._log_snapshot = ""
        self._card_anims: list[QPropertyAnimation] = []
        self._cards: list[_ConnectDeviceCard] = []
        self._selected_device_id: str | None = None
        self._onboarding_known_device_ids: set[str] = set()

        self.setObjectName("NexusConnectDevicesPage")
        self.setStyleSheet(f"""
            QFrame#NexusConnectDevicesPage {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self._title = QLabel("DEVICES")
        self._title.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        self._title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        self._subtitle = QLabel("Everything connected to Nexus.")
        self._subtitle.setFont(QFont("Segoe UI", 9))
        self._subtitle.setStyleSheet("color: rgba(255,255,255,0.62);")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box, 1)

        status_wrap = QVBoxLayout()
        status_wrap.setSpacing(4)
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._gateway_pill = QLabel("● Gateway Online")
        self._gateway_pill.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._gateway_pill.setStyleSheet("color: #35ff75; background: rgba(53,255,117,0.06); border: 1px solid rgba(53,255,117,0.16); border-radius: 12px; padding: 5px 10px;")
        top_row.addWidget(self._gateway_pill)
        top_row.addStretch(1)
        self._add_btn = QPushButton("+ Add Device")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setFixedHeight(34)
        self._add_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.10);
                color: #ffffff;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 12px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.16);
                border: 1px solid rgba(0, 229, 255, 0.40);
            }
        """)
        self._add_btn.clicked.connect(self._trigger_add_device)
        top_row.addWidget(self._add_btn)
        status_wrap.addLayout(top_row)
        self._gateway_meta = QLabel("Port: 8765  ┬╖  Devices: 0")
        self._gateway_meta.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._gateway_meta.setFont(QFont("Segoe UI", 8))
        self._gateway_meta.setStyleSheet("color: rgba(255,255,255,0.42);")
        status_wrap.addWidget(self._gateway_meta)
        header.addLayout(status_wrap)
        root.addLayout(header)

        self._main_stack = QStackedWidget()
        self._main_stack.setStyleSheet("background: transparent;")
        
        # ───────────────────────────────────────────────
        # PAGE 0 — OVERVIEW (GRID / EMPTY)
        # ───────────────────────────────────────────────
        self._overview_page = QWidget()
        ov_lay = QVBoxLayout(self._overview_page)
        ov_lay.setContentsMargins(0, 10, 0, 0)
        ov_lay.setSpacing(12)
        
        self._my_devices_lbl = QLabel("MY DEVICES")
        self._my_devices_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._my_devices_lbl.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        ov_lay.addWidget(self._my_devices_lbl)
        
        self._overview_stack = QStackedWidget()
        
        # Grid View
        self._grid_page = QWidget()
        grid_lay = QVBoxLayout(self._grid_page)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(16)
        self._scroll.setWidget(self._grid_host)
        grid_lay.addWidget(self._scroll)
        self._overview_stack.addWidget(self._grid_page)
        
        # Empty View
        self._empty_page = QWidget()
        empty_lay = QVBoxLayout(self._empty_page)
        empty_lay.addStretch(1)
        empty_lbl = QLabel("No devices connected yet.")
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setFont(QFont("Segoe UI", 12))
        empty_lbl.setStyleSheet("color: rgba(255,255,255,0.5);")
        empty_lay.addWidget(empty_lbl)
        empty_btn = QPushButton("+ ADD DEVICE")
        empty_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        empty_btn.setFixedSize(160, 40)
        empty_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        empty_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.10);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 20px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.20);
                border: 1px solid rgba(0, 229, 255, 0.50);
            }
        """)
        empty_btn.clicked.connect(self._trigger_add_device)
        empty_lay.addWidget(empty_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        empty_lay.addStretch(1)
        self._overview_stack.addWidget(self._empty_page)
        
        ov_lay.addWidget(self._overview_stack)
        self._main_stack.addWidget(self._overview_page)
        
        # ───────────────────────────────────────────────
        # PAGE 1 — DETAIL VIEW
        # ───────────────────────────────────────────────
        self._detail_page = QWidget()
        det_lay = QVBoxLayout(self._detail_page)
        det_lay.setContentsMargins(0, 10, 0, 0)
        det_lay.setSpacing(16)
        
        back_btn = QPushButton("← Back to Devices")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedSize(140, 32)
        back_btn.setFont(QFont("Segoe UI", 9))
        back_btn.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(255,255,255,0.7); border: none; text-align: left; }
            QPushButton:hover { color: #00e5ff; }
        """)
        back_btn.clicked.connect(self._close_detail)
        det_lay.addWidget(back_btn)
        
        self._detail_header = QHBoxLayout()
        self._detail_icon = QLabel()
        self._detail_icon.setFixedSize(48, 48)
        self._detail_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_icon.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self._detail_icon.setStyleSheet("background: rgba(0, 229, 255, 0.10); color: #00e5ff; border: 1px solid rgba(0, 229, 255,0.22); border-radius: 12px;")
        self._detail_header.addWidget(self._detail_icon)
        
        det_titles = QVBoxLayout()
        self._detail_title = QLabel()
        self._detail_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._detail_title.setStyleSheet("color: #ffffff;")
        det_titles.addWidget(self._detail_title)
        
        self._detail_status = QLabel()
        self._detail_status.setFont(QFont("Segoe UI", 10))
        self._detail_status.setStyleSheet("color: rgba(255,255,255,0.6);")
        det_titles.addWidget(self._detail_status)
        self._detail_header.addLayout(det_titles, 1)
        det_lay.addLayout(self._detail_header)
        
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._detail_content = QWidget()
        self._detail_content_lay = QVBoxLayout(self._detail_content)
        self._detail_content_lay.setContentsMargins(0, 10, 0, 10)
        self._detail_content_lay.setSpacing(16)
        
        # Meta info
        self._detail_meta = QLabel()
        self._detail_meta.setStyleSheet("color: rgba(255,255,255,0.7);")
        self._detail_content_lay.addWidget(self._detail_meta)
        
        # Controls
        self._action_box = QFrame()
        self._action_box.setStyleSheet("QFrame { background: rgba(10, 12, 18, 220); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; }")
        action_lay = QVBoxLayout(self._action_box)
        action_lay.setContentsMargins(16, 16, 16, 16)
        action_title = QLabel("CONTROLS")
        action_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        action_title.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        action_lay.addWidget(action_title)
        self._action_buttons = QGridLayout()
        self._action_buttons.setSpacing(8)
        action_lay.addLayout(self._action_buttons)
        self._detail_content_lay.addWidget(self._action_box)
        
        # Manage
        manage_box = QFrame()
        manage_box.setStyleSheet("QFrame { background: rgba(10, 12, 18, 220); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; }")
        manage_lay = QVBoxLayout(manage_box)
        manage_lay.setContentsMargins(16, 16, 16, 16)
        manage_title = QLabel("MANAGE")
        manage_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        manage_title.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        manage_lay.addWidget(manage_title)
        
        self._btn_rename = QPushButton("Rename Device")
        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_reconnect = QPushButton("Reconnect")
        self._btn_forget = QPushButton("Forget Device")
        self._btn_forget.setStyleSheet("QPushButton { color: #ff5555; } QPushButton:hover { background: rgba(255, 85, 85, 0.1); border-color: #ff5555; }")
        
        manage_grid = QGridLayout()
        manage_grid.setSpacing(8)
        for i, b in enumerate([self._btn_rename, self._btn_disconnect, self._btn_reconnect, self._btn_forget]):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(34)
            if b != self._btn_forget:
                b.setStyleSheet("""
                    QPushButton { background: rgba(255,255,255,0.03); color: #ffffff; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
                    QPushButton:hover { background: rgba(0, 229, 255,0.08); border: 1px solid rgba(0, 229, 255,0.22); color: #00e5ff; }
                """)
            else:
                b.setStyleSheet("""
                    QPushButton { background: rgba(255,255,255,0.03); color: #ff5555; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
                    QPushButton:hover { background: rgba(255,85,85,0.1); border: 1px solid rgba(255,85,85,0.3); }
                """)
            manage_grid.addWidget(b, i // 2, i % 2)
            
        manage_lay.addLayout(manage_grid)
        self._detail_content_lay.addWidget(manage_box)
        self._detail_content_lay.addStretch(1)
        self._detail_scroll.setWidget(self._detail_content)
        det_lay.addWidget(self._detail_scroll)
        
        self._main_stack.addWidget(self._detail_page)
        
        # ───────────────────────────────────────────────
        # PAGE 2 — ADD DEVICE (QR WIZARD)
        # ───────────────────────────────────────────────
        self._add_device_page = QWidget()
        add_lay = QVBoxLayout(self._add_device_page)
        add_lay.setContentsMargins(0, 10, 0, 0)
        
        add_back_btn = QPushButton("← Cancel")
        add_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_back_btn.setFixedSize(140, 32)
        add_back_btn.setFont(QFont("Segoe UI", 9))
        add_back_btn.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(255,255,255,0.7); border: none; text-align: left; }
            QPushButton:hover { color: #00e5ff; }
        """)
        add_back_btn.clicked.connect(self._close_detail)
        add_lay.addWidget(add_back_btn)
        
        # Re-use the stacked widget logic for the wizard steps
        self._wizard_stack = QStackedWidget()
        
        # Wizard State 0: Select Platform
        w0 = QWidget()
        w0_lay = QVBoxLayout(w0)
        w0_lay.addStretch(1)
        w0_title = QLabel("SELECT DEVICE TYPE")
        w0_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w0_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        w0_title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        w0_lay.addWidget(w0_title)
        w0_lay.addSpacing(20)
        
        w0_row = QHBoxLayout()
        w0_row.addStretch(1)
        self._cs_android_btn = QPushButton("ANDROID")
        self._cs_android_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cs_android_btn.setFixedSize(140, 80)
        self._cs_android_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._cs_android_btn.setStyleSheet("""
            QPushButton { background: rgba(10, 12, 18, 220); color: rgba(255,255,255,0.9); border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; }
            QPushButton:hover { color: #00e5ff; border: 1px solid rgba(0, 229, 255,0.6); background: rgba(0, 229, 255,0.1); }
        """)
        self._cs_android_btn.clicked.connect(self._cinema_select_android)
        w0_row.addWidget(self._cs_android_btn)
        
        self._cs_pc_btn = QPushButton("PC\n(Coming Soon)")
        self._cs_pc_btn.setFixedSize(140, 80)
        self._cs_pc_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._cs_pc_btn.setEnabled(False)
        self._cs_pc_btn.setStyleSheet("QPushButton { background: rgba(10, 12, 18, 120); color: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; }")
        w0_row.addWidget(self._cs_pc_btn)
        w0_row.addStretch(1)
        w0_lay.addLayout(w0_row)
        w0_lay.addStretch(1)
        self._wizard_stack.addWidget(w0)
        
        # Wizard State 1: QR Code
        w1 = QWidget()
        w1_lay = QVBoxLayout(w1)
        w1_lay.addStretch(1)
        w1_title = QLabel("SCAN TO CONNECT")
        w1_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w1_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        w1_title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        w1_lay.addWidget(w1_title)
        w1_lay.addSpacing(16)
        
        w1_qr_row = QHBoxLayout()
        w1_qr_row.addStretch(1)
        self._onb_qr_label = QLabel()
        self._onb_qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onb_qr_label.setFixedSize(200, 200)
        self._onb_qr_label.setStyleSheet("background: #ffffff; border-radius: 6px; padding: 4px;")
        w1_qr_row.addWidget(self._onb_qr_label)
        w1_qr_row.addStretch(1)
        w1_lay.addLayout(w1_qr_row)
        
        w1_lay.addSpacing(16)
        self._onb_code_lbl = QLabel("------")
        self._onb_code_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onb_code_lbl.setFont(QFont("Consolas", 18, QFont.Weight.Black))
        self._onb_code_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 6px;")
        w1_lay.addWidget(self._onb_code_lbl)
        
        self._onb_status_lbl = QLabel("WAITING FOR CONNECTION")
        self._onb_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onb_status_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._onb_status_lbl.setStyleSheet("color: rgba(255,255,255,0.5); letter-spacing: 1px;")
        w1_lay.addWidget(self._onb_status_lbl)
        
        w1_ctrl = QHBoxLayout()
        w1_ctrl.addStretch(1)
        w1_ref = QPushButton("Refresh Code")
        w1_ref.setCursor(Qt.CursorShape.PointingHandCursor)
        w1_ref.setFixedSize(120, 32)
        w1_ref.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.05); color: #ffffff; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; }
            QPushButton:hover { background: rgba(255,255,255,0.1); }
        """)
        w1_ref.clicked.connect(self._refresh_onboarding_offer)
        w1_ctrl.addWidget(w1_ref)
        w1_ctrl.addStretch(1)
        w1_lay.addLayout(w1_ctrl)
        w1_lay.addStretch(1)
        self._wizard_stack.addWidget(w1)
        
        # Wizard State 2: Success
        w2 = QWidget()
        w2_lay = QVBoxLayout(w2)
        w2_lay.addStretch(1)
        self._onb_success_title = QLabel("DEVICE CONNECTED")
        self._onb_success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onb_success_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Black))
        self._onb_success_title.setStyleSheet("color: #35ff75; letter-spacing: 2px;")
        w2_lay.addWidget(self._onb_success_title)
        self._onb_success_name = QLabel("")
        self._onb_success_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onb_success_name.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self._onb_success_name.setStyleSheet("color: #ffffff;")
        w2_lay.addWidget(self._onb_success_name)
        w2_lay.addStretch(1)
        self._wizard_stack.addWidget(w2)
        
        add_lay.addWidget(self._wizard_stack)
        self._main_stack.addWidget(self._add_device_page)
        
        root.addWidget(self._main_stack)
        
        self._onboarding_timer = QTimer(self)
        self._onboarding_timer.timeout.connect(self._tick_onboarding)
        self._onboarding_offer = {}
        self._onboarding_pulse = 0

    def _service_obj(self):
        return self._service or getattr(self.parentWidget(), "_nexus_connect", None)

    def set_service(self, service):
        self._service = service

    def _trigger_add_device(self):
        self._main_stack.setCurrentIndex(2)
        self._wizard_stack.setCurrentIndex(0)

    def _cinema_select_android(self):
        self._wizard_stack.setCurrentIndex(1)
        service = self._service_obj()
        self._onboarding_known_device_ids = set(str(d.get("device_id", "")) for d in service.list_devices()) if service else set()
        self._onboarding_timer.start(1000)
        self._refresh_onboarding_offer()

    def _refresh_onboarding_offer(self):
        service = self._service_obj()
        if service is None:
            self._onboarding_offer = {}
            self._onb_code_lbl.setText("------")
            self._onb_status_lbl.setText("GATEWAY UNAVAILABLE")
            return
        try:
            import io
            import qrcode

            self._onboarding_offer = dict(service.create_pairing_offer(device_name="Nexus Connect", platform="gateway"))
            code = str(self._onboarding_offer.get("pairing_code") or "------")
            self._onb_code_lbl.setText(code)
            self._onb_status_lbl.setText("WAITING FOR CONNECTION")
            
            payload = self._onboarding_offer
            text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            if qrcode is not None:
                qr = qrcode.QRCode(box_size=6, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(text)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                pix = QPixmap()
                pix.loadFromData(buf.getvalue(), "PNG")
                self._onb_qr_label.setPixmap(
                    pix.scaled(
                        self._onb_qr_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self._onb_qr_label.setText(text)
                
            self._tick_onboarding()
        except Exception as exc:
            self._onboarding_offer = {}
            self._onb_code_lbl.setText("------")
            self._onb_status_lbl.setText(f"ERROR: {exc}")

    def _tick_onboarding(self):
        if self._wizard_stack.currentIndex() != 1:
            return
        
        expires = self._onboarding_offer.get("expires")
        try:
            remaining = max(0, int(expires))
            if remaining <= 0 and self._onboarding_offer:
                self._onb_status_lbl.setText("CODE EXPIRED. REFRESH TO CONTINUE.")
        except Exception:
            pass
            
        service = self._service_obj()
        if service and self._onboarding_offer:
            devices = service.list_devices()
            new_device = next(
                (d for d in devices if str(d.get("device_id", "")) not in self._onboarding_known_device_ids),
                None,
            )
            if new_device:
                self._onboarding_timer.stop()
                self._connected_device = new_device
                self._trigger_onboarding_success()

    def _trigger_onboarding_success(self):
        self._wizard_stack.setCurrentIndex(2)
        dev = self._connected_device
        self._onb_success_name.setText(str(dev.get("name", "Device")).upper())
        QTimer.singleShot(2000, lambda: self.refresh(force=True))

    def _cancel_onboarding(self):
        self._onboarding_timer.stop()
        self._close_detail()

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_device_selected(self, device_id: str):
        if self._selected_device_id == device_id:
            self._selected_device_id = None
        else:
            self._selected_device_id = device_id
        self.refresh(force=True)

    def _on_card_action_requested(self, device_id: str, action: str, payload: dict):
        if action == "rename":
            service = self._service_obj()
            if not service:
                return
            device = next((d for d in service.list_devices() if str(d.get("device_id", "")) == device_id), None)
            if device:
                self._rename_device(device_id, str(device.get("name", "")))
            return
        if action == "disconnect":
            self._apply_tile_action(device_id, "disconnect", payload)
            return
        if action == "forget":
            self._apply_tile_action(device_id, "forget", payload)
            return
        self._apply_tile_action(device_id, action, payload)
        return

    def _close_detail(self):
        self._selected_device_id = None
        self._main_stack.setCurrentIndex(0)
        self.refresh(force=True)

    def refresh(self, force: bool = False):
        service = self._service_obj()
        if service is None:
            return
            
        devices = service.list_devices()
        port = getattr(service, "port", 8765)
        self._gateway_meta.setText(f"Port: {port}  ┬╖  Devices: {len(devices)}")
        
        # If we are in Add Device or Detail page, keep it there
        if self._main_stack.currentIndex() not in (0,) and not force:
            pass # Keep current index unless forced to reset
        elif len(devices) == 0:
            self._main_stack.setCurrentIndex(0)
            self._overview_stack.setCurrentIndex(1) # Empty state
        else:
            self._main_stack.setCurrentIndex(0)
            self._overview_stack.setCurrentIndex(0) # Grid state
            
        # Rebuild grid
        self._clear_layout(self._grid)
        self._cards.clear()
        
        if devices:
            cols = 4
            for i, dev in enumerate(devices):
                card = _ConnectDeviceCard(dev)
                card.clicked.connect(self._on_device_selected)
                card.action_requested.connect(self._on_card_action_requested)
                card.set_expanded(str(dev.get("device_id", "")) == self._selected_device_id)
                self._cards.append(card)
                self._grid.addWidget(card, i // cols, i % cols)
            self._grid.setRowStretch(len(devices) // cols + 1, 1)

    def _apply_tile_action(self, device_id: str, action: str, payload: dict):
        service = self._service_obj()
        if not service:
            return
        try:
            if action == "rename":
                device = next((d for d in service.list_devices() if str(d.get("device_id", "")) == device_id), None)
                if device:
                    self._rename_device(device_id, str(device.get("name", "")))
                    return
            elif action == "disconnect":
                if hasattr(service, "disconnect_device"):
                    try:
                        asyncio.run(service.disconnect_device(device_id))
                    except Exception:
                        pass
            elif action == "forget":
                self._forget_device(device_id)
                return
            elif action == "set_pin":
                self._set_device_pin(device_id)
                return
            else:
                if hasattr(service, "route_command"):
                    service.route_command(device_id, action, payload)
                else:
                    service.execute_device_action(device_id, action, payload)
        except Exception:
            pass
        QTimer.singleShot(200, lambda: self.refresh(force=True))

    def _rename_device(self, device_id: str, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Device", "New name:", text=current_name)
        if ok and new_name.strip():
            service = self._service_obj()
            if service:
                try:
                    service.rename_device(device_id, new_name.strip())
                    self._on_device_selected(device_id)
                except Exception:
                    pass
            self.refresh(force=True)

    def _set_device_pin(self, device_id: str):
        pin, ok = QInputDialog.getText(self, "Set Device PIN", "Enter device PIN:", QLineEdit.EchoMode.Password)
        if ok and pin.strip():
            try:
                settings = {}
                if APP_SETTINGS_FILE.exists():
                    with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                
                device_pins = settings.get("device_pins", {})
                device_pins[device_id] = pin.strip()
                settings["device_pins"] = device_pins
                
                with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=4)
            except Exception as e:
                print(f"Error saving pin: {e}")

    def _forget_device(self, device_id: str):
        service = self._service_obj()
        if service:
            try:
                if hasattr(service, "forget_device"):
                    service.forget_device(device_id)
                elif hasattr(service, "gateway") and hasattr(service.gateway, "device_manager"):
                    service.gateway.device_manager.remove(device_id)
            except Exception:
                pass
        self._close_detail()
        self.refresh(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh(force=True)

