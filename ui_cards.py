"""Reusable visual cards and the shared Nexus Core color palette."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

class C:
    # Nexus Core theme palette
    # Background: near-black with slight purple tint (deep space)
    BG        = "#0B0A14"
    # Surface: sidebar, cards, input bar
    PANEL     = "#141224"
    # Surface raised: hover states, popovers
    PANEL2    = "#1C1A33"
    # Slate purple: gradient start, selected items
    SLATE     = "#2B2347"
    # Teal: gradient end, secondary accent
    TEAL      = "#0E5560"
    # Bright teal: primary accent, links, active states
    ACC       = "#2FD1D9"
    # Secondary accent (dimmed bright teal)
    ACC2      = "#1FA3A8"
    # Ice blue: glow, core, key icons
    ICE       = "#D9F3FB"
    ICE_DIM   = "#A8CBD9"
    ICE_GHO   = "rgba(217, 243, 251, 0.15)"
    # Borders: faint blue-gray thin borders
    BORDER    = "rgba(43, 35, 71, 0.5)"
    BORDER_B  = "rgba(43, 35, 71, 0.8)"
    BORDER_A  = "rgba(217, 243, 251, 0.3)"
    # Text
    PRI       = "#E8EEF5"
    PRI_DIM   = "#8A93A6"
    PRI_GHO   = "rgba(232, 238, 245, 0.12)"
    TEXT      = "#E8EEF5"
    TEXT_DIM  = "#8A93A6"
    TEXT_MED  = "#B8C4D0"
    # Status colors
    GREEN     = "#2FD1D9"
    GREEN_D   = "#1FA3A8"
    RED       = "#D97A4B"
    MUTED_C   = "#2FD1D9"
    WHITE     = "#E8EEF5"
    DARK      = "#0B0A14"
    BAR_BG    = "#141224"
    # Gradient string for brand moments
    GRADIENT  = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B2347, stop:1 #0E5560)"
    GRADIENT_BRIGHT = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2FD1D9, stop:1 #0E5560)"
    _listeners: list = []

    @classmethod
    def register_listener(cls, callback):
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unregister_listener(cls, callback):
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def load_theme(cls, theme_hex: str):
        if not theme_hex.startswith("#") or len(theme_hex) != 7:
            # Fallback to predefined colors if it's not a hex or just a word
            if theme_hex.lower() == "blue": theme_hex = "#007aff"
            elif theme_hex.lower() == "green": theme_hex = "#37ff5f"
            elif theme_hex.lower() == "red": theme_hex = "#ff3b30"
            elif theme_hex.lower() == "ice": theme_hex = "#00e5ff"
            elif theme_hex.lower() == "white": theme_hex = "#ffffff"
            else: theme_hex = "#ffffff"
            
        import colorsys
        try:
            r = int(theme_hex[1:3], 16)
            g = int(theme_hex[3:5], 16)
            b = int(theme_hex[5:7], 16)
        except Exception:
            r, g, b = 255, 255, 255
            theme_hex = "#ffffff"
            
        h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        
        # Dim (darker by reducing l by 15%)
        l_dim = max(0.0, l - 0.15)
        r_dim, g_dim, b_dim = colorsys.hls_to_rgb(h, l_dim, s)
        hex_dim = f"#{int(r_dim*255):02x}{int(g_dim*255):02x}{int(b_dim*255):02x}"
        
        # Acc2 (lighter by increasing l by 15%)
        l_light = min(1.0, l + 0.15)
        r_light, g_light, b_light = colorsys.hls_to_rgb(h, l_light, s)
        hex_light = f"#{int(r_light*255):02x}{int(g_light*255):02x}{int(b_light*255):02x}"

        cls.PRI       = theme_hex
        cls.PRI_DIM   = hex_dim
        cls.PRI_GHO   = f"rgba({r}, {g}, {b}, 0.15)"
        cls.ACC       = "#00e5ff" if theme_hex.lower() in ("#ffffff", "#f4f6f8") else theme_hex
        cls.ACC2      = "#80ffff" if theme_hex.lower() in ("#ffffff", "#f4f6f8") else hex_light
        cls.MUTED_C   = "#00e5ff" if theme_hex.lower() in ("#ffffff", "#f4f6f8") else theme_hex
        cls.BORDER    = f"rgba({r}, {g}, {b}, 0.15)"
        cls.BORDER_B  = "rgba(0, 229, 255, 0.35)" if theme_hex.lower() in ("#ffffff", "#f4f6f8") else f"rgba({r}, {g}, {b}, 0.25)"
        cls.BORDER_A  = f"rgba({r}, {g}, {b}, 0.18)"

        for cb in list(cls._listeners):
            try:
                cb()
            except Exception:
                pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0â€“100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


class MessageCard(QFrame):
    def __init__(self, role: str, name: str, text: str, stamp: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MessageCard")
        accent_map = {
            "user": (C.BORDER_B, C.WHITE),
            "assistant": (C.PRI, C.PRI),
            "system": ("#4b8cff", "#4b8cff"),
            "file": ("#35c96d", "#35c96d"),
            "error": ("#ff8b3d", "#ff8b3d"),
        }
        border_col, left_col = accent_map.get(role, accent_map["system"])
        self.setStyleSheet(
            f"""
            QFrame#MessageCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13, 15, 20, 246),
                    stop:1 rgba(5, 6, 9, 238));
                border: 1px solid {border_col};
                border-left: 3px solid {left_col};
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        avatar = QLabel(name[:1].upper())
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        palette = {
            "user": ("#0d0f14", C.WHITE, C.BORDER_B),
            "assistant": ("#12090a", C.RED, C.PRI),
            "system": ("#101525", "#7cb7ff", "#4b8cff"),
            "file": ("#0f1410", C.GREEN, "#35c96d"),
            "error": ("#1a0f10", "#ffb074", "#ff8b3d"),
        }
        bg, fg, border = palette.get(role, palette["system"])
        avatar.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 17px;"
        )

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")

        time_lbl = QLabel(stamp)
        time_lbl.setFont(QFont("Segoe UI", 7))
        time_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(time_lbl)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setFont(QFont("Segoe UI", 9))
        text_color = {
            "user": C.TEXT,
            "assistant": C.WHITE,
            "system": C.TEXT_MED,
            "file": C.GREEN,
            "error": C.RED,
        }.get(role, C.TEXT)
        text_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")

        body.addLayout(top)
        body.addWidget(text_lbl)
        lay.addWidget(avatar)
        lay.addLayout(body)


class TaskCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskCard")
        self._active = False
        self._workspace_locked = False
        self.setStyleSheet(
            f"""
            QFrame#TaskCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                    stop:0.6 rgba(10, 12, 18, 210),
                    stop:1 rgba(5, 7, 11, 200));
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 16px;
            }}
            QFrame#TaskCard:hover {{
                border: 1px solid rgba(0, 229, 255, 0.28);
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self._title = QLabel("Task Workspace")
        self._title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {C.PRI}; background: transparent;")

        self._pct = QLabel("0%")
        self._pct.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._pct.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._title)
        row.addStretch()
        row.addWidget(self._pct)
        lay.addLayout(row)

        self._command_lbl = QLabel("Command: waiting for input")
        self._command_lbl.setWordWrap(True)
        self._command_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._command_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._command_lbl)

        self._plan_lbl = QLabel("Plan: Nexus Core will generate a task plan after you send a command.")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setFont(QFont("Segoe UI", 9))
        self._plan_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._plan_lbl)

        self._status_lbl = QLabel("Status: Idle")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._status_lbl)

        self._output_lbl = QLabel("Output: Ready to work.")
        self._output_lbl.setWordWrap(True)
        self._output_lbl.setFont(QFont("Segoe UI", 9))
        self._output_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._output_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.06);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {C.PRI};
                border-radius: 3px;
            }}
            """
        )
        lay.addWidget(self._bar)

        self._foot = QLabel("Working on it...")
        self._foot.setFont(QFont("Segoe UI", 9))
        self._foot.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._foot)

    def set_task(self, title: str, desc: str, percent: int):
        if self._workspace_locked:
            return
        if self._active:
            self.update_workspace(title=title, status=desc, percent=percent)
            return
        self._title.setText(title)
        self._status_lbl.setText(desc)
        self._output_lbl.setText(desc)
        self._plan_lbl.setText("Plan: Nexus Core will generate a task plan after you send a command.")
        self._command_lbl.setText("Command: waiting for input")
        self._pct.setText(f"{percent}%")
        self._bar.setValue(max(0, min(100, percent)))

    def _format_plan(self, plan: list[str] | str | None) -> str:
        if not plan:
            return "Plan: • Understand the request\n       • Execute the right tools\n       • Return the result"
        if isinstance(plan, str):
            text = plan.strip()
            return f"Plan: {text}" if text.lower().startswith("plan:") else f"Plan: {text}"
        items = [str(item).strip() for item in plan if str(item).strip()]
        if not items:
            return "Plan: • Understand the request\n       • Execute the right tools\n       • Return the result"
        return "Plan:\n" + "\n".join(f"• {item}" for item in items)

    def start_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._active = True
        self._workspace_locked = False
        self._title.setText("Task Workspace")
        self._command_lbl.setText(f"Command: {command or 'waiting for input'}")
        self._plan_lbl.setText(self._format_plan(plan))
        self._status_lbl.setText("Status: Planning task...")
        self._output_lbl.setText("Output: Waiting for execution.")
        self._pct.setText("8%")
        self._bar.setValue(8)
        self._foot.setText(f"Source: {source}")
        # self.show() intentionally removed to prevent flashing on quick/normal chats

    def update_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                         status: str | None = None, output: str | None = None, percent: int | None = None,
                         footer: str | None = None):
        if title:
            self._title.setText(title)
        if command:
            self._command_lbl.setText(f"Command: {command}")
        if plan is not None:
            self._plan_lbl.setText(self._format_plan(plan))
        if status:
            self._status_lbl.setText(f"Status: {status}" if not status.lower().startswith("status:") else status)
        if output:
            self._output_lbl.setText(f"Output: {output}" if not output.lower().startswith("output:") else output)
        if percent is not None:
            pct = max(0, min(100, int(percent)))
            self._pct.setText(f"{pct}%")
            self._bar.setValue(pct)
        self._foot.setText(footer)
        self._active = True
        self._workspace_locked = False
        if percent is not None and int(percent) > 10:
            self.show()

    def finish_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._active = False
        self._workspace_locked = True
        self._title.setText("Task Complete")
        self._status_lbl.setText(f"Status: {status}")
        self._output_lbl.setText(f"Output: {result or 'Done.'}")
        self._pct.setText(f"{max(0, min(100, percent))}%")
        self._bar.setValue(max(0, min(100, percent)))
        self._foot.setText("Resetting workspace shortly...")
        self.show()
        QTimer.singleShot(5000, self.clear_workspace)

    def clear_workspace(self):
        self._active = False
        self._workspace_locked = False
        self._title.setText("Ready")
        self._command_lbl.setText("Command: waiting for input")
        self._plan_lbl.setText("Plan: Nexus Core will generate a task plan after you send a command.")
        self._status_lbl.setText("Status: Idle")
        self._output_lbl.setText("Output: Ready to work.")
        self._pct.setText("0%")
        self._bar.setValue(0)
        self._foot.setText("Working on it...")
        self.hide()


