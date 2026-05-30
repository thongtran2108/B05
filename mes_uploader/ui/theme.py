# -*- coding: utf-8 -*-
"""Theme tối (dark) chuyên nghiệp cho toàn ứng dụng.

apply_dark_theme(app): đặt style Fusion + bảng màu tối + QSS đồng bộ cho
mọi widget (group box dạng card, nút bo góc, bảng, thanh tiến độ, …).
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt


# Bảng màu chủ đạo
BG = "#15181f"          # nền cửa sổ
CARD = "#1d212b"        # nền panel / card
ELEV = "#20242e"        # nền ô nhập / bảng
ELEV2 = "#232a38"       # nền nổi (card SN, header bảng)
BORDER = "#2a303b"      # viền nhạt
BORDER2 = "#36425a"     # viền nổi
TEXT = "#d7dce5"        # chữ chính
MUTED = "#8b94a7"       # chữ phụ
CAPTION = "#6f7a92"     # nhãn nhỏ
ACCENT = "#4c8dff"      # xanh nhấn
GREEN = "#27c281"
RED = "#e5484d"
AMBER = "#e0913a"


DARK_QSS = f"""
* {{
    font-family: "Segoe UI", "Roboto", "Noto Sans", "Arial";
    font-size: 13px;
}}
QWidget {{
    background-color: {BG};
    color: {TEXT};
}}
QToolTip {{
    background-color: {ELEV2};
    color: {TEXT};
    border: 1px solid {BORDER2};
    padding: 5px 7px;
    border-radius: 4px;
}}

/* ---- Card / GroupBox ---- */
QGroupBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 16px;
    padding: 12px 12px 10px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 3px 12px;
    color: #9fb4d8;
    background-color: {ELEV2};
    border: 1px solid {BORDER2};
    border-radius: 7px;
    font-weight: 700;
}}

QLabel {{ background: transparent; }}
QLabel#caption {{
    color: {CAPTION};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#muted {{ color: {MUTED}; }}

/* ---- Card SN ---- */
QFrame#snCard {{
    background-color: {ELEV2};
    border: 1px solid {BORDER2};
    border-radius: 10px;
}}
QLabel#snValue {{
    font-size: 22px;
    font-weight: 800;
    color: #eaf0fb;
}}

/* ---- Nút ---- */
QPushButton {{
    background-color: {ELEV};
    border: 1px solid {BORDER2};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #2b313d; }}
QPushButton:pressed {{ background-color: #1b1f27; }}
QPushButton:disabled {{ color: #56607a; background-color: #1a1d25; border-color: {BORDER}; }}

QPushButton#startBtn {{
    background-color: #1f7a4d; border: 1px solid #25925d;
    color: #eafff4; font-weight: 700;
}}
QPushButton#startBtn:hover {{ background-color: #25925d; }}
QPushButton#startBtn:disabled {{ background-color: #1a2a22; border-color: #234b39; color: #5d7d6c; }}

QPushButton#stopBtn {{
    background-color: #7d2a2e; border: 1px solid #a3373c;
    color: #ffecec; font-weight: 700;
}}
QPushButton#stopBtn:hover {{ background-color: #a3373c; }}
QPushButton#stopBtn:disabled {{ background-color: #2a1d1e; border-color: #4a2a2c; color: #7d5c5e; }}

QPushButton#settingsBtn, QPushButton#ghostBtn {{
    background-color: #2a3340; border: 1px solid {BORDER2};
}}
QPushButton#settingsBtn:hover, QPushButton#ghostBtn:hover {{ background-color: #323c4c; }}

/* ---- Ô nhập ---- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {ELEV};
    border: 1px solid {BORDER2};
    border-radius: 7px;
    padding: 5px 9px;
    selection-background-color: {ACCENT};
    selection-color: white;
    min-height: 18px;
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9fb4d8;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {ELEV};
    border: 1px solid {BORDER2};
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: 0;
}}

/* ---- Thanh tiến độ ---- */
QProgressBar {{
    background-color: {ELEV};
    border: 1px solid {BORDER};
    border-radius: 8px;
    height: 18px;
    text-align: center;
    color: {TEXT};
    font-weight: 600;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 7px;
}}

/* ---- Bảng ---- */
QTableWidget, QTableView {{
    background-color: {ELEV};
    alternate-background-color: #1a1e27;
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: #2d3a52;
    selection-color: #ffffff;
}}
QTableWidget::item {{ padding: 4px 6px; }}
QHeaderView::section {{
    background-color: {ELEV2};
    color: #9fb4d8;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
}}
QTableCornerButton::section {{ background-color: {ELEV2}; border: none; }}

/* ---- Log ---- */
QPlainTextEdit {{
    background-color: {ELEV};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    selection-background-color: {ACCENT};
}}

/* ---- Tabs (Setting) ---- */
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{
    background: {CARD};
    color: {MUTED};
    padding: 7px 16px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {ELEV}; color: {TEXT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* ---- Header app ---- */
QFrame#header {{
    background-color: #1a1e27;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#appTitle {{
    font-size: 17px;
    font-weight: 800;
    color: #eaf0fb;
    letter-spacing: 1px;
}}
QLabel#badge {{
    background-color: #222a36;
    color: #9fb4d8;
    border: 1px solid {BORDER2};
    border-radius: 12px;
    padding: 5px 14px;
    font-weight: 700;
}}

/* ---- Splitter & Scrollbar ---- */
QSplitter::handle {{ background: transparent; height: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333a47; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #404a5c; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #333a47; border-radius: 5px; min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: #404a5c; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QDialog {{ background-color: {BG}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {BORDER2}; background: {ELEV};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
"""


def apply_dark_theme(app):
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(ELEV))
    pal.setColor(QPalette.AlternateBase, QColor("#1a1e27"))
    pal.setColor(QPalette.ToolTipBase, QColor(ELEV2))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(ELEV))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#56607a"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#56607a"))
    app.setPalette(pal)

    app.setStyleSheet(DARK_QSS)
