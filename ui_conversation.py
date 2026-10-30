"""Conversation rendering widgets and markdown helpers for Nexus Core."""

from __future__ import annotations

import html as html_lib
import os
import time
import re
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QScrollBar, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from ui_cards import C, ArtifactCard, AttachmentCard, MessageCard, TaskCard

def _fmt_time_stamp(value: int | float | None = None) -> str:
    try:
        from datetime import datetime
        if value is None:
            dt = datetime.now()
        else:
            stamp = float(value)
            if stamp > 10_000_000_000:
                stamp /= 1000.0
            dt = datetime.fromtimestamp(stamp)
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def _markdown_to_html(text: str, role: str = "assistant") -> str:
    safe = html_lib.escape(text or "")
    safe = safe.replace("\r\n", "\n").replace("\r", "\n")

    # Bold and Italic
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", safe)

    # Inline monospace code
    safe = re.sub(
        r"`([^`]+)`",
        r'<code style="padding:1px 6px; border-radius:4px; background:rgba(0,229,255,0.12); color:#00e5ff; font-family:Consolas,monospace; font-size:11px;">\1</code>',
        safe,
    )
    # Headers
    safe = re.sub(r"(?m)^### (.+)$", r'<h3 style="margin:8px 0 4px 0; font-size:13px; color:#ffffff;">\1</h3>', safe)
    safe = re.sub(r"(?m)^## (.+)$", r'<h2 style="margin:10px 0 6px 0; font-size:14px; color:#00e5ff;">\1</h2>', safe)
    safe = re.sub(r"(?m)^# (.+)$", r'<h1 style="margin:12px 0 8px 0; font-size:16px; color:#00e5ff;">\1</h1>', safe)
    # Bullet points
    safe = re.sub(r"(?m)^[\*\-•] (.+)$", r'<div style="margin-left:8px; line-height:1.5;">• \1</div>', safe)

    safe = safe.replace("\n", "<br>")
    accent = C.WHITE if role == "assistant" else C.TEXT
    return (
        f'<div style="color:{accent}; font-size:12px; line-height:1.5; white-space:normal;">'
        f"{safe}"
        "</div>"
    )


def _split_markdown_code_blocks(text: str) -> list[dict]:
    """Splits markdown text into alternating chunks of normal text and code blocks."""
    pattern = re.compile(r"```([a-zA-Z0-9_\-\+]*)\n?(.*?)```", re.DOTALL)
    chunks = []
    last_end = 0
    for match in pattern.finditer(text or ""):
        start, end = match.span()
        if start > last_end:
            chunks.append({"type": "text", "content": text[last_end:start]})
        lang = (match.group(1) or "").strip().upper() or "CODE"
        code = match.group(2) or ""
        chunks.append({"type": "code", "lang": lang, "content": code})
        last_end = end
    if last_end < len(text or ""):
        chunks.append({"type": "text", "content": text[last_end:]})
    return chunks