class AttachmentCard(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentCard")
        self.setStyleSheet("""
            QFrame#AttachmentCard {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(0, 229, 255,0.26);
                border-radius: 10px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)
        icon = QLabel("⎙")
        icon.setFixedSize(26, 26)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: #00e5ff; background: rgba(255,255,255,0.03); border-radius: 13px; font-size: 14px;")
        lay.addWidget(icon)
        txt = QVBoxLayout()
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color: #ffffff; background: transparent; font: 600 9pt 'Segoe UI';")
        s = QLabel(subtitle)
        s.setStyleSheet("color: rgba(255,255,255,0.62); background: transparent; font: 8pt 'Segoe UI';")
        txt.addWidget(t)
        txt.addWidget(s)
        lay.addLayout(txt, 1)


class EventCard(QFrame):
    def __init__(self, title: str, detail: str, stamp: str, icon: str = "●", accent: str = "#00e5ff", parent=None):
        super().__init__(parent)
        self.setObjectName("EventCard")
        self.setStyleSheet(
            f"""
            QFrame#EventCard {{
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(0, 229, 255,0.15);
                border-radius: 12px;
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 12, 6)
        lay.setSpacing(8)

        icon_lbl = QLabel(icon[:1])
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"background: transparent; color: {accent};")
        lay.addWidget(icon_lbl)

        clean_detail = (detail or "").strip()
        if len(clean_detail) > 160:
            clean_detail = clean_detail[:157] + "..."
        full_text = f"{title}: {clean_detail}" if clean_detail and clean_detail != title else title
        title_lbl = QLabel(full_text)
        title_lbl.setFont(QFont("Segoe UI", 9))
        title_lbl.setWordWrap(True)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        lay.addWidget(title_lbl, 1)
        
        stamp_lbl = QLabel(stamp)
        stamp_lbl.setFont(QFont("Segoe UI", 7))
        stamp_lbl.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        lay.addWidget(stamp_lbl)


