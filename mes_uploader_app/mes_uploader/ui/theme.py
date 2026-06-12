# -*- coding: utf-8 -*-
"""Theme tối (dark) chuyên nghiệp cho toàn ứng dụng — phiên bản tinh chỉnh.

apply_dark_theme(app): đặt style Fusion + bảng màu tối + QSS đồng bộ cho
mọi widget (panel dạng card, nút bo góc, segmented control, chip trạng thái,
card SN, thanh đầu đo dạng segment, bảng, nhật ký monospace, …).
"""

from PySide6.QtGui import QColor, QPalette


# ---------------------------------------------------------------------- #
#  Bảng màu chủ đạo                                                       #
# ---------------------------------------------------------------------- #
BG = "#0e1116"          # nền cửa sổ
BG2 = "#0b0e12"         # nền lõm (bảng, nhật ký, segmented)
CARD = "#161b23"        # nền panel / card
ELEV = "#1b222c"        # nền ô nhập
ELEV2 = "#212a36"       # nền nổi (card SN, header section, segment)
BORDER = "#252e3a"      # viền nhạt
BORDER2 = "#323d4d"     # viền nổi
TEXT = "#e6eaf2"        # chữ chính
MUTED = "#909bad"       # chữ phụ
CAPTION = "#626d7e"     # nhãn nhỏ
ACCENT = "#4c8dff"      # xanh nhấn (CCD1)
ACCENT2 = "#2bc6c0"     # xanh ngọc (CCD2)
GREEN = "#2bbd73"
RED = "#ef5552"
AMBER = "#e2973f"

# Font: ưu tiên IBM Plex (nếu máy có cài), nếu không tự lùi về Segoe UI.
SANS = '"IBM Plex Sans", "Segoe UI", "Roboto", "Noto Sans", "Arial"'
MONO = '"IBM Plex Mono", "Consolas", "Menlo", "DejaVu Sans Mono", monospace'