class CodeBlockWidget(QFrame):
    """
    Sleek Cyberpunk Code Block Container.
    Features:
    - Language badge (e.g. PYTHON, POWERSHELL, JSON, BASH, etc.)
    - 1-click '📋 Copy' button that copies snippet to clipboard and switches to '✓ Copied!'
    - Dark monospace styling with Consolas / JetBrains Mono font
    - Subtle neon border matching theme
    """
    def __init__(self, code: str, lang: str = "CODE", parent=None):
        super().__init__(parent)
        self._raw_code = (code or "").rstrip("\r\n")
        self._lang = (lang or "CODE").strip().upper()
        self.setObjectName("CodeBlockWidget")
        self.setStyleSheet("""
            QFrame#CodeBlockWidget {
                background: rgba(6, 8, 12, 245);
                border: 1px solid rgba(0, 229, 255, 0.28);
                border-radius: 10px;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # Header bar
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)

        # Code language badge
        lang_lbl = QLabel(self._lang)
        lang_lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        lang_lbl.setStyleSheet("""
            color: #00e5ff;
            background: rgba(0, 229, 255, 0.12);
            border: 1px solid rgba(0, 229, 255, 0.35);
            border-radius: 4px;
            padding: 2px 7px;
        """)
        head.addWidget(lang_lbl)
        head.addStretch(1)

        # Copy button
        self._copy_btn = QPushButton("📋 Copy")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setFixedHeight(22)
        self._copy_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.20);
                color: #00e5ff;
                border: 1px solid #00e5ff;
            }
        """)
        self._copy_btn.clicked.connect(self._copy_code)
        head.addWidget(self._copy_btn)
        lay.addLayout(head)

        # Monospace code view
        self._code_edit = QTextEdit()
        self._code_edit.setReadOnly(True)
        self._code_edit.setPlainText(self._raw_code)
        self._code_edit.setFont(QFont("Consolas", 9))
        self._code_edit.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: #e2e8f0;
                border: none;
                selection-background-color: rgba(0, 229, 255, 0.35);
            }
        """)
        line_count = len(self._raw_code.splitlines()) or 1
        h = max(38, min(260, line_count * 18 + 18))
        self._code_edit.setFixedHeight(h)
        lay.addWidget(self._code_edit)

    def _copy_code(self):
        try:
            QApplication.clipboard().setText(self._raw_code)
        except Exception:
            try:
                import pyperclip
                pyperclip.copy(self._raw_code)
            except Exception:
                pass
        self._copy_btn.setText("✓ Copied!")
        self._copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(55, 255, 95, 0.25);
                color: #37ff5f;
                border: 1px solid #37ff5f;
                border-radius: 6px;
                padding: 1px 8px;
            }
        """)
        QTimer.singleShot(2200, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self._copy_btn.setText("📋 Copy")
        self._copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.20);
                color: #00e5ff;
                border: 1px solid #00e5ff;
            }
        """)


class ChatBubble(QFrame):
    def __init__(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None, parent=None, animate: bool = False):
        super().__init__(parent)
        self._role = role
        self._full_text = text or ""
        self._typing_index = 0
        self._typing_timer: QTimer | None = None
        self.setObjectName("ChatBubble")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(1)
        max_w = 340
        if parent and hasattr(parent, "viewport"):
            max_w = max(200, int(parent.viewport().width() * 0.84))
        self.setMaximumWidth(max_w)
        if role == "user":
            self.setMinimumWidth(120)

        bg_style = (
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(20, 16, 12, 0.45), stop:1 rgba(10, 8, 5, 0.60)); border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 16px;"
            if role != "user"
            else "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 229, 255, 0.22), stop:1 rgba(210, 140, 0, 0.32)); border: 1px solid rgba(0, 229, 255, 0.55); border-radius: 16px;"
        )
        self.setStyleSheet(f"QFrame#ChatBubble {{ {bg_style} }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        if role == "assistant":
            avatar = _framed_logo(24, 24, bg="rgba(12,14,20,245)", border="rgba(0, 229, 255,0.50)", radius=12, inset=4)
            head.addWidget(avatar)
            name_lbl = QLabel(name or "Nexus Core")
            name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
            head.addWidget(name_lbl)
        elif role != "user":
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
            head.addWidget(name_lbl)
        elif role == "user":
            user_icon = QLabel("👤")
            user_icon.setFont(QFont("Segoe UI", 9))
            user_icon.setStyleSheet("color: #00e5ff; background: transparent;")
            head.addWidget(user_icon)
            name_lbl = QLabel(name or "You")
            name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
            head.addWidget(name_lbl)

        head.addStretch()

        time_lbl = QLabel(stamp)
        time_lbl.setFont(QFont("Segoe UI", 7))
        time_lbl.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
        head.addWidget(time_lbl)

        outer.addLayout(head)

        # Content container for rich text and code blocks
        self._content_container = QWidget()
        self._content_container.setStyleSheet("background: transparent;")
        self._content_lay = QVBoxLayout(self._content_container)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content_lay.setSpacing(6)
        outer.addWidget(self._content_container)

        self._render_text(text or "", final=not animate)

        if attachments:
            for attachment in attachments:
                title = str(attachment.get("name") or attachment.get("title") or attachment.get("path") or "Attachment")
                subtitle = str(attachment.get("path") or attachment.get("description") or "")
                outer.addWidget(ArtifactCard(title, file_type=Path(title).suffix.lstrip(".").upper() or "File", status="Attached", path=subtitle or title))

        if animate and role == "assistant":
            self._start_typing_animation()

    def _render_text(self, text: str, final: bool = True):
        # Clear previous children in _content_lay
        while self._content_lay.count():
            item = self._content_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # If mid-typing and no full code blocks yet, fast-render simple text
        if not final and "```" not in text:
            lbl = QLabel(_markdown_to_html(text or "", self._role))
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #f4f6f8; background: transparent;")
            self._content_lay.addWidget(lbl)
            return

        chunks = _split_markdown_code_blocks(text or "")
        for chunk in chunks:
            if chunk["type"] == "code":
                code_widget = CodeBlockWidget(code=chunk["content"], lang=chunk.get("lang", "CODE"))
                self._content_lay.addWidget(code_widget)
            else:
                body_str = chunk["content"].strip()
                if body_str:
                    lbl = QLabel(_markdown_to_html(body_str, self._role))
                    lbl.setTextFormat(Qt.TextFormat.RichText)
                    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction | Qt.TextInteractionFlag.LinksAccessibleByMouse)
                    lbl.setOpenExternalLinks(True)
                    lbl.setWordWrap(True)
                    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                    lbl.setStyleSheet("QLabel { background: transparent; border: none; color: #f4f6f8; padding: 0; margin: 0; }")
                    self._content_lay.addWidget(lbl)

    def _start_typing_animation(self):
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(14)
        self._typing_timer.timeout.connect(self._tick_typing)
        self._typing_timer.start()

    def _tick_typing(self):
        self._typing_index = min(len(self._full_text), self._typing_index + 3)
        snippet = self._full_text[:self._typing_index]
        self._render_text(snippet, final=False)
        if self._typing_index >= len(self._full_text):
            try:
                self._typing_timer.stop()
            except Exception:
                pass
            self._render_text(self._full_text, final=True)


class HistoryConversationItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, conversation_id: str, title: str, stamp: str, pinned: bool = False, parent=None):
        super().__init__(parent)
        self._conversation_id = conversation_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("HistoryConversationItem")
        self.setStyleSheet(
            """
            QFrame#HistoryConversationItem {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0, 229, 255,0.18);
                border-radius: 10px;
            }
            QFrame#HistoryConversationItem:hover {
                background: rgba(0, 229, 255,0.07);
                border: 1px solid rgba(0, 229, 255,0.32);
            }
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        icon = QLabel("B")
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: rgba(0, 229, 255,0.10); color: #00e5ff; border: 1px solid rgba(0, 229, 255,0.28); border-radius: 15px; font: 700 11pt 'Segoe UI';")
        lay.addWidget(icon)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        title_lbl = QLabel(title or "Conversation")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        row.addWidget(title_lbl)
        if pinned:
            pin = QLabel("PIN")
            pin.setStyleSheet("color: #37ff5f; background: transparent; font: 700 7pt 'Courier New';")
            row.addWidget(pin)
        row.addStretch()
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont("Segoe UI", 7))
        stamp_lbl.setStyleSheet("color: rgba(255,255,255,0.50); background: transparent;")
        row.addWidget(stamp_lbl)
        meta.addLayout(row)
        lay.addLayout(meta, 1)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._conversation_id)


