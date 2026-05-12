"""Qt Style Sheet generated from a palette.

A single function `build_stylesheet(palette)` returns the QSS string.
Two presets are exported: DARK_PALETTE (default) and LIGHT_PALETTE.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg_app: str
    bg_sidebar: str
    bg_card: str
    bg_card_hover: str
    bg_input: str
    border: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_active: str
    danger: str
    success: str
    statusbar_bg: str


DARK_PALETTE = Palette(
    bg_app="#1a1b1f",
    bg_sidebar="#15161a",
    bg_card="#22232a",
    bg_card_hover="#2a2c34",
    bg_input="#1f2026",
    border="#2c2e36",
    text="#e6e7eb",
    text_dim="#9ba0ab",
    text_faint="#6b7079",
    accent="#7c8cff",
    accent_hover="#9aa6ff",
    accent_active="#5d6cff",
    danger="#ff6b6b",
    success="#4ade80",
    statusbar_bg="#15161a",
)


LIGHT_PALETTE = Palette(
    bg_app="#f5f6f8",
    bg_sidebar="#eceef2",
    bg_card="#ffffff",
    bg_card_hover="#f5f7fb",
    bg_input="#ffffff",
    border="#dadde3",
    text="#1a1b1f",
    text_dim="#5a606b",
    text_faint="#888d97",
    accent="#4a5bff",
    accent_hover="#3947f0",
    accent_active="#2a39d8",
    danger="#dc2626",
    success="#16a34a",
    statusbar_bg="#e6e8ec",
)


THEMES = {"dark": DARK_PALETTE, "light": LIGHT_PALETTE}


def build_stylesheet(p: Palette) -> str:
    info_banner_bg = (
        "rgba(124, 140, 255, 0.10)" if p is DARK_PALETTE
        else "rgba(74, 91, 255, 0.08)"
    )
    info_banner_border = (
        "rgba(124, 140, 255, 0.30)" if p is DARK_PALETTE
        else "rgba(74, 91, 255, 0.25)"
    )
    chip_accent_bg = (
        "rgba(124, 140, 255, 0.20)" if p is DARK_PALETTE
        else "rgba(74, 91, 255, 0.12)"
    )
    chip_accent_border = (
        "rgba(124, 140, 255, 0.40)" if p is DARK_PALETTE
        else "rgba(74, 91, 255, 0.35)"
    )

    return f"""
* {{
    color: {p.text};
    font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#contentArea, QWidget#pageRoot {{
    background-color: {p.bg_app};
}}

QFrame#sidebar {{
    background-color: {p.bg_sidebar};
    border: none;
}}

QLabel#appTitle {{
    color: {p.text};
    font-size: 14px;
    font-weight: 600;
    padding: 14px 18px 18px 18px;
}}

QPushButton#navItem {{
    text-align: left;
    background-color: transparent;
    border: none;
    color: {p.text_dim};
    padding: 10px 18px;
    margin: 1px 8px;
    border-radius: 8px;
    font-size: 13px;
}}

QPushButton#navItem:hover {{
    background-color: {p.bg_card};
    color: {p.text};
}}

QPushButton#navItem:checked {{
    background-color: {p.bg_card};
    color: {p.text};
    font-weight: 600;
    border-left: 3px solid {p.accent};
    padding-left: 15px;
}}

QFrame#topBar {{
    background-color: {p.bg_app};
    border-bottom: 1px solid {p.border};
}}

QLabel#topBarTitle {{
    font-size: 13px;
    color: {p.text_dim};
}}

QPushButton#folderPicker {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 7px 12px;
    color: {p.text};
    text-align: left;
}}

QPushButton#folderPicker:hover {{
    background-color: {p.bg_card_hover};
}}

QLabel#pageTitle {{
    color: {p.text};
    font-size: 22px;
    font-weight: 600;
}}

QLabel#pageSubtitle {{
    color: {p.text_dim};
    font-size: 12px;
}}

QLabel#sectionLabel {{
    color: {p.text_faint};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

QPushButton#primary {{
    background-color: {p.accent};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton#primary:hover {{ background-color: {p.accent_hover}; }}