DARK_QSS = f"""
* {{
    font-family: {SANS};
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
    padding: 5px 8px;
    border-radius: 6px;
}}

/* ---- Panel / GroupBox (card 1 bên) ---- */
QGroupBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 18px;
    padding: 14px 16px 14px 16px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 7px 13px;
    color: #dfe7f4;
    background-color: {ELEV2};
    border: 1px solid {BORDER2};
    border-radius: 9px;
    font-size: 12px;
    font-weight: 700;
}}
QGroupBox#panelRight::title {{
    color: #d3f3f0;
    background-color: #15302f;
    border-color: #1f5350;
}}
QGroupBox#panelLeft::title {{
    color: #dce8ff;
    background-color: #16243d;
    border-color: #284064;
}}

QLabel {{ background: transparent; }}
QLabel#caption {{
    color: {CAPTION};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.6px;
}}
QLabel#muted {{ color: {MUTED}; }}

/* ---- Chip trạng thái (PLC / state) ---- */
QFrame#chip {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel#chipText {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
    padding: 0;
}}

/* ---- Card SN (hero) ---- */
QFrame#snCard {{
    background-color: {BG2};
    border: 1px solid {BORDER2};
    border-radius: 13px;
}}
QLabel#snValue {{
    font-family: {MONO};
    font-size: 27px;
    font-weight: 600;
    letter-spacing: 2px;
    color: #f2f6fc;
}}

/* ---- Nút ---- */
QPushButton {{
    background-color: {ELEV2};
    border: 1px solid {BORDER2};
    border-radius: 10px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #2a3340; }}
QPushButton:pressed {{ background-color: #1a212b; }}
QPushButton:disabled {{ color: #56607a; background-color: #161c24; border-color: {BORDER}; }}

QPushButton#startBtn {{
    background-color: #1f9a5c; border: 1px solid #2bbd73;
    color: #eafff4; font-weight: 700; padding: 12px 14px;
}}
QPushButton#startBtn:hover {{ background-color: #25b06a; }}
QPushButton#startBtn:disabled {{ background-color: #15281f; border-color: #1f4634; color: #5d7d6c; }}

QPushButton#stopBtn {{
    background-color: {ELEV}; border: 1px solid #3a4452;
    color: {MUTED}; font-weight: 700; padding: 12px 14px;
}}
QPushButton#stopBtn:hover {{ background-color: #2a1d20; border-color: #5a2f33; color: #f0b6b8; }}
QPushButton#stopBtn:disabled {{ background-color: #161c24; border-color: {BORDER}; color: #4a5263; }}

QPushButton#settingsBtn, QPushButton#ghostBtn {{
    background-color: {ELEV2}; border: 1px solid {BORDER2}; font-weight: 600;
}}
QPushButton#settingsBtn:hover, QPushButton#ghostBtn:hover {{ background-color: #2a3543; border-color: #3c4a5e; }}

/* ---- Segmented control (loại đầu 4X / 8X / 16X) ---- */
QFrame#segGroup {{
    background-color: {BG2};
    border: 1px solid {BORDER2};
    border-radius: 9px;
}}
QPushButton#segBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    color: {MUTED};
    font-weight: 600;
}}
QPushButton#segBtn:hover {{ color: {TEXT}; background: rgba(255,255,255,0.04); }}
QPushButton#segBtn:checked {{ background-color: {ACCENT}; color: #ffffff; }}
QGroupBox#panelRight QPushButton#segBtn:checked {{ background-color: {ACCENT2}; color: #06201f; }}

/* ---- Segment đầu đo (head progress) ---- */
QFrame#headSeg {{
    background-color: {ELEV2};
    border: 1px solid {BORDER};
    border-radius: 5px;
}}
QFrame#headSeg[done="true"] {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QGroupBox#panelRight QFrame#headSeg[done="true"] {{
    background-color: {ACCENT2};
    border-color: {ACCENT2};
}}

/* ---- Ô nhập ---- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {ELEV};
    border: 1px solid {BORDER2};
    border-radius: 9px;
    padding: 8px 11px;
    selection-background-color: {ACCENT};
    selection-color: white;
    min-height: 20px;
}}
QComboBox:hover, QLineEdit:hover {{ border-color: #3c4a5e; }}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9fb4d8;
    margin-right: 9px;
}}
QComboBox QAbstractItemView {{
    background-color: {ELEV};
    border: 1px solid {BORDER2};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: 0;
    padding: 4px;
}}

/* ---- Bảng ---- */
QTableWidget, QTableView {{
    background-color: {BG2};
    alternate-background-color: #12171e;
    gridline-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 11px;
    selection-background-color: #243044;
    selection-color: #ffffff;
}}
QTableWidget::item {{ padding: 5px 7px; border-bottom: 1px solid #1a212b; }}
QHeaderView::section {{
    background-color: {ELEV};
    color: #9fb0c8;
    padding: 8px 9px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    font-weight: 700;
}}
QTableCornerButton::section {{ background-color: {ELEV}; border: none; }}

/* ---- Nhật ký ---- */
QPlainTextEdit {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 11px;
    padding: 10px 12px;
    font-family: {MONO};
    font-size: 14px;
    line-height: 150%;
    color: #9aa6b6;
    selection-background-color: {ACCENT};
}}

/* ---- Tabs (Setting) ---- */
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{
    background: {CARD};
    color: {MUTED};
    padding: 8px 17px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 3px;
}}
QTabBar::tab:selected {{ background: {ELEV}; color: {TEXT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* ---- Header app ---- */
QFrame#header {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#logoMark {{
    background-color: {ACCENT};
    border: 1px solid #6aa0ff;
    border-radius: 11px;
}}
QLabel#appTitle {{
    font-size: 18px;
    font-weight: 800;
    color: #f2f6fc;
    letter-spacing: 1.5px;
}}
QLabel#clock {{
    font-family: {MONO};
    color: {MUTED};
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 12px;
    font-size: 12px;
}}
QLabel#badge {{
    background-color: {ELEV2};
    color: #cdd6e4;
    border: 1px solid {BORDER2};
    border-radius: 999px;
    padding: 8px 16px;
    font-weight: 600;
}}

/* ---- Vùng cuộn nội dung panel (giữ nền card xuyên qua, bỏ viền) ---- */
QScrollArea#panelScroll {{ background: transparent; border: none; }}
QScrollArea#panelScroll > QWidget {{ background: transparent; }}
QWidget#panelScrollBody {{ background: transparent; }}

/* ---- Splitter & Scrollbar ---- */
QSplitter::handle {{ background: transparent; height: 10px; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333d4c; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #41506a; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #333d4c; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: #41506a; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QDialog {{ background-color: {BG}; }}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px; border-radius: 5px;
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
    pal.setColor(QPalette.AlternateBase, QColor("#12171e"))
    pal.setColor(QPalette.ToolTipBase, QColor(ELEV2))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(ELEV2))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(CAPTION))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#56607a"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#56607a"))
    app.setPalette(pal)

    app.setStyleSheet(DARK_QSS)
