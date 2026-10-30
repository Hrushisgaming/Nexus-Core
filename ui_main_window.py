"""Primary desktop window for Nexus Core.

Split from ui.py to isolate the main window implementation. The namespace
bridge keeps existing UI helpers and settings-page classes available without
changing runtime behaviour during this structural refactor.
"""
import ui as _ui
globals().update({name: value for name, value in vars(_ui).items() if not name.startswith("__")})

class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _scan_sig  = pyqtSignal(bool, str)
    _briefing_sig = pyqtSignal(object)
    _briefing_hide_sig = pyqtSignal()
    _attention_sig = pyqtSignal(object)
    _meeting_sig = pyqtSignal(object)
    _task_workspace_sig = pyqtSignal(object)
    _screen_capture_sig = pyqtSignal()
    discord_config_changed = pyqtSignal(object)
    discord_status_changed = pyqtSignal(str)
    minimized = pyqtSignal()
    restored = pyqtSignal()
    _hud_operation_sig = pyqtSignal(dict)
    _hud_deliverable_sig = pyqtSignal(dict)
    _circuit_hud_sig = pyqtSignal(object)
    _radar_hud_sig = pyqtSignal(object)
    _space_cleaner_sig = pyqtSignal(object)
    _call_screening_sig = pyqtSignal(object)
    _confirm_sig = pyqtSignal(str, str, str)
    _memory_overlay_sig = pyqtSignal(str)
    _audio_level_sig = pyqtSignal(float)
    _subtitle_sig = pyqtSignal(str, str, bool)
    _ultron_malfunction_sig = pyqtSignal(dict)

    def _make_window_icon(self) -> QIcon:
        return _logo_icon()

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.Tool, False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowIcon(self._make_window_icon())
        self.setWindowTitle("Nexus Core")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self.on_attention_action = None
        self.on_chat_event = None
        self.on_remote_clicked = None
        self._muted           = False
        self._wakeword_listening = False
        self._current_file: str | None = None
        self._state = "LISTENING"
        self._left_collapsed  = False
        self._right_collapsed = False
        self._current_page = "dashboard"
        self._settings_bridge = None
        self._api_ready = False
        self._app_settings_cache: dict | None = None
        self._overlay: QWidget | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._scan_overlay: ScanningOverlay | None = None
        self._incoming_alert: IncomingAlertDialog | None = None
        self._meeting_overlay: MeetingOverlay | None = None
        self._circuit_overlay: QWidget | None = None
        self._radar_overlay: QWidget | None = None
        self._space_cleaner_overlay: QWidget | None = None
        self._call_screening_dialog: QDialog | None = None
        self._call_screening_transcript: QLabel | None = None
        self._meeting_overlay_collapsed = False
        self._chat_source_queue: deque[str] = deque()
        self._subtitle_sig.connect(self._do_set_live_subtitles)

        central = BackgroundWidget(BACKGROUND_IMAGE_FILE if BACKGROUND_IMAGE_FILE.exists() else None)
        central.setStyleSheet("background: transparent;")
        self._bg_widget = central
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._taskbar = QWidget()
        self._taskbar.setStyleSheet("background: transparent;")
        taskbar_lay = QHBoxLayout(self._taskbar)
        taskbar_lay.setContentsMargins(10, 10, 10, 10)
        
        self._btn_dashboard = QPushButton("Dashboard")
        self._btn_chat = QPushButton("Chat")
        self._btn_settings = QPushButton("Settings")

        for btn in (self._btn_dashboard, self._btn_chat, self._btn_settings):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background: rgba(12,14,18,200); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }} QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}")
        
        self._status_badge = QLabel("● ONLINE")
        self._status_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._status_badge.setStyleSheet(
            f"color: {C.PRI}; background: rgba(12,14,18,220); border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 5px 12px;"
        )
        taskbar_lay.addWidget(self._status_badge)

        # Voice-reactive dynamic waveform right next to status badge
        self._taskbar_waveform = VoiceWaveformVisualizer(bars=16, parent=self._taskbar)
        taskbar_lay.addWidget(self._taskbar_waveform)

        # Real-time Live Subtitles Banner directly alongside the waveform
        self._live_subtitle_pill = QFrame(self._taskbar)
        self._live_subtitle_pill.setObjectName("LiveSubtitlePill")
        self._live_subtitle_pill.setStyleSheet("""
            QFrame#LiveSubtitlePill {
                background: rgba(14, 18, 27, 230);
                border: 1px solid rgba(0, 229, 255, 0.32);
                border-radius: 8px;
                padding: 2px 10px;
            }
        """)
        sub_lay = QHBoxLayout(self._live_subtitle_pill)
        sub_lay.setContentsMargins(6, 2, 6, 2)
        sub_lay.setSpacing(8)

        self._live_sub_speaker = QLabel("● LISTENING")
        self._live_sub_speaker.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._live_sub_speaker.setStyleSheet("color: #00e5ff; background: transparent; border: none;")

        self._live_sub_text = QLabel("Listening for voice...")
        self._live_sub_text.setFont(QFont("Segoe UI", 9))
        self._live_sub_text.setStyleSheet("color: #ffffff; background: transparent; border: none;")

        sub_lay.addWidget(self._live_sub_speaker)
        sub_lay.addWidget(self._live_sub_text)
        taskbar_lay.addWidget(self._live_subtitle_pill)

        taskbar_lay.addStretch()

        # Omni-Command Palette Quick Launcher
        self._btn_search = QPushButton("🔍 Search / Palette (Ctrl+K)")
        self._btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_search.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255, 0.08);
                color: {C.ACC};
                border: 1px solid rgba(0, 229, 255, 0.30);
                border-radius: 8px;
                padding: 5px 14px;
                font-weight: bold;
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.22);
                border: 1px solid {C.ACC};
                color: #ffffff;
            }}
        """)
        self._btn_search.clicked.connect(self._open_command_palette)
        taskbar_lay.addWidget(self._btn_search)

        taskbar_lay.addWidget(self._btn_dashboard)
        taskbar_lay.addWidget(self._btn_chat)
        taskbar_lay.addWidget(self._btn_settings)
        
        # Compact Gestures button in top bar
        self._btn_gestures_top = QPushButton("🖐 Gestures")
        self._btn_gestures_top.setFixedSize(95, 30)
        self._btn_gestures_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gestures_top.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.08); color: #ffffff; border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(0, 229, 255, 0.18); color: #00e5ff; border: 1px solid #00e5ff; }"
        )
        self._btn_gestures_top.clicked.connect(self._toggle_gestures_preview)
        taskbar_lay.addWidget(self._btn_gestures_top)
        
        taskbar_lay.addStretch()

        root.addWidget(self._taskbar)

        # Global shortcuts for Omni-Command Palette
        self._shortcut_ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self._shortcut_ctrl_k.activated.connect(self._open_command_palette)
        self._shortcut_ctrl_space = QShortcut(QKeySequence("Ctrl+Space"), self)
        self._shortcut_ctrl_space.activated.connect(self._open_command_palette)

        # Floating gesture card (hidden by default - use top bar button instead)
        self._floating_gesture_card = FloatingGestureCard(self.centralWidget())
        self._floating_gesture_card.hide()

        self._center_panel = self._build_center_panel_modern(face_path)
        body.addWidget(self._center_panel, stretch=1)
        _attach_pulse_glow(self._center_panel, color=C.PRI, blur_min=6.0, blur_max=14.0, alpha=36, period_ms=4200)

        self._right_collapsed = False
        self._right_panel = self._build_right_panel_modern()
        body.addWidget(self._right_panel, stretch=0)

        self._btn_dashboard.clicked.connect(self._on_nav_dashboard)
        self._btn_chat.clicked.connect(self._toggle_right_sidebar)
        self._btn_settings.clicked.connect(self._on_nav_settings)
        self._update_nav_styles()

        root.addLayout(body, stretch=1)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik gÃ¼ncelleme timer'Ä±
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._on_log_text)
        self._state_sig.connect(self._apply_state)
        self._briefing_sig.connect(self._apply_daily_briefing)
        self._briefing_hide_sig.connect(self._schedule_daily_briefing_hide)
        self._attention_sig.connect(self._show_attention_alert)
        self._meeting_sig.connect(self._apply_meeting_state)
        self._task_workspace_sig.connect(self._apply_task_workspace)
        self._scan_sig.connect(self._apply_scan_state)
        self._screen_capture_sig.connect(self._on_screen_capture_requested)
        self.discord_status_changed.connect(self._on_discord_status_update)
        self._hud_operation_sig.connect(self._apply_hud_operation)
        self._hud_deliverable_sig.connect(self._apply_hud_deliverable)
        self._circuit_hud_sig.connect(self._apply_circuit_overlay)
        self._radar_hud_sig.connect(self._apply_radar_overlay)
        self._space_cleaner_sig.connect(self._apply_space_cleaner_overlay)
        self._call_screening_sig.connect(self._apply_call_screening)
        self._confirm_sig.connect(self._apply_confirm_overlay)
        self._memory_overlay_sig.connect(self._apply_memory_overlay)
        self._audio_level_sig.connect(self._on_audio_level_sig)
        self._ultron_dialog: UltronMalfunctionDialog | None = None
        self._ultron_malfunction_sig.connect(self._apply_ultron_malfunction)
        try:
            from core import confirm as confirm_gate
            confirm_gate.bind(self.show_confirm, self.hide_confirm, self._log_sig.emit)
        except Exception:
            pass

        import threading
        self._screen_capture_event = threading.Event()

        self._ready = False
        self._card_hide_tmr = QTimer(self)
        self._card_hide_tmr.setSingleShot(True)
        self._card_hide_tmr.timeout.connect(self._hide_command_cards)
        self._briefing_hide_tmr = QTimer(self)
        self._briefing_hide_tmr.setSingleShot(True)
        self._briefing_hide_tmr.timeout.connect(self._hide_daily_briefing_card)

        self._ready = self._check_config()
        self._api_ready = self._ready
        if self._ready:
            self._apply_state("LISTENING")
        else:
            self._show_setup(self._load_api_defaults())
        self._scan_sig.connect(self._apply_scan_state)

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_left = QShortcut(QKeySequence("Ctrl+["), self)
        sc_left.activated.connect(self._toggle_left_sidebar)
        sc_right = QShortcut(QKeySequence("Ctrl+]"), self)
        sc_right.activated.connect(self._toggle_right_sidebar)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update(data)
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        _write_settings_files(settings)
        self._app_settings_cache = dict(settings)

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log("ERR: startup animation setting failed: %s" % e)
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log("SYS: Startup animation %s." % state)

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update(data)
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif not channel_id:
            status = "Token saved - channel optional"
            color = C.TEXT_MED
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setText("Start Discord Bot")
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setText("Stop Discord Bot")
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _save_discord_token(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        settings = self._load_discord_settings()
        settings["bot_token"] = token
        settings["channel_id"] = channel_id
        settings["enabled"] = bool(token)
        self._discord_enabled = bool(token)
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        if token:
            self._log.append_log("SYS: Discord bot token saved and bot enabled.")
            self._refresh_discord_card("Token saved")
        else:
            self._log.append_log("SYS: Discord bot token cleared.")
            self._discord_enabled = False
            self._refresh_discord_card("Token required")

    def _start_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        if not token:
            self._discord_enabled = False
            self._save_discord_token()
            return
        self._discord_enabled = True
        settings = {
            "bot_token": token,
            "enabled": True,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot started.")
        self._refresh_discord_card()

    def _stop_discord_bot(self):
        if not hasattr(self, "_discord_token_input"):
            return
        token = self._discord_token_input.text().strip()
        channel_id = self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else ""
        self._discord_enabled = False
        settings = {
            "bot_token": token,
            "enabled": False,
            "channel_id": channel_id,
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._log.append_log("SYS: Discord bot stopped.")
        self._refresh_discord_card()

    def _load_api_defaults(self) -> dict:
        merged = {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "anthropic_api_key": "",
            "nvidia_api_key": "",
            "groq_api_key": "",
            "custom_ai_api_key": "",
            "tavily_api_key": "",
            "firecrawl_api_key": "",
            "serpapi_api_key": "",
            "pollinations_api_key": "",
            "elevenlabs_api_key": "",
            "fish_audio_api_key": "",
            "cloudflare_api_key": "",
            "cloudflare_account_id": "",
            "os_system": platform.system(),
        }
        # api_keys.json first (first-run setup writes here), then app_settings.json;
        # a non-empty saved value is never replaced by an empty one.
        for source in (_read_json_dict(API_FILE), _read_json_dict(APP_SETTINGS_FILE)):
            for k, v in source.items():
                if isinstance(v, str) and not v.strip() and merged.get(k):
                    continue
                merged[k] = v
        return merged

    def _open_api_keys(self):
        """Open the API-keys dialog and merge the result into saved settings."""
        try:
            current = self._load_api_defaults()
            dialog = APIKeySettingsDialog(current, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            merged = self._load_app_settings()
            merged.update(current)
            merged.update(dialog.get_settings())
            self._save_app_settings(merged)
            try:
                self._log.append_log("SYS: API keys updated.")
            except Exception:
                pass
        except Exception as e:
            print(f"[Settings] Error saving API keys: {e}")

    def _startup_enabled(self) -> bool:
        from core.platform_api import platform_api
        return platform_api.is_startup_enabled("Nexus Core")

    def _set_startup_enabled(self, enabled: bool) -> bool:
        from core.platform_api import platform_api
        try:
            return platform_api.set_startup(
                enabled,
                app_name="Nexus Core",
                target_path=_startup_run_value().strip('"').split(" ")[0] if _startup_run_value() else None,
            )
        except Exception as e:
            self._log.append_log(f"ERR: startup setting failed: {e}")
            return False

    def _refresh_startup_button(self):
        if not hasattr(self, "_startup_btn"):
            return
        if platform.system() != "Windows":
            self._startup_btn.setText("Start on Startup (Windows only)")
            self._startup_btn.setEnabled(False)
            return
        if self._startup_enabled():
            self._startup_btn.setText("Start on Startup: ON")
        else:
            self._startup_btn.setText("Start on Startup: OFF")

    def _toggle_startup(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_enabled()
        if self._set_startup_enabled(enabled):
            self._refresh_startup_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Windows startup {state}.")

    def _toggle_left_sidebar(self):
        self._left_collapsed = not self._left_collapsed
        self._apply_sidebar_state()

    def _toggle_right_sidebar(self):
        self._right_collapsed = not self._right_collapsed
        self._apply_sidebar_state()
        if not self._right_collapsed and hasattr(self, "_inline_workspace"):
            if hasattr(self._inline_workspace, "focus_input"):
                self._inline_workspace.focus_input()

    def _apply_sidebar_state(self):
        if hasattr(self, "_left_content"):
            self._left_content.setVisible(not self._left_collapsed)
            if hasattr(self, "_left_panel"):
                self._left_panel.setFixedWidth(56 if self._left_collapsed else _LEFT_W)
            if hasattr(self, "_left_toggle_btn"):
                self._left_toggle_btn.setText(">" if self._left_collapsed else "<")
                self._left_toggle_btn.setToolTip("Expand left sidebar" if self._left_collapsed else "Collapse left sidebar")
        if hasattr(self, "_right_panel"):
            if self._right_collapsed:
                self._right_panel.setVisible(False)
            else:
                self._right_panel.setVisible(True)
                self._right_panel.setFixedWidth(_RIGHT_W)
        if hasattr(self, "_right_content"):
            self._right_content.setVisible(not self._right_collapsed)
        if hasattr(self, "_right_stack"):
            self._right_stack.setVisible(not self._right_collapsed)
        if hasattr(self, "_btn_chat"):
            if not getattr(self, "_right_collapsed", False):
                self._btn_chat.setStyleSheet(
                    f"QPushButton {{ background: rgba(0, 229, 255, 0.18); color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }}"
                )
            else:
                self._btn_chat.setStyleSheet(
                    f"QPushButton {{ background: rgba(12,14,18,200); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }} QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
                )
        if hasattr(self, "_center_panel"):
            self._center_panel.update()
        self.resizeEvent(None)

    def _on_nav_dashboard(self):
        if hasattr(self, "_center_stack"):
            self._center_stack.setCurrentIndex(0)
        self._update_nav_styles()

    def _on_nav_settings(self):
        if hasattr(self, "_center_stack"):
            self._center_stack.setCurrentIndex(4)
        self._update_nav_styles()

    def _update_nav_styles(self):
        cur_idx = self._center_stack.currentIndex() if hasattr(self, "_center_stack") else 0
        if hasattr(self, "_btn_dashboard"):
            if cur_idx == 0:
                self._btn_dashboard.setStyleSheet(
                    f"QPushButton {{ background: rgba(0, 229, 255, 0.18); color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }}"
                )
            else:
                self._btn_dashboard.setStyleSheet(
                    f"QPushButton {{ background: rgba(12,14,18,200); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }} QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
                )
        if hasattr(self, "_btn_settings"):
            if cur_idx in (3, 4):
                self._btn_settings.setStyleSheet(
                    f"QPushButton {{ background: rgba(0, 229, 255, 0.18); color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }}"
                )
            else:
                self._btn_settings.setStyleSheet(
                    f"QPushButton {{ background: rgba(12,14,18,200); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 5px 15px; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; }} QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
                )


    def set_settings_bridge(self, bridge):
        self._settings_bridge = bridge
        if hasattr(self, "_settings_page") and hasattr(self._settings_page, "set_controller"):
            self._settings_page.set_controller(bridge)
        if hasattr(self, "_settings_sidebar") and hasattr(self._settings_sidebar, "set_controller"):
            self._settings_sidebar.set_controller(bridge)
        self._set_page(self._current_page)

    def _set_page(self, page: str):
        self._current_page = page
        if hasattr(self, "_center_stack") and isinstance(self._center_stack, QStackedWidget):
            index = {"dashboard": 0, "home": 1, "devices": 2, "settings": 3}.get(page, 0)
            self._center_stack.setCurrentIndex(index)
        if page == "devices" and hasattr(self, "_devices_page"):
            try:
                self._devices_page.refresh()
            except Exception:
                pass
        if page == "home" and hasattr(self, "_home_page"):
            try:
                self._home_page.refresh()
            except Exception:
                pass
        if page == "dashboard" and hasattr(self, "_smart_devices_section"):
            try:
                self._smart_devices_section.refresh(force=True)
            except Exception:
                pass
        if hasattr(self, "_right_panel"):
            self._right_panel.setVisible(page == "dashboard")
        if hasattr(self, "_right_stack") and isinstance(self._right_stack, QStackedWidget):
            self._right_stack.setCurrentIndex({"dashboard": 0, "settings": 1, "home": 2}.get(page, 2))
            self._right_stack.setVisible(page == "dashboard")
        if self._settings_bridge and hasattr(self._settings_bridge, "set_dashboard_page"):
            try:
                self._settings_bridge.set_dashboard_page(page == "dashboard")
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_page"):
            try:
                self._settings_page.refresh()
            except Exception:
                pass
        if page == "settings" and hasattr(self, "_settings_sidebar"):
            try:
                self._settings_sidebar.refresh()
            except Exception:
                pass

    def set_nexus_connect_service(self, service):
        self._nexus_connect = service
        if hasattr(self, "_devices_page"):
            self._devices_page.set_service(service)
            if service is not None:
                self._devices_page.refresh(force=True)

    def resizeEvent(self, event):
        if event:
            super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible() and self.centralWidget():
            cw = self.centralWidget()
            self._overlay.setGeometry(0, 0, cw.width(), cw.height())
        if hasattr(self, '_floating_gesture_card') and self.centralWidget():
            cw = self.centralWidget()
            rw = self._right_panel.width() if hasattr(self, '_right_panel') and self._right_panel.isVisible() and not getattr(self, '_right_collapsed', False) else 0
            self._floating_gesture_card.move(cw.width() - rw - self._floating_gesture_card.width() - 20, 20)
        if getattr(self, '_briefing_overlay', None) and self._briefing_overlay.isVisible():
            self._position_briefing_overlay()
        if getattr(self, '_remote_overlay', None) and self._remote_overlay.isVisible():
            self._position_remote_overlay()
        if getattr(self, '_confirm_overlay', None) and self._confirm_overlay.isVisible():
            self._position_confirm_overlay()
        if getattr(self, '_memory_overlay', None) and self._memory_overlay.isVisible():
            self._position_memory_overlay()

    def _tick_clock(self):
        if hasattr(self, "_clock_lbl") and self._clock_lbl is not None:
            try:
                self._clock_lbl.setText(time.strftime("%H:%M"))
            except Exception:
                pass
        if hasattr(self, "_date_lbl") and self._date_lbl is not None:
            try:
                self._date_lbl.setText(time.strftime("%A • %d %b"))
            except Exception:
                pass

    def _update_metrics(self):
        if not hasattr(self, "_bar_cpu"):
            return
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        if hasattr(self, "_bar_cpu"):
            self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")
        if hasattr(self, "_stat_cpu"):
            cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 0
            cpu_threads = psutil.cpu_count(logical=True) or cpu_cores
            self._stat_cpu.set_value(
                f"{cpu:.0f}%",
                int(cpu),
                f"{cpu_threads} threads / {cpu_cores or cpu_threads} cores",
            )

        # MEM
        mem = snap["mem"]
        if hasattr(self, "_bar_mem"):
            self._bar_mem.set_value(mem, f"{mem:.0f}%")
        
        if hasattr(self, "_uptime_lbl"):
            try:
                boot = psutil.boot_time()
                uptime_min = int((time.time() - boot) / 60)
                self._uptime_lbl.setText(f"Up: {uptime_min // 60}h {uptime_min % 60}m")
            except: pass

        if hasattr(self, "_stat_mem"):
            vm = psutil.virtual_memory()
            used_gb = vm.used / (1024**3)
            total_gb = vm.total / (1024**3)
            self._stat_mem.set_value(
                f"{mem:.0f}%",
                int(mem),
                f"{used_gb:.1f} GB / {total_gb:.1f} GB used",
            )

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        if hasattr(self, "_bar_net"):
            self._bar_net.set_value(net_pct, net_str)
        if hasattr(self, "_stat_net"):
            self._stat_net.set_value(
                net_str if net >= 1 else "ONLINE",
                int(net_pct),
                _active_net_label(),
            )

        # GPU
        gpu = snap["gpu"]
        if hasattr(self, "_bar_gpu"):
            if gpu >= 0:
                self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
            else:
                self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if hasattr(self, "_bar_tmp"):
            if tmp >= 0:
                tmp_pct = min(100, (tmp / 100) * 100)
                self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
            else:
                self._bar_tmp.set_value(0, "N/A")
        if hasattr(self, "_stat_cam"):
            cam_on = _camera_available()
            self._stat_cam.set_value(
                "ON" if cam_on else "OFF",
                100 if cam_on else 0,
                "Webcam detected" if cam_on else "No camera found",
            )

        if hasattr(self, "_uptime_lbl"):
            try:
                boot_t  = psutil.boot_time()
                elapsed = time.time() - boot_t
                h = int(elapsed // 3600)
                m = int((elapsed % 3600) // 60)
                self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
            except Exception:
                self._uptime_lbl.setText("UP  --:--")

        if hasattr(self, "_proc_lbl"):
            try:
                proc_count = len(psutil.pids())
                self._proc_lbl.setText(f"PROC  {proc_count}")
            except Exception:
                self._proc_lbl.setText("PROC  --")


    def _browse_attachment(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach a file to Nexus Core", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._on_file_selected(path)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._wakeword_listening = self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if hasattr(self, "_taskbar_waveform") and self._taskbar_waveform:
            self._taskbar_waveform.set_muted(self._muted)
        # Also mute the live voice engine's mic input
        if hasattr(self, "_lve") and self._lve is not None:
            self._lve.set_muted(self._muted)
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
            sound_mgr.play_listening_stop()
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")
            sound_mgr.play_listening_start()

    def _toggle_gestures_preview(self):
        """Toggle the floating gesture camera preview card."""
        card = self._floating_gesture_card
        if card.isVisible():
            card.hide()
            card.preview._stop_camera()
            self._btn_gestures_top.setStyleSheet(
                "QPushButton { background: rgba(0, 229, 255, 0.08); color: #ffffff; border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background: rgba(0, 229, 255, 0.18); color: #00e5ff; border: 1px solid #00e5ff; }"
            )
        else:
            card.show()
            card.preview._start_camera()
            self._btn_gestures_top.setStyleSheet(
                "QPushButton { background: rgba(0, 229, 255, 0.18); color: #00e5ff; border: 1px solid #00e5ff; border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background: rgba(0, 229, 255, 0.25); color: #00e5ff; border: 1px solid #00e5ff; }"
            )

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        muted = bool(muted)
        if muted == self._muted and not wakeword:
            return
        self._muted = muted
        self.hud.muted = self._muted
        self._wakeword_listening = bool(muted)
        self._style_mute_btn()
        if hasattr(self, "_taskbar_waveform") and self._taskbar_waveform:
            self._taskbar_waveform.set_muted(self._muted)
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
            sound_mgr.play_listening_stop()
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")
            sound_mgr.play_listening_start()

    def _style_mute_btn(self):
        if not hasattr(self, "_mute_btn") or self._mute_btn is None:
            return
        if self._muted:
            self._mute_btn.setText("Muted")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1a1010; color: {C.RED};
                    border: 1px solid {C.RED}; border-radius: 16px;
                }}
            """)
        else:
            self._mute_btn.setText("Mic")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(16,16,16,235); color: {C.WHITE};
                    border: 1px solid {C.BORDER_B}; border-radius: 16px;
                }}
                QPushButton:hover {{ border: 1px solid {C.WHITE}; }}
            """)

    def _send(self, txt: str = ""):
        if not txt:
            txt = self._input.text().strip()
            self._input.clear()
        if not txt:
            return
        self.submit_command(txt)

    def submit_command(self, txt: str, source: str = "local"):
        txt = (txt or "").strip()
        if not txt:
            return
        self._chat_source_queue.append(source or "local")
        if hasattr(self, "_command_card"):
            preview = txt[:60] + ("…" if len(txt) > 60 else "")
            self._command_card.set_body(preview)
            self._command_card.hide()
        if hasattr(self, "_result_card"):
            self._result_card.set_body("Waiting for reply...")
            self._result_card.hide()
        self._restart_card_hide_timer()
        self._log_sig.emit(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt, source or "local"), daemon=True).start()

    def _on_log_text(self, text: str):
        self._log.append_log(text)
        raw = (text or "").strip()
        low = raw.lower()
        if hasattr(self, "_result_card") and low.startswith("you:"):
            user_msg = raw.split(":", 1)[1].strip()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event and user_msg:
                try:
                    self.on_chat_event({"role": "user", "text": user_msg, "source": source})
                except Exception:
                    pass
        if hasattr(self, "_result_card") and low.startswith("nexus core:"):
            reply = raw.split(":", 1)[1].strip()
            self._result_card.set_body(reply[:80] + ("…" if len(reply) > 80 else ""))
            self._result_card.hide()
            self._restart_card_hide_timer()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event and reply:
                try:
                    self.on_chat_event({"role": "assistant", "text": reply, "source": source})
                except Exception:
                    pass
            if self._chat_source_queue:
                self._chat_source_queue.popleft()
        elif hasattr(self, "_result_card") and low.startswith("err:"):
            self._result_card.set_body(raw.split(":", 1)[1].strip())
            self._result_card.hide()
            self._restart_card_hide_timer()
            source = self._chat_source_queue[0] if self._chat_source_queue else "local"
            if self.on_chat_event:
                try:
                    self.on_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip(), "source": source})
                except Exception:
                    pass
            if self._chat_source_queue:
                self._chat_source_queue.popleft()

    def _restart_card_hide_timer(self):
        if hasattr(self, "_card_hide_tmr"):
            self._card_hide_tmr.start(5000)

    def _hide_command_cards(self):
        if hasattr(self, "_command_card"):
            self._command_card.hide()
        if hasattr(self, "_result_card"):
            self._result_card.hide()
        if hasattr(self, "_hud_result_wing"):
            self._hud_result_wing.dismiss()
        if hasattr(self, "_hud_telemetry_wing"):
            self._hud_telemetry_wing.dismiss()

    def _apply_hud_operation(self, data: dict):
        if hasattr(self, "_hud_telemetry_wing"):
            self._hud_telemetry_wing.show_operation(
                title=data.get("title") or "OPERATION IN PROGRESS",
                step=data.get("step") or "Processing...",
                sources=data.get("sources") or [],
                tool=data.get("tool") or ""
            )

    def _apply_hud_deliverable(self, data: dict):
        if hasattr(self, "_hud_result_wing"):
            self._hud_result_wing.show_deliverable(
                title=data.get("title") or "MISSION DELIVERABLE",
                summary=data.get("summary") or "",
                bullets=data.get("bullets") or [],
                file_path=data.get("file_path"),
                kind=data.get("kind") or "result",
                actions=data.get("actions") or [],
                data=data.get("data") or {}
            )

    def _apply_daily_briefing(self, payload):
        action, data = payload if isinstance(payload, tuple) else ("show", payload)
        if action == "hide":
            if getattr(self, "_briefing_overlay", None):
                try:
                    self._briefing_overlay.hide()
                    self._briefing_overlay.deleteLater()
                except Exception:
                    pass
                self._briefing_overlay = None
            if hasattr(self, "_briefing_card"):
                self._briefing_card.hide()
            if hasattr(self, "_smart_devices_section"):
                self._smart_devices_section.show()
            return

        # Legacy label support if present
        if hasattr(self, "_briefing_text_lbl"):
            summary_txt = data if isinstance(data, str) else (data.get("spoken_narrative", "") if isinstance(data, dict) else str(data))
            clean_text = " ".join(str(summary_txt or "").split())
            self._briefing_text_lbl.setText(clean_text[:360] + ("..." if len(clean_text) > 360 else ""))

        # Holographic HUD card overlay
        if getattr(self, "_briefing_overlay", None):
            try:
                self._briefing_overlay.deleteLater()
            except Exception:
                pass
            self._briefing_overlay = None

        overlay = DailyBriefingOverlay(data, parent=self)
        overlay.closed.connect(lambda: setattr(self, "_briefing_overlay", None))
        self._briefing_overlay = overlay
        self._position_briefing_overlay()
        overlay.show()
        overlay.raise_()

        try:
            from sound_manager import sound_mgr
            sound_mgr.play_sfx("telemetry_chirp")
        except Exception:
            pass

    def _position_briefing_overlay(self):
        if not getattr(self, "_briefing_overlay", None):
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._briefing_overlay.width()) // 2)
        y = max(16, (geo.height() - self._briefing_overlay.height()) // 2)
        self._briefing_overlay.move(x, y)

    def _hide_daily_briefing_card(self):
        self._apply_daily_briefing(("hide", None))

    def _schedule_daily_briefing_hide(self):
        if getattr(self, "_briefing_overlay", None):
            self._briefing_overlay._remaining_secs = min(getattr(self._briefing_overlay, "_remaining_secs", 30), 10)

    def show_daily_briefing(self, text):
        self._briefing_sig.emit(("show", text))

    def hide_daily_briefing(self):
        self._briefing_sig.emit(("hide", None))

    def schedule_daily_briefing_hide(self):
        self._schedule_daily_briefing_hide()

    def show_confirm(self, title: str, detail: str = ""):
        self._confirm_sig.emit("show", title, detail)

    def hide_confirm(self):
        self._confirm_sig.emit("hide", "", "")

    def _apply_confirm_overlay(self, action: str, title: str = "", detail: str = ""):
        if action == "hide":
            if getattr(self, "_confirm_overlay", None):
                try:
                    self._confirm_overlay.deleteLater()
                except Exception:
                    pass
                self._confirm_overlay = None
            return

        if action == "show":
            if getattr(self, "_confirm_overlay", None):
                try:
                    self._confirm_overlay.deleteLater()
                except Exception:
                    pass
                self._confirm_overlay = None

            overlay = ConfirmationOverlay(title, detail, parent=self)
            overlay.answered.connect(self._on_confirm_answered)
            overlay.closed.connect(lambda: setattr(self, "_confirm_overlay", None))
            self._confirm_overlay = overlay
            self._position_confirm_overlay()
            overlay.show()
            overlay.raise_()

            try:
                from sound_manager import sound_mgr
                sound_mgr.play_sfx("telemetry_chirp")
            except Exception:
                pass

    def _apply_ultron_malfunction(self, payload: dict):
        action = (payload.get("action") or "show").lower()
        if action in ("close", "hide"):
            if getattr(self, "_ultron_dialog", None):
                try:
                    self._ultron_dialog.close()
                except Exception:
                    pass
                self._ultron_dialog = None
            return

        if getattr(self, "_ultron_dialog", None) is None or not self._ultron_dialog.isVisible():
            self._ultron_dialog = UltronMalfunctionDialog(payload, parent=None)
            screen = QApplication.primaryScreen().availableGeometry()
            self._ultron_dialog.adjustSize()
            x = max(24, screen.right() - self._ultron_dialog.width() - 28)
            y = screen.top() + 36
            self._ultron_dialog.move(x, y)
            self._ultron_dialog.show()
            self._ultron_dialog.raise_()
            self._ultron_dialog.activateWindow()
        else:
            self._ultron_dialog.update_content(payload)
            self._ultron_dialog.show()
            self._ultron_dialog.raise_()

    def _apply_circuit_overlay(self, circuit_data: dict):
        if self._circuit_overlay:
            self._circuit_overlay.deleteLater()
            self._circuit_overlay = None

        if hasattr(self, "_bg_widget") and self._bg_widget:
            self._bg_widget.pause_rendering()

        from core.circuit_hud import CircuitPopupOverlay

        parent = self.centralWidget()
        overlay = CircuitPopupOverlay(circuit_data or {}, parent=parent)
        def _on_circuit_closed():
            setattr(self, "_circuit_overlay", None)
            if hasattr(self, "_bg_widget") and self._bg_widget:
                self._bg_widget.resume_rendering()
        overlay.closed.connect(_on_circuit_closed)
        self._circuit_overlay = overlay
        overlay.move(max(8, (parent.width() - overlay.width()) // 2), max(8, (parent.height() - overlay.height()) // 2))
        overlay.show()
        overlay.raise_()

    def _apply_radar_overlay(self, radar_data: dict):
        if self._radar_overlay:
            self._radar_overlay.deleteLater()
            self._radar_overlay = None

        if hasattr(self, "_bg_widget") and self._bg_widget:
            self._bg_widget.pause_rendering()

        from core.radar_hud import RadarPopupOverlay

        parent = self.centralWidget()
        overlay = RadarPopupOverlay(radar_data or {}, parent=parent)
        def _on_radar_closed():
            setattr(self, "_radar_overlay", None)
            if hasattr(self, "_bg_widget") and self._bg_widget:
                self._bg_widget.resume_rendering()
        overlay.closed.connect(_on_radar_closed)
        self._radar_overlay = overlay
        overlay.move(max(8, (parent.width() - overlay.width()) // 2), max(8, (parent.height() - overlay.height()) // 2))
        overlay.show()
        overlay.raise_()

    def _apply_space_cleaner_overlay(self, data: dict = None):
        if hasattr(self, "_space_cleaner_overlay") and self._space_cleaner_overlay:
            self._space_cleaner_overlay.deleteLater()
            self._space_cleaner_overlay = None

        if hasattr(self, "_bg_widget") and self._bg_widget:
            self._bg_widget.pause_rendering()

        from core.space_cleaner_hud import SpaceCleanerPopupOverlay

        parent = self.centralWidget()
        overlay = SpaceCleanerPopupOverlay(parent=parent)
        def _on_sc_closed():
            setattr(self, "_space_cleaner_overlay", None)
            if hasattr(self, "_bg_widget") and self._bg_widget:
                self._bg_widget.resume_rendering()
        overlay.closed.connect(_on_sc_closed)
        self._space_cleaner_overlay = overlay
        overlay.move(max(8, (parent.width() - overlay.width()) // 2), max(8, (parent.height() - overlay.height()) // 2))
        overlay.show()
        overlay.raise_()

    def _apply_call_screening(self, payload: dict):
        payload = dict(payload or {})
        action = payload.get("action", "show")

        if action == "hide":
            if self._call_screening_dialog:
                self._call_screening_dialog.close()
            self._call_screening_dialog = None
            self._call_screening_transcript = None
            return

        if action == "transcript":
            if self._call_screening_transcript:
                speaker = str(payload.get("speaker", "Caller"))
                text = str(payload.get("text", ""))
                current = self._call_screening_transcript.text()
                self._call_screening_transcript.setText((current + "\n" if current else "") + f"{speaker}: {text}")
            return

        if self._call_screening_dialog:
            self._call_screening_dialog.close()

        dialog = QDialog(self)
        dialog.setWindowTitle("Nexus Core Call Screening")
        dialog.setModal(False)
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)
        caller = str(payload.get("caller", "Caller"))
        app_name = str(payload.get("app", "Phone / Call"))
        status = str(payload.get("status", "Screening call"))
        title = QLabel(f"{caller}  ·  {app_name}")
        title.setWordWrap(True)
        detail = QLabel(status)
        transcript = QLabel("")
        transcript.setWordWrap(True)
        transcript.setMinimumHeight(70)
        layout.addWidget(title)
        layout.addWidget(detail)
        layout.addWidget(transcript)

        buttons = QHBoxLayout()
        take_over = QPushButton("Take Over")
        hang_up = QPushButton("Hang Up")
        buttons.addWidget(take_over)
        buttons.addWidget(hang_up)
        layout.addLayout(buttons)
        take_over.clicked.connect(self._take_over_screened_call)
        hang_up.clicked.connect(self._hang_up_screened_call)

        self._call_screening_dialog = dialog
        self._call_screening_transcript = transcript
        dialog.finished.connect(lambda: setattr(self, "_call_screening_dialog", None))
        dialog.show()
        dialog.raise_()

    def _take_over_screened_call(self):
        from actions.call_assistant import take_over_active_call
        take_over_active_call()

    def _hang_up_screened_call(self):
        from actions.call_assistant import hang_up_active_call
        hang_up_active_call()

    def _on_confirm_answered(self, accepted: bool):
        try:
            from core import confirm as confirm_gate
            confirm_gate.resolve(accepted)
        except Exception:
            pass
        self._apply_confirm_overlay("hide", "", "")

    def _position_confirm_overlay(self):
        if not getattr(self, "_confirm_overlay", None):
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._confirm_overlay.width()) // 2)
        y = max(16, (geo.height() - self._confirm_overlay.height()) // 2)
        self._confirm_overlay.move(x, y)

    def show_memory_inspector(self):
        self._memory_overlay_sig.emit("show")

    def hide_memory_inspector(self):
        self._memory_overlay_sig.emit("hide")

    def _apply_memory_overlay(self, action: str):
        if action == "hide":
            if getattr(self, "_memory_overlay", None):
                try:
                    self._memory_overlay.deleteLater()
                except Exception:
                    pass
                self._memory_overlay = None
            return

        if action == "show":
            if getattr(self, "_memory_overlay", None):
                try:
                    self._memory_overlay.deleteLater()
                except Exception:
                    pass
                self._memory_overlay = None

            overlay = MemoryInspectorOverlay(parent=self)
            overlay.closed.connect(lambda: setattr(self, "_memory_overlay", None))
            self._memory_overlay = overlay
            self._position_memory_overlay()
            overlay.show()
            overlay.raise_()

    def _position_memory_overlay(self):
        if not getattr(self, "_memory_overlay", None):
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._memory_overlay.width()) // 2)
        y = max(16, (geo.height() - self._memory_overlay.height()) // 2)
        self._memory_overlay.move(x, y)

    def show_app(self):
        try:
            self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        except Exception:
            pass
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_remote_connect(self):
        if not self.on_remote_clicked:
            self._log_sig.emit("ERR: Mobile remote is not ready yet.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log_sig.emit("ERR: Mobile remote could not start. Install dashboard dependencies and try again.")
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else url
        manual = result[3] if len(result) >= 4 else url

        if self._remote_overlay is not None:
            try:
                self._remote_overlay.deleteLater()
            except Exception:
                pass
            self._remote_overlay = None

        overlay = RemoteKeyOverlay(url, key, auto, manual, parent=self)
        overlay.set_new_key_callback(self.on_remote_clicked)
        overlay.closed.connect(lambda: setattr(self, "_remote_overlay", None))
        self._remote_overlay = overlay
        self._position_remote_overlay()
        overlay.show()
        overlay.raise_()
        self._log_sig.emit(f"SYS: Mobile Connect ready at {manual}. Scan the QR code or enter key {key}.")

    def _position_remote_overlay(self):
        if not self._remote_overlay:
            return
        geo = self.geometry()
        x = max(16, (geo.width() - self._remote_overlay.width()) // 2)
        y = max(16, (geo.height() - self._remote_overlay.height()) // 2)
        self._remote_overlay.move(x, y)

    def notify_phone_connected(self):
        if self._remote_overlay is not None:
            self._remote_overlay.mark_connected()
        self._log_sig.emit("SYS: Phone connected to Nexus Core remote.")

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if hasattr(self, "_bg_widget") and hasattr(self._bg_widget, "set_pointer_norm"):
            w = max(1, self.width())
            h = max(1, self.height())
            pos = event.position() if hasattr(event, "position") else event.pos()
            nx = (pos.x() / w) * 2.0 - 1.0
            ny = -(pos.y() / h) * 2.0 + 1.0
            self._bg_widget.set_pointer_norm(nx, ny)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.minimized.emit()
            else:
                self.restored.emit()

    def _do_set_live_subtitles(self, speaker: str, text: str, is_interim: bool):
        speaker_upper = speaker.upper()
        clean_text = text.strip()
        if not clean_text:
            return

        # Check if speaker changed to avoid heavy stylesheet recompilation on every audio streaming token
        last_spk = getattr(self, "_last_sub_speaker", None)
        if last_spk != speaker_upper:
            self._last_sub_speaker = speaker_upper
            if hasattr(self, "_live_sub_speaker") and self._live_sub_speaker:
                self._live_sub_speaker.setText(f"● {speaker_upper}")
                if speaker_upper in ("YOU", "USER"):
                    self._live_sub_speaker.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
                elif speaker_upper in ("NEXUS", "AI", "MODEL"):
                    self._live_sub_speaker.setStyleSheet("color: #10b981; background: transparent; border: none;")
                else:
                    self._live_sub_speaker.setStyleSheet("color: #f59e0b; background: transparent; border: none;")

            if hasattr(self, "_desktop_sub_badge") and self._desktop_sub_badge:
                self._desktop_sub_badge.setText(f"● {speaker_upper}")
                if speaker_upper in ("YOU", "USER"):
                    self._desktop_sub_badge.setStyleSheet("""
                        color: #00e5ff;
                        background: rgba(0, 229, 255, 0.22);
                        border: 1px solid rgba(0, 229, 255, 0.60);
                        border-radius: 13px;
                        padding: 4px 12px;
                    """)
                elif speaker_upper in ("NEXUS", "AI", "MODEL"):
                    self._desktop_sub_badge.setStyleSheet("""
                        color: #10b981;
                        background: rgba(16, 185, 129, 0.22);
                        border: 1px solid rgba(16, 185, 129, 0.60);
                        border-radius: 13px;
                        padding: 4px 12px;
                    """)
                else:
                    self._desktop_sub_badge.setStyleSheet("""
                        color: #f59e0b;
                        background: rgba(245, 158, 11, 0.22);
                        border: 1px solid rgba(245, 158, 11, 0.60);
                        border-radius: 13px;
                        padding: 4px 12px;
                    """)

        # Fast flicker-free text update (< 0.1ms)
        if hasattr(self, "_live_sub_text") and self._live_sub_text:
            disp_short = clean_text if len(clean_text) <= 85 else clean_text[:82] + "..."
            self._live_sub_text.setText(disp_short)

        if hasattr(self, "_desktop_sub_text") and self._desktop_sub_text:
            disp_text = clean_text if len(clean_text) <= 125 else clean_text[:122] + "..."
            self._desktop_sub_text.setText(disp_text)

        if hasattr(self, "_desktop_subtitle_bar") and self._desktop_subtitle_bar and not self._desktop_subtitle_bar.isVisible():
            self._desktop_subtitle_bar.show()

        # Update input placeholder cleanly on completion
        if not is_interim and hasattr(self, "_input") and self._input and not self._input.hasFocus():
            if speaker_upper in ("YOU", "USER"):
                self._input.setPlaceholderText(f"🎤 Heard: \"{clean_text}\"")

        # Idle auto-reset timer (reset back to friendly prompt after 7 seconds of inactivity)
        if not is_interim:
            if not hasattr(self, "_sub_reset_timer") or self._sub_reset_timer is None:
                self._sub_reset_timer = QTimer(self)
                self._sub_reset_timer.setSingleShot(True)
                self._sub_reset_timer.timeout.connect(self._reset_desktop_subtitles)
            self._sub_reset_timer.start(7000)

    def _reset_desktop_subtitles(self):
        try:
            self._last_sub_speaker = None
            if hasattr(self, "_desktop_sub_badge") and self._desktop_sub_badge:
                self._desktop_sub_badge.setText("● LIVE VOICE")
                self._desktop_sub_badge.setStyleSheet("""
                    color: #00e5ff;
                    background: rgba(0, 229, 255, 0.18);
                    border: 1px solid rgba(0, 229, 255, 0.40);
                    border-radius: 13px;
                    padding: 4px 12px;
                """)
            if hasattr(self, "_desktop_sub_text") and self._desktop_sub_text:
                self._desktop_sub_text.setText("Listening for voice commands... (say 'Open Chrome' or ask anything)")
            if hasattr(self, "_input") and self._input and not self._input.hasFocus() and not self._input.text():
                self._input.setPlaceholderText("Ask Nexus Core anything... (or say \"Open Chrome\")")
        except Exception:
            pass

    def _on_audio_level_sig(self, level: float):
        if hasattr(self, "_bg_widget") and hasattr(self._bg_widget, "set_audio_level"):
            self._bg_widget.set_audio_level(level)
        if hasattr(self, "_chat_workspace") and hasattr(self._chat_workspace, "set_audio_level"):
            self._chat_workspace.set_audio_level(level)
        if hasattr(self, "_command_bar") and hasattr(self._command_bar, "set_audio_level"):
            self._command_bar.set_audio_level(level)
        if hasattr(self, "_taskbar_waveform") and self._taskbar_waveform:
            self._taskbar_waveform.set_audio_level(level)

    def set_audio_level(self, level: float):
        try:
            self._audio_level_sig.emit(float(level))
        except Exception:
            pass

    def _open_command_palette(self):
        """Opens the Holographic Omni-Command Palette."""
        if not hasattr(self, "_omni_palette") or self._omni_palette is None:
            self._omni_palette = OmniCommandPalette(commands=DEFAULT_PALETTE_COMMANDS, parent=self)
            self._omni_palette.command_executed.connect(self._handle_palette_command)
        screen = QApplication.primaryScreen().availableGeometry()
        self._omni_palette.move(
            max(20, (screen.width() - self._omni_palette.width()) // 2),
            max(40, (screen.height() - self._omni_palette.height()) // 3)
        )
        self._omni_palette.show()
        self._omni_palette.raise_()
        self._omni_palette.activateWindow()

    def _handle_palette_command(self, cmd: str):
        """Routes selected command from Omni-Command Palette to the proper system module."""
        if not cmd:
            return
        if cmd == "__action_toggle_globe__":
            if hasattr(self, "_toggle_globe_window"):
                self._toggle_globe_window()
            else:
                self._on_nav_dashboard()
        elif cmd == "__action_toggle_mute__":
            self._toggle_mute()
        elif cmd == "__action_clear_workspace__":
            self.clear_task_workspace()
        else:
            if hasattr(self, "on_text_command") and self.on_text_command:
                self.on_text_command(cmd)
            else:
                self._log.append_log(f"User: {cmd}")

    def _apply_state(self, state: str):
        if getattr(self, "_state", None) == state:
            return
        self._state = state
        if hasattr(self, "_bg_widget") and hasattr(self._bg_widget, "set_ai_state"):
            self._bg_widget.set_ai_state(state)
        if hasattr(self, "_chat_workspace") and hasattr(self._chat_workspace, "set_state"):
            self._chat_workspace.set_state(state)
        if hasattr(self, "_command_bar") and hasattr(self._command_bar, "set_state"):
            self._command_bar.set_state(state)
        elif hasattr(self, "centralWidget") and hasattr(self.centralWidget(), "set_ai_state"):
            self.centralWidget().set_ai_state(state)

        # Update top taskbar status badge
        if hasattr(self, "_status_badge"):
            badge_map = {
                "LISTENING":  ("◉ LISTENING",  "#00e5ff", "rgba(0, 229, 255, 0.4)",  "rgba(0, 229, 255, 0.08)"),
                "SPEAKING":   ("◈ SPEAKING",   "#00e5ff", "rgba(0, 229, 255, 0.5)",  "rgba(0, 229, 255, 0.12)"),
                "THINKING":   ("◒ THINKING",   "#ff9100", "rgba(255, 145, 0, 0.45)", "rgba(255, 145, 0, 0.08)"),
                "PROCESSING": ("◒ PROCESSING", "#ff9100", "rgba(255, 145, 0, 0.45)", "rgba(255, 145, 0, 0.08)"),
                "EXECUTING":  ("⚡ EXECUTING",  "#7c4dff", "rgba(124, 77, 255, 0.45)","rgba(124, 77, 255, 0.08)"),
                "WORKING":    ("⚡ WORKING",    "#7c4dff", "rgba(124, 77, 255, 0.45)","rgba(124, 77, 255, 0.08)"),
                "MUTED":      ("⊗ MUTED",      "#ff3b30", "rgba(255, 59, 48, 0.45)", "rgba(255, 59, 48, 0.08)"),
                "SCANNING":   ("◓ SCANNING",   "#37ff5f", "rgba(55, 255, 95, 0.45)", "rgba(55, 255, 95, 0.08)"),
            }
            lbl_txt, col, border, bg = badge_map.get(state, ("● ONLINE", "#00e5ff", "rgba(0, 229, 255, 0.25)", "rgba(12,14,18,220)"))
            self._status_badge.setText(lbl_txt)
            self._status_badge.setStyleSheet(
                f"color: {col}; background: {bg}; border: 1px solid {border}; border-radius: 8px; padding: 5px 12px;"
            )

        # Update command row input placeholder
        if hasattr(self, "_input"):
            ph_map = {
                "LISTENING": "Listening... (or type your command)",
                "SPEAKING": "Nexus Core is responding...",
                "THINKING": "Nexus is thinking...",
                "PROCESSING": "Processing request...",
                "EXECUTING": "Executing action...",
                "WORKING": "Working on it...",
                "MUTED": "Microphone muted — type command here...",
                "SCANNING": "Scanning display...",
            }
            self._input.setPlaceholderText(ph_map.get(state, "Ask Nexus Core anything..."))

        # Update chat workspace footer status
        if hasattr(self, "_inline_workspace") and hasattr(self._inline_workspace, "_footer_status"):
            foot_map = {
                "LISTENING": "● Listening for voice command...",
                "SPEAKING": "● Nexus is speaking...",
                "THINKING": "● Thinking...",
                "PROCESSING": "● Processing...",
                "EXECUTING": "● Executing system command...",
                "WORKING": "● Working on task...",
                "MUTED": "● Voice input muted",
                "SCANNING": "● Vision system active",
            }
            self._inline_workspace._footer_status.setText(foot_map.get(state, "Nexus Core is online"))

        if hasattr(self, "_status_chip"):
            chip_text = {
                "THINKING": "● WORKING",
                "SPEAKING": "● SPEAKING",
                "MUTED":    "● MUTED",
            }.get(state, "● ONLINE")
            self._status_chip.setText(chip_text)
            color = C.PRI if state == "MUTED" else C.GREEN if state in ("LISTENING", "SPEAKING") else C.WHITE
            border = C.PRI if state in ("MUTED", "THINKING") else "rgba(255,255,255,0.12)"
            self._status_chip.setStyleSheet(
                f"color: {color}; background: rgba(11,12,16,238); border: 1px solid {border}; border-radius: 999px; padding: 7px 14px;"
            )
        if hasattr(self, "_time_status_lbl"):
            status_text = {
                "THINKING": "Working",
                "SPEAKING": "Speaking",
                "MUTED": "Muted",
            }.get(state, "Online")
            self._time_status_lbl.setText(status_text)
            self._time_status_lbl.setStyleSheet(
                f"color: {C.GREEN if state in ('LISTENING', 'SPEAKING') else C.RED if state == 'MUTED' else C.WHITE}; background: transparent;"
            )
        if hasattr(self, "_task_card"):
            if state in ("THINKING", "PROCESSING", "EXECUTING", "WORKING"):
                self._task_card.set_task("Working on it...", "Nexus Core is processing your request.", 72)
            elif state == "SPEAKING":
                self._task_card.set_task("Responding...", "Nexus Core is speaking now.", 100)
            elif state == "MUTED":
                self._task_card.set_task("Microphone muted", "Voice input is paused.", 0)
            else:
                self._task_card.set_task("Ready", "Nexus Core is idle and ready.", 0)
        if hasattr(self, "_result_card"):
            if state in ("THINKING", "PROCESSING", "EXECUTING", "WORKING"):
                self._result_card.set_body("Action pending")
            elif state == "SPEAKING":
                self._result_card.set_body("Speaking now")
            elif state == "MUTED":
                self._result_card.set_body("Voice muted")
            else:
                self._result_card.set_body("Action completed")

    def _check_config(self) -> bool:
        saved = self._load_api_defaults()
        return any(str(saved.get(k, "")).strip() for k in _PROVIDER_KEY_FIELDS)

    def _apply_scan_state(self, enabled: bool, text: str = ""):
        if enabled:
            if self._scan_overlay is None:
                self._scan_overlay = ScanningOverlay()
            self._scan_overlay.show_fullscreen(text or "SCANNING SCREEN", "Analyzing display...")
        else:
            if self._scan_overlay is not None:
                self._scan_overlay.hide_overlay()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._scan_sig.emit(bool(enabled), text or "")

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._meeting_sig.emit({
            "enabled": bool(enabled),
            "title": title or "",
            "summary": summary or "",
            "answer": answer or "",
            "speech": speech or "",
        })

    def _on_screen_capture_requested(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QBuffer, QIODevice, Qt
        try:
            screen = QApplication.primaryScreen()
            if not screen:
                self._screen_capture_result = b""
            else:
                pixmap = screen.grabWindow(0)
                pixmap = pixmap.scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, 'JPG', 55)
                self._screen_capture_result = buffer.data().data()
        except Exception:
            self._screen_capture_result = b""
        finally:
            self._screen_capture_event.set()

    def capture_screen_threadsafe(self) -> bytes:
        print("[UI] capture_screen_threadsafe started")
        self._screen_capture_event.clear()
        self._screen_capture_sig.emit()
        self._screen_capture_event.wait(timeout=5.0)
        print(f"[UI] capture_screen_threadsafe finished, result {len(self._screen_capture_result) if self._screen_capture_result is not None else 'None'} bytes")
        return self._screen_capture_result

    def _apply_meeting_state(self, event: object):
        data = event if isinstance(event, dict) else {}
        enabled = bool(data.get("enabled"))
        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        answer = (data.get("answer") or "").strip()
        speech = (data.get("speech") or "").strip()

        if enabled:
            if self._meeting_overlay is None:
                self._meeting_overlay = MeetingOverlay()
                self._meeting_overlay.stop_requested.connect(self._request_stop_meeting)
                self._meeting_overlay.minimize_requested.connect(self._toggle_meeting_overlay)
                self._meeting_overlay.close_requested.connect(self._request_stop_meeting)
            self._meeting_overlay.set_content(
                title or "Meeting mode",
                summary or "Watching the meeting screen.",
                answer or "No question detected yet.",
                True,
                speech,
            )
            self._position_meeting_overlay()
            self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
            self._meeting_overlay.show()

    def _apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        target = getattr(self, "_task_card", None)
        if target is None:
            return
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            target.start_workspace(
                data.get("command") or "",
                data.get("plan") or [],
                data.get("source") or "local",
            )
        elif action == "update":
            target.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
        elif action == "finish":
            target.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                status=data.get("status") or "Task completed.",
                percent=int(data.get("percent") or 100),
            )
        elif action == "clear":
            target.clear_workspace()

    def _on_discord_status_update(self, message: str):
        if not message:
            return
        if hasattr(self, "_discord_status_lbl"):
            note = message.strip()
            self._refresh_discord_card(note)
            if self._meeting_overlay is not None:
                try:
                    self._meeting_overlay.raise_()
                except Exception:
                    pass
        else:
            if self._meeting_overlay is not None:
                self._meeting_overlay.hide()
            self._meeting_overlay_collapsed = False

    def _request_stop_meeting(self):
        if self.on_attention_action:
            try:
                self.on_attention_action({"kind": "meeting", "app": "Meeting mode"}, "stop")
            except Exception:
                pass

    def _toggle_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        self._meeting_overlay_collapsed = not self._meeting_overlay_collapsed
        self._meeting_overlay.set_collapsed(self._meeting_overlay_collapsed)
        self._position_meeting_overlay()
        if not self._meeting_overlay.isVisible():
            self._meeting_overlay.show()
        self._meeting_overlay.raise_()

    def _position_meeting_overlay(self):
        if self._meeting_overlay is None:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 12
        h = self._meeting_overlay.height()
        w = min(980, max(780, screen.width() - margin * 2))
        x = screen.left() + (screen.width() - w) // 2
        y = screen.top() + margin
        self._meeting_overlay.setGeometry(x, y, w, h)

    def _show_attention_alert(self, event: object):
        data = event if isinstance(event, dict) else {}
        if self._incoming_alert is not None:
            try:
                self._incoming_alert.close()
            except Exception:
                pass
            self._incoming_alert = None

        dlg = IncomingAlertDialog(data, None)
        dlg.decision.connect(lambda decision, ev=data: self._attention_choice(ev, decision))

        if (data.get("kind") or "").strip().lower() == "call":
            self.show_app()

        screen = QApplication.primaryScreen().availableGeometry()
        margin = 16
        dlg.adjustSize()
        x = screen.right() - dlg.width() - margin
        y = screen.top() + margin
        dlg.move(x, y)
        dlg.show()
        dlg.raise_()
        self._incoming_alert = dlg

    def _attention_choice(self, event: dict, decision: str):
        if self.on_attention_action:
            try:
                self.on_attention_action(event, decision)
            except Exception:
                pass
        self._incoming_alert = None

    def _show_setup(self, defaults: dict | None = None):
        try:
            if hasattr(self, '_floating_gesture_card'):
                self._floating_gesture_card.hide()
            if self._overlay:
                self._overlay.hide()
                self._overlay.deleteLater()
                self._overlay = None
            
            # Maximize the main window for the cinematic experience
            self.showMaximized()
            
            ov = SetupOverlay(self.centralWidget(), defaults=defaults or self._load_api_defaults())
            cw = self.centralWidget()
            ov.setGeometry(0, 0, cw.width(), cw.height())
            ov.done.connect(self._on_setup_done)
            ov.show()
            ov.raise_()
            ov.activateWindow()
            self._overlay = ov
        except Exception as e:
            import traceback
            with open('setup_crash.log', 'w') as err_f:
                err_f.write(traceback.format_exc())
            raise


    # Change signature:
    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        try:
            existing = self._load_app_settings()
            existing.update({
                "gemini_api_key":     key,
                "openrouter_api_key": or_key,
                "os_system":          os_name,
            })
            self._save_app_settings(existing)
            self._ready = True
            self._api_ready = True
            if self._overlay:
                self._overlay.hide()
                self._overlay.deleteLater()
                self._overlay = None
            if hasattr(self, '_floating_gesture_card'):
                self._floating_gesture_card.show()
            self.showNormal()
            self._apply_state("LISTENING")
            self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. Nexus Core online.")
        except Exception as e:
            self._log.append_log(f"ERR: setup failed: {e}")
            traceback.print_exc()

    def _build_center_panel_modern(self, face_path: str) -> QWidget:
        w = QWidget()
        w.setObjectName("CenterStage")
        w.setStyleSheet("QWidget#CenterStage { background: transparent; border-left: none; border-right: none; }")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 22, 28, 0)
        lay.setSpacing(14)

        stage_frame = QFrame()
        stage_frame.setObjectName("StageFrame")
        stage_frame.setStyleSheet("QFrame#StageFrame { background: transparent; border: none; }")
        stage = QVBoxLayout(stage_frame)
        stage.setContentsMargins(26, 22, 26, 0)
        stage.setSpacing(14)
        lay.addWidget(stage_frame, stretch=1)

        # Internal labels kept as hidden placeholders for safety
        self._hidden_legacy_container = QWidget(self)
        self._hidden_legacy_container.setObjectName("HiddenLegacyContainer")
        self._hidden_legacy_container.hide()

        self._core_lbl = QLabel(self._hidden_legacy_container)
        self._core_sub_lbl = QLabel(self._hidden_legacy_container)
        self._core_status_lbl = QLabel(self._hidden_legacy_container)
        self._clock_lbl = QLabel(self._hidden_legacy_container)
        self._date_lbl = QLabel(self._hidden_legacy_container)
        self._time_status_lbl = QLabel(self._hidden_legacy_container)
        self._cpu_lbl = QLabel(self._hidden_legacy_container)
        self._ram_lbl = QLabel(self._hidden_legacy_container)
        self._status_chip = QLabel(self._hidden_legacy_container)
        self._smart_devices_section = SmartDevicesSection(self._hidden_legacy_container)
        self._smart_devices_section.hide()
        self._briefing_card = QFrame(self._hidden_legacy_container)
        self._briefing_card.hide()
        self._briefing_text_lbl = QLabel(self._hidden_legacy_container)
        self._developer_card = QFrame(self._hidden_legacy_container)
        self._developer_card.hide()
        self._developer_status_lbl = QLabel(self._hidden_legacy_container)

        self._hud_result_wing = BrahmaResultWing(self)
        self._hud_telemetry_wing = BrahmaTelemetryWing(self)
        self._command_card = self._hud_result_wing
        self._result_card = self._hud_telemetry_wing

        class _HudShim:
            def __init__(self):
                self.state = "ONLINE"
                self.speaking = False
                self.listening = False
                self.muted = False
            def set_state(self, s): self.state = s
            def set_audio_level(self, lvl): pass
            def feed_level(self, lvl): pass
            def update(self): pass
            def repaint(self): pass
            def show(self): pass
            def hide(self): pass
            def isVisible(self): return False
            def setVisible(self, v): pass
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        self.hud = _HudShim()

        command_row = QHBoxLayout()
        command_row.setContentsMargins(6, 0, 6, 0)
        command_row.setSpacing(12)
        command_row.addWidget(self._hud_result_wing, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        command_row.addStretch(1)
        command_row.addWidget(self._hud_telemetry_wing, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        stage.addLayout(command_row, stretch=1)

        self._command_panel = QWidget()
        self._command_panel.setStyleSheet("background: transparent;")
        cmd_lay = QVBoxLayout(self._command_panel)
        cmd_lay.setContentsMargins(0, 0, 0, 16)
        cmd_lay.setSpacing(10)
        # Central Live Subtitle Banner (Directly below central 3D neural orb / waveform)
        self._desktop_subtitle_bar = QFrame()
        self._desktop_subtitle_bar.setObjectName("DesktopSubtitleBar")
        self._desktop_subtitle_bar.setMinimumWidth(320)
        self._desktop_subtitle_bar.setMaximumWidth(840)
        self._desktop_subtitle_bar.setFixedHeight(50)
        self._desktop_subtitle_bar.setStyleSheet("""
            QFrame#DesktopSubtitleBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(8, 14, 26, 0.92),
                    stop:0.5 rgba(14, 24, 42, 0.95),
                    stop:1 rgba(8, 14, 26, 0.92));
                border: 1.5px solid rgba(0, 229, 255, 0.65);
                border-radius: 25px;
            }
        """)
        sub_layout = QHBoxLayout(self._desktop_subtitle_bar)
        sub_layout.setContentsMargins(18, 4, 18, 4)
        sub_layout.setSpacing(12)

        self._desktop_sub_badge = QLabel("● LIVE VOICE")
        self._desktop_sub_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._desktop_sub_badge.setStyleSheet("""
            color: #00e5ff;
            background: rgba(0, 229, 255, 0.18);
            border: 1px solid rgba(0, 229, 255, 0.50);
            border-radius: 13px;
            padding: 4px 12px;
        """)
        sub_layout.addWidget(self._desktop_sub_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self._desktop_sub_text = QLabel("Listening for voice commands... (say 'Open Chrome' or ask anything)")
        self._desktop_sub_text.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        self._desktop_sub_text.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        self._desktop_sub_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        sub_layout.addWidget(self._desktop_sub_text, 1, Qt.AlignmentFlag.AlignVCenter)

        sub_wrapper = QHBoxLayout()
        sub_wrapper.setContentsMargins(0, 0, 0, 4)
        sub_wrapper.addStretch(1)
        sub_wrapper.addWidget(self._desktop_subtitle_bar, 0)
        sub_wrapper.addStretch(1)
        cmd_lay.addLayout(sub_wrapper)

        cmd_lay.addLayout(self._build_command_row())
        stage.addWidget(self._command_panel)

        self._home_page = BrahmaHomePage()
        self._devices_page = NexusConnectDevicesPage(self)
        self._center_stack = QStackedWidget()
        self._center_stack.setStyleSheet("background: transparent; border: none;")
        self._center_stack.addWidget(w)
        self._center_stack.addWidget(self._home_page)
        self._center_stack.addWidget(self._devices_page)
        self._settings_page = SystemConnectivityPage()
        self._center_stack.addWidget(self._settings_page)
        
        self._settings_hub_page = SettingsHubPage(lambda idx: self._center_stack.setCurrentIndex(idx))
        self._center_stack.addWidget(self._settings_hub_page)

        self._center_stack.setCurrentIndex(0)
        return self._center_stack

    def _build_right_panel_modern(self) -> QWidget:
        w = QWidget()
        self._right_panel = w
        w.setObjectName("ModularRightSidebar")
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(
            f"QWidget#ModularRightSidebar {{ "
            f"  background: rgba(8, 10, 15, 0.22); "
            f"  border-left: 1px solid rgba(0, 229, 255, 0.25); "
            f"}}"
        )
        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(14, 12, 14, 12)
        root_lay.setSpacing(10)

        # Modular Header
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(2, 2, 2, 2)
        header_bar.setSpacing(8)

        pulse_dot = QLabel("●")
        pulse_dot.setFont(QFont("Segoe UI", 10))
        pulse_dot.setStyleSheet("color: #37ff5f; background: transparent;")
        header_bar.addWidget(pulse_dot)

        header_title = QLabel("NEXUS CHAT")
        header_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header_title.setStyleSheet(f"color: {C.WHITE}; background: transparent; letter-spacing: 1px;")
        header_bar.addWidget(header_title)

        header_bar.addStretch(1)

        self._new_chat_btn = QPushButton("+ New")
        self._new_chat_btn.setFixedSize(54, 28)
        self._new_chat_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_chat_btn.setToolTip("Start a new chat session")
        self._new_chat_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(0, 229, 255, 0.10); color: {C.PRI}; border: 1px solid rgba(0, 229, 255, 0.30); border-radius: 6px; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background: rgba(0, 229, 255, 0.22); color: #FFFFFF; border-color: {C.PRI}; }}"
        )
        self._new_chat_btn.clicked.connect(lambda: self._inline_workspace.new_conversation() if hasattr(self, "_inline_workspace") else None)
        header_bar.addWidget(self._new_chat_btn)

        self._right_toggle_btn = QPushButton("❯")
        self._right_toggle_btn.setFixedSize(28, 28)
        self._right_toggle_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._right_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._right_toggle_btn.setToolTip("Collapse Chat Sidebar")
        self._right_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.06); color: {C.WHITE}; border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI}; background: rgba(0, 229, 255,0.12); }}"
        )
        self._right_toggle_btn.clicked.connect(self._toggle_right_sidebar)
        header_bar.addWidget(self._right_toggle_btn)
        root_lay.addLayout(header_bar)

        self._right_stack = QStackedWidget()
        self._right_stack.setStyleSheet("background: transparent; border: none;")

        self._right_content = QWidget()
        self._right_content.setStyleSheet("background: transparent;")
        chat_lay = QVBoxLayout(self._right_content)
        chat_lay.setContentsMargins(0, 4, 0, 0)
        chat_lay.setSpacing(8)

        self._inline_workspace = InlineChatWorkspace()
        self._inline_workspace.attach_requested.connect(self._browse_attachment)
        self._inline_workspace.mic_requested.connect(self._toggle_mute)
        self._inline_workspace.command_submitted.connect(self._send)
        self._log = self._inline_workspace
        chat_lay.addWidget(self._inline_workspace, stretch=1)

        self._settings_sidebar = SystemConnectivitySidebar()
        self._empty_right = QWidget()
        self._empty_right.setStyleSheet("background: transparent;")

        self._right_stack.addWidget(self._right_content)
        self._right_stack.addWidget(self._settings_sidebar)
        self._right_stack.addWidget(self._empty_right)
        root_lay.addWidget(self._right_stack, stretch=1)

        self._apply_sidebar_state()
        return w

    def _build_command_row(self) -> QHBoxLayout:
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(84)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.setStyleSheet(
            f"""
            QFrame {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 229, 255, 0.20);
                border-radius: 35px;
            }}
            """
        )
        try:
            shadow = QGraphicsDropShadowEffect(bar)
            shadow.setBlurRadius(24)
            shadow.setColor(QColor(0, 229, 255, 45))
            shadow.setOffset(0, 0)
            bar.setGraphicsEffect(shadow)
        except Exception:
            pass
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(12)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask Nexus Core anything...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setFixedHeight(50)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {C.WHITE};
                border: none;
                padding: 0 14px;
                selection-background-color: rgba(0, 229, 255, 0.25);
            }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)

        icon_button_style = f"""
            QPushButton {{
                background: transparent;
                color: {C.WHITE};
                border: none;
                border-radius: 22px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.15);
                color: {C.PRI};
            }}
            QPushButton:pressed {{
                background: rgba(0, 229, 255, 0.30);
            }}
        """

        attach = QPushButton()
        attach.setFixedSize(44, 44)
        attach.setCursor(Qt.CursorShape.PointingHandCursor)
        attach.setToolTip("Attach file")
        attach.setIcon(QIcon(_icon_pixmap("attach", 20)))
        attach.setIconSize(QSize(20, 20))
        attach.setStyleSheet(icon_button_style)
        attach.clicked.connect(self._browse_attachment)
        row.addWidget(attach)

        mic = QPushButton()
        mic.setFixedSize(44, 44)
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setToolTip("Microphone")
        mic.setIcon(QIcon(_icon_pixmap("mic", 20)))
        mic.setIconSize(QSize(20, 20))
        mic.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255, 0.10);
                color: {C.PRI};
                border: 1px solid rgba(0, 229, 255, 0.30);
                border-radius: 22px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.25);
                border: 1px solid rgba(0, 229, 255, 0.60);
            }}
            QPushButton:pressed {{
                background: rgba(0, 229, 255, 0.40);
            }}
        """)
        mic.clicked.connect(self._toggle_mute)
        row.addWidget(mic)

        self._send_btn = QPushButton()
        self._send_btn.setFixedSize(44, 44)
        self._send_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setIcon(QIcon(_icon_pixmap("send", 20)))
        self._send_btn.setIconSize(QSize(20, 20))
        self._send_btn.setStyleSheet(icon_button_style)
        self._send_btn.clicked.connect(self._send)
        row.addWidget(self._send_btn)

        wrapper.addWidget(bar)
        return wrapper