class ConversationFeed(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
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
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(8)
        self._layout.addStretch(1) # Stretch at bottom pushes bubbles tightly to the top
        self.setWidget(self._content)
        self._empty_widget: QWidget | None = None
        self._message_count = 0

    def _ensure_empty_widget(self):
        if self._empty_widget is not None:
            return self._empty_widget
        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(0, 229, 255,0.16);
                border-radius: 14px;
            }
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 8px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255,0.08);
                border: 1px solid rgba(0, 229, 255,0.28);
            }
            """
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        title = QLabel("Try asking Nexus Core")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; background: transparent;")
        subtitle = QLabel("Create a presentation, analyze a screen, build a website, organize files, or run browser automation.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(255,255,255,0.64); background: transparent;")
        lay.addWidget(title)
        lay.addWidget(subtitle)
        grid = QGridLayout()
        grid.setSpacing(8)
        self._empty_widget_buttons = []
        for idx, suggestion in enumerate([
            "Create Presentation",
            "Analyze Screen",
            "Build Website",
            "Organize Downloads",
            "Browser Automation",
        ]):
            btn = QPushButton(suggestion)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, s=suggestion: self._emit_empty_suggestion(s))
            self._empty_widget_buttons.append(btn)
            grid.addWidget(btn, idx // 2, idx % 2)
        lay.addLayout(grid)
        self._empty_widget = frame
        return frame

    def _emit_empty_suggestion(self, text: str):
        root = self.parentWidget()
        while root is not None and not hasattr(root, "command_submitted"):
            root = root.parentWidget()
        if root is not None and hasattr(root, "command_submitted"):
            root.command_submitted.emit(text)

    def clear_messages(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._empty_widget:
                widget.deleteLater()
        if self._empty_widget is not None:
            self._empty_widget.hide()
        self._layout.addStretch(1)
        self._message_count = 0

    def add_message(self, role: str, name: str, text: str, stamp: str, attachments: list[dict] | None = None, animate: bool = False, event_type: str | None = None):
        vw = self.viewport().width()
        if hasattr(self, "_content") and self._content is not None and vw > 20:
            self._content.setFixedWidth(vw)
        if self._layout.count() and self._layout.itemAt(self._layout.count() - 1).spacerItem() is not None:
            self._layout.takeAt(self._layout.count() - 1)
        if role == "system":
            bubble = self._build_event_card(text, stamp, event_type=event_type)
            self._layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        elif role == "file":
            bubble = self._build_artifact_card(text, attachments=attachments, stamp=stamp)
            self._layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        elif role == "user":
            bubble = ChatBubble(role, name, text, stamp, attachments=attachments, parent=self, animate=animate)
            self._layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            bubble = ChatBubble(role, name, text, stamp, attachments=attachments, parent=self, animate=animate)
            self._layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self._layout.addStretch(1)
        self._message_count += 1
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _build_event_card(self, text: str, stamp: str, event_type: str | None = None) -> QWidget:
        low = (event_type or text or "").lower()
        title = "System Event"
        icon = "●"
        accent = "#00e5ff"
        if "discord" in low and "connected" in low:
            title, icon, accent = "Discord Connected", "◉", "#5865F2"
        elif "presentation" in low:
            title, icon, accent = "Presentation Generated", "▣", "#ff7a45"
        elif "website" in low:
            title, icon, accent = "Website Created", "⌂", "#37ff5f"
        elif "spreadsheet" in low:
            title, icon, accent = "Spreadsheet Generated", "▦", "#6fd6ff"
        elif "browser" in low:
            title, icon, accent = "Browser Automation Completed", "↗", "#ffbf00"
        elif "organ" in low and "file" in low:
            title, icon, accent = "File Organization Completed", "🗂", "#37ff5f"
        elif "screen" in low and "analysis" in low:
            title, icon, accent = "Screen Analysis Completed", "◫", "#6fd6ff"
        return EventCard(title, text, stamp, icon=icon, accent=accent, parent=self)

    def _build_artifact_card(self, text: str, attachments: list[dict] | None = None, stamp: str = "") -> QWidget:
        attachment = (attachments or [{}])[0] if attachments else {}
        path = str(attachment.get("path") or attachment.get("file") or attachment.get("name") or "").strip()
        title = str(attachment.get("name") or attachment.get("title") or Path(path).name or "Generated File").strip()
        suffix = Path(path or title).suffix.lstrip(".").upper() or (str(attachment.get("type") or "FILE")).upper()
        status = "Ready"
        return ArtifactCard(title, file_type=suffix, status=status, path=path or title, parent=self)

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def load_messages(self, messages: list[dict[str, Any]], max_display: int = 40):
        self.clear_messages()
        # Cap batch to recent messages to prevent UI thread freeze with large histories
        display_messages = messages[-max_display:] if len(messages) > max_display else messages
        for msg in display_messages:
            role = (msg.get("role") or "assistant").strip().lower()
            content = msg.get("content") or ""
            stamp = _fmt_time_stamp(msg.get("timestamp"))
            attachments = msg.get("attachments") or []
            name = {
                "user": "You",
                "assistant": "Nexus Core",
                "system": "System",
                "file": "Files",
            }.get(role, "Nexus Core")
            self.add_message(role, name, content, stamp, attachments=attachments, animate=False)
        self._sync_empty_state()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _sync_empty_state(self):
        if self._empty_widget is None:
            self._ensure_empty_widget()
        if self._message_count <= 0:
            if self._layout.indexOf(self._empty_widget) == -1:
                self._layout.insertWidget(0, self._empty_widget)
            self._empty_widget.show()
        else:
            if self._layout.indexOf(self._empty_widget) != -1:
                self._layout.removeWidget(self._empty_widget)
            self._empty_widget.hide()

    def has_messages(self) -> bool:
        return self._message_count > 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vw = self.viewport().width()
        if hasattr(self, "_content") and self._content is not None and vw > 20:
            self._content.setFixedWidth(vw)
            for i in range(self._layout.count()):
                w = self._layout.itemAt(i).widget()
                if w and isinstance(w, ChatBubble):
                    max_w = max(180, int(vw * 0.84))
                    w.setMaximumWidth(max_w)
                elif w and hasattr(w, "_fit_to_content"):
                    w._fit_to_content()
        QTimer.singleShot(0, self.scroll_to_bottom)
