"""UI components

Split from ui.py. The namespace bridge preserves existing UI integrations
while this area is incrementally decoupled into explicit dependencies.
"""
import ui as _ui
globals().update({name: value for name, value in vars(_ui).items() if not name.startswith("__")})

class VoiceWaveformVisualizer(QWidget):
    """
    Live Voice-Reactive Waveform Visualizer.
    Draws dynamic, glowing equalizer bars pulsing with microphone & TTS audio levels.
    """
    def __init__(self, bars: int = 14, parent=None):
        super().__init__(parent)
        self._bar_count = bars
        self._audio_level = 0.0
        self._target_level = 0.0
        self._phase = 0.0
        self._muted = False
        self.setFixedSize(bars * 5 + 8, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_audio_level(self, level: float):
        self._target_level = max(0.0, min(1.0, float(level)))

    def set_muted(self, muted: bool):
        self._muted = bool(muted)
        self.update()

    def _tick(self):
        self._phase += 0.14
        self._audio_level += (self._target_level - self._audio_level) * 0.25
        self._target_level = max(0.0, self._target_level - 0.03)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = 3.0
        spacing = 2.0
        total_w = self._bar_count * (bar_w + spacing) - spacing
        start_x = (w - total_w) / 2.0

        for i in range(self._bar_count):
            harmonic = math.sin(self._phase + i * 0.6) * 0.45 + 0.55
            harmonic2 = math.cos(self._phase * 0.75 + i * 0.35) * 0.3 + 0.7

            idle_h = 3.0 + harmonic * 2.0
            amp = self._audio_level * (h - 4.0) * harmonic2
            bar_h = min(float(h - 2), idle_h + amp)
            if self._muted:
                bar_h = 2.0

            x = start_x + i * (bar_w + spacing)
            y = (h - bar_h) / 2.0

            if self._muted:
                color = QColor("#ff3b30")
                color.setAlpha(180)
            else:
                intensity = min(1.0, 0.45 + self._audio_level * 0.55)
                color = QColor("#00e5ff" if i % 2 == 0 else "#80ffff")
                color.setAlpha(int(240 * intensity))

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)

        painter.end()