QPushButton#primary:pressed {{ background-color: {p.accent_active}; }}
QPushButton#primary:disabled {{
    background-color: {p.border};
    color: {p.text_faint};
}}

QPushButton#secondary {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 7px 14px;
    color: {p.text};
}}

QPushButton#secondary:hover {{ background-color: {p.bg_card}; }}

QPushButton#iconBtn {{
    background-color: transparent;
    border: 1px solid {p.border};
    border-radius: 8px;
    color: {p.text_dim};
    padding: 0px;
    font-size: 14px;
}}

QPushButton#iconBtn:hover {{
    background-color: {p.bg_card_hover};
    color: {p.text};
    border-color: {p.text_faint};
}}

QLabel#dragHandle {{
    color: {p.text_faint};
    font-size: 18px;
    padding: 0 6px;
}}

QLabel#dragHandle:hover {{ color: {p.text}; }}

QFrame#card {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

QFrame#card:hover {{ border-color: {p.text_faint}; }}

QFrame#infoBanner {{
    background-color: {info_banner_bg};
    border: 1px solid {info_banner_border};
    border-radius: 10px;
}}

QLabel#infoBannerText {{ color: {p.text_dim}; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p.text};
    selection-background-color: {p.accent};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {p.accent};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {p.bg_card_hover};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {p.bg_card_hover};
    border-radius: 5px;
    min-width: 24px;
}}

QRadioButton {{ color: {p.text}; spacing: 8px; padding: 2px 0; }}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 2px solid {p.text_faint};
    background-color: transparent;
}}

QRadioButton::indicator:hover {{ border-color: {p.text_dim}; }}

QRadioButton::indicator:checked {{
    border-color: {p.accent};
    background-color: {p.accent};
}}

QComboBox QAbstractItemView {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    selection-background-color: {p.accent};
    selection-color: white;
    color: {p.text};
    padding: 4px;
}}

QComboBox::drop-down {{ width: 18px; border: none; }}
QComboBox::down-arrow {{ width: 0; height: 0; }}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {p.bg_card};
    border: none;
    width: 16px;
}}

QSpinBox::up-arrow, QSpinBox::down-arrow {{ width: 0; height: 0; }}

QPlainTextEdit {{
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 12px;
}}

QProgressBar {{
    background-color: {p.bg_input};
    border: none;
    border-radius: 3px;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 3px;
}}

QLabel#chipNeutral {{
    background-color: {p.bg_input};
    color: {p.text_dim};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 2px 10px;
}}

QLabel#chipAccent {{
    background-color: {chip_accent_bg};
    color: {p.accent};
    border: 1px solid {chip_accent_border};
    border-radius: 10px;
    padding: 2px 10px;
}}

QStatusBar {{
    background: {p.statusbar_bg};
    color: {p.text_dim};
    border-top: 1px solid {p.border};
}}

QStatusBar::item {{ border: none; }}

QMenu {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    color: {p.text};
    padding: 4px;
}}

QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {p.accent}; color: white; }}

QToolTip {{
    background-color: {p.bg_card};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 4px 6px;
}}
"""


_active_palette: Palette = DARK_PALETTE


def active_palette() -> Palette:
    """Current palette used by hand-painted widgets (Toggle, ColorDot, Chip)."""
    return _active_palette


def is_dark() -> bool:
    return _active_palette is DARK_PALETTE


# A Qt-style signal that widgets can subscribe to when they need to
# repaint themselves on a theme switch (e.g. Chip, EmptyState, anything
# that hand-applies inline QSS at construction time).
from PySide6.QtCore import QObject, Signal


class _ThemeBus(QObject):
    palette_changed = Signal()


_bus = _ThemeBus()


def palette_signal():
    return _bus.palette_changed


def set_active_palette(p: Palette) -> None:
    global _active_palette
    if p is _active_palette:
        return
    _active_palette = p
    _bus.palette_changed.emit()


# Backwards-compat constants — modules that imported these still work.
STYLESHEET = build_stylesheet(DARK_PALETTE)
