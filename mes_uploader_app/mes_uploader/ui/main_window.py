# -*- coding: utf-8 -*-
"""Cửa sổ chính: header + 2 panel Trái / Phải độc lập + nút Setting."""

from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from ..config import save_config, app_mode
from ..hardware.plc_client import make_shared_plc
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

        self.plc = None                  # kết nối PLC DÙNG CHUNG cho cả app
        self._rebuild_plc()              # tạo client + cấp cho 2 panel
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
        self.btn_plc = QPushButton(tr("Kết nối PLC"))
        self.btn_plc.setObjectName("settingsBtn")
        self.btn_plc.clicked.connect(self._toggle_plc)
        h.addWidget(self.btn_plc)
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

    # ------------------------------------------------------------------ #
    #  Kết nối PLC DÙNG CHUNG (1 kết nối cho cả app)                       #
    # ------------------------------------------------------------------ #
    def _rebuild_plc(self):
        """Tạo lại client PLC dùng chung từ cấu hình + cấp cho 2 panel."""
        if self.plc is not None:
            try:
                self.plc.close()
            except Exception:                # noqa: BLE001
                pass
        self.plc = make_shared_plc(self.cfg)
        if self.cfg.simulation:              # giả lập: "kết nối" ngay (Mock)
            try:
                self.plc.connect()
            except Exception:                # noqa: BLE001
                pass
        self.left.set_plc(self.plc)
        self.right.set_plc(self.plc)
        self._update_plc_button()

    def _plc_connected(self):
        return bool(self.plc is not None and getattr(self.plc, "is_connected", False))

    def _toggle_plc(self):
        if self.cfg.simulation:
            QMessageBox.information(self, tr("Kết nối PLC"),
                                   tr("Đang ở chế độ GIẢ LẬP — không cần kết nối PLC."))
            return
        if self._plc_connected():            # đang nối -> ngắt (dừng 2 bên trước)
            self.left.stop_worker()
            self.right.stop_worker()
            try:
                self.plc.close()
            except Exception:                # noqa: BLE001
                pass
            self._update_plc_button()
            return
        try:                                 # chưa nối -> kết nối 1 lần
            self.plc.connect()
            QMessageBox.information(
                self, tr("Kết nối PLC"),
                tr("Kết nối PLC %s:%s thành công.")
                % (self.cfg.plc.ip, self.cfg.plc.port))
        except Exception as ex:              # noqa: BLE001
            QMessageBox.critical(self, tr("Kết nối PLC"),
                                 tr("Lỗi kết nối PLC:\n%s") % ex)
        self._update_plc_button()

    def _update_plc_button(self):
        if self.cfg.simulation:
            self.btn_plc.setText(tr("PLC: giả lập"))
            self.btn_plc.setStyleSheet("")
            return
        if self._plc_connected():
            self.btn_plc.setText("●  " + tr("PLC đã kết nối"))
            self.btn_plc.setStyleSheet("color:%s; font-weight:700;" % GREEN)
        else:
            self.btn_plc.setText(tr("Kết nối PLC"))
            self.btn_plc.setStyleSheet("color:%s; font-weight:700;" % AMBER)

    def _update_mode_label(self):
        mode = app_mode(self.cfg)
        if mode == "sim":
            color, text = AMBER, tr("Chế độ GIẢ LẬP")
        elif mode == "manual_sn":
            color, text = AMBER, tr("Chế độ PLC THẬT + SN tay")
        else:
            color, text = GREEN, tr("Chế độ THẬT (PLC + scan)")
        self.lbl_mode.setText(
            '<span style="color:%s">●</span>&nbsp; %s' % (color, text))

    def retranslate(self):
        """Cập nhật lại toàn bộ văn bản tĩnh khi đổi ngôn ngữ."""
        self.setWindowTitle(tr("MES Uploader — Tải nội dung đo lên MES"))
        self.lbl_subtitle.setText(tr("Tải nội dung đo lên hệ thống MES"))
        self.btn_settings.setText("⚙  " + tr("Setting"))
        self._update_mode_label()
        self._update_plc_button()
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
            self._rebuild_plc()          # cấu hình PLC có thể đổi -> tạo lại kết nối
            self._update_mode_label()
            QMessageBox.information(
                self, tr("Setting"),
                tr("Đã lưu cấu hình. Bấm 'Kết nối PLC' rồi 'Bắt đầu' ở mỗi bên."))

    def closeEvent(self, event):
        remove_listener(self.retranslate)
        self.left.stop_worker()
        self.right.stop_worker()
        if self.plc is not None:
            try:
                self.plc.close()
            except Exception:                # noqa: BLE001
                pass
        super().closeEvent(event)
