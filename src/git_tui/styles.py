"""Shared styles, colors, and helpers for Git TUI."""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #
EMERALD = "#22c55e"
AMBER = "#f59e0b"
SKY = "#38bdf8"
CRIMSON = "#ef4444"
VIOLET = "#c084fc"
SLATE_BG = "#0f172a"
SLATE_PANEL = "#1e293b"
SLATE_BORDER = "#334155"
MUTED = "#94a3b8"
TEXT = "#e2e8f0"
FOCUS = SKY


def rgb(hex_color: str) -> QColor:
    return QColor(hex_color)


# --------------------------------------------------------------------------- #
# styled helpers
# --------------------------------------------------------------------------- #
def style_button(btn: QPushButton, kind: str = "primary"):
    base = {
        "primary": (SKY, SLATE_BG),
        "success": (EMERALD, SLATE_BG),
        "danger": (CRIMSON, SLATE_BG),
        "warning": (AMBER, SLATE_BG),
        "accent": (VIOLET, SLATE_BG),
        "ghost": (MUTED, SLATE_PANEL),
    }[kind]
    color, bg = base
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: {bg};
            color: {color};
            border: 1px solid {color};
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {color};
            color: {SLATE_BG};
        }}
        QPushButton:pressed {{
            background: #0f172a;
        }}
        """
    )


def style_input(line_edit: QLineEdit):
    line_edit.setStyleSheet(
        f"""
        QLineEdit {{
            background: #0f172a;
            color: {TEXT};
            border: 1px solid {SLATE_BORDER};
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {FOCUS};
        }}
        """
    )


def style_label(label: QLabel, kind: str = "text"):
    color = {
        "text": TEXT,
        "muted": MUTED,
        "emerald": EMERALD,
        "amber": AMBER,
        "sky": SKY,
        "crimson": CRIMSON,
        "violet": VIOLET,
        "header": SKY,
    }[kind]
    label.setStyleSheet(f"color: {color}; font-size: 13px;")