class CommandBar(QWidget):
    submitted = pyqtSignal(str)
    attach_clicked = pyqtSignal()
    mic_clicked = pyqtSignal()
    developer_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("CommandBar")
        self.setFixedSize(580, 48)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("CommandBarFrame")
        frame.setStyleSheet(f"""
            QFrame#CommandBarFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(6, 6, 10, 252),
                    stop:0.3 rgba(12, 11, 16, 252),
                    stop:0.7 rgba(12, 11, 16, 252),
                    stop:1 rgba(6, 6, 10, 252));
                border: 1px solid rgba(0, 229, 255, 0.22);
                border-radius: 20px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        # Nexus Core mini logo
        logo_frame = QFrame()
        logo_frame.setFixedSize(32, 32)
        logo_frame.setStyleSheet("""
            QFrame {
                background: rgba(0, 229, 255, 0.06);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 16px;
            }
        """)
        logo_lay = QVBoxLayout(logo_frame)
        logo_lay.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("\u092C\u094D\u0930")  # ब्र (short Hindi)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setFont(QFont("Nirmala UI", 9, QFont.Weight.Bold))
        logo_lbl.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        logo_lay.addWidget(logo_lbl)
        lay.addWidget(logo_frame)

        # Input field
        self._input = QLineEdit()
        self._input.setPlaceholderText("Tell Nexus Core what to do...")
        self._input.setFont(QFont("Segoe UI", 9))
        self._input.setFixedHeight(32)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 16px;
                padding: 0 14px;
                selection-background-color: rgba(0, 229, 255, 0.25);
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0, 229, 255, 0.45);
                background: rgba(0, 229, 255, 0.03);
            }}
        """)
        self._input.returnPressed.connect(self._submit)
        lay.addWidget(self._input, stretch=1)

        # Action buttons container
        btn_style_ghost = f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.03);
                color: rgba(255, 255, 255, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.12);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.4);
            }}
        """

        attach = QPushButton()
        attach.setFixedSize(28, 28)
        attach.setCursor(Qt.CursorShape.PointingHandCursor)
        attach.setToolTip("Attach file")
        attach.setIcon(QIcon(_icon_pixmap("attach", 13)))
        attach.setIconSize(QSize(13, 13))
        attach.setStyleSheet(btn_style_ghost)
        attach.clicked.connect(self.attach_clicked.emit)
        lay.addWidget(attach)

        mic = QPushButton()
        mic.setFixedSize(28, 28)
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setToolTip("Voice input")
        mic.setIcon(QIcon(_icon_pixmap("mic", 13)))
        mic.setIconSize(QSize(13, 13))
        mic.setStyleSheet(btn_style_ghost)
        mic.clicked.connect(self.mic_clicked.emit)
        lay.addWidget(mic)

        dev = QPushButton("DEV")
        dev.setFixedSize(40, 28)
        dev.setCursor(Qt.CursorShape.PointingHandCursor)
        dev.setToolTip("Developer mode")
        dev.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255, 0.06);
                color: rgba(0, 229, 255, 0.7);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 14px;
                font: 700 8px 'Segoe UI';
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.5);
            }}
        """)
        dev.clicked.connect(self.developer_clicked.emit)
        lay.addWidget(dev)

        # Send button — golden accent
        send = QPushButton()
        send.setFixedSize(32, 32)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setToolTip("Send")
        send.setIcon(QIcon(_icon_pixmap("send", 14)))
        send.setIconSize(QSize(14, 14))
        send.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 229, 255, 0.12);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 19px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.25);
                border: 1px solid #00e5ff;
            }}
        """)
        # Live voice waveform visualizer
        self._waveform = VoiceWaveformVisualizer(bars=10, parent=self)
        lay.addWidget(self._waveform)

        send.clicked.connect(self._submit)
        lay.addWidget(send)

        root.addWidget(frame)

    def show_near(self, anchor: QWidget):
        screen = QApplication.primaryScreen().availableGeometry()
        geo = anchor.geometry()
        x = geo.center().x() - (self.width() // 2)
        y = geo.bottom() + 14
        x = max(screen.left() + 12, min(x, screen.right() - self.width() - 12))
        y = max(screen.top() + 12, min(y, screen.bottom() - self.height() - 12))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()
        self._input.selectAll()

    def hideEvent(self, event):
        super().hideEvent(event)

    def _submit(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self.submitted.emit(txt)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def set_audio_level(self, level: float):
        if hasattr(self, "_waveform") and self._waveform:
            self._waveform.set_audio_level(level)

    def set_muted(self, muted: bool):
        if hasattr(self, "_waveform") and self._waveform:
            self._waveform.set_muted(muted)

    def set_state(self, state: str):
        if hasattr(self, "_waveform") and self._waveform:
            self._waveform.set_muted(state == "MUTED")


DEFAULT_PALETTE_COMMANDS = [
    {
        "id": "snapshot_ws",
        "title": "Snapshot Workspace",
        "desc": "Capture active browser research tabs, open apps, and windows into a FlowState restore point",
        "icon": "⚡",
        "badge": "FlowState",
        "cmd": "snapshot workspace",
    },
    {
        "id": "switch_ws",
        "title": "Restore / Switch Workspace",
        "desc": "Restore a previously saved FlowState workspace restoration point",
        "icon": "⏱️",
        "badge": "FlowState",
        "cmd": "switch workspace",
    },
    {
        "id": "ultron_heal",
        "title": "Ultron Autonomous Diagnostics",
        "desc": "Inspect auto-heal sentry, patch history, AST sandbox, and runtime health",
        "icon": "🛡️",
        "badge": "Ultron",
        "cmd": "auto heal status",
    },
    {
        "id": "trigger_test_bug",
        "title": "Trigger Autonomous Bug Test",
        "desc": "Simulate a live runtime malfunction and witness Ultron self-repair in real time",
        "icon": "🧪",
        "badge": "Ultron",
        "cmd": "trigger test bug",
    },
    {
        "id": "toggle_globe",
        "title": "Planetary 3D Globe & Earth",
        "desc": "Launch holographic 3D Earth and street-level intelligence interface",
        "icon": "🌐",
        "badge": "Navigation",
        "cmd": "__action_toggle_globe__",
    },
    {
        "id": "sys_diag",
        "title": "System Performance Report",
        "desc": "Retrieve real-time CPU, RAM, GPU, network, and battery diagnostics",
        "icon": "📊",
        "badge": "System",
        "cmd": "system diagnostics report",
    },
    {
        "id": "screen_ai",
        "title": "Multimodal Vision Screen Scan",
        "desc": "Capture desktop screen and process active windows with multimodal vision",
        "icon": "🖥️",
        "badge": "Vision",
        "cmd": "process screen",
    },
    {
        "id": "toggle_mute",
        "title": "Toggle Microphone / Voice Mute",
        "desc": "Mute or unmute the continuous microphone audio listener",
        "icon": "🎙️",
        "badge": "Audio",
        "cmd": "__action_toggle_mute__",
    },
    {
        "id": "study_guard",
        "title": "Study Guard Attention Monitor",
        "desc": "Monitor study sessions, posture, and detect productivity distractions",
        "icon": "📚",
        "badge": "Focus",
        "cmd": "study guard status",
    },
    {
        "id": "show_rules",
        "title": "Learned Behavioral Directives",
        "desc": "List autonomous rules learned through conversational self-improvement",
        "icon": "🧠",
        "badge": "Memory",
        "cmd": "list rules",
    },
    {
        "id": "clear_workspace",
        "title": "Reset HUD Task Workspace",
        "desc": "Clear active operation telemetry and reset holographic deliverable wings",
        "icon": "🧹",
        "badge": "Workspace",
        "cmd": "__action_clear_workspace__",
    },
]


class OmniCommandPalette(QDialog):
    """
    Holographic Omni-Command Palette (Spotlight / Raycast Style).
    Activated with Ctrl+K or Ctrl+Space.
    Instant fuzzy search across tools, actions, smart home devices, and workspace snapshots.
    """
    command_executed = pyqtSignal(str)

    def __init__(self, commands: list[dict] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("OmniCommandPalette")
        self.setFixedWidth(640)
        self.setFixedHeight(480)

        self._all_commands = commands or DEFAULT_PALETTE_COMMANDS
        self._filtered_commands = list(self._all_commands)
        self._selected_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName("OmniPaletteFrame")
        self._frame.setStyleSheet("""
            QFrame#OmniPaletteFrame {
                background: rgba(10, 12, 18, 252);
                border: 1.5px solid rgba(0, 229, 255, 0.45);
                border-radius: 16px;
            }
        """)
        root.addWidget(self._frame)

        lay = QVBoxLayout(self._frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        # 1. Search Bar Header
        search_box = QHBoxLayout()
        search_box.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setFont(QFont("Segoe UI Emoji", 13))
        search_icon.setStyleSheet("color: #00e5ff; background: transparent;")
        search_box.addWidget(search_icon)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Type a command, tool, or prompt... (e.g., 'snapshot', 'ultron', 'globe', 'heal')")
        self._search_input.setFont(QFont("Segoe UI", 11))
        self._search_input.setFixedHeight(36)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #ffffff;
                border: none;
                padding: 0 4px;
                selection-background-color: rgba(0, 229, 255, 0.35);
            }
        """)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.returnPressed.connect(self._on_submit_selected)
        search_box.addWidget(self._search_input, 1)

        esc_badge = QLabel("ESC to exit")
        esc_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        esc_badge.setStyleSheet("""
            color: rgba(255, 255, 255, 0.45);
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            padding: 3px 8px;
        """)
        search_box.addWidget(esc_badge)
        lay.addLayout(search_box)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(0, 229, 255, 0.18);")
        lay.addWidget(divider)

        # 2. Quick Action Chips Row
        chips_lay = QHBoxLayout()
        chips_lay.setSpacing(6)
        chips = [
            ("⚡ Snapshot", "snapshot workspace"),
            ("🛡️ Ultron Status", "auto heal status"),
            ("🌐 3D Globe", "__action_toggle_globe__"),
            ("🎙️ Toggle Mic", "__action_toggle_mute__"),
            ("📊 Diagnostics", "system diagnostics report"),
            ("🧪 Test Bug", "trigger test bug"),
        ]
        for chip_title, chip_cmd in chips:
            btn = QPushButton(chip_title)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 229, 255, 0.08);
                    color: #00e5ff;
                    border: 1px solid rgba(0, 229, 255, 0.22);
                    border-radius: 12px;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.22);
                    border: 1px solid #00e5ff;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda _, c=chip_cmd: self._run_command(c))
            chips_lay.addWidget(btn)
        chips_lay.addStretch(1)
        lay.addLayout(chips_lay)

        # 3. Scrollable Results List
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(10, 12, 18, 0.6);
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 229, 255, 0.3);
                border-radius: 3px;
            }
        """)
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 4, 0, 4)
        self._list_lay.setSpacing(4)
        self._scroll.setWidget(self._list_container)
        lay.addWidget(self._scroll, 1)

        # 4. Footer Hint
        foot = QHBoxLayout()
        hint = QLabel("↑ ↓ to navigate   •   ENTER to select   •   ESC to dismiss")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.35); background: transparent;")
        foot.addWidget(hint)
        foot.addStretch(1)
        brand = QLabel("NEXUS EVO OMNI-BAR")
        brand.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        brand.setStyleSheet("color: #00e5ff; background: transparent; letter-spacing: 1px;")
        foot.addWidget(brand)
        lay.addLayout(foot)

        self._render_items()

    def showEvent(self, event):
        super().showEvent(event)
        self._search_input.clear()
        self._search_input.setFocus()
        self._selected_index = 0
        self._on_search_text_changed("")

    def _on_search_text_changed(self, text: str):
        query = (text or "").lower().strip()
        if not query:
            self._filtered_commands = list(self._all_commands)
        else:
            matches = []
            for item in self._all_commands:
                title = item.get("title", "").lower()
                desc = item.get("desc", "").lower()
                badge = item.get("badge", "").lower()
                cmd = item.get("cmd", "").lower()
                if query in title or query in desc or query in badge or query in cmd:
                    matches.append(item)
            matches.append({
                "id": "custom_query",
                "title": f'Ask Nexus: "{text.strip()}"',
                "desc": "Submit prompt directly to Nexus AI agent",
                "icon": "💬",
                "badge": "Query",
                "cmd": text.strip(),
            })
            self._filtered_commands = matches

        self._selected_index = 0
        self._render_items()

    def _render_items(self):
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, cmd_item in enumerate(self._filtered_commands):
            is_selected = (idx == self._selected_index)
            btn = QFrame()
            btn.setObjectName("PaletteItem")
            border = "rgba(0, 229, 255, 0.50)" if is_selected else "rgba(255, 255, 255, 0.05)"
            bg = "rgba(0, 229, 255, 0.12)" if is_selected else "rgba(18, 22, 30, 160)"
            btn.setStyleSheet(f"""
                QFrame#PaletteItem {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 10px;
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            i_lay = QHBoxLayout(btn)
            i_lay.setContentsMargins(12, 8, 12, 8)
            i_lay.setSpacing(10)

            icon_lbl = QLabel(cmd_item.get("icon", "⚡"))
            icon_lbl.setFont(QFont("Segoe UI Emoji", 12))
            icon_lbl.setStyleSheet("background: transparent;")
            i_lay.addWidget(icon_lbl)

            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            title_lbl = QLabel(cmd_item.get("title", ""))
            title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            title_lbl.setStyleSheet(f"color: {'#ffffff' if is_selected else '#e2e8f0'}; background: transparent;")
            text_box.addWidget(title_lbl)

            desc_lbl = QLabel(cmd_item.get("desc", ""))
            desc_lbl.setFont(QFont("Segoe UI", 8))
            desc_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.50); background: transparent;")
            text_box.addWidget(desc_lbl)
            i_lay.addLayout(text_box, 1)

            badge_lbl = QLabel(cmd_item.get("badge", "Action"))
            badge_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            badge_lbl.setStyleSheet("""
                color: #00e5ff;
                background: rgba(0, 229, 255, 0.10);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            i_lay.addWidget(badge_lbl)

            cmd_val = cmd_item.get("cmd", "")
            btn.mousePressEvent = lambda _, c=cmd_val: self._run_command(c)
            self._list_lay.addWidget(btn)

    def _run_command(self, cmd: str):
        if cmd:
            self.command_executed.emit(cmd)
        self.close()

    def _on_submit_selected(self):
        if 0 <= self._selected_index < len(self._filtered_commands):
            cmd = self._filtered_commands[self._selected_index].get("cmd", "")
            self._run_command(cmd)
        elif self._search_input.text().strip():
            self._run_command(self._search_input.text().strip())

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        elif key == Qt.Key.Key_Down:
            if self._filtered_commands:
                self._selected_index = (self._selected_index + 1) % len(self._filtered_commands)
                self._render_items()
            return
        elif key == Qt.Key.Key_Up:
            if self._filtered_commands:
                self._selected_index = (self._selected_index - 1) % len(self._filtered_commands)
                self._render_items()
            return
        super().keyPressEvent(event)


class DeveloperModeDialog(QDialog):
    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Developer Mode")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background: rgba(8,10,14,235); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; }}
            QLabel {{ color: {C.TEXT}; }}
            QLineEdit {{
                background: rgba(16,16,16,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
                padding: 8px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
            QPushButton {{
                background: rgba(18,18,18,240);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{ background: rgba(28,28,28,245); border: 1px solid {C.PRI}; }}
            QCheckBox {{ color: {C.TEXT}; }}
        """)

        self._settings = dict(settings or {})
        self._enabled = bool(self._settings.get("developer_mode_enabled", False))
        fallback_workspace = str(Path(__file__).resolve().parent)
        self._workspace = str(self._settings.get("developer_mode_workspace", "") or fallback_workspace)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Developer Co-pilot")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI};")
        root.addWidget(title)

        desc = QLabel("Pick a workspace folder Nexus Core should use when building websites or other workspace-based tasks.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C.TEXT_DIM};")
        root.addWidget(desc)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self._workspace_edit = QLineEdit(self._workspace)
        self._workspace_edit.setPlaceholderText("Select a folder...")
        self._workspace_edit.setReadOnly(True)
        folder_row.addWidget(self._workspace_edit, stretch=1)

        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse)
        root.addLayout(folder_row)

        self._enabled_box = QCheckBox("Turn developer mode on")
        self._enabled_box.setChecked(self._enabled)
        root.addWidget(self._enabled_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self._save_and_close)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select developer workspace", self._workspace or str(BASE_DIR))
        if path:
            self._workspace_edit.setText(path)

    def _save_and_close(self):
        self._settings["developer_mode_enabled"] = bool(self._enabled_box.isChecked())
        self._settings["developer_mode_workspace"] = self._workspace_edit.text().strip()
        self.accept()

    def get_settings(self) -> dict:
        return dict(self._settings)


def _ease_out_expo(x: float) -> float:
    return 1.0 if x == 1.0 else 1.0 - math.pow(2.0, -10.0 * x)

def _ease_in_out_sine(x: float) -> float:
    return -(math.cos(math.pi * x) - 1.0) / 2.0

class ScanningOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self._text = "SCANNING SCREEN"
        self._sub = "Analyzing display..."
        self._result_text = ""
        
        self._time = 0.0
        self._dt = 0.016
        self._fade_out_opacity = 1.0
        self._is_finishing = False
        self._finish_time = 0.0
        
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        self._particles = []
        self._boxes = [] 
        self._context_lines = []
        
        self.GOLD = QColor("#00E5FF")

    def set_message(self, text: str, sub: str | None = None):
        self._text = (text or "SCANNING SCREEN").upper()
        if sub is not None:
            self._sub = sub
        self.update()

    def show_fullscreen(self, text: str = "SCANNING SCREEN", sub: str = "Analyzing display..."):
        self.set_message(text, sub)
        self._time = 0.0
        self._fade_out_opacity = 1.0
        self._is_finishing = False
        self._finish_time = 0.0
        
        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1920, 1080).toRect()
        self.setGeometry(geo)
        
        # Capture screen for OpenCV
        if screen:
            pixmap = screen.grabWindow(0)
            self._generate_layout(pixmap)
        else:
            self._generate_layout(None)
        
        self.show()
        self.raise_()
        self.setFocus()

    def hide_overlay(self):
        if not self._is_finishing:
            self._is_finishing = True
            self._finish_time = self._time
            
            self._result_text = "Workspace Recognized\\nVisual Studio Code · Browser · Terminal"

    def force_hide(self):
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.force_hide()
        else:
            super().keyPressEvent(event)

    def _generate_layout(self, pixmap):
        random.seed(42)
        w, h = self.width(), self.height()
        
        # Particles
        self._particles = []
        for _ in range(120):
            self._particles.append({
                'x': random.uniform(0, w),
                'y': random.uniform(0, h),
                'vx': random.uniform(-1, 1),
                'vy': random.uniform(-1, 1),
                'life': random.uniform(0, math.pi * 2)
            })
            
        self._boxes = []
        self._context_lines = []
        
        if pixmap is not None:
            try:
                import cv2
                import numpy as np
                # Convert QPixmap to CV2
                qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
                width = qimg.width()
                height = qimg.height()
                ptr = qimg.constBits()
                ptr.setsize(height * width * 3)
                arr = np.array(ptr).reshape(height, width, 3)
                
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                
                kernel = np.ones((5,5), np.uint8)
                dilated = cv2.dilate(edges, kernel, iterations=1)
                
                contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Sort contours by area
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                
                # Take top 30 elements to avoid crowding
                for cnt in contours[:30]:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    area = cw * ch
                    if area < 150: continue # Skip tiny noise
                    
                    category = "UNKNOWN"
                    start_time = 1.0
                    label = "UI Element"
                    
                    if cw > 400 and ch > 300:
                        category = "WINDOW"
                        start_time = 2.5
                        label = random.choice(["Dashboard Panel", "Task Workspace", "Editor Window"])
                    elif cw > 80 and ch < 40:
                        category = "OCR"
                        start_time = 0.5 + random.uniform(0, 0.5)
                        label = random.choice(["System Online", "Settings", "Microphone", "User Profile"])
                    elif cw < 60 and ch < 60:
                        category = "ICON"
                        start_time = 1.5 + random.uniform(0, 0.5)
                        label = "Icon Node"
                    elif 1.2 < (cw/ch) < 4.0 and ch < 80:
                        category = "BUTTON"
                        start_time = 1.0 + random.uniform(0, 0.5)
                        label = "Action Button"
                    else:
                        continue # Skip weird shapes
                        
                    self._boxes.append({
                        'x': x, 'y': y, 'w': cw, 'h': ch,
                        'category': category,
                        'label': label,
                        'conf': random.randint(67, 98) if category != "WINDOW" else random.randint(95, 99),
                        'start_time': start_time,
                        'has_product': (category == "WINDOW" and random.random() > 0.8)
                    })
                    
            except Exception as e:
                print(f"[ScanningOverlay] CV2 Error: {e}")
                
        # Fallback if no boxes found or CV failed
        if len(self._boxes) == 0:
            for _ in range(5):
                self._boxes.append({
                    'x': random.uniform(w*0.2, w*0.8),
                    'y': random.uniform(h*0.2, h*0.8),
                    'w': random.uniform(100, 300),
                    'h': random.uniform(30, 60),
                    'category': "OCR",
                    'label': "Fallback Element",
                    'conf': 85,
                    'start_time': random.uniform(0.5, 1.5),
                    'has_product': False
                })

        # Generate Context Lines between nearest neighbors (Phase 5)
        for i, b1 in enumerate(self._boxes):
            if i >= 15: break
            for j, b2 in enumerate(self._boxes):
                if i != j and j < 15:
                    dist = math.hypot(b1['x'] - b2['x'], b1['y'] - b2['y'])
                    if dist < 400 and random.random() > 0.7:
                        self._context_lines.append((i, j))
                        break # max 1 connection per node

    def _tick(self):
        self._time += self._dt
        if self._is_finishing:
            dt_finish = self._time - self._finish_time
            if dt_finish > 1.5: 
                self._fade_out_opacity = max(0.0, 1.0 - (dt_finish - 1.5) * 2.0)
                if self._fade_out_opacity <= 0.0:
                    self.hide()
                    return
        if self.isVisible():
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._fade_out_opacity)
        
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(5, 5, 5, 210))
        
        phase1_progress = min(1.0, self._time / 1.5)
        phase6_progress = min(1.0, max(0.0, (self._time - 4.5) / 1.5))
        
        self._draw_particles(p, W, H, phase6_progress)
        self._draw_scan_waves(p, W, H, phase1_progress)
        
        if self._time > 0.5 and not self._is_finishing:
            self._draw_all_boxes(p)
            
        if self._time > 3.5 and not self._is_finishing:
            self._draw_context_lines(p)
            
        if self._time > 4.5 and not self._is_finishing:
            self._draw_neural_net(p, W, H, phase6_progress)
            
        self._draw_center_status(p, W, H)

    def _draw_particles(self, p, W, H, converge_progress):
        cx, cy = W / 2, H / 2
        p.setPen(Qt.PenStyle.NoPen)
        for part in self._particles:
            part['x'] += part['vx']
            part['y'] += part['vy']
            part['life'] += 0.05
            if part['x'] < 0: part['x'] = W
            if part['x'] > W: part['x'] = 0
            if part['y'] < 0: part['y'] = H
            if part['y'] > H: part['y'] = 0
            
            x, y = part['x'], part['y']
            if converge_progress > 0:
                e = _ease_in_out_sine(converge_progress)
                x = x + (cx - x) * e * 0.8
                y = y + (cy - y) * e * 0.8
                
            alpha = int(100 + math.sin(part['life']) * 50)
            p.setBrush(QColor(0, 229, 255, alpha))
            size = 1.5 + math.sin(part['life']) * 1.0
            p.drawEllipse(QRectF(x - size, y - size, size * 2, size * 2))
            
    def _draw_scan_waves(self, p, W, H, progress):
        if progress >= 1.0 or self._is_finishing: return
        e = _ease_out_expo(progress)
        y = e * H
        grad = QLinearGradient(0, y - 50, 0, y + 50)
        grad.setColorAt(0.0, QColor(0, 229, 255, 0))
        grad.setColorAt(0.5, QColor(0, 229, 255, 150))
        grad.setColorAt(1.0, QColor(0, 229, 255, 0))
        p.fillRect(QRectF(0, y - 50, W, 100), grad)
        x = e * W
        grad2 = QLinearGradient(x - 50, 0, x + 50, 0)
        grad2.setColorAt(0.0, QColor(0, 229, 255, 0))
        grad2.setColorAt(0.5, QColor(0, 229, 255, 150))
        grad2.setColorAt(1.0, QColor(0, 229, 255, 0))
        p.fillRect(QRectF(x - 50, 0, 100, H), grad2)
        
    def _draw_all_boxes(self, p):
        p.setBrush(Qt.BrushStyle.NoBrush)
        for box in self._boxes:
            dt = self._time - box['start_time']
            if dt < 0: continue
            
            out_dt = self._time - 4.5
            alpha_mult = max(0.0, 1.0 - out_dt) if out_dt > 0 else 1.0
            if alpha_mult <= 0: continue
            
            prog = min(1.0, dt / 0.8)
            e = _ease_out_expo(prog)
            
            x, y, w, h = box['x'], box['y'], box['w'], box['h']
            cat = box['category']
            
            alpha = int(255 * alpha_mult)
            
            # Styles based on category
            if cat == "OCR":
                br = (w / 4) * e
                p.setPen(QPen(QColor(0, 229, 255, int(150 * alpha_mult)), 1))
                if prog < 0.5:
                    p.drawLine(QPointF(x, y), QPointF(x + br, y))
                    p.drawLine(QPointF(x, y), QPointF(x, y + br))
                    p.drawLine(QPointF(x + w, y), QPointF(x + w - br, y))
                    p.drawLine(QPointF(x + w, y), QPointF(x + w, y + br))
                    p.drawLine(QPointF(x, y + h), QPointF(x + br, y + h))
                    p.drawLine(QPointF(x, y + h), QPointF(x, y + h - br))
                    p.drawLine(QPointF(x + w, y + h), QPointF(x + w - br, y + h))
                    p.drawLine(QPointF(x + w, y + h), QPointF(x + w, y + h - br))
                else:
                    p.drawRect(QRectF(x, y, w, h))
                    
            elif cat == "WINDOW":
                br = 30 * e
                p.setPen(QPen(QColor(0, 229, 255, int(200 * alpha_mult)), 2))
                p.drawLine(QPointF(x, y), QPointF(x + br, y))
                p.drawLine(QPointF(x, y), QPointF(x, y + br))
                p.drawLine(QPointF(x + w, y), QPointF(x + w - br, y))
                p.drawLine(QPointF(x + w, y), QPointF(x + w, y + br))
                p.drawLine(QPointF(x, y + h), QPointF(x + br, y + h))
                p.drawLine(QPointF(x, y + h), QPointF(x, y + h - br))
                p.drawLine(QPointF(x + w, y + h), QPointF(x + w - br, y + h))
                p.drawLine(QPointF(x + w, y + h), QPointF(x + w, y + h - br))
                
            elif cat == "BUTTON":
                p.setPen(QPen(QColor(0, 229, 255, int(100 * e * alpha_mult)), 1))
                p.setBrush(QColor(0, 229, 255, int(20 * e * alpha_mult)))
                p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
                p.setBrush(Qt.BrushStyle.NoBrush)
                
            elif cat == "ICON":
                p.setPen(QPen(QColor(0, 229, 255, int(200 * e * alpha_mult)), 1))
                p.drawEllipse(QRectF(x + w/2 - 4*e, y + h/2 - 4*e, 8*e, 8*e))
                
            if dt > 0.8:
                text_prog = min(1.0, (dt - 0.8) / 0.5)
                te = _ease_out_expo(text_prog)
                
                conf = box['conf']
                label = box['label']
                if conf < 75: label = f"Possible {label}"
                
                p.setFont(QFont("Inter", 8, QFont.Weight.Bold))
                p.setPen(QColor(0, 229, 255, int(255 * te * alpha_mult)))
                ly = y - 6 + (1.0 - te) * 10
                p.drawText(QRectF(x, ly - 10, 200, 12), Qt.AlignmentFlag.AlignLeft, f"{label} {conf}%")

            if box['has_product'] and dt > 2.0:
                card_prog = min(1.0, (dt - 2.0) / 0.5)
                ce = _ease_out_expo(card_prog)
                
                cx, cy = x + w + 20, y + 20
                cw, ch = 220, 90
                
                p.setPen(QPen(QColor(0, 229, 255, int(150 * ce * alpha_mult)), 1, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x + w, y + 40), QPointF(cx, cy + ch/2))
                
                p.setPen(QPen(QColor(0, 229, 255, int(100 * ce * alpha_mult)), 1))
                p.setBrush(QColor(10, 10, 5, int(220 * ce * alpha_mult)))
                p.drawRoundedRect(QRectF(cx, cy, cw, ch), 6, 6)
                p.setBrush(Qt.BrushStyle.NoBrush)
                
                if card_prog > 0.8:
                    p.setPen(QColor(255, 255, 255, int(255 * alpha_mult)))
                    p.setFont(QFont("Inter", 10, QFont.Weight.Bold))
                    p.drawText(QRectF(cx + 12, cy + 10, cw, 20), Qt.AlignmentFlag.AlignLeft, "Detected Interface")
                    
                    p.setPen(QColor(0, 229, 255, int(255 * alpha_mult)))
                    p.setFont(QFont("Inter", 8))
                    p.drawText(QRectF(cx + 12, cy + 32, cw, 20), Qt.AlignmentFlag.AlignLeft, f"{label} Verified")

    def _draw_context_lines(self, p):
        dt = self._time - 3.5
        out_dt = self._time - 4.5
        alpha_mult = max(0.0, 1.0 - out_dt) if out_dt > 0 else 1.0
        if alpha_mult <= 0: return
        prog = min(1.0, dt / 1.0)
        p.setPen(QPen(QColor(0, 229, 255, int(100 * prog * alpha_mult)), 1, Qt.PenStyle.DotLine))
        for i, j in self._context_lines:
            b1 = self._boxes[i]
            b2 = self._boxes[j]
            c1x, c1y = b1['x'] + b1['w']/2, b1['y'] + b1['h']/2
            c2x, c2y = b2['x'] + b2['w']/2, b2['y'] + b2['h']/2
            path = QPainterPath()
            path.moveTo(c1x, c1y)
            path.cubicTo(c1x + 100, c1y, c2x - 100, c2y, c2x, c2y)
            p.drawPath(path)

    def _draw_neural_net(self, p, W, H, progress):
        cx, cy = W / 2, H / 2
        e = _ease_out_expo(progress)
        r = 80 * e
        grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        grad.setColorAt(0.0, QColor(0, 229, 255, 150))
        grad.setColorAt(1.0, QColor(0, 229, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QRectF(cx - r*1.5, cy - r*1.5, r*3, r*3))
        p.setPen(QPen(QColor(0, 229, 255, int(200 * e)), 1))
        num_nodes = 8
        time_rot = self._time * 0.5
        nodes = []
        for i in range(num_nodes):
            angle = (i / num_nodes) * math.pi * 2 + time_rot
            orbit_r = 120 + math.sin(self._time * 2 + i) * 20
            nx = cx + math.cos(angle) * orbit_r * e
            ny = cy + math.sin(angle) * orbit_r * e
            nodes.append((nx, ny))
            p.setBrush(QColor(0, 229, 255, 255))
            p.drawEllipse(QRectF(nx - 3, ny - 3, 6, 6))
        for i in range(num_nodes):
            n1 = nodes[i]
            n2 = nodes[(i+1)%num_nodes]
            n3 = nodes[(i+3)%num_nodes]
            p.drawLine(QPointF(*n1), QPointF(*n2))
            p.drawLine(QPointF(*n1), QPointF(*n3))
            p.drawLine(QPointF(cx, cy), QPointF(*n1))

    def _draw_center_status(self, p, W, H):
        cx, cy = W / 2, H / 2
        if self._is_finishing:
            dt = self._time - self._finish_time
            prog = min(1.0, dt / 0.5)
            e = _ease_out_expo(prog)
            pw, ph = 400, 120
            p.setPen(QPen(QColor(0, 229, 255, int(150 * e)), 1))
            p.setBrush(QColor(10, 10, 5, int(230 * e)))
            p.drawRoundedRect(QRectF(cx - pw/2, cy - ph/2, pw, ph), 8, 8)
            if prog > 0.8:
                p.setPen(QColor(255, 255, 255, 255))
                p.setFont(QFont("Inter", 14, QFont.Weight.Bold))
                lines = self._result_text.split("\\n")
                if len(lines) > 0:
                    p.drawText(QRectF(cx - pw/2, cy - 20, pw, 24), Qt.AlignmentFlag.AlignCenter, lines[0])
                if len(lines) > 1:
                    p.setPen(QColor(0, 229, 255, 255))
                    p.setFont(QFont("Inter", 10))
                    p.drawText(QRectF(cx - pw/2, cy + 10, pw, 20), Qt.AlignmentFlag.AlignCenter, lines[1])
        else:
            status = "INITIALIZING..."
            if self._time > 1.0: status = "SCANNING OCR..."
            if self._time > 2.5: status = "RECOGNIZING OBJECTS..."
            if self._time > 3.5: status = "ANALYZING CONTEXT..."
            if self._time > 4.5:
                cycle = int(self._time * 2) % 4
                dots = "." * cycle
                status = f"THINKING{dots}"
            p.setPen(QColor(255, 255, 255, 255))
            p.setFont(QFont("Inter", 12, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy + 160, W, 20), Qt.AlignmentFlag.AlignCenter, status)


class BootSequenceOverlay(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(1.0)

        self._boot_finished = False
        self._time = 0.0
        self._dt = 0.016
        self._total_duration = 3.6

        # Particles & Effects State
        self._particles = []
        self._impact_sparks = []
        self._played_whoosh = False
        self._played_impact = False

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)

    def _init_particles(self, w: float, h: float):
        self._particles = []
        for _ in range(280):
            self._particles.append({
                'x': random.uniform(0, w),
                'y': random.uniform(0, h),
                'vx': random.uniform(-0.65, 0.65),
                'vy': random.uniform(-0.65, 0.65),
                'size': random.uniform(1.4, 4.0),
                'base_alpha': random.uniform(0.65, 1.0),
                'twinkle_speed': random.uniform(2.5, 6.5),
                'twinkle_phase': random.uniform(0, math.pi * 2),
                'converge_delay': random.uniform(0.0, 0.25),
                'orig_x': 0.0,
                'orig_y': 0.0,
            })

    def start(self, device_name: str = "", greeting_name: str = ""):
        self._boot_finished = False
        screen = QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1920, 1080).toRect()
        self.setGeometry(geo)
        self._init_particles(float(geo.width()), float(geo.height()))
        self._time = 0.0
        self._played_whoosh = False
        self._played_impact = False
        self.show()
        self.raise_()
        self.activateWindow()
        self._tmr.start(16)

    def add_step(self, text: str):
        pass

    def set_step_status(self, text: str, status: str):
        pass

    def set_progress(self, percent: int, tip: str | None = None):
        pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._tmr.stop()
            self._boot_finished = True
            self.hide()
            self.close()
            self.finished.emit()

    def _tick(self):
        self._time += self._dt
        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        # Phase 1 (0.0 to 1.1s): particles drift across full screen
        if self._time < 1.1:
            for p in self._particles:
                p['x'] += p['vx']
                p['y'] += p['vy']
                if p['x'] < 0: p['x'] = w
                elif p['x'] > w: p['x'] = 0
                if p['y'] < 0: p['y'] = h
                elif p['y'] > h: p['y'] = 0

        # Phase 2 (1.1s to 1.8s): burst & convergence towards center
        elif 1.1 <= self._time < 1.8:
            if not self._played_whoosh:
                self._played_whoosh = True
                try:
                    from sound_manager import SoundManager
                    SoundManager.instance().play_deploy_whoosh()
                except Exception:
                    pass
                for p in self._particles:
                    p['orig_x'] = p['x']
                    p['orig_y'] = p['y']

            burst_t = (self._time - 1.1) / 0.7
            for p in self._particles:
                local_t = max(0.0, min(1.0, (burst_t - p['converge_delay']) / (1.0 - p['converge_delay'] + 0.001)))
                ease = math.pow(local_t, 3.2)
                p['x'] = p['orig_x'] + (cx - p['orig_x']) * ease
                p['y'] = p['orig_y'] + (cy - 30.0 - p['orig_y']) * ease

        # Phase 4 (2.5s to 3.2s): AI - EVO entrance with impact
        if self._time >= 2.5 and not self._played_impact:
            self._played_impact = True
            try:
                from sound_manager import SoundManager
                SoundManager.instance().play_mission_complete()
            except Exception:
                pass
            self._impact_sparks = []
            for _ in range(70):
                angle = random.uniform(0, math.pi * 2)
                spd = random.uniform(6.0, 24.0)
                self._impact_sparks.append({
                    'x': cx,
                    'y': cy + 55.0,
                    'vx': math.cos(angle) * spd,
                    'vy': math.sin(angle) * spd * 0.65,
                    'alpha': 1.0,
                    'size': random.uniform(2.0, 4.5),
                    'color': random.choice(['#00f0ff', '#ffffff', '#7dd3fc', '#38bdf8'])
                })

        if self._impact_sparks:
            for s in self._impact_sparks:
                s['x'] += s['vx']
                s['y'] += s['vy']
                s['vx'] *= 0.92
                s['vy'] *= 0.92
                s['alpha'] *= 0.92

        self.update()

        if self._time >= self._total_duration:
            self._tmr.stop()
            self._boot_finished = True
            self.hide()
            self.close()
            self.finished.emit()

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            # Minimal DWM compositing fill (alpha=1 ensures DWM layered composition without visible darkening)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

            w = float(self.width())
            h = float(self.height())
            cx = w / 2.0
            cy = h / 2.0

            # DO NOT DRAW BACKGROUND FILL: Purely transparent!

            # Transition out alpha (Phase 5: 3.2s to 3.6s)
            global_alpha = 1.0
            if self._time >= 3.2:
                exit_t = min(1.0, (self._time - 3.2) / 0.4)
                global_alpha = max(0.0, 1.0 - exit_t)

            # Camera Shake calculation during impact (2.5s to 3.0s)
            shake_x, shake_y = 0.0, 0.0
            if 2.5 <= self._time < 3.0:
                shake_dt = self._time - 2.5
                decay = max(0.0, 1.0 - (shake_dt / 0.45))
                shake_x = math.sin(shake_dt * 65.0) * 16.0 * decay
                shake_y = math.cos(shake_dt * 52.0) * 10.0 * decay

            painter.translate(shake_x, shake_y)

            # -------------------------------------------------------------
            # 1. DRAW PARTICLES
            # -------------------------------------------------------------
            if self._time < 1.8:
                for p in self._particles:
                    p_alpha = p['base_alpha']
                    if self._time < 0.6:
                        p_alpha *= (self._time / 0.6)
                    twinkle = 0.75 + 0.25 * math.sin(self._time * p['twinkle_speed'] + p['twinkle_phase'])
                    final_alpha = int(255 * p_alpha * twinkle * global_alpha)

                    if final_alpha <= 0:
                        continue

                    if p['size'] > 2.5:
                        glow_pen = QColor(255, 255, 255, int(final_alpha * 0.25))
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(glow_pen)
                        painter.drawEllipse(QPointF(p['x'], p['y']), p['size'] * 2.2, p['size'] * 2.2)

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(255, 255, 255, final_alpha))
                    painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])

            # -------------------------------------------------------------
            # 2. DRAW CENTER CONVERGENCE FLASH & SHOCKWAVE
            # -------------------------------------------------------------
            if 1.4 <= self._time < 1.9:
                flash_t = (self._time - 1.4) / 0.5
                flash_rad = 12.0 + math.sin(flash_t * math.pi) * 80.0
                flash_alpha = int(255 * math.sin(flash_t * math.pi) * global_alpha)
                if flash_alpha > 0:
                    grad = QRadialGradient(cx, cy - 30.0, flash_rad)
                    grad.setColorAt(0.0, QColor(255, 255, 255, flash_alpha))
                    grad.setColorAt(0.3, QColor(0, 240, 255, int(flash_alpha * 0.7)))
                    grad.setColorAt(1.0, QColor(0, 240, 255, 0))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(grad))
                    painter.drawEllipse(QPointF(cx, cy - 30.0), flash_rad, flash_rad)

            # Impact Shockwave at 2.5s
            if self._time >= 2.5:
                sw_prog = min(1.0, (self._time - 2.5) / 0.6)
                sw_rad = sw_prog * 480.0
                sw_alpha = int(255 * (1.0 - sw_prog) * global_alpha)
                if sw_alpha > 0:
                    sw_pen = QPen(QColor(0, 240, 255, sw_alpha), 3.0)
                    painter.setPen(sw_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(QPointF(cx, cy + 55.0), sw_rad, sw_rad * 0.6)

            # Impact Sparks
            if self._impact_sparks:
                painter.setPen(Qt.PenStyle.NoPen)
                for s in self._impact_sparks:
                    s_alpha = int(255 * s['alpha'] * global_alpha)
                    if s_alpha <= 0: continue
                    col = QColor(s['color'])
                    col.setAlpha(s_alpha)
                    painter.setBrush(col)
                    painter.drawEllipse(QPointF(s['x'], s['y']), s['size'], s['size'])

            # -------------------------------------------------------------
            # 3. DRAW "NEXUS" TEXT & TYPOGRAPHY EFFECT
            # -------------------------------------------------------------
            if self._time >= 1.35:
                text_t = min(1.0, (self._time - 1.35) / 0.45)
                text_alpha = int(255 * text_t * global_alpha)

                spacing_prog = min(1.0, (self._time - 1.35) / 1.5)
                letter_spacing = 10.0 + (spacing_prog * 14.0)

                font_nexus = QFont("Segoe UI", 56, QFont.Weight.Black)
                font_nexus.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
                painter.setFont(font_nexus)

                rect_nexus = QRectF(cx - 500, cy - 85, 1000, 90)

                # Outer text ice glow
                glow_col = QColor(47, 209, 217, int(text_alpha * 0.45))
                painter.setPen(glow_col)
                for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)]:
                    painter.drawText(rect_nexus.translated(ox, oy), Qt.AlignmentFlag.AlignCenter, "NEXUS")

                # Core white text with dynamic shimmer
                if 1.8 <= self._time < 2.5:
                    shim_t = (self._time - 1.8) / 0.7
                    sweep_x = cx - 350 + (shim_t * 700)
                    grad = QLinearGradient(sweep_x - 120, cy, sweep_x + 120, cy)
                    grad.setColorAt(0.0, QColor(232, 238, 245, int(text_alpha * 0.75)))
                    grad.setColorAt(0.5, QColor(217, 243, 251, text_alpha))
                    grad.setColorAt(0.7, QColor(232, 238, 245, text_alpha))
                    grad.setColorAt(1.0, QColor(232, 238, 245, int(text_alpha * 0.75)))
                    painter.setPen(QPen(QBrush(grad), 1))
                else:
                    painter.setPen(QColor(232, 238, 245, text_alpha))

                painter.drawText(rect_nexus, Qt.AlignmentFlag.AlignCenter, "NEXUS")

            # -------------------------------------------------------------
            # 4. DRAW "CORE" SUBTITLE WITH MAXIMUM IMPACT (>= 2.5s)
            # -------------------------------------------------------------
            if self._time >= 2.5:
                core_dt = self._time - 2.5
                core_alpha = int(255 * min(1.0, core_dt / 0.08) * global_alpha)

                slam_scale = 1.0
                if core_dt < 0.18:
                    slam_t = core_dt / 0.18
                    slam_scale = 1.5 - (0.5 * math.sin(slam_t * math.pi * 0.5))

                painter.save()
                painter.translate(cx, cy + 50.0)
                painter.scale(slam_scale, slam_scale)

                badge_w = 260.0
                badge_h = 44.0
                badge_rect = QRectF(-badge_w / 2.0, -badge_h / 2.0, badge_w, badge_h)

                painter.setPen(QPen(QColor(47, 209, 217, int(core_alpha * 0.8)), 1.5))
                painter.setBrush(QColor(43, 35, 71, int(core_alpha * 0.55)))
                painter.drawRoundedRect(badge_rect, 22.0, 22.0)

                font_sub = QFont("Segoe UI", 18, QFont.Weight.Bold)
                font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
                painter.setFont(font_sub)

                painter.setPen(QColor(232, 238, 245, core_alpha))
                painter.drawText(QRectF(-badge_w / 2.0, -badge_h / 2.0, 125, badge_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "CORE")

                painter.restore()

            painter.end()
        except Exception as e:
            import traceback
            traceback.print_exc()


class IncomingAlertDialog(QDialog):
    decision = pyqtSignal(str)

    def __init__(self, event: dict, parent=None):
        super().__init__(parent)
        self._event = event or {}
        self._kind = (self._event.get("kind") or "message").strip().lower()
        self._app = (self._event.get("app") or "App").strip()
        self._title = (self._event.get("title") or "").strip()
        self._preview = (self._event.get("preview") or "").strip()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("IncomingAlertDialog")
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("IncomingAlertFrame")
        frame.setStyleSheet(f"""
            QFrame#IncomingAlertFrame {{
                background: rgba(8, 8, 8, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 16px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        heading = QLabel("Incoming Call" if self._kind == "call" else "Incoming Message")
        heading.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        heading.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(heading)

        app_lbl = QLabel(f"From {self._app}")
        app_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        app_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(app_lbl)

        body = self._preview or self._title or "A notification was detected."
        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setFont(QFont("Segoe UI", 10))
        body_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(body_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        def _btn(text: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            fg = C.WHITE
            border = C.BORDER_B if primary else C.BORDER
            bg = "rgba(255,255,255,0.10)" if primary else "rgba(14,14,14,235)"
            if danger:
                border = C.RED
                bg = "rgba(60,10,10,235)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 11px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.14);
                    border: 1px solid {C.WHITE};
                }}
            """)
            return btn

        if self._kind == "call":
            self._accept_btn = _btn("Pick up", primary=True)
            self._ignore_btn = _btn("Ignore")
            self._cut_btn = _btn("Cut call", danger=True)
            self._x_btn = _btn("X")
            self._accept_btn.clicked.connect(lambda: self._choose("accept"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._cut_btn.clicked.connect(lambda: self._choose("cut"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            for btn in (self._accept_btn, self._ignore_btn, self._cut_btn, self._x_btn):
                btn_row.addWidget(btn)
        else:
            self._hear_btn = _btn("Hear it", primary=True)
            self._reply_btn = _btn("Reply")
            self._ignore_btn = _btn("Ignore")
            self._x_btn = _btn("X")
            self._hear_btn.clicked.connect(lambda: self._choose("hear"))
            self._reply_btn.clicked.connect(lambda: self._choose("reply"))
            self._ignore_btn.clicked.connect(lambda: self._choose("ignore"))
            self._x_btn.clicked.connect(lambda: self._choose("noop"))
            btn_row.addWidget(self._hear_btn)
            btn_row.addWidget(self._reply_btn)
            btn_row.addWidget(self._ignore_btn)
            btn_row.addWidget(self._x_btn)

        lay.addLayout(btn_row)

    def _choose(self, decision: str):
        self.decision.emit(decision)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._choose("ignore")
            return
        super().keyPressEvent(event)


class UltronMalfunctionDialog(QDialog):
    """
    Ultron Autonomous Malfunction & Self-Repair HUD Dialog.
    Pops up on screen immediately when any runtime error occurs in terminal or tool.
    Displays the problem, root cause, live surgical patch diff, and auto-repair progress.
    Operates autonomously under Ultron protocol (no user permission asked).
    """

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("UltronMalfunctionDialog")
        self.setFixedWidth(540)
        self.setMinimumHeight(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName("UltronPopupFrame")
        self._frame.setStyleSheet(f"""
            QFrame#UltronPopupFrame {{
                background: rgba(10, 12, 16, 252);
                border: 2px solid {C.RED};
                border-radius: 16px;
            }}
        """)
        root.addWidget(self._frame)

        self._lay = QVBoxLayout(self._frame)
        self._lay.setContentsMargins(20, 18, 20, 18)
        self._lay.setSpacing(10)

        # 1. Header Banner
        head_layout = QHBoxLayout()
        head_layout.setSpacing(8)

        self._title_icon = QLabel("🚨")
        self._title_icon.setFont(QFont("Segoe UI Emoji", 14))
        self._title_icon.setStyleSheet("background: transparent;")
        head_layout.addWidget(self._title_icon)

        self._title_lbl = QLabel("ULTRON AUTONOMOUS SELF-REPAIR")
        self._title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.RED}; background: transparent; letter-spacing: 1px;")
        head_layout.addWidget(self._title_lbl, 1)

        self._protocol_badge = QLabel("ULTRON PROTOCOL")
        self._protocol_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._protocol_badge.setStyleSheet(f"""
            color: #ffffff;
            background: rgba(255, 59, 48, 0.25);
            border: 1px solid {C.RED};
            border-radius: 6px;
            padding: 3px 7px;
        """)
        head_layout.addWidget(self._protocol_badge)
        self._lay.addLayout(head_layout)

        # Subtitle
        self._sub_lbl = QLabel("Sir, I detected a malfunction. Stand by, executing autonomous self-repair.")
        self._sub_lbl.setFont(QFont("Segoe UI", 9))
        self._sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._lay.addWidget(self._sub_lbl)

        # 2. Malfunction Target Box
        self._info_box = QFrame()
        self._info_box.setStyleSheet("""
            QFrame {
                background: rgba(20, 24, 32, 220);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
            }
        """)
        info_lay = QVBoxLayout(self._info_box)
        info_lay.setContentsMargins(12, 10, 12, 10)
        info_lay.setSpacing(4)

        self._target_lbl = QLabel("Component: Scanning...")
        self._target_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self._target_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        info_lay.addWidget(self._target_lbl)

        self._exc_lbl = QLabel("Exception: In Progress")
        self._exc_lbl.setFont(QFont("Consolas", 9))
        self._exc_lbl.setStyleSheet("color: #ff8580; background: transparent;")
        self._exc_lbl.setWordWrap(True)
        info_lay.addWidget(self._exc_lbl)
        self._lay.addWidget(self._info_box)

        # 3. Problem & Root Cause
        self._explanation_lbl = QLabel("Root cause analysis running...")
        self._explanation_lbl.setWordWrap(True)
        self._explanation_lbl.setFont(QFont("Segoe UI", 9))
        self._explanation_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._lay.addWidget(self._explanation_lbl)

        # 4. Surgical Patch Code Diff Box
        self._diff_scroll = QScrollArea()
        self._diff_scroll.setWidgetResizable(True)
        self._diff_scroll.setFixedHeight(120)
        self._diff_scroll.setStyleSheet("""
            QScrollArea {
                background: #06070a;
                border: 1px solid rgba(0, 229, 255, 0.20);
                border-radius: 8px;
            }
        """)
        diff_inner = QWidget()
        diff_inner.setStyleSheet("background: transparent;")
        self._diff_lay = QVBoxLayout(diff_inner)
        self._diff_lay.setContentsMargins(8, 8, 8, 8)
        self._diff_lay.setSpacing(6)

        self._diff_target = QLabel("")
        self._diff_target.setFont(QFont("Consolas", 9))
        self._diff_target.setStyleSheet("color: #ff7070; background: rgba(80, 20, 20, 0.40); padding: 4px; border-radius: 4px;")
        self._diff_target.setWordWrap(True)
        self._diff_lay.addWidget(self._diff_target)

        self._diff_rep = QLabel("")
        self._diff_rep.setFont(QFont("Consolas", 9))
        self._diff_rep.setStyleSheet("color: #40ff70; background: rgba(20, 80, 30, 0.40); padding: 4px; border-radius: 4px;")
        self._diff_rep.setWordWrap(True)
        self._diff_lay.addWidget(self._diff_rep)

        self._diff_scroll.setWidget(diff_inner)
        self._lay.addWidget(self._diff_scroll)

        # 5. Progress Bar & Status
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(6)
        self._pbar.setTextVisible(False)
        self._pbar.setValue(25)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{
                background: #151821;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C.RED}, stop:1 {C.ACC});
                border-radius: 3px;
            }}
        """)
        self._lay.addWidget(self._pbar)

        self._status_lbl = QLabel("Autonomous diagnosis and synthesis in progress...")
        self._status_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        self._lay.addWidget(self._status_lbl)

        # 6. Action Button (Dismiss / Close - NO asking for user permission!)
        btn_lay = QHBoxLayout()
        btn_lay.addStretch(1)

        self._close_btn = QPushButton("Acknowledge & Dismiss")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedHeight(32)
        self._close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.15);
                border: 1px solid {C.ACC};
            }}
        """)
        self._close_btn.clicked.connect(self.close)
        btn_lay.addWidget(self._close_btn)
        self._lay.addLayout(btn_lay)

        self.update_content(data)

    def update_content(self, data: dict):
        status = data.get("status") or ""
        percent = data.get("percent", 50)
        file_name = data.get("file_name") or data.get("target_file") or "System Component"
        line_num = data.get("line_number")
        exc_type = data.get("exception_type") or "Error"
        exc_msg = data.get("exception_message") or ""
        explanation = data.get("explanation") or ""
        target_chunk = data.get("target_chunk") or ""
        replacement_chunk = data.get("replacement_chunk") or ""

        line_str = f" (line {line_num})" if line_num else ""
        self._target_lbl.setText(f"📁 {file_name}{line_str}")
        self._exc_lbl.setText(f"💥 {exc_type}: {exc_msg}")

        if explanation:
            self._explanation_lbl.setText(f"🔍 Analysis: {explanation}")

        if target_chunk:
            self._diff_target.setText(f"- REMOVING:\n{target_chunk.strip()}")
            self._diff_target.setVisible(True)
        else:
            self._diff_target.setVisible(False)

        if replacement_chunk:
            self._diff_rep.setText(f"+ APPLYING HOTFIX:\n{replacement_chunk.strip()}")
            self._diff_rep.setVisible(True)
        else:
            self._diff_rep.setVisible(False)

        self._pbar.setValue(percent)
        if status:
            self._status_lbl.setText(status)

        # When finished, transition styling to glowing Green
        if percent >= 100:
            self._frame.setStyleSheet(f"""
                QFrame#UltronPopupFrame {{
                    background: rgba(10, 12, 16, 252);
                    border: 2px solid {C.GREEN};
                    border-radius: 16px;
                }}
            """)
            self._title_icon.setText("🛡️")
            self._title_lbl.setText("ULTRON SELF-REPAIR COMPLETED")
            self._title_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; letter-spacing: 1px;")
            self._protocol_badge.setText("SYSTEM HEALTHY")
            self._protocol_badge.setStyleSheet(f"""
                color: #ffffff;
                background: rgba(55, 255, 95, 0.25);
                border: 1px solid {C.GREEN};
                border-radius: 6px;
                padding: 3px 7px;
            """)
            self._status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
            self._close_btn.setText("Close")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


class MeetingOverlay(QWidget):
    stop_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self._expanded_height = 142
        self._collapsed_height = 58
        self._collapsed = False
        self.setFixedHeight(self._expanded_height)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(5, 5, 5, 232);
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        self._badge = QLabel("MEETING MODE")
        self._badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._badge.setStyleSheet(
            f"color: {C.WHITE}; background: rgba(255,255,255,0.06); border: 1px solid {C.BORDER_B}; border-radius: 10px; padding: 4px 10px;"
        )
        top.addWidget(self._badge)

        self._title = QLabel("Watching the meeting")
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        top.addWidget(self._title)
        top.addStretch()

        self._min_btn = QPushButton("-")
        self._min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min_btn.setFixedSize(28, 28)
        self._min_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._min_btn.setToolTip("Minimize meeting bar")
        self._min_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._min_btn.clicked.connect(self._toggle_collapsed)
        top.addWidget(self._min_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        top.addWidget(self._stop_btn)

        self._close_btn = QPushButton("x")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._close_btn.setToolTip("Close meeting bar")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border: 1px solid {C.WHITE};
            }}
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        top.addWidget(self._close_btn)
        lay.addLayout(top)

        self._summary = QLabel("Waiting for a meeting to start...")
        self._summary.setWordWrap(True)
        self._summary.setFont(QFont("Segoe UI", 10))
        self._summary.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._summary)

        self._speech = QLabel("They said: nothing yet.")
        self._speech.setWordWrap(True)
        self._speech.setFont(QFont("Segoe UI", 10))
        self._speech.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._speech)

        self._answer = QLabel("Nexus Core will show the live answer here.")
        self._answer.setWordWrap(True)
        self._answer.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._answer.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._answer)

        self._apply_collapsed_state(False)

    def set_content(self, title: str, summary: str, answer: str, active: bool = True, speech: str = ""):
        self._title.setText(title or "Watching the meeting")
        self._summary.setText(summary or "Watching the meeting screen.")
        self._speech.setText(f"They said: {speech or 'nothing yet.'}")
        self._answer.setText(answer or "No question detected yet.")
        self._badge.setText("MEETING LIVE" if active else "MEETING MODE")

    def _apply_collapsed_state(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        for widget in (self._summary, self._speech, self._answer):
            widget.setVisible(not self._collapsed)
        self._min_btn.setText("?" if self._collapsed else "-")
        self._min_btn.setToolTip("Restore meeting bar" if self._collapsed else "Minimize meeting bar")
        self.setFixedHeight(self._collapsed_height if self._collapsed else self._expanded_height)

    def set_collapsed(self, collapsed: bool):
        self._apply_collapsed_state(collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _toggle_collapsed(self):
        self.minimize_requested.emit()


class FloatingLauncher(QWidget):
    single_clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    action_requested = pyqtSignal(str)
    position_changed = pyqtSignal(int, int)

    _STATE_THEMES = {
        "idle": (255, 255, 255),       # Luminous Pure White
        "listening": (0, 229, 255),    # Electric Ice Cyan
        "thinking": (160, 230, 255),   # Frost Blue
        "speaking": (255, 255, 255),   # Brilliant White
        "executing": (0, 229, 255),    # Dynamic Ice Cyan
        "processing": (0, 229, 255),   # Dynamic Ice Cyan
        "working": (0, 229, 255),      # Dynamic Ice Cyan
        "muted": (160, 160, 160),      # Cool Silver
        "error": (255, 82, 82),        # Alert Crimson
    }

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(88, 88)
        self._state = "idle"
        self._status_line = "Ready"
        self._hovered = False

        # Animation state
        self._anim_angle = 0.0
        self._ring2_angle = 0.0
        self._breath_val = 0.0
        self._breath_dir = 1
        self._particle_angles = [i * 45.0 for i in range(8)]
        self._particle_trails = [[] for _ in range(8)]

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(25)  # 40fps

        self._single_timer = QTimer(self)
        self._single_timer.setSingleShot(True)
        self._single_timer.timeout.connect(self._on_single_click_timeout)

        # Kinetic spring physics & audio reactivity
        self._audio_lvl = 0.0
        self._gaze_x = 0.0
        self._gaze_y = 0.0
        self._target_snap_x = 0
        self._spring_timer = QTimer(self)
        self._spring_timer.setInterval(16)
        self._spring_timer.timeout.connect(self._spring_step)

        self._dragging = False
        self._drag_button = None
        self._drag_offset = QPoint(0, 0)
        self._press_pos = QPoint(0, 0)
        self._apply_state_style()

    def set_audio_level(self, lvl: float):
        self._audio_lvl = max(0.0, min(1.0, float(lvl)))
        self.update()

    def _spring_step(self):
        curr_x = self.x()
        diff = self._target_snap_x - curr_x
        if abs(diff) < 2:
            self.move(self._target_snap_x, self.y())
            self._spring_timer.stop()
            self.position_changed.emit(self.x(), self.y())
        else:
            step = int(diff * 0.28)
            if step == 0:
                step = 1 if diff > 0 else -1
            self.move(curr_x + step, self.y())

    def _on_single_click_timeout(self):
        self.single_clicked.emit()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_anim_timer") and self._anim_timer.isActive():
            self._anim_timer.stop()
        if hasattr(self, "_spring_timer") and self._spring_timer.isActive():
            self._spring_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_anim_timer") and not self._anim_timer.isActive():
            self._anim_timer.start(25)

    def _anim_tick(self):
        if not self.isVisible():
            if hasattr(self, "_anim_timer") and self._anim_timer.isActive():
                self._anim_timer.stop()
            return
        import math
        # State-dependent spin speeds
        spin_speed = 3.2 if self._state == "thinking" else (2.4 if self._state in ("listening", "speaking") else 1.5)
        self._anim_angle = (self._anim_angle + spin_speed) % 360.0
        self._ring2_angle = (self._ring2_angle - spin_speed * 0.75) % 360.0

        breath_step = 0.04 if self._state in ("listening", "speaking", "thinking") else 0.022
        self._breath_val += breath_step * self._breath_dir
        if self._breath_val >= 1.0:
            self._breath_val = 1.0
            self._breath_dir = -1
        elif self._breath_val <= 0.0:
            self._breath_val = 0.0
            self._breath_dir = 1

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        for i in range(len(self._particle_angles)):
            speed = 0.9 + i * 0.14
            self._particle_angles[i] = (self._particle_angles[i] + speed) % 360.0
            rad = math.radians(self._particle_angles[i])
            orbit_r = 35.0 + (i % 3) * 2.2 + self._audio_lvl * 5.0
            px = cx + math.cos(rad) * orbit_r
            py = cy + math.sin(rad) * orbit_r
            trail = self._particle_trails[i]
            trail.append((px, py))
            if len(trail) > 5:
                trail.pop(0)
        self.update()

    _ICON_SIZE = 46

    def _icon_pixmap(self):
        """App icon, scaled once for this screen. Drawn whole (never clipped to a circle)."""
        if hasattr(self, "_icon_pm_cache"):
            return self._icon_pm_cache
        pm = None
        try:
            src = QPixmap(str(APP_ICON_PNG))
            if not src.isNull():
                dpr = max(1.0, float(self.devicePixelRatioF()))
                px = int(round(self._ICON_SIZE * dpr))
                pm = src.scaled(
                    px, px,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                pm.setDevicePixelRatio(dpr)
        except Exception:
            pm = None
        self._icon_pm_cache = pm
        return pm

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        icon_pm = self._icon_pixmap()

        ar, ag, ab = self._STATE_THEMES.get(self._state, (255, 255, 255))
        breath = self._breath_val
        hover_boost = 1.35 if self._hovered else 1.0
        audio_boost = self._audio_lvl * 12.0

        # ── 1.5 Dynamic Acoustic Shockwave Ring (Voice Reactive) ──
        if self._audio_lvl > 0.05:
            shock_r = 38.0 + breath * 4.0 + self._audio_lvl * 20.0
            shock_alpha = int(min(220, self._audio_lvl * 240))
            shock_pen = QPen(QColor(0, 229, 255, shock_alpha), 1.8)
            painter.setPen(shock_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), shock_r, shock_r)

        # ── 1. Pulsing Ambient Glow (Audio Reactive) ──
        glow_r = (38.0 + breath * 5.5 + audio_boost) * (1.1 if self._hovered else 1.0)
        glow_alpha = int((30 + breath * 45 + self._audio_lvl * 70) * hover_boost)
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(ar, ag, ab, min(255, glow_alpha)))
        glow.setColorAt(0.55, QColor(ar, ag, ab, min(255, int(glow_alpha * 0.35))))
        glow.setColorAt(1.0, QColor(ar, ag, ab, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # ── 2. Subtle Outer Orbit Guide Ring ──
        guide_pen = QPen(QColor(ar, ag, ab, int(25 + breath * 20)), 0.75)
        guide_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(guide_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), 39.0, 39.0)

        # ── 3. High-Tech Dual Rotating Arcs ──
        # Primary Outer Arc
        a1 = min(255, int((170 + breath * 75 + self._audio_lvl * 50) * hover_boost))
        pen1 = QPen(QColor(ar, ag, ab, a1), 2.2 + self._audio_lvl * 1.5)
        pen1.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen1)
        rect1 = QRectF(cx - 35.0, cy - 35.0, 70.0, 70.0)
        arc_len = 110 if self._state != "thinking" else 140
        painter.drawArc(rect1, int(self._anim_angle * 16), int(arc_len * 16))

        # Secondary Counter-Rotating Arc
        a2 = min(255, int((90 + breath * 50) * hover_boost))
        pen2 = QPen(QColor(ar, ag, ab, a2), 1.3)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen2)
        rect2 = QRectF(cx - 31.5, cy - 31.5, 63.0, 63.0)
        painter.drawArc(rect2, int(self._ring2_angle * 16), int(80 * 16))

        # Orbiting Satellite Beacon
        sat_rad = math.radians(self._anim_angle + 180.0)
        sat_x = cx + math.cos(sat_rad) * 35.0
        sat_y = cy + math.sin(sat_rad) * 35.0
        sat_color = QColor(ar, ag, ab).lighter(150)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(sat_color.red(), sat_color.green(), sat_color.blue(), min(255, int(180 * hover_boost)))))
        painter.drawEllipse(QPointF(sat_x, sat_y), 2.2, 2.2)

        # ── 4. Central Glassmorphic Core (with Cursor Parallax) ──
        gx, gy = self._gaze_x, self._gaze_y
        core_r = 25.5 + self._audio_lvl * 2.0
        core_grad = QRadialGradient(cx + gx * 0.5, cy - 4.0 + gy * 0.5, core_r)
        core_grad.setColorAt(0.0, QColor(20, 22, 30, 246))
        core_grad.setColorAt(0.85, QColor(10, 11, 16, 252))
        core_grad.setColorAt(1.0, QColor(ar, ag, ab, 30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(core_grad))
        if icon_pm is None:
            painter.drawEllipse(QPointF(cx + gx * 0.5, cy + gy * 0.5), core_r, core_r)

        # Glowing Core Rim
        rim_alpha = min(255, int((110 + breath * 80 + self._audio_lvl * 60) * hover_boost))
        rim_pen = QPen(QColor(ar, ag, ab, rim_alpha), 1.2)
        painter.setPen(rim_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if icon_pm is None:
            painter.drawEllipse(QPointF(cx + gx * 0.5, cy + gy * 0.5), core_r, core_r)

        # ── 5. Orbiting Micro-Particle Comet Trails ──
        for i in range(len(self._particle_trails)):
            trail = self._particle_trails[i]
            for t_idx, (px, py) in enumerate(trail):
                frac = (t_idx + 1) / max(len(trail), 1)
                t_alpha = min(255, int(frac * (50 + breath * 70) * hover_boost))
                t_size = 0.5 + frac * 1.2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(ar, ag, ab, t_alpha)))
                painter.drawEllipse(QPointF(px, py), t_size, t_size)
            if trail:
                hx, hy = trail[-1]
                head_alpha = min(255, int((120 + breath * 120) * hover_boost))
                head_c = QColor(ar, ag, ab).lighter(140)
                painter.setBrush(QBrush(QColor(head_c.red(), head_c.green(), head_c.blue(), head_alpha)))
                painter.drawEllipse(QPointF(hx, hy), 1.6, 1.6)

        # ── 6. Emblem: the Nexus app icon (whole, uncropped) + Status Dot ──
        if icon_pm is not None:
            size = float(self._ICON_SIZE)
            ix = cx - size / 2.0 + gx * 0.5
            iy = cy - size / 2.0 + gy * 0.5
            radius = size * 0.22
            # soft contact shadow so the icon lifts off the glow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
            painter.drawRoundedRect(QRectF(ix + 0.5, iy + 2.0, size, size), radius, radius)
            painter.drawPixmap(QPointF(ix, iy), icon_pm)
            # state beacon on the icon's lower-right corner
            dot_alpha = min(255, int((170 + breath * 85) * hover_boost))
            bx, by = ix + size - 3.0, iy + size - 3.0
            painter.setBrush(QBrush(QColor(8, 10, 16, 235)))
            painter.drawEllipse(QPointF(bx, by), 4.6, 4.6)
            painter.setBrush(QBrush(QColor(ar, ag, ab, dot_alpha)))
            painter.drawEllipse(QPointF(bx, by), 3.0, 3.0)
        else:
            text_alpha = min(255, int((215 + breath * 40) * hover_boost))
            painter.setPen(QPen(QColor(0, 0, 0, 180)))
            painter.setFont(QFont("Nirmala UI", 11, QFont.Weight.Bold))
            painter.drawText(QRectF(cx - 21.0 + gx, cy - 13.0 + gy, 44.0, 22.0), Qt.AlignmentFlag.AlignCenter, "\u092C\u094D\u0930\u0939\u094D\u092E\u093E")

            # Crisp glowing text
            painter.setPen(QPen(QColor(ar, ag, ab, text_alpha)))
            painter.setFont(QFont("Nirmala UI", 11, QFont.Weight.Bold))
            painter.drawText(QRectF(cx - 22.0 + gx, cy - 14.0 + gy, 44.0, 22.0), Qt.AlignmentFlag.AlignCenter, "\u092C\u094D\u0930\u0939\u094D\u092E\u093E")

            # Tiny breathing status beacon directly below text
            dot_alpha = min(255, int((150 + breath * 105) * hover_boost))
            dot_color = QColor(ar, ag, ab, dot_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QPointF(cx + gx, cy + 12.0 + gy), 2.0, 2.0)

        painter.end()

    def show_at(self, x: int | None = None, y: int | None = None):
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 18
            y = screen.bottom() - self.height() - 90
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_state(self, state: str, detail: str | None = None):
        old_state = self._state
        self._state = (state or "idle").strip().lower()
        self._status_line = (detail or self._default_status()).strip() or self._default_status()
        self._apply_state_style()

        # Acoustic cyber cues on state changes
        if self._state != old_state:
            try:
                from sound_manager import SoundManager
                sm = SoundManager.instance()
                if self._state == "listening":
                    sm.play_listening_start()
                elif self._state == "idle" and old_state in ("thinking", "executing", "processing"):
                    sm.play_mission_complete()
                elif self._state in ("thinking", "executing", "processing"):
                    sm.play_telemetry_chirp()
            except Exception:
                pass

    def _default_status(self) -> str:
        return {
            "idle": "Ready",
            "listening": "Listening",
            "thinking": "Thinking...",
            "speaking": "Speaking",
            "executing": "Executing task...",
            "processing": "Processing...",
            "muted": "Muted",
            "error": "Error",
        }.get(self._state, "Ready")

    def _apply_state_style(self):
        self.setToolTip(
            f"Nexus Core ({self._status_line})\n"
            "• Single-click: Chat Workspace\n"
            "• Double-click: Open Full App\n"
            "• Drag: Move (Spring Snap)"
        )
        self.update()

    def _show_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(14, 16, 22, 248);
                color: #FFFFFF;
                border: 1px solid rgba(0, 229, 255, 0.45);
                border-radius: 12px;
                padding: 6px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 7px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(0, 229, 255, 0.20);
                color: #00e5ff;
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255, 255, 255, 0.10);
                margin: 4px 6px;
            }}
        """)

        open_full = QAction("Open Nexus Core (Full App)", self)
        open_full.triggered.connect(lambda: self.action_requested.emit("open_app"))
        menu.addAction(open_full)

        open_ws = QAction("Open Chat Workspace", self)
        open_ws.triggered.connect(lambda: self.action_requested.emit("open_workspace"))
        menu.addAction(open_ws)

        menu.addSeparator()

        voice_mode = QAction("Toggle Voice Mode", self)
        voice_mode.triggered.connect(lambda: self.action_requested.emit("voice_mode"))
        menu.addAction(voice_mode)

        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(lambda: self.action_requested.emit("settings"))
        menu.addAction(settings_act)

        menu.addSeparator()

        hide_act = QAction("Hide Floating Icon", self)
        hide_act.triggered.connect(self.hide)
        menu.addAction(hide_act)

        quit_act = QAction("Quit Nexus", self)
        quit_act.triggered.connect(lambda: self.action_requested.emit("quit"))
        menu.addAction(quit_act)

        menu.exec(global_pos)

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if hasattr(self, "_spring_timer") and self._spring_timer.isActive():
                self._spring_timer.stop()
            self._dragging = False
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._single_timer.stop()
            self._drag_button = event.button()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.globalPosition().toPoint()
        # Calculate subtle cursor parallax
        local_x = pos.x() - self.x() - self.width() / 2.0
        local_y = pos.y() - self.y() - self.height() / 2.0
        self._gaze_x = max(-2.5, min(2.5, local_x * 0.05))
        self._gaze_y = max(-2.5, min(2.5, local_y * 0.05))

        if event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton):
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos = pos - self._drag_offset
                new_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
                new_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
                self.move(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
            event.accept()
            return
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragging:
                self._single_timer.start(200)
            else:
                # Magnetic Spring Edge-Snap
                screen = QApplication.primaryScreen().availableGeometry()
                mid_x = (screen.left() + screen.right()) / 2.0
                if self.x() < mid_x:
                    self._target_snap_x = screen.left() + 16
                else:
                    self._target_snap_x = screen.right() - self.width() - 16
                self._spring_timer.start(16)
            self._dragging = False
            self._drag_button = None
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            if not self._dragging:
                self._show_menu(event.globalPosition().toPoint())
            self._dragging = False
            self._drag_button = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._single_timer.stop()
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_state_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._gaze_x = 0.0
        self._gaze_y = 0.0
        self._apply_state_style()
        super().leaveEvent(event)



class FloatingGestureCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)
        
        self.btn = QPushButton("🖐 Gestures")
        self.btn.setFixedSize(100, 36)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setStyleSheet(
            "QPushButton { background: #0c0e12; color: #ffffff; border: 1px solid rgba(0, 229, 255, 0.20); border-radius: 8px; font-weight: bold; }"
            "QPushButton:hover { color: #00e5ff; border: 1px solid #00e5ff; }"
        )
        self.btn.clicked.connect(self.toggle_preview)
        
        btn_lay = QHBoxLayout()
        btn_lay.addStretch(1)
        btn_lay.addWidget(self.btn)
        self.lay.addLayout(btn_lay)
        
        self.preview = GestureCameraPreview()
        self.preview.setFixedSize(280, 210)
        self.preview.hide()
        
        self.lay.addWidget(self.preview)
        
    def toggle_preview(self):
        if self.preview.isVisible():
            self.preview.hide()
            self.preview._stop_camera()
            self.btn.setStyleSheet(
                "QPushButton { background: #0c0e12; color: #ffffff; border: 1px solid rgba(0, 229, 255, 0.20); border-radius: 8px; font-weight: bold; }"
                "QPushButton:hover { color: #00e5ff; border: 1px solid #00e5ff; }"
            )
        else:
            self.preview.show()
            self.preview._start_camera()
            self.btn.setStyleSheet(
                "QPushButton { background: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid #00e5ff; border-radius: 8px; font-weight: bold; }"
                "QPushButton:hover { background: rgba(0, 229, 255, 0.25); }"
            )
        self.adjustSize()
        if self.window() and hasattr(self.window(), 'resizeEvent'):
            self.window().resizeEvent(None)


