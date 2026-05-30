# -*- coding: utf-8 -*-
"""Panel cho 1 bên (Trái / Phải). Mỗi panel có 1 SideWorker + 1 tay scan riêng.

Sự kiện từ worker (chạy ở luồng nền) được đưa về luồng GUI an toàn qua
signal Qt (_EventBridge) rồi mới cập nhật widget.
"""

from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ..config import side_addresses, head_count
from ..core.side_worker import SideWorker, ST_IDLE, ST_WAIT_SCAN, ST_RUNNING
from ..hardware.plc_client import make_plc_client, MockPlcClient
from ..hardware.scanner import SerialScanner


class _EventBridge(QObject):
    """Cầu nối: phát sự kiện worker (luồng nền) -> slot ở luồng GUI."""
    event = Signal(str, dict)


class SidePanel(QGroupBox):
    def __init__(self, side_key, cfg, parent=None):
        title = "BÊN TRÁI (CCD1)" if side_key == "left" else "BÊN PHẢI (CCD2)"
        super().__init__(title, parent)
        self.side_key = side_key
        self.cfg = cfg
        self.worker = None
        self.scanner = None

        self._bridge = _EventBridge()
        self._bridge.event.connect(self._on_event)

        self._build_ui()
        self._reload_materials()

    # ------------------------------------------------------------------ #
    #  Dựng widget                                                        #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Hàng chọn mã liệu + loại đầu ---
        sel = QHBoxLayout()
        sel.addWidget(QLabel("Mã liệu:"))
        self.cbo_material = QComboBox()
        self.cbo_material.setMinimumWidth(120)
        sel.addWidget(self.cbo_material, 1)
        sel.addWidget(QLabel("Loại đầu:"))
        self.cbo_type = QComboBox()
        self.cbo_type.addItems(["8X", "16X"])
        sel.addWidget(self.cbo_type)
        root.addLayout(sel)
        self.cbo_material.currentIndexChanged.connect(self._selection_changed)
        self.cbo_type.currentIndexChanged.connect(self._selection_changed)

        # --- Trạng thái + đèn PLC ---
        srow = QHBoxLayout()
        self.lbl_plc = QLabel("● PLC: --")
        self.lbl_state = QLabel("Trạng thái: chưa bật")
        srow.addWidget(self.lbl_plc)
        srow.addStretch(1)
        srow.addWidget(self.lbl_state)
        root.addLayout(srow)

        # --- SN lớn ---
        self.lbl_sn = QLabel("SN: ——")
        f = QFont(); f.setPointSize(16); f.setBold(True)
        self.lbl_sn.setFont(f)
        self.lbl_sn.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_sn)

        # --- Tiến độ ---
        self.progress = QProgressBar()
        self.progress.setFormat("Đầu %v/%m")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        # --- Kết quả lớn ---
        self.lbl_result = QLabel("——")
        fr = QFont(); fr.setPointSize(26); fr.setBold(True)
        self.lbl_result.setFont(fr)
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setMinimumHeight(60)
        self._set_result_style(None)
        root.addWidget(self.lbl_result)

        # --- Nút Bắt đầu / Dừng ---
        brow = QHBoxLayout()
        self.btn_start = QPushButton("Bắt đầu")
        self.btn_stop = QPushButton("Dừng")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        brow.addWidget(self.btn_start)
        brow.addWidget(self.btn_stop)
        root.addLayout(brow)

        # --- Khu giả lập (chỉ hiện khi simulation) ---
        self.sim_box = QWidget()
        sbl = QHBoxLayout(self.sim_box)
        sbl.setContentsMargins(0, 0, 0, 0)
        self.txt_sn = QLineEdit()
        self.txt_sn.setPlaceholderText("Nhập SN giả lập…")
        self.btn_scan = QPushButton("Quét (giả lập)")
        self.btn_trig = QPushButton("Tín hiệu PLC (giả lập)")
        self.btn_scan.clicked.connect(self._on_sim_scan)
        self.btn_trig.clicked.connect(self._on_sim_trigger)
        self.txt_sn.returnPressed.connect(self._on_sim_scan)
        sbl.addWidget(self.txt_sn, 1)
        sbl.addWidget(self.btn_scan)
        sbl.addWidget(self.btn_trig)
        root.addWidget(self.sim_box)
        self.sim_box.setVisible(self.cfg.simulation)

        # --- Log ---
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMinimumHeight(160)
        root.addWidget(self.log, 1)

    # ------------------------------------------------------------------ #
    #  Cấu hình / mã liệu                                                 #
    # ------------------------------------------------------------------ #
    def apply_config(self, cfg):
        """Áp cấu hình mới (gọi sau khi Setting thay đổi)."""
        self.stop_worker()
        self.cfg = cfg
        self.sim_box.setVisible(cfg.simulation)
        self._reload_materials()

    def _reload_materials(self):
        cur = self.cbo_material.currentText()
        self.cbo_material.blockSignals(True)
        self.cbo_material.clear()
        for m in self.cfg.materials:
            self.cbo_material.addItem(m.name)
        idx = self.cbo_material.findText(cur)
        if idx >= 0:
            self.cbo_material.setCurrentIndex(idx)
        self.cbo_material.blockSignals(False)

    def _current_material(self):
        name = self.cbo_material.currentText()
        for m in self.cfg.materials:
            if m.name == name:
                return m
        return None

    def _current_type(self):
        return self.cbo_type.currentText()

    # ------------------------------------------------------------------ #
    #  Bắt đầu / Dừng worker                                              #
    # ------------------------------------------------------------------ #
    def _on_start(self):
        material = self._current_material()
        head_type = self._current_type()
        if material is None:
            self._append_log("Chưa chọn mã liệu. Vào Setting > Mã liệu để thêm.")
            return
        n = head_count(material, head_type)
        if n <= 0:
            self._append_log("Mã liệu '%s' không có đầu %s." % (material.name, head_type))
            return

        side_cfg = getattr(self.cfg, self.side_key)
        plc = make_plc_client(self.cfg, side_cfg)
        self.worker = SideWorker(self.side_key, self.cfg, plc,
                                 self._emit_event)
        self.worker.start()
        self.worker.arm(material, head_type)

        # tay scan thật (chỉ khi không giả lập)
        if not self.cfg.simulation:
            self.scanner = SerialScanner(
                side_cfg.scanner_port, side_cfg.scanner_baud,
                on_scan=lambda sn: self.worker.submit_sn(sn),
                on_error=lambda msg: self._emit_event("log", text=msg))
            self.scanner.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.cbo_material.setEnabled(False)

    def _on_stop(self):
        self.stop_worker()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cbo_material.setEnabled(True)
        self.lbl_state.setText("Trạng thái: đã dừng")

    def stop_worker(self):
        if self.scanner:
            self.scanner.stop()
            self.scanner = None
        if self.worker:
            self.worker.disarm()
            self.worker.stop()
            self.worker = None

    # ------------------------------------------------------------------ #
    #  Lựa chọn / giả lập                                                 #
    # ------------------------------------------------------------------ #
    def _selection_changed(self):
        if self.worker:
            self.worker.set_selection(self._current_material(), self._current_type())

    def _on_sim_scan(self):
        sn = self.txt_sn.text().strip()
        if not sn:
            return
        if not self.worker:
            self._append_log("Chưa bấm 'Bắt đầu'.")
            return
        self.worker.submit_sn(sn)
        self.txt_sn.clear()

    def _on_sim_trigger(self):
        if not self.worker:
            self._append_log("Chưa bấm 'Bắt đầu'.")
            return
        self.worker.simulate_trigger()

    # ------------------------------------------------------------------ #
    #  Nhận sự kiện worker (đưa về luồng GUI)                             #
    # ------------------------------------------------------------------ #
    def _emit_event(self, etype, **data):
        # gọi từ luồng nền -> phát signal (queued) sang luồng GUI
        self._bridge.event.emit(etype, data)

    @Slot(str, dict)
    def _on_event(self, etype, data):
        if etype == "log":
            self._append_log(data.get("text", ""))
        elif etype == "status":
            self.lbl_state.setText("Trạng thái: " + data.get("text", ""))
        elif etype == "sn":
            self.lbl_sn.setText("SN: " + data.get("sn", "——"))
            self._set_result_style(None)
            self.lbl_result.setText("…")
        elif etype == "progress":
            done = data.get("done", 0); total = max(1, data.get("total", 1))
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        elif etype == "result":
            self._show_result(data.get("result", ""), data.get("ok", False))
        elif etype == "plc":
            self._set_plc(data.get("connected", False))
        elif etype == "state":
            st = data.get("state", "")
            label = {ST_IDLE: "chưa bật", ST_WAIT_SCAN: "chờ quét mã",
                     ST_RUNNING: "đang chạy"}.get(st, st)
            self.lbl_state.setText("Trạng thái: " + label)

    # ------------------------------------------------------------------ #
    #  Helper hiển thị                                                    #
    # ------------------------------------------------------------------ #
    def _append_log(self, text):
        if text:
            self.log.appendPlainText(text)

    def _set_plc(self, connected):
        if connected:
            self.lbl_plc.setText("● PLC: kết nối")
            self.lbl_plc.setStyleSheet("color: green;")
        else:
            self.lbl_plc.setText("● PLC: mất kết nối")
            self.lbl_plc.setStyleSheet("color: red;")

    def _set_result_style(self, ok):
        if ok is None:
            self.lbl_result.setStyleSheet(
                "background:#eee; color:#888; border-radius:6px;")
        elif ok:
            self.lbl_result.setStyleSheet(
                "background:#1f8a36; color:white; border-radius:6px;")
        else:
            self.lbl_result.setStyleSheet(
                "background:#c0392b; color:white; border-radius:6px;")

    def _show_result(self, result, ok):
        is_ok = (str(result).upper() == "OK") and ok
        self.lbl_result.setText("OK" if str(result).upper() == "OK" else "NG")
        # ok = đã gửi MES thành công; nếu gửi lỗi thì viền vàng cảnh báo
        if not ok:
            self.lbl_result.setText(
                ("OK" if str(result).upper() == "OK" else "NG") + " (gửi lỗi)")
            self.lbl_result.setStyleSheet(
                "background:#e67e22; color:white; border-radius:6px;")
        else:
            self._set_result_style(str(result).upper() == "OK")