class ArtifactCard(QFrame):
    def __init__(self, title: str, file_type: str = "File", status: str = "Generated", path: str = "", parent=None):
        super().__init__(parent)
        self._path = path.strip()
        self.setObjectName("ArtifactCard")
        self.setStyleSheet(
            """
            QFrame#ArtifactCard {
                background: rgba(11, 12, 16, 230);
                border: 1px solid rgba(0, 229, 255,0.22);
                border-radius: 12px;
            }
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255,0.08);
                border: 1px solid rgba(0, 229, 255,0.35);
            }
            QPushButton:disabled {
                color: rgba(255,255,255,0.35);
            }
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        badge = QLabel("↗")
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        badge.setStyleSheet("background: rgba(0, 229, 255,0.08); color: #00e5ff; border: 1px solid rgba(0, 229, 255,0.24); border-radius: 15px;")
        head.addWidget(badge)

        meta = QVBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(2)
        name_lbl = QLabel(title or "Generated file")
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        type_lbl = QLabel(f"{file_type} • {status}")
        type_lbl.setFont(QFont("Segoe UI", 8))
        type_lbl.setStyleSheet("color: rgba(255,255,255,0.62); background: transparent;")
        meta.addWidget(name_lbl)
        meta.addWidget(type_lbl)
        head.addLayout(meta, 1)
        lay.addLayout(head)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._open_btn = QPushButton("Open")
        self._reveal_btn = QPushButton("Reveal Folder")
        self._open_btn.clicked.connect(self._open_file)
        self._reveal_btn.clicked.connect(self._reveal_file)
        if not self._path or not Path(self._path).exists():
            self._open_btn.setEnabled(False)
            self._reveal_btn.setEnabled(False)
        btn_row.addWidget(self._open_btn)
        btn_row.addWidget(self._reveal_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

    def _open_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(self._path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._path)])
            else:
                subprocess.Popen(["xdg-open", str(self._path)])
        except Exception:
            pass

    def _reveal_file(self):
        if not self._path or not Path(self._path).exists():
            return
        try:
            import subprocess
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", self._path])
            elif sys.platform == "darwin":
                # Reveal the file/folder in Finder.
                subprocess.Popen(["open", "-R", str(self._path)])
            else:
                subprocess.Popen(["xdg-open", str(Path(self._path).parent)])
        except Exception:
            pass
