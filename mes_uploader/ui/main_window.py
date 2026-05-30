# -*- coding: utf-8 -*-
"""Cửa sổ chính: 2 panel Trái / Phải hoạt động độc lập + nút Setting."""

from PySide6.QtWidgets import (
    QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ..config import save_config
from .side_panel import SidePanel
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, cfg, config_path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.setWindowTitle("MES Uploader — Tải nội dung đo lên MES")
        self.resize(1100, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # thanh công cụ trên cùng
        top = QHBoxLayout()
        self.btn_settings = QPushButton("⚙ Setting")
        self.btn_settings.clicked.connect(self._open_settings)
        top.addWidget(self.btn_settings)
        top.addStretch(1)
        self.lbl_mode = QPushButton()
        self.lbl_mode.setEnabled(False)
        top.addWidget(self.lbl_mode)
        root.addLayout(top)

        # 2 panel
        panels = QHBoxLayout()
        self.left = SidePanel("left", cfg)
        self.right = SidePanel("right", cfg)
        panels.addWidget(self.left, 1)
        panels.addWidget(self.right, 1)
        root.addLayout(panels, 1)

        self._update_mode_label()

    def _update_mode_label(self):
        self.lbl_mode.setText("Chế độ: GIẢ LẬP" if self.cfg.simulation
                              else "Chế độ: THẬT (PLC + scan)")

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
