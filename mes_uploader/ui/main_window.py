# -*- coding: utf-8 -*-
"""Cửa sổ chính: header + 2 panel Trái / Phải độc lập + nút Setting."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from ..config import save_config
from .side_panel import SidePanel
from .settings_dialog import SettingsDialog
from .theme import GREEN, AMBER


class MainWindow(QMainWindow):
    def __init__(self, cfg, config_path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.setWindowTitle("MES Uploader — Tải nội dung đo lên MES")
        self.resize(1180, 760)

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

    def _build_header(self):
        header = QFrame(); header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 10, 14, 10)

        titles = QVBoxLayout(); titles.setSpacing(0)
        t = QLabel("MES UPLOADER"); t.setObjectName("appTitle")
        sub = QLabel("Tải nội dung đo lên hệ thống MES"); sub.setObjectName("muted")
        titles.addWidget(t); titles.addWidget(sub)
        h.addLayout(titles)
        h.addStretch(1)

        self.lbl_mode = QLabel(); self.lbl_mode.setObjectName("badge")
        h.addWidget(self.lbl_mode)
        self.btn_settings = QPushButton("⚙  Setting"); self.btn_settings.setObjectName("settingsBtn")
        self.btn_settings.clicked.connect(self._open_settings)
        h.addWidget(self.btn_settings)
        return header

    def _update_mode_label(self):
        if self.cfg.simulation:
            self.lbl_mode.setText(
                '<span style="color:%s">●</span>&nbsp; Chế độ GIẢ LẬP' % AMBER)
        else:
            self.lbl_mode.setText(
                '<span style="color:%s">●</span>&nbsp; Chế độ THẬT (PLC + scan)' % GREEN)

    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg = dlg.result_config()
            try:
                save_config(self.cfg, self.config_path)
            except Exception as ex:          # noqa: BLE001
                QMessageBox.warning(self, "Lưu cấu hình",
                                    "Không lưu được file cấu hình:\n%s" % ex)
            self.left.apply_config(self.cfg)
            self.right.apply_config(self.cfg)
            self._update_mode_label()
            QMessageBox.information(
                self, "Setting",
                "Đã lưu cấu hình. Bấm 'Bắt đầu' lại ở mỗi bên để áp dụng.")

    def closeEvent(self, event):
        self.left.stop_worker()
        self.right.stop_worker()
        super().closeEvent(event)
