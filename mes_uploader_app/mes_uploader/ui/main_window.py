# -*- coding: utf-8 -*-
"""Cửa sổ chính: header + 2 panel Trái / Phải độc lập + nút Setting."""

from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from ..config import save_config
from ..i18n import tr, set_language, add_listener, remove_listener
from .side_panel import SidePanel
from .settings_dialog import SettingsDialog
from .theme import GREEN, AMBER


class MainWindow(QMainWindow):
    def __init__(self, cfg, config_path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        set_language(getattr(cfg, "language", "vi"))   # áp dụng ngôn ngữ đã lưu
        self.setWindowTitle(tr("MES Uploader — Tải nội dung đo lên MES"))
        self.resize(1280, 860)
        self.setMinimumSize(1040, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        panels = QHBoxLayout()
        panels.setSpacing(12)
        self.left = SidePanel("left", cfg)
        self.right = SidePanel("right", cfg)
        panels.addWidget(self.left, 1)
        panels.addWidget(self.right, 1)
        root.addLayout(panels, 1)

        self._update_mode_label()
        add_listener(self.retranslate)   # đổi ngôn ngữ -> cập nhật toàn bộ văn bản

    def _build_header(self):
        header = QFrame(); header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 12, 14, 12)
        h.setSpacing(13)

        logo = QFrame(); logo.setObjectName("logoMark")
        logo.setFixedSize(42, 42)
        h.addWidget(logo)

        titles = QVBoxLayout(); titles.setSpacing(1)
        t = QLabel("MES UPLOADER"); t.setObjectName("appTitle")
        self.lbl_subtitle = QLabel(tr("Tải nội dung đo lên hệ thống MES"))
        self.lbl_subtitle.setObjectName("muted")
        titles.addWidget(t); titles.addWidget(self.lbl_subtitle)
        h.addLayout(titles)
        h.addStretch(1)

        self.lbl_clock = QLabel(); self.lbl_clock.setObjectName("clock")
        self.lbl_clock.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.lbl_clock)
        self._tick_clock()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)

        self.lbl_mode = QLabel(); self.lbl_mode.setObjectName("badge")
        h.addWidget(self.lbl_mode)
        self.btn_settings = QPushButton("⚙  " + tr("Setting"))
        self.btn_settings.setObjectName("settingsBtn")
        self.btn_settings.clicked.connect(self._open_settings)
        h.addWidget(self.btn_settings)
        return header

    def _tick_clock(self):
        now = QDateTime.currentDateTime()
        self.lbl_clock.setText(
            "<b style='color:#e6eaf2;letter-spacing:1px'>%s</b>&nbsp;&nbsp;"
            "<span style='color:#626d7e'>%s</span>"
            % (now.toString("HH:mm:ss"), now.toString("dd/MM/yyyy")))

    def _update_mode_label(self):
        if self.cfg.simulation:
            self.lbl_mode.setText(
                '<span style="color:%s">●</span>&nbsp; %s'
                % (AMBER, tr("Chế độ GIẢ LẬP")))
        else:
            self.lbl_mode.setText(
                '<span style="color:%s">●</span>&nbsp; %s'
                % (GREEN, tr("Chế độ THẬT (PLC + scan)")))

    def retranslate(self):
        """Cập nhật lại toàn bộ văn bản tĩnh khi đổi ngôn ngữ."""
        self.setWindowTitle(tr("MES Uploader — Tải nội dung đo lên MES"))
        self.lbl_subtitle.setText(tr("Tải nội dung đo lên hệ thống MES"))
        self.btn_settings.setText("⚙  " + tr("Setting"))
        self._update_mode_label()
        self.left.retranslate()
        self.right.retranslate()

    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg = dlg.result_config()
            try:
                save_config(self.cfg, self.config_path)
            except Exception as ex:          # noqa: BLE001
                QMessageBox.warning(self, tr("Lưu cấu hình"),
                                    tr("Không lưu được file cấu hình:\n%s") % ex)
            self.left.apply_config(self.cfg)
            self.right.apply_config(self.cfg)
            self._update_mode_label()
            QMessageBox.information(
                self, tr("Setting"),
                tr("Đã lưu cấu hình. Bấm 'Bắt đầu' lại ở mỗi bên để áp dụng."))

    def closeEvent(self, event):
        remove_listener(self.retranslate)
        self.left.stop_worker()
        self.right.stop_worker()
        super().closeEvent(event)
