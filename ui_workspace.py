"""UI components

Split from ui.py. The namespace bridge preserves existing UI integrations
while this area is incrementally decoupled into explicit dependencies.
"""
import ui as _ui
globals().update({name: value for name, value in vars(_ui).items() if not name.startswith("__")})

class TaskDock(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskDock")
        self._collapsed = False
        self._expanded_w = 392
        self._collapsed_w = 44
        self.setFixedWidth(self._expanded_w)
        self.setStyleSheet(
            f"""
            QFrame#TaskDock {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(7, 8, 12, 250),
                    stop:1 rgba(3, 4, 6, 245));
                border-left: 1px solid rgba(0, 229, 255, 0.55);
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title = QLabel("TASK WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()

        self._toggle_btn = QPushButton(">")
        self._toggle_btn.setFixedSize(34, 34)
        self._toggle_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(12,14,18,245); color: {C.WHITE}; border: 1px solid {C.BORDER_B}; border-radius: 8px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.PRI}; }}"
        )
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._toggle_btn)
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.PRI_GHO}; margin: 2px 0;")
        root.addWidget(sep)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._mini_hint = QLabel("TASK")
        self._mini_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mini_hint.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._mini_hint.setStyleSheet(
            f"color: {C.PRI}; background: rgba(12,14,18,245); border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 10px 4px;"
        )
        self._mini_hint.setVisible(False)
        lay.addWidget(self._mini_hint)

        root.addWidget(self._content, stretch=1)
        self._apply_state()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        self._apply_state()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._content.setVisible(not self._collapsed)
        self._mini_hint.setVisible(self._collapsed)
        self._toggle_btn.setText(">" if self._collapsed else "<")
        self._toggle_btn.setToolTip("Open task workspace" if self._collapsed else "Collapse task workspace")
        self._title.setVisible(not self._collapsed)
        self.setFixedWidth(self._collapsed_w if self._collapsed else self._expanded_w)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._task_card.start_workspace(command, plan, source)
        if self._collapsed:
            return

    def update_workspace(self, **kwargs):
        self._task_card.update_workspace(**kwargs)

    def finish_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._task_card.finish_workspace(result, status, percent)

    def clear_workspace(self):
        self._task_card.clear_workspace()


class WorkspaceSidebar(QWidget):
    command_submitted = pyqtSignal(str)
    close_requested = pyqtSignal()
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._collapsed = True
        self._expanded_w = 468
        self._target_h = 860
        self._active_conversation_id: str | None = None
        self._store = workspace_store()
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._panel = QFrame(self)
        self._panel.setObjectName("WorkspaceSidebarPanel")
        self._panel.setStyleSheet(
            """
            QFrame#WorkspaceSidebarPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                stop:0.55 rgba(10, 12, 18, 210),
                stop:1 rgba(5, 7, 11, 200));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 22px;
            }
            """
        )
        try:
            shadow = QGraphicsDropShadowEffect(self._panel)
            shadow.setBlurRadius(35)
            shadow.setColor(QColor(0, 0, 0, 72))
            shadow.setOffset(0, 12)
            self._panel.setGraphicsEffect(shadow)
        except Exception:
            pass
        root = QHBoxLayout(self._panel)
        root.setContentsMargins(14, 14, 12, 14)
        root.setSpacing(10)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content = QVBoxLayout(self._content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._title = QLabel("NEXUS EVO WORKSPACE")
        self._title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        header.addWidget(self._title)
        header.addStretch()
        self._close_btn = QPushButton("✕")
        self._close_btn.setToolTip("Close Workspace")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 15px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(255, 82, 82, 0.25);
                color: #FF5252;
                border: 1px solid rgba(255, 82, 82, 0.50);
            }
            """
        )
        self._close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self._close_btn)
        content.addLayout(header)

        self._tab_row = QHBoxLayout()
        self._tab_row.setSpacing(8)
        self._chat_tab_btn = self._make_tab_button("CHAT", True)
        self._history_tab_btn = self._make_tab_button("HISTORY", False)
        self._chat_tab_btn.clicked.connect(lambda: self._set_tab(0))
        self._history_tab_btn.clicked.connect(lambda: self._set_tab(1))
        self._tab_row.addWidget(self._chat_tab_btn)
        self._tab_row.addWidget(self._history_tab_btn)
        self._tab_row.addStretch(1)
        content.addLayout(self._tab_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_history_tab())
        content.addWidget(self._stack, 1)

        root.addWidget(self._content, stretch=1)

        self._panel.hide()
        self.hide()
        self._set_tab(0)
        self._ensure_active_conversation()
        self._load_active_conversation()
        self._refresh_history()
        self._apply_state()

    def _make_tab_button(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setStyleSheet(self._tab_style(active))
        return btn

    def _tab_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: rgba(0, 229, 255,0.16);
                    color: #FFFFFF;
                    border: 1px solid rgba(0, 229, 255,180);
                    border-radius: 10px;
                    padding: 0 14px;
                }
            """
        return """
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.82);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255,0.08);
                border: 1px solid rgba(0, 229, 255,120);
            }
        """

    def _set_tab(self, index: int):
        index = 0 if index == 0 else 1
        self._stack.setCurrentIndex(index)
        self._chat_tab_btn.setStyleSheet(self._tab_style(index == 0))
        self._history_tab_btn.setStyleSheet(self._tab_style(index == 1))
        self._chat_tab_btn.setChecked(index == 0)
        self._history_tab_btn.setChecked(index == 1)
        if index == 1:
            self._history_search.setFocus(Qt.FocusReason.TabFocusReason)

    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._task_card = TaskCard()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(0, 229, 255,0.05);
                border: 1px solid rgba(0, 229, 255,0.24);
                border-radius: 12px;
            }
            """
        )
        mem_lay = QVBoxLayout(self._memory_frame)
        mem_lay.setContentsMargins(12, 10, 12, 10)
        mem_lay.setSpacing(6)
        mem_title = QLabel("Using Memory:")
        mem_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        mem_title.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._memory_items = QLabel("")
        self._memory_items.setWordWrap(True)
        self._memory_items.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        mem_lay.addWidget(mem_title)
        mem_lay.addWidget(self._memory_items)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        lay.addWidget(self._feed, 1)

        # Sleek modern chat input container for Workspace
        input_container = QFrame()
        input_container.setStyleSheet(
            f"QFrame {{ "
            f"  background: rgba(14, 17, 24, 0.75); "
            f"  border: 1px solid rgba(0, 229, 255, 0.35); "
            f"  border-radius: 14px; "
            f"}}"
        )
        input_row = QHBoxLayout(input_container)
        input_row.setContentsMargins(10, 6, 10, 6)
        input_row.setSpacing(8)

        self._attach_btn = QPushButton("📎")
        self._attach_btn.setFixedSize(30, 30)
        self._attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach_btn.setToolTip("Attach file")
        self._attach_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.WHITE}; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; }}"
        )
        self._attach_btn.clicked.connect(self.attach_requested.emit)
        input_row.addWidget(self._attach_btn)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Nexus Core...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {C.WHITE}; border: none; padding: 2px 4px; selection-background-color: rgba(0, 229, 255, 0.25); }}"
        )
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(30, 30)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Voice")
        self._mic_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.WHITE}; border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; }}"
        )
        self._mic_btn.clicked.connect(self.mic_requested.emit)
        input_row.addWidget(self._mic_btn)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(32, 30)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setToolTip("Send message (Enter)")
        self._send_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(0, 229, 255, 0.25); color: {C.PRI}; border: 1px solid rgba(0, 229, 255, 0.50); border-radius: 8px; font-weight: bold; font-size: 13px; }}"
            f"QPushButton:hover {{ background: rgba(0, 229, 255, 0.45); color: #FFFFFF; border-color: {C.PRI}; }}"
        )
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        lay.addWidget(input_container)

        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._history_search = QLineEdit()
        self._history_search.setPlaceholderText("Search conversations...")
        self._history_search.setFont(QFont("Segoe UI", 10))
        self._history_search.setFixedHeight(38)
        self._history_search.setStyleSheet(
            """
            QLineEdit {
                background: rgba(10,11,14,205);
                color: #FFFFFF;
                border: 1px solid rgba(0, 229, 255,100);
                border-radius: 12px;
                padding: 0 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 229, 255,190);
            }
            """
        )
        self._history_search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._history_search)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 229, 255,0.45);
                border-radius: 4px;
                min-height: 24px;
            }
            """
        )
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    def _ensure_active_conversation(self, first_message: str | None = None) -> str:
        convo_id = self._active_conversation_id
        if convo_id:
            convo = self._store.get_conversation(convo_id)
            if convo:
                return convo_id
        convo_id = self._store.ensure_active_conversation(first_message or "")
        self._active_conversation_id = convo_id
        return convo_id

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.58); background: transparent; letter-spacing: 1px;")
        return lbl

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._history_search.text().strip() if hasattr(self, "_history_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        current = self._active_conversation_id
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet("color: rgba(255,255,255,0.60); background: transparent;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                widget = HistoryConversationItem(
                    item["id"],
                    item["title"],
                    _fmt_time_stamp(item["updatedAt"]),
                    pinned=bool(item["pinned"]),
                )
                if item["id"] == current:
                    widget.setStyleSheet(
                        """
                        QFrame#HistoryConversationItem {
                            background: rgba(0, 229, 255,0.10);
                            border: 1px solid rgba(0, 229, 255,0.55);
                            border-radius: 10px;
                        }
                        QFrame#HistoryConversationItem:hover {
                            background: rgba(0, 229, 255,0.14);
                            border: 1px solid rgba(0, 229, 255,0.70);
                        }
                        """
                    )
                widget.clicked.connect(self._load_conversation)
                self._history_layout.addWidget(widget)
            self._history_layout.addSpacing(4)
        self._history_layout.addStretch(1)

    def _show_memory_banner(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_items.setText("")
            self._memory_frame.hide()
            return
        self._memory_items.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memory_banner(self):
        self._memory_items.setText("")
        self._memory_frame.hide()

    def _load_active_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])
            self._active_conversation_id = convo_id
            self._hide_memory_banner()

    def _load_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _new_conversation(self):
        self._active_conversation_id = self._store.create_conversation("New Conversation")
        self._feed.clear_messages()
        self._hide_memory_banner()
        self._refresh_history()
        self._set_tab(0)

    def _clear_current_conversation(self):
        self._new_conversation()

    def _rename_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        current = (convo or {}).get("title") or "Conversation"
        title, ok = QInputDialog.getText(self, "Rename Conversation", "Conversation title:", text=current)
        if ok and title.strip():
            self._store.rename_conversation(convo_id, title.strip())
            self._refresh_history()

    def _export_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        title = (convo or {}).get("title") or "conversation"
        default = str(BASE_DIR / "downloads" / f"{title}.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export Conversation", default, "JSON Files (*.json)")
        if not path:
            return
        try:
            self._store.export_conversation(convo_id, path)
        except Exception:
            pass

    def _pin_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        convo = self._store.get_conversation(convo_id)
        pinned = not bool((convo or {}).get("pinned"))
        self._store.pin_conversation(convo_id, pinned)
        self._refresh_history()

    def _delete_current_conversation(self):
        convo_id = self._ensure_active_conversation()
        self._store.delete_conversation(convo_id)
        self._active_conversation_id = None
        self._new_conversation()

    def show_at(self):
        self.show_workspace(animate=False)

    def reposition(self):
        if not self.isVisible():
            return
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self._expanded_w + 1
        y = screen.top() + 18
        h = max(640, screen.height() - 36)
        self.setGeometry(x, y, self._expanded_w, h)
        self._target_h = h
        self._panel.setGeometry(0, 0, self._expanded_w, h)

    def _dock_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() - w + 1
        return QRectF(x, y, w, h)

    def _collapsed_rect(self) -> QRectF:
        screen = QApplication.primaryScreen().availableGeometry()
        h = max(640, screen.height() - 36)
        y = screen.top() + 18
        w = self._expanded_w
        x = screen.right() + 8
        return QRectF(x, y, w, h)

    def focus_input(self):
        self._set_tab(0)
        if hasattr(self, "_input") and self._input.isVisible():
            self._input.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_workspace(self, animate: bool = True):
        self._collapsed = False
        self._panel.show()
        self._content.show()
        dock = self._dock_rect()
        start = self._collapsed_rect() if animate else dock
        self.setGeometry(start.toRect())
        self.show()
        self.raise_()
        self.activateWindow()
        self._apply_state()
        if animate:
            self._anim.stop()
            self._anim.setStartValue(start.toRect())
            self._anim.setEndValue(dock.toRect())
            self._anim.start()
        else:
            self.setGeometry(dock.toRect())
        self._panel.setGeometry(0, 0, self.width(), self.height())
        QTimer.singleShot(100, self.focus_input)

    def hide_workspace(self, animate: bool = True):
        self._collapsed = True
        if not self.isVisible():
            self._panel.hide()
            self.hide()
            return
        if animate:
            dock = self.geometry()
            end = self._collapsed_rect()
            self._anim.stop()
            self._anim.setStartValue(dock)
            self._anim.setEndValue(end.toRect())
            self._anim.finished.connect(self._hide_after_anim)
            self._anim.start()
        else:
            self._hide_after_anim()

    def _hide_after_anim(self):
        try:
            self._anim.finished.disconnect(self._hide_after_anim)
        except Exception:
            pass
        self._panel.hide()
        self.hide()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        if bool(collapsed):
            self.hide_workspace(animate=True)
        else:
            self.show_workspace(animate=True)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _apply_state(self):
        self._panel.setVisible(not self._collapsed)
        self._content.setVisible(not self._collapsed)
        if self.isVisible() and not self._collapsed:
            self.reposition()

    def append_log(self, text: str):
        raw = (text or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low.startswith(("you:", "nexus core:")):
            return
        if low.startswith("sys:"):
            self.record_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip(), "source": "local"})

    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text:
            return

        now = time.time()
        if not hasattr(self, "_last_chat_events"):
            self._last_chat_events = []
        for prev_role, prev_text, prev_time in self._last_chat_events[-6:]:
            if prev_role == role and prev_text == text and (now - prev_time < 2.5):
                return
        self._last_chat_events.append((role, text, now))
        if len(self._last_chat_events) > 20:
            self._last_chat_events = self._last_chat_events[-10:]

        attachments = data.get("attachments") or []
        stamp = data.get("timestamp")
        convo_id = data.get("conversation_id") or self._active_conversation_id
        if role == "user":
            self._feed.add_message("user", "You", text, _fmt_time_stamp(stamp), attachments=attachments)
            memories = self._store.search_memories(text)
            self._show_memory_banner(memories)
        elif role == "assistant":
            self._feed.add_message("assistant", "Nexus Core", text, _fmt_time_stamp(stamp), attachments=attachments, animate=True)
            self._hide_memory_banner()
        elif role == "system":
            self._feed.add_message("system", "System", text, _fmt_time_stamp(stamp), attachments=attachments, event_type=text)
        elif role == "file":
            self._feed.add_message("file", "Files", text, _fmt_time_stamp(stamp), attachments=attachments)
        self._refresh_history()

    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            command = data.get("command") or ""
            plan = data.get("plan") or []
            plan_text = plan if isinstance(plan, str) else "\n".join(f"• {item}" for item in plan) if plan else ""
            self._task_card.show()
            self._task_card.start_workspace(command, plan, data.get("source") or "local")
            # Intentionally do not post a 'Task started' system message to the activity feed
            # because the workspace UI already shows the task status.
        elif action == "update":
            self._task_card.show()
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            chunks = [data.get("status") or "", data.get("output") or "", data.get("footer") or ""]
            text = "\n".join(chunk for chunk in chunks if chunk)
            if text:
                self.record_chat_event({"role": "system", "text": text, "source": data.get("source") or "local"})
        elif action == "finish":
            self._task_card.show()
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or "Task completed.",
                int(data.get("percent") or 100),
            )
            self.record_chat_event({
                "role": "system",
                "text": data.get("result") or data.get("output") or "Done.",
                "source": data.get("source") or "local",
            })
            QTimer.singleShot(4000, self._task_card.hide)
        elif action == "clear":
            self._task_card.clear_workspace()

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._ensure_active_conversation(text)
        self.command_submitted.emit(text)


class InlineChatWorkspace(QFrame):
    command_submitted = pyqtSignal(str)
    attach_requested = pyqtSignal()
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InlineChatWorkspace")
        self._store = workspace_store()
        self._active_conversation_id: str | None = None
        self.setStyleSheet(
            """
            QFrame#InlineChatWorkspace {
                background: transparent;
                border: none;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        tabs = QHBoxLayout()
        tabs.setContentsMargins(0, 0, 0, 4)
        tabs.setSpacing(8)
        self._chat_btn = self._mk_tab("CHAT", True)
        self._history_btn = self._mk_tab("HISTORY", False)
        self._chat_btn.clicked.connect(lambda: self._set_tab(0))
        self._history_btn.clicked.connect(lambda: self._set_tab(1))
        tabs.addWidget(self._chat_btn)
        tabs.addWidget(self._history_btn)
        tabs.addStretch(1)
        root.addLayout(tabs)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_tab())
        self._stack.addWidget(self._build_history_tab())
        root.addWidget(self._stack, 1)

        self._set_tab(0)
        self._ensure_conversation()
        self._load_active_conversation()
        self._refresh_history()

    def _mk_tab(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.82);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255,0.08);
                border: 1px solid rgba(0, 229, 255,0.30);
            }
            """
        )
        return btn

    def _set_tab(self, index: int):
        self._stack.setCurrentIndex(0 if index == 0 else 1)
        self._chat_btn.setChecked(index == 0)
        self._history_btn.setChecked(index == 1)
        if index == 0:
            self._chat_btn.setStyleSheet("""
                QPushButton { background: rgba(0, 229, 255,0.16); color: #FFFFFF; border: 1px solid rgba(0, 229, 255,180); border-radius: 10px; padding: 0 14px; }
            """)
            self._history_btn.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.82); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 14px; }
                QPushButton:hover { background: rgba(0, 229, 255,0.08); border: 1px solid rgba(0, 229, 255,0.30); }
            """)
        else:
            self._history_btn.setStyleSheet("""
                QPushButton { background: rgba(0, 229, 255,0.16); color: #FFFFFF; border: 1px solid rgba(0, 229, 255,180); border-radius: 10px; padding: 0 14px; }
            """)
            self._chat_btn.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.82); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0 14px; }
                QPushButton:hover { background: rgba(0, 229, 255,0.08); border: 1px solid rgba(0, 229, 255,0.30); }
            """)

    def _build_chat_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        today_bar = QHBoxLayout()
        today_bar.addStretch()
        today_pill = QLabel("Today")
        today_pill.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        today_pill.setStyleSheet("""
            QLabel {
                background: rgba(0, 229, 255, 0.12);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 12px;
                padding: 4px 14px;
            }
        """)
        today_bar.addWidget(today_pill)
        today_bar.addStretch()
        lay.addLayout(today_bar)

        self._task_card = TaskCard()
        self._task_card.hide()
        lay.addWidget(self._task_card)

        self._memory_frame = QFrame()
        self._memory_frame.setVisible(False)
        self._memory_frame.setStyleSheet("""
            QFrame {
                background: rgba(0, 229, 255,0.05);
                border: 1px solid rgba(0, 229, 255,0.24);
                border-radius: 12px;
            }
        """)
        mlay = QVBoxLayout(self._memory_frame)
        mlay.setContentsMargins(12, 10, 12, 10)
        mlay.setSpacing(6)
        title = QLabel("Using Memory:")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._memory_lbl = QLabel("")
        self._memory_lbl.setWordWrap(True)
        self._memory_lbl.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        mlay.addWidget(title)
        mlay.addWidget(self._memory_lbl)
        lay.addWidget(self._memory_frame)

        self._feed = ConversationFeed()
        lay.addWidget(self._feed, 1)

        input_container = QFrame()
        input_container.setStyleSheet(
            f"QFrame {{ "
            f"  background: rgba(14, 17, 24, 0.40); "
            f"  border: 1px solid rgba(0, 229, 255, 0.32); "
            f"  border-radius: 12px; "
            f"}}"
        )
        input_row = QHBoxLayout(input_container)
        input_row.setContentsMargins(8, 6, 8, 6)
        input_row.setSpacing(6)

        self._attach_btn = QPushButton("📎")
        self._attach_btn.setFixedSize(28, 28)
        self._attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach_btn.setToolTip("Attach file")
        self._attach_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.WHITE}; border: none; font-size: 13px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; }}"
        )
        self._attach_btn.clicked.connect(self.attach_requested.emit)
        input_row.addWidget(self._attach_btn)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Nexus Core...")
        self._input.setFont(QFont("Segoe UI", 10))
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {C.WHITE}; border: none; padding: 0 4px; selection-background-color: rgba(0, 229, 255, 0.25); }}"
        )
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(28, 28)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Voice")
        self._mic_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.WHITE}; border: none; font-size: 13px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; }}"
        )
        self._mic_btn.clicked.connect(self.mic_requested.emit)
        input_row.addWidget(self._mic_btn)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(30, 28)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setToolTip("Send message")
        self._send_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(0, 229, 255, 0.22); color: {C.PRI}; border: 1px solid rgba(0, 229, 255, 0.45); border-radius: 7px; font-weight: bold; font-size: 13px; }}"
            f"QPushButton:hover {{ background: rgba(0, 229, 255, 0.40); color: #FFFFFF; border-color: {C.PRI}; }}"
        )
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        lay.addWidget(input_container)

        footer = QHBoxLayout()
        footer.setContentsMargins(4, 2, 4, 2)
        self._footer_status = QLabel("Nexus Core is ready")
        self._footer_status.setFont(QFont("Segoe UI", 8))
        self._footer_status.setStyleSheet("color: rgba(255, 255, 255, 0.55); background: transparent;")
        footer.addWidget(self._footer_status)
        footer.addStretch(1)

        lay.addLayout(footer)

        return page

    def set_audio_level(self, level: float):
        pass

    def set_state(self, state: str):
        if hasattr(self, "_footer_status") and self._footer_status:
            status_text = {
                "listening": "Listening to your voice...",
                "speaking": "Nexus Core is speaking...",
                "thinking": "Synthesizing response...",
                "executing": "Executing task...",
                "working": "Processing request...",
                "muted": "Microphone muted",
            }.get((state or "").lower(), "Nexus Core is ready")
            self._footer_status.setText(status_text)

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations...")
        self._search.setFont(QFont("Segoe UI", 10))
        self._search.setFixedHeight(38)
        self._search.setStyleSheet("QLineEdit { background: rgba(10,11,14,205); color: #FFFFFF; border: 1px solid rgba(0, 229, 255,100); border-radius: 12px; padding: 0 12px; }")
        self._search.textChanged.connect(self._refresh_history)
        lay.addWidget(self._search)
        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch(1)
        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return page

    def _ensure_conversation(self, first_message: str | None = None):
        if self._active_conversation_id:
            convo = self._store.get_conversation(self._active_conversation_id)
            if convo:
                return self._active_conversation_id
        self._active_conversation_id = self._store.ensure_active_conversation(first_message or "")
        return self._active_conversation_id

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_history(self, *_):
        search = self._search.text().strip() if hasattr(self, "_search") else ""
        self._clear_layout(self._history_layout)
        groups = self._store.grouped_conversations(search)
        if not groups:
            empty = QLabel("No conversations yet.")
            empty.setStyleSheet("color: rgba(255,255,255,0.60); background: transparent;")
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch(1)
            return
        for group_name, items in groups.items():
            self._history_layout.addWidget(self._group_label(group_name))
            for item in items:
                card = HistoryConversationItem(item["id"], item["title"], _fmt_time_stamp(item["updatedAt"]), pinned=bool(item["pinned"]))
                card.clicked.connect(self._open_conversation)
                self._history_layout.addWidget(card)
        self._history_layout.addStretch(1)

    def _group_label(self, title: str) -> QLabel:
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: rgba(255,255,255,0.58); background: transparent; letter-spacing: 1px;")
        return lbl

    def _show_memories(self, memories: list[dict[str, object]]):
        texts = [str(m.get("content") or "").strip() for m in memories if str(m.get("content") or "").strip()]
        if not texts:
            self._memory_lbl.setText("")
            self._memory_frame.hide()
            return
        self._memory_lbl.setText("• " + "\n• ".join(texts[:4]))
        self._memory_frame.show()

    def _hide_memories(self):
        self._memory_lbl.setText("")
        self._memory_frame.hide()

    def _open_conversation(self, conversation_id: str):
        convo = self._store.get_conversation(conversation_id)
        if not convo:
            return
        self._active_conversation_id = conversation_id
        self._store.set_active_conversation_id(conversation_id)
        self._feed.load_messages(convo.get("messages") or [])
        self._hide_memories()
        self._refresh_history()
        self._set_tab(0)

    def _load_active_conversation(self):
        convo_id = self._ensure_conversation()
        convo = self._store.get_conversation(convo_id)
        if convo:
            self._feed.load_messages(convo.get("messages") or [])
        self._refresh_history()

    def record_chat_event(self, event: object):
        data = event if isinstance(event, dict) else {}
        role = (data.get("role") or "").strip().lower()
        text = (data.get("text") or data.get("content") or "").strip()
        if not role or not text:
            return

        now = time.time()
        if not hasattr(self, "_last_chat_events"):
            self._last_chat_events = []
        for prev_role, prev_text, prev_time in self._last_chat_events[-6:]:
            if prev_role == role and prev_text == text and (now - prev_time < 2.5):
                return
        self._last_chat_events.append((role, text, now))
        if len(self._last_chat_events) > 20:
            self._last_chat_events = self._last_chat_events[-10:]

        convo_id = data.get("conversation_id") or self._ensure_conversation(text if role == "user" else None)
        attachments = data.get("attachments") or []
        stamp = _fmt_time_stamp(data.get("timestamp"))
        if role == "user":
            self._store.record_chat("user", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("user", "You", text, stamp, attachments=attachments)
            self._show_memories(self._store.search_memories(text))
        elif role == "assistant":
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("assistant", "Nexus Core", text, stamp, attachments=attachments)
            self._hide_memories()
        elif role == "system":
            self._store.record_chat("system", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("system", "System", text, stamp, attachments=attachments)
        elif role == "file":
            self._store.record_chat("assistant", text, conversation_id=convo_id, attachments=attachments)
            self._feed.add_message("file", "Files", text, stamp, attachments=attachments)
        self._refresh_history()

    def append_log(self, text: str):
        raw = (text or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low.startswith("you:"):
            self.record_chat_event({"role": "user", "text": raw.split(":", 1)[1].strip()})
        elif low.startswith("nexus core:"):
            self.record_chat_event({"role": "assistant", "text": raw.split(":", 1)[1].strip()})
        elif low.startswith("sys:"):
            self.record_chat_event({"role": "system", "text": raw.split(":", 1)[1].strip()})
        elif low.startswith("file:"):
            self.record_chat_event({"role": "file", "text": raw.split(":", 1)[1].strip()})
    def apply_task_workspace(self, event: object):
        data = event if isinstance(event, dict) else {}
        action = (data.get("action") or "update").strip().lower()
        if action == "start":
            command = data.get("command") or ""
            plan = data.get("plan") or []
            plan_text = plan if isinstance(plan, str) else "\n".join(f"• {item}" for item in plan) if plan else ""
            self._task_card.start_workspace(command, plan, data.get("source") or "local")
            # Do not emit a 'Task started' system event into the conversation feed.
        elif action == "update":
            self._task_card.update_workspace(
                title=data.get("title"),
                command=data.get("command"),
                plan=data.get("plan"),
                status=data.get("status"),
                output=data.get("output"),
                percent=data.get("percent"),
                footer=data.get("footer"),
            )
            chunks = [data.get("status") or "", data.get("output") or "", data.get("footer") or ""]
            text = "\n".join(chunk for chunk in chunks if chunk)
            if text:
                self.record_chat_event({"role": "system", "text": text, "source": data.get("source") or "local"})
        elif action == "finish":
            self._task_card.finish_workspace(
                data.get("result") or data.get("output") or "Done.",
                data.get("status") or "Task completed.",
                int(data.get("percent") or 100),
            )
            self.record_chat_event({
                "role": "system",
                "text": data.get("result") or data.get("output") or "Done.",
                "source": data.get("source") or "local",
            })
            QTimer.singleShot(4000, self._task_card.hide)
        elif action == "clear":
            self._task_card.clear_workspace()

    def _send(self):
        text = self._input.text().strip() if hasattr(self, "_input") else ""
        if not text:
            return
        self._input.clear()
        convo_id = self._ensure_conversation(text)
        self.record_chat_event({"role": "user", "text": text, "conversation_id": convo_id})
        self.command_submitted.emit(text)

    def focus_input(self):
        if hasattr(self, "_input"):
            self._input.setFocus()

    def new_conversation(self):
        self._active_conversation_id = self._store.create_conversation("New Conversation")
        self._feed.load_messages([])
        self._hide_memories()
        self._refresh_history()
        self._set_tab(0)
        self.focus_input()



