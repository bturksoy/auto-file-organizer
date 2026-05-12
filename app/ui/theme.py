"""Qt Style Sheet for the dark theme.

A single QSS string applied at the QApplication level so every widget
inherits consistent colors and shapes. Tweak the palette constants below
to retheme the whole app.
"""

# Palette
BG_APP = "#1a1b1f"
BG_SIDEBAR = "#15161a"
BG_CARD = "#22232a"
BG_CARD_HOVER = "#2a2c34"
BG_INPUT = "#1f2026"
BORDER = "#2c2e36"
TEXT = "#e6e7eb"
TEXT_DIM = "#9ba0ab"
TEXT_FAINT = "#6b7079"
ACCENT = "#7c8cff"
ACCENT_HOVER = "#9aa6ff"
ACCENT_ACTIVE = "#5d6cff"
DANGER = "#ff6b6b"
SUCCESS = "#4ade80"


STYLESHEET = f"""
* {{
    color: {TEXT};
    font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#contentArea, QWidget#pageRoot {{
    background-color: {BG_APP};
}}

/* ------- Sidebar ------- */
QFrame#sidebar {{
    background-color: {BG_SIDEBAR};
    border: none;
}}

QLabel#appTitle {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 600;
    padding: 14px 18px 18px 18px;
}}

QPushButton#navItem {{
    text-align: left;
    background-color: transparent;
    border: none;
    color: {TEXT_DIM};
    padding: 10px 18px;
    margin: 1px 8px;
    border-radius: 8px;
    font-size: 13px;
}}

QPushButton#navItem:hover {{
    background-color: {BG_CARD};
    color: {TEXT};
}}

QPushButton#navItem:checked {{
    background-color: {BG_CARD};
    color: {TEXT};
    font-weight: 600;
    border-left: 3px solid {ACCENT};
    padding-left: 15px;
}}

/* ------- Top bar (folder picker) ------- */
QFrame#topBar {{
    background-color: {BG_APP};
    border-bottom: 1px solid {BORDER};
}}

QLabel#topBarTitle {{
    font-size: 13px;
    color: {TEXT_DIM};
}}

QPushButton#folderPicker {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
    text-align: left;
}}

QPushButton#folderPicker:hover {{
    background-color: {BG_CARD_HOVER};
}}

/* ------- Headings ------- */
QLabel#pageTitle {{
    color: {TEXT};
    font-size: 22px;
    font-weight: 600;
}}

QLabel#pageSubtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QLabel#sectionLabel {{
    color: {TEXT_FAINT};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ------- Primary button ------- */
QPushButton#primary {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primary:pressed {{
    background-color: {ACCENT_ACTIVE};
}}

QPushButton#secondary {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
}}

QPushButton#secondary:hover {{
    background-color: {BG_CARD};
}}

/* Small icon-style buttons (edit / delete / menu / drag handle).
   The text is a unicode glyph so we just need decent contrast + hover. */
QPushButton#iconBtn {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_DIM};
    padding: 0px;
    font-size: 14px;
}}

QPushButton#iconBtn:hover {{
    background-color: {BG_CARD_HOVER};
    color: {TEXT};
    border-color: {TEXT_FAINT};
}}

QPushButton#iconBtnDanger:hover {{
    color: {DANGER};
    border-color: {DANGER};
}}

QLabel#dragHandle {{
    color: {TEXT_FAINT};
    font-size: 18px;
    padding: 0 6px;
}}

QLabel#dragHandle:hover {{
    color: {TEXT};
}}

QPushButton#primary:disabled {{
    background-color: {BORDER};
    color: {TEXT_FAINT};
}}

QFrame#card:hover {{
    border-color: #3a3d46;
}}

/* ------- Cards ------- */
QFrame#card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#infoBanner {{
    background-color: rgba(124, 140, 255, 0.10);
    border: 1px solid rgba(124, 140, 255, 0.30);
    border-radius: 10px;
}}

QLabel#infoBannerText {{
    color: {TEXT_DIM};
}}

/* ------- Inputs ------- */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}

/* ------- ScrollBar ------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BG_CARD_HOVER};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_FAINT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {BG_CARD_HOVER};
    border-radius: 5px;
    min-width: 24px;
}}

/* ------- Toggle switch (we use QCheckBox with custom indicator) ------- */
QCheckBox#toggle::indicator {{
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
}}

QCheckBox#toggle::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ------- Radio buttons ------- */
QRadioButton {{
    color: {TEXT};
    spacing: 8px;
    padding: 2px 0;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 2px solid {TEXT_FAINT};
    background-color: transparent;
}}

QRadioButton::indicator:hover {{
    border-color: {TEXT_DIM};
}}

QRadioButton::indicator:checked {{
    border-color: {ACCENT};
    background-color: {ACCENT};
}}

/* ------- Combo box dropdown contents ------- */
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    color: {TEXT};
    padding: 4px;
}}

QComboBox::drop-down {{
    width: 18px;
    border: none;
}}

QComboBox::down-arrow {{
    width: 0;
    height: 0;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BG_CARD};
    border: none;
    width: 16px;
}}

QSpinBox::up-arrow, QSpinBox::down-arrow {{
    width: 0;
    height: 0;
}}

QPlainTextEdit {{
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 12px;
}}

/* ------- Progress bar ------- */
QProgressBar {{
    background-color: {BG_INPUT};
    border: none;
    border-radius: 3px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ------- Status chip ------- */
QLabel#chipNeutral {{
    background-color: {BG_INPUT};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 2px 10px;
}}

QLabel#chipAccent {{
    background-color: rgba(124, 140, 255, 0.20);
    color: {ACCENT};
    border: 1px solid rgba(124, 140, 255, 0.40);
    border-radius: 10px;
    padding: 2px 10px;
}}
"""
